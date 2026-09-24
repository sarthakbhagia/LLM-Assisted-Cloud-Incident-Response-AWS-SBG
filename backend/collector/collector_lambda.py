"""
collector_lambda.py — Phase 3: Data Collection

Triggered by EventBridge rules (CloudWatch alarms, AWS Config, GuardDuty).

Pipeline:
  1. Parse incoming event → fault_class + resource identifiers
  2. Collect fault-class-specific observability evidence
  3. Write evidence bundle → S3 (incidents/{incident_id}/raw_data.json)
  4. Write initial IncidentRecord → DynamoDB
  5. Async-invoke diagnosis_lambda (Phase 4 stub for now)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# AWS clients — initialised once at cold start
# ---------------------------------------------------------------------------
_cw_logs = boto3.client("logs")
_cw = boto3.client("cloudwatch")
_s3 = boto3.client("s3")
_dynamodb = boto3.resource("dynamodb")
_config = boto3.client("config")
_guardduty = boto3.client("guardduty")
_xray = boto3.client("xray")
_lambda = boto3.client("lambda")

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
INCIDENTS_TABLE = os.environ["INCIDENTS_TABLE"]
DATA_LAKE_BUCKET = os.environ["DATA_LAKE_BUCKET"]
DIAGNOSIS_FUNCTION_NAME = os.environ.get("DIAGNOSIS_FUNCTION_NAME", "")

# Evidence lookback window in seconds (15 min)
LOOKBACK_SECONDS = 900

# CloudWatch Logs Insights max wait for query (seconds)
CWL_QUERY_MAX_WAIT = 60


# ===========================================================================
# Entry point
# ===========================================================================

def lambda_handler(event, context):
    logger.info(json.dumps({"event": "collector_triggered", "raw_event": event}, default=str))

    try:
        parsed = _parse_event(event)
    except ValueError as exc:
        logger.error(json.dumps({"event": "parse_error", "error": str(exc), "raw": event}, default=str))
        return {"statusCode": 400, "body": str(exc)}

    incident_id = str(uuid.uuid4())
    detected_at = datetime.now(timezone.utc).isoformat()
    fault_class = parsed["fault_class"]

    logger.info(json.dumps({
        "event": "incident_created",
        "incident_id": incident_id,
        "fault_class": fault_class,
        "resource_id": parsed.get("resource_id"),
    }))

    # Collect evidence
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (LOOKBACK_SECONDS * 1000)

    raw_data = {
        "incident_id": incident_id,
        "fault_class": fault_class,
        "detected_at": detected_at,
        "detection_source": parsed.get("source", "unknown"),
        "detection_event": parsed,
        "evidence": {},
    }

    try:
        raw_data["evidence"] = _collect_evidence(parsed, start_ms, now_ms)
    except Exception as exc:  # noqa: BLE001
        logger.error(json.dumps({"event": "evidence_collection_error", "error": str(exc)}, default=str))
        raw_data["evidence_error"] = str(exc)

    # Write to S3
    s3_key = f"incidents/{incident_id}/raw_data.json"
    try:
        _s3.put_object(
            Bucket=DATA_LAKE_BUCKET,
            Key=s3_key,
            Body=json.dumps(raw_data, indent=2, default=str),
            ContentType="application/json",
        )
        logger.info(json.dumps({"event": "s3_written", "key": s3_key}))
    except ClientError as exc:
        logger.error(json.dumps({"event": "s3_write_error", "error": str(exc)}, default=str))
        raise

    # Write initial IncidentRecord to DynamoDB
    _write_incident_record(incident_id, detected_at, fault_class, s3_key, parsed)

    # Async-invoke diagnosis Lambda
    _invoke_diagnosis(incident_id, fault_class, s3_key)

    return {
        "statusCode": 200,
        "body": json.dumps({"incident_id": incident_id, "s3_key": s3_key}),
    }


# ===========================================================================
# Event parsing
# ===========================================================================

def _parse_event(event: dict) -> dict:
    """
    Normalise the EventBridge event payload produced by any of the three
    InputTransformer rules (or raw GuardDuty) into a unified dict:

        {
            "fault_class":  "resource_exhaustion" | "misconfiguration" | "service_cascade",
            "source":       str,          # aws.cloudwatch | aws_config | aws.guardduty
            "resource_id":  str | None,
            "alarm_name":   str | None,   # resource_exhaustion / service_cascade
            "config_rule":  str | None,   # misconfiguration
            "resource_type": str | None,  # misconfiguration
            "finding_id":   str | None,   # GuardDuty
            "detector_id":  str | None,   # GuardDuty
        }
    """
    fault_class = event.get("fault_class")
    source = event.get("source", "")

    # ---- CloudWatch Alarm (resource_exhaustion or service_cascade) ----------
    if source in ("cloudwatch", "aws.cloudwatch") and fault_class in (
        "resource_exhaustion", "service_cascade"
    ):
        return {
            "fault_class": fault_class,
            "source": "cloudwatch",
            "alarm_name": event.get("alarm_name"),
            "resource_id": event.get("alarm_name"),
            "config_rule": None,
            "resource_type": None,
            "finding_id": None,
            "detector_id": None,
            "state": event.get("state"),
            "reason": event.get("reason"),
        }

    # ---- AWS Config (misconfiguration) -------------------------------------
    if source in ("aws_config", "aws.config") and fault_class == "misconfiguration":
        return {
            "fault_class": "misconfiguration",
            "source": "aws_config",
            "alarm_name": None,
            "resource_id": event.get("resource_id"),
            "config_rule": event.get("config_rule"),
            "resource_type": event.get("resource_type"),
            "finding_id": None,
            "detector_id": None,
        }

    # ---- GuardDuty (raw finding — no InputTransformer applied) -------------
    if source == "aws.guardduty" or event.get("detail-type") == "GuardDuty Finding":
        detail = event.get("detail", event)
        finding_id = detail.get("id") or detail.get("findingId")
        account_id = detail.get("accountId") or detail.get("accountID")
        return {
            "fault_class": "misconfiguration",  # GuardDuty findings → misconfiguration class
            "source": "guardduty",
            "alarm_name": None,
            "resource_id": finding_id,
            "config_rule": None,
            "resource_type": detail.get("type"),
            "finding_id": finding_id,
            "detector_id": _get_guardduty_detector_id(),
            "account_id": account_id,
        }

    # ---- Test / manual invocation fallback ---------------------------------
    if fault_class in ("resource_exhaustion", "misconfiguration", "service_cascade"):
        logger.warning(json.dumps({
            "event": "unknown_source",
            "source": source,
            "fault_class": fault_class,
            "message": "Proceeding with best-effort parsing",
        }))
        return {
            "fault_class": fault_class,
            "source": source or "unknown",
            "alarm_name": event.get("alarm_name"),
            "resource_id": event.get("resource_id") or event.get("alarm_name"),
            "config_rule": event.get("config_rule"),
            "resource_type": event.get("resource_type"),
            "finding_id": event.get("finding_id"),
            "detector_id": event.get("detector_id"),
        }

    raise ValueError(
        f"Cannot determine fault_class from event (source={source!r}, "
        f"fault_class={fault_class!r})"
    )


# ===========================================================================
# Evidence collection — dispatches by fault_class
# ===========================================================================

def _collect_evidence(parsed: dict, start_ms: int, end_ms: int) -> dict:
    fault_class = parsed["fault_class"]

    if fault_class == "resource_exhaustion":
        return _collect_resource_exhaustion(parsed, start_ms, end_ms)
    elif fault_class == "misconfiguration":
        return _collect_misconfiguration(parsed, start_ms, end_ms)
    elif fault_class == "service_cascade":
        return _collect_service_cascade(parsed, start_ms, end_ms)
    else:
        raise ValueError(f"Unknown fault_class: {fault_class}")


# ---------------------------------------------------------------------------
# resource_exhaustion evidence
# ---------------------------------------------------------------------------

def _collect_resource_exhaustion(parsed: dict, start_ms: int, end_ms: int) -> dict:
    """
    CW Logs Insights on the triggering Lambda's log group +
    CW Metrics: Duration, Errors, Throttles for the last 15 min.
    """
    alarm_name = parsed.get("alarm_name", "")
    # Infer function name from alarm dimensions if embedded in alarm name.
    # Alarm name format: "incident-service-a-resource-exhaustion-<env>"
    function_name = _infer_function_name_from_alarm(alarm_name)
    log_group = f"/aws/lambda/{function_name}" if function_name else None

    evidence = {
        "fault_class": "resource_exhaustion",
        "alarm_name": alarm_name,
        "function_name": function_name,
        "log_group": log_group,
    }

    # SE-5: If the function name could not be resolved, record the reason explicitly in
    # the evidence bundle so operators know why logs and metrics are missing, instead of
    # silently omitting them and making the LLM diagnose from an incomplete bundle.
    if not function_name:
        evidence["evidence_collection_partial"] = True
        evidence["evidence_collection_reason"] = (
            f"Could not resolve Lambda function name from alarm name '{alarm_name}'. "
            "This may be caused by an IAM permission denial on lambda:ListFunctions, "
            "or because the function naming convention has changed. "
            "Logs and metrics tabs in the Evidence Explorer will be empty."
        )
        logger.warning(json.dumps({
            "event": "function_name_resolution_failed",
            "alarm_name": alarm_name,
            "impact": "logs_insights and metrics will not be collected for this incident",
        }))
    else:
        if log_group:
            evidence["logs_insights"] = _run_logs_insights_query(
                log_groups=[log_group],
                query=(
                    "fields @timestamp, @message, @requestId, @duration, @billedDuration, @maxMemoryUsed "
                    "| filter @type = 'REPORT' or @message like /ERROR/ or @message like /Exception/ "
                    "| sort @timestamp desc "
                    "| limit 50"
                ),
                start_ms=start_ms,
                end_ms=end_ms,
            )

        evidence["metrics"] = _get_lambda_metrics(function_name, start_ms, end_ms)

    return evidence


def _infer_function_name_from_alarm(alarm_name: str) -> str | None:
    """
    Map the known alarm names to Lambda function names.
    Alarm names follow: incident-service-<x>-<type>-<env>
    """
    alarm_name_lower = alarm_name.lower()
    if "service-a" in alarm_name_lower:
        return _resolve_lambda_name("ServiceA")
    if "service-b" in alarm_name_lower:
        return _resolve_lambda_name("ServiceB")
    if "service-c" in alarm_name_lower:
        return _resolve_lambda_name("ServiceC")
    return None


def _resolve_lambda_name(service_prefix: str) -> str | None:
    """
    List Lambda functions and return the one matching our service prefix.
    Uses the SAM naming convention: <stack>-<service>Function-<suffix>
    """
    try:
        paginator = boto3.client("lambda").get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page["Functions"]:
                name = fn["FunctionName"]
                if service_prefix.lower() in name.lower():
                    return name
    except ClientError as exc:
        logger.warning(json.dumps({"event": "resolve_lambda_error", "error": str(exc)}, default=str))
    return None


def _get_lambda_metrics(function_name: str, start_ms: int, end_ms: int) -> dict:
    """
    Fetch Duration, Errors, Throttles, and Invocations for the Lambda function.

    SE-6: Metric names are intentionally stored with lowercase keys (e.g. "duration",
    "errors") to normalise the CloudWatch API's PascalCase names. Any consumer of
    evidence.metrics (frontend Evidence Explorer, evaluation scripts, diagnosis prompts)
    must use lowercase keys. Do NOT change this without updating all consumers.
    """
    from datetime import datetime, timezone  # noqa: PLC0415
    start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)

    metric_specs = [
        ("Duration", "Maximum", "Milliseconds"),
        ("Errors", "Sum", "Count"),
        ("Throttles", "Sum", "Count"),
        ("Invocations", "Sum", "Count"),
    ]

    result = {}
    for metric_name, stat, unit in metric_specs:
        try:
            resp = _cw.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName=metric_name,
                Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                StartTime=start_dt,
                EndTime=end_dt,
                Period=60,
                Statistics=[stat],
                Unit=unit,
            )
            # SE-6: lowercase key - matches what EvidenceTabContent reads in the frontend
            result[metric_name.lower()] = sorted(
                [
                    {"timestamp": str(dp["Timestamp"]), "value": dp[stat]}
                    for dp in resp.get("Datapoints", [])
                ],
                key=lambda x: x["timestamp"],
            )
        except ClientError as exc:
            result[metric_name.lower()] = {"error": str(exc)}

    return result


# ---------------------------------------------------------------------------
# misconfiguration evidence
# ---------------------------------------------------------------------------

def _collect_misconfiguration(parsed: dict, start_ms: int, end_ms: int) -> dict:
    """
    AWS Config compliance details for the flagged rule + resource, plus
    GuardDuty finding detail if the event originated from GuardDuty.
    """
    evidence = {
        "fault_class": "misconfiguration",
        "config_rule": parsed.get("config_rule"),
        "resource_id": parsed.get("resource_id"),
        "resource_type": parsed.get("resource_type"),
    }

    # Config compliance details
    if parsed.get("config_rule"):
        evidence["config_compliance"] = _get_config_compliance(
            rule_name=parsed["config_rule"],
            resource_type=parsed.get("resource_type"),
            resource_id=parsed.get("resource_id"),
        )

    # Resource configuration history from Config
    if parsed.get("resource_type") and parsed.get("resource_id"):
        evidence["resource_config_history"] = _get_resource_config_history(
            resource_type=parsed["resource_type"],
            resource_id=parsed["resource_id"],
        )

    # GuardDuty finding detail
    if parsed.get("source") == "guardduty" and parsed.get("finding_id") and parsed.get("detector_id"):
        evidence["guardduty_finding"] = _get_guardduty_finding(
            detector_id=parsed["detector_id"],
            finding_id=parsed["finding_id"],
        )

    return evidence


def _get_config_compliance(rule_name: str, resource_type: str | None, resource_id: str | None) -> dict:
    try:
        kwargs = {"ConfigRuleName": rule_name, "ComplianceTypes": ["NON_COMPLIANT"], "Limit": 25}
        if resource_type:
            kwargs["Filters"] = {"ResourceType": resource_type}
            if resource_id:
                kwargs["Filters"]["ResourceId"] = resource_id
        resp = _config.get_compliance_details_by_config_rule(**kwargs)
        return {
            "results": [
                {
                    "resource_id": r.get("EvaluationResultIdentifier", {})
                    .get("EvaluationResultQualifier", {})
                    .get("ResourceId"),
                    "resource_type": r.get("EvaluationResultIdentifier", {})
                    .get("EvaluationResultQualifier", {})
                    .get("ResourceType"),
                    "compliance_type": r.get("ComplianceType"),
                    "result_recorded_time": str(r.get("ResultRecordedTime")),
                    "annotation": r.get("Annotation"),
                }
                for r in resp.get("EvaluationResults", [])
            ]
        }
    except ClientError as exc:
        return {"error": str(exc)}


def _get_resource_config_history(resource_type: str, resource_id: str) -> dict:
    try:
        resp = _config.get_resource_config_history(
            resourceType=resource_type,
            resourceId=resource_id,
            limit=5,
        )
        return {
            "items": [
                {
                    "version": item.get("version"),
                    "configuration": item.get("configuration"),
                    "config_capture_time": str(item.get("configurationItemCaptureTime")),
                    "configuration_state_id": item.get("configurationStateId"),
                    "resource_creation_time": str(item.get("resourceCreationTime")),
                    "relationships": item.get("relationships"),
                    "tags": item.get("tags"),
                }
                for item in resp.get("configurationItems", [])
            ]
        }
    except ClientError as exc:
        return {"error": str(exc)}


def _get_guardduty_detector_id() -> str | None:
    """Return the first active GuardDuty detector ID in this account/region."""
    try:
        resp = _guardduty.list_detectors()
        ids = resp.get("DetectorIds", [])
        return ids[0] if ids else None
    except ClientError as exc:
        logger.warning(json.dumps({"event": "guardduty_list_error", "error": str(exc)}, default=str))
        return None


def _get_guardduty_finding(detector_id: str, finding_id: str) -> dict:
    try:
        resp = _guardduty.get_findings(
            DetectorId=detector_id,
            FindingIds=[finding_id],
        )
        findings = resp.get("Findings", [])
        return {"finding": findings[0] if findings else None}
    except ClientError as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# service_cascade evidence
# ---------------------------------------------------------------------------

def _collect_service_cascade(parsed: dict, start_ms: int, end_ms: int) -> dict:
    """
    CW Logs Insights on all 3 service log groups +
    X-Ray trace summaries for the affected service graph.
    """
    from datetime import datetime, timezone  # noqa: PLC0415
    start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)

    # Discover all three Lambda function names
    service_functions = {
        "service_a": _resolve_lambda_name("ServiceA"),
        "service_b": _resolve_lambda_name("ServiceB"),
        "service_c": _resolve_lambda_name("ServiceC"),
    }
    log_groups = [
        f"/aws/lambda/{fn}"
        for fn in service_functions.values()
        if fn
    ]

    evidence = {
        "fault_class": "service_cascade",
        "alarm_name": parsed.get("alarm_name"),
        "service_functions": service_functions,
        "log_groups_queried": log_groups,
    }

    # CW Logs Insights across all service log groups
    if log_groups:
        evidence["logs_insights"] = _run_logs_insights_query(
            log_groups=log_groups,
            query=(
                "fields @timestamp, @log, @message, @requestId "
                "| filter @message like /ERROR/ or @message like /Exception/ or @message like /downstream/ "
                "| sort @timestamp desc "
                "| limit 100"
            ),
            start_ms=start_ms,
            end_ms=end_ms,
        )

    # X-Ray trace summaries
    try:
        resp = _xray.get_trace_summaries(
            StartTime=start_dt,
            EndTime=end_dt,
            TimeRangeType="Event",
            Sampling=False,
            FilterExpression="responsetime > 1",
        )
        summaries = resp.get("TraceSummaries", [])
        evidence["xray_trace_summaries"] = [
            {
                "id": s.get("Id"),
                "duration": s.get("Duration"),
                "response_time": s.get("ResponseTime"),
                "has_fault": s.get("HasFault"),
                "has_error": s.get("HasError"),
                "has_throttle": s.get("HasThrottle"),
                "http": s.get("Http"),
                "users": s.get("Users"),
                "service_ids": s.get("ServiceIds"),
                "entry_point": s.get("EntryPoint"),
            }
            for s in summaries[:25]  # cap at 25 summaries
        ]
        evidence["xray_approximate_traces_processed"] = resp.get("ApproximateTime")
    except ClientError as exc:
        evidence["xray_error"] = str(exc)

    # X-Ray service graph
    try:
        resp = _xray.get_service_graph(
            StartTime=start_dt,
            EndTime=end_dt,
        )
        evidence["xray_service_graph"] = [
            {
                "reference_id": svc.get("ReferenceId"),
                "name": svc.get("Name"),
                "type": svc.get("Type"),
                "edges": svc.get("Edges"),
                "summary_statistics": svc.get("SummaryStatistics"),
                "duration_histogram": svc.get("DurationHistogram"),
                "response_time_histogram": svc.get("ResponseTimeHistogram"),
            }
            for svc in resp.get("Services", [])
        ]
    except ClientError as exc:
        evidence["xray_service_graph_error"] = str(exc)

    return evidence


# ===========================================================================
# CloudWatch Logs Insights helper
# ===========================================================================

def _run_logs_insights_query(
    log_groups: list[str],
    query: str,
    start_ms: int,
    end_ms: int,
) -> dict:
    """Run a CW Logs Insights query and poll until complete, then return results."""
    start_s = start_ms // 1000
    end_s = end_ms // 1000

    try:
        start_resp = _cw_logs.start_query(
            logGroupNames=log_groups,
            startTime=start_s,
            endTime=end_s,
            queryString=query,
            limit=100,
        )
        query_id = start_resp["queryId"]
    except ClientError as exc:
        return {"error": f"Failed to start query: {exc}"}

    # Poll until complete (max CWL_QUERY_MAX_WAIT seconds)
    deadline = time.time() + CWL_QUERY_MAX_WAIT
    while time.time() < deadline:
        time.sleep(2)
        try:
            result_resp = _cw_logs.get_query_results(queryId=query_id)
        except ClientError as exc:
            return {"error": f"Failed to get query results: {exc}"}

        status = result_resp.get("status", "")
        if status in ("Complete", "Failed", "Cancelled"):
            break

    if status != "Complete":
        return {"error": f"Query ended with status: {status}", "query_id": query_id}

    # Flatten field-value pairs into row dicts
    rows = []
    for row in result_resp.get("results", []):
        rows.append({field["field"]: field["value"] for field in row})

    return {
        "query_id": query_id,
        "status": status,
        "statistics": result_resp.get("statistics", {}),
        "rows": rows,
    }


# ===========================================================================
# DynamoDB IncidentRecord (initial write)
# ===========================================================================

def _write_incident_record(
    incident_id: str,
    detected_at: str,
    fault_class: str,
    s3_key: str,
    parsed: dict,
) -> None:
    table = _dynamodb.Table(INCIDENTS_TABLE)
    item = {
        "incident_id": incident_id,
        "fault_class": fault_class,
        "detected_at": detected_at,
        "raw_data_s3_key": s3_key,
        "diagnosis": {
            "root_cause": None,
            "confidence": None,
            "affected_resources": [],
            "suggested_action": None,
            "reasoning_trace": None,
            "used_rag": None,
            "failure_mode": None,
        },
        "remediation": {
            "status": "pending_approval",
            "action_taken": None,
            "executed_at": None,
        },
        "verification": {
            "status": "not_run",
            "checked_at": None,
            "signal_rechecked": None,
            "notes": None,
        },
        "ground_truth": {
            "true_fault_class": None,
            "injected_at": None,
        },
        # Metadata for query convenience
        "detection_source": parsed.get("source", "unknown"),
        "resource_id": parsed.get("resource_id"),
    }
    try:
        table.put_item(Item=item)
        logger.info(json.dumps({
            "event": "dynamodb_written",
            "incident_id": incident_id,
            "table": INCIDENTS_TABLE,
        }))
    except ClientError as exc:
        logger.error(json.dumps({
            "event": "dynamodb_write_error",
            "incident_id": incident_id,
            "error": str(exc),
        }))
        raise


# ===========================================================================
# Async invocation of Diagnosis Lambda
# ===========================================================================

def _invoke_diagnosis(incident_id: str, fault_class: str, s3_key: str) -> None:
    if not DIAGNOSIS_FUNCTION_NAME:
        logger.warning(json.dumps({
            "event": "diagnosis_invoke_skipped",
            "reason": "DIAGNOSIS_FUNCTION_NAME not configured",
        }))
        return

    payload = {
        "incident_id": incident_id,
        "fault_class": fault_class,
        "raw_data_s3_key": s3_key,
    }
    try:
        _lambda.invoke(
            FunctionName=DIAGNOSIS_FUNCTION_NAME,
            InvocationType="Event",  # async — fire and forget
            Payload=json.dumps(payload),
        )
        logger.info(json.dumps({
            "event": "diagnosis_invoked",
            "incident_id": incident_id,
            "function": DIAGNOSIS_FUNCTION_NAME,
        }))
    except ClientError as exc:
        # Log the error but do NOT fail the collector — evidence is already saved.
        logger.error(json.dumps({
            "event": "diagnosis_invoke_error",
            "incident_id": incident_id,
            "error": str(exc),
        }))
