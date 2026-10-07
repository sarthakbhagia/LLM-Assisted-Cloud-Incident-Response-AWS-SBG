#!/usr/bin/env python3
"""
Evaluation Runner CLI
Runs fault injection trials, queries pipeline records, computes benchmark metrics,
and writes CSV/JSON paper artifacts into evaluation/results/.
"""

import argparse
import csv
import datetime
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, List

# Add repository root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import boto3
from botocore.exceptions import ClientError

from evaluation.metrics import compute_aggregate_metrics
from fault_injection.inject_misconfiguration import inject_misconfiguration
from fault_injection.inject_resource_exhaustion import inject_resource_exhaustion
from fault_injection.inject_service_cascade import inject_service_cascade

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def generate_mock_incidents(num_runs: int = 3, ablation: bool = False) -> List[Dict[str, Any]]:
    """Generate deterministic synthetic incident records for offline evaluation testing."""
    records = []
    fault_classes = ["resource_exhaustion", "misconfiguration", "service_cascade"]
    actions_map = {
        "resource_exhaustion": "scale_up",
        "misconfiguration": "lock_s3_bucket",
        "service_cascade": "restart_downstream_service",
    }

    base_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

    for i in range(num_runs):
        for fc in fault_classes:
            inc_id = str(uuid.uuid4())
            det_dt = base_time + datetime.timedelta(minutes=i * 10)
            exec_dt = det_dt + datetime.timedelta(seconds=45 + (i * 5))
            verif_dt = exec_dt + datetime.timedelta(minutes=2)

            # Introduce realistic variance (e.g. 1 gap / unresolved case, 1 failure mode)
            is_gap_case = (i == num_runs - 1 and fc == "service_cascade")
            verif_status = "not_resolved" if is_gap_case else "resolved"

            failure_mode = "none"
            if is_gap_case:
                failure_mode = "correlation_as_causation"
            elif i == 1 and fc == "misconfiguration":
                failure_mode = "hallucinated_permission"

            rec = {
                "incident_id": inc_id,
                "fault_class": fc,
                "detected_at": det_dt.isoformat(),
                "ground_truth": {
                    "true_fault_class": fc,
                    "injected_at": det_dt.isoformat(),
                },
                "diagnosis": {
                    "root_cause": f"Root cause for {fc}: detected high metric/policy violation in mock run {i}",
                    "confidence": 0.95 if not is_gap_case else 0.85,
                    "affected_resources": [f"mock-resource-{fc}"],
                    "suggested_action": actions_map[fc],
                    "reasoning_trace": f"Reasoning step 1: analyzed telemetry for {fc}. Step 2: recommended {actions_map[fc]}.",
                    "used_rag": not ablation,
                    "failure_mode": failure_mode,
                },
                "remediation": {
                    "status": "executed",
                    "action_taken": actions_map[fc],
                    "executed_at": exec_dt.isoformat(),
                },
                "verification": {
                    "status": verif_status,
                    "checked_at": verif_dt.isoformat(),
                    "signal_rechecked": f"mock_signal_{fc}",
                    "notes": f"Rechecked signal for {fc}: status is {verif_status}",
                },
            }
            records.append(rec)

    return records


def export_results(metrics_summary: Dict[str, Any], output_dir: str) -> List[str]:
    """Write benchmark outputs (summary.json, failure_taxonomy.csv, diagnosis_recovery_gap.csv, raw_evaluation_runs.csv)."""
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []

    # Check if this is a mock run (output_dir ends with /mock)
    is_mock = output_dir.endswith("/mock") or output_dir.endswith("\\mock")

    # 1. Write summary.json
    summary_path = os.path.join(output_dir, "summary.json")
    summary_data = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_incidents": metrics_summary["total_incidents"],
        "mttr_seconds_avg": metrics_summary["mttr_seconds_avg"],
        "rca_accuracy_pct": metrics_summary["rca_accuracy_pct"],
        "hallucination_rate_pct": metrics_summary["hallucination_rate_pct"],
        "diagnosis_recovery_gap_pct": metrics_summary["diagnosis_recovery_gap_pct"],
        "high_confidence_incidents": metrics_summary["high_confidence_incidents"],
        "unresolved_high_confidence_incidents": metrics_summary["unresolved_high_confidence_incidents"],
        "failure_taxonomy": metrics_summary["failure_taxonomy"],
        "rag_ablation_comparison": metrics_summary["rag_ablation_comparison"],
    }
    # Add synthetic metrics if present
    if "synthetic_incidents" in metrics_summary:
        summary_data["synthetic_incidents"] = metrics_summary["synthetic_incidents"]
        summary_data["synthetic_rca_accuracy_pct"] = metrics_summary["synthetic_rca_accuracy_pct"]
        summary_data["synthetic_diagnosis_recovery_gap_pct"] = metrics_summary["synthetic_diagnosis_recovery_gap_pct"]
    if is_mock:
        summary_data["synthetic"] = True
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    generated_files.append(summary_path)

    # 2. Write failure_taxonomy.csv
    taxonomy_path = os.path.join(output_dir, "failure_taxonomy.csv")
    with open(taxonomy_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["failure_mode", "count", "percentage_of_total"])
        total = metrics_summary["total_incidents"] or 1
        for mode, count in metrics_summary["failure_taxonomy"].items():
            pct = round((count / total) * 100, 2)
            writer.writerow([mode, count, pct])
    generated_files.append(taxonomy_path)

    # 3. Write diagnosis_recovery_gap.csv
    gap_path = os.path.join(output_dir, "diagnosis_recovery_gap.csv")
    with open(gap_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_incidents", metrics_summary["total_incidents"]])
        writer.writerow(["high_confidence_incidents", metrics_summary["high_confidence_incidents"]])
        writer.writerow(["unresolved_high_confidence_incidents", metrics_summary["unresolved_high_confidence_incidents"]])
        writer.writerow(["diagnosis_recovery_gap_pct", metrics_summary["diagnosis_recovery_gap_pct"]])
    generated_files.append(gap_path)

    # 4. Write raw_evaluation_runs.csv
    runs_path = os.path.join(output_dir, "raw_evaluation_runs.csv")
    runs = metrics_summary.get("runs", [])
    if runs:
        headers = list(runs[0].keys())
        with open(runs_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(runs)
        generated_files.append(runs_path)

    logger.info(f"Successfully exported benchmark results to {output_dir}: {generated_files}")
    return generated_files


def _wait_for_incident_created(
    fault_class: str,
    injected_at: str,
    incidents_table: str,
    region: str,
    timeout_seconds: int = 60,
    poll_interval_seconds: int = 5,
) -> Dict[str, Any] | None:
    """
    Poll DynamoDB until a NEW incident is created for this injection.
    Returns the incident record or None if timeout.
    """
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(incidents_table)
    injected_dt = datetime.datetime.fromisoformat(injected_at.replace("Z", "+00:00"))
    
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            resp = table.scan(
                FilterExpression="fault_class = :fc",
                ExpressionAttributeValues={":fc": fault_class},
            )
            items = resp.get("Items", [])
            # Filter for incidents created after injection time
            new_items = [
                item for item in items
                if item.get("detected_at") and item["detected_at"] >= injected_at
            ]
            if new_items:
                # Sort by detected_at descending and take the most recent
                new_items.sort(key=lambda x: x.get("detected_at", ""), reverse=True)
                logger.info(f"Found new incident {new_items[0]['incident_id']} for fault_class={fault_class}")
                return new_items[0]
            time.sleep(poll_interval_seconds)
        except ClientError as exc:
            logger.warning(f"Error scanning for new incident: {exc}")
            time.sleep(poll_interval_seconds)
    
    logger.warning(f"Timeout waiting for new incident for fault_class={fault_class} after {timeout_seconds}s")
    return None


def _wait_for_incident_completion(
    incident_id: str,
    incidents_table: str,
    region: str,
    timeout_seconds: int = 600,
    poll_interval_seconds: int = 10,
) -> Dict[str, Any] | None:
    """
    Poll DynamoDB until the incident reaches a terminal state.
    Terminal state: verification.status is set (resolved, not_resolved, inconclusive).
    Returns the incident record or None if timeout.
    """
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(incidents_table)
    
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            resp = table.get_item(Key={"incident_id": incident_id})
            item = resp.get("Item")
            if item:
                verification = item.get("verification", {})
                verif_status = verification.get("status")
                if verif_status in ("resolved", "not_resolved", "inconclusive", "resolved_unverified"):
                    logger.info(f"Incident {incident_id} reached terminal state: {verif_status}")
                    return item
                # Also check if remediation failed
                remediation = item.get("remediation", {})
                if remediation.get("status") == "failed":
                    logger.info(f"Incident {incident_id} remediation failed, treating as terminal")
                    return item
            time.sleep(poll_interval_seconds)
        except ClientError as exc:
            logger.warning(f"Error polling incident {incident_id}: {exc}")
            time.sleep(poll_interval_seconds)
    
    logger.warning(f"Timeout waiting for incident {incident_id} to complete after {timeout_seconds}s")
    # Return the latest state even if not terminal
    try:
        resp = table.get_item(Key={"incident_id": incident_id})
        return resp.get("Item")
    except ClientError:
        return None


def _approve_incident(
    incident_id: str,
    incidents_table: str,
    region: str,
    approved_via: str = "eval_harness",
) -> bool:
    """
    Approve an incident by writing directly to DynamoDB (similar to demo_control).
    Records approved_via as 'eval_harness'.
    """
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(incidents_table)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    try:
        # First check the incident exists and is pending approval
        resp = table.get_item(Key={"incident_id": incident_id})
        item = resp.get("Item")
        if not item:
            logger.error(f"Incident {incident_id} not found for approval")
            return False
        
        remediation_status = (item.get("remediation") or {}).get("status")
        if remediation_status != "pending_approval":
            logger.warning(f"Incident {incident_id} is not pending approval (status: {remediation_status})")
            return False
        
        # Fetch diagnosis to get recommended_solutions for validation
        diagnosis = item.get("diagnosis", {})
        recommended_solutions = diagnosis.get("recommended_solutions")
        fault_class = item.get("fault_class", "unknown")
        suggested_action = diagnosis.get("suggested_action", "manual_review_required")
        
        if not recommended_solutions:
            # Derive using same logic
            fault_class_alternatives = {
                "resource_exhaustion": [
                    {"action": "scale_up", "risk": "low", "source": "runbook"},
                    {"action": "restart_service", "risk": "medium", "source": "runbook"},
                    {"action": "manual_review_required", "risk": "low", "source": "runbook"},
                ],
                "misconfiguration": [
                    {"action": "lock_s3_bucket", "risk": "medium", "source": "runbook"},
                    {"action": "tighten_iam_policy", "risk": "medium", "source": "runbook"},
                    {"action": "manual_review_required", "risk": "low", "source": "runbook"},
                ],
                "service_cascade": [
                    {"action": "restart_downstream_service", "risk": "medium", "source": "runbook"},
                    {"action": "restart_service", "risk": "medium", "source": "runbook"},
                    {"action": "manual_review_required", "risk": "low", "source": "runbook"},
                ],
            }
            alternatives = fault_class_alternatives.get(fault_class, [])
            solutions = []
            seen = set()

            primary_solution = {
                "id": "sol-1",
                "action": suggested_action,
                "title": suggested_action.replace("_", " ").title(),
                "description": f"Apply {suggested_action.replace('_', ' ')} remediation per diagnosis",
                "risk": "medium",
                "expected_outcome": f"Resolve the incident via {suggested_action.replace('_', ' ')}",
                "rationale": "Primary diagnosis suggested action",
                "confidence": 0.9,
                "source": "llm",
            }
            solutions.append(primary_solution)
            seen.add(suggested_action)

            for alt in alternatives:
                action = alt["action"]
                if action in seen:
                    continue
                seen.add(action)

                solutions.append({
                    "id": f"sol-{len(solutions)+1}",
                    "action": action,
                    "title": action.replace("_", " ").title(),
                    "description": f"Apply {action.replace('_', ' ')} remediation per runbook",
                    "risk": alt["risk"],
                    "expected_outcome": f"Resolve the {fault_class} incident via {action.replace('_', ' ')}",
                    "rationale": f"Runbook-prescribed alternative for {fault_class} fault class",
                    "confidence": 0.7,
                    "source": "runbook",
                })
                if len(solutions) >= 3:
                    break
            recommended_solutions = solutions

        # Select first solution
        selected_solution = recommended_solutions[0] if recommended_solutions else None
        selected_action = selected_solution.get("action", suggested_action) if selected_solution else suggested_action
        solution_id = selected_solution.get("id", "sol-1") if selected_solution else "sol-1"

        # Conditional write to approve
        try:
            table.update_item(
                Key={"incident_id": incident_id},
                UpdateExpression=(
                    "SET remediation.#st = :approved, "
                    "remediation.decided_at = :now, "
                    "remediation.selected_action = :sel_action, "
                    "remediation.selected_solution_id = :sel_id, "
                    "remediation.approved_via = :via"
                ),
                ConditionExpression=(
                    "attribute_exists(incident_id) AND remediation.#st = :pending"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":approved": "approved",
                    ":pending": "pending_approval",
                    ":now": now,
                    ":sel_action": selected_action,
                    ":sel_id": solution_id,
                    ":via": approved_via,
                },
            )
            logger.info(f"Approved incident {incident_id} via {approved_via} (solution_id={solution_id}, action={selected_action})")
            
            # Fire remediation asynchronously
            lambda_client = boto3.client("lambda", region_name=region)
            remediation_fn = os.environ.get("REMEDIATION_FUNCTION_NAME", "")
            if remediation_fn:
                try:
                    lambda_client.invoke(
                        FunctionName=remediation_fn,
                        InvocationType="Event",
                        Payload=json.dumps({"incident_id": incident_id}),
                    )
                    logger.info(f"Remediation invoked async for incident {incident_id}")
                except Exception as exc:
                    logger.warning(f"Failed to invoke remediation for {incident_id}: {exc}")
            
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                resp = table.get_item(Key={"incident_id": incident_id})
                item = resp.get("Item")
                if not item:
                    logger.error(f"Incident {incident_id!r} not found")
                    return False
                current = item.get("remediation", {}).get("status", "unknown")
                logger.error(f"Cannot approve: incident is already in status '{current}'")
            raise
    except Exception as exc:
        logger.error(f"Error approving incident {incident_id}: {exc}")
        raise
    return False


def _build_record_from_dynamodb(item: Dict[str, Any], ground_truth_fault_class: str, injected_at: str) -> Dict[str, Any]:
    """
    Build an evaluation record from a DynamoDB item.
    Ground truth comes from the injection, NOT from the incident's own fault_class.
    """
    if not item:
        return None
    
    # Extract timestamps
    detected_at = item.get("detected_at") or injected_at
    remediation = item.get("remediation", {})
    executed_at = remediation.get("executed_at")
    verification = item.get("verification", {})
    checked_at = verification.get("checked_at")
    diagnosis = item.get("diagnosis", {})
    
    # Get used_rag from the diagnosis record (what was actually loaded)
    used_rag = diagnosis.get("used_rag", True)
    
    return {
        "incident_id": item.get("incident_id"),
        "fault_class": item.get("fault_class", "unknown"),
        "detected_at": detected_at,
        "ground_truth": {
            "true_fault_class": ground_truth_fault_class,
            "injected_at": injected_at,
        },
        "diagnosis": {
            "root_cause": diagnosis.get("root_cause", ""),
            "confidence": diagnosis.get("confidence", 0.0),
            "affected_resources": diagnosis.get("affected_resources", []),
            "suggested_action": diagnosis.get("suggested_action", "manual_review_required"),
            "reasoning_trace": diagnosis.get("reasoning_trace", ""),
            "used_rag": used_rag,
            "failure_mode": diagnosis.get("failure_mode", "none"),
            "diagnosis_status": diagnosis.get("diagnosis_status", "success"),
        },
        "remediation": {
            "status": remediation.get("status", "unknown"),
            "action_taken": remediation.get("action_taken", ""),
            "executed_at": executed_at,
        },
        "verification": {
            "status": verification.get("status", "not_run"),
            "checked_at": checked_at,
            "signal_rechecked": verification.get("signal_rechecked", ""),
            "notes": verification.get("notes", ""),
        },
        "evidence": item.get("evidence", {}),
    }


def run_evaluation(
    num_runs: int = 3,
    ablation: bool = False,
    mock: bool = False,
    environment: str = "dev",
    region: str = "ap-south-1",
    output_dir: str = "evaluation/results",
    auto_approve: bool = False,
) -> Dict[str, Any]:
    logger.info(f"Starting evaluation run: num_runs={num_runs}, ablation={ablation}, mock={mock}, env={environment}, auto_approve={auto_approve}")

    # Mock runs always write to mock/ subfolder
    if mock:
        output_dir = os.path.join(output_dir, "mock")
        records = generate_mock_incidents(num_runs=num_runs, ablation=ablation)
        # Mark all mock records as synthetic
        for rec in records:
            rec["evidence"] = rec.get("evidence", {})
            rec["evidence"]["demo_synthetic"] = True
    else:
        logger.info("Triggering fault injections in live AWS environment...")
        incidents_table = os.environ.get("INCIDENTS_TABLE", f"incidents-{environment}")
        
        # Track injections with their ground truth
        injections = []
        
        # Inject resource_exhaustion
        logger.info("Injecting resource_exhaustion fault...")
        injected_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        inject_resource_exhaustion(environment=environment, region=region, dry_run=False)
        injections.append({"fault_class": "resource_exhaustion", "injected_at": injected_at})
        
        # Inject misconfiguration
        logger.info("Injecting misconfiguration fault...")
        injected_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        inject_misconfiguration(environment=environment, region=region, dry_run=False)
        injections.append({"fault_class": "misconfiguration", "injected_at": injected_at})
        
        # Inject service_cascade
        logger.info("Injecting service_cascade fault...")
        injected_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        inject_service_cascade(environment=environment, region=region, dry_run=False)
        injections.append({"fault_class": "service_cascade", "injected_at": injected_at})
        
        # Wait for each incident to complete and build records
        records = []
        for injection in injections:
            # Find the NEW incident created for this injection
            logger.info(f"Waiting for {injection['fault_class']} incident to be created...")
            new_incident = _wait_for_incident_created(
                injection["fault_class"],
                injection["injected_at"],
                incidents_table,
                region,
                timeout_seconds=60,
            )
            
            if not new_incident:
                logger.warning(f"No new incident created for {injection['fault_class']} within timeout")
                continue
            
            incident_id = new_incident["incident_id"]
            logger.info(f"Found incident {incident_id}, waiting for approval...")
            
            # Check if we should auto-approve
            remediation_status = (new_incident.get("remediation") or {}).get("status")
            if remediation_status == "pending_approval":
                if auto_approve:
                    logger.info(f"Auto-approving incident {incident_id}")
                    if not _approve_incident(incident_id, incidents_table, region, "eval_harness"):
                        logger.error(f"Failed to auto-approve incident {incident_id}")
                        continue
                else:
                    logger.warning(f"Incident {incident_id} stalled at pending_approval (use --auto-approve to proceed)")
                    # Record as stalled
                    record = _build_record_from_dynamodb(
                        new_incident,
                        injection["fault_class"],
                        injection["injected_at"],
                    )
                    if record:
                        record["verification"]["status"] = "stalled_pending_approval"
                        record["verification"]["notes"] = "Incident stalled at pending_approval (no --auto-approve)"
                        records.append(record)
                    continue
            
            # Wait for incident to complete
            logger.info(f"Waiting for incident {incident_id} to complete...")
            # Wait timeout = VerificationMaxWaitSeconds (60) + remediation buffer (120) = 180s
            completed_item = _wait_for_incident_completion(
                incident_id,
                incidents_table,
                region,
                timeout_seconds=300,  # 5 minutes = 300s > 60+120
            )
            
            if completed_item:
                record = _build_record_from_dynamodb(
                    completed_item,
                    injection["fault_class"],
                    injection["injected_at"],
                )
                if record:
                    records.append(record)
                    logger.info(f"Built record for incident {record['incident_id']}")
            else:
                logger.warning(f"No completed incident found for {injection['fault_class']}")

    metrics_summary = compute_aggregate_metrics(records)
    export_results(metrics_summary, output_dir)
    return metrics_summary


def main():
    parser = argparse.ArgumentParser(description="Run Phase 7 Evaluation & Benchmarking Harness")
    parser.add_argument("--num-runs", type=int, default=3, help="Number of evaluation trials per fault class")
    parser.add_argument("--ablation", action="store_true", help="Run in ablation mode (used_rag=false)")
    parser.add_argument("--mock", action="store_true", help="Run with deterministic synthetic mock dataset")
    parser.add_argument("--environment", default="dev", help="AWS environment stage")
    parser.add_argument("--region", default="ap-south-1", help="AWS region")
    parser.add_argument("--output-dir", default="evaluation/results", help="Directory for CSV/JSON outputs")
    parser.add_argument("--auto-approve", action="store_true", help="Automatically approve incidents (records approved_via='eval_harness')")

    args = parser.parse_args()

    try:
        summary = run_evaluation(
            num_runs=args.num_runs,
            ablation=args.ablation,
            mock=args.mock,
            environment=args.environment,
            region=args.region,
            output_dir=args.output_dir,
            auto_approve=args.auto_approve,
        )
        print("\n--- Evaluation Summary ---")
        print(json.dumps({
            "total_incidents": summary["total_incidents"],
            "mttr_seconds_avg": summary["mttr_seconds_avg"],
            "rca_accuracy_pct": summary["rca_accuracy_pct"],
            "hallucination_rate_pct": summary["hallucination_rate_pct"],
            "diagnosis_recovery_gap_pct": summary["diagnosis_recovery_gap_pct"],
            "failure_taxonomy": summary["failure_taxonomy"],
        }, indent=2))
    except Exception as exc:
        logger.error(f"Evaluation runner failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()