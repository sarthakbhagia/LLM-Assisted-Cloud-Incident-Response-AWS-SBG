"""
test_notify.py — unit tests for the Phase 5 notify Lambda.

Uses mocked boto3 (stdlib-only stubs from helpers.py) — no AWS access needed.
Covers: happy path with Slack posting, message construction, approval links,
graceful degradation when config is missing, and payload escaping.
"""

import hashlib
import hmac
import json
import os
import re
import sys
import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

import helpers  # noqa: F401  (must precede botocore: installs stdlib-only stub)
from botocore.exceptions import ClientError

from helpers import REPO_ROOT, Fixture

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

APP = os.path.join(REPO_ROOT, "src", "reporting", "app.py")

SECRET = "test-secret"
INC = "11111111-2222-3333-4444-555555555555"
WEBHOOK = "https://hooks.slack.com/services/T000/B000/XYZ"
SSM_WEBHOOK = "/llm-incident-response/slack-webhook-url"
SSM_SECRET = "/llm-incident-response/approval-token-secret"
API_BASE = "https://api.example.com/prod/approval"

DIAGNOSIS = {
    "root_cause": "Memory pressure on <service-a> caused timeouts & errors",
    "confidence": 0.87,
    "affected_resources": ["incident-service-a-dev"],
    "suggested_action": "scale_up",
    "explanation": "Service A is <timing out> under memory pressure & needs a scale up",
    "reasoning_trace": "1) Duration breached. 2) Memory near limit. 3) No downstream errors.",
}


class FakeTable:
    def __init__(self, items=None):
        self.items = items or {}

    def get_item(self, Key):
        item = self.items.get(Key["incident_id"])
        return {"Item": item} if item else {}


class FakeBody:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text.encode("utf-8")


def notify_event(**extra):
    event = {"incident_id": INC, "diagnosis": dict(DIAGNOSIS)}
    event.update(extra)
    return event


class NotifyHandlerCase(Fixture):
    def setUp(self):
        super().setUp()
        self.mod = self.load_handler(APP)

    # -- fixture wiring -------------------------------------------------------

    @staticmethod
    def _not_found():
        raise ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "missing"}}, "GetParameter"
        )

    def _wire(self, incident_items=None, with_webhook=True, with_secret=True, s3_raw=None):
        # Handlers snapshot env into module constants at import; patch the
        # module attributes the code actually reads at call time.
        self.mod.INCIDENTS_TABLE = "incidents-dev"
        self.mod.DATA_LAKE_BUCKET = "datalake-dev"
        self.mod.SLACK_WEBHOOK_URL_SSM = SSM_WEBHOOK if with_webhook else ""
        self.mod.APPROVAL_TOKEN_SECRET_SSM = SSM_SECRET if with_secret else ""
        self.mod.APPROVAL_API_BASE = API_BASE

        params = {}
        if with_webhook:
            params[SSM_WEBHOOK] = WEBHOOK
        if with_secret:
            params[SSM_SECRET] = SECRET

        self.mod._ssm = SimpleNamespace(
            get_parameter=lambda Name, WithDecryption=False: (
                {"Parameter": {"Value": params[Name]}} if Name in params else self._not_found()
            )
        )
        self.mod._dynamodb = SimpleNamespace(
            Table=lambda TableName: FakeTable(incident_items or {})
        )
        if s3_raw is None:
            s3_raw = {}
        self.mod._s3 = SimpleNamespace(
            get_object=lambda Bucket, Key: (
                {"Body": FakeBody(s3_raw[Key])} if Key in s3_raw else self._not_found()
            )
        )
        self.mod._cache.clear()

    def incident_item(self, fault_class="resource_exhaustion"):
        return {
            "incident_id": INC,
            "fault_class": fault_class,
            "detected_at": "2026-09-12T10:00:00+00:00",
            "raw_data_s3_key": "incidents/" + INC + "/raw_data.json",
        }

    # -- happy path -------------------------------------------------------------

    def test_happy_path_posts_to_slack(self):
        self._wire(incident_items={INC: self.incident_item()})

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            resp = self.mod.lambda_handler(notify_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertTrue(json.loads(resp["body"])["slack_posted"])

        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args[0][0]
        self.assertTrue(request.full_url.startswith("https://hooks.slack.com/services/"))
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("blocks", payload)
        self.assertIn("11111111", payload["text"])
        self.assertIn("Resource Exhaustion", json.dumps(payload))

    def test_message_contains_diagnosis_fields(self):
        self._wire(incident_items={INC: self.incident_item()})

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            self.mod.lambda_handler(notify_event(), None)

        payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
        rendered = json.dumps(payload)
        self.assertIn("87%", rendered)                      # confidence
        self.assertIn("scale_up", rendered)                 # suggested action
        self.assertIn("incident-service-a-dev", rendered)   # affected resources
        self.assertIn("Memory pressure", rendered)          # root cause
        self.assertIn("needs a scale up", rendered)         # explanation

    def test_reasoning_trace_not_sent_to_slack(self):
        self._wire(incident_items={INC: self.incident_item()})

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            self.mod.lambda_handler(notify_event(), None)

        payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
        self.assertNotIn("reasoning_trace", json.dumps(payload))

    # -- approval links -----------------------------------------------------------

    def test_approval_links_signed_and_included(self):
        self._wire(incident_items={INC: self.incident_item()}, with_secret=True)

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            self.mod.lambda_handler(notify_event(), None)

        payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
        section_texts = [
            b["text"]["text"]
            for b in payload["blocks"]
            if b.get("type") == "section" and "Approve fix" in json.dumps(b)
        ]
        self.assertEqual(len(section_texts), 1)
        urls = re.findall(r"<(https://[^|>]+)\|", section_texts[0])
        self.assertEqual(len(urls), 2)

        # The link token is now bound to incident_id:action, not just incident_id.
        approve_token = hmac.new(
            SECRET.encode("utf-8"), f"{INC}:approve".encode("utf-8"), hashlib.sha256
        ).hexdigest()
        reject_token = hmac.new(
            SECRET.encode("utf-8"), f"{INC}:reject".encode("utf-8"), hashlib.sha256
        ).hexdigest()
        approve = [u for u in urls if "action=approve" in u]
        reject = [u for u in urls if "action=reject" in u]
        self.assertEqual(len(approve), 1)
        self.assertEqual(len(reject), 1)
        self.assertIn("token=" + approve_token, approve[0])
        self.assertIn("token=" + reject_token, reject[0])
        # Cross-check: the approve token must NOT verify for a reject action.
        reject_check = hmac.new(
            SECRET.encode("utf-8"), f"{INC}:reject".encode("utf-8"), hashlib.sha256
        ).hexdigest()
        self.assertNotEqual(approve_token, reject_check)

    def test_approval_links_omitted_without_base_url(self):
        self._wire(incident_items={INC: self.incident_item()})
        self.mod.APPROVAL_API_BASE = ""

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            resp = self.mod.lambda_handler(notify_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
        self.assertIn("Approval links not configured", json.dumps(payload))
        self.assertNotIn("action=approve", json.dumps(payload))

    # -- graceful degradation -------------------------------------------------------

    def test_no_webhook_configured_skips_posting(self):
        self._wire(incident_items={INC: self.incident_item()}, with_webhook=False)

        with mock.patch("urllib.request.urlopen") as urlopen:
            resp = self.mod.lambda_handler(notify_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertFalse(json.loads(resp["body"])["slack_posted"])
        urlopen.assert_not_called()

    def test_missing_incident_record_falls_back_to_payload_fields(self):
        self._wire(incident_items={})  # empty table

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            resp = self.mod.lambda_handler(
                notify_event(fault_class="service_cascade"), None
            )

        self.assertEqual(resp["statusCode"], 200)
        payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
        self.assertIn("Service Failure Cascade", json.dumps(payload))

    def test_dynamodb_error_does_not_break_message(self):
        class ExplodingTable:
            def get_item(self, Key):
                raise ClientError(
                    {"Error": {"Code": "InternalServerError", "Message": "boom"}},
                    "GetItem",
                )

        self._wire()
        self.mod._dynamodb = SimpleNamespace(Table=lambda TableName: ExplodingTable())

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            resp = self.mod.lambda_handler(notify_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
        rendered = json.dumps(payload)
        self.assertIn("Evidence unavailable", rendered)
        self.assertIn("check Lambda logs", rendered)

    # -- detection context -------------------------------------------------------------

    def test_detection_trigger_context_included(self):
        raw = json.dumps({
            "detection_source": "cloudwatch",
            "detection_event": {
                "source": "cloudwatch",
                "alarm_name": "incident-service-a-resource-exhaustion-dev",
                "resource_id": "incident-service-a-resource-exhaustion-dev",
            },
        })
        self._wire(
            incident_items={INC: self.incident_item()},
            s3_raw={"incidents/" + INC + "/raw_data.json": raw},
        )

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            self.mod.lambda_handler(notify_event(), None)

        payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
        rendered = json.dumps(payload)
        self.assertIn("Triggered by", rendered)
        self.assertIn("incident-service-a-resource-exhaustion-dev", rendered)

    # -- escaping --------------------------------------------------------------------------

    def test_special_characters_escaped(self):
        self._wire(incident_items={INC: self.incident_item()})

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = SimpleNamespace(
                read=lambda: b"ok", status=200
            )
            self.mod.lambda_handler(notify_event(), None)

        rendered = json.dumps(json.loads(urlopen.call_args[0][0].data.decode("utf-8")))
        self.assertIn("&lt;service-a&gt;", rendered)
        self.assertIn("&amp;", rendered)
        self.assertNotIn("<service-a>", rendered)

    # -- input validation ----------------------------------------------------------------

    def test_missing_incident_id_returns_400(self):
        self._wire()
        resp = self.mod.lambda_handler({"diagnosis": DIAGNOSIS}, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_missing_diagnosis_returns_400(self):
        self._wire()
        resp = self.mod.lambda_handler({"incident_id": INC}, None)
        self.assertEqual(resp["statusCode"], 400)

    # -- Slack delivery failures ----------------------------------------------------------

    def test_slack_http_error_returns_false(self):
        self._wire(incident_items={INC: self.incident_item()})

        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(WEBHOOK, 500, "Server Error", None, None),
        ):
            resp = self.mod.lambda_handler(notify_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertFalse(json.loads(resp["body"])["slack_posted"])

    def test_slack_connection_error_returns_false(self):
        self._wire(incident_items={INC: self.incident_item()})

        with mock.patch(
            "urllib.request.urlopen", side_effect=OSError("connection refused")
        ):
            resp = self.mod.lambda_handler(notify_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertFalse(json.loads(resp["body"])["slack_posted"])


if __name__ == "__main__":
    unittest.main()
