"""
test_local_backend.py — unit tests for the local_backend.py Flask proxy.

Focus: the Phase 5 dashboard approve/reject routes (POST /api/incidents/:id/approve|reject),
which must reach the real approval handler with a valid HMAC token, exactly as
the deployed API Gateway mappings would. Uses Flask's test client; AWS is
stubbed at the approval-module boundary (stdlib only, no AWS access).
"""

import importlib.util
import io
import json
import os
import sys
import unittest
from hashlib import sha256
from hmac import new as hmac_new
from types import SimpleNamespace
from unittest import mock

import helpers  # noqa: F401  (must precede botocore: installs stdlib-only stub)
from botocore.exceptions import ClientError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_BACKEND_PATH = os.path.join(REPO_ROOT, "local_backend.py")

SECRET = "test-secret"
INC = "11111111-2222-3333-4444-555555555555"


def signed(incident_id=INC, action="approve", secret=SECRET):
    return hmac_new(secret.encode(), f"{incident_id}:{action}".encode(), sha256).hexdigest()


def load_local_backend():
    spec = importlib.util.spec_from_file_location("local_backend", LOCAL_BACKEND_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ApprovalRoutesCase(unittest.TestCase):
    """POST /api/incidents/:id/approve and /reject reach the approval handler."""

    def setUp(self):
        self.lb = load_local_backend()
        self.client = self.lb.main_app.test_client()

        # Stub the approval module boundary: SSM secret + a recording handler.
        self.handler_events = []

        def fake_lambda_handler(event, context):
            self.handler_events.append(event)
            action = json.loads(event["body"])["action"]
            body = {"status": action, "incident_id": json.loads(event["body"])["incident_id"]}
            return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}

        self.approval_stub = SimpleNamespace(
            lambda_handler=fake_lambda_handler,
            APPROVAL_TOKEN_SECRET_SSM="/llm-incident-response/approval-token-secret",
            _ssm=SimpleNamespace(
                get_parameter=lambda Name, WithDecryption=False: {"Parameter": {"Value": SECRET}}
            ),
        )
        self.lb.approval_module = self.approval_stub
        self.addCleanup(setattr, self.lb, "approval_module", None)

    def test_approve_route_reaches_handler_with_valid_token(self):
        resp = self.client.post(f"/api/incidents/{INC}/approve")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "approve")
        event = self.handler_events[0]
        self.assertEqual(event["httpMethod"], "POST")
        body = json.loads(event["body"])
        self.assertEqual(body["incident_id"], INC)
        self.assertEqual(body["action"], "approve")
        # The proxy must sign the token itself, mirroring the notify Lambda.
        self.assertEqual(body["token"], signed(INC, "approve"))

    def test_reject_route_sends_reject_action(self):
        resp = self.client.post(f"/api/incidents/{INC}/reject")

        self.assertEqual(resp.status_code, 200)
        body = json.loads(self.handler_events[0]["body"])
        self.assertEqual(body["action"], "reject")
        self.assertEqual(body["token"], signed(INC, "reject"))

    def test_reject_route_forwards_reason_from_body(self):
        """The dashboard Reject form sends { reason }; the proxy must pass it
        through to the approval handler (BACKEND_SPEC 5.2)."""
        resp = self.client.post(
            f"/api/incidents/{INC}/reject",
            json={"reason": "wrong service diagnosed"},
        )

        self.assertEqual(resp.status_code, 200)
        body = json.loads(self.handler_events[0]["body"])
        self.assertEqual(body["action"], "reject")
        self.assertEqual(body["reason"], "wrong service diagnosed")
        self.assertEqual(body["token"], signed(INC, "reject"))

    def test_route_returns_handler_error_status(self):
        def conflict_handler(event, context):
            return {
                "statusCode": 409,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "already processed"}),
            }

        self.approval_stub.lambda_handler = conflict_handler
        resp = self.client.post(f"/api/incidents/{INC}/approve")

        self.assertEqual(resp.status_code, 409)
        self.assertIn("already processed", resp.get_data(as_text=True))

    def test_missing_ssm_secret_forwards_empty_token(self):
        def no_secret(Name, WithDecryption=False):
            raise ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
                "GetParameter",
            )

        self.approval_stub._ssm = SimpleNamespace(get_parameter=no_secret)
        resp = self.client.post(f"/api/incidents/{INC}/approve")

        # The proxy must never fabricate or bypass auth: it forwards the
        # empty-token request and the real approval handler fails closed
        # (403 — covered by tests/test_approval.py::test_missing_ssm_secret_fails_closed).
        body = json.loads(self.handler_events[0]["body"])
        self.assertEqual(body["token"], "")

    def test_handler_not_loaded_returns_500(self):
        self.lb.approval_module = None
        resp = self.client.post(f"/api/incidents/{INC}/approve")
        self.assertEqual(resp.status_code, 500)

    def test_cors_preflight_allowed(self):
        resp = self.client.options(f"/api/incidents/{INC}/approve")
        self.assertEqual(resp.status_code, 204)
        self.assertIn("Access-Control-Allow-Origin", resp.headers)


class ReadOnlyFallbackCase(unittest.TestCase):
    """Read-only GET routes fall back to the deployed Dashboard API when the
    local handler fails (e.g. IAM denial on the -staging resources)."""

    def setUp(self):
        self.lb = load_local_backend()
        self.client = self.lb.main_app.test_client()

        def iam_denied_handler(event, context):
            # The shape invoke_handler sees when DynamoDB/S3 reads are denied.
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"data": None, "error": "Internal server error"}),
            }

        self.lb.dashboard_handler = SimpleNamespace(lambda_handler=iam_denied_handler)

    def test_get_incidents_falls_back_to_deployed_api_on_500(self):
        deployed_body = json.dumps(
            {"data": {"items": [{"incident_id": "abc"}], "next_token": None, "count": 1}, "error": None}
        )
        with mock.patch.object(self.lb, "_proxy_to_deployed", return_value=(200, deployed_body)) as proxy:
            resp = self.client.get("/api/incidents?limit=1")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["data"]["items"][0]["incident_id"], "abc")
        proxy.assert_called_once()
        # The proxy forwards path + query string so filters/sorting survive.
        self.assertEqual(proxy.call_args[0][1], "/api/incidents?limit=1")

    def test_get_returns_local_500_when_fallback_unreachable(self):
        with mock.patch.object(self.lb, "_proxy_to_deployed", return_value=None):
            resp = self.client.get("/api/incidents?limit=1")

        self.assertEqual(resp.status_code, 500)
        self.assertIn("Internal server error", resp.get_data(as_text=True))

    def test_fallback_disabled_via_empty_url(self):
        self.lb.DASHBOARD_API_FALLBACK_URL = ""
        with mock.patch.object(self.lb.urllib.request, "urlopen") as urlopen:
            self.assertIsNone(self.lb._proxy_to_deployed("GET", "/api/incidents"))
        urlopen.assert_not_called()

    def test_proxy_passes_through_deployed_404(self):
        error = self.lb.urllib.error.HTTPError(
            "/api/incidents/x", 404, "Not Found", {}, io.BytesIO(b'{"data": null, "error": "Not found"}')
        )
        with mock.patch.object(self.lb.urllib.request, "urlopen", side_effect=error):
            result = self.lb._proxy_to_deployed("GET", "/api/incidents/x")

        self.assertEqual(result, (404, '{"data": null, "error": "Not found"}'))


class WriteFallbackCase(unittest.TestCase):
    """Denied local WRITES delegate to the deployed demo API / approval Lambda:
    the IAM gap also blocks SetAlarmState (demo inject) and UpdateItem
    (approve/reject), so POSTs need the same delegation as GETs."""

    def setUp(self):
        self.lb = load_local_backend()
        self.demo_client = self.lb.demo_app.test_client()
        self.main_client = self.lb.main_app.test_client()

        def denied(event, context):
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(
                    {"data": None, "error": "An error occurred (AccessDenied) when calling the "
                     "SetAlarmState operation: User is not authorized to perform: "
                     "cloudwatch:SetAlarmState because no identity-based policy allows it"}
                ),
            }

        self.lb.demo_handler = SimpleNamespace(lambda_handler=denied)

        def denied_approval(event, context):
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "User is not authorized to perform: dynamodb:UpdateItem"}),
            }

        self.approval_stub = SimpleNamespace(
            lambda_handler=denied_approval,
            APPROVAL_TOKEN_SECRET_SSM="/llm-incident-response/approval-token-secret",
            _ssm=SimpleNamespace(
                get_parameter=lambda Name, WithDecryption=False: {"Parameter": {"Value": SECRET}}
            ),
        )
        self.lb.approval_module = self.approval_stub
        self.addCleanup(setattr, self.lb, "approval_module", None)

    def test_demo_inject_delegates_to_deployed_api_on_access_denied(self):
        deployed = json.dumps({"data": {"message": "Fault injection triggered"}, "error": None})
        with mock.patch.object(
            self.lb, "_invoke_write_fallback", return_value=(200, deployed)
        ) as delegate:
            resp = self.demo_client.post("/demo/inject", json={"fault_class": "resource_exhaustion"})

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Fault injection triggered", resp.get_data(as_text=True))
        delegate.assert_called_once()
        path, body = delegate.call_args[0]
        self.assertEqual(path, "/demo/inject")
        self.assertEqual(json.loads(body)["fault_class"], "resource_exhaustion")

    def test_demo_inject_returns_local_error_when_fallback_unreachable(self):
        with mock.patch.object(self.lb, "_invoke_write_fallback", return_value=None):
            resp = self.demo_client.post("/demo/inject", json={"fault_class": "resource_exhaustion"})

        self.assertEqual(resp.status_code, 400)
        self.assertIn("AccessDenied", resp.get_data(as_text=True))

    def test_demo_inject_does_not_fallback_on_business_errors(self):
        """A real 4xx (invalid fault class) must surface as-is — no delegation."""
        def invalid_class(event, context):
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"data": None, "error": "Invalid fault_class. Must be one of: ..."}),
            }

        self.lb.demo_handler.lambda_handler = invalid_class
        with mock.patch.object(self.lb, "_invoke_write_fallback") as delegate:
            resp = self.demo_client.post("/demo/inject", json={"fault_class": "bogus"})

        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid fault_class", resp.get_data(as_text=True))
        delegate.assert_not_called()

    def test_approval_write_delegates_to_deployed_lambda_on_denial(self):
        # The real _invoke_lambda_via_fallback returns the PARSED Lambda
        # response payload ({statusCode, body, ...}).
        raw_lambda_response = {
            "statusCode": 200,
            "body": json.dumps({"message": "approved"}),
        }
        with mock.patch.object(
            self.lb, "_invoke_lambda_via_fallback", return_value=raw_lambda_response
        ) as invoke:
            resp = self.main_client.post(
                f"/api/incidents/{INC}/approve",
                json={"reason": "", "approved_by": "John Doe"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertIn("approved", resp.get_data(as_text=True))
        invoke.assert_called_once()
        fname, payload = invoke.call_args[0]
        self.assertEqual(fname, self.lb.DEPLOYED_APPROVAL_FUNCTION)
        # The ORIGINAL request payload is forwarded (token + audit fields),
        # not the failed handler response.
        self.assertEqual(payload["incident_id"], INC)
        self.assertEqual(payload["action"], "approve")
        self.assertEqual(payload["token"], signed(INC, "approve"))
        self.assertEqual(payload["approved_by"], "John Doe")

    def test_approval_returns_local_error_when_invoke_fails(self):
        with mock.patch.object(self.lb, "_invoke_lambda_via_fallback", return_value=None):
            resp = self.main_client.post(f"/api/incidents/{INC}/approve")

        self.assertEqual(resp.status_code, 500)
        self.assertIn("not authorized", resp.get_data(as_text=True))

    def test_approve_without_token_delegates_to_demo_api(self):
        """SSM denied locally → no token → local 403. Approve escapes via the
        deployed /demo/approve/{id} route, which invokes the approval Lambda
        internally with its own SSM access (no local token needed)."""
        def no_secret(Name, WithDecryption=False):
            raise ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
                "GetParameter",
            )

        self.approval_stub._ssm = SimpleNamespace(get_parameter=no_secret)
        deployed = json.dumps({"message": f"Incident {INC} approved", "incident_id": INC})
        with mock.patch.object(self.lb, "_invoke_write_fallback", return_value=(200, deployed)) as delegate:
            resp = self.main_client.post(f"/api/incidents/{INC}/approve")

        self.assertEqual(resp.status_code, 200)
        self.assertIn("approved", resp.get_data(as_text=True))
        delegate.assert_called_once()
        path, body = delegate.call_args[0]
        self.assertEqual(path, f"/demo/approve/{INC}")

    def test_reject_without_token_returns_guidance(self):
        """Reject has no deployed escape hatch, so the 403 comes back with a
        note explaining the SSM/IAM gap instead of a bare token error."""
        def no_secret(Name, WithDecryption=False):
            raise ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
                "GetParameter",
            )

        self.approval_stub._ssm = SimpleNamespace(get_parameter=no_secret)

        # The real handler fails closed on a bad/empty token (403) — the SSM
        # read happens before any DynamoDB access.
        def bad_token_handler(event, context):
            return {
                "statusCode": 403,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(
                    {"error": "Invalid or missing approval token. Use the link from the Slack incident message."}
                ),
            }

        self.approval_stub.lambda_handler = bad_token_handler
        resp = self.main_client.post(f"/api/incidents/{INC}/reject", json={"reason": "nope"})

        self.assertEqual(resp.status_code, 403)
        data = resp.get_data(as_text=True)
        self.assertIn("Invalid or missing approval token", data)
        self.assertIn("approval-token secret could not be read from SSM", data)

    def test_approve_detects_unlanded_deployed_approval(self):
        """Pre-fix deployed demo Lambdas return success while discarding the
        inner approval result. The proxy must verify the decision actually
        landed and surface a 502 with guidance when it did not."""
        def no_secret(Name, WithDecryption=False):
            raise ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
                "GetParameter",
            )

        self.approval_stub._ssm = SimpleNamespace(get_parameter=no_secret)
        deployed_ok = json.dumps({"message": f"Incident {INC} approved", "incident_id": INC})
        with mock.patch.object(self.lb, "_invoke_write_fallback", return_value=(200, deployed_ok)), \
                mock.patch.object(self.lb, "_incident_status_via_fallback", return_value="pending_approval"):
            resp = self.main_client.post(f"/api/incidents/{INC}/approve")

        self.assertEqual(resp.status_code, 502)
        self.assertIn("needs a redeploy", resp.get_data(as_text=True))

    def test_approve_passes_when_decision_lands(self):
        """When the delegated approval actually persists, the success is real."""
        def no_secret(Name, WithDecryption=False):
            raise ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
                "GetParameter",
            )

        self.approval_stub._ssm = SimpleNamespace(get_parameter=no_secret)
        deployed_ok = json.dumps({"message": f"Incident {INC} approved", "incident_id": INC})
        with mock.patch.object(self.lb, "_invoke_write_fallback", return_value=(200, deployed_ok)), \
                mock.patch.object(self.lb, "_incident_status_via_fallback", return_value="approved"):
            resp = self.main_client.post(f"/api/incidents/{INC}/approve")

        self.assertEqual(resp.status_code, 200)
        self.assertIn("approved", resp.get_data(as_text=True))

    def test_permission_error_detection(self):
        self.assertTrue(self.lb._is_permission_error("User is not authorized to perform: x"))
        self.assertTrue(self.lb._is_permission_error("An error occurred (AccessDenied) ..."))
        self.assertFalse(self.lb._is_permission_error("Invalid fault_class"))
        self.assertFalse(self.lb._is_permission_error("Incident was already processed"))

    def test_normalize_lambda_result_variants(self):
        ok = self.lb._normalize_lambda_result({"statusCode": 200, "body": json.dumps({"a": 1})})
        self.assertEqual(ok, (200, '{"a": 1}'))
        # Non-JSON body strings pass through untouched
        raw = self.lb._normalize_lambda_result({"statusCode": 403, "body": "plain text"})
        self.assertEqual(raw, (403, "plain text"))
        plain_dict = self.lb._normalize_lambda_result({"message": "hi"})
        self.assertEqual(plain_dict, (200, json.dumps({"message": "hi"})))
        self.assertIsNone(self.lb._normalize_lambda_result(None))


if __name__ == "__main__":
    unittest.main()
