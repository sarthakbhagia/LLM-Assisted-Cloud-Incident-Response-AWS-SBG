import json


def lambda_handler(event, context):
    print("Detection event received:")
    print(json.dumps(event, indent=2, default=str))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Detection event received successfully"
        })
    }
