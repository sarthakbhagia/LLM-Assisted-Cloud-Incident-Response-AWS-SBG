"""
prompts.py - Phase 4: Prompt Construction for Incident Diagnosis

Constructs system and user prompts for Bedrock model execution (primary: Amazon Nova Pro),
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
  "reasoning_trace": "string — step-by-step diagnostic reasoning trace for audit log",
  "recommended_solutions": [
    {
      "id": "string — unique solution identifier (e.g., sol-1, sol-2)",
      "action": "one of: scale_up | restart_service | lock_s3_bucket | tighten_iam_policy | restart_downstream_service | manual_review_required",
      "title": "string — short human-readable title",
      "description": "string — detailed description of the remediation action",
      "risk": "low | medium | high",
      "expected_outcome": "string — expected result after applying this solution",
      "rationale": "string — why this solution addresses the root cause",
      "confidence": 0.95,
      "source": "llm | runbook"
    }
  ]
}

RULES:
1. `suggested_action` MUST be EXACTLY one of: "scale_up", "restart_service", "lock_s3_bucket", "tighten_iam_policy", "restart_downstream_service", "manual_review_required".
2. `confidence` MUST be a float between 0.0 and 1.0.
3. `affected_resources` MUST be a JSON array of strings.
4. `recommended_solutions` MUST be an array of 2-3 objects, each with the exact fields above.
5. `recommended_solutions[0].action` MUST equal `suggested_action`.
6. Each solution's `action` MUST be exactly one of: "scale_up", "restart_service", "lock_s3_bucket", "tighten_iam_policy", "restart_downstream_service", "manual_review_required".
7. Each solution's `risk` MUST be exactly one of: "low", "medium", "high".
8. Each solution's `source` MUST be exactly one of: "llm", "runbook".
9. Each solution's `confidence` MUST be a float between 0.0 and 1.0.
10. Output ONLY the JSON object.
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

    prompt_parts.extend([
        "",
        "Generate the JSON diagnosis response now. The response MUST include a 'recommended_solutions' array with 2-3 solution objects, each containing:",
        "  - id: unique solution identifier (e.g., sol-1, sol-2)",
        "  - action: must be one of: scale_up, restart_service, lock_s3_bucket, tighten_iam_policy, restart_downstream_service, manual_review_required",
        "  - title: short human-readable title",
        "  - description: detailed description of the remediation action",
        "  - risk: must be exactly one of: low, medium, high",
        "  - expected_outcome: expected result after applying this solution",
        "  - rationale: why this solution addresses the root cause",
        "  - confidence: number between 0.0 and 1.0",
        "  - source: must be exactly 'llm' or 'runbook'",
        "",
        "The first solution in recommended_solutions MUST have its 'action' field equal to the top-level 'suggested_action' field.",
    ])
    return "\n".join(prompt_parts)


def build_error_correction_prompt(raw_response: str, error_message: str) -> str:
    """Construct an error correction prompt for retrying invalid LLM output."""
    return (
        f"Your previous response failed JSON schema validation.\n\n"
        f"Error: {error_message}\n\n"
        f"Previous Response:\n{raw_response}\n\n"
        f"Please correct the JSON object and return ONLY the valid JSON matching the specified schema."
    )
