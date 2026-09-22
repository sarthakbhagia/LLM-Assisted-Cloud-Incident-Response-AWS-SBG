"""
app.py — Phase 5: Approval Lambda Handler

API Gateway + Lambda endpoint (spec step 18): receives an approve/reject call
from the links embedded in the Slack message, updates the incident's
remediation status in DynamoDB, and if approved invokes the remediation
Lambda (Phase 6 — gracefully skipped until it exists).

Design notes:
- Route: GET /approval (link-style, spec's "button-style link" path) and
  POST /approval (JSON body — works for future Slack slash commands/buttons).
- Auth: HMAC-SHA256 token over `incident_id:action`, keyed by an SSM SecureString
  secret. The token is embedded in the Slack links by the notify Lambda, so
  the URL is unguessable and action-bound: an approve link cannot be reused
  as a reject link (and vice-versa). Not a replacement for full Slack
  signature verification — documented trade-off in the spec's "simplest path"
  spirit.
- Idempotency / race safety: the status flip is a conditional DynamoDB update
  (ConditionExpression on remediation.status = pending_approval), so a double
  click or concurrent approve/reject cannot double-apply. This conditional
  `approved` write is also the guardrail gate required before any remediation
  executes (spec Guardrails: "No remediation executes without a status change
  to `approved` in DynamoDB first").
- Response bodies:
  - GET (link flow from Slack): human-readable HTML so a browser user sees a clear
    approve/reject confirmation page.
  - POST / JSON: JSON response shape (machine-friendly) for future Slack slash
    commands, interactive payloads, and any Phase 7/8 consumer that hits the
    endpoint programmatically.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients — initialised once at cold start
_ssm = boto3.client("ssm")
_dynamodb = boto3.resource("dynamodb")
_lambda = boto3.client("lambda")

# Config from environment
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "")
APPROVAL_TOKEN_SECRET_SSM = os.environ.get("APPROVAL_TOKEN_SECRET_SSM", "")
REMEDIATION_FUNCTION_NAME = os.environ.get("REMEDIATION_FUNCTION_NAME", "")

VALID_ACTIONS = ("approve", "reject")
VALID_OUTCOMES = ("approved", "rejected")

_cache: dict = {}


# ===========================================================================
# Entry point
# ===========================================================================

def lambda_handler(event, context):
    logger.info(json.dumps({"event": "approval_triggered", "payload_event": event}, default=str))

    params, error_response = _parse_request(event)
    if error_response:
        return error_response

    incident_id = params["incident_id"]
    action = params["action"]

    if not INCIDENTS_TABLE:
        logger.error("INCIDENTS_TABLE not configured")
        return _response(500, {"error": "Server configuration error: incidents table not set."})

    # 1. Verify the HMAC token (when the secret is configured)
    if not _token_valid(incident_id, action, params.get("token")):
        logger.warning(json.dumps({"event": "approval_rejected_bad_token", "incident_id": incident_id, "action": action}))
        return _response(403, {"error": "Invalid or missing approval token. Use the link from the Slack incident message."})

    # 2. Flip remediation.status — conditionally, so only the first caller wins
    new_status = "approved" if action == "approve" else "rejected"
    updated = _update_remediation_status(
        incident_id,
        new_status,
        approved_by=params.get("approved_by") or None,
        rejected_reason=params.get("reason") or None,
    )

    if updated == "conditional_failed":
        current = _get_current_status(incident_id)
        return _response(
            409,
            {"error": f"Incident {incident_id} was already processed (current status: {current}). No change made."},
        )
    if updated is None:
        return _response(500, {"error": f"Failed to update incident {incident_id} — check Lambda logs."})

    # 3. If approved, kick off remediation (Phase 6; no-op until it exists)
    remediation_invoked = False
    if new_status == "approved":
        remediation_invoked = _invoke_remediation(incident_id)

    logger.info(json.dumps({
        "event": "approval_complete",
        "incident_id": incident_id,
        "action": action,
        "new_status": new_status,
        "remediation_invoked": remediation_invoked,
    }))

    if new_status == "approved":
        detail = "Remediation has been triggered." if remediation_invoked else (
            "Remediation Lambda is not wired up yet (Phase 6) — incident is marked approved."
        )
        return _response(200, {
            "status": "approved",
            "incident_id": incident_id,
            "remediation_invoked": remediation_invoked,
            "detail": detail,
        })
    return _response(200, {
        "status": "rejected",
        "incident_id": incident_id,
        "detail": "The incident record has been updated.",
    })


# ===========================================================================
# Request parsing (GET query string and POST JSON body)
# ===========================================================================

def _parse_request(event: dict) -> tuple[dict | None, dict | None]:
    """Normalise API Gateway REST (v1) and HTTP API (v2) events into params."""
    method = (event.get("httpMethod")
              or (event.get("requestContext", {}).get("http", {}) or {}).get("method")
              or "GET").upper()

    params: dict = {}

    # Query string params (GET link flow)
    raw_qs = event.get("queryStringParameters") or {}
    params.update({k: v for k, v in raw_qs.items() if v is not None})

    # POST JSON body (future Slack slash command / interactive payload)
    if method == "POST":
        body_raw = event.get("body") or ""
        if event.get("isBase64Encoded"):
            import base64
            body_raw = base64.b64decode(body_raw).decode("utf-8", "replace")
        if body_raw:
            try:
                body = json.loads(body_raw)
                if isinstance(body, dict):
                    params.update({k: v for k, v in body.items() if isinstance(v, str)})
            except json.JSONDecodeError:
                # application/x-www-form-urlencoded fallback (Slack slash commands)
                try:
                    import urllib.parse
                    form = dict(urllib.parse.parse_qsl(body_raw))
                    params.update(form)
                except Exception:  # noqa: BLE001
                    pass

    incident_id = (params.get("incident_id") or "").strip()
    action = (params.get("action") or "").strip().lower()
    token = (params.get("token") or "").strip()

    # Optional audit fields (BACKEND_SPEC 5.2): approver identity and the
    # rejection reason submitted from the dashboard's Reject form.
    approved_by = (params.get("approved_by") or "").strip()[:1000]
    reason = (params.get("reason") or "").strip()[:1000]

    if not incident_id:
        return None, _response(400, {"error": "Missing incident_id."})
    if not re.fullmatch(r"[0-9a-fA-F-]{16,64}", incident_id):
        return None, _response(400, {"error": "Malformed incident_id."})
    if action not in VALID_ACTIONS:
        return None, _response(400, {"error": f"Invalid action '{action}'. Must be one of: approve, reject."})

    return {
        "incident_id": incident_id,
        "action": action,
        "token": token,
        "approved_by": approved_by,
        "reason": reason,
    }, None


# ===========================================================================
# Token verification
# ===========================================================================

def _token_valid(incident_id: str, action: str, token: str | None) -> bool:
    """HMAC-SHA256(incident_id:action) check. Returns False on any mismatch/failure.

    The token is bound to both the incident_id and the action, matching the
    notify Lambda's link builder: token = HMAC-SHA256(secret, f"{incident_id}:{action}").hexdigest()
    """
    secret = _get_approval_secret()
    if not secret:
        # No secret configured: fail closed for security, log loudly.
        logger.error(
            "APPROVAL_TOKEN_SECRET_SSM not configured or empty — rejecting request. "
            "Create the SSM SecureString parameter (see README, Phase 5 setup)."
        )
        return False
    if not token:
        return False
    signed = f"{incident_id}:{action}"
    expected = hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, token.lower())


def _get_approval_secret() -> str | None:
    if "approval_secret" in _cache:
        return _cache["approval_secret"]
    if not APPROVAL_TOKEN_SECRET_SSM:
        return None
    try:
        resp = _ssm.get_parameter(Name=APPROVAL_TOKEN_SECRET_SSM, WithDecryption=True)
        value = (resp.get("Parameter", {}).get("Value") or "").strip()
    except ClientError as exc:
        logger.error(json.dumps({"event": "ssm_read_error", "parameter": APPROVAL_TOKEN_SECRET_SSM, "error": str(exc)}))
        return None
    _cache["approval_secret"] = value or None
    return _cache["approval_secret"]


# ===========================================================================
# DynamoDB status transition (conditional — the guardrail gate)
# ===========================================================================

def _update_remediation_status(
    incident_id: str,
    new_status: str,
    approved_by: str | None = None,
    rejected_reason: str | None = None,
) -> str | None:
    """
    Conditionally set remediation.status from pending_approval to
    approved/rejected, optionally recording the approver identity and/or
    rejection reason (BACKEND_SPEC 5.2 approval audit trail). Returns the new
    status on success, "conditional_failed" when the item was already
    processed, or None on error/no-item.
    """
    table = _dynamodb.Table(INCIDENTS_TABLE)
    now = datetime.now(timezone.utc).isoformat()
    set_parts = [
        "remediation.#st = :new_status",
        "remediation.#decided_at = :decided_at",
    ]
    names = {"#st": "status", "#decided_at": "decided_at"}
    values = {
        ":pending": "pending_approval",
        ":new_status": new_status,
        ":decided_at": now,
    }
    if approved_by:
        set_parts.append("remediation.#approved_by = :approved_by")
        names["#approved_by"] = "approved_by"
        values[":approved_by"] = approved_by
    if rejected_reason:
        set_parts.append("remediation.#rejected_reason = :rejected_reason")
        names["#rejected_reason"] = "rejected_reason"
        values[":rejected_reason"] = rejected_reason
    try:
        table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression="SET " + ", ".join(set_parts),
            ConditionExpression="remediation.#st = :pending",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return new_status
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ConditionalCheckFailedException":
            return "conditional_failed"
        logger.error(json.dumps({
            "event": "dynamodb_update_error",
            "incident_id": incident_id,
            "error": str(exc),
        }))
        return None


def _get_current_status(incident_id: str) -> str | None:
    try:
        resp = _dynamodb.Table(INCIDENTS_TABLE).get_item(
            Key={"incident_id": incident_id},
            ProjectionExpression="remediation.#st",
            ExpressionAttributeNames={"#st": "status"},
        )
        return (resp.get("Item", {}).get("remediation", {}) or {}).get("status")
    except ClientError as exc:
        logger.error(json.dumps({"event": "dynamodb_get_error", "incident_id": incident_id, "error": str(exc)}))
        return None


# ===========================================================================
# Remediation invocation (Phase 6 stub)
# ===========================================================================

def _invoke_remediation(incident_id: str) -> bool:
    """Async-invoke the remediation Lambda; False when it's not wired yet."""
    if not REMEDIATION_FUNCTION_NAME:
        logger.warning(json.dumps({
            "event": "remediation_invoke_skipped",
            "reason": "REMEDIATION_FUNCTION_NAME not configured (Phase 6 not deployed)",
            "incident_id": incident_id,
        }))
        return False
    try:
        _lambda.invoke(
            FunctionName=REMEDIATION_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps({"incident_id": incident_id}),
        )
        logger.info(json.dumps({"event": "remediation_invoked", "incident_id": incident_id}))
        return True
    except ClientError as exc:
        logger.error(json.dumps({
            "event": "remediation_invoke_error",
            "incident_id": incident_id,
            "error": str(exc),
        }))
        return False


# ===========================================================================
# Human-readable HTML responses (endpoint is clicked from Slack)
# ===========================================================================

def _html_response(status_code: int, message: str) -> dict:
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Incident Approval</title>"
        "<style>body{font-family:-apple-system,sans-serif;display:flex;"
        "align-items:center;justify-content:center;height:100vh;margin:0;"
        "background:#1a1d21;color:#fff}div{max-width:480px;text-align:center;"
        "padding:2rem}h1{font-size:1.2rem}</style></head>"
        f"<body><div><h1>LLM Incident Response</h1><p>{message}</p></div></body></html>"
    )
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": html,
    }


def _response(status_code: int, body_obj: dict) -> dict:
    """JSON response — used for POST bodies and any machine consumer."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_obj),
    }
