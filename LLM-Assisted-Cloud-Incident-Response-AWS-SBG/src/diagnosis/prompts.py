"""
prompts.py — Phase 4: Prompt Construction for Incident Diagnosis

Constructs system and user prompts for Bedrock Claude model execution,
enforcing strict JSON response formatting matching the diagnosis output contract.
"""

import json

VALID_SUGGESTED_ACTIONS = [
    "scale_up",
    "restart_service",
    "lock_s3_bucket",
    "tighten_iam_policy",
    "restart_downstream_service",
    "manual_review_required",
]

SYSTEM_PROMPT = """You are an expert AWS Cloud Reliability Engineer and Automated Incident Response Agent.
Your task is to diagnose system incidents based on observability data, telemetry evidence, and optional runbook procedures.

You MUST respond with a SINGLE valid JSON object adhering EXACTLY to this JSON schema, with no markdown formatting, no code block markers (do NOT use ```json), and no extra text before or after the JSON:

{
  "root_cause": "string — clear, concise root cause explanation",
  "confidence": 0.95,
  "affected_resources": ["string — list of affected AWS resource names or ARNs"],
  "suggested_action": "one of: scale_up | restart_service | lock_s3_bucket | tighten_iam_policy | restart_downstream_service | manual_review_required",
  "explanation": "string — plain-English incident summary suitable for Slack incident report",
  "reasoning_trace": "string — step-by-step diagnostic reasoning trace for audit log"
}

RULES:
1. `suggested_action` MUST be EXACTLY one of: "scale_up", "restart_service", "lock_s3_bucket", "tighten_iam_policy", "restart_downstream_service", "manual_review_required".
2. `confidence` MUST be a float between 0.0 and 1.0.
3. `affected_resources` MUST be a JSON array of strings.
4. Output ONLY the JSON object.
"""


def build_diagnosis_prompt(raw_data: dict, runbook_text: str | None = None) -> str:
    """Build the user prompt combining incident evidence and optional runbook context."""
    fault_class = raw_data.get("fault_class", "unknown")
    incident_id = raw_data.get("incident_id", "unknown")
    detected_at = raw_data.get("detected_at", "")
    evidence = raw_data.get("evidence", {})

    prompt_parts = [
        f"INCIDENT DIAGNOSIS REQUEST (Incident ID: {incident_id})",
        f"Fault Class: {fault_class}",
        f"Detected At: {detected_at}",
        "",
        "--- OBSERVABILITY & TELEMETRY EVIDENCE ---",
        json.dumps(evidence, indent=2, default=str),
        "",
    ]

    if runbook_text:
        prompt_parts.extend([
            "--- INJECTED RUNBOOK PROCEDURES & REMEDIATION GUIDANCE ---",
            runbook_text,
            "",
            "Instructions: Use the above runbook procedures to analyze the evidence and determine the root cause and suggested remediation action.",
        ])
    else:
        prompt_parts.extend([
            "Note: No runbook context is provided (ablated mode). Use your intrinsic AWS cloud knowledge to diagnose the incident.",
        ])

    prompt_parts.append("\nGenerate the JSON diagnosis response now:")
    return "\n".join(prompt_parts)


def build_error_correction_prompt(raw_response: str, error_message: str) -> str:
    """Construct an error correction prompt for retrying invalid LLM output."""
    return (
        f"Your previous response failed JSON schema validation.\n\n"
        f"Error: {error_message}\n\n"
        f"Previous Response:\n{raw_response}\n\n"
        f"Please correct the JSON object and return ONLY the valid JSON matching the specified schema."
    )
