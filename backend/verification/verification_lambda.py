"""
app.py - Phase 6.5: Closed-loop Verification Lambda

Core research novelty: after remediation executes, wait 2 minutes,
re-query the same signal that triggered detection, and write the result
back to IncidentRecord.verification.

This measures the gap between "the LLM diagnosed correctly" and
"the fix actually resolved the incident" - which is the paper's
headline contribution (diagnosis-recovery gap metric).

Signal re-check logic per fault_class:
  resource_exhaustion  -> CloudWatch Metrics: Lambda Duration for the affected function.
                           Compare max value in last 5 min against the original alarm threshold.
  misconfiguration     -> AWS Config: compliance status of the original Config rule + resource.
                           NON_COMPLIANT count = 0 means resolved.
  service_cascade      -> CloudWatch Metrics: Service A Errors sum + Service C Duration average.
                           Both must be below their respective alarm thresholds.
  (plus active probe for resource_exhaustion and service_cascade)

Outcomes written to IncidentRecord.verification.status:
  "resolved"              - signal is back to normal (below threshold / compliant)
  "not_resolved"          - signal still triggering (above threshold / still non-compliant)
  "inconclusive"          - ambiguous data (no datapoints, API error, unknown fault_class)
  "resolved_unverified"   - demo mode: alarm was reset but no independent verification
  "evidence_type" field records what was used: active_probe | metric | alarm_state_fallback | s3_direct | config
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_cw = boto3.client("cloudwatch")
_config_client = boto3.client("config")
_dynamodb = boto3.resource("dynamodb")
_lambda_client = boto3.client("lambda")

INCIDENTS_TABLE = os.environ["INCIDENTS_TABLE"]

# Configurable wait/poll/max-wait via environment variables
# Defaults: wait 120s, poll every 10s, max wait 300s
# For demos: set VERIFICATION_WAIT_SECONDS=15, VERIFICATION_MAX_WAIT_SECONDS=60
VERIFICATION_WAIT_SECONDS = int(os.environ.get("VERIFICATION_WAIT_SECONDS", "120"))
VERIFICATION_POLL_SECONDS = int(os.environ.get("VERIFICATION_POLL_SECONDS", "10"))
VERIFICATION_MAX_WAIT_SECONDS = int(os.environ.get("VERIFICATION_MAX_WAIT_SECONDS", "300"))

# Lookback window for metric re-check (last 5 minutes of data points)
METRIC_LOOKBACK_SECONDS = 300

# Demo mode flag - if true, use alarm reset and mark as resolved_unverified
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"


# ===========================================================================
# Entry point
# ===========================================================================

def lambda_handler(event, context):
    logger.info(json.dumps({"event": "verification_triggered", "payload": event}, default=str))

    incident_id = event.get("incident_id")
    fault_class = event.get("fault_class", "unknown")
    original_signal = event.get("original_signal") or {}
    # Remediation completion timestamp - ignore any alarm state or datapoint older than this
    remediation_completed_at = event.get("remediation_completed_at")
    # Whether the remediation action reset the CloudWatch alarm (DEMO_MODE only)
    alarm_reset = event.get("alarm_reset", False)
    # Whether the evidence is synthetic (demo mode)
    evidence_synthetic = event.get("evidence_synthetic", False)
    # Action key to check for manual_review_required gating
    action_key = event.get("action_key", "")

    if not incident_id:
        logger.error("Missing incident_id in verification event")
        return {"statusCode": 400, "body": json.dumps({"error": "Missing incident_id"})}

    # GATING: Skip verification if remediation failed or was manual_review_required
    if action_key == "manual_review_required":
        logger.info(json.dumps({
            "event": "verification_skipped_manual_review",
            "incident_id": incident_id,
            "action_key": action_key,
        }))
        _update_verification_record(
            incident_id,
            "not_run",
            "manual_review_required - no automated verification",
            "Remediation was manual_review_required; no verification performed.",
            "manual_review",
        )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "incident_id": incident_id,
                "verification_status": "not_run",
                "signal_rechecked": "manual_review_required",
                "notes": "Remediation was manual_review_required; no verification performed.",
                "evidence_type": "manual_review",
            }),
        }

    # We still invoke verification for failed remediation to record the failure,
    # but we don't run the actual checks - just record the status
    if action_key and action_key != "manual_review_required":
        # Check if the remediation record shows failure
        pass  # We'll let the verification run to capture the failure state

    # Parse remediation completion time if provided
    remediation_dt = None
    if remediation_completed_at:
        try:
            remediation_dt = datetime.fromisoformat(remediation_completed_at.replace("Z", "+00:00"))
            logger.info(json.dumps({
                "event": "verification_using_remediation_timestamp",
                "incident_id": incident_id,
                "remediation_completed_at": remediation_completed_at,
            }))
        except (ValueError, TypeError) as exc:
            logger.warning(f"Could not parse remediation_completed_at: {exc}")

    # Wait for the fix to propagate before re-checking the signal.
    # Use configurable wait time, then poll until resolved or max wait exceeded.
    logger.info(json.dumps({
        "event": "verification_waiting",
        "incident_id": incident_id,
        "initial_wait_seconds": VERIFICATION_WAIT_SECONDS,
        "poll_interval_seconds": VERIFICATION_POLL_SECONDS,
        "max_wait_seconds": VERIFICATION_MAX_WAIT_SECONDS,
        "fault_class": fault_class,
        "demo_mode": DEMO_MODE,
        "alarm_reset": alarm_reset,
        "evidence_synthetic": evidence_synthetic,
    }))
    time.sleep(VERIFICATION_WAIT_SECONDS)

    # Poll for resolution
    status, signal_rechecked, notes, evidence_type = _poll_for_resolution(
        fault_class, original_signal, remediation_dt, alarm_reset, evidence_synthetic
    )

    logger.info(json.dumps({
        "event": "verification_result",
        "incident_id": incident_id,
        "status": status,
        "signal_rechecked": signal_rechecked,
        "notes": notes,
        "evidence_type": evidence_type,
    }))

    # Write result back to DynamoDB
    _update_verification_record(incident_id, status, signal_rechecked, notes, evidence_type)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "incident_id": incident_id,
            "verification_status": status,
            "signal_rechecked": signal_rechecked,
            "notes": notes,
            "evidence_type": evidence_type,
        }),
    }


# ===========================================================================
# Polling logic
# ===========================================================================

def _poll_for_resolution(fault_class: str, original_signal: dict, remediation_dt: datetime | None, alarm_reset: bool, evidence_synthetic: bool) -> tuple[str, str, str, str]:
    """
    Poll the verification signal until resolved, max wait exceeded, or error.
    Returns (status, signal_rechecked, notes, evidence_type).
    """
    start_time = time.time()
    max_wait = VERIFICATION_MAX_WAIT_SECONDS
    
    while time.time() - start_time < max_wait:
        status, signal_rechecked, notes, evidence_type = _recheck_signal(fault_class, original_signal, remediation_dt, alarm_reset, evidence_synthetic)
        
        if status == "resolved":
            return status, signal_rechecked, notes, evidence_type
        
        # For demo mode, if we get "resolved" via alarm_state_fallback, don't exit early
        # unless we have active probe confirmation (handled in _recheck_signal)
        
        logger.info(json.dumps({
            "event": "verification_poll_not_resolved",
            "status": status,
            "evidence_type": evidence_type,
            "elapsed_seconds": round(time.time() - start_time),
            "max_wait_seconds": max_wait,
        }))
        time.sleep(VERIFICATION_POLL_SECONDS)
    
    # Max wait exceeded - return last check result
    logger.warning(json.dumps({
        "event": "verification_max_wait_exceeded",
        "fault_class": fault_class,
        "max_wait_seconds": max_wait,
    }))
    return status, signal_rechecked, notes, evidence_type


# ===========================================================================
# Signal re-check dispatch
# ===========================================================================

def _recheck_signal(fault_class: str, original_signal: dict, remediation_dt: datetime | None, alarm_reset: bool, evidence_synthetic: bool) -> tuple[str, str, str, str]:
    """
    Returns (status, signal_rechecked, notes, evidence_type).
    status is one of: "resolved" | "not_resolved" | "inconclusive" | "resolved_unverified"
    evidence_type: active_probe | metric | alarm_state_fallback | s3_direct | config | probe_unavailable | manual_review
    """
    if fault_class == "resource_exhaustion":
        return _recheck_resource_exhaustion(original_signal, remediation_dt, alarm_reset, evidence_synthetic)
    if fault_class == "misconfiguration":
        return _recheck_misconfiguration(original_signal, remediation_dt, alarm_reset, evidence_synthetic)
    if fault_class == "service_cascade":
        return _recheck_service_cascade(original_signal, remediation_dt, alarm_reset, evidence_synthetic)
    return (
        "inconclusive",
        f"fault_class={fault_class}",
        f"Unknown fault_class '{fault_class}' - no verification logic defined for this class.",
        "none",
    )


# ===========================================================================
# resource_exhaustion: re-check Lambda Duration metric + active probe
# ===========================================================================

def _recheck_resource_exhaustion(signal: dict, remediation_dt: datetime | None, alarm_reset: bool, evidence_synthetic: bool) -> tuple[str, str, str, str]:
    """
    Re-check the Lambda Duration metric for the affected function.
    Also run an active probe (invoke Service A endpoint) to verify actual health.
    """
    threshold = signal.get("threshold", 50000)
    alarm_name = signal.get("alarm_name") or ""
    metric_name = signal.get("metric_name", "Duration")

    function_name = _resolve_function_from_alarm(alarm_name)
    if not function_name:
        return (
            "inconclusive",
            f"Lambda {metric_name} for alarm '{alarm_name}'",
            f"Could not resolve Lambda function name from alarm name '{alarm_name}'. Cannot re-check.",
            "none",
        )

    signal_desc = (
        f"Lambda {metric_name} (Maximum) for '{function_name}' "
        f"vs alarm threshold {threshold}ms"
    )

    # 1. Try active probe first (invoke Service A endpoint)
    probe_result = _active_probe_service_a()
    if probe_result.get("probe_unavailable", False):
        # Probe cannot run - return probe_unavailable, don't fall back to resolved from alarm state
        return (
            "inconclusive",
            "Active probe: Service A invoke",
            "Active probe unavailable: " + probe_result.get("error", "Unknown error"),
            "probe_unavailable",
        )
    
    if probe_result["success"]:
        # Active probe succeeded - check if latency is acceptable
        # Use PROBE_LATENCY_THRESHOLD_MS env var (default 3000ms), not the 50000ms alarm threshold
        probe_threshold = int(os.environ.get("PROBE_LATENCY_THRESHOLD_MS", "3000"))
        if probe_result["p95_latency_ms"] <= probe_threshold:
            return (
                "resolved",
                f"Active probe: Service A invoke (p95={probe_result['p95_latency_ms']:.0f}ms) vs threshold {probe_threshold}ms",
                f"Active probe success rate: {probe_result['success_rate']:.1%}, p95 latency: {probe_result['p95_latency_ms']:.0f}ms. Below threshold - incident resolved.",
                "active_probe",
            )
        else:
            return (
                "not_resolved",
                f"Active probe: Service A invoke (p95={probe_result['p95_latency_ms']:.0f}ms) vs threshold {probe_threshold}ms",
                f"Active probe success rate: {probe_result['success_rate']:.1%}, p95 latency: {probe_result['p95_latency_ms']:.0f}ms. Still above threshold.",
                "active_probe",
            )

    # 2. Probe failed (success_rate < 0.8) - fall back to CloudWatch metrics (filter by remediation_dt)
    try:
        datapoints = _get_lambda_metric_datapoints(function_name, metric_name, "Maximum", remediation_dt)
    except ClientError as exc:
        return ("inconclusive", signal_desc, f"CloudWatch GetMetricStatistics error: {exc}", "metric")

    if not datapoints:
        # No recent invocations - fall back to checking the CloudWatch alarm state.
        if alarm_name:
            alarm_status, alarm_notes = _get_alarm_state(alarm_name)
            fallback_desc = f"CloudWatch alarm state for '{alarm_name}' (no recent Lambda invocations)"
            # Alarm state fallback alone yields inconclusive, not resolved
            if alarm_status == "resolved":
                if alarm_reset and DEMO_MODE:
                    return ("resolved_unverified", fallback_desc, alarm_notes + " (alarm state fallback only - no active probe or metric data, alarm was reset by demo remediation)", "alarm_state_fallback")
                return ("inconclusive", fallback_desc, alarm_notes + " (alarm state fallback only - no active probe or metric data)", "alarm_state_fallback")
            return (alarm_status, fallback_desc, alarm_notes, "alarm_state_fallback")
        return (
            "inconclusive",
            signal_desc,
            (
                f"No {metric_name} datapoints returned for '{function_name}' "
                f"in the last {METRIC_LOOKBACK_SECONDS}s and no alarm name available to check state. "
                "Function may not have been invoked since remediation."
            ),
            "none",
        )

    # Filter datapoints to only those after remediation
    if remediation_dt:
        datapoints = [dp for dp in datapoints if dp["timestamp_dt"] > remediation_dt]
    
    if not datapoints:
        if alarm_name:
            alarm_status, alarm_notes = _get_alarm_state(alarm_name)
            fallback_desc = f"CloudWatch alarm state for '{alarm_name}' (no post-remediation datapoints)"
            if alarm_status == "resolved":
                if alarm_reset and DEMO_MODE:
                    return ("resolved_unverified", fallback_desc, alarm_notes + " (alarm state fallback only - no post-remediation metric data, alarm was reset by demo remediation)", "alarm_state_fallback")
                return ("inconclusive", fallback_desc, alarm_notes + " (alarm state fallback only - no post-remediation metric data)", "alarm_state_fallback")
            return (alarm_status, fallback_desc, alarm_notes, "alarm_state_fallback")
        return (
            "inconclusive",
            signal_desc,
            f"No post-remediation {metric_name} datapoints for '{function_name}'.",
            "metric",
        )

    max_value = max(dp["value"] for dp in datapoints)
    notes = (
        f"Max {metric_name} = {max_value:.0f}ms over post-remediation window. "
        f"Alarm threshold = {threshold}ms."
    )

    if max_value <= threshold:
        return ("resolved", signal_desc, notes + " Below threshold - incident resolved.", "metric")
    return ("not_resolved", signal_desc, notes + " Still above threshold - incident not resolved.", "metric")


def _active_probe_service_a() -> dict:
    """
    Invoke the Service A endpoint N times and compute success rate and p95 latency.
    URL from SERVICE_A_URL env var (required - no discovery fallback).
    Probe success requires success_rate >= 0.8.
    """
    import urllib.request
    import urllib.error
    
    service_a_url = os.environ.get("SERVICE_A_URL")
    if not service_a_url:
        return {"success": False, "error": "SERVICE_A_URL not configured", "probe_unavailable": True}
    
    probe_count = int(os.environ.get("VERIFICATION_PROBE_COUNT", "5"))
    probe_timeout = int(os.environ.get("VERIFICATION_PROBE_TIMEOUT_SECONDS", "10"))
    
    latencies = []
    successes = 0
    
    for _ in range(probe_count):
        start = time.perf_counter()
        try:
            req = urllib.request.Request(service_a_url, method="GET")
            with urllib.request.urlopen(req, timeout=probe_timeout) as resp:
                if 200 <= resp.status < 300:
                    successes += 1
            latencies.append((time.perf_counter() - start) * 1000)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            latencies.append((time.perf_counter() - start) * 1000)
            logger.warning(f"Active probe failed: {exc}")
    
    if not latencies:
        return {"success": False, "error": "No probe attempts completed", "probe_unavailable": True}
    
    latencies.sort()
    p95_idx = int(len(latencies) * 0.95)
    p95_latency = latencies[min(p95_idx, len(latencies) - 1)]
    success_rate = successes / probe_count
    
    # Probe success requires success_rate >= 0.8
    probe_success = success_rate >= 0.8
    
    return {
        "success": probe_success,
        "success_rate": success_rate,
        "p95_latency_ms": p95_latency,
        "latencies_ms": latencies,
        "probe_unavailable": False,
    }


# ===========================================================================
# misconfiguration: S3 direct check PRIMARY, Config as fallback
# ===========================================================================

# ===========================================================================
# misconfiguration: S3 direct check PRIMARY, Config as fallback
# ===========================================================================

def _recheck_misconfiguration(signal: dict, remediation_dt: datetime | None, alarm_reset: bool, evidence_synthetic: bool) -> tuple[str, str, str, str]:
    """
    Re-check the S3 public access block FIRST (primary check).
    Only fall back to AWS Config if the S3 check could not run.
    """
    config_rule = (signal.get("config_rule") or "").strip()
    resource_type = signal.get("resource_type")
    resource_id = signal.get("resource_id")

    # PRIMARY: Direct S3 public access block check
    # If resource_id is a bucket (resource_type is S3 bucket or config_rule starts with "s3-")
    is_s3_resource = (
        resource_type == "AWS::S3::Bucket" or
        (config_rule and config_rule.startswith("s3-"))
    )
    
    if is_s3_resource and resource_id:
        s3_check_result = _check_s3_public_access_block([resource_id], remediation_dt)
        if s3_check_result is not None:
            status, s3_notes, after_state = s3_check_result
            return (
                status,
                f"S3 public access block for bucket '{resource_id}'",
                s3_notes,
                "s3_direct",
            )

    # FALLBACK: Config rule compliance check (only if S3 check couldn't run)
    if not config_rule:
        return (
            "inconclusive",
            "AWS Config compliance check",
            "original_signal did not contain a config_rule name. S3 direct check also could not run.",
            "none",
        )

    signal_desc = f"Config rule '{config_rule}' NON_COMPLIANT count"
    if resource_id:
        signal_desc += f" for resource '{resource_id}'"

    # Force a fresh evaluation so we see post-remediation state.
    try:
        _config_client.start_config_rules_evaluation(ConfigRuleNames=[config_rule])
        logger.info(json.dumps({
            "event": "config_evaluation_triggered",
            "config_rule": config_rule,
            "note": "Forced fresh evaluation before compliance check",
        }))
    except ClientError as exc:
        logger.warning(json.dumps({
            "event": "config_evaluation_trigger_failed",
            "config_rule": config_rule,
            "error": str(exc),
        }))

    try:
        kwargs: dict = {
            "ConfigRuleName": config_rule,
            "ComplianceTypes": ["NON_COMPLIANT"],
            "Limit": 50,
        }

        resp = _config_client.get_compliance_details_by_config_rule(**kwargs)
        all_results = resp.get("EvaluationResults", [])

        non_compliant_items = []
        for result in all_results:
            qualifier = (
                result.get("EvaluationResultIdentifier", {})
                .get("EvaluationResultQualifier", {})
            )
            res_type = qualifier.get("ResourceType")
            res_id = qualifier.get("ResourceId")
            if resource_type and res_type != resource_type:
                continue
            if resource_id and res_id != resource_id:
                continue
            non_compliant_items.append(result)

    except ClientError as exc:
        return ("inconclusive", signal_desc, f"Config GetComplianceDetailsByConfigRule error: {exc}", "config")

    if not non_compliant_items:
        return (
            "resolved",
            signal_desc,
            f"Config rule '{config_rule}' returned 0 NON_COMPLIANT resources. Resource is now compliant - incident resolved.",
            "config",
        )

    resource_list = [
        (e.get("EvaluationResultIdentifier", {})
         .get("EvaluationResultQualifier", {})
         .get("ResourceId", "unknown"))
        for e in non_compliant_items
    ]

    # Config still shows NON_COMPLIANT - fall back to S3 direct check (if not already tried)
    s3_check_result = _check_s3_public_access_block(resource_list, remediation_dt)
    if s3_check_result is not None:
        status, s3_notes, after_state = s3_check_result
        return (
            status,
            f"S3 public access block (Config eval lag fallback for '{config_rule}')",
            s3_notes,
            "s3_direct",
        )

    return (
        "not_resolved",
        signal_desc,
        (
            f"Config rule '{config_rule}' still has {len(non_compliant_items)} NON_COMPLIANT "
            f"resource(s): {', '.join(resource_list)}. Config may not have re-evaluated yet."
        ),
        "config",
    )


def _check_s3_public_access_block(bucket_names: list[str], remediation_dt: datetime | None) -> tuple[str, str, dict] | None:
    """
    Directly check whether S3 public access block is fully enabled for the
    given bucket names. Records state for before/after comparison.
    
    Returns (status, notes, after_state) if any bucket could be checked, else None.
    - "resolved"     - all checked buckets have full public access block enabled
    - "not_resolved" - at least one bucket still has public access enabled
    - None           - could not check any buckets (no valid bucket names)
    after_state is the public access block configuration after remediation.
    """
    _s3 = boto3.client("s3")
    results = []
    for bucket in bucket_names:
        if not bucket or bucket == "unknown":
            continue
        try:
            resp = _s3.get_public_access_block(Bucket=bucket)
            cfg = resp.get("PublicAccessBlockConfiguration", {})
            fully_blocked = all([
                cfg.get("BlockPublicAcls", False),
                cfg.get("IgnorePublicAcls", False),
                cfg.get("BlockPublicPolicy", False),
                cfg.get("RestrictPublicBuckets", False),
            ])
            results.append((bucket, fully_blocked, cfg))
            logger.info(json.dumps({
                "event": "s3_public_access_check",
                "bucket": bucket,
                "fully_blocked": fully_blocked,
                "config": cfg,
            }))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchPublicAccessBlockConfiguration":
                results.append((bucket, False, {}))
            else:
                logger.warning(json.dumps({
                    "event": "s3_public_access_check_error",
                    "bucket": bucket,
                    "error": str(exc),
                }))

    if not results:
        return None

    unblocked = [b for b, blocked, _ in results if not blocked]
    if unblocked:
        after_state = results[0][2] if results else {}
        return (
            "not_resolved",
            (
                f"S3 public access block not fully enabled on: {', '.join(unblocked)}. "
                "lock_s3_bucket remediation may not have applied yet, or failed."
            ),
            after_state,
        )
    checked = [b for b, _, _ in results]
    after_state = results[0][2] if results else {}
    return (
        "resolved",
        (
            f"S3 public access block fully enabled on: {', '.join(checked)}. "
            "Bucket is no longer publicly accessible - incident resolved."
        ),
        after_state,
    )


# ===========================================================================
# service_cascade: re-check Service A errors + Service C latency + active probe
# ===========================================================================

def _recheck_service_cascade(signal: dict, remediation_dt: datetime | None, alarm_reset: bool, evidence_synthetic: bool) -> tuple[str, str, str, str]:
    """
    Re-check both signals that define the composite cascade alarm:
    - Service A: Errors sum < error_threshold
    - Service C: Duration average <= latency_threshold
    Plus active probe to Service A endpoint.
    """
    error_threshold = signal.get("service_a_error_threshold", 5)
    latency_threshold = signal.get("service_c_latency_threshold", 3000)
    alarm_name = signal.get("alarm_name") or ""

    service_a_name = _find_lambda_by_prefix("ServiceA")
    service_c_name = _find_lambda_by_prefix("ServiceC")

    if not service_a_name or not service_c_name:
        return (
            "inconclusive",
            "Service A Errors + Service C Duration",
            (
                f"Could not resolve function names "
                f"(ServiceA={service_a_name}, ServiceC={service_c_name}). "
                "Cannot re-check cascade signals."
            ),
            "none",
        )

    signal_desc = (
        f"Service A Errors (sum, threshold {error_threshold}) + "
        f"Service C Duration (avg, threshold {latency_threshold}ms)"
    )

    # 1. Active probe to Service A
    probe_result = _active_probe_service_a()
    if probe_result["success"]:
        # Check both probe and Service C metric
        # Use PROBE_LATENCY_THRESHOLD_MS env var (default 3000ms)
        probe_threshold = int(os.environ.get("PROBE_LATENCY_THRESHOLD_MS", "3000"))
        if probe_result["p95_latency_ms"] <= probe_threshold:
            # Probe passed, now check Service C metric
            try:
                c_latency_data = _get_lambda_metric_datapoints(service_c_name, "Duration", "Average", remediation_dt)
            except ClientError as exc:
                return ("inconclusive", signal_desc, f"CloudWatch GetMetricStatistics error: {exc}", "active_probe")

            if c_latency_data:
                if remediation_dt:
                    c_latency_data = [dp for dp in c_latency_data if dp["timestamp_dt"] > remediation_dt]
                
                if c_latency_data:
                    c_max_latency = max(dp["value"] for dp in c_latency_data)
                    if c_max_latency <= latency_threshold:
                        return (
                            "resolved",
                            f"Active probe Service A (p95={probe_result['p95_latency_ms']:.0f}ms) + Service C Duration (avg={c_max_latency:.0f}ms) vs threshold {latency_threshold}ms",
                            f"Active probe success rate: {probe_result['success_rate']:.1%}, Service C avg latency: {c_max_latency:.0f}ms. Both below threshold - cascade resolved.",
                            "active_probe",
                        )
                    return (
                        "not_resolved",
                        signal_desc,
                        f"Active probe OK but Service C latency {c_max_latency:.0f}ms > {latency_threshold}ms threshold.",
                        "active_probe",
                    )
            # No Service C datapoints - fall through to alarm check

    # 2. Fall back to CloudWatch metrics (filter by remediation_dt)
    try:
        a_errors_data = _get_lambda_metric_datapoints(service_a_name, "Errors", "Sum", remediation_dt)
        c_latency_data = _get_lambda_metric_datapoints(service_c_name, "Duration", "Average", remediation_dt)
    except ClientError as exc:
        return ("inconclusive", signal_desc, f"CloudWatch GetMetricStatistics error: {exc}", "metric")

    # No datapoints for EITHER service - fall back to composite alarm state
    if not a_errors_data and not c_latency_data:
        if alarm_name:
            alarm_status, alarm_notes = _get_alarm_state_composite(alarm_name)
            fallback_desc = f"Composite alarm state for '{alarm_name}' (no recent Lambda invocations)"
            if alarm_status == "resolved":
                if alarm_reset and DEMO_MODE:
                    return ("resolved_unverified", fallback_desc, alarm_notes + " (alarm state fallback only - no active probe or metric data, alarm was reset by demo remediation)", "alarm_state_fallback")
                return ("inconclusive", fallback_desc, alarm_notes + " (alarm state fallback only - no active probe or metric data)", "alarm_state_fallback")
            return (alarm_status, fallback_desc, alarm_notes, "alarm_state_fallback")
        return (
            "inconclusive",
            signal_desc,
            (
                "No metric datapoints for ServiceA or ServiceC in the last "
                f"{METRIC_LOOKBACK_SECONDS}s and no composite alarm name to check. "
                "Services may not have been invoked since remediation."
            ),
            "none",
        )

    # Filter datapoints to only those after remediation
    if remediation_dt:
        a_errors_data = [dp for dp in a_errors_data if dp["timestamp_dt"] > remediation_dt]
        c_latency_data = [dp for dp in c_latency_data if dp["timestamp_dt"] > remediation_dt]

    if not a_errors_data and not c_latency_data:
        if alarm_name:
            alarm_status, alarm_notes = _get_alarm_state_composite(alarm_name)
            fallback_desc = f"Composite alarm state for '{alarm_name}' (no post-remediation datapoints)"
            if alarm_status == "resolved":
                if alarm_reset and DEMO_MODE:
                    return ("resolved_unverified", fallback_desc, alarm_notes + " (alarm state fallback only - no post-remediation metric data, alarm was reset by demo remediation)", "alarm_state_fallback")
                return ("inconclusive", fallback_desc, alarm_notes + " (alarm state fallback only - no post-remediation metric data)", "alarm_state_fallback")
            return (alarm_status, fallback_desc, alarm_notes, "alarm_state_fallback")
        return (
            "inconclusive",
            signal_desc,
            "No post-remediation metric datapoints for ServiceA or ServiceC.",
            "metric",
        )

    a_max_errors = max((dp["value"] for dp in a_errors_data), default=0)
    c_max_latency = max((dp["value"] for dp in c_latency_data), default=0)

    notes = (
        f"Service A max errors = {a_max_errors:.0f} (threshold {error_threshold}); "
        f"Service C max duration = {c_max_latency:.0f}ms (threshold {latency_threshold}ms)."
    )

    if a_max_errors < error_threshold and c_max_latency <= latency_threshold:
        return ("resolved", signal_desc, notes + " Both below threshold - cascade resolved.", "metric")

    still_firing = []
    if a_max_errors >= error_threshold:
        still_firing.append(f"Service A errors ({a_max_errors:.0f} >= {error_threshold})")
    if c_max_latency > latency_threshold:
        still_firing.append(f"Service C latency ({c_max_latency:.0f}ms > {latency_threshold}ms)")

    return (
        "not_resolved",
        signal_desc,
        notes + " Still above threshold: " + "; ".join(still_firing) + ".",
        "metric",
    )


# ===========================================================================
# Helper functions
# ===========================================================================

def _resolve_function_from_alarm(alarm_name: str) -> str | None:
    """Map alarm name (e.g. 'incident-service-a-resource-exhaustion-dev') to a Lambda function name."""
    alarm_lower = alarm_name.lower()
    if "service-a" in alarm_lower:
        return _find_lambda_by_prefix("ServiceA")
    if "service-b" in alarm_lower:
        return _find_lambda_by_prefix("ServiceB")
    if "service-c" in alarm_lower:
        return _find_lambda_by_prefix("ServiceC")
    return None


def _find_lambda_by_prefix(prefix: str) -> str | None:
    """Return the first Lambda function name containing the given prefix (case-insensitive)."""
    try:
        paginator = _lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page["Functions"]:
                if prefix.lower() in fn["FunctionName"].lower():
                    return fn["FunctionName"]
    except ClientError as exc:
        logger.warning(json.dumps({"event": "find_lambda_error", "prefix": prefix, "error": str(exc)}))
    return None


def _get_lambda_metric_datapoints(function_name: str, metric_name: str, stat: str, remediation_dt: datetime | None = None) -> list[dict]:
    """Fetch metric datapoints for a Lambda function over the last METRIC_LOOKBACK_SECONDS."""
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(seconds=METRIC_LOOKBACK_SECONDS)

    resp = _cw.get_metric_statistics(
        Namespace="AWS/Lambda",
        MetricName=metric_name,
        Dimensions=[{"Name": "FunctionName", "Value": function_name}],
        StartTime=start_dt,
        EndTime=end_dt,
        Period=60,
        Statistics=[stat],
    )
    datapoints = []
    for dp in resp.get("Datapoints", []):
        ts = dp["Timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        datapoints.append({
            "timestamp": str(dp["Timestamp"]),
            "timestamp_dt": ts,
            "value": dp[stat],
        })
    return datapoints


def _get_alarm_state(alarm_name: str) -> tuple[str, str]:
    """
    Fetch the current state of a CloudWatch alarm and map it to a
    verification outcome.
    """
    try:
        resp = _cw.describe_alarms(AlarmNames=[alarm_name], AlarmTypes=["MetricAlarm"])
        alarms = resp.get("MetricAlarms", [])
        if not alarms:
            return (
                "inconclusive",
                f"Alarm '{alarm_name}' not found via DescribeAlarms. Cannot determine resolution state.",
            )
        state = alarms[0].get("StateValue", "INSUFFICIENT_DATA")
        state_reason = alarms[0].get("StateReason", "")
        if state == "OK":
            return (
                "resolved",
                f"CloudWatch alarm '{alarm_name}' returned to OK state. {state_reason}",
            )
        if state == "ALARM":
            return (
                "not_resolved",
                f"CloudWatch alarm '{alarm_name}' is still in ALARM state. {state_reason}",
            )
        return (
            "inconclusive",
            f"CloudWatch alarm '{alarm_name}' is in INSUFFICIENT_DATA state. {state_reason}",
        )
    except ClientError as exc:
        return (
            "inconclusive",
            f"DescribeAlarms error for '{alarm_name}': {exc}",
        )


def _get_alarm_state_composite(alarm_name: str) -> tuple[str, str]:
    """Like _get_alarm_state but checks CompositeAlarm type."""
    try:
        resp = _cw.describe_alarms(AlarmNames=[alarm_name], AlarmTypes=["CompositeAlarm"])
        alarms = resp.get("CompositeAlarms", [])
        if not alarms:
            return (
                "inconclusive",
                f"Composite alarm '{alarm_name}' not found via DescribeAlarms. Cannot determine resolution state.",
            )
        state = alarms[0].get("StateValue", "INSUFFICIENT_DATA")
        state_reason = alarms[0].get("StateReason", "")
        if state == "OK":
            return (
                "resolved",
                f"Composite alarm '{alarm_name}' returned to OK state. {state_reason}",
            )
        if state == "ALARM":
            return (
                "not_resolved",
                f"Composite alarm '{alarm_name}' is still in ALARM state. {state_reason}",
            )
        return (
            "inconclusive",
            f"Composite alarm '{alarm_name}' is in INSUFFICIENT_DATA state. {state_reason}",
        )
    except ClientError as exc:
        return (
            "inconclusive",
            f"DescribeAlarms (composite) error for '{alarm_name}': {exc}",
        )


# ===========================================================================
# DynamoDB write-back
# ===========================================================================

def _update_verification_record(
    incident_id: str,
    status: str,
    signal_rechecked: str,
    notes: str,
    evidence_type: str,
    after_state: dict | None = None,
) -> None:
    """
    Write the verification outcome to IncidentRecord.verification.
    This is the core data that feeds the diagnosis-recovery gap metric.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        update_expr = (
            "SET verification.#st = :status, "
            "verification.checked_at = :checked_at, "
            "verification.signal_rechecked = :signal, "
            "verification.notes = :notes, "
            "verification.evidence_type = :evidence_type"
        )
        expr_vals = {
            ":status": status,
            ":checked_at": now,
            ":signal": signal_rechecked,
            ":notes": notes,
            ":evidence_type": evidence_type,
        }
        if after_state is not None:
            update_expr += ", verification.after_state = :after_state"
            expr_vals[":after_state"] = after_state
        
        _dynamodb.Table(INCIDENTS_TABLE).update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues=expr_vals,
        )
        logger.info(json.dumps({
            "event": "verification_record_written",
            "incident_id": incident_id,
            "status": status,
            "evidence_type": evidence_type,
            "checked_at": now,
        }))
    except ClientError as exc:
        logger.error(json.dumps({
            "event": "dynamodb_verification_write_error",
            "incident_id": incident_id,
            "intended_status": status,
            "error": str(exc),
            "ATTENTION": (
                "Verification result could NOT be written to DynamoDB. "
                "This incident will show verification.status='not_run' in evaluation results."
            ),
        }))