"""
test_remediation.py — Unit tests for Phase 6 Remediation Lambda.
"""

import json
import os
import sys
import unittest
from unittest import mock

import helpers  # noqa: F401
from helpers import REPO_ROOT, Fixture

REMEDIATION_DIR = os.path.join(REPO_ROOT, "backend", "remediation")
REMEDIATION_PATH = os.path.join(REMEDIATION_DIR, "remediation_lambda.py")


class TestRemediationLambda(Fixture):
    def setUp(self):
        super().setUp()
        if REMEDIATION_DIR not in sys.path:
            sys.path.insert(0, REMEDIATION_DIR)

    def test_remediation_unapproved_skipped(self):
        mod = self.load_handler(
            REMEDIATION_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
            },
        )
        with mock.patch.object(mod, "_get_incident_record") as mock_get_record:
            mock_get_record.return_value = {
                "incident_id": "inc-1",
                "remediation": {"status": "pending_approval"},
            }
            res = mod.lambda_handler({"incident_id": "inc-1"}, None)
            self.assertEqual(res["statusCode"], 409)
            self.assertIn("No remediation action was executed", res["body"])

    def test_remediation_approved_executed(self):
        mod = self.load_handler(
            REMEDIATION_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
            },
        )
        with (
            mock.patch.object(mod, "_get_incident_record") as mock_get_record,
            mock.patch.object(mod, "dispatch") as mock_dispatch,
            mock.patch.object(mod, "_update_remediation_record") as mock_update_db,
            mock.patch.object(mod, "_invoke_verification") as mock_verif,
        ):
            mock_get_record.return_value = {
                "incident_id": "inc-1",
                "fault_class": "resource_exhaustion",
                "remediation": {"status": "approved"},
                "diagnosis": {"suggested_action": "scale_up"},
            }
            mock_dispatch.return_value = {
                "action_key": "scale_up",
                "action_taken": "scale_up",
                "executed_at": "2026-01-01T00:00:00Z",
                "notes": "Scaled up successfully",
                "status": "executed",
                "success": True,
            }

            res = mod.lambda_handler({"incident_id": "inc-1"}, None)
            self.assertEqual(res["statusCode"], 200)
            self.assertTrue(mock_dispatch.called)
            self.assertTrue(mock_update_db.called)
            self.assertTrue(mock_verif.called)


if __name__ == "__main__":
    unittest.main()
