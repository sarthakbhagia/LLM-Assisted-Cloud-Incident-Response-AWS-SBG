"""
test_verification.py — Unit tests for Phase 6.5 Verification Lambda.

The Lambda is two-phase: the first invoke schedules a one-off EventBridge
Scheduler re-invocation (+VERIFICATION_WAIT_SECONDS) and returns without
sleeping; the scheduled callback (phase="recheck") runs the signal re-check
and writes the outcome to DynamoDB.
"""

import json
import os
import sys
import unittest
from unittest import mock

import helpers  # noqa: F401
from helpers import REPO_ROOT, Fixture

VERIFICATION_DIR = os.path.join(REPO_ROOT, "backend", "verification")
VERIFICATION_PATH = os.path.join(VERIFICATION_DIR, "verification_lambda.py")


class _FakeContext:
    invoked_function_arn = (
        "arn:aws:lambda:ap-south-1:889081505756:function:verification-test"
    )


class TestVerificationScheduling(Fixture):
    """Phase 1: first invoke schedules the re-check and never sleeps."""

    def setUp(self):
        super().setUp()
        if VERIFICATION_DIR not in sys.path:
            sys.path.insert(0, VERIFICATION_DIR)
        self.mod = self.load_handler(
            VERIFICATION_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "SCHEDULER_ROLE_ARN": "arn:aws:iam::123456789012:role/scheduler-role",
                "SCHEDULER_GROUP_NAME": "verification-rechecks-staging",
                "PIPELINE_DLQ_ARN": "arn:aws:sqs:ap-south-1:123456789012:incident-pipeline-dlq-staging",
            },
        )
        self.set_table(self.aws["dynamodb.resource"], mock.MagicMock())
        self.scheduler = self.aws["scheduler"]
        self.created = {}

        def fake_create_schedule(**kwargs):
            if kwargs["Name"] in self.created:
                raise self.mod.ClientError(
                    {"Error": {"Code": "ConflictException", "Message": "exists"}},
                    "CreateSchedule",
                )
            self.created[kwargs["Name"]] = kwargs

        self.scheduler.create_schedule = fake_create_schedule

    def _event(self, **extra):
        event = {
            "incident_id": "inc-1",
            "fault_class": "resource_exhaustion",
            "original_signal": {"metric_name": "Duration"},
        }
        event.update(extra)
        return event

    def test_first_invoke_schedules_recheck_and_returns_without_sleeping(self):
        # The module no longer imports time at all; patch the stdlib anyway to
        # prove the scheduling path never sleeps.
        with mock.patch("time.sleep") as mock_sleep:
            res = self.mod.lambda_handler(self._event(), _FakeContext())
            mock_sleep.assert_not_called()

        self.assertEqual(res["statusCode"], 200)
        body = json.loads(res["body"])
        self.assertTrue(body["scheduled"])
        self.assertEqual(body["schedule_name"], "verify-inc-1")

        call = self.created["verify-inc-1"]
        self.assertEqual(call["GroupName"], "verification-rechecks-staging")
        self.assertTrue(call["ScheduleExpression"].startswith("at("))
        self.assertEqual(call["ScheduleExpressionTimezone"], "UTC")
        self.assertEqual(call["ActionAfterCompletion"], "DELETE")
        self.assertEqual(call["Target"]["Arn"], _FakeContext.invoked_function_arn)
        self.assertEqual(call["Target"]["RoleArn"],
                         "arn:aws:iam::123456789012:role/scheduler-role")
        payload = json.loads(call["Target"]["Input"])
        self.assertEqual(payload["phase"], "recheck")
        self.assertEqual(payload["incident_id"], "inc-1")
        # Scheduler retries cover transient failures; the DLQ catches the rest
        self.assertEqual(call["Target"]["RetryPolicy"]["MaximumRetryAttempts"], 5)
        self.assertEqual(
            call["Target"]["DeadLetterConfig"],
            {"Arn": "arn:aws:sqs:ap-south-1:123456789012:incident-pipeline-dlq-staging"},
        )

    def test_duplicate_invoke_is_idempotent(self):
        first = self.mod.lambda_handler(self._event(), _FakeContext())
        second = self.mod.lambda_handler(self._event(), _FakeContext())

        self.assertEqual(first["statusCode"], 200)
        self.assertEqual(second["statusCode"], 200)
        self.assertTrue(json.loads(second["body"]).get("already_scheduled"))
        self.assertEqual(len(self.created), 1)

    def test_schedule_failure_is_surfaced_not_swallowed(self):
        def boom(**kwargs):
            raise self.mod.ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "nope"}},
                "CreateSchedule",
            )
        self.scheduler.create_schedule = boom

        res = self.mod.lambda_handler(self._event(), _FakeContext())
        self.assertEqual(res["statusCode"], 500)

    def test_missing_target_arn_returns_500(self):
        res = self.mod.lambda_handler(self._event(), None)
        self.assertEqual(res["statusCode"], 500)

    def test_missing_incident_id_is_400(self):
        res = self.mod.lambda_handler({"phase": "recheck"}, _FakeContext())
        self.assertEqual(res["statusCode"], 400)


class TestVerificationRecheck(Fixture):
    """Phase 2: the scheduled callback runs the re-check and writes the result."""

    def setUp(self):
        super().setUp()
        if VERIFICATION_DIR not in sys.path:
            sys.path.insert(0, VERIFICATION_DIR)
        self.mod = self.load_handler(
            VERIFICATION_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev"},
        )
        self.set_table(self.aws["dynamodb.resource"], mock.MagicMock())

    def test_scheduled_recheck_runs_signal_check_and_writes_record(self):
        with (
            mock.patch.object(self.mod, "_recheck_signal") as mock_recheck,
            mock.patch.object(self.mod, "_update_verification_record") as mock_update_db,
        ):
            mock_recheck.return_value = (
                "resolved", "CloudWatch Metric Duration", "Metric below threshold")
            res = self.mod.lambda_handler(
                {
                    "incident_id": "inc-1",
                    "fault_class": "resource_exhaustion",
                    "original_signal": {"metric_name": "Duration"},
                    "phase": "recheck",
                },
                _FakeContext(),
            )

        self.assertEqual(res["statusCode"], 200)
        body = json.loads(res["body"])
        self.assertEqual(body["verification_status"], "resolved")
        mock_recheck.assert_called_once_with(
            "resource_exhaustion", {"metric_name": "Duration"})
        mock_update_db.assert_called_once_with(
            "inc-1", "resolved", "CloudWatch Metric Duration", "Metric below threshold")

    def test_recheck_without_incident_id_is_400(self):
        res = self.mod.lambda_handler({"phase": "recheck"}, _FakeContext())
        self.assertEqual(res["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
