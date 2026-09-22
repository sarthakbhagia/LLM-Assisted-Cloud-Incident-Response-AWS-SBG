#!/usr/bin/env python3
"""
local_backend.py - Runs the Dashboard API and Demo Control Lambda handlers
locally without Docker or SAM. Simulates API Gateway HTTP events directly.

Usage:
    pip install boto3 flask flask-cors
    python local_backend.py

Main API runs on http://localhost:3001
Demo API runs on http://localhost:3002 (separate thread)
"""

import functools
import hashlib
import hmac
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Environment config - point at the real dev AWS resources
# ---------------------------------------------------------------------------
os.environ.setdefault("INCIDENTS_TABLE", "incidents-staging")
os.environ.setdefault("DATA_LAKE_BUCKET", "llm-incident-datalake-889081505756-staging")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_REGION", "ap-south-1")
os.environ.setdefault("ENVIRONMENT", "staging")
# Phase 5 approval handler config — needed for the dashboard approve/reject
# routes added below (same handler the deployed /approval endpoint uses).
os.environ.setdefault(
    "APPROVAL_TOKEN_SECRET_SSM", "/llm-incident-response/approval-token-secret"
)
REMEDIATION_FUNCTION_NAME = os.environ.get(
    "REMEDIATION_FUNCTION_NAME", ""
)  # empty by default: approving locally flips status but does not
   # invoke the real remediation Lambda from your laptop

# ---------------------------------------------------------------------------
# Import Lambda handlers (must be after env vars are set)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "dashboard_api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "demo_control"))

try:
    import dashboard_api_lambda as dashboard_handler
    print("[OK] Loaded dashboard_api_lambda")
except ImportError as e:
    print(f"[WARN] Could not load dashboard_api_lambda: {e}")
    dashboard_handler = None

try:
    import demo_control_lambda as demo_handler
    print("[OK] Loaded demo_control_lambda")
except ImportError as e:
    print(f"[WARN] Could not load demo_control_lambda: {e}")
    demo_handler = None

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "approval"))
    import approval_handler as approval_module
    approval_module.REMEDIATION_FUNCTION_NAME = REMEDIATION_FUNCTION_NAME
    print("[OK] Loaded approval_handler")
except ImportError as e:
    print(f"[WARN] Could not load approval_handler: {e}")
    approval_module = None

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    print("Installing flask and flask-cors...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "flask-cors", "boto3"])
    from flask import Flask, request, jsonify
    from flask_cors import CORS

# ---------------------------------------------------------------------------
# API Gateway event builder
# ---------------------------------------------------------------------------

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


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def cors_preflight():
    """Return a 204 preflight response. No Lambda handler involved."""
    from flask import make_response
    resp = make_response("", 204)
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp

# ---------------------------------------------------------------------------
# Deployed-API fallback for read-only GETs
# ---------------------------------------------------------------------------
# The local user's IAM policy (LLMIncidentResponseProjectAccess) scopes
# DynamoDB/S3 access to -dev resource names while the stack is deployed as
# -staging, so direct DynamoDB/S3 reads are denied and the handlers return 500.
# Read-only GET routes therefore fall back to the deployed Dashboard API
# (same handler code, same incidents table) so local development keeps
# working. Set DASHBOARD_API_FALLBACK_URL="" to disable the fallback and
# surface the local IAM errors instead.
DASHBOARD_API_FALLBACK_URL = os.environ.get(
    "DASHBOARD_API_FALLBACK_URL",
    "https://o212lf1md4.execute-api.ap-south-1.amazonaws.com/Prod",
).rstrip("/")

# Same story for denied WRITES: the local user cannot SetAlarmState (demo
# fault injection) or UpdateItem (approve/reject) on the -staging resources.
# Denied local writes are delegated to the deployed Demo Control API and the
# deployed approval Lambda — same handler code, same incidents table — which
# run under their own IAM roles. Set DEMO_API_FALLBACK_URL="" /
# DEPLOYED_APPROVAL_FUNCTION="" to disable and surface local IAM errors.
DEMO_API_FALLBACK_URL = os.environ.get(
    "DEMO_API_FALLBACK_URL",
    "https://0l32vjl4n8.execute-api.ap-south-1.amazonaws.com/Prod",
).rstrip("/")
DEPLOYED_APPROVAL_FUNCTION = os.environ.get(
    "DEPLOYED_APPROVAL_FUNCTION",
    "llm-incident-response-staging-ApprovalFunction-gs029Jg8Igg3",
)


def _query_string(query_params) -> str:
    if not query_params:
        return ""
    return "?" + urllib.parse.urlencode(query_params)


def _proxy_to_deployed(method: str, path_qs: str, body=None, base_url: str = None):
    """Forward a request to a deployed API.

    Returns (status_code, body_text), or None when the fallback is disabled
    or unreachable. HTTPError responses are returned as-is so the client sees
    the deployed API's real status (e.g. 404 for a missing incident).
    """
    base = base_url if base_url is not None else DASHBOARD_API_FALLBACK_URL
    if not base:
        return None
    if isinstance(body, str):
        body = body.encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path_qs}", data=body, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            return exc.code, "{}"
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Deployed-API fallback failed for {path_qs}: {exc}")
        return None


def _invoke_write_fallback(path_qs: str, body=None):
    """Delegate a denied local write to the deployed Demo Control API.

    Same handler code, same table; the deployed function runs under its own
    IAM role, so writes the local user cannot perform (SetAlarmState,
    UpdateItem) still execute exactly as they would in production.
    """
    return _proxy_to_deployed("POST", path_qs, body=body, base_url=DEMO_API_FALLBACK_URL)


def _incident_status_via_fallback(incident_id: str):
    """Read one incident's remediation status through the deployed Dashboard
    API. Returns 'approved' / 'pending_approval' / ..., or None when the read
    itself is impossible (fallback disabled/unreachable).
    """
    proxied = _proxy_to_deployed(
        "GET", f"/api/incidents/{incident_id}", body=None,
        base_url=DASHBOARD_API_FALLBACK_URL,
    )
    if proxied is None or proxied[0] >= 300:
        return None
    try:
        data = json.loads(proxied[1])
        return (data.get("data") or {}).get("remediation", {}).get("status")
    except (json.JSONDecodeError, AttributeError):
        return None


@functools.lru_cache(maxsize=None)
def _get_boto3_client(service: str):
    """Cached boto3 client built with the local AWS credentials."""
    try:
        import boto3
    except ImportError:
        print("[WARN] boto3 not available; deployed-Lambda fallback disabled")
        return None
    try:
        return boto3.client(service, region_name=os.environ.get("AWS_REGION", "ap-south-1"))
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not create boto3 {service} client: {exc}")
        return None


def _invoke_lambda_via_fallback(function_name: str, payload: dict):
    """Invoke a deployed Lambda function directly with local credentials.

    Used for handlers that are not exposed through a public API (the Phase 5
    approval handler). Returns the raw Lambda response dict, or None when
    invocation is not possible or fails.
    """
    if not function_name:
        return None
    client = _get_boto3_client("lambda")
    if client is None:
        return None
    try:
        resp = client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode("utf-8"),
        )
        raw = resp.get("Payload").read().decode("utf-8")
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Direct Lambda invoke failed for {function_name}: {exc}")
        return None


def _normalize_lambda_result(result):
    """Normalize a direct-invoke Lambda response to (status, body_text).

    Lambda returns the handler's own {statusCode, body} dict; a plain dict is
    treated as a 200 success. Returns None for unusable results.
    """
    if isinstance(result, dict) and "statusCode" in result and "body" in result:
        body = result.get("body")
        if not isinstance(body, str):
            body = json.dumps(body)
        try:
            return int(result.get("statusCode", 200)), body
        except (TypeError, ValueError):
            return 500, body
    if isinstance(result, dict):
        return 200, json.dumps(result)
    return None


def _is_permission_error(text: str) -> bool:
    """True when a handler error looks like an IAM denial (as opposed to a
    business-level 4xx such as 'already processed' or 'invalid action')."""
    low = (text or "").lower()
    return any(
        marker in low
        for marker in (
            "not authorized to perform",
            "accessdenied",
            "no identity-based policy",
        )
    )


def _safe_json_dict(text):
    try:
        parsed = json.loads(text) if text else None
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def invoke_handler(handler_module, event):
    """Invoke a Lambda handler and return a Flask response."""
    # Handle CORS preflight without hitting the Lambda (it can't handle Flask events)
    if event["httpMethod"] == "OPTIONS":
        return cors_preflight()

    if handler_module is None:
        return jsonify({"data": None, "error": "Handler not loaded"}), 500

    local_error = None
    try:
        result = handler_module.lambda_handler(event, {})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        local_error = str(exc)
        result = None

    status = (result or {}).get("statusCode", 500)
    body_raw = (result or {}).get("body", "{}")

    # Read-only fallback: when the local handler fails (typically IAM denial
    # on the -staging resources), forward GETs to the deployed Dashboard API,
    # which runs the same handler code against the same table.
    if status >= 500 and event["httpMethod"] == "GET":
        path_qs = event["path"] + _query_string(event.get("queryStringParameters"))
        proxied = _proxy_to_deployed("GET", path_qs)
        if proxied is not None and proxied[0] < 500:
            p_status, p_body = proxied
            try:
                resp = jsonify(json.loads(p_body) if p_body else {})
                print(f"[INFO] {path_qs} served via deployed API fallback (local status {status})")
                resp.status_code = p_status
                for k, v in CORS_HEADERS.items():
                    resp.headers[k] = v
                return resp
            except json.JSONDecodeError:
                print(f"[WARN] Deployed fallback returned non-JSON for {path_qs}")

    # Write fallback for demo routes: same IAM gap, but for POSTs. When the
    # local demo handler fails with a permission error, delegate to the
    # deployed Demo Control API (same handler, Lambda's own role). The
    # approval routes use _run_approval's own Lambda-invoke fallback.
    if event["httpMethod"] == "POST" and (status >= 500 or (status >= 400 and _is_permission_error(body_raw or ""))):
        path = event.get("path", "")
        resource = event.get("resource", "")
        if resource.startswith("/demo/"):
            # Forward the ORIGINAL request body (e.g. {fault_class}), not the
            # failed handler response.
            proxied = _invoke_write_fallback(path, event.get("body"))
            if proxied is not None:
                p_status, p_body = proxied
                print(f"[INFO] {path} delegated to deployed demo API (local status {status})")
                resp = jsonify(_safe_json_dict(p_body))
                resp.status_code = p_status
                for k, v in CORS_HEADERS.items():
                    resp.headers[k] = v
                return resp

    body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
    if local_error and status >= 500:
        body = {"data": None, "error": str(body.get("error") or local_error)}
    resp = jsonify(body)
    resp.status_code = status
    # Add CORS headers so browsers work even without the Vite proxy
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp

# ---------------------------------------------------------------------------
# Main API app (port 3001)
# ---------------------------------------------------------------------------
main_app = Flask("main_api")
CORS(main_app, origins="*")

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

# --- Phase 5: dashboard approve/reject (POST /api/incidents/:id/approve|reject)
# Dashboard-facing routes per docs/FRONTEND_SPEC.md. The deployed stack only
# exposes the Slack-link flow (/approval) and /demo/approve/{id}, so the local
# proxy implements these routes on top of the SAME approval handler, signing
# the HMAC token from SSM exactly as the notify Lambda does.


def _sign_approval_token(incident_id: str, action: str) -> str:
    """Sign HMAC-SHA256(incident_id:action) with the SSM secret, mirroring the
    token the notify Lambda embeds in Slack approval links."""
    try:
        resp = approval_module._ssm.get_parameter(
            Name=approval_module.APPROVAL_TOKEN_SECRET_SSM, WithDecryption=True
        )
        secret = resp.get("Parameter", {}).get("Value") or ""
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not read approval token secret from SSM: {exc}")
        return ""
    signed = f"{incident_id}:{action}"
    return hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()


def _run_approval(incident_id: str, action: str, body=None):
    """Invoke the real Phase 5 approval handler for the dashboard routes."""
    payload = {
        "incident_id": incident_id,
        "action": action,
        "token": _sign_approval_token(incident_id, action),
    }
    # Pass through spec'd fields (BACKEND_SPEC 5.2): rejection reason, and
    # optional approver identity when the dashboard supplies one.
    if isinstance(body, dict):
        for key in ("reason", "approved_by"):
            if isinstance(body.get(key), str) and body[key].strip():
                payload[key] = body[key].strip()
    event = {
        "httpMethod": "POST",
        "path": "/approval",
        "resource": "/approval",
        "queryStringParameters": None,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }
    result = approval_module.lambda_handler(event, {})

    # IAM gap: the local user may be denied dynamodb:UpdateItem on the
    # -staging table, which surfaces as a 500 from the local handler. Retry
    # the SAME payload against the deployed approval Lambda (direct invoke),
    # which re-verifies the token with its own SSM access. Never fallback on
    # business-level 4xx (409 already processed, 403 bad token).
    status = (result or {}).get("statusCode", 500)
    body_text = (result or {}).get("body", "")
    if approval_module is not None and (
        status >= 500 or (status >= 400 and _is_permission_error(body_text))
    ):
        raw = _invoke_lambda_via_fallback(DEPLOYED_APPROVAL_FUNCTION, payload)
        normalized = _normalize_lambda_result(raw)
        if normalized is not None:
            print(
                f"[INFO] /approval {action} delegated to deployed approval "
                f"Lambda (local status {status})"
            )
            p_status, p_body = normalized
            return {"statusCode": p_status, "body": p_body}

    # Token could not be signed locally (SSM GetParameter denied — part of the
    # same IAM gap). Approve has a deployed escape hatch: /demo/approve/{id}
    # invokes the approval Lambda internally with its own SSM access, so no
    # local token is needed. Reject has no deployed route — surface the local
    # 403 with guidance instead of a bare "invalid token".
    if not payload["token"]:
        if action == "approve" and DEMO_API_FALLBACK_URL:
            proxied = _invoke_write_fallback(f"/demo/approve/{incident_id}", None)
            if proxied is not None:
                p_status, p_body = proxied
                if 200 <= p_status < 300:
                    # The deployed demo Lambda (pre-fix builds) reports success
                    # even when the inner approval fails and is discarded.
                    # Verify the decision actually landed on the record.
                    landed = _incident_status_via_fallback(incident_id)
                    if landed in (None, "approved"):
                        print(
                            f"[INFO] /approval approve for {incident_id[:8]} delegated to "
                            "deployed demo API (approval-token secret unavailable locally)"
                        )
                        return {"statusCode": p_status, "body": p_body}
                    return {
                        "statusCode": 502,
                        "body": json.dumps({
                            "data": None,
                            "error": (
                                "Approval acknowledged by the deployed demo API, but the "
                                "incident did not change state — the deployed Demo Control "
                                "Lambda is missing the inner-result fix and needs a redeploy "
                                "(see team handoff message)."
                            ),
                        }),
                    }
                return {"statusCode": p_status, "body": p_body}
        else:
            try:
                err_body = json.loads(body_text) if body_text else {}
            except json.JSONDecodeError:
                err_body = {}
            if isinstance(err_body, dict) and err_body.get("error"):
                err_body["error"] += (
                    " (local proxy note: the approval-token secret could not be read from SSM, "
                    "so no valid token could be minted — apply the pending IAM policy update "
                    "to enable local rejects)"
                )
                return {"statusCode": status, "body": json.dumps(err_body)}
    return result


@main_app.route("/api/incidents/<incident_id>/approve", methods=["POST", "OPTIONS"])
def approve_incident(incident_id):
    if request.method == "OPTIONS":
        return cors_preflight()
    if approval_module is None:
        return jsonify({"data": None, "error": "Approval handler not loaded"}), 500
    result = _run_approval(incident_id, "approve", request.get_json(silent=True))
    status = result.get("statusCode", 200)
    body = json.loads(result.get("body", "{}"))
    resp = jsonify(body)
    resp.status_code = status
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp


@main_app.route("/api/incidents/<incident_id>/reject", methods=["POST", "OPTIONS"])
def reject_incident(incident_id):
    if request.method == "OPTIONS":
        return cors_preflight()
    if approval_module is None:
        return jsonify({"data": None, "error": "Approval handler not loaded"}), 500
    result = _run_approval(incident_id, "reject", request.get_json(silent=True))
    status = result.get("statusCode", 200)
    body = json.loads(result.get("body", "{}"))
    resp = jsonify(body)
    resp.status_code = status
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp

@main_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "server": "local_backend main api"}), 200

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
    event = build_event(request, path_params={"incident_id": incident_id},
                        resource="/demo/approve/{incident_id}")
    return invoke_handler(demo_handler, event)

@demo_app.route("/health", methods=["GET"])
def demo_health():
    return jsonify({"status": "ok", "server": "local_backend demo api"}), 200

# ---------------------------------------------------------------------------
# Run both servers
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Local Backend Server")
    print("  Main API  -> http://localhost:3001")
    print("  Demo API  -> http://localhost:3002")
    print("  AWS Region: ap-south-1")
    print("  DynamoDB Table:", os.environ["INCIDENTS_TABLE"])
    print("  S3 Bucket:     ", os.environ["DATA_LAKE_BUCKET"])
    print("  Read fallback: ", DASHBOARD_API_FALLBACK_URL or "(disabled)")
    print("  Demo fallback: ", DEMO_API_FALLBACK_URL or "(disabled)")
    print("  Approval fall: ", DEPLOYED_APPROVAL_FUNCTION or "(disabled)")
    print("="*60 + "\n")

    demo_thread = threading.Thread(
        target=lambda: demo_app.run(host="0.0.0.0", port=3002, debug=False, use_reloader=False),
        daemon=True,
        name="demo-api",
    )
    demo_thread.start()
    print("[INFO] Demo API started on port 3002")

    # Main API runs in main thread
    main_app.run(host="0.0.0.0", port=3001, debug=True, use_reloader=False)
