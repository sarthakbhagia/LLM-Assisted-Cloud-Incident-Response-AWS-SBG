"""
test_verification.py — Unit tests for Phase 6.5 Verification Lambda.
"""

import json
import os
import sys
import unittest
from unittest import mock

import helpers  # noqa: F401
from helpers import REPO_ROOT, Fixture

VERIFICATION_DIR = os.path.join(REPO_ROOT, "src", "verification")
VERIFICATION_PATH = os.path.join(VERIFICATION_DIR, "app.py")


class TestVerificationLambda(Fixture):
    def setUp(self):
        super().setUp()
        if VERIFICATION_DIR not in sys.path:
            sys.path.insert(0, VERIFICATION_DIR)

    def test_verification_flow(self):
        mod = self.load_handler(
            VERIFICATION_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
            },
        )
        self.set_table(self.aws["dynamodb.resource"], mock.MagicMock())

        with (
            mock.patch.object(mod.time, "sleep") as mock_sleep,
            mock.patch.object(mod, "_recheck_signal") as mock_recheck,
            mock.patch.object(mod, "_update_verification_record") as mock_update_db,
        ):
            mock_recheck.return_value = ("resolved", "CloudWatch Metric Duration", "Metric below threshold")

            event = {
                "incident_id": "inc-1",
                "fault_class": "resource_exhaustion",
                "original_signal": {"metric_name": "Duration"},
            }
            res = mod.lambda_handler(event, None)
            self.assertEqual(res["statusCode"], 200)
            body = json.loads(res["body"])
            self.assertEqual(body["verification_status"], "resolved")
            self.assertTrue(mock_update_db.called)


if __name__ == "__main__":
    unittest.main()
