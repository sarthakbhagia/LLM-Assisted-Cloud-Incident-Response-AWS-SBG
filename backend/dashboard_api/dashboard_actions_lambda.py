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

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Content-Type": "application/json",
}


def _decimal_default(obj: Any) -> Any:
    """JSON serializer for Decimal values that DynamoDB returns."""
    if isinstance(obj, Decimal):
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


def _bad_request(message: str) -> dict:
    return _err(message, 400)


def _not_found(message: str = "Not found") -> dict:
    return _err(message, 404)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _approve_incident(incident_id: str) -> dict:
    """
    POST /api/incidents/{incident_id}/approve
    Dashboard-trust model: no HMAC token required (caller is the authenticated
    frontend user, not an external Slack link).
    Writes remediation.status = 'approved' to DynamoDB, then asynchronously
    invokes the RemediationFunction.
    """
    table = _dynamodb.Table(INCIDENTS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    # Conditional write: only approve if currently pending_approval
    try:
        table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=(
                "SET remediation.#st = :approved, remediation.decided_at = :now"
            ),
            ConditionExpression=(
                "attribute_exists(incident_id) AND remediation.#st = :pending"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":approved": "approved",
                ":pending": "pending_approval",
                ":now": now,
            },
        )
        logger.info("Approved incident %s via dashboard", incident_id)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            resp = table.get_item(Key={"incident_id": incident_id})
            item = resp.get("Item")
            if not item:
                return _not_found(f"Incident {incident_id!r} not found")
            current = item.get("remediation", {}).get("status", "unknown")
            return _err(
                f"Cannot approve: incident is already in status '{current}'", 409
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

    return _ok({"incident_id": incident_id, "status": "approved"})


def _reject_incident(incident_id: str, reason: str = "") -> dict:
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
                return _not_found(f"Incident {incident_id!r} not found")
            current = item.get("remediation", {}).get("status", "unknown")
            return _err(
                f"Cannot reject: incident is already in status '{current}'", 409
            )
        raise

    return _ok({"incident_id": incident_id, "status": "rejected"})


def _trigger_diagnosis(incident_id: str) -> dict:
    """
    POST /api/incidents/{incident_id}/diagnose
    Fetches the incident record, then invokes the DiagnosisFunction asynchronously.
    Returns immediately with a 202 Accepted so the UI can poll for the result.
    """
    if not DIAGNOSIS_FUNCTION_NAME:
        return _err("DIAGNOSIS_FUNCTION_NAME not configured", 503)

    table = _dynamodb.Table(INCIDENTS_TABLE)
    resp = table.get_item(Key={"incident_id": incident_id})
    item = resp.get("Item")
    if not item:
        return _not_found(f"Incident {incident_id!r} not found")

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
        return _err(f"Failed to invoke diagnosis: {exc}", 502)

    return _ok(
        {"incident_id": incident_id, "message": "Diagnosis triggered. Poll incident for result."},
        status=202,
    )


def _get_trace(incident_id: str) -> dict:
    """
    GET /api/incidents/{incident_id}/trace
    Returns the full DynamoDB record, a list of S3 artifacts, and a pipeline
    summary — everything needed to debug a failing incident without the AWS console.
    """
    table = _dynamodb.Table(INCIDENTS_TABLE)
    resp = table.get_item(Key={"incident_id": incident_id})
    item = resp.get("Item")
    if not item:
        return _not_found(f"Incident {incident_id!r} not found")

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
    })


def _get_trace_artifact(incident_id: str, key: str) -> dict:
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


def _get_services() -> dict:
    """
    GET /api/services
    Returns the list of demo microservices with their roles.
    Static metadata — no AWS calls needed.
    """
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
            "role": "Downstream dependency of service-a",
            "fault_classes": ["service_cascade"],
        },
    ]
    return _ok({"services": services})


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

    logger.info("Dashboard Actions: %s %s", method, resource)

    # OPTIONS preflight — return CORS headers with 200
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        incident_id = path_params.get("incident_id", "")

        # ---- Approve --------------------------------------------------------
        if method == "POST" and resource == "/api/incidents/{incident_id}/approve":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter")
            return _approve_incident(incident_id)

        # ---- Reject ---------------------------------------------------------
        if method == "POST" and resource == "/api/incidents/{incident_id}/reject":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter")
            body_raw = event.get("body") or "{}"
            try:
                body = json.loads(body_raw)
            except json.JSONDecodeError:
                body = {}
            reason = body.get("reason", "")
            return _reject_incident(incident_id, reason)

        # ---- Diagnose -------------------------------------------------------
        if method == "POST" and resource == "/api/incidents/{incident_id}/diagnose":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter")
            return _trigger_diagnosis(incident_id)

        # ---- Trace ----------------------------------------------------------
        if method == "GET" and resource == "/api/incidents/{incident_id}/trace":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter")
            return _get_trace(incident_id)

        # ---- Trace artifact -------------------------------------------------
        if method == "GET" and resource == "/api/incidents/{incident_id}/trace/artifact":
            if not incident_id:
                return _bad_request("Missing incident_id path parameter")
            key = qs_params.get("key", "")
            return _get_trace_artifact(incident_id, key)

        # ---- Services -------------------------------------------------------
        if method == "GET" and resource == "/api/services":
            return _get_services()

        # ---- Unmatched ------------------------------------------------------
        return _err(f"No route matched: {method} {resource}", 404)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in dashboard actions handler: %s", exc)
        return _err("Internal server error", 500)
