"""
test_demo_control.py — unit tests for the Demo Control Lambda handler.

Uses mocked boto3 (stdlib-only stubs from helpers.py) — no AWS access needed.
Focus: POST /demo/approve/{id} must propagate the approval handler's inner
result instead of reporting success unconditionally (a deployed-code bug that
silently left incidents pending_approval while returning success).
"""

import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import helpers  # noqa: F401  (must precede botocore: installs stdlib-only stub)
from helpers import REPO_ROOT, Fixture

DEMO = os.path.join(REPO_ROOT, "backend", "demo_control", "demo_control_lambda.py")
INC = "11111111-2222-3333-4444-555555555555"
APPROVAL_FN = "llm-incident-response-staging-ApprovalFunction-XYZ"


class DemoApproveCase(Fixture):
    """POST /demo/approve/{id} reflects the approval handler's inner result."""

    def setUp(self):
        super().setUp()

        # Minimal AWS surface: DynamoDB (existence + status check), SSM
        # (secret), Lambda (inner approval invoke).
        self.items = {
            INC: {"incident_id": INC, "remediation": {"status": "pending_approval"}}
        }

        class FakeTable:
            def get_item(self, Key):
                item = self.items.get(Key["incident_id"])
                if item is None:
                    return {}
                return {"Item": json.loads(json.dumps(item))}

        table = FakeTable()
        table.items = self.items
        self.mod = self.load_handler(DEMO, env={
            "INCIDENTS_TABLE": "incidents-staging",
            "APPROVAL_FUNCTION_NAME": APPROVAL_FN,
            "ENVIRONMENT": "staging",
        })
        self.mod._dynamodb = SimpleNamespace(Table=lambda name: table)
        self.mod.boto3 = SimpleNamespace(
            client=lambda service, *a, **kw: self.aws.get(service)
        )
        self.lambda_client = self.aws.setdefault("lambda", SimpleNamespace(invoke=mock.MagicMock()))
        self.lambda_client.invoke = mock.MagicMock()
        self.ssm_client = self.aws.setdefault(
            "ssm",
            SimpleNamespace(
                get_parameter=lambda Name, WithDecryption=False: {
                    "Parameter": {"Value": "test-secret"}
                }
            ),
        )

    def _post(self, incident_id=INC):
        event = {
            "httpMethod": "POST",
            "resource": "/demo/approve/{incident_id}",
            "pathParameters": {"incident_id": incident_id},
            "body": None,
            "isBase64Encoded": False,
        }
        return self.mod.lambda_handler(event, {})

    def _set_inner_response(self, status_code, body):
        payload = json.dumps({"statusCode": status_code, "body": json.dumps(body)})
        self.lambda_client.invoke.return_value = {
            "Payload": SimpleNamespace(read=lambda: payload.encode())
        }

    def test_inner_2xx_reports_success(self):
        self._set_inner_response(200, {"message": "approved"})
        resp = self._post()

        self.assertEqual(resp["statusCode"], 200)
        data = json.loads(resp["body"])
        self.assertEqual(data["data"]["incident_id"], INC)

    def test_inner_403_surfaces_as_error(self):
        """Bad inner token/secret → the caller must NOT see success."""
        self._set_inner_response(403, {"error": "Invalid or missing approval token."})
        resp = self._post()

        self.assertEqual(resp["statusCode"], 400)
        data = json.loads(resp["body"])
        self.assertIsNone(data["data"])
        self.assertIn("Invalid or missing approval token", data["error"])

    def test_inner_409_surfaces_as_conflict(self):
        """Already-processed race → the conflict must reach the caller."""
        self._set_inner_response(409, {"error": "Incident was already processed (current status: approved)."})
        resp = self._post()

        self.assertEqual(resp["statusCode"], 400)
        data = json.loads(resp["body"])
        self.assertIn("already processed", data["error"])

    def test_inner_500_surfaces_as_error(self):
        self._set_inner_response(500, {"error": "Failed to update incident — check Lambda logs."})
        resp = self._post()

        self.assertEqual(resp["statusCode"], 400)
        data = json.loads(resp["body"])
        self.assertIn("Failed to update incident", data["error"])


if __name__ == "__main__":
    unittest.main()
