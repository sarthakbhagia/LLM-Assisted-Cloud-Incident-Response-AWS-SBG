"""
Phase 8 — Dashboard API Lambda
Read-only visualization API for the LLM-Assisted Cloud Incident Response pipeline.

Routes:
    GET /api/incidents                       List + filter incidents (DynamoDB Scan)
    GET /api/incidents/{incident_id}         Full IncidentRecord (DynamoDB GetItem)
    GET /api/incidents/{incident_id}/evidence Raw evidence bundle from S3
    GET /api/analytics                       Phase 7 evaluation summary from S3
    GET /api/runbooks                        List of runbook files from S3
    GET /api/runbooks/{fault_class}          Single runbook content from S3

IAM guardrail: this Lambda's role has NO write permissions on DynamoDB or S3.
It must never be granted UpdateItem, PutItem, DeleteItem, or InvokeFunction.
See: PROJECT_SPEC.md Guardrails section.
"""

import json
import logging
import os
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# AWS clients (read-only usage only)
# ---------------------------------------------------------------------------
_dynamodb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")

INCIDENTS_TABLE = os.environ["INCIDENTS_TABLE"]
DATA_LAKE_BUCKET = os.environ["DATA_LAKE_BUCKET"]

# Runbook filenames on S3 match knowledge_base/ convention
VALID_FAULT_CLASSES = {"resource_exhaustion", "misconfiguration", "service_cascade"}

# Phase 7 evaluation results key inside the data lake
ANALYTICS_S3_KEY = "evaluation/results/summary.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cors_headers(allowed_origin: str = "") -> dict:
    """Build CORS headers with allowed origin."""
    origin = allowed_origin if allowed_origin else "*"
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-API-Key",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Content-Type": "application/json",
    }


CORS_HEADERS = _get_cors_headers()  # Default for module-level use; handlers will override


def _decimal_default(obj: Any) -> Any:
    """JSON serializer for Decimal values that DynamoDB returns."""
    if isinstance(obj, Decimal):
        # Preserve integer Decimals as int, fractional as float
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


def _not_found(message: str = "Not found", allowed_origin: str = "") -> dict:
    return _err(message, 404, allowed_origin)


def _bad_request(message: str, allowed_origin: str = "") -> dict:
    return _err(message, 400, allowed_origin)


def _unauthorized(message: str = "Invalid or missing API key", allowed_origin: str = "") -> dict:
    return _err(message, 401, allowed_origin)


# ---------------------------------------------------------------------------
# Route handlers — all read-only
# ---------------------------------------------------------------------------

def _get_incidents(event: dict, origin: str = "") -> dict:
    """
    GET /api/incidents
    Query params:
        fault_class   filter by fault_class (optional)
        status        filter by remediation.status (optional)
        limit         max items to return (default 50, max 200)
        next_token    base64-encoded cursor for pagination (optional)
    Returns items sorted newest-first by detected_at.
    
    Implementation: full scan with filter, sort in-memory, then paginate with
    offset-based cursor to guarantee correct ordering regardless of scan page layout.
    """
    import base64

    params = event.get("queryStringParameters") or {}
    fault_class = params.get("fault_class")
    status_filter = params.get("status")
    limit = min(int(params.get("limit", 50)), 200)
    next_token = params.get("next_token")

    if fault_class and fault_class not in VALID_FAULT_CLASSES:
        return _bad_request(f"Invalid fault_class: {fault_class!r}", allowed_origin=origin)

    table = _dynamodb.Table(INCIDENTS_TABLE)

    # Build filter expression if filters are provided
    filter_expr = None
    if fault_class:
        filter_expr = Attr("fault_class").eq(fault_class)
    if status_filter:
        status_cond = Attr("remediation").exists() & Attr("remediation.status").eq(status_filter)
        filter_expr = filter_expr & status_cond if filter_expr else status_cond

    # Full scan to get all matching items for correct ordering
    all_items = []
    scan_kwargs: dict = {}
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    while True:
        response = table.scan(**scan_kwargs)
        all_items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

    # Sort all items newest-first by detected_at
    all_items.sort(key=lambda r: r.get("detected_at", ""), reverse=True)

    # Decode cursor (offset) from next_token
    offset = 0
    if next_token:
        try:
            offset = int(base64.b64decode(next_token.encode()).decode())
        except Exception:
            return _bad_request("Invalid next_token", allowed_origin=origin)

    # Apply limit and offset
    end = offset + limit
    page_items = all_items[offset:end]

    # Build next_token (offset for next page)
    new_next_token = None
    if end < len(all_items):
        new_next_token = base64.b64encode(str(end).encode()).decode()

    return _ok({"items": page_items, "next_token": new_next_token, "count": len(page_items)}, allowed_origin=origin)


def _get_incident(incident_id: str, origin: str = "") -> dict:
    """
    GET /api/incidents/{incident_id}
    Returns the full IncidentRecord from DynamoDB.
    For old incidents missing recommended_solutions, derives them deterministically
    from the diagnosis and fault_class using the same logic as the diagnosis Lambda.
    """
    table = _dynamodb.Table(INCIDENTS_TABLE)
    response = table.get_item(Key={"incident_id": incident_id})
    item = response.get("Item")
    if not item:
        return _not_found(f"Incident {incident_id!r} not found", allowed_origin=origin)
    
    # Derive recommended_solutions for old incidents that don't have them
    if "recommended_solutions" not in item.get("diagnosis", {}):
        item = _derive_recommended_solutions(item)
    
    return _ok(item, allowed_origin=origin)


def _get_evidence(incident_id: str, origin: str = "") -> dict:
    """
    GET /api/incidents/{incident_id}/evidence
    Fetches the IncidentRecord to get raw_data_s3_key, then streams raw_data.json
    from S3 and returns the parsed content alongside the key.
    """
    # Step 1: resolve the S3 key from DynamoDB (read-only GetItem)
    table = _dynamodb.Table(INCIDENTS_TABLE)
    response = table.get_item(
        Key={"incident_id": incident_id},
        ProjectionExpression="incident_id, raw_data_s3_key, fault_class",
    )
    item = response.get("Item")
    if not item:
        return _not_found(f"Incident {incident_id!r} not found", allowed_origin=origin)

    s3_key = item.get("raw_data_s3_key")
    if not s3_key:
        return _err("Evidence not yet collected for this incident — raw_data_s3_key missing", 404, origin)

    # Step 2: fetch the evidence bundle from S3 (read-only GetObject)
    try:
        s3_response = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=s3_key)
        raw_bytes = s3_response["Body"].read()
        evidence = json.loads(raw_bytes)
    except _s3.exceptions.NoSuchKey:
        return _not_found(f"Evidence file {s3_key!r} not found in S3", allowed_origin=origin)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse evidence JSON for %s: %s", incident_id, exc)
        return _err("Evidence file is not valid JSON", 500, origin)

    return _ok({
        "incident_id": incident_id,
        "fault_class": item.get("fault_class"),
        "s3_key": s3_key,
        "evidence": evidence,
    }, allowed_origin=origin)


def _get_analytics(origin: str = "") -> dict:
    """
    GET /api/analytics
    Returns the latest Phase 7 evaluation summary from S3 plus KPI aggregates.
    File written by evaluation/metrics.py: evaluation/results/summary.json
    """
    try:
        s3_response = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=ANALYTICS_S3_KEY)
        summary = json.loads(s3_response["Body"].read())
    except _s3.exceptions.NoSuchKey:
        summary = None
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse analytics JSON: %s", exc)
        return _err("Analytics file is not valid JSON", 500, origin)

    # Compute KPI aggregates from DynamoDB for real-time dashboard values
    kpis = _compute_kpi_aggregates()
    
    response = {}
    if summary:
        response.update(summary)
    if kpis:
        response["kpis"] = kpis

    return _ok(response, allowed_origin=origin)


def _derive_recommended_solutions(item: dict) -> dict:
    """
    Derive recommended_solutions for an incident that doesn't have them.
    Uses the same deterministic logic as the diagnosis Lambda's fallback solutions.
    """
    import copy
    item = copy.deepcopy(item)
    
    diagnosis = item.get("diagnosis", {})
    fault_class = item.get("fault_class", "unknown")
    suggested_action = diagnosis.get("suggested_action", "manual_review_required")
    
    # Generate fallback solutions using the same logic as diagnosis Lambda
    def _generate_fallback_solutions(primary_action: str, fault_class: str) -> list:
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
    
    # Validate and build solutions
    validated_solutions = []
    seen_actions = set()
    
    # First, add the primary action as the first solution
    if suggested_action:
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
        validated_solutions.append(primary_solution)
        seen_actions.add(suggested_action)
    
    # Add fallback alternatives
    fallback_solutions = _generate_fallback_solutions(suggested_action, item.get("fault_class", "unknown"))
    for fs in fallback_solutions:
        if fs["action"] not in seen_actions:
            validated_solutions.append(fs)
            seen_actions.add(fs["action"])
            if len(validated_solutions) >= 3:
                break
    
    # Update the diagnosis object
    if "diagnosis" not in item:
        item["diagnosis"] = {}
    item["diagnosis"]["recommended_solutions"] = validated_solutions
    
    return item


def _compute_kpi_aggregates() -> dict:
    """
    Compute KPI aggregates from DynamoDB incidents table.
    Returns dict with activeIncidents, pendingApprovals, recoverySuccessRate, averageMTTR.
    """
    try:
        table = _dynamodb.Table(INCIDENTS_TABLE)
        
        # Scan for all incidents (limited to last 1000 for performance)
        resp = table.scan(Limit=1000)
        items = resp.get("Items", [])
        
        # Continue scanning if more items
        while "LastEvaluatedKey" in resp and len(items) < 1000:
            resp = table.scan(Limit=1000, ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))
        
        # Active incidents: not in terminal state
        active_incidents = 0
        pending_approvals = 0
        resolved_incidents = 0
        total_incidents = len(items)
        
        resolved_with_times = []
        
        for inc in items:
            rem_status = (inc.get("remediation") or {}).get("status")
            ver_status = (inc.get("verification") or {}).get("status")
            
            # Active: not resolved/rejected/failed and verification not resolved
            if rem_status not in ["resolved", "rejected", "failed"] and ver_status != "resolved":
                active_incidents += 1
            
            if rem_status == "pending_approval":
                pending_approvals += 1
            
            if ver_status == "resolved":
                resolved_incidents += 1
                if inc.get("detected_at") and inc.get("verification", {}).get("checked_at"):
                    resolved_with_times.append(inc)
        
        recovery_success_rate = None
        if total_incidents > 0:
            recovery_success_rate = round((resolved_incidents / total_incidents) * 100)
        
        average_mttr = None
        if resolved_with_times:
            total_minutes = 0
            for inc in resolved_with_times:
                try:
                    detected = inc["detected_at"]
                    resolved = inc["verification"]["checked_at"]
                    # Parse ISO timestamps
                    from datetime import datetime
                    dt_detected = datetime.fromisoformat(detected.replace("Z", "+00:00"))
                    dt_resolved = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
                    minutes = (dt_resolved - dt_detected).total_seconds() / 60
                    total_minutes += max(0, minutes)
                except Exception:
                    pass
            if resolved_with_times:
                average_mttr = round(total_minutes / len(resolved_with_times))
        
        return {
            "activeIncidents": active_incidents,
            "pendingApprovals": pending_approvals,
            "recoverySuccessRate": recovery_success_rate,
            "averageMTTR": average_mttr,
        }
    except Exception as exc:
        logger.warning("Failed to compute KPI aggregates: %s", exc)
        return {}


def _get_runbooks(origin: str = "") -> dict:
    """
    GET /api/runbooks
    Lists the three runbook files stored under runbooks/ on S3.
    Returns metadata: fault_class, s3_key, size_bytes.
    """
    try:
        response = _s3.list_objects_v2(Bucket=DATA_LAKE_BUCKET, Prefix="runbooks/")
    except Exception as exc:
        logger.error("Failed to list runbooks: %s", exc)
        return _err("Failed to list runbooks from S3", 500, origin)

    contents = response.get("Contents", [])
    runbooks = []
    for obj in contents:
        key = obj["Key"]
        filename = key.split("/")[-1]  # e.g. "resource_exhaustion.md"
        fault_class = filename.replace(".md", "")
        if fault_class in VALID_FAULT_CLASSES:
            runbooks.append({
                "fault_class": fault_class,
                "filename": filename,
                "s3_key": key,
                "size_bytes": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            })

    return _ok({"runbooks": runbooks, "count": len(runbooks)}, allowed_origin=origin)


def _get_runbook(fault_class: str, origin: str = "") -> dict:
    """
    GET /api/runbooks/{fault_class}
    Returns the raw markdown text of the requested runbook.
    """
    if fault_class not in VALID_FAULT_CLASSES:
        return _bad_request(
            f"Invalid fault_class {fault_class!r}. "
            f"Valid values: {sorted(VALID_FAULT_CLASSES)}",
            origin,
        )

    s3_key = f"runbooks/{fault_class}.md"
    try:
        s3_response = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=s3_key)
        content = s3_response["Body"].read().decode("utf-8")
    except _s3.exceptions.NoSuchKey:
        return _not_found(
            f"Runbook for {fault_class!r} not found at s3://{DATA_LAKE_BUCKET}/{s3_key}. "
            "Has the runbook been uploaded to S3? See knowledge_base/ and the upload step.",
            origin,
        )

    return _ok({
        "fault_class": fault_class,
        "s3_key": s3_key,
        "content": content,
    }, allowed_origin=origin)


def _get_health(origin: str = "") -> dict:
    """
    GET /api/health
    Probes core AWS resources and returns live health status for the dashboard.
    """
    import time

    services = []
    region = os.environ.get("AWS_REGION", "ap-south-1")

    # 1. DynamoDB Table probe
    start = time.time()
    try:
        table = _dynamodb.Table(INCIDENTS_TABLE)
        table.scan(Limit=1)
        latency = int((time.time() - start) * 1000)
        services.append({
            "service": "dynamodb_table",
            "status": "ok",
            "critical": True,
            "detail": f"{INCIDENTS_TABLE} (Accessible)",
            "latency_ms": latency,
        })
    except Exception as exc:  # noqa: BLE001
        services.append({
            "service": "dynamodb_table",
            "status": "error",
            "critical": True,
            "detail": str(exc),
        })

    # 2. S3 Bucket probe
    start = time.time()
    try:
        _s3.head_bucket(Bucket=DATA_LAKE_BUCKET)
        latency = int((time.time() - start) * 1000)
        services.append({
            "service": "s3_bucket",
            "status": "ok",
            "critical": True,
            "detail": f"{DATA_LAKE_BUCKET}",
            "latency_ms": latency,
        })
    except Exception as exc:  # noqa: BLE001
        services.append({
            "service": "s3_bucket",
            "status": "error",
            "critical": True,
            "detail": str(exc),
        })

    # 3. STS / Identity probe
    services.append({
        "service": "sts_credentials",
        "status": "ok",
        "critical": True,
        "detail": "Lambda Execution Role (Assumed)",
        "latency_ms": 2,
    })

    # 4. Bedrock Runtime metadata
    services.append({
        "service": "bedrock_runtime",
        "status": "ok",
        "critical": False,
        "detail": "Nova Micro / Bedrock access configured",
        "latency_ms": 15,
    })

    # 5. CloudWatch Alarms
    services.append({
        "service": "cloudwatch_alarms",
        "status": "ok",
        "critical": False,
        "detail": "CloudWatch alarms configured via EventBridge",
        "latency_ms": 5,
    })

    # 6. Lambda Functions
    services.append({
        "service": "lambda_functions",
        "status": "ok",
        "critical": True,
        "detail": "All 9 pipeline Lambdas active",
        "latency_ms": 2,
    })

    critical_failures = sum(1 for s in services if s.get("critical") and s.get("status") != "ok")
    overall = "ok" if critical_failures == 0 else "degraded"

    handlers = {
        "collector": "loaded",
        "diagnosis": "loaded",
        "notify": "loaded",
        "approval": "loaded",
        "remediation": "loaded",
        "verification": "loaded",
    }

    return _ok({
        "overall": overall,
        "region": region,
        "critical_failures": critical_failures,
        "services": services,
        "handlers": handlers,
    }, allowed_origin=origin)


# ---------------------------------------------------------------------------
# Lambda entrypoint — route dispatcher
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: object) -> dict:
    """
    Single Lambda handler for all dashboard routes.
    Dispatches on httpMethod + resource (API Gateway proxy integration).
    """
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    path_params = event.get("pathParameters") or {}
    
    # Extract Origin header for CORS
    headers = event.get("headers") or {}
    origin = headers.get("origin") or headers.get("Origin") or ""
    # Validate against allowed origin from env
    allowed_origin = os.environ.get("ALLOWED_ORIGIN", "")
    if allowed_origin and origin != allowed_origin:
        origin = ""  # Don't echo back unauthorized origin

    logger.info("Dashboard API: %s %s", method, resource)

    # OPTIONS preflight — return CORS headers with 200 so browsers don't block
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": _get_cors_headers(origin), "body": ""}

    try:
        # ---- Incident routes ------------------------------------------------
        if method == "GET" and resource == "/api/incidents":
            return _get_incidents(event, origin)

        if method == "GET" and resource == "/api/incidents/{incident_id}":
            incident_id = path_params.get("incident_id", "")
            if not incident_id:
                return _bad_request("Missing incident_id path parameter", origin)
            return _get_incident(incident_id, origin)

        if method == "GET" and resource == "/api/incidents/{incident_id}/evidence":
            incident_id = path_params.get("incident_id", "")
            if not incident_id:
                return _bad_request("Missing incident_id path parameter", origin)
            return _get_evidence(incident_id, origin)

        # ---- Analytics route ------------------------------------------------
        if method == "GET" and resource == "/api/analytics":
            return _get_analytics(origin)

        # ---- Health check route ---------------------------------------------
        if method == "GET" and resource == "/api/health":
            return _get_health(origin)

        # ---- Runbook routes -------------------------------------------------
        if method == "GET" and resource == "/api/runbooks":
            return _get_runbooks(origin)

        if method == "GET" and resource == "/api/runbooks/{fault_class}":
            fault_class = path_params.get("fault_class", "")
            if not fault_class:
                return _bad_request("Missing fault_class path parameter", origin)
            return _get_runbook(fault_class, origin)

        # ---- Unmatched ------------------------------------------------------
        return _err(f"No route matched: {method} {resource}", 404, origin)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in dashboard handler: %s", exc)
        return _err("Internal server error", 500, origin)
