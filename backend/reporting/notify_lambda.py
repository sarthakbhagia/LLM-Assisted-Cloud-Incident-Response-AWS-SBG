"""
app.py — Phase 5: Notify Lambda Handler (reporting)

Receives the diagnosis payload from the diagnosis Lambda, formats it into a
readable Slack incident report (root cause, confidence, suggested action,
explanation) and posts it to a Slack channel via incoming webhook
(spec step 17). The message ends with approve/reject links pointing at the
Phase 5 approval endpoint.

Design notes:
- Invoked async (fire-and-forget) from the diagnosis Lambda. Failures are
  logged and returned as a flag, never raised — a Slack outage must not break
  the incident pipeline.
- Secrets (Slack webhook URL, approval-link HMAC secret) are read at runtime
  from SSM SecureString parameters — no secrets in env values or code.
- Everything beyond the incoming payload (incident record, raw data, SSM
  values) is best-effort: the message degrades gracefully instead of failing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients — initialised once at cold start
_ssm = boto3.client("ssm")
_dynamodb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")

# Config from environment
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "")
DATA_LAKE_BUCKET = os.environ.get("DATA_LAKE_BUCKET", "")
SLACK_WEBHOOK_URL_SSM = os.environ.get("SLACK_WEBHOOK_URL_SSM", "")
APPROVAL_TOKEN_SECRET_SSM = os.environ.get("APPROVAL_TOKEN_SECRET_SSM", "")
APPROVAL_API_BASE = os.environ.get("APPROVAL_API_BASE", "").rstrip("/")

# Slack message limits
SLACK_TEXT_CLIP = 700
SLACK_HEADER_CLIP = 140

# Module-level caches (warm container reuse) for SSM lookups
_cache: dict = {}

FAULT_CLASS_LABELS = {
    "resource_exhaustion": "Resource Exhaustion",
    "misconfiguration": "Misconfiguration / Security Non-Compliance",
    "service_cascade": "Service Failure Cascade",
}

ACTION_LABELS = {
    "scale_up": "Scale up the service",
    "restart_service": "Restart the service",
    "lock_s3_bucket": "Lock the S3 bucket (enable Public Access Block)",
    "tighten_iam_policy": "Tighten the IAM policy",
    "restart_downstream_service": "Restart the downstream service",
    "manual_review_required": "Manual review required — no automated fix",
}


# ===========================================================================
# Entry point
# ===========================================================================

def lambda_handler(event, context):
    logger.info(json.dumps({"event": "notify_triggered", "payload_event": event}, default=str))

    incident_id = event.get("incident_id")
    diagnosis = event.get("diagnosis") or {}

    if not incident_id or not diagnosis:
        logger.error("notify invoked without incident_id or diagnosis; skipping")
        return {"statusCode": 400, "body": json.dumps({"error": "missing incident_id or diagnosis"})}

    # Best-effort enrichment: incident record (fault_class, detected_at, key)
    incident = _get_incident_record(incident_id)
    if not incident:
        # Allow local/test payloads to carry these fields directly.
        incident = {
            "fault_class": event.get("fault_class"),
            "detected_at": event.get("detected_at"),
            "raw_data_s3_key": event.get("raw_data_s3_key"),
        }

    detection_context = _get_detection_context(incident)

    message = _build_slack_message(incident_id, diagnosis, incident, detection_context)
    posted = _post_to_slack(message)

    logger.info(json.dumps({
        "event": "notify_complete",
        "incident_id": incident_id,
        "slack_posted": posted,
    }))
    return {
        "statusCode": 200,
        "body": json.dumps({"incident_id": incident_id, "slack_posted": posted}),
    }


# ===========================================================================
# Data enrichment (all best-effort)
# ===========================================================================

def _get_incident_record(incident_id: str) -> dict:
    """Fetch the IncidentRecord for enrichment; empty dict on any failure."""
    if not INCIDENTS_TABLE:
        logger.warning("INCIDENTS_TABLE not configured; message will use payload fields only")
        return {}
    try:
        resp = _dynamodb.Table(INCIDENTS_TABLE).get_item(Key={"incident_id": incident_id})
        return resp.get("Item") or {}
    except ClientError as exc:
        logger.warning(json.dumps({"event": "incident_fetch_error", "error": str(exc)}))
        return {}


def _get_detection_context(incident: dict) -> dict:
    """Pull the detection trigger (alarm/rule/finding) from raw_data.json; best-effort."""
    bucket = DATA_LAKE_BUCKET
    s3_key = incident.get("raw_data_s3_key")
    if not bucket or not s3_key:
        return {}
    try:
        resp = _s3.get_object(Bucket=bucket, Key=s3_key)
        raw = json.loads(resp["Body"].read().decode("utf-8"))
        detection = raw.get("detection_event", {}) or {}
        return {
            "source": raw.get("detection_source") or detection.get("source"),
            "alarm_name": detection.get("alarm_name"),
            "config_rule": detection.get("config_rule"),
            "resource_id": detection.get("resource_id"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(json.dumps({"event": "raw_data_fetch_error", "error": str(exc)}))
        return {}


# ===========================================================================
# Slack message construction
# ===========================================================================

def _slack_escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clip(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _confidence_display(confidence) -> str:
    try:
        return f"{float(confidence) * 100:.0f}%"
    except (TypeError, ValueError):
        return "unknown"


def _approval_url(incident_id: str, action: str) -> str | None:
    """Build a signed approve/reject link; None when config is incomplete.

    The token is bound to both the incident_id and the action, so an approve
    link cannot be reused as a reject link (and vice-versa). Syntax:
        token = HMAC-SHA256(secret, f"{incident_id}:{action}").hexdigest()
    """
    if not APPROVAL_API_BASE:
        return None
    secret = _get_approval_secret()
    if not secret:
        return None
    signed = f"{incident_id}:{action}"
    token = hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
    query = urllib.parse.urlencode({"incident_id": incident_id, "action": action, "token": token})
    return f"{APPROVAL_API_BASE}?{query}"


def _build_slack_message(incident_id: str, diagnosis: dict, incident: dict, detection: dict) -> dict:
    fault_class = incident.get("fault_class") or diagnosis.get("fault_class") or "unknown"
    fault_label = FAULT_CLASS_LABELS.get(fault_class, fault_class)
    detected_at = incident.get("detected_at") or diagnosis.get("detected_at") or "unknown"
    root_cause = diagnosis.get("root_cause") or "(missing root cause)"
    confidence = _confidence_display(diagnosis.get("confidence"))
    suggested_action = diagnosis.get("suggested_action") or "unknown"
    action_label = ACTION_LABELS.get(suggested_action, suggested_action)
    explanation = diagnosis.get("explanation") or "(no explanation provided)"
    affected = ", ".join(diagnosis.get("affected_resources") or []) or "(none listed)"

    header_text = _clip(f":rotating_light: Incident {incident_id[:8]} — {fault_label}", SLACK_HEADER_CLIP)

    fields = [
        {"type": "mrkdwn", "text": f"*Fault class:*\n{_slack_escape(fault_label)}"},
        {"type": "mrkdwn", "text": f"*Diagnosis confidence:*\n{_slack_escape(confidence)}"},
        {"type": "mrkdwn", "text": f"*Suggested action:*\n`{_slack_escape(suggested_action)}` — {_slack_escape(action_label)}"},
        {"type": "mrkdwn", "text": f"*Detected at:*\n{_slack_escape(detected_at)}"},
    ]

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header_text}},
        {"type": "section", "fields": fields},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Root cause:*\n{_slack_escape(_clip(root_cause, SLACK_TEXT_CLIP))}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Explanation:*\n{_slack_escape(_clip(explanation, SLACK_TEXT_CLIP))}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Affected resources:*\n{_slack_escape(_clip(affected, SLACK_TEXT_CLIP))}"}},
    ]

    trigger_bits = [detection.get("source"), detection.get("alarm_name"), detection.get("config_rule"), detection.get("resource_id")]
    trigger_bits = [b for b in trigger_bits if b]
    if trigger_bits:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":mag: Triggered by: {_slack_escape(' | '.join(str(b) for b in trigger_bits))}"}],
        })

    approve_url = _approval_url(incident_id, "approve")
    reject_url = _approval_url(incident_id, "reject")
    if approve_url and reject_url:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f":white_check_mark: *<{approve_url}|Approve fix>*    "
                f":no_entry: *<{reject_url}|Reject>*"
            )},
        })
    else:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": (
                ":information_source: Approval links not configured — set the "
                "`ApprovalApiBaseUrl` parameter and redeploy, or POST to /approval directly."
            )}],
        })

    context_bits = [f"Incident: `{incident_id}`"]
    if DATA_LAKE_BUCKET and incident.get("raw_data_s3_key"):
        context_bits.append(
            f"<https://s3.console.aws.amazon.com/s3/object/{DATA_LAKE_BUCKET}"
            f"?prefix={urllib.parse.quote(str(incident['raw_data_s3_key']))}|raw evidence>"
        )
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "  •  ".join(context_bits) + "  •  Full reasoning trace: DynamoDB incident record"}],
    })

    text_fallback = (
        f":rotating_light: Incident {incident_id} ({_slack_escape(fault_label)}) — "
        f"{_slack_escape(root_cause)} "
        f"(confidence {confidence}, suggested action: {_slack_escape(suggested_action)})"
    )
    # When enrichment (incident record + raw_data.json) is unavailable the
    # message still posts — we never let a downstream outage break the
    # pipeline — but we flag it explicitly so the channel operator can tell
    # "LLM had no explanation" apart from "our reporting layer couldn't load
    # the record".
    enrichment_ok = bool(incident.get("incident_id") and detection.get("source"))
    if not enrichment_ok:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": (
                ":warning: Evidence unavailable — incident record or raw_data.json "
                "could not be loaded (check Lambda logs). Posting with payload fields only."
            )}],
        })

    return {"text": _clip(text_fallback, 300), "blocks": blocks}


# ===========================================================================
# Secrets + Slack delivery
# ===========================================================================

def _get_ssm_secure_parameter(name: str, cache_key: str) -> str | None:
    """Read and decrypt an SSM SecureString; cached per warm container."""
    if not name:
        return None
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        resp = _ssm.get_parameter(Name=name, WithDecryption=True)
        value = (resp.get("Parameter", {}).get("Value") or "").strip()
    except ClientError as exc:
        logger.error(json.dumps({"event": "ssm_read_error", "parameter": name, "error": str(exc)}))
        return None
    _cache[cache_key] = value or None
    return _cache[cache_key]


def _get_approval_secret() -> str | None:
    return _get_ssm_secure_parameter(APPROVAL_TOKEN_SECRET_SSM, "approval_secret")


def _get_webhook_url() -> str | None:
    return _get_ssm_secure_parameter(SLACK_WEBHOOK_URL_SSM, "webhook_url")


def _post_to_slack(message: dict) -> bool:
    """POST the message to the Slack incoming webhook. Never raises."""
    webhook_url = _get_webhook_url()
    if not webhook_url:
        logger.warning(
            "SLACK_WEBHOOK_URL_SSM not configured or parameter empty; skipping Slack post. "
            "Create the SSM SecureString parameter (see README, Phase 5 setup)."
        )
        return False

    payload = json.dumps(message).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            body = resp.read().decode("utf-8", "replace")
        logger.info(json.dumps({"event": "slack_posted", "status": resp.status, "response": body[:100]}))
        return True
    except urllib.error.HTTPError as exc:
        # The error response body may be unreadable (fp=None) — never let the
        # logging path itself raise.
        try:
            body = exc.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            body = "(unreadable)"
        logger.error(json.dumps({"event": "slack_http_error", "status": exc.code, "body": body}))
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error(json.dumps({"event": "slack_post_error", "error": str(exc)}))
        return False
