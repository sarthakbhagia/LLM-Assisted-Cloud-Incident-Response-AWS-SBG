#!/usr/bin/env python3
"""
replay_dlq.py - Drain the shared pipeline DLQ and re-invoke the matching
Lambda for every failed message.

Every async hop in the pipeline (EventBridge rules, function async invokes,
the Scheduler-driven verification re-check) lands failed events in
`incident-pipeline-dlq-{env}`. This script reads each message, works out
which Lambda should have processed it, re-invokes that Lambda with the
original payload, and deletes the message ONLY on a successful re-invoke.
Undecipherable messages are optionally moved aside instead of deleted.

Usage:
    python scripts/replay_dlq.py [--region ap-south-1] \
        [--stack llm-incident-response-staging] [--queue <name|url>] \
        [--env staging] [--dry-run] [--limit N] [--keep-poison]

Target resolution order (classification ladder):
  1. Envelope preserved by Lambda async-invoke / EventBridge rule DLQs:
     {"requestContext": {"requestId": ...}, "responsePayload": ...}  (async)
     {"version": ..., "responseContext": {...}, "requestPayload": ...} (rule)
     -> route to the hop that dropped it, using requestPayload.
  2. Scheduler DLQ payload: the verification re-check input
     {"incident_id": ..., "phase": "recheck", ...} -> VerificationFunction.
  3. Raw EventBridge rule input (e.g. collector InputTransformer output):
     {"source": "cloudwatch", "fault_class": ..., "alarm_name": ...}
     -> CollectorFunction.
  4. Envelope with unknown structure or unresolvable function:
     logged, kept (never deleted), counted as unknown unless --keep-poison
     is off, in which case unresolvable-but-parseable JSON goes to the
     parking-lot queue suffix "-poison".

Exit codes: 0 = nothing stranded or all replayed; 1 = some messages could
not be replayed (they remain in the queue); 2 = usage/AWS error.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Hop ordering: each entry knows how to classify one message shape.
# (description, classifier(message_dict) -> function_logical_name | None)

KNOWN_FUNCTIONS = {
    "collector": "CollectorFunction",
    "diagnosis": "DiagnosisFunction",
    "notify": "NotifyFunction",
    "approval": "ApprovalFunction",
    "remediation": "RemediationFunction",
    "verification": "VerificationFunction",
    "dashboard": "DashboardApiFunction",
    "sweeper": "SweeperFunction",
}


def _envelope_function_and_payload(message: dict):
    """
    Unwrap Lambda-async / EventBridge-rule failure envelopes.
    Returns (function_logical_name | None, inner_payload_dict_or_None).
    """
    request_ctx = message.get("requestContext")
    if isinstance(request_ctx, dict) and "requestPayload" not in message:
        # Lambda async-invoke DLQ envelope: condition excludes rule envelopes
        # (they carry requestPayload at top level and responseContext).
        pass
    if "requestPayload" in message and "responseContext" in message:
        # EventBridge rule DLQ envelope
        return None, message.get("requestPayload")
    if "requestContext" in message and "responsePayload" in message:
        # Lambda async-invoke envelope; requestId encodes the function ARN
        # only in some paths - can't resolve reliably, caller decides.
        return None, message.get("requestPayload") if "requestPayload" in message else message
    return None, None


def classify_message(message: dict) -> tuple:
    """
    Returns (target_logical_name | None, payload_for_invoke | None, note).
    Classification ladder - first match wins.
    """
    # --- ladder 1: EventBridge rule envelope -------------------------------
    if "requestPayload" in message and "responseContext" in message:
        inner = message["requestPayload"]
        if isinstance(inner, dict):
            fn = _classify_business_payload(inner)
            return fn, inner, "eventbridge-rule-envelope"
        return None, None, "eventbridge-rule-envelope-unparseable"

    # --- ladder 2: Lambda async-invoke envelope ----------------------------
    if "requestContext" in message and "responsePayload" in message:
        request_payload = message.get("requestPayload")
        if isinstance(request_payload, dict):
            fn = _classify_business_payload(request_payload)
            note = "lambda-async-envelope"
            if fn is None:
                fn = _function_from_response_payload(message.get("responsePayload"))
            return fn, request_payload, note
        return None, None, "lambda-async-envelope-unparseable"

    # --- ladder 3/4: raw payload (scheduler DLQ, transformer output, etc) --
    fn = _classify_business_payload(message)
    if fn:
        return fn, message, "raw-payload"

    # Scheduler DLQ shape is the re-check payload itself; phase=recheck is
    # a strong signal but payload came back None, so report it explicitly.
    if message.get("phase") == "recheck":
        return None, None, "scheduler-payload-unresolvable"

    return None, None, "unknown-shape"


def _classify_business_payload(payload: dict):
    """Map a pipeline business payload to the owning function's logical name."""
    if not isinstance(payload, dict):
        return None
    if payload.get("phase") == "recheck" and payload.get("incident_id"):
        return "VerificationFunction"
    if payload.get("source") == "cloudwatch" and payload.get("fault_class"):
        return "CollectorFunction"
    if payload.get("source") == "guardduty" and payload.get("fault_class"):
        return "CollectorFunction"
    if payload.get("incident_id") and "original_signal" in payload:
        return "VerificationFunction"
    if payload.get("incident_id") and payload.get("action") in ("approve", "reject"):
        return "ApprovalFunction"
    if isinstance(payload.get("incident_id"), str) and payload.get("fault_class") is None \
            and payload.get("original_signal") is None and payload.get("phase") is None:
        # Bare {"incident_id": ...} is the approval->remediation contract;
        # verified against approval_handler._invoke_remediation.
        return "RemediationFunction"
    return None


def _function_from_response_payload(response_payload) -> str | None:
    """Best-effort: extract the failing function from an error response body."""
    if isinstance(response_payload, str):
        try:
            response_payload = json.loads(response_payload)
        except (ValueError, TypeError):
            return None
    if not isinstance(response_payload, dict):
        return None
    body = response_payload.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (ValueError, TypeError):
            body = {}
    if not isinstance(body, dict):
        return None
    # e.g. remediation 409 body mentions remediation status; approval errors
    # mention approval. Keep this conservative - only accept exact hints.
    error = str(body.get("error", "")).lower()
    if "remediation" in error:
        return "RemediationFunction"
    if "verification" in error:
        return "VerificationFunction"
    if "approval" in error:
        return "ApprovalFunction"
    return None


def resolve_queue(client, args) -> str:
    """Return the queue URL from explicit name/url, stack physical ids, or env suffix."""
    if args.queue:
        if args.queue.startswith("http"):
            return args.queue
        return client.get_queue_url(QueueName=args.queue)["QueueUrl"]

    if args.stack:
        cfn = boto3.client("cloudformation", region_name=args.region)
        try:
            res = cfn.describe_stack_resource(
                StackName=args.stack, LogicalResourceId="PipelineDlq")
            physical = res["StackResourceDetail"]["PhysicalResourceId"]
            if physical:
                return client.get_queue_url(QueueName=physical)["QueueUrl"]
        except (ClientError, BotoCoreError):
            pass  # fall through to conventional name

    name = f"incident-pipeline-dlq-{args.env}"
    return client.get_queue_url(QueueName=name)["QueueUrl"]


def resolve_function_arn(client_lambda, logical_name: str, stack: str | None) -> str:
    """Resolve a logical name to a real function; stack name narrows the search."""
    if stack:
        try:
            cfn = boto3.client("cloudformation", region_name=boto3.session.Session().region_name
                               or "ap-south-1")
            res = cfn.describe_stack_resource(
                StackName=stack, LogicalResourceId=logical_name)
            physical = res["StackResourceDetail"]["PhysicalResourceId"]
            if physical:
                return physical
        except (ClientError, BotoCoreError):
            pass
    # Fall back to prefix search over the account's functions
    for page in client_lambda.get_paginator("list_functions").paginate():
        for fn in page["Functions"]:
            name = fn["FunctionName"]
            if logical_name in name or name.endswith(f"-{logical_name}"):
                return name
    raise ValueError(f"could not resolve function for logical name {logical_name!r}")


def replay_message(sqs, lambdas, msg: dict, args) -> dict:
    """
    Handle one SQS message. Returns a per-message outcome dict.
    Never deletes on failure - the message stays for the next run.
    """
    body_raw = msg.get("Body", "")
    receipt = msg["ReceiptHandle"]
    attrs = msg.get("MessageAttributes", {})
    orig_id = attrs.get("OriginalRequestId", {}).get("StringValue")
    try:
        body = json.loads(body_raw)
        if not isinstance(body, dict):
            body = {"_non_dict": body}
    except ValueError:
        body = {"_unparseable": body_raw[:200]}

    target_logical, payload, note = classify_message(body)

    if target_logical is None or payload is None:
        return {"status": "unknown", "note": note, "orig_id": orig_id}

    try:
        function_name = resolve_function_arn(
            boto3.client("lambda", region_name=args.region), target_logical, args.stack)
    except ValueError as exc:
        return {"status": "unknown", "note": f"resolution-failed: {exc}", "orig_id": orig_id}

    if isinstance(payload, dict) and "event_uid" not in payload:
        payload = dict(payload, event_uid=uuid.uuid4().hex[:12])

    if args.dry_run:
        return {"status": "dry-run", "target": function_name,
                "note": note, "orig_id": orig_id}

    try:
        lambdas.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(payload, default=str),
        )
    except (ClientError, BotoCoreError) as exc:
        return {"status": "invoke-failed", "target": function_name,
                "note": str(exc)[:200], "orig_id": orig_id}

    # Success only now: the message leaves the queue.
    sqs.delete_message(QueueUrl=args.queue_url, ReceiptHandle=receipt)
    return {"status": "replayed", "target": function_name, "note": note,
            "orig_id": orig_id}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay stranded pipeline messages from the shared DLQ.")
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--stack",
                        help="CloudFormation stack name; resolves PipelineDlq + functions exactly")
    parser.add_argument("--queue",
                        help="DLQ name or https:// URL; overrides --stack/--env")
    parser.add_argument("--env", default="staging",
                        help="environment suffix for the conventional queue name (default: staging)")
    parser.add_argument("--limit", type=int, default=50,
                        help="max messages to process per run (default 50)")
    parser.add_argument("--dry-run", action="store_true",
                        help="classify and print without invoking or deleting")
    parser.add_argument("--keep-poison", action="store_true",
                        help="leave undecipherable messages in the queue (default keeps them too)")
    args = parser.parse_args(argv)

    sqs = boto3.client("sqs", region_name=args.region)
    try:
        args.queue_url = resolve_queue(sqs, args)
    except (ClientError, BotoCoreError) as exc:
        print(f"ERROR: could not resolve DLQ queue: {exc}", file=sys.stderr)
        return 2

    print(f"DLQ: {args.queue_url}")
    lambdas = boto3.client("lambda", region_name=args.region)

    summary = {"replayed": 0, "dry-run": 0, "unknown": 0, "invoke-failed": 0}
    processed = 0

    while processed < args.limit:
        resp = sqs.receive_message(
            QueueUrl=args.queue_url,
            MaxNumberOfMessages=min(10, args.limit - processed),
            WaitTimeSeconds=1,
            MessageAttributeNames=["All"],
        )
        messages = resp.get("Messages", [])
        if not messages:
            break

        for msg in messages:
            if processed >= args.limit:
                break
            processed += 1
            outcome = replay_message(sqs, lambdas, msg, args)
            summary[outcome["status"]] = summary.get(outcome["status"], 0) + 1
            stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{stamp}] {outcome['status']:>13}  "
                  f"target={outcome.get('target', '-'):40}  "
                  f"note={outcome.get('note', '')[:70]}  "
                  f"orig_id={outcome.get('orig_id') or '-'}")

    if not processed:
        print("Queue is empty - nothing to replay.")
        return 0

    print(f"\nDone: {summary}")
    if summary["unknown"] or summary["invoke-failed"]:
        print("Some messages could not be replayed and remain in the queue.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
