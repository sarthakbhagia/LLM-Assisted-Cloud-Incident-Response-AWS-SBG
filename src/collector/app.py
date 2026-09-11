import json
import logging
import os
import uuid
from datetime import datetime, timezone

try:
    import boto3
except ImportError:
    boto3 = None


logger = logging.getLogger()
logger.setLevel(logging.INFO)

EVIDENCE_KEY_TEMPLATE = "incidents/{incident_id}/evidence.json"
DETECTION_SOURCES = {"cloudwatch", "config", "guardduty", "cascade"}


def _detection_source(event, fault_class):
    source = str(event.get("source", "")).lower()
    if fault_class == "service_cascade" or "cascade" in source:
        return "cascade"
    if source in {"aws.config", "aws_config", "config"}:
        return "config"
    if source in {"aws.guardduty", "guardduty"}:
        return "guardduty"
    if source in {"aws.cloudwatch", "cloudwatch"}:
        return "cloudwatch"
    if source in DETECTION_SOURCES:
        return source
    return "unknown"


def _event_detail(event):
    detail = event.get("detail")
    return detail if isinstance(detail, dict) else {}


def _fault_class(event, detail):
    supplied = _first_value(event.get("fault_class"), detail.get("fault_class"))
    if supplied:
        return supplied
    alarm_name = str(_first_value(detail.get("alarmName"), event.get("alarm_name"), "")).lower()
    if "cascade" in alarm_name:
        return "service_cascade"
    if "resource-exhaustion" in alarm_name:
        return "resource_exhaustion"
    if str(event.get("source", "")).lower() in {"aws.config", "aws_config", "config"}:
        return "misconfiguration"
    return "unknown"


def _first_value(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _cloudwatch_evidence(event, detail):
    state = detail.get("state") if isinstance(detail.get("state"), dict) else {}
    previous_state = detail.get("previousState")
    if not isinstance(previous_state, dict):
        previous_state = {}
    configuration = detail.get("configuration", {})
    if not isinstance(configuration, dict):
        configuration = {}

    return {
        "alarm_name": _first_value(detail.get("alarmName"), event.get("alarm_name")),
        "alarm_state": _first_value(
            state.get("value"), detail.get("stateValue"), event.get("state")
        ),
        "state_reason": _first_value(
            state.get("reason"), detail.get("reason"), event.get("reason")
        ),
        "previous_state": previous_state,
        "metric_configuration": configuration,
        "alarm_arn": detail.get("alarmArn"),
    }


def _config_evidence(event, detail):
    evaluation = detail.get("newEvaluationResult", {})
    if not isinstance(evaluation, dict):
        evaluation = {}
    return {
        "compliance": {
            "compliance_type": _first_value(
                evaluation.get("complianceType"), detail.get("complianceType")
            ),
            "annotation": evaluation.get("annotation"),
            "result_token": evaluation.get("resultToken"),
        },
        "resource": {
            "resource_type": _first_value(
                detail.get("resourceType"), event.get("resource_type")
            ),
            "resource_id": _first_value(
                detail.get("resourceId"), event.get("resource_id")
            ),
        },
        "rule": {
            "name": _first_value(
                detail.get("configRuleName"), event.get("config_rule")
            ),
            "arn": detail.get("configRuleArn"),
        },
    }


def _guardduty_evidence(detail):
    resource = detail.get("resource", {})
    if not isinstance(resource, dict):
        resource = {}
    return {
        "finding_id": detail.get("id"),
        "finding_type": detail.get("type"),
        "severity": detail.get("severity"),
        "affected_resource": resource,
        "finding": detail,
    }


def _cascade_evidence(event, detail):
    return {
        "composite_alarm": {
            "alarm_name": _first_value(detail.get("alarmName"), event.get("alarm_name")),
            "alarm_arn": detail.get("alarmArn"),
            "state": _first_value(
                detail.get("state", {}).get("value")
                if isinstance(detail.get("state"), dict)
                else None,
                event.get("state"),
            ),
        },
        "alarm_details": detail,
    }


def build_incident(event):
    """Normalize an EventBridge event without making network calls."""
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")

    detail = _event_detail(event)
    fault_class = _fault_class(event, detail)
    source = _detection_source(event, fault_class)
    incident_id = str(uuid.uuid4())
    timestamp = _first_value(event.get("time"), event.get("timestamp"))
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    if source == "cloudwatch":
        collected_evidence = {"cloudwatch": _cloudwatch_evidence(event, detail)}
    elif source == "config":
        collected_evidence = {"config": _config_evidence(event, detail)}
    elif source == "guardduty":
        collected_evidence = {"guardduty": _guardduty_evidence(detail)}
    elif source == "cascade":
        collected_evidence = {"cascade": _cascade_evidence(event, detail)}
    else:
        collected_evidence = {"event": detail or event}

    collected_evidence["event_metadata"] = {
        "event_id": _first_value(event.get("id"), event.get("event_id")),
        "event_source": event.get("source"),
        "detail_type": event.get("detail-type"),
        "timestamp": timestamp,
        "region": event.get("region"),
        "account": event.get("account"),
        "fault_class": fault_class,
    }

    evidence = {
        "incident_id": incident_id,
        "timestamp": timestamp,
        "fault_class": fault_class,
        "detection_source": source,
        "detection_event": event,
        "collected_evidence": collected_evidence,
    }
    return evidence


def _incident_record(evidence, bucket, evidence_key, status="DETECTED", error=None):
    event = evidence["detection_event"]
    detail = _event_detail(event)
    cloudwatch = evidence["collected_evidence"].get("cloudwatch", {})
    guardduty = evidence["collected_evidence"].get("guardduty", {})
    config = evidence["collected_evidence"].get("config", {})
    resource = config.get("resource", {})
    affected_resource = _first_value(
        detail.get("resource"),
        cloudwatch.get("alarm_arn"),
        guardduty.get("affected_resource"),
        resource.get("resource_id"),
        event.get("resource_id"),
    )
    record = {
        "incident_id": evidence["incident_id"],
        "timestamp": evidence["timestamp"],
        "fault_class": evidence["fault_class"],
        "detection_source": evidence["detection_source"],
        "status": status,
        "s3_bucket": bucket,
        "s3_evidence_key": evidence_key,
        "event_id": _first_value(event.get("id"), event.get("event_id"), "unknown"),
    }
    optional_fields = {
        "affected_resource": affected_resource,
        "alarm_name": _first_value(cloudwatch.get("alarm_name"), event.get("alarm_name")),
        "finding_id": _first_value(guardduty.get("finding_id"), detail.get("findingId")),
        "error": error,
    }
    record.update({key: value for key, value in optional_fields.items() if value is not None})
    return record


def lambda_handler(event, context):
    bucket = os.environ.get("INCIDENT_DATA_LAKE_BUCKET")
    table_name = os.environ.get("INCIDENTS_TABLE_NAME")
    region = os.environ.get("INCIDENT_AWS_REGION")
    if not bucket or not table_name:
        raise RuntimeError("INCIDENT_DATA_LAKE_BUCKET and INCIDENTS_TABLE_NAME are required")
    if boto3 is None:
        raise RuntimeError("boto3 is required when storing incident data")

    evidence = build_incident(event)
    evidence_key = EVIDENCE_KEY_TEMPLATE.format(incident_id=evidence["incident_id"])
    s3_error = None
    try:
        s3_client = boto3.client("s3", region_name=region) if region else boto3.client("s3")
        s3_client.put_object(
            Bucket=bucket,
            Key=evidence_key,
            Body=json.dumps(evidence, default=str).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as error:
        s3_error = str(error)
        logger.exception("Failed to store incident evidence in S3")

    status = "DETECTED" if s3_error is None else "COLLECTION_ERROR"
    record = _incident_record(evidence, bucket, evidence_key, status=status, error=s3_error)
    try:
        dynamodb = boto3.resource("dynamodb", region_name=region) if region else boto3.resource("dynamodb")
        dynamodb.Table(table_name).put_item(Item=record)
    except Exception:
        logger.exception("Failed to store incident record in DynamoDB")
        raise

    if s3_error is not None:
        raise RuntimeError(f"Incident evidence collection failed: {s3_error}")

    logger.info(json.dumps({"event": "incident_detected", "incident_id": evidence["incident_id"], "detection_source": evidence["detection_source"]}))
    return {"statusCode": 200, "body": json.dumps({"incident_id": evidence["incident_id"], "status": status})}
