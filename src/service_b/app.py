import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger()
logger.setLevel(logging.INFO)

DOWNSTREAM_TIMEOUT_SECONDS = 5


def _call_service(url):
    started_at = time.perf_counter()
    request = Request(url, method="GET")

    try:
        with urlopen(request, timeout=DOWNSTREAM_TIMEOUT_SECONDS) as response:
            status_code = response.status
            body = response.read().decode("utf-8")
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(json.dumps({"event": "downstream_response", "service": "C", "url": url, "status_code": status_code, "latency_ms": latency_ms}))
        return status_code, json.loads(body)
    except HTTPError as error:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(json.dumps({"event": "downstream_http_error", "service": "C", "url": url, "status_code": error.code, "latency_ms": latency_ms}))
        return error.code, {"error": "Service C returned an HTTP error"}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(json.dumps({"event": "downstream_request_failed", "service": "C", "url": url, "latency_ms": latency_ms, "error": str(error)}))
        return None, {"error": "Service C could not be reached"}


def lambda_handler(event, context):
    service_c_url = os.environ.get("SERVICE_C_URL")
    if not service_c_url:
        logger.error("SERVICE_C_URL is not configured")
        return _error_response(500, "Service C URL is not configured")

    logger.info(json.dumps({"event": "service_b_request", "service_c_url": service_c_url}))
    status_code, service_c_response = _call_service(service_c_url)

    if status_code is not None and 200 <= status_code < 300:
        response = {"service": "B", "status": "success", "service_c_response": service_c_response, "overall_status": "success"}
        return _json_response(200, response)

    response = {"service": "B", "status": "error", "service_c_response": service_c_response, "overall_status": "failure"}
    return _json_response(504 if status_code is None else 502, response)


def _json_response(status_code, body):
    return {"statusCode": status_code, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def _error_response(status_code, message):
    return _json_response(status_code, {"service": "B", "status": "error", "service_c_response": {"error": message}, "overall_status": "failure"})
