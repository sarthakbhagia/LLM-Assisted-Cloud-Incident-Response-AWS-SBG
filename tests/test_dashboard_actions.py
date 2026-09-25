"""
Unit tests for dashboard_actions_lambda.py
"""

import os
import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Set default env vars for tests if not present
os.environ.setdefault("INCIDENTS_TABLE", "incidents-dev")
os.environ.setdefault("DATA_LAKE_BUCKET", "llm-incident-datalake-889081505756-dev")
os.environ.setdefault("DIAGNOSIS_FUNCTION_NAME", "llm-incident-response-dev-DiagnosisFunction")
os.environ.setdefault("REMEDIATION_FUNCTION_NAME", "llm-incident-response-dev-RemediationFunction")

from backend.dashboard_api import dashboard_actions_lambda


@pytest.fixture
def mock_dynamodb():
    with patch.object(dashboard_actions_lambda, "_dynamodb") as mock_db:
        mock_table = MagicMock()
        mock_db.Table.return_value = mock_table
        yield mock_table


@pytest.fixture
def mock_s3():
    with patch.object(dashboard_actions_lambda, "_s3") as mock:
        yield mock


@pytest.fixture
def mock_lambda():
    with patch.object(dashboard_actions_lambda, "_lambda_client") as mock:
        yield mock


def test_options_preflight():
    event = {"httpMethod": "OPTIONS"}
    response = dashboard_actions_lambda.lambda_handler(event, {})
    assert response["statusCode"] == 200
    assert response["headers"]["Access-Control-Allow-Methods"] == "GET,POST,OPTIONS"


def test_approve_incident_success(mock_dynamodb, mock_lambda):
    mock_dynamodb.update_item.return_value = {}

    event = {
        "httpMethod": "POST",
        "resource": "/api/incidents/{incident_id}/approve",
        "pathParameters": {"incident_id": "inc-123"},
    }

    response = dashboard_actions_lambda.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["data"]["status"] == "approved"
    assert body["data"]["incident_id"] == "inc-123"

    mock_dynamodb.update_item.assert_called_once()
    mock_lambda.invoke.assert_called_once_with(
        FunctionName="llm-incident-response-dev-RemediationFunction",
        InvocationType="Event",
        Payload=json.dumps({"incident_id": "inc-123"}),
    )


def test_approve_incident_not_found(mock_dynamodb):
    error = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
    )
    mock_dynamodb.update_item.side_effect = error
    mock_dynamodb.get_item.return_value = {}

    event = {
        "httpMethod": "POST",
        "resource": "/api/incidents/{incident_id}/approve",
        "pathParameters": {"incident_id": "inc-nonexistent"},
    }

    response = dashboard_actions_lambda.lambda_handler(event, {})
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "not found" in body["error"]


def test_reject_incident_success(mock_dynamodb):
    mock_dynamodb.update_item.return_value = {}

    event = {
        "httpMethod": "POST",
        "resource": "/api/incidents/{incident_id}/reject",
        "pathParameters": {"incident_id": "inc-123"},
        "body": json.dumps({"reason": "Risk too high"}),
    }

    response = dashboard_actions_lambda.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["data"]["status"] == "rejected"


def test_diagnose_incident_success(mock_dynamodb, mock_lambda):
    mock_dynamodb.get_item.return_value = {
        "Item": {
            "incident_id": "inc-123",
            "fault_class": "resource_exhaustion",
            "raw_data_s3_key": "incidents/inc-123/raw.json",
        }
    }

    event = {
        "httpMethod": "POST",
        "resource": "/api/incidents/{incident_id}/diagnose",
        "pathParameters": {"incident_id": "inc-123"},
    }

    response = dashboard_actions_lambda.lambda_handler(event, {})
    assert response["statusCode"] == 202
    mock_lambda.invoke.assert_called_once_with(
        FunctionName="llm-incident-response-dev-DiagnosisFunction",
        InvocationType="Event",
        Payload=json.dumps({
            "incident_id": "inc-123",
            "fault_class": "resource_exhaustion",
            "raw_data_s3_key": "incidents/inc-123/raw.json",
        }),
    )


def test_get_trace_success(mock_dynamodb, mock_s3):
    mock_dynamodb.get_item.return_value = {
        "Item": {
            "incident_id": "inc-123",
            "fault_class": "resource_exhaustion",
            "diagnosis": {"status": "completed"},
        }
    }

    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "incidents/inc-123/raw.json",
                    "Size": 1024,
                    "LastModified": MagicMock(isoformat=lambda: "2026-09-25T12:00:00Z"),
                }
            ]
        }
    ]
    mock_s3.get_paginator.return_value = mock_paginator

    event = {
        "httpMethod": "GET",
        "resource": "/api/incidents/{incident_id}/trace",
        "pathParameters": {"incident_id": "inc-123"},
    }

    response = dashboard_actions_lambda.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["data"]["incident_id"] == "inc-123"
    assert len(body["data"]["s3_artifacts"]) == 1


def test_get_trace_artifact_invalid_key():
    event = {
        "httpMethod": "GET",
        "resource": "/api/incidents/{incident_id}/trace/artifact",
        "pathParameters": {"incident_id": "inc-123"},
        "queryStringParameters": {"key": "incidents/other-inc/raw.json"},
    }

    response = dashboard_actions_lambda.lambda_handler(event, {})
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "does not belong" in body["error"]


def test_get_services():
    event = {
        "httpMethod": "GET",
        "resource": "/api/services",
    }

    response = dashboard_actions_lambda.lambda_handler(event, {})
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["data"]["services"]) == 3
