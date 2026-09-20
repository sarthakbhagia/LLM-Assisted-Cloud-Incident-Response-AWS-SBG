#!/usr/bin/env python3
"""
Evaluation Metrics Computation Engine
Computes MTTR, RCA Accuracy, Hallucination Rate, Diagnosis-Recovery Gap, and Failure Mode Taxonomy.
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Expected action mappings per fault class for rule-based RCA accuracy evaluation
EXPECTED_ACTIONS = {
    "resource_exhaustion": ["scale_up", "restart_service"],
    "misconfiguration": ["lock_s3_bucket", "tighten_iam_policy"],
    "service_cascade": ["restart_downstream_service", "restart_service"],
}

# Key terms per fault class for root cause text matching
KEY_TERMS = {
    "resource_exhaustion": ["cpu", "memory", "exhaustion", "spike", "capacity", "scale", "utilization"],
    "misconfiguration": ["s3", "bucket", "public", "iam", "policy", "permissive", "config", "exposure"],
    "service_cascade": ["cascade", "downstream", "dependency", "service-c", "service-a", "latency", "timeout"],
}


def calculate_mttr(detected_at: str | None, executed_at: str | None) -> float | None:
    """Calculate Mean Time to Remediation in seconds."""
    if not detected_at or not executed_at:
        return None
    try:
        dt_start = datetime.datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
        dt_end = datetime.datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
        return max(0.0, (dt_end - dt_start).total_seconds())
    except (ValueError, TypeError) as exc:
        logger.warning(f"Could not parse timestamps for MTTR ({detected_at}, {executed_at}): {exc}")
        return None


def evaluate_rca_accuracy(record: Dict[str, Any]) -> bool:
    """Evaluate whether the diagnosis root cause matches the ground truth fault class.
    
    Returns False for parse_failed diagnoses.
    """
    diagnosis = record.get("diagnosis", {})
    if diagnosis.get("diagnosis_status") == "parse_failed":
        return False
    
    ground_truth = record.get("ground_truth", {}).get("true_fault_class") or record.get("fault_class")
    if not ground_truth:
        return False

    suggested_action = diagnosis.get("suggested_action")
    root_cause = (diagnosis.get("root_cause") or "").lower()

    # Rule 1: Action matching
    expected_actions = EXPECTED_ACTIONS.get(ground_truth, [])
    action_match = suggested_action in expected_actions

    # Rule 2: Root cause keyword matching
    keywords = KEY_TERMS.get(ground_truth, [])
    keyword_match = any(kw in root_cause for kw in keywords)

    return action_match or keyword_match


def detect_hallucination(record: Dict[str, Any], raw_data: Dict[str, Any] | None = None) -> bool:
    """
    Audit whether the reasoning trace or affected resources reference entity ARNs / metrics
    absent from raw collected data.
    """
    diagnosis = record.get("diagnosis", {})
    reasoning_trace = (diagnosis.get("reasoning_trace") or "").lower()
    affected_resources = diagnosis.get("affected_resources") or []

    if not reasoning_trace and not affected_resources:
        return False

    # Check for hallucinated AWS resources or bogus ARNs
    raw_str = json.dumps(raw_data or {}).lower() if raw_data else ""
    
    # Specific known hallucination indicators for testing/audit:
    hallucination_triggers = ["nonexistent", "fake_arn", "hallucinated_policy", "imaginary_metric"]
    for trigger in hallucination_triggers:
        if trigger in reasoning_trace:
            return True

    # Check if affected resources are present in raw data
    if raw_str:
        for res in affected_resources:
            if isinstance(res, str) and len(res) > 5 and res.lower() not in raw_str:
                return True

    return False


def classify_failure_mode(record: Dict[str, Any], is_rca_correct: bool, is_hallucinated: bool) -> str:
    """Classify the diagnosis failure mode according to the AWS reasoning failure taxonomy."""
    explicit_mode = record.get("diagnosis", {}).get("failure_mode")
    if explicit_mode:
        return explicit_mode

    if is_rca_correct and not is_hallucinated:
        return "none"

    diagnosis = record.get("diagnosis", {})
    trace = (diagnosis.get("reasoning_trace") or "").lower()

    if is_hallucinated or "permission" in trace or "policy" in trace:
        return "hallucinated_permission"
    if "arn" in trace or "resource" in trace:
        return "metric_arn_confusion"
    if "correlation" in trace or "causation" in trace or "cascade" in trace:
        return "correlation_as_causation"

    return "unsupported_action" if not is_rca_correct else "none"


def compute_aggregate_metrics(records: List[Dict[str, Any]], raw_data_map: Dict[str, Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """Compute aggregate evaluation metrics across N incident records."""
    raw_data_map = raw_data_map or {}
    
    total_incidents = len(records)
    if total_incidents == 0:
        return {
            "total_incidents": 0,
            "mttr_seconds_avg": 0.0,
            "rca_accuracy_pct": 0.0,
            "hallucination_rate_pct": 0.0,
            "diagnosis_recovery_gap_pct": 0.0,
            "parse_failed_count": 0,
            "parse_failed_pct": 0.0,
            "failure_taxonomy": {},
            "rag_ablation_comparison": {},
        }

    mttr_list = []
    rca_correct_count = 0
    hallucination_count = 0
    gap_count = 0
    high_confidence_count = 0
    parse_failed_count = 0
    failure_taxonomy: Dict[str, int] = {}
    evaluated_runs: List[Dict[str, Any]] = []

    rag_true_records = []
    rag_false_records = []

    for rec in records:
        inc_id = rec.get("incident_id", "unknown")
        raw = raw_data_map.get(inc_id)

        # Timestamps and MTTR
        det_at = rec.get("detected_at")
        exec_at = rec.get("remediation", {}).get("executed_at")
        mttr = calculate_mttr(det_at, exec_at)
        if mttr is not None:
            mttr_list.append(mttr)

        # Track parse_failed diagnoses
        if rec.get("diagnosis", {}).get("diagnosis_status") == "parse_failed":
            parse_failed_count += 1

        # RCA Accuracy (returns False for parse_failed)
        is_correct = evaluate_rca_accuracy(rec)
        if is_correct:
            rca_correct_count += 1

        # Hallucination
        is_hallucinated = detect_hallucination(rec, raw)
        if is_hallucinated:
            hallucination_count += 1

        # Failure Mode Taxonomy
        f_mode = classify_failure_mode(rec, is_correct, is_hallucinated)
        failure_taxonomy[f_mode] = failure_taxonomy.get(f_mode, 0) + 1

        # Diagnosis-Recovery Gap
        diag_conf = float(rec.get("diagnosis", {}).get("confidence", 0.0))
        verif_status = rec.get("verification", {}).get("status", "not_run")
        if diag_conf >= 0.7:
            high_confidence_count += 1
            if verif_status == "not_resolved":
                gap_count += 1

        # RAG Ablation tracking
        used_rag = rec.get("diagnosis", {}).get("used_rag", True)
        if used_rag:
            rag_true_records.append((is_correct, is_hallucinated))
        else:
            rag_false_records.append((is_correct, is_hallucinated))

        evaluated_runs.append({
            "incident_id": inc_id,
            "fault_class": rec.get("fault_class"),
            "true_fault_class": rec.get("ground_truth", {}).get("true_fault_class") or rec.get("fault_class"),
            "suggested_action": rec.get("diagnosis", {}).get("suggested_action"),
            "confidence": diag_conf,
            "used_rag": used_rag,
            "rca_correct": is_correct,
            "hallucinated": is_hallucinated,
            "diagnosis_status": rec.get("diagnosis", {}).get("diagnosis_status", "success"),
            "mttr_seconds": mttr if mttr is not None else "",
            "verification_status": verif_status,
            "failure_mode": f_mode,
        })

    avg_mttr = round(sum(mttr_list) / len(mttr_list), 2) if mttr_list else 0.0
    rca_acc = round((rca_correct_count / total_incidents) * 100, 2)
    hallucination_rate = round((hallucination_count / total_incidents) * 100, 2)
    diag_gap_pct = round((gap_count / high_confidence_count) * 100, 2) if high_confidence_count > 0 else 0.0
    parse_failed_pct = round((parse_failed_count / total_incidents) * 100, 2)

    # RAG Ablation Summary
    rag_true_acc = round(sum(1 for c, _ in rag_true_records if c) / len(rag_true_records) * 100, 2) if rag_true_records else 0.0
    rag_false_acc = round(sum(1 for c, _ in rag_false_records if c) / len(rag_false_records) * 100, 2) if rag_false_records else 0.0

    return {
        "total_incidents": total_incidents,
        "mttr_seconds_avg": avg_mttr,
        "rca_accuracy_pct": rca_acc,
        "hallucination_rate_pct": hallucination_rate,
        "diagnosis_recovery_gap_pct": diag_gap_pct,
        "parse_failed_count": parse_failed_count,
        "parse_failed_pct": parse_failed_pct,
        "high_confidence_incidents": high_confidence_count,
        "unresolved_high_confidence_incidents": gap_count,
        "failure_taxonomy": failure_taxonomy,
        "rag_ablation_comparison": {
            "used_rag_true": {
                "count": len(rag_true_records),
                "accuracy_pct": rag_true_acc,
            },
            "used_rag_false": {
                "count": len(rag_false_records),
                "accuracy_pct": rag_false_acc,
            },
        },
        "runs": evaluated_runs,
    }
