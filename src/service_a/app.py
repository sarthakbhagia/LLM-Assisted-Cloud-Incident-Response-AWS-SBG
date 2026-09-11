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
        logger.info(json.dumps({"event": "downstream_response", "service": "B", "url": url, "status_code": status_code, "latency_ms": latency_ms}))
        return status_code, json.loads(body)
    except HTTPError as error:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(json.dumps({"event": "downstream_http_error", "service": "B", "url": url, "status_code": error.code, "latency_ms": latency_ms}))
        return error.code, {"error": "Service B returned an HTTP error"}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(json.dumps({"event": "downstream_request_failed", "service": "B", "url": url, "latency_ms": latency_ms, "error": str(error)}))
        return None, {"error": "Service B could not be reached"}


def lambda_handler(event, context):
    service_b_url = os.environ.get("SERVICE_B_URL")
    if not service_b_url:
        logger.error("SERVICE_B_URL is not configured")
        return _error_response(500, "Service B URL is not configured")

    logger.info(json.dumps({"event": "service_a_request", "service_b_url": service_b_url}))
    status_code, service_b_response = _call_service(service_b_url)

    if status_code is not None and 200 <= status_code < 300:
        response = {"service": "A", "status": "success", "service_b_response": service_b_response, "overall_status": "success"}
        return _json_response(200, response)

    logger.error("Service A downstream dependency failed; raising an exception so the Lambda Errors metric increments for Phase 2 detection.")
    raise RuntimeError(f"Service A downstream failure detected: status_code={status_code}, response={service_b_response}")


def _json_response(status_code, body):
    return {"statusCode": status_code, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def _error_response(status_code, message):
    return _json_response(status_code, {"service": "A", "status": "error", "service_b_response": {"error": message}, "overall_status": "failure"})
