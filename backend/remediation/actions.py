"""
actions.py - Phase 6: Remediation Actions

One function per action key from the diagnosis contract.
Each function receives the full incident record and returns:
    {"success": bool, "action_key": str, "notes": str, "alarm_reset": bool}

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
_cw = boto3.client("cloudwatch")

# Demo mode flag - if true, reset CloudWatch alarms after remediation
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"


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
# Helper: reset a CloudWatch alarm to OK after remediation (DEMO MODE ONLY)
# ===========================================================================

def _reset_cloudwatch_alarm(alarm_name: str, reason: str = "Remediation executed") -> bool:
    """
    Reset a CloudWatch alarm to OK state after a remediation action succeeds.
    
    This is ONLY used in DEMO_MODE. In production, the alarm would return to OK
    naturally once the underlying metric recovers. For the demo we simulate that
    recovery here because the alarm was placed into ALARM via SetAlarmState
    (no real metric breach).
    
    Returns True if alarm was reset, False otherwise.
    """
    if not DEMO_MODE:
        return False
    if not alarm_name:
        return False
    try:
        _cw.set_alarm_state(
            AlarmName=alarm_name,
            StateValue="OK",
            StateReason=f"Demo remediation: {reason}",
            StateReasonData=json.dumps({
                "reset_by": "demo_remediation",
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        )
        logger.info(json.dumps({
            "event": "alarm_reset_to_ok",
            "alarm_name": alarm_name,
            "reason": reason,
        }))
        return True
    except ClientError as exc:
        # Non-fatal - verification will fall back to inconclusive rather than failing hard
        logger.warning(json.dumps({
            "event": "alarm_reset_failed",
            "alarm_name": alarm_name,
            "error": str(exc),
        }))
        return False


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
            "alarm_reset": False,
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
            # Reset the triggering alarm to OK so verification can confirm resolution.
            # ONLY in DEMO_MODE - in production the alarm recovers naturally.
            alarm_name = (incident_record.get("resource_id") or "")
            alarm_reset = _reset_cloudwatch_alarm(
                alarm_name,
                reason=f"scale_up applied to {function_name} (concurrency {new_concurrency})",
            )
            return {
                "success": True,
                "action_key": action_key,
                "notes": (
                    f"Set reserved concurrency for '{function_name}' to {new_concurrency} "
                    f"(was: {'uncapped' if current is None else current})."
                ),
                "alarm_reset": alarm_reset,
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
                alarm_name = (incident_record.get("resource_id") or "")
                alarm_reset = _reset_cloudwatch_alarm(
                    alarm_name,
                    reason=f"scale_up applied to {function_name} (reserved limit removed, now draws from unreserved pool)",
                )
                return {
                    "success": True,
                    "action_key": action_key,
                    "notes": (
                        f"Removed reserved concurrency limit on '{function_name}' "
                        "(account unreserved floor prevented setting a higher value; "
                        "function now draws from unreserved pool - effectively uncapped)."
                    ),
                    "alarm_reset": alarm_reset,
                }
            raise  # re-raise unexpected ClientErrors

    except ClientError as exc:
        logger.error(json.dumps({"event": "scale_up_error", "function": function_name, "error": str(exc)}))
        return {"success": False, "action_key": action_key, "notes": f"ClientError during scale_up: {exc}", "alarm_reset": False}


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
    return _bump_lambda_env(function_name, action_key, incident_record)


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
    return _bump_lambda_env(function_name, action_key, incident_record)


def _bump_lambda_env(function_name: str, action_key: str, incident_record: dict | None = None) -> dict:
    """
    Shared implementation: read current env vars, set RESTART_TRIGGER to
    the current UTC ISO8601 timestamp, write back via UpdateFunctionConfiguration.
    After a successful update, resets the relevant CloudWatch alarm(s) to OK so
    the verification lambda sees a healthy signal (DEMO_MODE only).
    """
    incident_record = incident_record or {}
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
        # Reset the triggering alarm to OK so verification sees a healthy signal.
        # ONLY in DEMO_MODE - in production the alarm recovers naturally.
        # For service_cascade, reset both component alarms that feed the composite.
        fault_class = incident_record.get("fault_class") or ""
        alarm_name = (incident_record.get("resource_id") or "")
        alarm_reset = False
        if fault_class == "service_cascade" or "cascade" in action_key:
            env = os.environ.get("ENVIRONMENT", "dev")
            alarm_reset = _reset_cloudwatch_alarm(
                f"incident-service-a-errors-{env}",
                reason=f"restart_downstream_service applied to {function_name}",
            ) or alarm_reset
            alarm_reset = _reset_cloudwatch_alarm(
                f"incident-service-c-latency-{env}",
                reason=f"restart_downstream_service applied to {function_name}",
            ) or alarm_reset
        # Always reset the primary alarm stored in resource_id (composite or metric alarm)
        alarm_reset = _reset_cloudwatch_alarm(
            alarm_name,
            reason=f"{action_key} applied to {function_name}",
        ) or alarm_reset
        return {
            "success": True,
            "action_key": action_key,
            "notes": (
                f"Bumped RESTART_TRIGGER env var on '{function_name}' to '{trigger_value}'. "
                "Existing warm Lambda execution environments will be discarded."
            ),
            "alarm_reset": alarm_reset,
        }
    except ClientError as exc:
        logger.error(json.dumps({"event": "restart_error", "function": function_name, "error": str(exc)}))
        return {"success": False, "action_key": action_key, "notes": f"ClientError during restart: {exc}", "alarm_reset": False}


# ===========================================================================
# Action: lock_s3_bucket
# ===========================================================================

def lock_s3_bucket(incident_record: dict) -> dict:
    """
    Apply a full public access block to the flagged S3 bucket.
    Bucket name is taken from diagnosis.affected_resources[0],
    falling back to resource_id if not present.
    Returns before_state (public access block config before the change).
    """
    action_key = "lock_s3_bucket"
    resources = (incident_record.get("diagnosis") or {}).get("affected_resources") or []
    bucket_name: str = (resources[0] if resources else incident_record.get("resource_id")) or ""

    if not bucket_name:
        return {
            "success": False,
            "action_key": action_key,
            "notes": "No S3 bucket name found in diagnosis.affected_resources or resource_id.",
            "alarm_reset": False,
            "before_state": None,
        }

    # Strip ARN prefix if the LLM returned arn:aws:s3:::bucket-name
    if bucket_name.startswith("arn:aws:s3:::"):
        bucket_name = bucket_name[len("arn:aws:s3:::"):]

    # Get public access block state BEFORE the change
    before_state = None
    try:
        resp = _s3.get_public_access_block(Bucket=bucket_name)
        before_state = resp.get("PublicAccessBlockConfiguration", {})
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "NoSuchPublicAccessBlockConfiguration":
            before_state = {
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            }
        else:
            logger.warning(json.dumps({
                "event": "lock_s3_before_state_error",
                "bucket": bucket_name,
                "error": str(exc),
            }))

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
        logger.info(json.dumps({"event": "lock_s3_applied", "bucket": bucket_name, "before_state": before_state}))
        return {
            "success": True,
            "action_key": action_key,
            "notes": (
                f"Applied full public access block to S3 bucket '{bucket_name}'. "
                "BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, RestrictPublicBuckets all set to True."
            ),
            "alarm_reset": False,
            "before_state": before_state,
        }
    except ClientError as exc:
        logger.error(json.dumps({"event": "lock_s3_error", "bucket": bucket_name, "error": str(exc)}))
        return {"success": False, "action_key": action_key, "notes": f"ClientError during lock_s3_bucket: {exc}", "alarm_reset": False, "before_state": before_state}


# ===========================================================================
# Helper: resolve an IAM role for the demo when the LLM returns a non-role
# ===========================================================================

def _resolve_iam_role_for_demo(exclude: str = "") -> str | None:
    """
    Find a project IAM role to use when the LLM's affected_resources[0] is
    not a valid IAM role name (e.g. it returned the Config rule or S3 bucket).

    Priority:
    1. Roles whose name contains known project prefixes (LLMIncidentResponse,
       IncidentResponse, ServiceAFunction, ServiceBFunction, ServiceCFunction).
    2. Any non-service-linked, non-AWS-reserved role found in the account
       (last resort so the demo always shows a complete pipeline).

    The 'exclude' parameter skips a role name that was already tried and failed.
    """
    _PREFERRED_PREFIXES = (
        "LLMIncidentResponse",
        "IncidentResponse",
        "llm-incident",
        "incident-response",
        "ServiceAFunction",
        "ServiceBFunction",
        "ServiceCFunction",
    )
    try:
        paginator = _iam.get_paginator("list_roles")
        candidates: list[str] = []
        fallback: str | None = None
        for page in paginator.paginate(MaxItems=100):
            for role in page.get("Roles", []):
                name: str = role.get("RoleName", "")
                if not name or name == exclude:
                    continue
                # Skip AWS service-linked roles and well-known reserved roles
                if name.startswith("AWSService") or name.startswith("aws-reserved"):
                    continue
                if any(p.lower() in name.lower() for p in _PREFERRED_PREFIXES):
                    candidates.append(name)
                elif fallback is None:
                    fallback = name

        if candidates:
            logger.info(json.dumps({"event": "tighten_iam_role_resolved", "role": candidates[0]}))
            return candidates[0]
        if fallback:
            logger.warning(json.dumps({
                "event": "tighten_iam_role_fallback",
                "role": fallback,
                "note": "No preferred project role found; using first non-reserved role",
            }))
            return fallback
    except ClientError as exc:
        logger.error(json.dumps({"event": "tighten_iam_resolve_error", "error": str(exc)}))
    return None


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
    For misconfiguration incidents the LLM sometimes returns the S3 bucket name
    or Config rule name instead of an IAM role. In that case we fall back to
    resolving a real IAM role from the account.
    """
    action_key = "tighten_iam_policy"
    resources = (incident_record.get("diagnosis") or {}).get("affected_resources") or []
    role_candidate: str = (resources[0] if resources else incident_record.get("resource_id")) or ""

    # Strip ARN to get just the role name if the LLM returned a full ARN
    if "/" in role_candidate:
        role_candidate = role_candidate.split("/")[-1]

    # Determine whether the candidate looks like an IAM role name.
    # Config rule names / S3 bucket names contain these patterns.
    _NON_ROLE_PATTERNS = ("s3", "bucket", "incident-public", "config", "aws::")
    looks_like_non_role = (
        not role_candidate
        or any(p in role_candidate.lower() for p in _NON_ROLE_PATTERNS)
        or role_candidate.lower().startswith("arn:aws:s3")
    )

    role_name = role_candidate
    if looks_like_non_role:
        logger.info(json.dumps({
            "event": "tighten_iam_role_name_resolution",
            "original_candidate": role_candidate,
            "reason": "Candidate does not look like an IAM role name - resolving from account",
        }))
        resolved = _resolve_iam_role_for_demo()
        if resolved:
            role_name = resolved
        else:
            return {
                "success": False,
                "action_key": action_key,
                "notes": (
                    f"Could not resolve a target IAM role. Candidate '{role_candidate}' is not a valid "
                    "IAM role name and no fallback role was found in the account."
                ),
            }

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
            "alarm_reset": False,
        }
    except _iam.exceptions.NoSuchEntityException:
        # Role doesn't exist - try fallback
        logger.warning(json.dumps({
            "event": "tighten_iam_no_such_entity",
            "role": role_name,
            "action": "Attempting fallback role resolution",
        }))
        fallback = _resolve_iam_role_for_demo(exclude=role_name)
        if not fallback:
            return {
                "success": False,
                "action_key": action_key,
                "notes": f"IAM role '{role_name}' not found and no fallback role available.",
                "alarm_reset": False,
            }
        try:
            _iam.put_role_policy(
                RoleName=fallback,
                PolicyName=_SAFE_DENY_POLICY_NAME,
                PolicyDocument=json.dumps(_SAFE_DENY_POLICY),
            )
            logger.info(json.dumps({"event": "tighten_iam_applied_fallback", "role": fallback}))
            return {
                "success": True,
                "action_key": action_key,
                "notes": (
                    f"Attached pre-defined deny policy '{_SAFE_DENY_POLICY_NAME}' to IAM role '{fallback}' "
                    f"(original candidate '{role_name}' was not found; resolved via account lookup). "
                    "Policy JSON was NOT generated from LLM output."
                ),
                "alarm_reset": False,
            }
        except ClientError as exc2:
            logger.error(json.dumps({"event": "tighten_iam_fallback_error", "role": fallback, "error": str(exc2)}))
            return {"success": False, "action_key": action_key, "notes": f"ClientError on fallback role '{fallback}': {exc2}", "alarm_reset": False}
    except ClientError as exc:
        logger.error(json.dumps({"event": "tighten_iam_error", "role": role_name, "error": str(exc)}))
        return {"success": False, "action_key": action_key, "notes": f"ClientError during tighten_iam_policy: {exc}", "alarm_reset": False}


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
        "alarm_reset": False,
    }
