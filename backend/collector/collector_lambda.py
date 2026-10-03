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
            "injected_by": event.get("injected_by"),
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
            "injected_by": event.get("injected_by"),
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
            "injected_by": event.get("injected_by"),
        }

    raise ValueError(
        f"Cannot determine fault_class from event (source={source!r}, "
        f"fault_class={fault_class!r})"
    )


# ===========================================================================
# Evidence collection — dispatches by fault_class
# ===========================================================================

def _get_alarm_thresholds(alarm_name: str) -> dict:
    """Fetch CloudWatch alarm definition and extract threshold info."""
    if not alarm_name:
        return {}
    try:
        resp = _cw.describe_alarms(AlarmNames=[alarm_name])
        alarms = resp.get("MetricAlarms", [])
        if not alarms:
            return {}
        alarm = alarms[0]
        return {
            "metric_name": alarm.get("MetricName"),
            "namespace": alarm.get("Namespace"),
            "threshold": alarm.get("Threshold"),
            "comparison_operator": alarm.get("ComparisonOperator"),
            "period": alarm.get("Period"),
            "evaluation_periods": alarm.get("EvaluationPeriods"),
            "datapoints_to_alarm": alarm.get("DatapointsToAlarm"),
            "statistic": alarm.get("Statistic"),
            "dimensions": alarm.get("Dimensions"),
            "treat_missing_data": alarm.get("TreatMissingData"),
        }
    except ClientError as exc:
        logger.warning(json.dumps({"event": "describe_alarm_error", "alarm_name": alarm_name, "error": str(exc)}, default=str))
        return {}


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

    # Add alarm thresholds for frontend threshold lines
    alarm_thresholds = _get_alarm_thresholds(alarm_name)
    if alarm_thresholds:
        evidence["alarm_thresholds"] = alarm_thresholds

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

        # Demo mode: if the demo control injected this alarm but no real Lambda traffic
        # existed in the collection window (common because SetAlarmState does not invoke
        # the function), fill in clearly-labelled synthetic telemetry so the Evidence
        # Explorer has data to render. This only fires when ALL metric series are empty
        # AND the event was explicitly injected by demo_mode.
        is_demo = parsed.get("injected_by") == "demo_mode"
        if is_demo and _all_metrics_empty(evidence.get("metrics", {})):
            synthetic = _make_synthetic_resource_exhaustion_evidence(end_ms, function_name)
            evidence["metrics"] = synthetic["metrics"]
            evidence["logs_insights"] = synthetic["logs_insights"]
            evidence["demo_synthetic"] = True
            evidence["demo_synthetic_reason"] = (
                "Demo mode: no real Lambda invocations occurred in the 15-minute collection window "
                "because SetAlarmState does not trigger a Lambda execution. "
                "This data is illustrative only and shows what a real resource-exhaustion incident would look like."
            )
            logger.info(json.dumps({
                "event": "demo_synthetic_evidence_injected",
                "function_name": function_name,
                "reason": "all_metrics_empty_demo_mode",
            }))

    return evidence


def _all_metrics_empty(metrics: dict) -> bool:
    """Return True if every metric series in the dict is an empty list."""
    if not metrics:
        return True
    return all(isinstance(v, list) and len(v) == 0 for v in metrics.values())


def _make_synthetic_resource_exhaustion_evidence(end_ms: int, function_name: str) -> dict:
    """
    Build realistic-looking synthetic evidence for a resource_exhaustion demo incident.

    The Duration series escalates from ~3 s to beyond the 50,000 ms alarm threshold,
    with matching Errors and Invocations. Log rows include REPORT lines that mirror
    what CloudWatch Logs Insights returns for a real runaway Lambda.

    All timestamps are anchored to the 15-minute window ending at end_ms so the
    chart x-axis aligns with the incident detection time.
    """
    from datetime import datetime, timezone as tz  # noqa: PLC0415

    # Build 15 one-minute datapoints ending at end_ms
    end_s = end_ms // 1000
    # Duration escalation: starts normal (~3 s), then spikes past 50 s
    duration_values = [
        3100, 3250, 3800, 5200, 8400, 14300, 22100, 35600, 51200, 58900,
        61400, 59800, 57200, 55000, 53100,
    ]
    # One error in the middle of the spike; invocations stay constant
    error_values =    [0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 3, 2, 1, 1, 1]
    throttle_values = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0]
    invocation_values = [12, 11, 13, 12, 11, 10, 10, 9, 8, 8, 7, 8, 8, 9, 10]

    n = len(duration_values)
    metrics = {"duration": [], "errors": [], "throttles": [], "invocations": []}
    log_rows = []

    for i in range(n):
        ts_s = end_s - (n - 1 - i) * 60
        ts_iso = datetime.fromtimestamp(ts_s, tz=tz.utc).strftime("%Y-%m-%d %H:%M:%S.000")
        ts_str = datetime.fromtimestamp(ts_s, tz=tz.utc).isoformat()

        metrics["duration"].append({"timestamp": ts_str, "value": duration_values[i]})
        metrics["errors"].append({"timestamp": ts_str, "value": error_values[i]})
        metrics["throttles"].append({"timestamp": ts_str, "value": throttle_values[i]})
        metrics["invocations"].append({"timestamp": ts_str, "value": invocation_values[i]})

        # Generate a REPORT log row for each datapoint
        billed = min(duration_values[i] + 100, 900000)
        log_rows.append({
            "@timestamp": ts_iso,
            "@message": (
                f"REPORT RequestId: demo-{i:04x}-{ts_s % 0xFFFF:04x}\t"
                f"Duration: {duration_values[i]:.2f} ms\t"
                f"Billed Duration: {billed} ms\t"
                f"Memory Size: 512 MB\t"
                f"Max Memory Used: {280 + i * 8} MB"
            ),
            "@requestId": f"demo-{i:04x}-{ts_s % 0xFFFF:04x}",
            "@duration": str(duration_values[i]),
            "@billedDuration": str(billed),
            "@maxMemoryUsed": str(280 + i * 8),
        })
        # Add ERROR rows for the spike period
        if error_values[i] > 0:
            log_rows.append({
                "@timestamp": ts_iso,
                "@message": (
                    f"[ERROR] RequestId: demo-err-{i:04x}\t"
                    f"Task timed out after {duration_values[i] / 1000:.2f} seconds"
                ),
                "@requestId": f"demo-err-{i:04x}",
            })

    return {
        "metrics": metrics,
        "logs_insights": {
            "status": "Complete",
            "rows": log_rows,
            "bytesScanned": len(log_rows) * 220,
            "demo_synthetic": True,
        },
    }


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
    try:
        paginator = _lambda.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page["Functions"]:
                name = fn["FunctionName"]
                if service_prefix.lower() in name.lower():
                    # If we are in dev (indicated by incidents-dev table), skip staging functions
                    incidents_table = os.environ.get("INCIDENTS_TABLE", "")
                    if "dev" in incidents_table and "staging" in name.lower():
                        continue
                    return name
    except ClientError as exc:
        logger.warning(json.dumps({"event": "resolve_lambda_error", "service_prefix": service_prefix, "error": str(exc)}, default=str))
    except Exception as exc:
        logger.error(json.dumps({"event": "resolve_lambda_unexpected_error", "service_prefix": service_prefix, "error": str(exc), "error_type": type(exc).__name__}, default=str))
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

    # Demo mode: Config events injected by demo_mode query the same real AWS Config
    # backend, but the demo resource was already remediated (Public Access Block applied),
    # so NON_COMPLIANT results are empty. Fill in synthetic Config evidence so the Config
    # tab has something to display. Guard: injected_by == "demo_mode" AND results empty.
    is_demo = parsed.get("injected_by") == "demo_mode"
    config_results = evidence.get("config_compliance", {}).get("results", [])
    if is_demo and not config_results:
        synthetic = _make_synthetic_misconfiguration_evidence(
            resource_id=parsed.get("resource_id", "demo-bucket"),
            resource_type=parsed.get("resource_type", "AWS::S3::Bucket"),
            config_rule=parsed.get("config_rule", "demo-config-rule"),
        )
        evidence["config_compliance"] = synthetic["config_compliance"]
        evidence["resource_config_history"] = synthetic["resource_config_history"]
        evidence["demo_synthetic"] = True
        evidence["demo_synthetic_reason"] = (
            "Demo mode: the demo bucket was already remediated (Public Access Block is enabled), "
            "so AWS Config reports zero NON_COMPLIANT resources. "
            "This data is illustrative only and shows what a real public-S3 misconfiguration incident would look like."
        )
        logger.info(json.dumps({
            "event": "demo_synthetic_evidence_injected",
            "fault_class": "misconfiguration",
            "reason": "config_results_empty_demo_mode",
        }))

    return evidence


def _make_synthetic_misconfiguration_evidence(resource_id: str, resource_type: str, config_rule: str) -> dict:
    """
    Generate realistic synthetic Config evidence for a misconfiguration demo incident.

    Shows an S3 bucket that has public access enabled (no Public Access Block),
    with a configuration history showing the bucket was created without the block
    and was later misconfigured via a bucket policy change.
    """
    from datetime import datetime, timezone as tz, timedelta  # noqa: PLC0415

    now = datetime.now(tz=tz.utc)
    created_at = (now - timedelta(hours=48)).isoformat()
    misconfigured_at = (now - timedelta(minutes=45)).isoformat()

    return {
        "config_compliance": {
            "results": [
                {
                    "resource_id": resource_id,
                    "resource_type": resource_type,
                    "compliance_type": "NON_COMPLIANT",
                    "result_recorded_time": misconfigured_at,
                    "annotation": (
                        "S3 bucket has public read access enabled via bucket ACL. "
                        "BlockPublicAcls and BlockPublicPolicy are both disabled. "
                        "Objects in this bucket may be accessible to the public internet."
                    ),
                }
            ],
            "demo_synthetic": True,
        },
        "resource_config_history": {
            "items": [
                {
                    "version": "1.3",
                    "config_capture_time": misconfigured_at,
                    "configuration_state_id": "3",
                    "resource_creation_time": created_at,
                    "configuration": (
                        '{"BlockPublicAcls": false, "IgnorePublicAcls": false, '
                        '"BlockPublicPolicy": false, "RestrictPublicBuckets": false}'
                    ),
                    "relationships": [],
                    "tags": {"Environment": "demo", "ManagedBy": "terraform"},
                },
                {
                    "version": "1.2",
                    "config_capture_time": created_at,
                    "configuration_state_id": "2",
                    "resource_creation_time": created_at,
                    "configuration": (
                        '{"BlockPublicAcls": true, "IgnorePublicAcls": true, '
                        '"BlockPublicPolicy": true, "RestrictPublicBuckets": true}'
                    ),
                    "relationships": [],
                    "tags": {"Environment": "demo", "ManagedBy": "terraform"},
                },
            ],
            "demo_synthetic": True,
        },
    }


def _get_config_compliance(rule_name: str, resource_type: str | None, resource_id: str | None) -> dict:
    """
    Fetch NON_COMPLIANT evaluation results for a Config rule.

    NOTE: get_compliance_details_by_config_rule does NOT accept a Filters parameter.
    We fetch all NON_COMPLIANT results and filter by resource_type/resource_id in Python.
    """
    try:
        # No Filters argument — the API does not support it; filter post-fetch instead.
        resp = _config.get_compliance_details_by_config_rule(
            ConfigRuleName=rule_name,
            ComplianceTypes=["NON_COMPLIANT"],
            Limit=25,
        )
        results = []
        for r in resp.get("EvaluationResults", []):
            qualifier = (
                r.get("EvaluationResultIdentifier", {})
                .get("EvaluationResultQualifier", {})
            )
            r_resource_id = qualifier.get("ResourceId")
            r_resource_type = qualifier.get("ResourceType")
            # Filter in Python when a specific resource was provided
            if resource_type and r_resource_type != resource_type:
                continue
            if resource_id and r_resource_id not in (resource_id, None):
                continue
            results.append({
                "resource_id": r_resource_id,
                "resource_type": r_resource_type,
                "compliance_type": r.get("ComplianceType"),
                "result_recorded_time": str(r.get("ResultRecordedTime")),
                "annotation": r.get("Annotation"),
            })
        return {"results": results}
    except ClientError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # catches ParamValidationError and any other boto3 issue
        return {"error": f"Config API error: {exc}"}


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

    # Add alarm thresholds for the composite alarm and component alarms
    composite_alarm_name = parsed.get("alarm_name", "")
    alarm_thresholds = _get_alarm_thresholds(composite_alarm_name)
    if alarm_thresholds:
        evidence["alarm_thresholds"] = alarm_thresholds

    # Also fetch component alarm thresholds for service_cascade
    env = os.environ.get("ENVIRONMENT", "dev")
    component_alarms = [
        f"incident-service-a-errors-{env}",
        f"incident-service-c-latency-{env}",
    ]
    for ca in component_alarms:
        ca_thresholds = _get_alarm_thresholds(ca)
        if ca_thresholds:
            evidence.setdefault("component_alarm_thresholds", {})[ca] = ca_thresholds

    # CW Logs Insights across all service log groups
    # Filter to only groups that exist: including a non-existent group in the query
    # causes a ResourceNotFoundException and fails the whole query (not just that group).
    existing_log_groups = []
    for lg in log_groups:
        try:
            resp = _cw_logs.describe_log_groups(logGroupNamePrefix=lg, limit=1)
            if any(g["logGroupName"] == lg for g in resp.get("logGroups", [])):
                existing_log_groups.append(lg)
            else:
                logger.warning(json.dumps({"event": "log_group_not_found", "log_group": lg}))
        except ClientError as exc:
            logger.warning(json.dumps({"event": "log_group_describe_error", "log_group": lg, "error": str(exc)}))

    if existing_log_groups:
        evidence["logs_insights"] = _run_logs_insights_query(
            log_groups=existing_log_groups,
            query=(
                "fields @timestamp, @log, @message, @requestId "
                "| filter @message like /ERROR/ or @message like /Exception/ or @message like /downstream/ "
                "| sort @timestamp desc "
                "| limit 100"
            ),
            start_ms=start_ms,
            end_ms=end_ms,
        )
    else:
        evidence["logs_insights"] = {
            "status": "Skipped",
            "rows": [],
            "reason": "No service log groups exist yet (Lambda functions may not have been invoked).",
        }


    # CloudWatch metrics for every resolved service function.
    # Flattened into evidence["metrics"] as { "service_a_duration": [...], "service_a_errors": [...], ... }
    # so the frontend EvidenceTabContent metrics tab can chart them directly — it expects
    # evidence["metrics"] to be a flat dict where each value is an array of {timestamp, value} points.
    flat_metrics = {}
    for svc_key, fn_name in service_functions.items():
        if fn_name:
            svc_metrics = _get_lambda_metrics(fn_name, start_ms, end_ms)
            for metric_key, datapoints in svc_metrics.items():
                flat_metrics[f"{svc_key}_{metric_key}"] = datapoints
    if flat_metrics:
        evidence["metrics"] = flat_metrics

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

    # Demo mode: if the demo control injected this event but no real inter-service
    # traffic occurred (the demo only calls SetAlarmState / direct collector invoke,
    # it does not actually invoke Service A), all metric series and log rows will be
    # empty. Fill in synthetic telemetry so the Evidence Explorer has data to render.
    # Guard: only fires when injected_by == "demo_mode" AND all collected metrics empty.
    is_demo = parsed.get("injected_by") == "demo_mode"
    if is_demo and _all_metrics_empty(evidence.get("metrics", {})):
        synthetic = _make_synthetic_service_cascade_evidence(end_ms, service_functions)
        evidence["metrics"] = synthetic["metrics"]
        evidence["logs_insights"] = synthetic["logs_insights"]
        evidence["xray_trace_summaries"] = synthetic["xray_trace_summaries"]
        evidence["demo_synthetic"] = True
        evidence["demo_synthetic_reason"] = (
            "Demo mode: no real inter-service traffic occurred in the 15-minute collection window "
            "because the demo only injects an alarm state change — it does not invoke Service A. "
            "This data is illustrative only and shows what a real service-cascade incident would look like."
        )
        logger.info(json.dumps({
            "event": "demo_synthetic_evidence_injected",
            "fault_class": "service_cascade",
            "reason": "all_metrics_empty_demo_mode",
        }))

    return evidence


def _make_synthetic_service_cascade_evidence(end_ms: int, service_functions: dict) -> dict:
    """
    Generate realistic synthetic evidence for a service_cascade demo incident.

    Service C develops latency first (slow DB), which causes Service B to time out,
    which causes Service A to error and raise. Metrics escalate over 15 minutes.
    All timestamps are anchored to the real collection window end so charts align.
    """
    from datetime import datetime, timezone as tz  # noqa: PLC0415

    end_s = end_ms // 1000
    n = 15  # one datapoint per minute

    # service_a: errors spike after service_b starts failing (~minute 8)
    svc_a_errors =       [0, 0, 0, 0, 0, 0, 0, 1, 3, 5, 6, 6, 5, 4, 4]
    svc_a_duration =     [320, 330, 315, 340, 325, 330, 5100, 5050, 5020, 5030, 5010, 5040, 5020, 5000, 5010]
    svc_a_invocations =  [10, 11, 10, 12, 11, 10, 10, 9, 8, 8, 7, 7, 8, 9, 9]
    svc_a_throttles =    [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0]

    # service_b: errors start ~minute 7, duration spikes due to downstream timeout
    svc_b_errors =       [0, 0, 0, 0, 0, 0, 1, 3, 4, 5, 5, 5, 4, 3, 3]
    svc_b_duration =     [210, 215, 220, 210, 215, 3800, 5000, 5020, 5010, 5000, 5010, 5000, 4990, 5000, 4980]
    svc_b_invocations =  [10, 11, 10, 12, 11, 10, 10, 9, 8, 8, 7, 7, 8, 9, 9]
    svc_b_throttles =    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    # service_c: latency climbs steadily (slow downstream DB), no hard errors
    svc_c_errors =       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    svc_c_duration =     [180, 210, 350, 620, 980, 1800, 2900, 3800, 4500, 5100, 5300, 5200, 5100, 5050, 5020]
    svc_c_invocations =  [10, 11, 10, 12, 11, 10, 10, 9, 8, 8, 7, 7, 8, 9, 9]
    svc_c_throttles =    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0]

    series_map = {
        "service_a": {"errors": svc_a_errors, "duration": svc_a_duration,
                      "invocations": svc_a_invocations, "throttles": svc_a_throttles},
        "service_b": {"errors": svc_b_errors, "duration": svc_b_duration,
                      "invocations": svc_b_invocations, "throttles": svc_b_throttles},
        "service_c": {"errors": svc_c_errors, "duration": svc_c_duration,
                      "invocations": svc_c_invocations, "throttles": svc_c_throttles},
    }

    metrics: dict = {}
    log_rows = []
    xray_traces = []

    for i in range(n):
        ts_s = end_s - (n - 1 - i) * 60
        ts_str = datetime.fromtimestamp(ts_s, tz=tz.utc).isoformat()
        ts_iso = datetime.fromtimestamp(ts_s, tz=tz.utc).strftime("%Y-%m-%d %H:%M:%S.000")

        for svc_key, series in series_map.items():
            for metric_key, values in series.items():
                flat_key = f"{svc_key}_{metric_key}"
                metrics.setdefault(flat_key, []).append({"timestamp": ts_str, "value": values[i]})

        # Log rows: generate ERROR entries for services that have errors at this minute
        for svc_key, series in series_map.items():
            err_count = series["errors"][i]
            dur = series["duration"][i]
            fn_name = service_functions.get(svc_key) or f"demo-{svc_key}"
            # Always emit a REPORT row
            log_rows.append({
                "@timestamp": ts_iso,
                "@log": f"/aws/lambda/{fn_name}",
                "@message": (
                    f"REPORT RequestId: demo-{svc_key[8:]}-{i:04x}\t"
                    f"Duration: {dur:.1f} ms\tBilled Duration: {dur + 100} ms\t"
                    f"Memory Size: 256 MB\tMax Memory Used: 145 MB"
                ),
                "@requestId": f"demo-{svc_key[8:]}-{i:04x}",
            })
            if err_count > 0:
                if svc_key == "service_a":
                    msg = f"[ERROR] Service A downstream failure: Service B timed out after {dur:.0f} ms"
                elif svc_key == "service_b":
                    msg = f"[ERROR] Service B downstream request to Service C timed out after {dur:.0f} ms"
                else:
                    msg = f"[ERROR] Service C database query exceeded latency budget: {dur:.0f} ms"
                log_rows.append({
                    "@timestamp": ts_iso,
                    "@log": f"/aws/lambda/{fn_name}",
                    "@message": msg,
                    "@requestId": f"demo-err-{svc_key[8:]}-{i:04x}",
                })

        # Synthetic X-Ray trace for minutes where errors exist
        if svc_a_errors[i] > 0:
            xray_traces.append({
                "id": f"demo-trace-{i:04x}-{ts_s % 0xFFFF:04x}",
                "duration": round(svc_a_duration[i] / 1000, 3),
                "response_time": round(svc_a_duration[i] / 1000, 3),
                "has_fault": True,
                "has_error": True,
                "has_throttle": svc_a_throttles[i] > 0,
                "http": {"response": {"status": 500}},
                "service_ids": [
                    {"name": "service-a", "type": "AWS::Lambda::Function"},
                    {"name": "service-b", "type": "AWS::Lambda::Function"},
                    {"name": "service-c", "type": "AWS::Lambda::Function"},
                ],
                "entry_point": {"name": "service-a", "type": "AWS::Lambda::Function"},
            })

    return {
        "metrics": metrics,
        "logs_insights": {
            "status": "Complete",
            "rows": log_rows,
            "bytesScanned": len(log_rows) * 180,
            "demo_synthetic": True,
        },
        "xray_trace_summaries": xray_traces,
    }


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
        # For misconfiguration faults: the Config rule name that triggered the event.
        # Stored here so remediation_lambda can pass the correct rule name to verification
        # without needing to re-derive it from resource_id (which is the bucket name).
        "config_rule": parsed.get("config_rule"),
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
