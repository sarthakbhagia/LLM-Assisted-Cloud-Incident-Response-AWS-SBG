"""
verification_lambda.py — Phase 6.5: Closed-loop Verification Lambda

Core research novelty: after remediation executes, wait 2 minutes,
re-query the same signal that triggered detection, and write the result
back to IncidentRecord.verification.

This measures the gap between "the LLM diagnosed correctly" and
"the fix actually resolved the incident" - which is the paper's
headline contribution (diagnosis-recovery gap metric).

Two-phase design (no sleeping in the function):
  Phase 1 (first invoke, no `phase` field):
      Registers a one-off EventBridge Scheduler schedule ~VERIFICATION_WAIT_SECONDS
      in the future whose target re-invokes THIS Lambda with phase="recheck"
      and the original payload. Returns immediately - zero billed wall-clock
      wait, no container held hostage, and Scheduler's built-in retry policy
      covers transient failures (the old time.sleep(120) version did neither).
  Phase 2 (scheduled invoke, phase="recheck"):
      Runs the signal re-check and writes the outcome to DynamoDB.

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
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_cw = boto3.client("cloudwatch")
_config_client = boto3.client("config")
_dynamodb = boto3.resource("dynamodb")
_lambda_client = boto3.client("lambda")
_scheduler = boto3.client("scheduler")

INCIDENTS_TABLE = os.environ["INCIDENTS_TABLE"]

# Delay before re-checking (2 minutes, per spec step 21 "2-5 minutes")
VERIFICATION_WAIT_SECONDS = int(os.environ.get("VERIFICATION_WAIT_SECONDS", "120"))

# IAM role the EventBridge Scheduler assumes to invoke this function
SCHEDULER_ROLE_ARN = os.environ.get("SCHEDULER_ROLE_ARN", "")
# Named schedule group the one-off schedules are created in (matches IAM scope)
SCHEDULER_GROUP_NAME = os.environ.get("SCHEDULER_GROUP_NAME", "default")
# Shared pipeline DLQ: Scheduler delivers here when re-check delivery fails
PIPELINE_DLQ_ARN = os.environ.get("PIPELINE_DLQ_ARN", "")

# Lookback window for metric re-check (last 5 minutes of data points)
METRIC_LOOKBACK_SECONDS = 300


# ===========================================================================
# Entry point
# ===========================================================================

def lambda_handler(event, context):
    payload = event if isinstance(event, dict) else {}
    logger.info(json.dumps({"event": "verification_triggered", "payload": payload}, default=str))

    incident_id = payload.get("incident_id")
    if not incident_id:
        logger.error("Missing incident_id in verification event")
        return {"statusCode": 400, "body": json.dumps({"error": "Missing incident_id"})}

    if payload.get("phase") == "recheck":
        return _run_recheck(payload)
    return _schedule_recheck(payload, context)


# ===========================================================================
# Phase 1: register the one-off scheduled re-check
# ===========================================================================

def _schedule_recheck(payload: dict, context) -> dict:
    incident_id = payload["incident_id"]
    # Original event-id of the trigger (set by the DLQ replay script) so the
    # one-off schedule name is unique per replayed delivery.
    event_uid = payload.get("event_uid")
    suffix = f"-{event_uid}" if event_uid else ""
    incident_id_log = incident_id if not event_uid else f"{incident_id}#evt:{event_uid}"

    # Re-invoking verification (e.g. the sweeper retried remediation) must not
    # stack duplicate schedules; the name is unique per incident.
    schedule_name = f"verify-{incident_id}{suffix}"[:64]
    run_at = datetime.now(timezone.utc) + timedelta(seconds=VERIFICATION_WAIT_SECONDS)
    # one-off "at()" schedules are expressed in UTC
    schedule_expression = f"at({run_at.strftime('%Y-%m-%dT%H:%M:%S')})"

    target_arn = (
        getattr(context, "invoked_function_arn", None) if context is not None else None
    ) or os.environ.get("VERIFICATION_FUNCTION_ARN", "")

    if not target_arn:
        logger.error(json.dumps({
            "event": "verification_schedule_error",
            "incident_id": incident_id,
            "error": "no target function ARN (no Lambda context and VERIFICATION_FUNCTION_ARN unset)",
        }))
        return {"statusCode": 500, "body": json.dumps({"error": "Verification target not configured"})}

    recheck_payload = dict(payload, phase="recheck")
    try:
        _scheduler.create_schedule(
            Name=schedule_name,
            GroupName=SCHEDULER_GROUP_NAME,
            ScheduleExpression=schedule_expression,
            ScheduleExpressionTimezone="UTC",
            FlexibleTimeWindow={"Mode": "OFF"},
            ActionAfterCompletion="DELETE",  # one-shot: clean itself up
            Target={
                "Arn": target_arn,
                "RoleArn": SCHEDULER_ROLE_ARN,
                "Input": json.dumps(recheck_payload, default=str),
                "RetryPolicy": {
                    "MaximumRetryAttempts": 5,
                    "MaximumEventAgeInSeconds": 3600,
                },
                # After Scheduler's retries exhaust, land the re-check payload
                # in the shared pipeline DLQ so the loss is alarmed on.
                "DeadLetterConfig": {"Arn": PIPELINE_DLQ_ARN},
            },
        )
        logger.info(json.dumps({
            "event": "verification_scheduled",
            "incident_id": incident_id_log,
            "schedule_name": schedule_name,
            "recheck_at": run_at.isoformat(),
            "wait_seconds": VERIFICATION_WAIT_SECONDS,
        }))
        return {
            "statusCode": 200,
            "body": json.dumps({
                "incident_id": incident_id,
                "scheduled": True,
                "schedule_name": schedule_name,
                "recheck_at": run_at.isoformat(),
            }),
        }
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConflictException":
            # Already scheduled for this incident (duplicate invoke) - idempotent.
            logger.info(json.dumps({
                "event": "verification_schedule_exists",
                "incident_id": incident_id,
                "schedule_name": schedule_name,
            }))
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "incident_id": incident_id,
                    "scheduled": True,
                    "already_scheduled": True,
                    "schedule_name": schedule_name,
                }),
            }
        logger.error(json.dumps({
            "event": "verification_schedule_error",
            "incident_id": incident_id,
            "error": str(exc),
            "ATTENTION": (
                "Could not schedule the verification re-check. This incident will "
                "keep verification.status='not_run' unless re-invoked."
            ),
        }))
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": f"Failed to schedule verification re-check: {exc}"
            }),
        }


# ===========================================================================
# Phase 2: the scheduled re-check (original Phase 6.5 logic)
# ===========================================================================

def _run_recheck(payload: dict) -> dict:
    incident_id = payload["incident_id"]
    fault_class = payload.get("fault_class", "unknown")
    original_signal = payload.get("original_signal") or {}

    status, signal_rechecked, notes = _recheck_signal(fault_class, original_signal)

    logger.info(json.dumps({
        "event": "verification_result",
        "incident_id": incident_id,
        "status": status,
        "signal_rechecked": signal_rechecked,
        "notes": notes,
    }))

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
        return (
            "inconclusive",
            signal_desc,
            (
                f"No {metric_name} datapoints returned for '{function_name}' "
                f"in the last {METRIC_LOOKBACK_SECONDS}s. Function may not have been invoked "
                "since remediation, or metrics have not yet populated."
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


# ===========================================================================
# misconfiguration: re-check Config rule compliance
# ===========================================================================

def _recheck_misconfiguration(signal: dict) -> tuple[str, str, str]:
    """
    Re-check the Config rule compliance status for the flagged resource.
    If 0 NON_COMPLIANT results are returned for the rule (optionally filtered
    to the specific resource), the incident is considered resolved.
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
    return (
        "not_resolved",
        signal_desc,
        (
            f"Config rule '{config_rule}' still has {len(non_compliant_items)} NON_COMPLIANT "
            f"resource(s): {', '.join(resource_list)}."
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
    """
    error_threshold = signal.get("service_a_error_threshold", 5)
    latency_threshold = signal.get("service_c_latency_threshold", 3000)

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
