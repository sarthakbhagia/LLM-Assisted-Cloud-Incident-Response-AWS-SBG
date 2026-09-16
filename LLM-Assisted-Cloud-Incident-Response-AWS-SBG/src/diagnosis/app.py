"""
app.py — Phase 4: Diagnosis Lambda Handler

Receives incident payload from collector, reads raw_data.json from S3,
loads runbook context (unless used_rag=false ablation flag is set),
invokes AWS Bedrock Nova/Llama/Mistral model, validates JSON diagnosis, updates DynamoDB,
and invokes notify Lambda.
"""

from __future__ import annotations

import json
import logging
import os
import re
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
- suggested_action must match one of the 6 exact values above"""

LLAMA_SYSTEM_PROMPT = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{SYSTEM_PROMPT}

{NOVA_SYSTEM_PROMPT}
<|eot_id|><|start_header_id|>user<|end_header_id|>

{{prompt}}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

MISTRAL_SYSTEM_PROMPT = f"""<s>[INST] {SYSTEM_PROMPT}

{NOVA_SYSTEM_PROMPT} [/INST]"""


def lambda_handler(event, context):
    logger.info(json.dumps({"event": "diagnosis_triggered", "payload": event}))

    incident_id = event.get("incident_id")
    fault_class = event.get("fault_class", "unknown")
    s3_key = event.get("raw_data_s3_key") or f"incidents/{incident_id}/raw_data.json"
    used_rag = event.get("used_rag", True)

    if not incident_id or not DATA_LAKE_BUCKET:
        logger.error("Missing incident_id or DATA_LAKE_BUCKET")
        return {"statusCode": 400, "body": "Missing required parameters"}

    # 1. Fetch raw evidence from S3
    raw_data = _fetch_s3_raw_data(s3_key)

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
    )

    # 5. Update DynamoDB IncidentRecord
    _update_dynamodb_diagnosis(incident_id, diagnosis_output, used_rag, failure_mode)

    # 6. Invoke Notify Lambda
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
    try:
        resp = _s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=s3_key)
        content = resp["Body"].read().decode("utf-8")
        return json.loads(content)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error reading S3 raw_data key={s3_key}: {exc}")
        return {"fault_class": "unknown", "evidence": {}, "error": str(exc)}


def _invoke_llm_with_validation(
    user_prompt: str,
    fault_class: str,
    raw_data: dict,
) -> tuple[dict, str | None]:
    """Call Bedrock LLM, parse & validate JSON diagnosis, retry once if malformed."""
    raw_response = None
    failure_mode = None

    try:
        raw_response = _call_bedrock(user_prompt)
        logger.info(f"Raw LLM response (first 500 chars): {str(raw_response)[:500]}")
        validated_diag = _parse_and_validate_json(raw_response)
        return validated_diag, None
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Initial LLM response invalid or failed: {exc}. Raw response: {str(raw_response)[:500]}. Retrying once...")
        failure_mode = f"validation_error: {exc}"

        if raw_response:
            correction_prompt = build_error_correction_prompt(raw_response, str(exc))
            try:
                second_response = _call_bedrock(correction_prompt)
                logger.info(f"Retry LLM response (first 500 chars): {str(second_response)[:500]}")
                validated_diag = _parse_and_validate_json(second_response)
                return validated_diag, "retry_succeeded"
            except Exception as retry_exc:  # noqa: BLE001
                logger.error(f"Retry LLM invocation failed: {retry_exc}")
                failure_mode = f"retry_failed: {retry_exc}"

    # Fallback heuristic diagnosis if Bedrock is unreachable / unconfigured
    fallback_diag = _generate_fallback_diagnosis(fault_class, raw_data)
    return fallback_diag, failure_mode or "fallback_heuristic_used"


def _call_bedrock(prompt: str) -> str:
    """Invoke Bedrock model with fallback chain: Nova Pro -> Llama 3 70B -> Mistral Large -> Nova Micro."""
    logger.info(f"_call_bedrock invoked with prompt length: {len(prompt)}")
    logger.info("_call_bedrock: Starting execution")

    nova_payload = {
        "messages": [
            {"role": "user", "content": [{"text": NOVA_SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"text": prompt}]}
        ],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.1},
    }

    llama_payload = {
        "prompt": LLAMA_SYSTEM_PROMPT.format(prompt=prompt),
        "max_gen_len": 1024,
        "temperature": 0.1,
    }

    mistral_payload = {
        "prompt": MISTRAL_SYSTEM_PROMPT.format(prompt=prompt),
        "max_tokens": 1024,
        "temperature": 0.1,
    }

    def _invoke_nova(model_id: str) -> str:
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
            message = output.get("message", {})
            logger.info(f"Nova message keys: {list(message.keys()) if message else 'None'}")
            content = message.get("content", [])
            logger.info(f"Nova content: {content}")
            if content and isinstance(content, list):
                text = content[0].get("text", "")
                logger.info(f"Nova text (first 200): {text[:200]}")
                return text
            logger.warning(f"Nova unexpected response format: {response_body}")
            return str(response_body)
        except Exception as e:
            logger.error(f"Nova invocation failed with {type(e).__name__}: {e}")
            raise

    def _invoke_llama(model_id: str) -> str:
        logger.info(f"Invoking Llama model: {model_id}")
        try:
            response = _bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps(llama_payload),
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read().decode("utf-8"))
            return response_body.get("generation", "")
        except Exception as e:
            logger.error(f"Llama invocation failed with {type(e).__name__}: {e}")
            raise

    def _invoke_mistral(model_id: str) -> str:
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
            if outputs and isinstance(outputs, list):
                return outputs[0].get("text", "")
            return str(response_body)
        except Exception as e:
            logger.error(f"Mistral invocation failed with {type(e).__name__}: {e}")
            raise

    def _try_model(model_id: str, invoke_fn, model_name: str, next_model: str | None = None):
        logger.info(f"_try_model called for {model_name}")
        try:
            logger.info(f"Trying model: {model_name} ({model_id})")
            result = invoke_fn(model_id)
            logger.info(f"Model {model_name} returned: {type(result)}")
            return result
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
    try:
        logger.info("Attempt 1: Nova Pro")
        result = _try_model(BEDROCK_MODEL_ID, _invoke_nova, "Nova Pro", FALLBACK_MODEL_ID)
        logger.info(f"Nova Pro attempt returned: {result[:100] if result else 'None'}")
        return result
    except ClientError as e:
        logger.warning(f"Nova Pro failed with ClientError: {e}")
        pass

    try:
        logger.info("Attempt 2: Llama 3 70B")
        result = _try_model(FALLBACK_MODEL_ID, _invoke_llama, "Llama 3 70B", SECOND_FALLBACK_MODEL_ID)
        logger.info(f"Llama attempt returned: {result[:100] if result else 'None'}")
        return result
    except ClientError as e:
        logger.warning(f"Llama failed with ClientError: {e}")
        pass

    try:
        logger.info("Attempt 3: Mistral Large")
        result = _try_model(SECOND_FALLBACK_MODEL_ID, _invoke_mistral, "Mistral Large", NOVA_FALLBACK_MODEL_ID)
        logger.info(f"Mistral attempt returned: {result[:100] if result else 'None'}")
        return result
    except ClientError as e:
        logger.warning(f"Mistral failed with ClientError: {e}")
        pass

    try:
        logger.info("Attempt 4: Nova Micro")
        result = _try_model(NOVA_FALLBACK_MODEL_ID, _invoke_nova, "Nova Micro", None)
        logger.info(f"Nova Micro attempt returned: {result[:100] if result else 'None'}")
        return result
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

    data = json.loads(clean_text)

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
        "increase instance type": "scale_up",
        "scale out": "scale_up",
        "scale up": "scale_up",
        "add instances": "scale_up",
        "restart": "restart_service",
        "restart service": "restart_service",
        "terminate processes": "restart_service",
        "lock bucket": "lock_s3_bucket",
        "block public access": "lock_s3_bucket",
        "tighten policy": "tighten_iam_policy",
        "restrict permissions": "tighten_iam_policy",
        "restart downstream": "restart_downstream_service",
        "manual review": "manual_review_required",
        "investigate manually": "manual_review_required",
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

    if not explanation or not isinstance(explanation, str):
        raise ValueError("Missing or invalid 'explanation'")

    if not reasoning_trace or not isinstance(reasoning_trace, str):
        raise ValueError("Missing or invalid 'reasoning_trace'")

    return {
        "root_cause": root_cause,
        "confidence": float(confidence),
        "affected_resources": [str(r) for r in affected_resources],
        "suggested_action": suggested_action,
        "explanation": explanation,
        "reasoning_trace": reasoning_trace,
    }


def _generate_fallback_diagnosis(fault_class: str, raw_data: dict) -> dict:
    """Generate heuristic fallback diagnosis when Bedrock is unavailable/unconfigured."""
    evidence = raw_data.get("evidence", {})
    resource_id = raw_data.get("detection_event", {}).get("resource_id", "unknown-resource")

    if fault_class == "resource_exhaustion":
        return {
            "root_cause": "Lambda execution duration exceeded threshold under memory/compute exhaustion pressure",
            "confidence": 0.85,
            "affected_resources": [evidence.get("function_name") or resource_id],
            "suggested_action": "scale_up",
            "explanation": "Service A experienced high duration causing timeout alarms.",
            "reasoning_trace": "Fallback diagnosis based on resource_exhaustion telemetry metrics.",
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
            "confidence": 0.90,
            "affected_resources": [resource_id],
            "suggested_action": action,
            "explanation": f"Security non-compliance detected on {resource_id}.",
            "reasoning_trace": "Fallback diagnosis based on AWS Config / GuardDuty compliance record.",
        }

    if fault_class == "service_cascade":
        return {
            "root_cause": "Downstream Service C failure cascaded upstream to Service B and Service A",
            "confidence": 0.88,
            "affected_resources": ["ServiceC", "ServiceB", "ServiceA"],
            "suggested_action": "restart_downstream_service",
            "explanation": "Cascading failure initiated at leaf service Service C.",
            "reasoning_trace": "Fallback diagnosis based on X-Ray service graph & log correlation.",
        }

    return {
        "root_cause": "Unspecified incident anomaly detected",
        "confidence": 0.50,
        "affected_resources": [resource_id],
        "suggested_action": "manual_review_required",
        "explanation": "Incident requires manual investigation.",
        "reasoning_trace": "Fallback generic diagnosis.",
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
                "diagnosis.#exp = :exp"
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
            },
            ExpressionAttributeValues={
                ":rc": diagnosis_output["root_cause"],
                ":conf": str(diagnosis_output["confidence"]),
                ":ar": diagnosis_output["affected_resources"],
                ":sa": diagnosis_output["suggested_action"],
                ":rt": diagnosis_output["reasoning_trace"],
                ":ur": used_rag,
                ":fm": failure_mode,
                ":exp": diagnosis_output["explanation"],
            },
            ConditionExpression="attribute_exists(incident_id)"
            ExpressionAttributeNames={
                "#rc": "root_cause",
                "#conf": "confidence",
                "#ar": "affected_resources",
                "#sa": "suggested_action",
                "#rt": "reasoning_trace",
                "#ur": "used_rag",
                "#fm": "failure_mode",
                "#exp": "explanation",
            },
            ExpressionAttributeValues={
                ":rc": diagnosis_output["root_cause"],
                ":conf": str(diagnosis_output["confidence"]),
                ":ar": diagnosis_output["affected_resources"],
                ":sa": diagnosis_output["suggested_action"],
                ":rt": diagnosis_output["reasoning_trace"],
                ":ur": used_rag,
                ":fm": failure_mode,
                ":exp": diagnosis_output["explanation"],
            },
        )
        logger.info(json.dumps({
            "event": "dynamodb_diagnosis_updated",
            "incident_id": incident_id,
            "table": INCIDENTS_TABLE,
        }))
    except ClientError as exc:
        logger.error(f"Error updating DynamoDB diagnosis item {incident_id}: {exc}")


def _invoke_notify(incident_id: str, diagnosis_output: dict) -> None:
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
    except ClientError as exc:
        logger.error(f"Error invoking Notify Lambda {NOTIFY_FUNCTION_NAME}: {exc}")