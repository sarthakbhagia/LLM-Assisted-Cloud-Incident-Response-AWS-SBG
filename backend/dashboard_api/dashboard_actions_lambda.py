"""
Dashboard Actions Lambda
Write-path and action routes for the LLM-Assisted Cloud Incident Response dashboard.

This Lambda handles the routes that cannot live in the strictly read-only
DashboardApiFunction. It has narrowly-scoped write permissions on DynamoDB
(UpdateItem on the incidents table only) and invoke permission on
DiagnosisFunction.

Routes:
    POST /api/incidents/{incident_id}/approve     Approve a pending incident
    POST /api/incidents/{incident_id}/reject      Reject a pending incident
    POST /api/incidents/{incident_id}/diagnose    Re-trigger diagnosis
    GET  /api/incidents/{incident_id}/trace       Full pipeline trace (debug)
    GET  /api/incidents/{incident_id}/trace/artifact  Fetch a specific S3 artifact
    GET  /api/services                            List demo services + status

Design note: approve/reject here use the dashboard-trust model (no HMAC token).
Production Slack-link approvals still use the HMAC-protected ApprovalFunction
at GET/POST /approval. Both paths converge on the same DynamoDB status update.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

try:
    from prompts import VALID_SUGGESTED_ACTIONS
except ImportError:
    from diagnosis.prompts import VALID_SUGGESTED_ACTIONS

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# AWS clients
# ---------------------------------------------------------------------------
_dynamodb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")
_lambda_client = boto3.client("lambda")

INCIDENTS_TABLE = os.environ["INCIDENTS_TABLE"]
DATA_LAKE_BUCKET = os.environ["DATA_LAKE_BUCKET"]
DIAGNOSIS_FUNCTION_NAME = os.environ.get("DIAGNOSIS_FUNCTION_NAME", "")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cors_headers(allowed_origin: str = "") -> dict:
    """Build CORS headers with allowed origin."""
    origin = allowed_origin if allowed_origin else "*"
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-API-Key",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Content-Type": "application/json",
    }


CORS_HEADERS = _get_cors_headers()  # Default for module-level use; handlers will override


def _decimal_default(obj: Any) -> Any:
    """JSON serializer for Decimal values that DynamoDB returns."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def _ok(data: Any, status: int = 200, allowed_origin: str = "") -> dict:
    return {
        "statusCode": status,
        "headers": _get_cors_headers(allowed_origin),
        "body": json.dumps({"data": data, "error": None}, default=_decimal_default),
    }


def _err(message: str, status: int = 500, allowed_origin: str = "") -> dict:
    return {
        "statusCode": status,
        "headers": _get_cors_headers(allowed_origin),
        "body": json.dumps({"data": None, "error": message}),
    }


def _bad_request(message: str, allowed_origin: str = "") -> dict:
    return _err(message, 400, allowed_origin)


def _not_found(message: str = "Not found", allowed_origin: str = "") -> dict:
    return _err(message, 404, allowed_origin)


def _unauthorized(message: str = "Invalid or missing API key", allowed_origin: str = "") -> dict:
    return _err(message, 401, allowed_origin)


def _check_api_key(event: dict, origin: str) -> tuple[bool, str]:
    """Check if the request has a valid API key.
    Returns (is_valid, origin) - if not valid, returns (False, origin) and caller should return 401.
    """
    # Get API key from environment
    expected_key = os.environ.get("DASHBOARD_API_KEY", "")
    if not expected_key:
        # No API key configured - allow request (development mode)
        return True, origin
    
    # Get API key from request headers
    headers = event.get("headers") or {}
    provided_key = headers.get("x-api-key") or headers.get("X-API-Key") or ""
    
    if provided_key != expected_key:
        return False, origin
    
    return True, origin


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _approve_incident(incident_id: str, body: dict | None = None, origin: str = "") -> dict:
    """
    POST /api/incidents/{incident_id}/approve
    Dashboard-trust model: no HMAC token required (caller is the authenticated
    frontend user, not an external Slack link).
    Writes remediation.status = 'approved' to DynamoDB, then asynchronously
    invokes the RemediationFunction.

    Optional body: { "solution_id": "...", "selected_action": "..." }
    - Validates against the incident's recommended_solutions (derives if missing)
    - If no body, defaults to the top-ranked solution
    - Persists remediation.selected_action, remediation.selected_solution_id,
      remediation.decided_at, remediation.approved_via
    """
    table = _dynamodb.Table(INCIDENTS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    # First, fetch the incident to get recommended_solutions for validation
    resp = table.get_item(Key={"incident_id": incident_id})
    item = resp.get("Item")
    if not item:
        return _not_found(f"Incident {incident_id!r} not found", origin)

    # Get recommended_solutions (derive if missing, same logic as dashboard_api_lambda)
    diagnosis = item.get("diagnosis", {})
    recommended_solutions = diagnosis.get("recommended_solutions")
    fault_class = item.get("fault_class", "unknown")
    suggested_action = diagnosis.get("suggested_action", "manual_review_required")

    if not recommended_solutions:
        # Derive using same logic as dashboard_api_lambda._derive_recommended_solutions
        recommended_solutions = _derive_approve_solutions(suggested_action, fault_class)

    # Determine which solution to use
    selected_solution = None
    selected_action = None

    if body:
        solution_id = body.get("solution_id")
        selected_action = body.get("selected_action")

        if solution_id:
            # Find solution by ID
            for sol in recommended_solutions:
                if sol.get("id") == solution_id:
                    selected_solution = sol
                    break
            if not selected_solution:
                return _err(f"Invalid solution_id: {solution_id!r}. Not found in recommended_solutions.", 400, origin)

        if selected_action:
            # Validate action matches a solution
            action_found = False
            for sol in recommended_solutions:
                if sol.get("action") == selected_action:
                    action_found = True
                    if not selected_solution:
                        selected_solution = sol
                    break
            if not action_found:
                return _err(f"Invalid selected_action: {selected_action!r}. Not a valid action in recommended_solutions.", 400, origin)

        # If only one of solution_id or selected_action provided, validate they match
        if selected_solution and solution_id and selected_action:
            if selected_solution.get("action") != selected_action:
                return _err(f"Mismatch: solution_id {solution_id!r} has action {selected_solution.get('action')!r}, but selected_action is {selected_action!r}.", 400, origin)

    # Default to top-ranked solution if none selected
    if not selected_solution:
        selected_solution = recommended_solutions[0]
    if not selected_action:
        selected_action = selected_solution.get("action", suggested_action)

    # Final validation: selected_action must be in VALID_SUGGESTED_ACTIONS
    if selected_action not in VALID_SUGGESTED_ACTIONS:
        return _err(f"Invalid action: {selected_action!r}. Must be one of {VALID_SUGGESTED_ACTIONS}.", 400, origin)

    solution_id = selected_solution.get("id", "sol-1")

    # Conditional write: only approve if currently pending_approval
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
                ":via": "dashboard",
            },
        )
        logger.info("Approved incident %s via dashboard (solution_id=%s, action=%s)", incident_id, solution_id, selected_action)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            resp = table.get_item(Key={"incident_id": incident_id})
            item = resp.get("Item")
            if not item:
                return _not_found(f"Incident {incident_id!r} not found", origin)
            current = item.get("remediation", {}).get("status", "unknown")
            return _err(
                f"Cannot approve: incident is already in status '{current}'", 409, origin
            )
        raise

    # Fire remediation asynchronously (Event invocation — does not block response)
    remediation_fn = os.environ.get("REMEDIATION_FUNCTION_NAME", "")
    if remediation_fn:
        try:
            _lambda_client.invoke(
                FunctionName=remediation_fn,
                InvocationType="Event",  # async
                Payload=json.dumps({"incident_id": incident_id}),
            )
            logger.info("Remediation invoked async for incident %s", incident_id)
        except Exception as exc:  # noqa: BLE001
            # Non-fatal: the DynamoDB status is already set to approved
            logger.warning("Failed to invoke remediation for %s: %s", incident_id, exc)

    return _ok({"incident_id": incident_id, "status": "approved", "selected_action": selected_action, "selected_solution_id": solution_id}, allowed_origin=origin)


def _derive_approve_solutions(suggested_action: str, fault_class: str) -> list:
    """
    Derive recommended_solutions for approval validation.
    Uses the same deterministic logic as the diagnosis Lambda's fallback solutions.
    """
    # Define alternative actions per fault class from runbooks
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

    # First, add the primary action as the first solution
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

    # Add fallback alternatives
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

    return solutions


def _reject_incident(incident_id: str, reason: str = "", origin: str = "") -> dict:
    """
    POST /api/incidents/{incident_id}/reject
    Dashboard-trust model. Writes remediation.status = 'rejected' to DynamoDB.
    """
    table = _dynamodb.Table(INCIDENTS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    update_expr = "SET remediation.#st = :rejected, remediation.decided_at = :now"
    expr_vals: dict = {
        ":rejected": "rejected",
        ":pending": "pending_approval",
        ":now": now,
    }
    if reason:
        update_expr += ", remediation.reject_reason = :reason"
        expr_vals[":reason"] = reason

    try:
        table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=update_expr,
            ConditionExpression=(
                "attribute_exists(incident_id) AND remediation.#st = :pending"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues=expr_vals,
        )
        logger.info("Rejected incident %s via dashboard (reason=%r)", incident_id, reason)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            resp = _dynamodb.Table(INCIDENTS_TABLE).get_item(
                Key={"incident_id": incident_id}
            )
            item = resp.get("Item")
            if not item:
                return _not_found(f"Incident {incident_id!r} not found", origin)
            current = item.get("remediation", {}).get("status", "unknown")
            return _err(
                f"Cannot reject: incident is already in status '{current}'", 409, origin
            )
        raise

    return _ok({"incident_id": incident_id, "status": "rejected"}, allowed_origin=origin)


def _trigger_diagnosis(incident_id: str, origin: str = "") -> dict:
    """
    POST /api/incidents/{incident_id}/diagnose
    Fetches the incident record, then invokes the DiagnosisFunction asynchronously.
    Returns immediately with a 202 Accepted so the UI can poll for the result.
    """
    if not DIAGNOSIS_FUNCTION_NAME:
        return _err("DIAGNOSIS_FUNCTION_NAME not configured", 503, origin)

    table = _dynamodb.Table(INCIDENTS_TABLE)
    resp = table.get_item(Key={"incident_id": incident_id})
    item = resp.get("Item")
    if not item:
        return _not_found(f"Incident {incident_id!r} not found", origin)

    payload = {
        "incident_id": incident_id,
        "fault_class": item.get("fault_class", "unknown"),
        "raw_data_s3_key": item.get("raw_data_s3_key", ""),
    }

    try:
        _lambda_client.invoke(
            FunctionName=DIAGNOSIS_FUNCTION_NAME,
            InvocationType="Event",  # async — caller polls for result
            Payload=json.dumps(payload),
        )
        logger.info("Diagnosis invoked async for incident %s", incident_id)
    except Exception as exc:  # noqa: BLE001
        return _err(f"Failed to invoke diagnosis: {exc}", 502, origin)

    return _ok(
        {"incident_id": incident_id, "message": "Diagnosis triggered. Poll incident for result."},
        status=202,
        allowed_origin=origin,
    )


def _get_trace(incident_id: str, origin: str = "") -> dict:
    """
    GET /api/incidents/{incident_id}/trace
    Returns the full DynamoDB record, a list of S3 artifacts, and a pipeline
    summary — everything needed to debug a failing incident without the AWS console.
    """
    table = _dynamodb.Table(INCIDENTS_TABLE)
    resp = table.get_item(Key={"incident_id": incident_id})
    item = resp.get("Item")
    if not item:
        return _not_found(f"Incident {incident_id!r} not found", origin)

    # Serialize Decimal values
    record = json.loads(json.dumps(item, default=_decimal_default))

    # List all S3 objects under incidents/{incident_id}/
    prefix = f"incidents/{incident_id}/"
    s3_artifacts: list[dict] = []
    try:
        paginator = _s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=DATA_LAKE_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                s3_artifacts.append({
                    "key": obj["Key"],
                    "size_bytes": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "fetch_url": (
                        f"/api/incidents/{incident_id}/trace/artifact"
                        f"?key={obj['Key']}"
                    ),
                })
    except Exception as exc:  # noqa: BLE001
        s3_artifacts = [{"error": str(exc)}]

    diagnosis = record.get("diagnosis") or {}
    remediation = record.get("remediation") or {}
    verification = record.get("verification") or {}

    pipeline_summary = {
        "evidence_collected": bool(record.get("raw_data_s3_key")),
        "diagnosis_status": diagnosis.get("diagnosis_status", "unknown"),
        "failure_mode_full": diagnosis.get("failure_mode"),
        "is_heuristic": diagnosis.get("is_heuristic", False),
        "model_used": diagnosis.get("model_used", "unknown"),
        "confidence": diagnosis.get("confidence"),
        "suggested_action": diagnosis.get("suggested_action"),
        "notify_failed": diagnosis.get("notify_failed", False),
        "remediation_status": remediation.get("status"),
        "action_taken": remediation.get("action_taken"),
        "verification_status": verification.get("status"),
        "verification_notes": verification.get("notes"),
        "llm_artifacts": [
            a for a in s3_artifacts
            if "llm_raw_response" in a.get("key", "")
        ],
    }

    return _ok({
        "incident_id": incident_id,
        "dynamodb_record": record,
        "s3_artifacts": s3_artifacts,
        "pipeline_summary": pipeline_summary,
    }, allowed_origin=origin)


def _get_trace_artifact(incident_id: str, key: str, origin: str = "") -> dict:
    """
    GET /api/incidents/{incident_id}/trace/artifact?key=...
    Fetch the content of a specific S3 artifact. The key must belong to the
    incident's prefix (security guard).
    """
    if not key:
        return _bad_request("Missing required query parameter: key", origin)
    if not key.startswith(f"incidents/{incident_id}/"):
        return _err("Key does not belong to this incident", 403, origin)

    try:
        obj = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=key)
        content_str = obj["Body"].read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(content_str)
            return _ok({"key": key, "content": parsed, "content_type": "json"}, origin=origin)
        except json.JSONDecodeError:
            return _ok({"key": key, "content": content_str, "content_type": "text"}, origin=origin)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return _not_found(f"Artifact not found: {key}", origin)
        raise

    return _ok({
        "incident_id": incident_id,
        "dynamodb_record": record,
        "s3_artifacts": s3_artifacts,
        "pipeline_summary": pipeline_summary,
    })


def _get_trace_artifact(incident_id: str, key: str, origin: str = "") -> dict:
    """
    GET /api/incidents/{incident_id}/trace/artifact?key=...
    Fetch the content of a specific S3 artifact. The key must belong to the
    incident's prefix (security guard).
    """
    if not key:
        return _bad_request("Missing required query parameter: key")
    if not key.startswith(f"incidents/{incident_id}/"):
        return _err("Key does not belong to this incident", 403)

    try:
        obj = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=key)
        content_str = obj["Body"].read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(content_str)
            return _ok({"key": key, "content": parsed, "content_type": "json"})
        except json.JSONDecodeError:
            return _ok({"key": key, "content": content_str, "content_type": "text"})
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return _not_found(f"Artifact not found: {key}")
        raise


def _get_services(origin: str = "") -> dict:
    """
    GET /api/services
    Returns the list of demo microservices with their roles and live health status.
    Queries CloudWatch for metrics and DynamoDB for active incidents.
    """
    import time
    import os
    from boto3.dynamodb.conditions import Attr
    
    region = os.environ.get("AWS_REGION", "ap-south-1")
    environment = os.environ.get("ENVIRONMENT", "dev")
    
    # Static service definitions
    services = [
        {
            "name": "service-a",
            "role": "Entry point — receives traffic, triggers collector on fault",
            "fault_classes": ["resource_exhaustion", "service_cascade"],
        },
        {
            "name": "service-b",
            "role": "Downstream dependency of service-a",
            "fault_classes": ["service_cascade"],
        },
        {
            "name": "service-c",
            "role": "Downstream dependency of service-b",
            "fault_classes": ["service_cascade"],
        },
    ]
    
    # Get live health for each service
    cw = boto3.client("cloudwatch", region_name=region)
    
    for svc in services:
        function_name = _find_lambda_function_name(svc["name"], origin)
        health = {"status": "unknown", "latency_ms": None}
        
        if function_name:
            try:
                # Get last 5 minutes of Duration and Errors metrics
                from datetime import datetime, timezone
                end = time.time()
                start = end - 300  # 5 minutes
                start_dt = datetime.fromtimestamp(start, tz=timezone.utc)
                end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
                
                # Duration metric
                duration_resp = cw.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Duration",
                    Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                    StartTime=start_dt,
                    EndTime=end_dt,
                    Period=60,
                    Statistics=["Average", "Maximum"],
                )
                
                # Errors metric
                errors_resp = cw.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Errors",
                    Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                    StartTime=start_dt,
                    EndTime=end_dt,
                    Period=60,
                    Statistics=["Sum"],
                )
                
                avg_duration = 0
                max_duration = 0
                if duration_resp.get("Datapoints"):
                    avg_duration = sum(d["Average"] for d in duration_resp["Datapoints"]) / len(duration_resp["Datapoints"])
                    max_duration = max(d["Maximum"] for d in duration_resp["Datapoints"])
                
                total_errors = 0
                if errors_resp.get("Datapoints"):
                    total_errors = sum(d["Sum"] for d in errors_resp["Datapoints"])
                
                # Determine health status
                if total_errors > 0:
                    health = {"status": "error", "latency_ms": int(avg_duration), "errors": int(total_errors), "max_duration_ms": int(max_duration)}
                elif avg_duration > 10000:  # 10 second threshold for warning
                    health = {"status": "warning", "latency_ms": int(avg_duration), "max_duration_ms": int(max_duration)}
                else:
                    health = {"status": "ok", "latency_ms": int(avg_duration), "max_duration_ms": int(max_duration)}
                    
            except Exception as exc:
                logger.warning(f"Failed to get CloudWatch metrics for {function_name}: {exc}")
                health = {"status": "unknown", "latency_ms": None}
        
        svc["health"] = health
    
    # Check for active incidents per service from DynamoDB
    try:
        table = _dynamodb.Table(INCIDENTS_TABLE)
        # Scan for non-terminal incidents
        resp = table.scan(
            FilterExpression=(
                Attr("remediation").exists() & 
                Attr("remediation.status").ne("resolved") & 
                Attr("remediation.status").ne("rejected") & 
                Attr("remediation.status").ne("failed")
            ) | (
                Attr("verification").exists() & 
                Attr("verification.status").ne("resolved")
            ),
            ProjectionExpression="incident_id, fault_class, resource_id, remediation, verification"
        )
        
        active_incidents = resp.get("Items", [])
        
        # Map active incidents to services
        for svc in services:
            svc["active_incidents"] = []
            for inc in active_incidents:
                resource_id = (inc.get("resource_id") or "").lower()
                fault_class = inc.get("fault_class", "")
                
                # Check if this incident affects this service
                affects_service = False
                if svc["name"] in resource_id:
                    affects_service = True
                elif svc["name"] == "service-a" and fault_class in ["resource_exhaustion", "service_cascade"]:
                    affects_service = True
                elif svc["name"] in ["service-b", "service-c"] and fault_class == "service_cascade":
                    affects_service = True
                
                if affects_service:
                    svc["active_incidents"].append({
                        "incident_id": inc.get("incident_id"),
                        "fault_class": fault_class,
                        "status": inc.get("remediation", {}).get("status") or inc.get("verification", {}).get("status")
                    })
                    
    except Exception as exc:
        logger.warning(f"Failed to get active incidents from DynamoDB: {exc}")
    
    return _ok({"services": services}, allowed_origin=origin)


def _find_lambda_function_name(service_name: str, origin: str = "") -> str | None:
    """Find the deployed Lambda function name for a service."""
    try:
        prefix_map = {
            "service-a": "ServiceAFunction",
            "service-b": "ServiceBFunction",
            "service-c": "ServiceCFunction",
        }
        prefix = prefix_map.get(service_name, service_name)
        
        paginator = _lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page["Functions"]:
                if prefix.lower() in fn["FunctionName"].lower():
                    return fn["FunctionName"]
    except Exception as exc:
        logger.warning(f"Failed to find Lambda for {service_name}: {exc}")
    return None


# ---------------------------------------------------------------------------
# Lambda entrypoint — route dispatcher
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: object) -> dict:
    """
    Dashboard Actions Lambda handler.
    Dispatches on httpMethod + resource (API Gateway proxy integration).
    Handles write-path and trace routes that cannot live in the read-only
    DashboardApiFunction.
    """
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    path_params = event.get("pathParameters") or {}
    qs_params = event.get("queryStringParameters") or {}
    
    # Extract Origin header for CORS
    headers = event.get("headers") or {}
    origin = headers.get("origin") or headers.get("Origin") or ""
    # Validate against allowed origin from env
    allowed_origin = os.environ.get("ALLOWED_ORIGIN", "")
    if allowed_origin and origin != allowed_origin:
        origin = ""  # Don't echo back unauthorized origin

    logger.info("Dashboard Actions: %s %s", method, resource)

    # OPTIONS preflight — return CORS headers with 200
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": _get_cors_headers(origin), "body": ""}

    # Check API key for write operations (POST)
    if method == "POST":
        valid, origin = _check_api_key(event, origin)
        if not valid:
            return _unauthorized("Invalid or missing API key", origin)

    try:
        incident_id = path_params.get("incident_id", "")

        # ---- Approve --------------------------------------------------------
        if method == "POST" and resource == "/api/incidents/{incident_id}/approve":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter", origin)
            body_raw = event.get("body") or "{}"
            try:
                body = json.loads(body_raw)
            except json.JSONDecodeError:
                body = {}
            return _approve_incident(incident_id, body, origin)

        # ---- Reject ---------------------------------------------------------
        if method == "POST" and resource == "/api/incidents/{incident_id}/reject":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter", origin)
            body_raw = event.get("body") or "{}"
            try:
                body = json.loads(body_raw)
            except json.JSONDecodeError:
                body = {}
            reason = body.get("reason", "")
            return _reject_incident(incident_id, reason, origin)

        # ---- Diagnose -------------------------------------------------------
        if method == "POST" and resource == "/api/incidents/{incident_id}/diagnose":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter", origin)
            return _trigger_diagnosis(incident_id, origin)

        # ---- Trace ----------------------------------------------------------
        if method == "GET" and resource == "/api/incidents/{incident_id}/trace":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter", origin)
            return _get_trace(incident_id, origin)

        # ---- Trace artifact -------------------------------------------------
        if method == "GET" and resource == "/api/incidents/{incident_id}/trace/artifact":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter", origin)
            key = qs_params.get("key", "")
            return _get_trace_artifact(incident_id, key, origin)

        # ---- Services -------------------------------------------------------
        if method == "GET" and resource == "/api/services":
            return _get_services(origin)

        # ---- Unmatched ------------------------------------------------------
        return _err(f"No route matched: {method} {resource}", 404, origin)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in dashboard actions handler: %s", exc)
        return _err("Internal server error", 500, origin)
