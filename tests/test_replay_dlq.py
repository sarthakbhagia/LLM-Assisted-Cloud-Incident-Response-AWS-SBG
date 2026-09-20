"""
test_replay_dlq.py — unit tests for scripts/replay_dlq.py.

Covers the classification ladder (rule envelopes, Lambda async envelopes,
scheduler payloads, raw business payloads, unknown shapes) and the drain
semantics (invoke-then-delete, failures and unknowns stay in the queue).
Uses the shared stdlib boto3 stub; no AWS access.
"""

import importlib.util
import json
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Fixture, REPO_ROOT  # noqa: E402

SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "replay_dlq.py")


class ReplayDlqTestBase(Fixture):
    """
    Loads the script under the Fixture stub. The script imports boto3 at
    module level, so it must be loaded only while the stub is installed -
    loading it with the real boto3 while the stub botocore occupies
    sys.modules breaks the import.
    """

    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("replay_dlq", SCRIPT_PATH)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)


class ClassificationTest(ReplayDlqTestBase):
    """Pure classification ladder - no AWS involved."""

    def test_eventbridge_rule_envelope_routes_by_inner_payload(self):
        msg = {
            "version": "0",
            "responseContext": {"statusCode": 200},
            "requestPayload": {
                "source": "cloudwatch",
                "fault_class": "resource_exhaustion",
                "alarm_name": "incident-service-a-resource-exhaustion-staging",
            },
        }
        target, payload, note = self.mod.classify_message(msg)
        self.assertEqual(target, "CollectorFunction")
        self.assertEqual(payload, msg["requestPayload"])
        self.assertEqual(note, "eventbridge-rule-envelope")

    def test_lambda_async_envelope_routes_by_request_payload(self):
        msg = {
            "requestContext": {"requestId": "req-1", "functionArn": "arn:..."},
            "responsePayload": {"statusCode": 500, "body": "{\"error\": \"boom\"}"},
            "requestPayload": {"incident_id": "inc-1"},
        }
        target, payload, note = self.mod.classify_message(msg)
        self.assertEqual(target, "RemediationFunction")
        self.assertEqual(payload, {"incident_id": "inc-1"})
        self.assertEqual(note, "lambda-async-envelope")

    def test_scheduler_recheck_payload_routes_to_verification(self):
        msg = {
            "incident_id": "inc-2",
            "phase": "recheck",
            "fault_class": "resource_exhaustion",
            "original_signal": {"threshold": 50000},
        }
        target, payload, note = self.mod.classify_message(msg)
        self.assertEqual(target, "VerificationFunction")
        self.assertEqual(payload, msg)
        self.assertEqual(note, "raw-payload")

    def test_alarm_event_without_envelope_routes_to_collector(self):
        msg = {
            "source": "cloudwatch",
            "fault_class": "service_cascade",
            "alarm_name": "incident-service-cascade-staging",
        }
        target, _, _ = self.mod.classify_message(msg)
        self.assertEqual(target, "CollectorFunction")

    def test_guardduty_event_routes_to_collector(self):
        target, _, _ = self.mod.classify_message(
            {"source": "guardduty", "fault_class": "misconfiguration"})
        self.assertEqual(target, "CollectorFunction")

    def test_approval_contract_routes_to_approval(self):
        target, _, _ = self.mod.classify_message(
            {"incident_id": "inc-3", "action": "approve", "token": "hmac"})
        self.assertEqual(target, "ApprovalFunction")

    def test_unknown_shape_is_not_classified(self):
        target, payload, note = self.mod.classify_message({"foo": "bar"})
        self.assertIsNone(target)
        self.assertIsNone(payload)
        self.assertEqual(note, "unknown-shape")

    def test_unparseable_rule_envelope_is_not_classified(self):
        target, payload, note = self.mod.classify_message(
            {"requestPayload": "not-json", "responseContext": {}})
        self.assertIsNone(target)
        self.assertEqual(note, "eventbridge-rule-envelope-unparseable")


class DrainLoopTest(ReplayDlqTestBase):
    """End-to-end drain against stubbed SQS/Lambda clients."""

    def setUp(self):
        super().setUp()
        # Pre-register the fake clients replay_message resolves internally.
        self.mod.boto3.client("sqs", region_name="ap-south-1")
        self.mod.boto3.client("lambda", region_name="ap-south-1")

    def _make_args(self, queue_url="https://sqs.ap-south-1.amazonaws.com/123/dlq"):
        args = types.SimpleNamespace(
            region="ap-south-1", stack=None, queue=None, env="staging",
            limit=50, dry_run=False, keep_poison=False, queue_url=queue_url,
        )
        return args

    def test_replayed_message_is_deleted_unknown_is_kept(self):
        sqs = self.aws["sqs"]
        lam = self.aws["lambda"]

        deleted = []

        def fake_delete(QueueUrl, ReceiptHandle):
            deleted.append(ReceiptHandle)
        sqs.delete_message = fake_delete

        invokes = []

        def fake_invoke(**kwargs):
            invokes.append(kwargs)
            return {"StatusCode": 202}
        lam.invoke = fake_invoke

        args = self._make_args()
        replayed_msg = {
            "Body": json.dumps({"source": "cloudwatch", "fault_class": "resource_exhaustion"}),
            "ReceiptHandle": "rh-1",
            "MessageAttributes": {},
        }
        unknown_msg = {
            "Body": json.dumps({"foo": "bar"}),
            "ReceiptHandle": "rh-2",
            "MessageAttributes": {},
        }
        with mock.patch.object(self.mod, "resolve_function_arn",
                               return_value="llm-CollectorFunction-abc"):
            outcome_r = self.mod.replay_message(sqs, lam, replayed_msg, args)
            outcome_u = self.mod.replay_message(sqs, lam, unknown_msg, args)

        self.assertEqual(outcome_r["status"], "replayed")
        self.assertEqual(outcome_r["target"], "llm-CollectorFunction-abc")
        self.assertEqual(deleted, ["rh-1"])  # unknown never deleted

        self.assertEqual(outcome_u["status"], "unknown")

        # event_uid injected for idempotent re-processing
        payload = json.loads(invokes[0]["Payload"])
        self.assertIn("event_uid", payload)

    def test_invoke_failure_leaves_message_in_queue(self):
        sqs = self.aws["sqs"]
        lam = self.aws["lambda"]

        deleted = []
        sqs.delete_message = lambda QueueUrl, ReceiptHandle: deleted.append(ReceiptHandle)
        lam.invoke = mock.Mock(side_effect=self.mod.ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "rate"}}, "Invoke"))

        args = self._make_args()
        msg = {
            "Body": json.dumps({"source": "cloudwatch", "fault_class": "resource_exhaustion"}),
            "ReceiptHandle": "rh-3",
            "MessageAttributes": {},
        }
        with mock.patch.object(self.mod, "resolve_function_arn",
                               return_value="llm-CollectorFunction-abc"):
            outcome = self.mod.replay_message(sqs, lam, msg, args)

        self.assertEqual(outcome["status"], "invoke-failed")
        self.assertEqual(deleted, [])  # stays for the next run

    def test_dry_run_classifies_but_neither_invokes_nor_deletes(self):
        sqs = self.aws["sqs"]
        lam = self.aws["lambda"]
        sqs.delete_message = mock.Mock()
        lam.invoke = mock.Mock()

        args = self._make_args()
        args.dry_run = True
        msg = {
            "Body": json.dumps({"source": "cloudwatch", "fault_class": "resource_exhaustion"}),
            "ReceiptHandle": "rh-4",
            "MessageAttributes": {},
        }
        with mock.patch.object(self.mod, "resolve_function_arn",
                               return_value="llm-CollectorFunction-abc"):
            outcome = self.mod.replay_message(sqs, lam, msg, args)

        self.assertEqual(outcome["status"], "dry-run")
        self.assertEqual(lam.invoke.call_count, 0)
        self.assertEqual(sqs.delete_message.call_count, 0)

    def test_main_exit_codes(self):
        sqs = self.aws["sqs"]

        # Empty queue -> exit 0
        sqs.receive_message = lambda **kwargs: {"Messages": []}
        rc = self.mod.main(["--queue", "https://q", "--env", "staging"])
        self.assertEqual(rc, 0)

        # Queue with one unknown-shape message -> exit 1, message kept.
        # Return the message once, then empty, so the drain loop terminates
        # the way a real queue behaves (the message is never deleted).
        remaining = [{"Body": "{\"mystery\": true}", "ReceiptHandle": "rh-9",
                      "MessageAttributes": {}}]
        sqs.receive_message = lambda **kwargs: {
            "Messages": [remaining.pop(0)] if remaining else []}
        sqs.delete_message = mock.Mock()
        rc = self.mod.main(["--queue", "https://q", "--env", "staging"])
        self.assertEqual(rc, 1)
        self.assertEqual(sqs.delete_message.call_count, 0)


if __name__ == "__main__":
    unittest.main()
