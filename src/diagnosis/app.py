"""
diagnosis_lambda.py — Phase 4 STUB

This Lambda is invoked asynchronously by the collector after evidence is
collected. Phase 4 will implement the full Bedrock / LLM diagnosis pipeline.

For now this stub:
  - Logs the incoming payload so we can confirm the async invocation works
  - Returns immediately without updating DynamoDB
"""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info(json.dumps({
        "event": "diagnosis_stub_invoked",
        "incident_id": event.get("incident_id"),
        "fault_class": event.get("fault_class"),
        "raw_data_s3_key": event.get("raw_data_s3_key"),
        "note": "Phase 4 stub — full LLM diagnosis not yet implemented",
    }, default=str))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Diagnosis stub received event — Phase 4 will implement the real pipeline",
            "incident_id": event.get("incident_id"),
        }),
    }
