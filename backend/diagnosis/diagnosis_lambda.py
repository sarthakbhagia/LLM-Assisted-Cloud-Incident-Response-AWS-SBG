"""
app.py - Phase 4: Diagnosis Lambda Handler

Receives incident payload from collector, reads raw_data.json from S3,
loads runbook context (unless used_rag=false ablation flag is set),
invokes Amazon Bedrock (primary: Nova Pro, fallback chain: Llama 3 70B ->
Mistral Large -> Nova Micro), validates JSON diagnosis, updates DynamoDB,
and invokes notify Lambda.
"""

from __future__ import annotations

import json
import logging
import os
import re
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

try:
    from prompts import SYSTEM_PROMPT, VALID_SUGGESTED_ACTIONS, build_diagnosis_prompt, build_error_correction_prompt
    from runbook_loader import load_runbook
except ImportError:
    from .prompts import SYSTEM_PROMPT, VALID_SUGGESTED_ACTIONS, build_diagnosis_prompt, build_error_correction_prompt
    from .runbook_loader import load_runbook


logger = logging.getLogger()
logger.setLevel(logging.INFO)

logger.info("=== MODULE LOADED: diagnosis/app.py v2024-09-16-FALLBACK-CHAIN ===")

# AWS Clients
_s3 = boto3.client("s3")
_dynamodb = boto3.resource("dynamodb")
_bedrock = boto3.client("bedrock-runtime")
_lambda = boto3.client("lambda")

# Config from environment
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "")
DATA_LAKE_BUCKET = os.environ.get("DATA_LAKE_BUCKET", "")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "apac.amazon.nova-pro-v1:0"
)
FALLBACK_MODEL_ID = "meta.llama3-70b-instruct-v1:0"
SECOND_FALLBACK_MODEL_ID = "mistral.mistral-large-2402-v1:0"
NOVA_FALLBACK_MODEL_ID = "apac.amazon.nova-micro-v1:0"
NOTIFY_FUNCTION_NAME = os.environ.get("NOTIFY_FUNCTION_NAME", "")

# Increased max tokens for models to reduce truncation
MAX_TOKENS = 2048


NOVA_SYSTEM_PROMPT = """You are an AWS incident diagnosis expert. Output ONLY a raw JSON object with these EXACT fields:
- root_cause: string
- confidence: number (0.0 to 1.0, e.g., 0.85)
- affected_resources: array of strings (resource names only)
- suggested_action: MUST be exactly one of: scale_up, restart_service, lock_s3_bucket, tighten_iam_policy, restart_downstream_service, manual_review_required
- explanation: string
- reasoning_trace: string (NOT an array)

Rules:
- NO markdown code fences (no ```json or ```)
- NO extra text before or after the JSON
- NO comments
- confidence must be a NUMBER not a string
- reasoning_trace must be a STRING not an array
- suggested_action must match one of the 6 exact values above
- Output must be complete and valid JSON — do not truncate."""

LLAMA_SYSTEM_PROMPT = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{SYSTEM_PROMPT}

{NOVA_SYSTEM_PROMPT}
<|eot_id|><|start_header_id|>user<|end_header_id|>

__PROMPT__<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

MISTRAL_SYSTEM_PROMPT = f"""<s>[INST] {SYSTEM_PROMPT}

{NOVA_SYSTEM_PROMPT} [/INST]
__PROMPT__"""


def lambda_handler(event, context):
    logger.info(json.dumps({"event": "diagnosis_triggered", "payload": event}))

    incident_id = event.get("incident_id")
    fault_class = event.get("fault_class", "unknown")
    s3_key = event.get("raw_data_s3_key") or f"incidents/{incident_id}/raw_data.json"
    used_rag = event.get("used_rag", True)

    if not incident_id or not DATA_LAKE_BUCKET:
        logger.error("Missing incident_id or DATA_LAKE_BUCKET")
        return {"statusCode": 400, "body": "Missing required parameters"}

    # 1. Fetch raw evidence from S3 - raises RuntimeError if S3 is unreachable or key
    #    is missing, so we cannot silently diagnose from an empty evidence blob (SE-1).
    try:
        raw_data = _fetch_s3_raw_data(s3_key)
    except RuntimeError as exc:
        # Write an explicit error status to DynamoDB so the operator can see this
        # incident was never diagnosed due to evidence fetch failure.
        _update_dynamodb_diagnosis(
            incident_id,
            {
                "root_cause": "Evidence fetch failed - cannot diagnose",
                "confidence": 0.0,
                "affected_resources": [],
                "suggested_action": "manual_review_required",
                "explanation": str(exc),
                "reasoning_trace": "Diagnosis aborted: S3 evidence bundle could not be read.",
                "diagnosis_status": "evidence_fetch_failed",
                "is_heuristic": True,
            },
            used_rag,
            f"evidence_fetch_failed: {exc}",
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc), "incident_id": incident_id}),
        }

    # 2. Load runbook context (if RAG enabled)
    runbook_text = None
    if used_rag:
        runbook_text = load_runbook(fault_class)

    # 3. Construct prompt
    user_prompt = build_diagnosis_prompt(raw_data, runbook_text)

    # 4. Invoke Bedrock LLM with JSON validation & 1-retry fallback
    diagnosis_output, failure_mode = _invoke_llm_with_validation(
        user_prompt=user_prompt,
        fault_class=fault_class,
        raw_data=raw_data,
        incident_id=incident_id,
    )

    # 5. Update DynamoDB IncidentRecord
    _update_dynamodb_diagnosis(incident_id, diagnosis_output, used_rag, failure_mode)

    # 6. Invoke Notify Lambda - writes notify_failed flag to DynamoDB on failure (SE-14)
    _invoke_notify(incident_id, diagnosis_output)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "incident_id": incident_id,
            "diagnosis": diagnosis_output,
            "used_rag": used_rag,
            "failure_mode": failure_mode,
        }),
    }


def _fetch_s3_raw_data(s3_key: str) -> dict:
    """
    Fetch raw evidence JSON from S3. Raises RuntimeError on any failure so the
    caller cannot silently continue on an empty evidence dict and produce a
    high-confidence heuristic diagnosis from zero data (SE-1).
    """
    try:
        resp = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=s3_key)
        content = resp["Body"].read().decode("utf-8")
        return json.loads(content)
    except Exception as exc:  # noqa: BLE001
        logger.error(json.dumps({
            "event": "s3_evidence_fetch_failed",
            "s3_key": s3_key,
            "error": str(exc),
            "ATTENTION": "Cannot run diagnosis without evidence - raising so the incident record gets an explicit error status",
        }))
        raise RuntimeError(f"Evidence fetch failed for key={s3_key!r}: {exc}") from exc


def _invoke_llm_with_validation(
    user_prompt: str,
    fault_class: str,
    raw_data: dict,
    incident_id: str | None = None,
) -> tuple[dict, str | None]:
    """Call Bedrock LLM, parse & validate JSON diagnosis, retry once if malformed.
    
    On final parse failure, stores raw response in S3 and returns parse_failed diagnosis.
    """
    raw_response = None
    failure_mode = None
    model_used = None

    def _save_raw_response_to_s3(response_text: str, error_type: str) -> str | None:
        """Save raw LLM response to S3 for debugging. Returns S3 key or None on failure."""
        if not incident_id or not DATA_LAKE_BUCKET:
            return None
        try:
            s3_key = f"incidents/{incident_id}/llm_raw_response_{error_type}.json"
            _s3.put_object(
                Bucket=DATA_LAKE_BUCKET,
                Key=s3_key,
                Body=json.dumps({
                    "incident_id": incident_id,
                    "error_type": error_type,
                    "raw_response": response_text,
                    "prompt_length": len(user_prompt),
                }, indent=2, default=str),
                ContentType="application/json",
            )
            logger.info(f"Saved raw LLM response to S3: {s3_key}")
            return s3_key
        except Exception as e:
            logger.error(f"Failed to save raw response to S3: {e}")
            return None

    def _attempt_llm_call(prompt: str, attempt_name: str) -> tuple[str | None, str | None, str | None, str | None]:
        """Attempt LLM call and validation. Returns (validated_diag, raw_response, failure_mode, model_used)."""
        raw_resp = None
        try:
            raw_resp, stop_reason, is_truncated, model_name = _call_bedrock(prompt)
            logger.info(f"{attempt_name} LLM response (first 500 chars): {str(raw_resp)[:500]}, stop_reason: {stop_reason}, truncated: {is_truncated}, model: {model_name}")
            
            if is_truncated:
                failure = f"{attempt_name.lower()}_truncated: stop_reason={stop_reason}"
                s3_key = _save_raw_response_to_s3(str(raw_resp), f"{attempt_name.lower()}_truncated")
                if s3_key:
                    failure += f"; raw_saved_to_s3:{s3_key}"
                return None, raw_resp, failure, model_name
            
            validated_diag = _parse_and_validate_json(raw_resp)
            return validated_diag, raw_resp, None, model_name
        except ValueError as exc:
            failure = None
            if "truncated" in str(exc).lower():
                failure = f"{attempt_name.lower()}_truncated: {exc}"
                s3_key = _save_raw_response_to_s3(str(raw_resp), f"{attempt_name.lower()}_truncated")
                if s3_key:
                    failure += f"; raw_saved_to_s3:{s3_key}"
            else:
                # Traceability fix: save raw response on validation errors too.
                # Previously only truncation saved the raw response, so when the LLM
                # returned bad JSON or the wrong suggested_action value, there was no
                # way to see what it actually returned. Now the raw text is always saved.
                failure = f"{attempt_name.lower()}_validation_error: {exc}"
                s3_key = _save_raw_response_to_s3(str(raw_resp), f"{attempt_name.lower()}_validation_error")
                if s3_key:
                    failure += f"; raw_saved_to_s3:{s3_key}"
            return None, raw_resp, failure, model_name if 'model_name' in locals() else None
        except Exception as exc:  # noqa: BLE001
            return None, raw_resp, f"{attempt_name.lower()}_error: {exc}", model_name if 'model_name' in locals() else None

    # Attempt 1: Initial call
    validated_diag, raw_response, failure_mode, model_used = _attempt_llm_call(user_prompt, "Initial")
    if validated_diag is not None:
        validated_diag["model_used"] = model_used
        return validated_diag, None

    # Attempt 2: Retry with correction prompt (if we got a raw response)
    if raw_response:
        correction_prompt = build_error_correction_prompt(raw_response, failure_mode or "unknown error")
        validated_diag, second_response, retry_failure, retry_model = _attempt_llm_call(correction_prompt, "Retry")
        if validated_diag is not None:
            validated_diag["model_used"] = retry_model or model_used
            return validated_diag, "retry_succeeded"
        if retry_failure:
            failure_mode = retry_failure
            # Save retry raw response if different from initial
            if second_response and second_response != raw_response:
                s3_key = _save_raw_response_to_s3(str(second_response), "retry_" + failure_mode.split(":")[0])
                if s3_key:
                    failure_mode += f"; raw_saved_to_s3:{s3_key}"

    # Fallback heuristic diagnosis if Bedrock is unreachable / unconfigured / parse failed
    fallback_diag = _generate_fallback_diagnosis(fault_class, raw_data)
    fallback_diag["diagnosis_status"] = "parse_failed"
    fallback_diag["model_used"] = "heuristic"
    return fallback_diag, failure_mode or "fallback_heuristic_used"


def _call_bedrock(prompt: str) -> tuple[str, str | None, bool, str]:
    """Invoke Bedrock model with fallback chain: Nova Pro -> Llama 3 70B -> Mistral Large -> Nova Micro.
    
    Returns (text, stop_reason, is_truncated, model_name).
    """
    logger.info(f"_call_bedrock invoked with prompt length: {len(prompt)}")
    logger.info("_call_bedrock: Starting execution")

    nova_payload = {
        "system": [{"text": NOVA_SYSTEM_PROMPT}],
        "messages": [
            {"role": "user", "content": [{"text": prompt}]}
        ],
        "inferenceConfig": {"maxTokens": MAX_TOKENS, "temperature": 0.1},
    }

    llama_payload = {
        # Use .replace() not .format() — SYSTEM_PROMPT contains literal JSON braces
        # which would be misinterpreted as format placeholders and raise KeyError.
        "prompt": LLAMA_SYSTEM_PROMPT.replace("__PROMPT__", prompt),
        "max_gen_len": MAX_TOKENS,
        "temperature": 0.1,
    }

    mistral_payload = {
        # Use .replace() not .format() — same reason as llama_payload above.
        "prompt": MISTRAL_SYSTEM_PROMPT.replace("__PROMPT__", prompt),
        "max_tokens": MAX_TOKENS,
        "temperature": 0.1,
    }

    def _invoke_nova(model_id: str) -> tuple[str, str | None]:
        """Invoke Nova model and return (text, stop_reason)."""
        logger.info(f"Invoking Nova model: {model_id}")
        try:
            response = _bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps(nova_payload),
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read().decode("utf-8"))
            logger.info(f"Nova response body keys: {list(response_body.keys())}")
            output = response_body.get("output", {})
            logger.info(f"Nova output keys: {list(output.keys()) if output else 'None'}")
            stop_reason = output.get("stopReason")
            logger.info(f"Nova stopReason: {stop_reason}")
            message = output.get("message", {})
            logger.info(f"Nova message keys: {list(message.keys()) if message else 'None'}")
            content = message.get("content", [])
            logger.info(f"Nova content: {content}")
            if content and isinstance(content, list):
                text = content[0].get("text", "")
                logger.info(f"Nova text (first 200): {text[:200]}")
                return text, stop_reason
            logger.warning(f"Nova unexpected response format: {response_body}")
            return str(response_body), stop_reason
        except Exception as e:
            logger.error(f"Nova invocation failed with {type(e).__name__}: {e}")
            raise

    def _invoke_llama(model_id: str) -> tuple[str, str | None]:
        """Invoke Llama model and return (text, stop_reason)."""
        logger.info(f"Invoking Llama model: {model_id}")
        try:
            response = _bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps(llama_payload),
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read().decode("utf-8"))
            stop_reason = response_body.get("stop_reason")
            logger.info(f"Llama stop_reason: {stop_reason}")
            return response_body.get("generation", ""), stop_reason
        except Exception as e:
            logger.error(f"Llama invocation failed with {type(e).__name__}: {e}")
            raise

    def _invoke_mistral(model_id: str) -> tuple[str, str | None]:
        """Invoke Mistral model and return (text, stop_reason)."""
        logger.info(f"Invoking Mistral model: {model_id}")
        try:
            response = _bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps(mistral_payload),
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read().decode("utf-8"))
            outputs = response_body.get("outputs", [])
            stop_reason = None
            if outputs and isinstance(outputs, list):
                stop_reason = outputs[0].get("stop_reason")
            logger.info(f"Mistral stop_reason: {stop_reason}")
            if outputs and isinstance(outputs, list):
                return outputs[0].get("text", ""), stop_reason
            return str(response_body), stop_reason
        except Exception as e:
            logger.error(f"Mistral invocation failed with {type(e).__name__}: {e}")
            raise

    def _try_model(model_id: str, invoke_fn, model_name: str, next_model: str | None = None) -> tuple[str, str | None]:
        logger.info(f"_try_model called for {model_name}")
        try:
            logger.info(f"Trying model: {model_name} ({model_id})")
            result, stop_reason = invoke_fn(model_id)
            logger.info(f"Model {model_name} returned: {type(result)}, stop_reason: {stop_reason}")
            return result, stop_reason
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "AccessDeniedException" and "INVALID_PAYMENT_INSTRUMENT" in str(exc):
                msg = f"Model {model_id} ({model_name}) blocked by payment issue"
            else:
                msg = f"Model {model_id} ({model_name}) failed: {exc}"
            if next_model:
                logger.warning(f"{msg}. Trying {next_model}...")
            else:
                logger.error(f"{msg}. No more fallbacks.")
            raise
        except Exception as e:
            logger.error(f"Model {model_name} ({model_id}) raised {type(e).__name__}: {e}")
            raise

    logger.info("All inner functions defined successfully")
    logger.info("Starting model fallback chain")
    logger.info("About to try Nova Pro")
    # SE-7: Each leg catches Exception (not just ClientError) so non-boto errors
    # (e.g. KeyError parsing the response body) also fall through to the next model.
    # SE-4: Llama uses "stop" as its normal completion signal (not truncation).
    #       Only "max_tokens" and "length" mean the output was cut short for Llama.
    try:
        logger.info("Attempt 1: Nova Pro")
        result, stop_reason = _try_model(BEDROCK_MODEL_ID, _invoke_nova, "Nova Pro", FALLBACK_MODEL_ID)
        logger.info(f"Nova Pro attempt returned: {result[:100] if result else 'None'}, stop_reason: {stop_reason}")
        is_truncated = stop_reason in ("max_tokens", "length")
        if is_truncated:
            logger.warning(f"Nova Pro output truncated (stop_reason={stop_reason})")
        return result, stop_reason, is_truncated, "Nova Pro"
    except Exception as e:  # SE-7: catch all, not just ClientError
        logger.warning(f"Nova Pro failed ({type(e).__name__}): {e}")

    try:
        logger.info("Attempt 2: Llama 3 70B")
        result, stop_reason = _try_model(FALLBACK_MODEL_ID, _invoke_llama, "Llama 3 70B", SECOND_FALLBACK_MODEL_ID)
        logger.info(f"Llama attempt returned: {result[:100] if result else 'None'}, stop_reason: {stop_reason}")
        # SE-4: "stop" is Llama's normal EOS token - not a truncation signal.
        is_truncated = stop_reason in ("max_tokens", "length")
        if is_truncated:
            logger.warning(f"Llama output truncated (stop_reason={stop_reason})")
        return result, stop_reason, is_truncated, "Llama 3 70B"
    except Exception as e:  # SE-7
        logger.warning(f"Llama failed ({type(e).__name__}): {e}")

    try:
        logger.info("Attempt 3: Mistral Large")
        result, stop_reason = _try_model(SECOND_FALLBACK_MODEL_ID, _invoke_mistral, "Mistral Large", NOVA_FALLBACK_MODEL_ID)
        logger.info(f"Mistral attempt returned: {result[:100] if result else 'None'}, stop_reason: {stop_reason}")
        is_truncated = stop_reason in ("max_tokens", "length")
        if is_truncated:
            logger.warning(f"Mistral output truncated (stop_reason={stop_reason})")
        return result, stop_reason, is_truncated, "Mistral Large"
    except Exception as e:  # SE-7
        logger.warning(f"Mistral failed ({type(e).__name__}): {e}")

    try:
        logger.info("Attempt 4: Nova Micro")
        result, stop_reason = _try_model(NOVA_FALLBACK_MODEL_ID, _invoke_nova, "Nova Micro", None)
        logger.info(f"Nova Micro attempt returned: {result[:100] if result else 'None'}, stop_reason: {stop_reason}")
        is_truncated = stop_reason in ("max_tokens", "length")
        if is_truncated:
            logger.warning(f"Nova Micro output truncated (stop_reason={stop_reason})")
        return result, stop_reason, is_truncated, "Nova Micro"
    except Exception as final_exc:
        logger.error(f"All models failed: {final_exc}")
        raise RuntimeError("All Bedrock models failed")


def _parse_and_validate_json(raw_text: str) -> dict:
    """Extract and validate JSON against the diagnosis contract."""
    clean_text = raw_text.strip()
    # Strip markdown fence if present
    if "```" in clean_text:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
        if match:
            clean_text = match.group(1)
        else:
            clean_text = clean_text.replace("```json", "").replace("```", "").strip()

    # Extract bare JSON object when the LLM emits preamble text before the '{'
    # (e.g. Nova Pro sometimes outputs '\n "root_cause"' or a sentence before the JSON).
    # This fires even without markdown fences, so it covers the common case where
    # json.loads would otherwise raise JSONDecodeError on the leading noise.
    if not clean_text.startswith('{'):
        start = clean_text.find('{')
        end = clean_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            clean_text = clean_text[start:end + 1]

    data = json.loads(clean_text)

    # Normalize keys: the LLM sometimes emits keys with leading/trailing
    # whitespace or newlines (e.g. '\n  "root_cause"'). Strip them all so
    # downstream .get() lookups work correctly.
    if isinstance(data, dict):
        data = {k.strip(): v for k, v in data.items()}

    # Validate mandatory fields
    if not isinstance(data, dict):
        raise ValueError("Response is not a JSON object")

    root_cause = data.get("root_cause")
    confidence = data.get("confidence")
    affected_resources = data.get("affected_resources")
    suggested_action = data.get("suggested_action")
    explanation = data.get("explanation")
    reasoning_trace = data.get("reasoning_trace")

    if not root_cause or not isinstance(root_cause, str):
        raise ValueError("Missing or invalid 'root_cause'")

    # Normalize confidence: handle string values like "High", "Medium", "Low"
    if isinstance(confidence, str):
        confidence_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
        confidence = confidence_map.get(confidence.lower(), 0.5)
    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
        raise ValueError("Field 'confidence' must be float between 0.0 and 1.0")

    if not isinstance(affected_resources, list):
        raise ValueError("Field 'affected_resources' must be a list")

    # Normalize reasoning_trace: convert array to string if needed
    if isinstance(reasoning_trace, list):
        reasoning_trace = " ".join(str(item) for item in reasoning_trace)

    # Map suggested_action to valid values
    action_mapping = {
        # Canonical values pass through as-is (LLM already used the right token)
        "scale_up": "scale_up",
        "restart_service": "restart_service",
        "lock_s3_bucket": "lock_s3_bucket",
        "tighten_iam_policy": "tighten_iam_policy",
        "restart_downstream_service": "restart_downstream_service",
        "manual_review_required": "manual_review_required",
        # Human-phrase aliases the LLM sometimes emits
        "increase instance type": "scale_up",
        "scale out": "scale_up",
        "scale up": "scale_up",
        "add instances": "scale_up",
        "increase concurrency": "scale_up",
        "increase memory": "scale_up",
        "adjust memory": "scale_up",
        "restart": "restart_service",
        "restart service": "restart_service",
        "terminate processes": "restart_service",
        "force cold start": "restart_service",
        "redeploy": "restart_service",
        "lock bucket": "lock_s3_bucket",
        "block public access": "lock_s3_bucket",
        "s3 public access": "lock_s3_bucket",
        "tighten policy": "tighten_iam_policy",
        "restrict permissions": "tighten_iam_policy",
        "update iam": "tighten_iam_policy",
        "iam policy": "tighten_iam_policy",
        "restrict iam": "tighten_iam_policy",
        "restart downstream": "restart_downstream_service",
        "restart service c": "restart_downstream_service",
        "restart service b": "restart_downstream_service",
        "manual review": "manual_review_required",
        "investigate manually": "manual_review_required",
        "escalate": "manual_review_required",
        "human review": "manual_review_required",
    }
    if suggested_action:
        suggested_action_lower = suggested_action.lower().strip()
        for key, valid_action in action_mapping.items():
            if key in suggested_action_lower:
                suggested_action = valid_action
                break

    if suggested_action not in VALID_SUGGESTED_ACTIONS:
        raise ValueError(
            f"Invalid 'suggested_action' {suggested_action!r}. Must be one of {VALID_SUGGESTED_ACTIONS}"
        )

    # explanation and reasoning_trace are display-only fields - they do NOT need to be
    # non-empty to accept the diagnosis. Raising ValueError here caused every LLM call
    # where Nova returned a valid JSON but with a short/empty trace to fall back to the
    # heuristic at 85% confidence, which is far worse than showing an empty trace.
    if not explanation or not isinstance(explanation, str):
        explanation = "(no explanation provided by model)"

    if not reasoning_trace or not isinstance(reasoning_trace, str):
        reasoning_trace = "(no reasoning trace provided by model)"

    return {
        "root_cause": root_cause,
        "confidence": float(confidence),
        "affected_resources": [str(r) for r in affected_resources],
        "suggested_action": suggested_action,
        "explanation": explanation,
        "reasoning_trace": reasoning_trace,
    }


def _generate_fallback_diagnosis(fault_class: str, raw_data: dict) -> dict:
    """
    Generate heuristic fallback diagnosis when Bedrock is unavailable or all models
    failed / produced un-parseable output.

    SE-2: Confidence is set to 0.30 (low) instead of 0.85-0.90. A heuristic that has
    not seen any evidence should never show a high-confidence bar in the UI. The
    is_heuristic flag is set to True so the UI can display a clear banner.
    """
    evidence = raw_data.get("evidence", {})
    resource_id = raw_data.get("detection_event", {}).get("resource_id", "unknown-resource")

    # SE-2: Low confidence for all heuristic paths - these are pattern-matched guesses,
    # not evidence-based conclusions.
    HEURISTIC_CONFIDENCE = 0.30

    if fault_class == "resource_exhaustion":
        return {
            "root_cause": "Lambda execution duration exceeded threshold under memory/compute exhaustion pressure",
            "confidence": HEURISTIC_CONFIDENCE,
            "affected_resources": [evidence.get("function_name") or resource_id],
            "suggested_action": "scale_up",
            "explanation": "Service A experienced high duration causing timeout alarms. (Heuristic - LLM unavailable)",
            "reasoning_trace": "Heuristic fallback: LLM diagnosis unavailable. Pattern matched from fault_class=resource_exhaustion.",
            "is_heuristic": True,
        }

    if fault_class == "misconfiguration":
        config_rule = evidence.get("config_rule", "")
        if "PUBLIC" in config_rule or "S3" in config_rule:
            action = "lock_s3_bucket"
        elif "ADMIN" in config_rule or "IAM" in config_rule:
            action = "tighten_iam_policy"
        else:
            action = "lock_s3_bucket"

        return {
            "root_cause": f"AWS Security non-compliance flagged by rule {config_rule or resource_id}",
            "confidence": HEURISTIC_CONFIDENCE,
            "affected_resources": [resource_id],
            "suggested_action": action,
            "explanation": f"Security non-compliance detected on {resource_id}. (Heuristic - LLM unavailable)",
            "reasoning_trace": "Heuristic fallback: LLM diagnosis unavailable. Pattern matched from fault_class=misconfiguration.",
            "is_heuristic": True,
        }

    if fault_class == "service_cascade":
        return {
            "root_cause": "Downstream Service C failure cascaded upstream to Service B and Service A",
            "confidence": HEURISTIC_CONFIDENCE,
            "affected_resources": ["ServiceC", "ServiceB", "ServiceA"],
            "suggested_action": "restart_downstream_service",
            "explanation": "Cascading failure initiated at leaf service Service C. (Heuristic - LLM unavailable)",
            "reasoning_trace": "Heuristic fallback: LLM diagnosis unavailable. Pattern matched from fault_class=service_cascade.",
            "is_heuristic": True,
        }

    return {
        "root_cause": "Unspecified incident anomaly detected",
        "confidence": HEURISTIC_CONFIDENCE,
        "affected_resources": [resource_id],
        "suggested_action": "manual_review_required",
        "explanation": "Incident requires manual investigation. (Heuristic - LLM unavailable)",
        "reasoning_trace": "Heuristic fallback: unknown fault_class, cannot pattern-match.",
        "is_heuristic": True,
    }


def _update_dynamodb_diagnosis(
    incident_id: str,
    diagnosis_output: dict,
    used_rag: bool,
    failure_mode: str | None,
) -> None:
    if not INCIDENTS_TABLE:
        logger.warning("INCIDENTS_TABLE not configured; skipping DynamoDB update")
        return

    table = _dynamodb.Table(INCIDENTS_TABLE)
    try:
        table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=(
                "SET diagnosis.#rc = :rc, "
                "diagnosis.#conf = :conf, "
                "diagnosis.#ar = :ar, "
                "diagnosis.#sa = :sa, "
                "diagnosis.#rt = :rt, "
                "diagnosis.#ur = :ur, "
                "diagnosis.#fm = :fm, "
                "diagnosis.#exp = :exp, "
                "diagnosis.#ds = :ds, "
                "diagnosis.#mu = :mu, "
                "diagnosis.#ih = :ih"
            ),
            ExpressionAttributeNames={
                "#rc": "root_cause",
                "#conf": "confidence",
                "#ar": "affected_resources",
                "#sa": "suggested_action",
                "#rt": "reasoning_trace",
                "#ur": "used_rag",
                "#fm": "failure_mode",
                "#exp": "explanation",
                "#ds": "diagnosis_status",
                "#mu": "model_used",
                "#ih": "is_heuristic",
            },
            ExpressionAttributeValues={
                ":rc": diagnosis_output["root_cause"],
                ":conf": Decimal(str(diagnosis_output["confidence"])),
                ":ar": diagnosis_output["affected_resources"],
                ":sa": diagnosis_output["suggested_action"],
                ":rt": diagnosis_output["reasoning_trace"],
                ":ur": used_rag,
                ":fm": failure_mode,
                ":exp": diagnosis_output["explanation"],
                ":ds": diagnosis_output.get("diagnosis_status", "success"),
                ":mu": diagnosis_output.get("model_used", BEDROCK_MODEL_ID),
                ":ih": bool(diagnosis_output.get("is_heuristic", False)),
            },
            ConditionExpression="attribute_exists(incident_id)"
        )
        logger.info(json.dumps({
            "event": "dynamodb_diagnosis_updated",
            "incident_id": incident_id,
            "table": INCIDENTS_TABLE,
        }))
    except ClientError as exc:
        logger.error(f"Error updating DynamoDB diagnosis item {incident_id}: {exc}")


def _invoke_notify(incident_id: str, diagnosis_output: dict) -> None:
    """
    Invoke the notify Lambda. On any failure, write a notify_failed flag to DynamoDB
    so operators can see that no Slack notification was sent (SE-14). We do NOT raise
    here - notification failure must never block the diagnosis record from being saved.
    """
    if not NOTIFY_FUNCTION_NAME:
        logger.warning("NOTIFY_FUNCTION_NAME not configured; skipping notify step")
        return

    payload = {
        "incident_id": incident_id,
        "diagnosis": diagnosis_output,
    }
    try:
        _lambda.invoke(
            FunctionName=NOTIFY_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
        logger.info(f"Invoked Notify Lambda {NOTIFY_FUNCTION_NAME} for incident {incident_id}")
    except Exception as exc:  # noqa: BLE001 - SE-14: catch all, not just ClientError
        logger.error(json.dumps({
            "event": "notify_invoke_failed",
            "incident_id": incident_id,
            "error": str(exc),
            "ATTENTION": "Slack notification was NOT sent. Writing notify_failed flag to DynamoDB.",
        }))
        # SE-14: Write the failure flag so the UI and evaluation scripts can detect it.
        if INCIDENTS_TABLE:
            try:
                _dynamodb.Table(INCIDENTS_TABLE).update_item(
                    Key={"incident_id": incident_id},
                    UpdateExpression="SET diagnosis.notify_failed = :v, diagnosis.notify_error = :e",
                    ExpressionAttributeValues={
                        ":v": True,
                        ":e": str(exc),
                    },
                )
            except Exception as ddb_exc:  # noqa: BLE001
                logger.error(f"Could not write notify_failed flag to DynamoDB: {ddb_exc}")