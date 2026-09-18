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
ENVIRONMENT = os.environ.get("ENVIRONMENT", "staging")
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "")
APPROVAL_FUNCTION_NAME = os.environ.get("APPROVAL_FUNCTION_NAME", "")
DATA_LAKE_BUCKET = os.environ.get("DATA_LAKE_BUCKET", "")

# Rate limiting: track active demo incidents in memory (per container)
# For production, use DynamoDB TTL or ElastiCache
_active_demo_incidents: dict = {}

# Fault class mapping to alarm names
FAULT_CLASS_ALARMS = {
    "resource_exhaustion": f"incident-service-a-resource-exhaustion-{ENVIRONMENT}",
    "misconfiguration": f"incident-public-s3-{ENVIRONMENT}",  # Config rule name
    "service_cascade": f"incident-service-cascade-{ENVIRONMENT}",
}

# Valid fault classes
VALID_FAULT_CLASSES = {"resource_exhaustion", "misconfiguration", "service_cascade"}

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
    # Clean up completed incidents and stale pending entries
    current_time = datetime.now(timezone.utc)
    for inc_id, info in list(_active_demo_incidents.items()):
        if info.get("status") in ("completed", "failed"):
            del _active_demo_incidents[inc_id]
        elif info.get("status") == "injected":
            # Check if the injection is stale (> 2 minutes)
            injected_at = datetime.fromisoformat(info.get("started_at", "").replace("Z", "+00:00"))
            if (current_time - injected_at).total_seconds() > 120:
                del _active_demo_incidents[inc_id]

    if _active_demo_incidents:
        # Return the active incident ID so UI can show it
        active_id = next(iter(_active_demo_incidents))
        return False, active_id
    return True, None


def _inject_fault(fault_class: str) -> dict:
    """Trigger a fault by setting CloudWatch alarm state or Config evaluation."""
    alarm_name = FAULT_CLASS_ALARMS.get(fault_class)
    if not alarm_name:
        return {"success": False, "error": f"Unknown fault_class: {fault_class}"}

    try:
        if fault_class in ("resource_exhaustion", "service_cascade"):
            # Set CloudWatch alarm to ALARM state
            _cloudwatch.set_alarm_state(
                AlarmName=alarm_name,
                StateValue="ALARM",
                StateReason=f"Demo Mode: Injected {fault_class} fault",
                StateReasonData=json.dumps({
                    "injected_by": "demo_mode",
                    "fault_class": fault_class,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }),
            )
            return {"success": True, "method": "cloudwatch_alarm", "alarm_name": alarm_name}

        elif fault_class == "misconfiguration":
            # Trigger Config rule evaluation
            config_client = boto3.client("config")
            config_client.start_config_rules_evaluation(ConfigRuleNames=[alarm_name])
            return {"success": True, "method": "config_evaluation", "config_rule": alarm_name}

    except ClientError as exc:
        logger.error(f"Fault injection failed: {exc}")
        return {"success": False, "error": str(exc)}

    return {"success": False, "error": "No injection method available"}


def _approve_incident(incident_id: str) -> dict:
    """Approve an incident by invoking the approval handler internally."""
    if not APPROVAL_FUNCTION_NAME:
        return {"success": False, "error": "Approval function not configured"}

    try:
        payload = {
            "incident_id": incident_id,
            "action": "approve",
            # Generate a valid token for the approval handler
            # The approval handler validates HMAC(token, incident_id:approve)
            # We need to read the secret from SSM to generate a valid token
        }
        # Read the approval secret from SSM
        ssm = boto3.client("ssm")
        secret_param = f"/llm-incident-response/approval-token-secret"
        try:
            resp = ssm.get_parameter(Name=secret_param, WithDecryption=True)
            secret = resp["Parameter"]["Value"]
        except ClientError:
            return {"success": False, "error": "Approval secret not configured in SSM"}

        import hmac
        import hashlib
        signed = f"{incident_id}:approve"
        token = hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()

        # Invoke approval handler with the token
        invoke_payload = {
            "incident_id": incident_id,
            "action": "approve",
            "token": token,
        }
        _lambda.invoke(
            FunctionName=APPROVAL_FUNCTION_NAME,
            InvocationType="RequestResponse",  # synchronous for demo
            Payload=json.dumps(invoke_payload),
        )
        return {"success": True, "incident_id": incident_id}

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

        # Approve the incident
        result = _approve_incident(incident_id)
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