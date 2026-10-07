import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger()
logger.setLevel(logging.INFO)

DOWNSTREAM_TIMEOUT_SECONDS = 5

# Module-level fault state for Service A (similar to Service C)
_FAULT_STATE = {
    "latency_ms": 0,
    "error_rate": 0.0,
    "error_type": "timeout",
    "enabled": False,
}

_FAULT_INJECTION_TOKEN = os.environ.get("FAULT_INJECTION_TOKEN", "")


def _verify_fault_token(event):
    """Verify the fault injection token from Authorization header."""
    if not _FAULT_INJECTION_TOKEN:
        return False
    auth_header = event.get("headers", {}).get("authorization") or event.get("headers", {}).get("Authorization")
    if not auth_header:
        return False
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return parts[1] == _FAULT_INJECTION_TOKEN


def _inject_fault():
    """Apply fault injection based on current fault state."""
    import random
    if not _FAULT_STATE["enabled"]:
        return None
    
    if _FAULT_STATE["latency_ms"] > 0:
        time.sleep(_FAULT_STATE["latency_ms"] / 1000.0)
    
    if _FAULT_STATE["error_rate"] > 0 and random.random() < _FAULT_STATE["error_rate"]:
        error_type = _FAULT_STATE["error_type"]
        if error_type == "timeout":
            raise TimeoutError("Simulated Service A timeout")
        elif error_type == "500":
            raise RuntimeError("Simulated Service A internal error")
        elif error_type == "connection":
            raise ConnectionError("Simulated Service A connection error")
    
    return None


def _call_service(url):
    started_at = time.perf_counter()
    request = Request(url, method="GET")

    try:
        with urlopen(request, timeout=DOWNSTREAM_TIMEOUT_SECONDS) as response:
            status_code = response.status
            body = response.read().decode("utf-8")
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(json.dumps({
            "event": "downstream_response",
            "service": "B",
            "url": url,
            "status_code": status_code,
            "latency_ms": latency_ms,
        }))
        return status_code, json.loads(body)
    except HTTPError as error:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(json.dumps({
            "event": "downstream_http_error",
            "service": "B",
            "url": url,
            "status_code": error.code,
            "latency_ms": latency_ms,
        }))
        return error.code, {"error": "Service B returned an HTTP error"}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(json.dumps({
            "event": "downstream_request_failed",
            "service": "B",
            "url": url,
            "latency_ms": latency_ms,
            "error": str(error),
        }))
        return None, {"error": "Service B could not be reached"}


def lambda_handler(event, context):
    # Check for fault injection management endpoint
    path = event.get("path", "") or event.get("rawPath", "")
    method = event.get("httpMethod", "") or event.get("requestContext", {}).get("http", {}).get("method", "")
    
    if path == "/start/fault" and method in ("POST", "GET"):
        return _handle_fault_management(event, method)
    
    # Apply fault injection
    _inject_fault()
    
    service_b_url = os.environ.get("SERVICE_B_URL")
    if not service_b_url:
        logger.error("SERVICE_B_URL is not configured")
        return _error_response(500, "Service B URL is not configured")

    logger.info(json.dumps({"event": "service_a_request", "service_b_url": service_b_url}))
    status_code, service_b_response = _call_service(service_b_url)

    if status_code is not None and 200 <= status_code < 300:
        response = {
            "service": "A",
            "status": "success",
            "service_b_response": service_b_response,
            "overall_status": "success",
        }
        return _json_response(200, response)

    logger.error("Service A downstream dependency failed; raising an exception so the Lambda Errors metric increments for Phase 2 detection.")
    raise RuntimeError(f"Service A downstream failure detected: status_code={status_code}, response={service_b_response}")


def _handle_fault_management(event, method):
    """Handle fault injection configuration via authenticated endpoint."""
    if not _verify_fault_token(event):
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Unauthorized: invalid or missing fault injection token"}),
        }
    
    if method == "GET":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "fault_state": _FAULT_STATE,
                "note": "Use POST to modify fault state. For throttling demo, set reserved concurrency to 1 via AWS Console/CLI.",
            }),
        }
    
    try:
        body = json.loads(event.get("body", "{}") or "{}")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON body"}),
        }
    
    if "latency_ms" in body:
        latency = int(body["latency_ms"])
        if latency < 0 or latency > 30000:
            return _error_response(400, "latency_ms must be between 0 and 30000")
        _FAULT_STATE["latency_ms"] = latency
    
    if "error_rate" in body:
        error_rate = float(body["error_rate"])
        if error_rate < 0.0 or error_rate > 1.0:
            return _error_response(400, "error_rate must be between 0.0 and 1.0")
        _FAULT_STATE["error_rate"] = error_rate
    
    if "error_type" in body:
        error_type = body["error_type"]
        if error_type not in ("timeout", "500", "connection"):
            return _error_response(400, "error_type must be one of: timeout, 500, connection")
        _FAULT_STATE["error_type"] = error_type
    
    if "enabled" in body:
        _FAULT_STATE["enabled"] = bool(body["enabled"])
    
    logger.info(json.dumps({
        "event": "fault_state_updated",
        "fault_state": _FAULT_STATE,
    }))
    
    return _json_response(200, {
        "success": True,
        "fault_state": _FAULT_STATE,
    })


def _json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _error_response(status_code, message):
    return _json_response(status_code, {
        "service": "A",
        "status": "error",
        "service_b_response": {"error": message},
        "overall_status": "failure",
    })