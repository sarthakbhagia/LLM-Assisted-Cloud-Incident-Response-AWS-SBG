import json
import logging


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info(json.dumps({"event": "service_c_request", "request": event}))

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