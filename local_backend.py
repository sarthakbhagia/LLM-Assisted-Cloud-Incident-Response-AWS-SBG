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

import json
import os
import sys
import threading

# ---------------------------------------------------------------------------
# Environment config - point at the real dev AWS resources
# ---------------------------------------------------------------------------
os.environ.setdefault("INCIDENTS_TABLE", "incidents-staging")
os.environ.setdefault("DATA_LAKE_BUCKET", "llm-incident-datalake-889081505756-staging")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_REGION", "ap-south-1")
os.environ.setdefault("ENVIRONMENT", "staging")

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

def invoke_handler(handler_module, event):
    """Invoke a Lambda handler and return a Flask response."""
    # Handle CORS preflight without hitting the Lambda (it can't handle Flask events)
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
        # Add CORS headers so browsers work even without the Vite proxy
        for k, v in CORS_HEADERS.items():
            resp.headers[k] = v
        return resp
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"data": None, "error": str(exc)}), 500

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
