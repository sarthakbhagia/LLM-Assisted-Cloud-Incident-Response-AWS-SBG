"""
sweeper_lambda.py — Approved-state sweeper (pipeline self-healing)

The approval handler flips remediation.status to "approved" and then
async-invokes the remediation Lambda. If that invoke fails (throttle,
permissions, transient AWS error) or the remediation Lambda crashes before
writing its own terminal status, the incident is stranded at "approved"
forever — observed live in staging (incident approved at 08:03 UTC still
sitting there 9+ hours later).

This sweeper runs on a schedule (default every 5 minutes), finds incidents
whose remediation.status has been "approved" for longer than
STUCK_AFTER_SECONDS, and re-invokes the remediation Lambda.

Safety properties:
  - Re-invocation is idempotent: remediation re-checks remediation.status
    and writes its terminal state under a conditional update; the sweeper
    never changes remediation.status itself.
  - STUCK_AFTER_SECONDS (default 600) comfortably exceeds the remediation
    function timeout (300s), so the sweeper can never race a still-running
    first attempt.
  - MAX_SWEEP_PER_RUN bounds blast radius; MAX_AGE_HOURS stops re-invoking
    abandoned records (they are counted and logged instead).
  - Every sweep is recorded (remediation.swept_at, remediation.sweep_count)
    so the Phase 7 evaluation can quantify how often the loop stalls.

Event: scheduled (EventBridge rate) or manual test invoke {"dry_run": true}
Response: {"scanned": n, "swept": n, "skipped_recent": n, "expired": n, "failed": n}
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

_dynamodb = boto3.resource("dynamodb")
_lambda = boto3.client("lambda")

INCIDENTS_TABLE = os.environ["INCIDENTS_TABLE"]
REMEDIATION_FUNCTION_NAME = os.environ.get("REMEDIATION_FUNCTION_NAME", "")
STUCK_AFTER_SECONDS = int(os.environ.get("STUCK_AFTER_SECONDS", "600"))
MAX_SWEEP_PER_RUN = int(os.environ.get("MAX_SWEEP_PER_RUN", "10"))
MAX_AGE_HOURS = int(os.environ.get("MAX_AGE_HOURS", "48"))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _stuck_since(record: dict) -> datetime | None:
    """Timestamp the record entered 'approved': decided_at, else detected_at."""
    remediation = record.get("remediation") or {}
    return (
        _parse_iso(remediation.get("decided_at"))
        or _parse_iso(record.get("detected_at"))
    )


def _scan_approved(table) -> list:
    """Scan the whole table, keeping records with remediation.status=approved."""
    records: list = []
    scan_kwargs = {
        "FilterExpression": "remediation.#st = :approved",
        "ExpressionAttributeNames": {"#st": "status"},
        "ExpressionAttributeValues": {":approved": "approved"},
        "ProjectionExpression": (
            "incident_id, detected_at, remediation, diagnosis.suggested_action"
        ),
    }
    while True:
        response = table.scan(**scan_kwargs)
        records.extend(response.get("Items", []))
        lek = response.get("LastEvaluatedKey")
        if not lek:
            return records
        scan_kwargs["ExclusiveStartKey"] = lek


def _reinvoke_remediation(incident_id: str) -> bool:
    if not REMEDIATION_FUNCTION_NAME:
        logger.warning(json.dumps({
            "event": "sweep_invoke_skipped",
            "reason": "REMEDIATION_FUNCTION_NAME not configured",
            "incident_id": incident_id,
        }))
        return False
    try:
        _lambda.invoke(
            FunctionName=REMEDIATION_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps({"incident_id": incident_id}),
        )
        return True
    except ClientError as exc:
        logger.error(json.dumps({
            "event": "sweep_invoke_error",
            "incident_id": incident_id,
            "error": str(exc),
        }))
        return False


def _record_sweep(table, incident_id: str) -> None:
    """Bookkeeping only — deliberately does NOT touch remediation.status."""
    table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression=(
            "SET remediation.swept_at = :now, "
            "remediation.sweep_count = if_not_exists(remediation.sweep_count, :zero) + :one"
        ),
        ExpressionAttributeValues={":now": datetime.now(timezone.utc).isoformat(),
                                   ":zero": 0, ":one": 1},
    )


def lambda_handler(event, context):
    dry_run = bool(isinstance(event, dict) and event.get("dry_run"))
    now = datetime.now(timezone.utc)
    stuck_after = timedelta(seconds=STUCK_AFTER_SECONDS)
    max_age = timedelta(hours=MAX_AGE_HOURS)

    table = _dynamodb.Table(INCIDENTS_TABLE)
    result = {"scanned": 0, "swept": 0, "skipped_recent": 0,
              "expired": 0, "failed": 0, "dry_run": dry_run}

    try:
        candidates = _scan_approved(table)
    except ClientError as exc:
        logger.error(json.dumps({"event": "sweeper_scan_error", "error": str(exc)}))
        result["error"] = "scan_failed"
        return result

    result["scanned"] = len(candidates)

    for record in candidates:
        incident_id = record.get("incident_id", "unknown")
        entered_approved = _stuck_since(record)
        if entered_approved is None:
            result["expired"] += 1  # no usable timestamp: do not retry forever
            continue

        stuck_for = now - entered_approved
        if stuck_for < stuck_after:
            result["skipped_recent"] += 1
            continue
        if stuck_for > max_age:
            result["expired"] += 1
            logger.warning(json.dumps({
                "event": "sweep_expired",
                "incident_id": incident_id,
                "stuck_hours": round(stuck_for.total_seconds() / 3600, 1),
            }))
            continue

        if result["swept"] + result["failed"] >= MAX_SWEEP_PER_RUN:
            break  # defer the rest to the next scheduled run

        if dry_run:
            logger.info(json.dumps({
                "event": "sweep_dry_run",
                "incident_id": incident_id,
                "stuck_seconds": int(stuck_for.total_seconds()),
            }))
            result["swept"] += 1
            continue

        if _reinvoke_remediation(incident_id):
            _record_sweep(table, incident_id)
            result["swept"] += 1
            logger.info(json.dumps({
                "event": "incident_swept",
                "incident_id": incident_id,
                "stuck_seconds": int(stuck_for.total_seconds()),
            }))
        else:
            result["failed"] += 1

    logger.info(json.dumps({"event": "sweeper_complete", **result}))
    return result
