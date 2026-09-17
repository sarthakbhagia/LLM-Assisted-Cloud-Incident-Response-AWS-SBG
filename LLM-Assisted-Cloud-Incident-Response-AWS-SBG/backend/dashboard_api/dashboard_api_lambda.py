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

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Content-Type": "application/json",
}


def _decimal_default(obj: Any) -> Any:
    """JSON serializer for Decimal values that DynamoDB returns."""
    if isinstance(obj, Decimal):
        # Preserve integer Decimals as int, fractional as float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def _ok(data: Any, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps({"data": data, "error": None}, default=_decimal_default),
    }


def _err(message: str, status: int = 500) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps({"data": None, "error": message}),
    }


def _not_found(message: str = "Not found") -> dict:
    return _err(message, 404)


def _bad_request(message: str) -> dict:
    return _err(message, 400)


# ---------------------------------------------------------------------------
# Route handlers — all read-only
# ---------------------------------------------------------------------------

def _get_incidents(event: dict) -> dict:
    """
    GET /api/incidents
    Query params:
        fault_class   filter by fault_class (optional)
        status        filter by remediation.status (optional)
        limit         max items to return (default 50, max 200)
        next_token    base64-encoded ExclusiveStartKey for pagination (optional)
    Returns items sorted newest-first by detected_at.
    """
    import base64

    params = event.get("queryStringParameters") or {}
    fault_class = params.get("fault_class")
    status_filter = params.get("status")
    limit = min(int(params.get("limit", 50)), 200)
    next_token = params.get("next_token")

    if fault_class and fault_class not in VALID_FAULT_CLASSES:
        return _bad_request(f"Invalid fault_class: {fault_class!r}")

    table = _dynamodb.Table(INCIDENTS_TABLE)

    scan_kwargs: dict = {"Limit": limit}

    # Build filter expression if filters are provided
    filter_expr = None
    if fault_class:
        filter_expr = Attr("fault_class").eq(fault_class)
    if status_filter:
        status_cond = Attr("remediation").exists() & Attr("remediation.status").eq(status_filter)
        filter_expr = filter_expr & status_cond if filter_expr else status_cond
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    # Pagination: decode the continuation token
    if next_token:
        try:
            lek_bytes = base64.b64decode(next_token.encode())
            scan_kwargs["ExclusiveStartKey"] = json.loads(lek_bytes)
        except Exception:
            return _bad_request("Invalid next_token")

    response = table.scan(**scan_kwargs)
    items = response.get("Items", [])

    # Sort newest-first in-Lambda (DynamoDB Scan has no ORDER BY)
    items.sort(key=lambda r: r.get("detected_at", ""), reverse=True)

    # Build next_token for the caller
    new_next_token = None
    last_evaluated_key = response.get("LastEvaluatedKey")
    if last_evaluated_key:
        new_next_token = base64.b64encode(
            json.dumps(last_evaluated_key, default=_decimal_default).encode()
        ).decode()

    return _ok({"items": items, "next_token": new_next_token, "count": len(items)})


def _get_incident(incident_id: str) -> dict:
    """
    GET /api/incidents/{incident_id}
    Returns the full IncidentRecord from DynamoDB.
    """
    table = _dynamodb.Table(INCIDENTS_TABLE)
    response = table.get_item(Key={"incident_id": incident_id})
    item = response.get("Item")
    if not item:
        return _not_found(f"Incident {incident_id!r} not found")
    return _ok(item)


def _get_evidence(incident_id: str) -> dict:
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
        return _not_found(f"Incident {incident_id!r} not found")

    s3_key = item.get("raw_data_s3_key")
    if not s3_key:
        return _err("Evidence not yet collected for this incident — raw_data_s3_key missing", 404)

    # Step 2: fetch the evidence bundle from S3 (read-only GetObject)
    try:
        s3_response = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=s3_key)
        raw_bytes = s3_response["Body"].read()
        evidence = json.loads(raw_bytes)
    except _s3.exceptions.NoSuchKey:
        return _not_found(f"Evidence file {s3_key!r} not found in S3")
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse evidence JSON for %s: %s", incident_id, exc)
        return _err("Evidence file is not valid JSON", 500)

    return _ok({
        "incident_id": incident_id,
        "fault_class": item.get("fault_class"),
        "s3_key": s3_key,
        "evidence": evidence,
    })


def _get_analytics() -> dict:
    """
    GET /api/analytics
    Returns the latest Phase 7 evaluation summary from S3.
    File written by evaluation/metrics.py: evaluation/results/summary.json
    """
    try:
        s3_response = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=ANALYTICS_S3_KEY)
        summary = json.loads(s3_response["Body"].read())
    except _s3.exceptions.NoSuchKey:
        return _ok(None, 200)  # Phase 7 has not run yet — return empty, not an error
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse analytics JSON: %s", exc)
        return _err("Analytics file is not valid JSON", 500)

    return _ok(summary)


def _get_runbooks() -> dict:
    """
    GET /api/runbooks
    Lists the three runbook files stored under runbooks/ on S3.
    Returns metadata: fault_class, s3_key, size_bytes.
    """
    try:
        response = _s3.list_objects_v2(Bucket=DATA_LAKE_BUCKET, Prefix="runbooks/")
    except Exception as exc:
        logger.error("Failed to list runbooks: %s", exc)
        return _err("Failed to list runbooks from S3", 500)

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

    return _ok({"runbooks": runbooks, "count": len(runbooks)})


def _get_runbook(fault_class: str) -> dict:
    """
    GET /api/runbooks/{fault_class}
    Returns the raw markdown text of the requested runbook.
    """
    if fault_class not in VALID_FAULT_CLASSES:
        return _bad_request(
            f"Invalid fault_class {fault_class!r}. "
            f"Valid values: {sorted(VALID_FAULT_CLASSES)}"
        )

    s3_key = f"runbooks/{fault_class}.md"
    try:
        s3_response = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=s3_key)
        content = s3_response["Body"].read().decode("utf-8")
    except _s3.exceptions.NoSuchKey:
        return _not_found(
            f"Runbook for {fault_class!r} not found at s3://{DATA_LAKE_BUCKET}/{s3_key}. "
            "Has the runbook been uploaded to S3? See knowledge_base/ and the upload step."
        )

    return _ok({
        "fault_class": fault_class,
        "s3_key": s3_key,
        "content": content,
    })


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

    logger.info("Dashboard API: %s %s", method, resource)

    # OPTIONS preflight — return CORS headers with 200 so browsers don't block
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        # ---- Incident routes ------------------------------------------------
        if method == "GET" and resource == "/api/incidents":
            return _get_incidents(event)

        if method == "GET" and resource == "/api/incidents/{incident_id}":
            incident_id = path_params.get("incident_id", "")
            if not incident_id:
                return _bad_request("Missing incident_id path parameter")
            return _get_incident(incident_id)

        if method == "GET" and resource == "/api/incidents/{incident_id}/evidence":
            incident_id = path_params.get("incident_id", "")
            if not incident_id:
                return _bad_request("Missing incident_id path parameter")
            return _get_evidence(incident_id)

        # ---- Analytics route ------------------------------------------------
        if method == "GET" and resource == "/api/analytics":
            return _get_analytics()

        # ---- Runbook routes -------------------------------------------------
        if method == "GET" and resource == "/api/runbooks":
            return _get_runbooks()

        if method == "GET" and resource == "/api/runbooks/{fault_class}":
            fault_class = path_params.get("fault_class", "")
            if not fault_class:
                return _bad_request("Missing fault_class path parameter")
            return _get_runbook(fault_class)

        # ---- Unmatched ------------------------------------------------------
        return _err(f"No route matched: {method} {resource}", 404)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in dashboard handler: %s", exc)
        return _err("Internal server error", 500)
