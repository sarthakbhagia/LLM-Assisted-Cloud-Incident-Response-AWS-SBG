"""
actions.py - Phase 6: Remediation Actions

One function per action key from the diagnosis contract.
Each function receives the full incident record and returns:
    {"success": bool, "action_key": str, "notes": str}

Design notes:
- All functions are Lambda-based. The demo app uses Lambda, not ECS.
- restart_service / restart_downstream_service: bump a RESTART_TRIGGER
  env var via UpdateFunctionConfiguration to force a cold start without
  changing runtime behaviour.
- scale_up: increase Lambda reserved concurrency via PutFunctionConcurrency.
- lock_s3_bucket: apply full public access block via PutPublicAccessBlock.
- tighten_iam_policy: attach a hardcoded safe deny policy. The LLM output
  is NEVER used to generate IAM policy JSON - this is enforced by the spec
  guardrail ("have a pre-defined safe policy ready").
- manual_review_required: no-op, just flags for a human.

All functions catch ClientError and return success=False rather than raising,
so the remediation Lambda can always update DynamoDB with the outcome.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_lambda_client = boto3.client("lambda")
_s3 = boto3.client("s3")
_iam = boto3.client("iam")

# ---------------------------------------------------------------------------
# Pre-defined safe deny policy for tighten_iam_policy.
# This is a MODULE CONSTANT - never generated from LLM output.
# Denies admin-equivalent IAM, org, and account-management actions.
# ---------------------------------------------------------------------------
_SAFE_DENY_POLICY: dict = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DenyAdminActions",
            "Effect": "Deny",
            "Action": [
                "iam:*",
                "organizations:*",
                "account:*",
            ],
            "Resource": "*",
        }
    ],
}

_SAFE_DENY_POLICY_NAME = "IncidentResponseSafeDenyPolicy"


# ===========================================================================
# Dispatcher
# ===========================================================================

def dispatch(action_key: str, incident_record: dict) -> dict:
    """Route to the correct action function based on action_key."""
    _map = {
        "scale_up": scale_up,
        "restart_service": restart_service,
        "lock_s3_bucket": lock_s3_bucket,
        "tighten_iam_policy": tighten_iam_policy,
        "restart_downstream_service": restart_downstream_service,
        "manual_review_required": manual_review_required,
    }
    fn = _map.get(action_key)
    if fn is None:
        logger.error(json.dumps({"event": "unknown_action_key", "action_key": action_key}))
        return {
            "success": False,
            "action_key": action_key,
            "notes": (
                f"Unknown action key '{action_key}'. "
                "No remediation applied - incident flagged for manual review."
            ),
        }
    return fn(incident_record)


# ===========================================================================
# Helper: resolve target Lambda function name from the incident record
# ===========================================================================

def _get_affected_lambda(incident_record: dict) -> str | None:
    """
    Resolve the target Lambda function name.

    Priority:
    1. diagnosis.affected_resources[0] - what the LLM identified.
       If it looks like an ARN, extract the function-name portion.
    2. Fallback: infer from resource_id (which is the alarm name for
       CloudWatch-triggered incidents) using known naming conventions.
    """
    resources = (incident_record.get("diagnosis") or {}).get("affected_resources") or []
    if resources:
        candidate = str(resources[0])
        # Strip ARN prefix if the LLM returned a full ARN
        if "function:" in candidate:
            return candidate.split("function:")[-1].split(":")[0]
        # If it's a plain function name (not an ARN, not an alarm name), use it directly
        if not candidate.startswith("arn:") and not candidate.startswith("incident-"):
            return candidate

    # Fallback: infer from resource_id (alarm name)
    resource_id = (incident_record.get("resource_id") or "").lower()
    fault_class = incident_record.get("fault_class", "")

    if "service-c" in resource_id or fault_class == "service_cascade":
        return _find_lambda_by_prefix("ServiceC")
    if "service-b" in resource_id:
        return _find_lambda_by_prefix("ServiceB")
    # Default to service-a (resource exhaustion alarm targets service-a)
    return _find_lambda_by_prefix("ServiceA")


def _find_lambda_by_prefix(prefix: str) -> str | None:
    """Return the first Lambda function name containing the prefix (case-insensitive)."""
    try:
        paginator = _lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page["Functions"]:
                if prefix.lower() in fn["FunctionName"].lower():
                    return fn["FunctionName"]
    except ClientError as exc:
        logger.error(json.dumps({"event": "find_lambda_error", "prefix": prefix, "error": str(exc)}))
    return None


# ===========================================================================
# Action: scale_up
# ===========================================================================

def scale_up(incident_record: dict) -> dict:
    """
    Increase Lambda reserved concurrency for the affected function.

    If concurrency is currently uncapped (no reserved limit), set it to 50.
    If it already has a reserved limit, increase it by 25.
    If the account's unreserved concurrency floor would be violated, fall back
    to removing the reserved limit entirely (uncapped = effectively scaled up
    relative to a previously throttled function).
    """
    action_key = "scale_up"
    function_name = _get_affected_lambda(incident_record)
    if not function_name:
        return {
            "success": False,
            "action_key": action_key,
            "notes": "Could not resolve target Lambda function name from incident record.",
        }

    try:
        resp = _lambda_client.get_function_concurrency(FunctionName=function_name)
        current = resp.get("ReservedConcurrentExecutions")
        new_concurrency = (current + 25) if current is not None else 50

        try:
            _lambda_client.put_function_concurrency(
                FunctionName=function_name,
                ReservedConcurrentExecutions=new_concurrency,
            )
            logger.info(json.dumps({
                "event": "scale_up_applied",
                "function": function_name,
                "previous_concurrency": current,
                "new_concurrency": new_concurrency,
            }))
            return {
                "success": True,
                "action_key": action_key,
                "notes": (
                    f"Set reserved concurrency for '{function_name}' to {new_concurrency} "
                    f"(was: {'uncapped' if current is None else current})."
                ),
            }
        except ClientError as put_exc:
            error_code = put_exc.response.get("Error", {}).get("Code", "")
            # Account-level floor hit: remove the reserved limit instead so the
            # function shares from the unreserved pool (effectively uncapped).
            if error_code == "InvalidParameterValueException" and "UnreservedConcurrentExecution" in str(put_exc):
                logger.warning(json.dumps({
                    "event": "scale_up_floor_hit_removing_reserved_limit",
                    "function": function_name,
                    "attempted_concurrency": new_concurrency,
                    "error": str(put_exc),
                }))
                _lambda_client.delete_function_concurrency(FunctionName=function_name)
                return {
                    "success": True,
                    "action_key": action_key,
                    "notes": (
                        f"Removed reserved concurrency limit on '{function_name}' "
                        "(account unreserved floor prevented setting a higher value; "
                        "function now draws from unreserved pool - effectively uncapped)."
                    ),
                }
            raise  # re-raise unexpected ClientErrors

    except ClientError as exc:
        logger.error(json.dumps({"event": "scale_up_error", "function": function_name, "error": str(exc)}))
        return {"success": False, "action_key": action_key, "notes": f"ClientError during scale_up: {exc}"}


# ===========================================================================
# Action: restart_service
# ===========================================================================

def restart_service(incident_record: dict) -> dict:
    """
    Force a Lambda cold start on the affected service by bumping the
    _RESTART_TRIGGER environment variable to the current UTC timestamp.
    Lambda discards existing warm execution environments on the next deploy
    (UpdateFunctionConfiguration counts as a deploy event).
    """
    action_key = "restart_service"
    function_name = _get_affected_lambda(incident_record)
    if not function_name:
        return {
            "success": False,
            "action_key": action_key,
            "notes": "Could not resolve target Lambda function name from incident record.",
        }
    return _bump_lambda_env(function_name, action_key)


# ===========================================================================
# Action: restart_downstream_service
# ===========================================================================

def restart_downstream_service(incident_record: dict) -> dict:
    """
    Force a cold start specifically on service-c (the downstream dependency
    in the service_cascade fault class).
    """
    action_key = "restart_downstream_service"
    function_name = _find_lambda_by_prefix("ServiceC")
    if not function_name:
        return {
            "success": False,
            "action_key": action_key,
            "notes": "Could not find a Lambda function matching 'ServiceC'.",
        }
    return _bump_lambda_env(function_name, action_key)


def _bump_lambda_env(function_name: str, action_key: str) -> dict:
    """
    Shared implementation: read current env vars, set RESTART_TRIGGER to
    the current UTC ISO8601 timestamp, write back via UpdateFunctionConfiguration.
    """
    try:
        config_resp = _lambda_client.get_function_configuration(FunctionName=function_name)
        env_vars: dict = ((config_resp.get("Environment") or {}).get("Variables") or {}).copy()
        trigger_value = datetime.now(timezone.utc).isoformat()
        env_vars["RESTART_TRIGGER"] = trigger_value

        _lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={"Variables": env_vars},
        )
        logger.info(json.dumps({
            "event": "restart_applied",
            "action_key": action_key,
            "function": function_name,
            "trigger_value": trigger_value,
        }))
        return {
            "success": True,
            "action_key": action_key,
            "notes": (
                f"Bumped RESTART_TRIGGER env var on '{function_name}' to '{trigger_value}'. "
                "Existing warm Lambda execution environments will be discarded."
            ),
        }
    except ClientError as exc:
        logger.error(json.dumps({"event": "restart_error", "function": function_name, "error": str(exc)}))
        return {"success": False, "action_key": action_key, "notes": f"ClientError during restart: {exc}"}


# ===========================================================================
# Action: lock_s3_bucket
# ===========================================================================

def lock_s3_bucket(incident_record: dict) -> dict:
    """
    Apply a full public access block to the flagged S3 bucket.
    Bucket name is taken from diagnosis.affected_resources[0],
    falling back to resource_id if not present.
    """
    action_key = "lock_s3_bucket"
    resources = (incident_record.get("diagnosis") or {}).get("affected_resources") or []
    bucket_name: str = (resources[0] if resources else incident_record.get("resource_id")) or ""

    if not bucket_name:
        return {
            "success": False,
            "action_key": action_key,
            "notes": "No S3 bucket name found in diagnosis.affected_resources or resource_id.",
        }

    # Strip ARN prefix if the LLM returned arn:aws:s3:::bucket-name
    if bucket_name.startswith("arn:aws:s3:::"):
        bucket_name = bucket_name[len("arn:aws:s3:::"):]

    try:
        _s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        logger.info(json.dumps({"event": "lock_s3_applied", "bucket": bucket_name}))
        return {
            "success": True,
            "action_key": action_key,
            "notes": (
                f"Applied full public access block to S3 bucket '{bucket_name}'. "
                "BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, RestrictPublicBuckets all set to True."
            ),
        }
    except ClientError as exc:
        logger.error(json.dumps({"event": "lock_s3_error", "bucket": bucket_name, "error": str(exc)}))
        return {"success": False, "action_key": action_key, "notes": f"ClientError during lock_s3_bucket: {exc}"}


# ===========================================================================
# Action: tighten_iam_policy
# ===========================================================================

def tighten_iam_policy(incident_record: dict) -> dict:
    """
    Attach a pre-defined safe deny policy to the flagged IAM role.

    GUARDRAIL: The policy JSON is _SAFE_DENY_POLICY defined at the top of this
    module - a hardcoded constant. The LLM output is NEVER used to generate
    IAM policy JSON directly (per spec Guardrails section).

    Role name is taken from diagnosis.affected_resources[0].
    """
    action_key = "tighten_iam_policy"
    resources = (incident_record.get("diagnosis") or {}).get("affected_resources") or []
    role_name: str = (resources[0] if resources else incident_record.get("resource_id")) or ""

    if not role_name:
        return {
            "success": False,
            "action_key": action_key,
            "notes": "No IAM role name found in diagnosis.affected_resources or resource_id.",
        }

    # Strip ARN to get just the role name if the LLM returned a full ARN
    if "/" in role_name:
        role_name = role_name.split("/")[-1]

    try:
        _iam.put_role_policy(
            RoleName=role_name,
            PolicyName=_SAFE_DENY_POLICY_NAME,
            PolicyDocument=json.dumps(_SAFE_DENY_POLICY),
        )
        logger.info(json.dumps({
            "event": "tighten_iam_applied",
            "role": role_name,
            "policy": _SAFE_DENY_POLICY_NAME,
        }))
        return {
            "success": True,
            "action_key": action_key,
            "notes": (
                f"Attached pre-defined deny policy '{_SAFE_DENY_POLICY_NAME}' to IAM role '{role_name}'. "
                "Policy denies iam:*, organizations:*, account:* actions on all resources. "
                "Policy JSON was NOT generated from LLM output."
            ),
        }
    except ClientError as exc:
        logger.error(json.dumps({"event": "tighten_iam_error", "role": role_name, "error": str(exc)}))
        return {"success": False, "action_key": action_key, "notes": f"ClientError during tighten_iam_policy: {exc}"}


# ===========================================================================
# Action: manual_review_required
# ===========================================================================

def manual_review_required(incident_record: dict) -> dict:
    """
    No automated action. The LLM determined manual review is needed.
    Returns success=True because 'no action' is the correct action here.
    """
    incident_id = incident_record.get("incident_id", "unknown")
    logger.info(json.dumps({"event": "manual_review_flagged", "incident_id": incident_id}))
    return {
        "success": True,
        "action_key": "manual_review_required",
        "notes": (
            f"Incident '{incident_id}' flagged for manual review. "
            "The LLM diagnosis indicated automated remediation is not safe or applicable. "
            "No automated action was taken."
        ),
    }
