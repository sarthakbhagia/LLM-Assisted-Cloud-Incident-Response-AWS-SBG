"""
test_approval.py — unit tests for the Phase 5 approval handler.

Uses mocked boto3 (stdlib-only stubs from helpers.py) — no AWS access needed.
Covers: happy path (approve + reject), bad/missing token, already-processed
(conditional-write race), request parsing, idempotency, and the Phase 6
remediation invocation stub.
"""

import hmac
import json
import os
import sys
import unittest
from datetime import datetime
from hashlib import sha256
from types import SimpleNamespace

import helpers  # noqa: F401  (must precede botocore: installs stdlib-only stub)
from botocore.exceptions import ClientError

from helpers import REPO_ROOT, Fixture

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

APP = os.path.join(REPO_ROOT, "backend", "approval", "approval_handler.py")

SECRET = "test-secret"
INC = "11111111-2222-3333-4444-555555555555"
REMEDIATION_FN = "llm-incident-response-RemediationFunction-ABC123"


def signed(incident_id=INC, action="approve", secret=SECRET):
    """Token the notify Lambda would embed in an approval link."""
    return hmac.new(secret.encode("utf-8"), f"{incident_id}:{action}".encode("utf-8"), sha256).hexdigest()


def make_token(incident_id=INC, secret=SECRET):
    return signed(incident_id, secret=secret)


def api_event(action="approve", token=None, incident_id=INC, method="GET", body=None):
    """Build an API Gateway REST (v1) proxy event for GET or POST.

    When token is omitted, one is computed with :func:`signed` so it matches
    what the notify Lambda would embed in an approval link.
    """
    event = {
        "httpMethod": method,
        "path": "/approval",
        "resource": "/approval",
        "isBase64Encoded": False,
        "requestContext": {"httpMethod": method, "path": "/Prod/approval", "resourcePath": "/approval"},
    }
    if method == "GET":
        event["queryStringParameters"] = {
            "incident_id": incident_id,
            "action": action,
            "token": token if token is not None else signed(incident_id, action),
        }
    else:
        event["queryStringParameters"] = {}
        event["headers"] = {"Content-Type": "application/json"}
        event["body"] = body if body is not None else json.dumps(
            {"incident_id": incident_id, "action": action, "token": signed(incident_id, action)}
        )
    return event


class FakeTable:
    """In-memory DynamoDB table mimicking the conditional update_item."""

    def __init__(self, items=None, conditional=True):
        self.items = items or {}
        self.conditional = conditional
        self.calls = []

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None, ExpressionAttributeValues=None):
        self.calls.append({"op": "update", "key": Key})
        incident_id = Key["incident_id"]
        if incident_id not in self.items:
            raise ClientError(
                {"Error": {"Code": "ValidationException", "Message": "item not found"}},
                "UpdateItem",
            )
        status_field = ExpressionAttributeNames["#st"]
        current = self.items[incident_id]["remediation"]["status"]
        if self.conditional and current != ExpressionAttributeValues[":pending"]:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "condition failed"}},
                "UpdateItem",
            )
        remediation = dict(self.items[incident_id]["remediation"])
        remediation[status_field] = ExpressionAttributeValues[":new_status"]
        remediation[ExpressionAttributeNames["#decided_at"]] = ExpressionAttributeValues[":decided_at"]
        self.items[incident_id]["remediation"] = remediation
        return {}

    def get_item(self, Key, ProjectionExpression=None, ExpressionAttributeNames=None):
        self.calls.append({"op": "get", "key": Key})
        item = self.items.get(Key["incident_id"])
        if item is None:
            return {}
        return {"Item": {"remediation": {"status": item["remediation"]["status"]}}}


class FakeLambda:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"StatusCode": 202}


def pending_item(incident_id=INC, status="pending_approval"):
    return {
        "incident_id": incident_id,
        "fault_class": "resource_exhaustion",
        "remediation": {"status": status, "action_taken": None, "executed_at": None},
    }


class ApprovalHandlerCase(Fixture):
    def setUp(self):
        super().setUp()
        self.mod = self.load_handler(APP)

    # -- fixture wiring ------------------------------------------------------

    def _set_table(self, table):
        self.table = table
        self.mod.INCIDENTS_TABLE = "incidents-dev"  # module constant read at call time
        self.mod._dynamodb = SimpleNamespace(Table=lambda TableName: table)

    def _set_ssm(self, parameters):
        self.mod.APPROVAL_TOKEN_SECRET_SSM = "/llm-incident-response/approval-token-secret"
        self.setenv("APPROVAL_TOKEN_SECRET_SSM", self.mod.APPROVAL_TOKEN_SECRET_SSM)
        self.mod._ssm = SimpleNamespace(
            get_parameter=lambda Name, WithDecryption=False: (
                {"Parameter": {"Value": parameters[Name]}} if Name in parameters
                else self._parameter_not_found()
            )
        )
        self.mod._cache.clear()

    def _set_lambda(self, fake):
        self.lamb = fake
        self.mod._lambda = fake

    @staticmethod
    def _parameter_not_found():
        raise ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}}, "GetParameter"
        )

    # -- happy path -----------------------------------------------------------

    def test_approve_happy_path(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())
        self.mod.REMEDIATION_FUNCTION_NAME = REMEDIATION_FN

        resp = self.mod.lambda_handler(api_event("approve"), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertIn("approved", resp["body"])
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "approved")
        self.assertEqual(len(self.lamb.calls), 1)
        self.assertEqual(self.lamb.calls[0]["FunctionName"], REMEDIATION_FN)
        self.assertEqual(json.loads(self.lamb.calls[0]["Payload"]), {"incident_id": INC})
        self.assertEqual(self.lamb.calls[0]["InvocationType"], "Event")

    def test_reject_happy_path_does_not_invoke_remediation(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())
        self.mod.REMEDIATION_FUNCTION_NAME = REMEDIATION_FN

        resp = self.mod.lambda_handler(api_event("reject"), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertIn("rejected", resp["body"])
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "rejected")
        self.assertEqual(self.lamb.calls, [])

    def test_decided_at_timestamp_written(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())
        self.mod.REMEDIATION_FUNCTION_NAME = REMEDIATION_FN

        self.mod.lambda_handler(api_event("approve"), None)

        decided_at = self.table.items[INC]["remediation"]["decided_at"]
        self.assertIsNotNone(decided_at)
        parsed = datetime.fromisoformat(decided_at)
        self.assertIsNotNone(parsed.tzinfo)

    # -- token verification ----------------------------------------------------

    def test_bad_token_rejected_and_no_state_change(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())

        resp = self.mod.lambda_handler(api_event("approve", token="deadbeef"), None)

        self.assertEqual(resp["statusCode"], 403)
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "pending_approval")
        self.assertEqual(self.lamb.calls, [])

    def test_token_bound_to_incident_id(self):
        other = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self._set_table(FakeTable({other: pending_item(other)}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())

        # token correctly signed for INC, but used against a different incident
        resp = self.mod.lambda_handler(
            api_event("approve", token=make_token(INC), incident_id=other), None
        )

        self.assertEqual(resp["statusCode"], 403)
        self.assertEqual(self.table.items[other]["remediation"]["status"], "pending_approval")

    def test_missing_token_rejected(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})

        resp = self.mod.lambda_handler(api_event("approve", token=""), None)

        self.assertEqual(resp["statusCode"], 403)

    def test_missing_ssm_secret_fails_closed(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({})  # parameter does not exist
        self._set_lambda(FakeLambda())

        resp = self.mod.lambda_handler(api_event("approve"), None)

        self.assertEqual(resp["statusCode"], 403)
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "pending_approval")
        self.assertEqual(self.lamb.calls, [])

    # -- already-processed / race ----------------------------------------------

    def test_already_processed_returns_409(self):
        self._set_table(FakeTable({INC: pending_item(status="approved")}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())
        self.mod.REMEDIATION_FUNCTION_NAME = REMEDIATION_FN

        resp = self.mod.lambda_handler(api_event("approve"), None)

        self.assertEqual(resp["statusCode"], 409)
        self.assertIn("already processed", resp["body"])
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "approved")
        self.assertEqual(self.lamb.calls, [])

    def test_conflicting_action_after_approve_is_409(self):
        # Approve already won the race; a late reject click must not flip the
        # incident back — the conditional write blocks it and we return 409.
        self._set_table(FakeTable({INC: pending_item(status="approved")}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())
        self.mod.REMEDIATION_FUNCTION_NAME = REMEDIATION_FN

        resp = self.mod.lambda_handler(api_event("reject"), None)

        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "approved")
        self.assertEqual(self.lamb.calls, [])

    # -- request parsing ---------------------------------------------------------

    def test_malformed_incident_id_returns_400(self):
        resp = self.mod.lambda_handler(api_event("approve", incident_id="not-a-uuid!"), None)
        self.assertEqual(resp["statusCode"], 400)

    def test_invalid_action_returns_400(self):
        resp = self.mod.lambda_handler(api_event("nuke"), None)
        self.assertEqual(resp["statusCode"], 400)

    def test_missing_incident_id_returns_400(self):
        event = api_event("approve")
        event["queryStringParameters"] = {"action": "approve", "token": make_token()}
        resp = self.mod.lambda_handler(event, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_post_json_body_supported(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())
        self.mod.REMEDIATION_FUNCTION_NAME = REMEDIATION_FN

        resp = self.mod.lambda_handler(api_event(method="POST"), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "approved")
        self.assertEqual(len(self.lamb.calls), 1)

    def test_post_invalid_json_body_returns_400(self):
        resp = self.mod.lambda_handler(api_event(method="POST", body="this is not json{{"), None)
        self.assertEqual(resp["statusCode"], 400)

    # -- remediation stub behaviour ------------------------------------------------

    def test_remediation_skipped_when_not_configured(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda())
        self.mod.REMEDIATION_FUNCTION_NAME = ""

        resp = self.mod.lambda_handler(api_event("approve"), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertIn("not wired up", resp["body"])
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "approved")
        self.assertEqual(self.lamb.calls, [])

    def test_remediation_invoke_error_still_marks_approved(self):
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        self._set_lambda(FakeLambda(error=ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "no such function"}},
            "Invoke",
        )))
        self.mod.REMEDIATION_FUNCTION_NAME = REMEDIATION_FN

        resp = self.mod.lambda_handler(api_event("approve"), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertIn("approved", resp["body"])
        self.assertEqual(self.table.items[INC]["remediation"]["status"], "approved")

    # -- infrastructure errors ----------------------------------------------------

    def test_dynamodb_error_returns_500(self):
        class ExplodingTable:
            def update_item(self, **kwargs):
                raise ClientError(
                    {"Error": {"Code": "InternalServerError", "Message": "boom"}}, "UpdateItem"
                )

        self._set_table(ExplodingTable())
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})

        resp = self.mod.lambda_handler(api_event("approve"), None)

        self.assertEqual(resp["statusCode"], 500)

    def test_missing_incident_item_returns_500(self):
        self._set_table(FakeTable({}))  # table exists, incident does not
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})

        resp = self.mod.lambda_handler(api_event("approve"), None)

        self.assertEqual(resp["statusCode"], 500)

    def test_secret_rotation_rejects_link(self):
        """If the SSM secret is rotated between link generation and approval,
        the token no longer verifies and the request is rejected (403)."""
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_lambda(FakeLambda())
        self.mod.REMEDIATION_FUNCTION_NAME = REMEDIATION_FN

        # Start with secret A; build a link token signed with it (what notify
        # would have embedded).
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})
        old_token = signed(INC, action="approve", secret=SECRET)

        # Rotating the secret to B makes old_token unverifiable.
        self._set_ssm({"/llm-incident-response/approval-token-secret": "rotated-secret"})
        self.mod._cache.clear()

        resp = self.mod.lambda_handler(
            api_event("approve", token=old_token, incident_id=INC), None
        )

        self.assertEqual(resp["statusCode"], 403)
        # State must not change on a rejected token.
        self.assertEqual(
            self.table.items[INC]["remediation"]["status"], "pending_approval"
        )
        self.assertEqual(self.lamb.calls, [])

    def test_wrong_action_token_rejected(self):
        """An approve link's token is bound to the approve action; using it
        against a reject request must be rejected (403)."""
        self._set_table(FakeTable({INC: pending_item()}))
        self._set_ssm({"/llm-incident-response/approval-token-secret": SECRET})

        # Token signed for 'approve'.
        approve_token = signed(INC, action="approve")
        resp = self.mod.lambda_handler(
            api_event("reject", token=approve_token, incident_id=INC), None
        )

        self.assertEqual(resp["statusCode"], 403)
        self.assertEqual(
            self.table.items[INC]["remediation"]["status"], "pending_approval"
        )


if __name__ == "__main__":
    unittest.main()
