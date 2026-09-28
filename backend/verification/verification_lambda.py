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

Outcomes written to IncidentRecord.verification.status:
  "resolved"      - signal is back to normal (below threshold / compliant)
  "not_resolved"  - signal still triggering (above threshold / still non-compliant)
  "inconclusive"  - ambiguous data (no datapoints, API error, unknown fault_class)
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

# Wait period before re-checking (2 minutes, per spec step 21 "2-5 minutes")
VERIFICATION_WAIT_SECONDS = 120

# Lookback window for metric re-check (last 5 minutes of data points)
METRIC_LOOKBACK_SECONDS = 300


# ===========================================================================
# Entry point
# ===========================================================================

def lambda_handler(event, context):
    logger.info(json.dumps({"event": "verification_triggered", "payload": event}, default=str))

    incident_id = event.get("incident_id")
    fault_class = event.get("fault_class", "unknown")
    original_signal = event.get("original_signal") or {}

    if not incident_id:
        logger.error("Missing incident_id in verification event")
        return {"statusCode": 400, "body": json.dumps({"error": "Missing incident_id"})}

    # Wait for the fix to propagate before re-checking the signal.
    # This is intentional - the spec requires a fixed interval post-remediation.
    logger.info(json.dumps({
        "event": "verification_waiting",
        "incident_id": incident_id,
        "wait_seconds": VERIFICATION_WAIT_SECONDS,
        "fault_class": fault_class,
    }))
    time.sleep(VERIFICATION_WAIT_SECONDS)

    # Re-check the original signal
    status, signal_rechecked, notes = _recheck_signal(fault_class, original_signal)

    logger.info(json.dumps({
        "event": "verification_result",
        "incident_id": incident_id,
        "status": status,
        "signal_rechecked": signal_rechecked,
        "notes": notes,
    }))

    # Write result back to DynamoDB
    _update_verification_record(incident_id, status, signal_rechecked, notes)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "incident_id": incident_id,
            "verification_status": status,
            "signal_rechecked": signal_rechecked,
            "notes": notes,
        }),
    }


# ===========================================================================
# Signal re-check dispatch
# ===========================================================================

def _recheck_signal(fault_class: str, original_signal: dict) -> tuple[str, str, str]:
    """
    Returns (status, signal_rechecked, notes).
    status is one of: "resolved" | "not_resolved" | "inconclusive"
    signal_rechecked is a human-readable description of what was queried.
    notes is a brief explanation of the finding.
    """
    if fault_class == "resource_exhaustion":
        return _recheck_resource_exhaustion(original_signal)
    if fault_class == "misconfiguration":
        return _recheck_misconfiguration(original_signal)
    if fault_class == "service_cascade":
        return _recheck_service_cascade(original_signal)
    return (
        "inconclusive",
        f"fault_class={fault_class}",
        f"Unknown fault_class '{fault_class}' - no verification logic defined for this class.",
    )


# ===========================================================================
# resource_exhaustion: re-check Lambda Duration metric
# ===========================================================================

def _recheck_resource_exhaustion(signal: dict) -> tuple[str, str, str]:
    """
    Re-check the Lambda Duration metric for the affected function.
    Compares the maximum Duration in the last METRIC_LOOKBACK_SECONDS
    against the original alarm threshold.
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
        )

    signal_desc = (
        f"Lambda {metric_name} (Maximum) for '{function_name}' "
        f"vs alarm threshold {threshold}ms"
    )

    try:
        datapoints = _get_lambda_metric_datapoints(function_name, metric_name, "Maximum")
    except ClientError as exc:
        return ("inconclusive", signal_desc, f"CloudWatch GetMetricStatistics error: {exc}")

    if not datapoints:
        # No recent invocations - fall back to checking the CloudWatch alarm state.
        # This covers the demo scenario where the alarm was artificially set via
        # SetAlarmState (no real Lambda invocations, so no Duration datapoints exist).
        # The alarm returning to OK is the most direct resolution signal available.
        if alarm_name:
            alarm_status, alarm_notes = _get_alarm_state(alarm_name)
            fallback_desc = f"CloudWatch alarm state for '{alarm_name}' (no recent Lambda invocations)"
            return (alarm_status, fallback_desc, alarm_notes)
        return (
            "inconclusive",
            signal_desc,
            (
                f"No {metric_name} datapoints returned for '{function_name}' "
                f"in the last {METRIC_LOOKBACK_SECONDS}s and no alarm name available to check state. "
                "Function may not have been invoked since remediation."
            ),
        )

    max_value = max(dp["value"] for dp in datapoints)
    notes = (
        f"Max {metric_name} = {max_value:.0f}ms over last {METRIC_LOOKBACK_SECONDS}s. "
        f"Alarm threshold = {threshold}ms."
    )

    if max_value <= threshold:
        return ("resolved", signal_desc, notes + " Below threshold - incident resolved.")
    return ("not_resolved", signal_desc, notes + " Still above threshold - incident not resolved.")


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


def _get_lambda_metric_datapoints(function_name: str, metric_name: str, stat: str) -> list[dict]:
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
    return [
        {"timestamp": str(dp["Timestamp"]), "value": dp[stat]}
        for dp in resp.get("Datapoints", [])
    ]


def _get_alarm_state(alarm_name: str) -> tuple[str, str]:
    """
    Fetch the current state of a CloudWatch alarm and map it to a
    verification outcome.

    Returns (status, notes) where status is one of:
      "resolved"     - alarm state is OK (signal has returned to normal)
      "not_resolved" - alarm state is still ALARM
      "inconclusive" - INSUFFICIENT_DATA or DescribeAlarms error

    This is the fallback for demo scenarios where the alarm was triggered
    via SetAlarmState (no real Lambda invocations, so no metric datapoints).
    The alarm returning to OK is the most direct resolution signal available.
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
        # INSUFFICIENT_DATA
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
    """
    Like _get_alarm_state but checks CompositeAlarm type.
    Used as fallback for service_cascade when no metric datapoints exist.

    Returns (status, notes):
      "resolved"     - composite alarm is OK
      "not_resolved" - composite alarm is still ALARM
      "inconclusive" - INSUFFICIENT_DATA or API error
    """
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


def _check_s3_public_access_block(bucket_names: list[str]) -> tuple[str, str] | None:
    """
    Directly check whether S3 public access block is fully enabled for the
    given bucket names. Used as a fallback for misconfiguration verification
    when AWS Config has not re-evaluated since the lock_s3_bucket remediation.

    Returns (status, notes) if any bucket could be checked, else None.
    - "resolved"     - all checked buckets have full public access block enabled
    - "not_resolved" - at least one bucket still has public access enabled
    - None           - could not check any buckets (no valid bucket names)
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
            results.append((bucket, fully_blocked))
            logger.info(json.dumps({
                "event": "s3_public_access_check",
                "bucket": bucket,
                "fully_blocked": fully_blocked,
                "config": cfg,
            }))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchPublicAccessBlockConfiguration":
                # No block config set at all - bucket is publicly accessible
                results.append((bucket, False))
            else:
                logger.warning(json.dumps({
                    "event": "s3_public_access_check_error",
                    "bucket": bucket,
                    "error": str(exc),
                }))

    if not results:
        return None

    unblocked = [b for b, blocked in results if not blocked]
    if unblocked:
        return (
            "not_resolved",
            (
                f"S3 public access block not fully enabled on: {', '.join(unblocked)}. "
                "lock_s3_bucket remediation may not have applied yet, or failed."
            ),
        )
    checked = [b for b, _ in results]
    return (
        "resolved",
        (
            f"S3 public access block fully enabled on: {', '.join(checked)}. "
            "Bucket is no longer publicly accessible - incident resolved."
        ),
    )


# ===========================================================================
# misconfiguration: re-check Config rule compliance
# ===========================================================================

def _recheck_misconfiguration(signal: dict) -> tuple[str, str, str]:
    """
    Re-check the Config rule compliance status for the flagged resource.
    If 0 NON_COMPLIANT results are returned for the rule (optionally filtered
    to the specific resource), the incident is considered resolved.

    Improvements over the original:
    1. Force a fresh Config evaluation before querying results, so the check
       reflects the post-remediation state rather than the pre-remediation cache.
    2. If the Config API still shows NON_COMPLIANT results (evaluation lag),
       fall back to checking the S3 public access block status directly (since
       the only misconfiguration fault class in this demo is an S3 public bucket).
    """
    config_rule = (signal.get("config_rule") or "").strip()
    resource_type = signal.get("resource_type")
    resource_id = signal.get("resource_id")

    if not config_rule:
        return (
            "inconclusive",
            "AWS Config compliance check",
            "original_signal did not contain a config_rule name. Cannot re-check compliance.",
        )

    signal_desc = f"Config rule '{config_rule}' NON_COMPLIANT count"
    if resource_id:
        signal_desc += f" for resource '{resource_id}'"

    # Force a fresh evaluation so we see post-remediation state.
    # StartConfigRulesEvaluation is async - results may not be ready immediately,
    # but it re-queues the evaluation so the next check will be accurate.
    try:
        _config_client.start_config_rules_evaluation(ConfigRuleNames=[config_rule])
        logger.info(json.dumps({
            "event": "config_evaluation_triggered",
            "config_rule": config_rule,
            "note": "Forced fresh evaluation before compliance check",
        }))
    except ClientError as exc:
        # Non-fatal: evaluation may already be running. Continue to compliance check.
        logger.warning(json.dumps({
            "event": "config_evaluation_trigger_failed",
            "config_rule": config_rule,
            "error": str(exc),
        }))

    try:
        kwargs: dict = {
            "ConfigRuleName": config_rule,
            "ComplianceTypes": ["NON_COMPLIANT"],
            "Limit": 10,
        }
        if resource_type and resource_id:
            kwargs["Filters"] = {"ResourceType": resource_type, "ResourceId": resource_id}
        elif resource_type:
            kwargs["Filters"] = {"ResourceType": resource_type}

        resp = _config_client.get_compliance_details_by_config_rule(**kwargs)
        non_compliant_items = resp.get("EvaluationResults", [])
    except ClientError as exc:
        return ("inconclusive", signal_desc, f"Config GetComplianceDetailsByConfigRule error: {exc}")

    if not non_compliant_items:
        return (
            "resolved",
            signal_desc,
            (
                f"Config rule '{config_rule}' returned 0 NON_COMPLIANT resources. "
                "Resource is now compliant - incident resolved."
            ),
        )

    resource_list = [
        (e.get("EvaluationResultIdentifier", {})
         .get("EvaluationResultQualifier", {})
         .get("ResourceId", "unknown"))
        for e in non_compliant_items
    ]

    # Config still shows NON_COMPLIANT - it may not have re-evaluated yet after
    # the lock_s3_bucket remediation. Fall back to directly checking the S3 public
    # access block for each non-compliant bucket resource.
    s3_check_result = _check_s3_public_access_block(resource_list)
    if s3_check_result is not None:
        status, s3_notes = s3_check_result
        return (
            status,
            f"S3 public access block (Config eval lag fallback for '{config_rule}')",
            s3_notes,
        )

    return (
        "not_resolved",
        signal_desc,
        (
            f"Config rule '{config_rule}' still has {len(non_compliant_items)} NON_COMPLIANT "
            f"resource(s): {', '.join(resource_list)}. Config may not have re-evaluated yet."
        ),
    )


# ===========================================================================
# service_cascade: re-check Service A errors + Service C latency
# ===========================================================================

def _recheck_service_cascade(signal: dict) -> tuple[str, str, str]:
    """
    Re-check both signals that define the composite cascade alarm:
    - Service A: Errors sum < error_threshold
    - Service C: Duration average <= latency_threshold

    Both must be below threshold for the incident to be "resolved".

    Fallback: if neither service has recent metric datapoints (demo scenario
    where the composite alarm was triggered via SetAlarmState without real
    traffic), fall back to checking the composite alarm state directly.
    This prevents a false "resolved" from 0-defaulted metrics while the
    composite alarm may still be in ALARM state.
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
        )

    signal_desc = (
        f"Service A Errors (sum, threshold {error_threshold}) + "
        f"Service C Duration (avg, threshold {latency_threshold}ms)"
    )

    try:
        a_errors_data = _get_lambda_metric_datapoints(service_a_name, "Errors", "Sum")
        c_latency_data = _get_lambda_metric_datapoints(service_c_name, "Duration", "Average")
    except ClientError as exc:
        return ("inconclusive", signal_desc, f"CloudWatch GetMetricStatistics error: {exc}")

    # No datapoints for EITHER service - this is the demo scenario (SetAlarmState,
    # no real traffic). Defaulting to 0 would always return "resolved" which is a
    # false positive if the composite alarm is still in ALARM state.
    # Fall back to the composite alarm state as the authoritative signal.
    if not a_errors_data and not c_latency_data:
        if alarm_name:
            alarm_status, alarm_notes = _get_alarm_state_composite(alarm_name)
            fallback_desc = f"Composite alarm state for '{alarm_name}' (no recent Lambda invocations)"
            return (alarm_status, fallback_desc, alarm_notes)
        return (
            "inconclusive",
            signal_desc,
            (
                "No metric datapoints for ServiceA or ServiceC in the last "
                f"{METRIC_LOOKBACK_SECONDS}s and no composite alarm name to check. "
                "Services may not have been invoked since remediation."
            ),
        )

    a_max_errors = max((dp["value"] for dp in a_errors_data), default=0)
    c_max_latency = max((dp["value"] for dp in c_latency_data), default=0)

    notes = (
        f"Service A max errors = {a_max_errors:.0f} (threshold {error_threshold}); "
        f"Service C max duration = {c_max_latency:.0f}ms (threshold {latency_threshold}ms)."
    )

    if a_max_errors < error_threshold and c_max_latency <= latency_threshold:
        return ("resolved", signal_desc, notes + " Both below threshold - cascade resolved.")

    still_firing = []
    if a_max_errors >= error_threshold:
        still_firing.append(f"Service A errors ({a_max_errors:.0f} >= {error_threshold})")
    if c_max_latency > latency_threshold:
        still_firing.append(f"Service C latency ({c_max_latency:.0f}ms > {latency_threshold}ms)")

    return (
        "not_resolved",
        signal_desc,
        notes + " Still above threshold: " + "; ".join(still_firing) + ".",
    )


# ===========================================================================
# DynamoDB write-back
# ===========================================================================

def _update_verification_record(
    incident_id: str,
    status: str,
    signal_rechecked: str,
    notes: str,
) -> None:
    """
    Write the verification outcome to IncidentRecord.verification.
    This is the core data that feeds the diagnosis-recovery gap metric.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        _dynamodb.Table(INCIDENTS_TABLE).update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=(
                "SET verification.#st = :status, "
                "verification.checked_at = :checked_at, "
                "verification.signal_rechecked = :signal, "
                "verification.notes = :notes"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":checked_at": now,
                ":signal": signal_rechecked,
                ":notes": notes,
            },
        )
        logger.info(json.dumps({
            "event": "verification_record_written",
            "incident_id": incident_id,
            "status": status,
            "checked_at": now,
        }))
    except ClientError as exc:
        # This is serious - losing verification data means losing the paper's
        # key metric for this incident. Log with maximum urgency.
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
