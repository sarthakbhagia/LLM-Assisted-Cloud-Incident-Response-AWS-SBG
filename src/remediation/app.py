"""
app.py - Phase 6: Remediation Lambda Handler

Receives {"incident_id": "..."} from the approval handler (async invoke).

Pipeline:
  1. Fetch full IncidentRecord from DynamoDB
  2. Defensive check: remediation.status must be "approved"
  3. Read diagnosis.suggested_action and dispatch to the correct actions.py function
  4. Update DynamoDB: set status to "executed" or "failed", record action_taken
  5. Build the original_signal payload for the verification Lambda
  6. Async-invoke the verification Lambda (Phase 6.5)

Guardrails enforced here:
  - Step 2: double-check that status is "approved" before executing anything.
    The conditional DynamoDB update in the approval handler is the primary gate;
    this is a defensive check that catches any race or mis-invocation.
  - actions.py is the only code that touches AWS resources for remediation.
    The LLM-produced suggested_action string is used only as a dispatch key -
    it never becomes executable code or IAM policy JSON.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

try:
    from actions import dispatch
except ImportError:
    from .actions import dispatch

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_dynamodb = boto3.resource("dynamodb")
_lambda = boto3.client("lambda")

INCIDENTS_TABLE = os.environ["INCIDENTS_TABLE"]
DATA_LAKE_BUCKET = os.environ.get("DATA_LAKE_BUCKET", "")
VERIFICATION_FUNCTION_NAME = os.environ.get("VERIFICATION_FUNCTION_NAME", "")

# ===========================================================================
# Entry point
# ===========================================================================

def lambda_handler(event, context):
    logger.info(json.dumps({"event": "remediation_triggered", "payload": event}, default=str))

    incident_id = event.get("incident_id")
    if not incident_id:
        logger.error("Missing incident_id in event payload")
        return {"statusCode": 400, "body": json.dumps({"error": "Missing incident_id"})}

    # 1. Fetch full IncidentRecord from DynamoDB
    record = _get_incident_record(incident_id)
    if not record:
        logger.error(json.dumps({"event": "record_not_found", "incident_id": incident_id}))
        return {"statusCode": 404, "body": json.dumps({"error": f"Incident '{incident_id}' not found."})}

    # 2. Defensive status check - the approval handler's conditional write is the
    #    primary gate, but we check again here before touching any AWS resource.
    remediation_status = (record.get("remediation") or {}).get("status")
    if remediation_status != "approved":
        logger.warning(json.dumps({
            "event": "remediation_skipped_wrong_status",
            "incident_id": incident_id,
            "current_status": remediation_status,
        }))
        return {
            "statusCode": 409,
            "body": json.dumps({
                "error": (
                    f"Expected remediation.status='approved', got '{remediation_status}'. "
                    "No remediation action was executed."
                )
            }),
        }

    # 3. Determine action key from the LLM diagnosis
    diagnosis = record.get("diagnosis") or {}
    action_key = (diagnosis.get("suggested_action") or "manual_review_required").strip()
    fault_class = record.get("fault_class", "unknown")

    logger.info(json.dumps({
        "event": "dispatching_action",
        "incident_id": incident_id,
        "action_key": action_key,
        "fault_class": fault_class,
    }))

    # 4. Execute the action - actions.py handles all actual AWS API calls
    result = dispatch(action_key, record)

    logger.info(json.dumps({
        "event": "action_result",
        "incident_id": incident_id,
        "success": result["success"],
        "action_key": result["action_key"],
        "notes": result["notes"],
    }))

    # 5. Update DynamoDB with the outcome
    now = datetime.now(timezone.utc).isoformat()
    new_remediation_status = "executed" if result["success"] else "failed"
    _update_remediation_record(incident_id, new_remediation_status, result["action_key"], result["notes"], now)

    # 6. Build original_signal payload (thresholds from template.yaml - hardcoded to avoid
    #    needing DescribeAlarms; these must match the alarm definitions in template.yaml)
    original_signal = _build_original_signal(record)

    # 7. Async-invoke verification Lambda (Phase 6.5)
    _invoke_verification(incident_id, fault_class, original_signal)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "incident_id": incident_id,
            "action_key": action_key,
            "success": result["success"],
            "new_status": new_remediation_status,
            "notes": result["notes"],
        }),
    }


# ===========================================================================
# DynamoDB helpers
# ===========================================================================

def _get_incident_record(incident_id: str) -> dict | None:
    try:
        resp = _dynamodb.Table(INCIDENTS_TABLE).get_item(Key={"incident_id": incident_id})
        return resp.get("Item")
    except ClientError as exc:
        logger.error(json.dumps({
            "event": "dynamodb_get_error",
            "incident_id": incident_id,
            "error": str(exc),
        }))
        return None


def _update_remediation_record(
    incident_id: str,
    new_status: str,
    action_taken: str,
    notes: str,
    executed_at: str,
) -> None:
    try:
        _dynamodb.Table(INCIDENTS_TABLE).update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=(
                "SET remediation.#st = :status, "
                "remediation.action_taken = :action, "
                "remediation.executed_at = :executed_at, "
                "remediation.notes = :notes"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": new_status,
                ":action": action_taken,
                ":executed_at": executed_at,
                ":notes": notes,
            },
        )
        logger.info(json.dumps({
            "event": "dynamodb_remediation_updated",
            "incident_id": incident_id,
            "new_status": new_status,
            "action_taken": action_taken,
        }))
    except ClientError as exc:
        # Log but do not raise - the action has already executed.
        # Losing the DynamoDB write here means we lose evaluation data,
        # which is worse than an unclean status, so log loudly.
        logger.error(json.dumps({
            "event": "dynamodb_update_error",
            "incident_id": incident_id,
            "error": str(exc),
            "ATTENTION": "DynamoDB write failed after action executed - incident record may be stale",
        }))


# ===========================================================================
# Verification payload construction
# ===========================================================================

def _build_original_signal(record: dict) -> dict:
    """
    Build the signal description dict for the verification Lambda.
    Alarm thresholds are hardcoded here to match the alarm definitions in
    template.yaml - this avoids a DescribeAlarms call and keeps the
    remediation Lambda's IAM role tightly scoped.

    If template.yaml alarm thresholds change, this function must be updated.
    """
    fault_class = record.get("fault_class", "unknown")
    resource_id = (record.get("resource_id") or "").strip()
    detection_source = (record.get("detection_source") or "").strip()

    signal: dict = {
        "fault_class": fault_class,
        "resource_id": resource_id,
        "detection_source": detection_source,
    }

    if fault_class == "resource_exhaustion":
        # resource_id for cloudwatch-triggered incidents is the alarm name
        signal["alarm_name"] = resource_id
        signal["metric_name"] = "Duration"
        # Threshold from template.yaml ServiceAResourceExhaustionAlarm (ms)
        signal["threshold"] = 50000

    elif fault_class == "misconfiguration":
        # The collector stores the parsed event; try to extract config_rule from it.
        # The raw_data detection_event field is not in DynamoDB - we use resource_id
        # as the config_rule name fallback (the collector populates resource_id from config_rule
        # for misconfiguration events from Config).
        diagnosis = record.get("diagnosis") or {}
        affected = diagnosis.get("affected_resources") or []
        signal["config_rule"] = resource_id  # alarm_name / resource_id for Config events IS the rule name
        signal["resource_type"] = affected[0] if affected else None

    elif fault_class == "service_cascade":
        signal["alarm_name"] = resource_id
        # Thresholds from template.yaml (must stay in sync)
        signal["service_a_error_threshold"] = 5       # ServiceAErrorAlarm: Errors >= 5 over 2 periods
        signal["service_c_latency_threshold"] = 3000  # ServiceCHighLatencyAlarm: Duration avg > 3000ms

    return signal


# ===========================================================================
# Verification Lambda invocation
# ===========================================================================

def _invoke_verification(incident_id: str, fault_class: str, original_signal: dict) -> None:
    if not VERIFICATION_FUNCTION_NAME:
        logger.warning(json.dumps({
            "event": "verification_invoke_skipped",
            "reason": "VERIFICATION_FUNCTION_NAME env var is not set (Phase 6.5 not deployed yet)",
            "incident_id": incident_id,
        }))
        return

    payload = {
        "incident_id": incident_id,
        "fault_class": fault_class,
        "original_signal": original_signal,
    }
    try:
        _lambda.invoke(
            FunctionName=VERIFICATION_FUNCTION_NAME,
            InvocationType="Event",  # async - remediation does not wait for verification
            Payload=json.dumps(payload),
        )
        logger.info(json.dumps({
            "event": "verification_invoked",
            "incident_id": incident_id,
            "function": VERIFICATION_FUNCTION_NAME,
        }))
    except ClientError as exc:
        # Log but do not raise - remediation has already executed and been recorded.
        # Missing verification is a data loss for the paper, not a system failure.
        logger.error(json.dumps({
            "event": "verification_invoke_error",
            "incident_id": incident_id,
            "error": str(exc),
            "ATTENTION": "Verification Lambda could not be invoked - verification.status will remain 'not_run'",
        }))
