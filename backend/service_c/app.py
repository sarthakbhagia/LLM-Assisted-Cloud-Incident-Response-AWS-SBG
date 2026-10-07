import json
import logging
import os
import random
import time
from functools import wraps

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level fault state for demo fault injection
# These can be set via the /fault endpoint (authenticated)
_FAULT_STATE = {
    "latency_ms": 0,           # Additional latency to inject (ms)
    "error_rate": 0.0,         # Probability of returning an error (0.0 to 1.0)
    "error_type": "timeout",   # Type of error: "timeout", "500", "connection"
    "enabled": False,          # Whether fault injection is active
}

# Authentication token for fault injection (set via environment variable)
_FAULT_INJECTION_TOKEN = os.environ.get("FAULT_INJECTION_TOKEN", "")


def _verify_fault_token(event):
    """Verify the fault injection token from Authorization header."""
    if not _FAULT_INJECTION_TOKEN:
        return False
    auth_header = event.get("headers", {}).get("authorization") or event.get("headers", {}).get("Authorization")
    if not auth_header:
        return False
    # Expect "Bearer <token>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return parts[1] == _FAULT_INJECTION_TOKEN


def _inject_fault():
    """Apply fault injection based on current fault state."""
    if not _FAULT_STATE["enabled"]:
        return None
    
    # Inject latency
    if _FAULT_STATE["latency_ms"] > 0:
        time.sleep(_FAULT_STATE["latency_ms"] / 1000.0)
    
    # Inject error
    if _FAULT_STATE["error_rate"] > 0 and random.random() < _FAULT_STATE["error_rate"]:
        error_type = _FAULT_STATE["error_type"]
        if error_type == "timeout":
            raise TimeoutError("Simulated downstream timeout")
        elif error_type == "500":
            raise RuntimeError("Simulated internal server error")
        elif error_type == "connection":
            raise ConnectionError("Simulated connection error")
    
    return None


def lambda_handler(event, context):
    # Check for fault injection management endpoint
    path = event.get("path", "") or event.get("rawPath", "")
    method = event.get("httpMethod", "") or event.get("requestContext", {}).get("http", {}).get("method", "")
    
    if path == "/service-c/fault" and method in ("POST", "GET"):
        return _handle_fault_management(event, method)
    
    logger.info(json.dumps({"event": "service_c_request", "request": event}))
    
    # Apply fault injection
    fault_result = _inject_fault()
    if fault_result is not None:
        # This shouldn't happen as _inject_fault raises exceptions
        pass
    
    response = {
        "service": "C",
        "status": "success",
        "message": "Service C completed successfully",
    }
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response),
    }


def _handle_fault_management(event, method):
    """Handle fault injection configuration via authenticated endpoint."""
    if not _verify_fault_token(event):
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Unauthorized: invalid or missing fault injection token"}),
        }
    
    if method == "GET":
        # Return current fault state
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "fault_state": _FAULT_STATE,
                "note": "Use POST to modify fault state",
            }),
        }
    
    # POST: update fault state
    try:
        body = json.loads(event.get("body", "{}") or "{}")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON body"}),
        }
    
    # Validate and update fault state
    if "latency_ms" in body:
        latency = int(body["latency_ms"])
        if latency < 0 or latency > 30000:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "latency_ms must be between 0 and 30000"}),
            }
        _FAULT_STATE["latency_ms"] = latency
    
    if "error_rate" in body:
        error_rate = float(body["error_rate"])
        if error_rate < 0.0 or error_rate > 1.0:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "error_rate must be between 0.0 and 1.0"}),
            }
        _FAULT_STATE["error_rate"] = error_rate
    
    if "error_type" in body:
        error_type = body["error_type"]
        if error_type not in ("timeout", "500", "connection"):
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "error_type must be one of: timeout, 500, connection"}),
            }
        _FAULT_STATE["error_type"] = error_type
    
    if "enabled" in body:
        _FAULT_STATE["enabled"] = bool(body["enabled"])
    
    logger.info(json.dumps({
        "event": "fault_state_updated",
        "fault_state": _FAULT_STATE,
    }))
    
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "success": True,
            "fault_state": _FAULT_STATE,
        }),
    }


# For backward compatibility - allow direct function invocation
def invoke_with_fault(event, context):
    """Wrapper for direct Lambda invocation that applies fault injection."""
    return lambda_handler(event, context)