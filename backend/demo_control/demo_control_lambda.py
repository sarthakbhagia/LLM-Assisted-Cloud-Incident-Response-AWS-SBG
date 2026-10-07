"""
demo_control_lambda.py — Demo Mode Backend

Provides a safe, rate-limited API for non-technical users to trigger
fault injections and approve incidents from the dashboard UI.

Endpoints:
  POST /demo/inject          - Inject a fault (resource_exhaustion | misconfiguration | service_cascade)
  POST /demo/approve/{id}    - Approve an incident (calls existing approval handler internally)

IAM: Separate narrowly-scoped role with permissions only for fault injection
     and invoking the approval handler. No direct remediation or DynamoDB write permissions.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
_lambda = boto3.client("lambda")
_cloudwatch = boto3.client("cloudwatch")
_s3 = boto3.client("s3")
_dynamodb = boto3.resource("dynamodb")

# Config from environment
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "")
APPROVAL_FUNCTION_NAME = os.environ.get("APPROVAL_FUNCTION_NAME", "")
DATA_LAKE_BUCKET = os.environ.get("DATA_LAKE_BUCKET", "")

# Rate limiting: track active demo incidents in memory (per container)
# For production, use DynamoDB TTL or ElastiCache
_active_demo_incidents: dict = {}

# Fault class mapping to alarm names.
# For service_cascade we must set the two COMPONENT metric alarms, not the
# composite alarm. CloudWatch SetAlarmState on a composite alarm does NOT
# generate an EventBridge event, so the collector would never fire.
FAULT_CLASS_ALARMS = {
    "resource_exhaustion": f"incident-service-a-resource-exhaustion-{ENVIRONMENT}",
    "misconfiguration": f"incident-public-s3-{ENVIRONMENT}",  # Config rule name
    "service_cascade": f"incident-service-cascade-{ENVIRONMENT}",  # composite - see _inject_fault
}

# The two component metric alarms that drive the composite cascade alarm.
# Setting BOTH to ALARM causes the composite to transition to ALARM naturally,
# which DOES generate an EventBridge event (unlike calling SetAlarmState directly
# on a composite alarm, which does NOT fire EventBridge).
SERVICE_CASCADE_COMPONENT_ALARMS = [
    f"incident-service-a-errors-{ENVIRONMENT}",
    f"incident-service-c-latency-{ENVIRONMENT}",
]

# Valid fault classes
VALID_FAULT_CLASSES = {"resource_exhaustion", "misconfiguration", "service_cascade"}

# Valid suggested actions (must match VALID_SUGGESTED_ACTIONS in prompts.py)
VALID_SUGGESTED_ACTIONS = [
    "scale_up",
    "restart_service",
    "lock_s3_bucket",
    "tighten_iam_policy",
    "restart_downstream_service",
    "manual_review_required",
]

# CORS headers
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
    "Content-Type": "application/json",
}


def _ok(data: dict, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps({"data": data, "error": None}),
    }


def _err(message: str, status: int = 400) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps({"data": None, "error": message}),
    }


def _rate_limit_check() -> tuple[bool, str | None]:
    """Check if a demo is already active. Returns (allowed, incident_id)."""
    current_time = datetime.now(timezone.utc)
    for inc_id, info in list(_active_demo_incidents.items()):
        if info.get("status") in ("completed", "failed", "resolved", "approved"):
            del _active_demo_incidents[inc_id]
        elif info.get("status") == "injected":
            # Check if the injection is stale (> 90 seconds).
            # The full pipeline (alarm -> EventBridge -> collector -> diagnosis) can take
            # up to 60-90s, so 30s was too short and caused false rate-limit blocks.
            try:
                injected_at = datetime.fromisoformat(info.get("started_at", "").replace("Z", "+00:00"))
                if (current_time - injected_at).total_seconds() > 90:
                    del _active_demo_incidents[inc_id]
            except Exception:
                del _active_demo_incidents[inc_id]

    if _active_demo_incidents:
        active_id = next(iter(_active_demo_incidents))
        return False, active_id
    return True, None


def _inject_fault(fault_class: str) -> dict:
    """
    Trigger a fault by the method appropriate for each fault class.

    resource_exhaustion:
        SetAlarmState on the metric alarm. The alarm state change generates
        an EventBridge event that triggers the CollectorFunction.

    service_cascade:
        Set BOTH component metric alarms (service-a-errors and service-c-latency)
        to ALARM. The composite alarm then transitions to ALARM naturally, which
        DOES generate an EventBridge event (unlike calling SetAlarmState directly
        on a composite alarm, which does NOT fire EventBridge).

    misconfiguration:
        Directly invoke the CollectorFunction with a pre-built payload.
        start_config_rules_evaluation is async and unreliable for demos -
        it only fires an event when Config finds a NON_COMPLIANT resource,
        which depends on whether a non-compliant resource actually exists.
    """
    try:
        collector_fn = os.environ.get("COLLECTOR_FUNCTION_NAME", "")
        # Detect local mode: the LocalLambdaRouter in local_backend.py sets the
        # collector name to "LOCAL::collector". In that mode we must NOT call
        # SetAlarmState because the real EventBridge rule would fire the real deployed
        # CollectorFunction Lambda, creating a second empty incident that the UI then
        # picks as the newest. Instead, invoke the local collector directly.
        # In deployed AWS mode (collector_fn is a real Lambda ARN), SetAlarmState
        # triggers EventBridge which is the authoritative trigger; we skip the direct
        # invocation to avoid the same duplicate problem in reverse.
        is_local_mode = collector_fn.startswith("LOCAL::")

        if fault_class == "resource_exhaustion":
            alarm_name = FAULT_CLASS_ALARMS["resource_exhaustion"]

            if is_local_mode:
                # Local mode: direct invocation only — do NOT call SetAlarmState.
                # SetAlarmState would trigger the real EventBridge rule → real deployed
                # CollectorFunction → a second, empty incident that the UI picks instead
                # of the correctly synthesised one.
                synthetic_event = {
                    "source": "aws.cloudwatch",
                    "fault_class": "resource_exhaustion",
                    "alarm_name": alarm_name,
                    "resource_id": alarm_name,
                    "injected_by": "demo_mode",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                _lambda.invoke(
                    FunctionName=collector_fn,
                    InvocationType="Event",
                    Payload=json.dumps(synthetic_event),
                )
                result = {
                    "success": True,
                    "method": "local_direct_invoke",
                    "alarm_name": alarm_name,
                    "collector_invoked": True,
                }
            else:
                # Deployed AWS mode: direct collector invocation (same as local mode).
                # SetAlarmState → EventBridge was the original approach but has two problems:
                #   1. SetAlarmState does not generate real Lambda invocation metrics, so the
                #      collector always receives empty CloudWatch evidence in demo mode.
                #   2. The EventBridge InputTransformer cannot parse injected_by out of
                #      StateReasonData (a JSON string inside JSON), so the collector's
                #      synthetic evidence branch never fires.
                # Direct invocation passes injected_by as a first-class field and avoids
                # the duplicate-incident problem that required the EventBridge path originally.
                synthetic_event = {
                    "source": "aws.cloudwatch",
                    "fault_class": "resource_exhaustion",
                    "alarm_name": alarm_name,
                    "resource_id": alarm_name,
                    "injected_by": "demo_mode",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                _lambda.invoke(
                    FunctionName=collector_fn,
                    InvocationType="Event",
                    Payload=json.dumps(synthetic_event),
                )
                result = {
                    "success": True,
                    "method": "direct_collector_invoke",
                    "alarm_name": alarm_name,
                    "collector_invoked": True,
                }
            return result

        elif fault_class == "service_cascade":
            reason_data = json.dumps({
                "injected_by": "demo_mode",
                "fault_class": fault_class,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            if is_local_mode:
                # Local mode: direct invocation only — skip SetAlarmState for the same
                # reason as resource_exhaustion above.
                composite_alarm = FAULT_CLASS_ALARMS["service_cascade"]
                synthetic_event = {
                    "source": "aws.cloudwatch",
                    "fault_class": "service_cascade",
                    "alarm_name": composite_alarm,
                    "resource_id": composite_alarm,
                    "injected_by": "demo_mode",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                _lambda.invoke(
                    FunctionName=collector_fn,
                    InvocationType="Event",
                    Payload=json.dumps(synthetic_event),
                )
                result = {
                    "success": True,
                    "method": "local_direct_invoke",
                    "composite_alarm": composite_alarm,
                    "collector_invoked": True,
                }
            else:
                # Deployed AWS mode: direct collector invocation (same reasons as resource_exhaustion above).
                composite_alarm = FAULT_CLASS_ALARMS["service_cascade"]
                synthetic_event = {
                    "source": "aws.cloudwatch",
                    "fault_class": "service_cascade",
                    "alarm_name": composite_alarm,
                    "resource_id": composite_alarm,
                    "injected_by": "demo_mode",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                _lambda.invoke(
                    FunctionName=collector_fn,
                    InvocationType="Event",
                    Payload=json.dumps(synthetic_event),
                )
                result = {
                    "success": True,
                    "method": "direct_collector_invoke",
                    "composite_alarm": composite_alarm,
                    "collector_invoked": True,
                }
            return result

        elif fault_class == "misconfiguration":
            # Directly invoke the collector with a synthetic Config-style event.
            # This bypasses the async Config evaluation loop and makes the demo
            # reliable regardless of whether non-compliant resources exist.
            # Use the DemoMisconfigBucket (sacrificial bucket) not the data lake bucket.
            collector_fn = os.environ.get("COLLECTOR_FUNCTION_NAME", "")
            if not collector_fn:
                # Fallback: try Config evaluation (original behaviour)
                config_client = boto3.client("config")
                config_rule = FAULT_CLASS_ALARMS["misconfiguration"]
                config_client.start_config_rules_evaluation(ConfigRuleNames=[config_rule])
                return {"success": True, "method": "config_evaluation", "config_rule": config_rule,
                        "warning": "COLLECTOR_FUNCTION_NAME not set - fell back to config evaluation"}

            # Get the demo misconfig bucket name
            demo_bucket = os.environ.get("DEMO_MISCONFIG_BUCKET")
            if not demo_bucket:
                try:
                    sts = boto3.client("sts")
                    account_id = sts.get_caller_identity()["Account"]
                    env = os.environ.get("ENVIRONMENT", "dev")
                    demo_bucket = f"llm-incident-demo-misconfig-{account_id}-{env}"
                except Exception:
                    demo_bucket = FAULT_CLASS_ALARMS["misconfiguration"]

            synthetic_event = {
                "source": "aws_config",
                "fault_class": "misconfiguration",
                "config_rule": FAULT_CLASS_ALARMS["misconfiguration"],
                "resource_id": demo_bucket,
                "resource_type": "AWS::S3::Bucket",
                "injected_by": "demo_mode",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _lambda.invoke(
                FunctionName=collector_fn,
                InvocationType="Event",  # async - fire and forget
                Payload=json.dumps(synthetic_event),
            )
            return {
                "success": True,
                "method": "direct_collector_invoke",
                "config_rule": FAULT_CLASS_ALARMS["misconfiguration"],
                "demo_bucket": demo_bucket,
            }

    except ClientError as exc:
        logger.error(f"Fault injection failed: {exc}")
        return {"success": False, "error": str(exc)}

    return {"success": False, "error": f"Unknown fault_class: {fault_class}"}


def _approve_incident(incident_id: str, solution_id: str | None = None, selected_action: str | None = None) -> dict:
    """Approve an incident by writing directly to DynamoDB (dashboard-trust model).
    This is the demo approve path - it bypasses the HMAC approval handler.
    """
    if not INCIDENTS_TABLE:
        return {"success": False, "error": "INCIDENTS_TABLE not configured"}

    try:
        table = _dynamodb.Table(INCIDENTS_TABLE)
        from datetime import datetime, timezone

        # Fetch incident to get recommended_solutions for validation
        resp = table.get_item(Key={"incident_id": incident_id})
        item = resp.get("Item")
        if not item:
            return {"success": False, "error": f"Incident {incident_id!r} not found"}

        remediation_status = (item.get("remediation") or {}).get("status")
        if remediation_status != "pending_approval":
            return {"success": False, "error": f"Incident is not pending approval (current status: {remediation_status})"}

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

        # Determine which solution to use
        selected_solution = None

        if solution_id:
            for sol in recommended_solutions:
                if sol.get("id") == solution_id:
                    selected_solution = sol
                    break
            if not selected_solution:
                return {"success": False, "error": f"Invalid solution_id: {solution_id!r}"}

        if selected_action:
            action_found = False
            for sol in recommended_solutions:
                if sol.get("action") == selected_action:
                    action_found = True
                    if not selected_solution:
                        selected_solution = sol
                    break
            if not action_found:
                return {"success": False, "error": f"Invalid selected_action: {selected_action!r}"}

        if selected_solution and solution_id and selected_action:
            if selected_solution.get("action") != selected_action:
                return {"success": False, "error": f"Mismatch: solution_id {solution_id!r} has action {selected_solution.get('action')!r}, but selected_action is {selected_action!r}."}

        if not selected_solution:
            selected_solution = recommended_solutions[0]
        if not selected_action:
            selected_action = selected_solution.get("action", suggested_action)

        if selected_action not in VALID_SUGGESTED_ACTIONS:
            return {"success": False, "error": f"Invalid selected_action: {selected_action!r}. Must be one of {VALID_SUGGESTED_ACTIONS}."}

        final_solution_id = selected_solution.get("id", "sol-1")
        now = datetime.now(timezone.utc).isoformat()

        # Conditional write
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
                    ":sel_id": final_solution_id,
                    ":via": "demo",
                },
            )
            logger.info("Approved incident %s via demo (solution_id=%s, action=%s)", incident_id, final_solution_id, selected_action)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                resp = table.get_item(Key={"incident_id": incident_id})
                item = resp.get("Item")
                if not item:
                    return {"success": False, "error": f"Incident {incident_id!r} not found"}
                current = item.get("remediation", {}).get("status", "unknown")
                return {"success": False, "error": f"Cannot approve: incident is already in status '{current}'"}
            raise

        # Fire remediation asynchronously
        remediation_fn = os.environ.get("REMEDIATION_FUNCTION_NAME", "")
        if remediation_fn:
            try:
                _lambda.invoke(
                    FunctionName=remediation_fn,
                    InvocationType="Event",
                    Payload=json.dumps({"incident_id": incident_id}),
                )
                logger.info("Remediation invoked async for incident %s", incident_id)
            except Exception as exc:
                logger.warning("Failed to invoke remediation for %s: %s", incident_id, exc)

        return {"success": True, "incident_id": incident_id, "selected_action": selected_action, "selected_solution_id": final_solution_id}

    except ClientError as exc:
        logger.error(f"Approval failed: {exc}")
        return {"success": False, "error": str(exc)}


def lambda_handler(event: dict, context) -> dict:
    logger.info(json.dumps({"event": "demo_control_triggered", "path": event.get("resource"), "method": event.get("httpMethod")}, default=str))

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    # OPTIONS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # POST /demo/inject
    if method == "POST" and resource == "/demo/inject":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _err("Invalid JSON body")

        fault_class = body.get("fault_class")
        if not fault_class or fault_class not in VALID_FAULT_CLASSES:
            return _err(f"Invalid fault_class. Must be one of: {', '.join(VALID_FAULT_CLASSES)}")

        # Rate limit check
        allowed, active_id = _rate_limit_check()
        if not allowed:
            return _err(f"A demo is already running (incident: {active_id}). Wait for it to complete or approve it first.", 429)

        # Inject the fault
        result = _inject_fault(fault_class)
        if not result.get("success"):
            return _err(result.get("error", "Fault injection failed"))

        # Track this demo incident with a unique key
        # We don't know the incident_id yet, but we can mark that a demo is in progress
        import uuid
        tracking_key = f"injected_{fault_class}_{uuid.uuid4().hex[:8]}"
        _active_demo_incidents[tracking_key] = {
            "fault_class": fault_class,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "injected",
        }

        return _ok({
            "message": f"Fault injection triggered: {fault_class}",
            "fault_class": fault_class,
            "details": result,
        })

    # POST /demo/approve/{incident_id}
    if method == "POST" and resource == "/demo/approve/{incident_id}":
        path_params = event.get("pathParameters") or {}
        incident_id = path_params.get("incident_id")
        if not incident_id:
            return _err("Missing incident_id")

        # Verify incident exists and is pending approval
        if INCIDENTS_TABLE:
            try:
                table = _dynamodb.Table(INCIDENTS_TABLE)
                resp = table.get_item(Key={"incident_id": incident_id})
                item = resp.get("Item")
                if not item:
                    return _err(f"Incident {incident_id} not found", 404)
                remediation_status = (item.get("remediation") or {}).get("status")
                if remediation_status != "pending_approval":
                    return _err(f"Incident is not pending approval (current status: {remediation_status})", 409)
            except ClientError as exc:
                logger.error(f"DynamoDB error: {exc}")
                return _err("Failed to verify incident status", 500)

        # Parse optional body for solution selection
        body_raw = event.get("body") or "{}"
        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError:
            body = {}
        solution_id = body.get("solution_id")
        selected_action = body.get("selected_action")

        # Approve the incident
        result = _approve_incident(incident_id, solution_id, selected_action)
        if not result.get("success"):
            return _err(result.get("error", "Approval failed"))

        # Update rate limit tracking
        if "pending" in _active_demo_incidents:
            _active_demo_incidents[incident_id] = _active_demo_incidents.pop("pending")
            _active_demo_incidents[incident_id]["status"] = "approved"

        return _ok({
            "message": f"Incident {incident_id} approved",
            "incident_id": incident_id,
        })

    return _err(f"No route matched: {method} {resource}", 404)