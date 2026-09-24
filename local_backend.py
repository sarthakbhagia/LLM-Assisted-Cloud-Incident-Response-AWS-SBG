#!/usr/bin/env python3
"""
local_backend.py - Full local pipeline runner for LLM-Assisted Cloud Incident Response.

Runs ALL Lambda handlers in-process against real AWS resources (DynamoDB, S3,
Bedrock, CloudWatch). No Docker, SAM, or deployed Lambdas required.

Pipeline stages wired locally:
  collector    -> diagnosis -> notify (async, best-effort)
  approve      -> remediation -> verification (async, 2-min wait in background thread)

Usage:
    pip install boto3 flask flask-cors
    python local_backend.py

Main API runs on http://localhost:3001
Demo API runs on http://localhost:3002 (separate thread)
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import threading
import traceback
import boto3

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("local_backend")

# ---------------------------------------------------------------------------
# Environment config - point at the real dev AWS resources
# Must be set BEFORE importing Lambda handler modules so they pick up the
# values at module load time.
# ---------------------------------------------------------------------------
os.environ.setdefault("INCIDENTS_TABLE", "incidents-staging")
os.environ.setdefault("DATA_LAKE_BUCKET", "llm-incident-datalake-889081505756-staging")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_REGION", "ap-south-1")
os.environ.setdefault("ENVIRONMENT", "staging")

# Inter-Lambda "function names" - used by the LocalLambdaRouter below.
# We set them to well-known sentinel strings that the router recognises.
os.environ.setdefault("DIAGNOSIS_FUNCTION_NAME", "LOCAL::diagnosis")
os.environ.setdefault("NOTIFY_FUNCTION_NAME", "LOCAL::notify")
os.environ.setdefault("REMEDIATION_FUNCTION_NAME", "LOCAL::remediation")
os.environ.setdefault("VERIFICATION_FUNCTION_NAME", "LOCAL::verification")
os.environ.setdefault("APPROVAL_FUNCTION_NAME", "LOCAL::approval")

# Skip HMAC token check in approval handler by leaving the SSM path empty.
# The local approve route bypasses the approval handler entirely and writes
# directly to DynamoDB, then chains the remediation handler.
os.environ.setdefault("APPROVAL_TOKEN_SECRET_SSM", "")

# ---------------------------------------------------------------------------
# LocalLambdaRouter - monkey-patches boto3 lambda client invoke()
# ---------------------------------------------------------------------------
# Any handler module that calls:
#   _lambda.invoke(FunctionName="LOCAL::remediation", Payload=..., InvocationType=...)
# will have its call intercepted here and routed to the in-process handler
# instead of making a real AWS API call.

class LocalLambdaRouter:
    """Routes boto3 lambda.invoke() calls to in-process handler functions."""

    _registry: dict[str, callable] = {}
    _original_invoke = None

    @classmethod
    def register(cls, name: str, fn: callable) -> None:
        cls._registry[name] = fn
        logger.info("[Router] Registered local handler: %s", name)

    @classmethod
    def _local_invoke(cls, FunctionName: str, Payload=b"", InvocationType: str = "RequestResponse", **_kwargs):
        fn = cls._registry.get(FunctionName)
        if fn is None:
            # Not a locally-registered function - fall through to real AWS invoke.
            if cls._original_invoke is not None:
                return cls._original_invoke(
                    FunctionName=FunctionName,
                    Payload=Payload,
                    InvocationType=InvocationType,
                    **_kwargs,
                )
            raise RuntimeError(f"No local handler for '{FunctionName}' and original invoke not saved.")

        if isinstance(Payload, (bytes, bytearray)):
            event = json.loads(Payload.decode())
        elif isinstance(Payload, str):
            event = json.loads(Payload)
        else:
            event = Payload

        if InvocationType == "Event":
            # Async fire-and-forget - run in a daemon thread so it never blocks the caller.
            def _run():
                try:
                    fn(event, {})
                except Exception:
                    logger.exception("[Router] Background handler '%s' raised an exception", FunctionName)

            t = threading.Thread(target=_run, daemon=True, name=f"lambda-{FunctionName.split('::')[-1]}")
            t.start()
            return {"StatusCode": 202, "Payload": io.BytesIO(b"{}")}
        else:
            # RequestResponse - synchronous, block until done.
            try:
                result = fn(event, {})
            except Exception as exc:
                logger.exception("[Router] Sync handler '%s' raised an exception", FunctionName)
                result = {"statusCode": 500, "body": json.dumps({"error": str(exc)})}
            payload_bytes = json.dumps(result).encode()
            return {"StatusCode": 200, "Payload": io.BytesIO(payload_bytes)}

    @classmethod
    def patch(cls) -> None:
        """Monkey-patch the invoke method on all boto3 Lambda clients."""
        import botocore.client
        original = botocore.client.ClientCreator

        # Patch at the botocore level so every boto3.client("lambda") instance
        # created anywhere (including inside handler modules) uses our interceptor.
        _real_make_api_call = botocore.client.BaseClient._make_api_call

        def _patched_make_api_call(self_client, operation_name, api_params):
            if (
                operation_name == "Invoke"
                and self_client.meta.service_model.service_name == "lambda"
            ):
                fn_name = api_params.get("FunctionName", "")
                if fn_name in cls._registry:
                    return cls._local_invoke(
                        FunctionName=fn_name,
                        Payload=api_params.get("Payload", b"{}"),
                        InvocationType=api_params.get("InvocationType", "RequestResponse"),
                    )
            return _real_make_api_call(self_client, operation_name, api_params)

        botocore.client.BaseClient._make_api_call = _patched_make_api_call
        logger.info("[Router] boto3 Lambda invoke() patched - all LOCAL:: calls will route in-process")


# ---------------------------------------------------------------------------
# Import Lambda handler modules
# Must be AFTER env vars are set AND AFTER router patch setup (not yet applied).
# ---------------------------------------------------------------------------
_BACKEND = os.path.join(os.path.dirname(__file__), "backend")

def _add_path(*parts: str) -> None:
    p = os.path.join(_BACKEND, *parts)
    if p not in sys.path:
        sys.path.insert(0, p)

_add_path("dashboard_api")
_add_path("demo_control")
_add_path("collector")
_add_path("diagnosis")
_add_path("approval")
_add_path("remediation")
_add_path("verification")
_add_path("reporting")


def _try_import(module_name: str, label: str):
    try:
        import importlib
        mod = importlib.import_module(module_name)
        logger.info("[OK] Loaded %s", label)
        return mod
    except Exception as exc:
        logger.warning("[WARN] Could not load %s: %s", label, exc)
        return None


dashboard_handler   = _try_import("dashboard_api_lambda",   "dashboard_api_lambda")
demo_handler        = _try_import("demo_control_lambda",    "demo_control_lambda")
collector_handler   = _try_import("collector_lambda",       "collector_lambda")
diagnosis_handler   = _try_import("diagnosis_lambda",       "diagnosis_lambda")
approval_handler_mod = _try_import("approval_handler",      "approval_handler")
remediation_handler = _try_import("remediation_lambda",     "remediation_lambda")
verification_handler = _try_import("verification_lambda",   "verification_lambda")
notify_handler      = _try_import("notify_lambda",          "notify_lambda")

# ---------------------------------------------------------------------------
# Register handlers and apply the monkey-patch
# ---------------------------------------------------------------------------
if collector_handler:
    LocalLambdaRouter.register("LOCAL::collector", collector_handler.lambda_handler)
if diagnosis_handler:
    LocalLambdaRouter.register("LOCAL::diagnosis", diagnosis_handler.lambda_handler)
if notify_handler:
    LocalLambdaRouter.register("LOCAL::notify", notify_handler.lambda_handler)
if approval_handler_mod:
    LocalLambdaRouter.register("LOCAL::approval", approval_handler_mod.lambda_handler)
if remediation_handler:
    LocalLambdaRouter.register("LOCAL::remediation", remediation_handler.lambda_handler)
if verification_handler:
    LocalLambdaRouter.register("LOCAL::verification", verification_handler.lambda_handler)

# Apply the patch AFTER all modules are imported (so we only patch once and
# don't interfere with module-level boto3 client instantiation).
LocalLambdaRouter.patch()

# ---------------------------------------------------------------------------
# Flask setup
# ---------------------------------------------------------------------------
try:
    from flask import Flask, request, jsonify, make_response
    from flask_cors import CORS
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "flask-cors"])
    from flask import Flask, request, jsonify, make_response
    from flask_cors import CORS

# ---------------------------------------------------------------------------
# Helpers shared by both apps
# ---------------------------------------------------------------------------

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def build_event(flask_request, path_params=None, resource=None):
    """Convert a Flask request into an API Gateway proxy event dict."""
    body = flask_request.get_data(as_text=True) or None
    return {
        "httpMethod": flask_request.method,
        "path": flask_request.path,
        "resource": resource or flask_request.path,
        "pathParameters": path_params or {},
        "queryStringParameters": dict(flask_request.args) or None,
        "headers": dict(flask_request.headers),
        "body": body,
        "isBase64Encoded": False,
    }


def cors_preflight():
    resp = make_response("", 204)
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp


def invoke_handler(handler_module, event):
    """Invoke a Lambda handler module and return a Flask response."""
    if event["httpMethod"] == "OPTIONS":
        return cors_preflight()
    if handler_module is None:
        return jsonify({"data": None, "error": "Handler not loaded"}), 500
    try:
        result = handler_module.lambda_handler(event, {})
        status = result.get("statusCode", 200)
        body_raw = result.get("body", "{}")
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
        resp = jsonify(body)
        resp.status_code = status
        for k, v in CORS_HEADERS.items():
            resp.headers[k] = v
        return resp
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"data": None, "error": str(exc)}), 500


def _json_resp(data=None, error=None, status=200):
    """Build a CORS-annotated JSON response in the dashboard envelope format."""
    resp = jsonify({"data": data, "error": error})
    resp.status_code = status
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp


def _run_remediation_pipeline(incident_id: str) -> None:
    """
    Run remediation -> verification in a background thread.
    Called after the DynamoDB status has been set to 'approved'.
    Verification will sleep ~120 s before re-checking the signal - that is by design.
    """
    if remediation_handler is None:
        logger.warning("[Pipeline] remediation_handler not loaded - skipping pipeline for %s", incident_id)
        return

    logger.info("[Pipeline] Starting remediation for incident %s", incident_id)
    try:
        remediation_handler.lambda_handler({"incident_id": incident_id}, {})
    except Exception:
        logger.exception("[Pipeline] Remediation raised for incident %s", incident_id)


# ---------------------------------------------------------------------------
# Main API app (port 3001)
# ---------------------------------------------------------------------------
main_app = Flask("main_api")
CORS(main_app, origins="*")


# ---- Read-only dashboard routes --------------------------------------------

@main_app.route("/api/incidents", methods=["GET", "OPTIONS"])
def get_incidents():
    event = build_event(request, resource="/api/incidents")
    return invoke_handler(dashboard_handler, event)


@main_app.route("/api/incidents/<incident_id>", methods=["GET", "OPTIONS"])
def get_incident(incident_id):
    event = build_event(request, path_params={"incident_id": incident_id},
                        resource="/api/incidents/{incident_id}")
    return invoke_handler(dashboard_handler, event)


@main_app.route("/api/incidents/<incident_id>/evidence", methods=["GET", "OPTIONS"])
def get_evidence(incident_id):
    event = build_event(request, path_params={"incident_id": incident_id},
                        resource="/api/incidents/{incident_id}/evidence")
    return invoke_handler(dashboard_handler, event)


@main_app.route("/api/analytics", methods=["GET", "OPTIONS"])
def get_analytics():
    event = build_event(request, resource="/api/analytics")
    return invoke_handler(dashboard_handler, event)


@main_app.route("/api/runbooks", methods=["GET", "OPTIONS"])
def get_runbooks():
    event = build_event(request, resource="/api/runbooks")
    return invoke_handler(dashboard_handler, event)


@main_app.route("/api/runbooks/<fault_class>", methods=["GET", "OPTIONS"])
def get_runbook(fault_class):
    event = build_event(request, path_params={"fault_class": fault_class},
                        resource="/api/runbooks/{fault_class}")
    return invoke_handler(dashboard_handler, event)


# ---- Approval / rejection routes ------------------------------------------

@main_app.route("/api/incidents/<incident_id>/approve", methods=["POST", "OPTIONS"])
def approve_incident(incident_id):
    """
    Local-dev approve endpoint.
    1. Writes remediation.status = 'approved' to DynamoDB directly (no HMAC).
    2. Spawns a background thread that runs remediation -> verification.

    In production this is handled by the approval Lambda (HMAC token required).
    """
    if request.method == "OPTIONS":
        return cors_preflight()
    try:
        table = boto3.resource("dynamodb").Table(os.environ["INCIDENTS_TABLE"])
        from datetime import datetime, timezone
        table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression="SET remediation.#st = :v, remediation.decided_at = :dt",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":v": "approved",
                ":dt": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info("[Approve] incident %s marked approved - launching pipeline thread", incident_id)

        # Fire remediation pipeline in background (does not block the HTTP response).
        t = threading.Thread(
            target=_run_remediation_pipeline,
            args=(incident_id,),
            daemon=True,
            name=f"pipeline-{incident_id[:8]}",
        )
        t.start()

        return _json_resp(data={
            "incident_id": incident_id,
            "status": "approved",
            "pipeline": "remediation started in background",
        })
    except Exception as exc:
        traceback.print_exc()
        return _json_resp(error=str(exc), status=500)


@main_app.route("/api/incidents/<incident_id>/reject", methods=["POST", "OPTIONS"])
def reject_incident(incident_id):
    """
    Local-dev reject endpoint.
    Writes remediation.status = 'rejected' + optional reason to DynamoDB directly.
    No pipeline is triggered on rejection.

    In production this is handled by the approval Lambda (HMAC token required).
    """
    if request.method == "OPTIONS":
        return cors_preflight()
    try:
        body = request.get_json(silent=True) or {}
        reason = body.get("reason", "")
        table = boto3.resource("dynamodb").Table(os.environ["INCIDENTS_TABLE"])
        from datetime import datetime, timezone
        update_expr = "SET remediation.#st = :v, remediation.decided_at = :dt"
        expr_names = {"#st": "status"}
        expr_vals = {
            ":v": "rejected",
            ":dt": datetime.now(timezone.utc).isoformat(),
        }
        if reason:
            update_expr += ", remediation.reject_reason = :r"
            expr_vals[":r"] = reason
        table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
        )
        logger.info("[Reject] incident %s marked rejected (reason: %r)", incident_id, reason)
        return _json_resp(data={"incident_id": incident_id, "status": "rejected"})
    except Exception as exc:
        traceback.print_exc()
        return _json_resp(error=str(exc), status=500)


# ---- Diagnosis trigger route -----------------------------------------------

@main_app.route("/api/incidents/<incident_id>/diagnose", methods=["POST", "OPTIONS"])
def trigger_diagnosis(incident_id):
    """
    Manually trigger the diagnosis Lambda for an existing incident.
    Fetches the incident from DynamoDB to build the event payload, then
    invokes diagnosis_handler in-process (synchronous so the caller sees the result).
    """
    if request.method == "OPTIONS":
        return cors_preflight()
    if diagnosis_handler is None:
        return _json_resp(error="Diagnosis handler not loaded", status=500)
    try:
        table = boto3.resource("dynamodb").Table(os.environ["INCIDENTS_TABLE"])
        resp = table.get_item(Key={"incident_id": incident_id})
        item = resp.get("Item")
        if not item:
            return _json_resp(error=f"Incident {incident_id!r} not found", status=404)

        s3_key = item.get("raw_data_s3_key", "")

        # SE-10: If the S3 key is missing the diagnosis Lambda will construct a default
        # path and likely get a NoSuchKey error (which now raises RuntimeError), so the
        # diagnosis will correctly return an evidence_fetch_failed status instead of
        # silently producing a heuristic diagnosis from an empty evidence bundle.
        # We still warn here so the operator sees the issue in the local server log.
        if not s3_key:
            logger.warning(
                "[Diagnose] incident %s has no raw_data_s3_key - "
                "diagnosis will attempt default S3 path and likely fail with evidence_fetch_failed",
                incident_id,
            )

        event = {
            "incident_id": incident_id,
            "fault_class": item.get("fault_class", "unknown"),
            "raw_data_s3_key": s3_key,
        }
        logger.info("[Diagnose] manually triggering diagnosis for %s", incident_id)
        result = diagnosis_handler.lambda_handler(event, {})
        body_raw = result.get("body", "{}")
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
        resp_flask = jsonify(body)
        resp_flask.status_code = result.get("statusCode", 200)
        for k, v in CORS_HEADERS.items():
            resp_flask.headers[k] = v
        return resp_flask
    except Exception as exc:
        traceback.print_exc()
        return _json_resp(error=str(exc), status=500)



# ---------------------------------------------------------------------------
# AWS Health checks
# ---------------------------------------------------------------------------

def _probe(name: str, fn, critical: bool = True) -> dict:
    """Run a single probe function and capture latency + result."""
    import time as _time
    start = _time.monotonic()
    try:
        detail = fn()
        latency = round((_time.monotonic() - start) * 1000)
        return {"service": name, "status": "ok", "latency_ms": latency,
                "detail": detail, "critical": critical}
    except Exception as exc:
        latency = round((_time.monotonic() - start) * 1000)
        return {"service": name, "status": "error", "latency_ms": latency,
                "detail": str(exc), "critical": critical}


def _run_aws_health_checks() -> dict:
    """Run all AWS service probes concurrently and aggregate results."""
    import concurrent.futures
    from datetime import datetime, timezone as _tz

    region = os.environ.get("AWS_DEFAULT_REGION", "ap-south-1")
    table_name = os.environ.get("INCIDENTS_TABLE", "")
    bucket = os.environ.get("DATA_LAKE_BUCKET", "")

    probes = [
        # (label, fn, critical)
        ("sts_credentials", lambda: (
            lambda r: f"Account {r['Account']} | ARN: {r['Arn']}"
        )(boto3.client("sts", region_name=region).get_caller_identity()), True),

        ("dynamodb_table", lambda: (
            lambda r: (
                f"Table '{table_name}' | "
                f"status={r['Table']['TableStatus']} | "
                f"items={r['Table'].get('ItemCount', '?')}"
            )
        )(boto3.client("dynamodb", region_name=region).describe_table(TableName=table_name))
        if table_name else "INCIDENTS_TABLE env var not set", True),

        ("s3_bucket", lambda: (
            boto3.client("s3", region_name=region).head_bucket(Bucket=bucket),
            f"Bucket '{bucket}' accessible"
        )[1] if bucket else "DATA_LAKE_BUCKET env var not set", True),

        ("bedrock_runtime", lambda: (
            lambda r: (
                f"Model responded | stop_reason={r.get('stopReason', '?')}"
            )
        )(
            __import__("json").loads(
                boto3.client("bedrock-runtime", region_name=region).invoke_model(
                    modelId="apac.amazon.nova-micro-v1:0",
                    body=__import__("json").dumps({
                        "messages": [{"role": "user", "content": [{"text": "ping"}]}],
                        "inferenceConfig": {"maxTokens": 5},
                    }),
                    contentType="application/json",
                    accept="application/json",
                )["body"].read()
            ).get("output", {})
        ), True),

        ("cloudwatch_alarms", lambda: (
            lambda r: (
                f"{len(r.get('MetricAlarms', []))} alarm(s) visible | "
                f"region={region}"
            )
        )(boto3.client("cloudwatch", region_name=region).describe_alarms(MaxRecords=5)), True),

        ("lambda_functions", lambda: (
            lambda r: (
                f"{len(r.get('Functions', []))} function(s) listed (first page)"
            )
        )(boto3.client("lambda", region_name=region).list_functions(MaxItems=10)), True),

        ("ssm_parameters", lambda: (
            lambda r: (
                f"{r.get('totalCount', '?')} parameters in account (region={region})"
            )
        )(boto3.client("ssm", region_name=region).describe_parameters(MaxResults=1)), False),
    ]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(probes)) as pool:
        futures = {
            pool.submit(_probe, label, fn, critical): label
            for label, fn, critical in probes
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # Sort by service name for deterministic output
    results.sort(key=lambda r: r["service"])

    critical_failures = [r for r in results if r["critical"] and r["status"] == "error"]
    all_ok = len(critical_failures) == 0

    pipeline_status = {
        name.replace("LOCAL::", ""): "loaded"
        for name in LocalLambdaRouter._registry
    }

    return {
        "overall": "ok" if all_ok else "degraded",
        "checked_at": datetime.now(_tz.utc).isoformat(),
        "region": region,
        "services": results,
        "pipeline_handlers": pipeline_status,
        "critical_failures": len(critical_failures),
    }


@main_app.route("/health", methods=["GET"])
def health():
    """Fast health check - server up + handler registration only."""
    registered = {
        name.replace("LOCAL::", ""): "loaded"
        for name in LocalLambdaRouter._registry
    }
    resp = jsonify({
        "status": "ok",
        "server": "local_backend main api",
        "region": os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"),
        "incidents_table": os.environ.get("INCIDENTS_TABLE", ""),
        "pipeline_handlers": registered,
    })
    resp.status_code = 200
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp


@main_app.route("/health/aws", methods=["GET", "OPTIONS"])
def health_aws():
    """
    Deep AWS health check - probes all downstream services concurrently.
    Returns per-service latency, status, and detail message.
    HTTP 200 if all critical services pass, 503 if any critical service fails.
    """
    if request.method == "OPTIONS":
        return cors_preflight()
    try:
        result = _run_aws_health_checks()
        status_code = 200 if result["overall"] == "ok" else 503
        resp = jsonify(result)
        resp.status_code = status_code
        for k, v in CORS_HEADERS.items():
            resp.headers[k] = v
        return resp
    except Exception as exc:
        traceback.print_exc()
        return _json_resp(error=str(exc), status=500)



# ---------------------------------------------------------------------------
# Demo control app (port 3002)
# ---------------------------------------------------------------------------
demo_app = Flask("demo_api")
CORS(demo_app, origins="*")


@demo_app.route("/demo/inject", methods=["POST", "OPTIONS"])
def demo_inject():
    event = build_event(request, resource="/demo/inject")
    return invoke_handler(demo_handler, event)


@demo_app.route("/demo/approve/<incident_id>", methods=["POST", "OPTIONS"])
def demo_approve(incident_id):
    """Demo approve: delegates to the demo_control handler (which uses SSM + HMAC).
    Falls back gracefully if SSM is not configured."""
    event = build_event(request, path_params={"incident_id": incident_id},
                        resource="/demo/approve/{incident_id}")
    return invoke_handler(demo_handler, event)


@demo_app.route("/demo/collect/<incident_id>", methods=["POST", "OPTIONS"])
def demo_collect(incident_id):
    """Manually re-trigger the collector for an existing incident_id."""
    if request.method == "OPTIONS":
        return cors_preflight()
    if collector_handler is None:
        return jsonify({"data": None, "error": "Collector handler not loaded"}), 500
    body = request.get_json(silent=True) or {}
    event = {
        "incident_id": incident_id,
        "fault_class": body.get("fault_class", "resource_exhaustion"),
        "source": body.get("source", "local-trigger"),
    }
    return invoke_handler(collector_handler, event)


@demo_app.route("/demo/diagnose/<incident_id>", methods=["POST", "OPTIONS"])
def demo_diagnose(incident_id):
    """Manually re-trigger diagnosis for an existing incident."""
    if request.method == "OPTIONS":
        return cors_preflight()
    if diagnosis_handler is None:
        return jsonify({"data": None, "error": "Diagnosis handler not loaded"}), 500
    try:
        table = boto3.resource("dynamodb").Table(os.environ["INCIDENTS_TABLE"])
        resp = table.get_item(Key={"incident_id": incident_id})
        item = resp.get("Item")
        if not item:
            return jsonify({"data": None, "error": f"Incident {incident_id!r} not found"}), 404
        s3_key = item.get("raw_data_s3_key", "")
        # SE-10: warn if missing so operator can see it in the log
        if not s3_key:
            logger.warning(
                "[DemoDiagnose] incident %s has no raw_data_s3_key - "
                "diagnosis will attempt default S3 path and likely fail with evidence_fetch_failed",
                incident_id,
            )
        event = {
            "incident_id": incident_id,
            "fault_class": item.get("fault_class", "unknown"),
            "raw_data_s3_key": s3_key,
        }
        return invoke_handler(diagnosis_handler, event)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"data": None, "error": str(exc)}), 500


@demo_app.route("/health", methods=["GET"])
def demo_health():
    return jsonify({"status": "ok", "server": "local_backend demo api"}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# SE-15: Startup validation - fail loudly if any critical handler did not load.
# Without this, the server starts silently and all requests to that stage return
# a 500 error that is easy to miss, especially during active development.
_CRITICAL_HANDLERS = {
    "collector": collector_handler,
    "diagnosis": diagnosis_handler,
    "remediation": remediation_handler,
    "verification": verification_handler,
}
_MISSING_CRITICAL = [name for name, mod in _CRITICAL_HANDLERS.items() if mod is None]

if __name__ == "__main__":
    if _MISSING_CRITICAL:
        print()
        print("=" * 62)
        print("  STARTUP ERROR: Critical handlers failed to load")
        for name in _MISSING_CRITICAL:
            print(f"  MISSING: {name}")
        print()
        print("  These pipeline stages will return 500 for all requests.")
        print("  Fix the import errors above before proceeding.")
        print("=" * 62)
        print()
        # Non-critical handlers (notify, approval, demo) are warnings only.
        # Critical handler failure means the pipeline cannot run at all.
        import sys
        sys.exit(1)

    print("\n" + "=" * 62)
    print("  Local Backend - Full Pipeline Mode")
    print("  Main API  -> http://localhost:3001")
    print("  Demo API  -> http://localhost:3002")
    print("  AWS Region:", os.environ["AWS_DEFAULT_REGION"])
    print("  DynamoDB :", os.environ["INCIDENTS_TABLE"])
    print("  S3 Bucket:", os.environ["DATA_LAKE_BUCKET"])
    print()
    print("  Pipeline handlers registered:")
    for name in LocalLambdaRouter._registry:
        print(f"    {name}")
    if notify_handler is None:
        print("  [WARN] notify_handler not loaded - Slack notifications disabled")
    if approval_handler_mod is None:
        print("  [WARN] approval_handler not loaded - using direct DynamoDB approve route")
    print("=" * 62 + "\n")

    demo_thread = threading.Thread(
        target=lambda: demo_app.run(host="0.0.0.0", port=3002, debug=False, use_reloader=False),
        daemon=True,
        name="demo-api",
    )
    demo_thread.start()
    print("[INFO] Demo API started on port 3002")

    # Main API in the main thread (debug=True enables auto-reload on save,
    # use_reloader=False prevents the process from forking which would break
    # our monkey-patch and background threads).
    main_app.run(host="0.0.0.0", port=3001, debug=True, use_reloader=False)
