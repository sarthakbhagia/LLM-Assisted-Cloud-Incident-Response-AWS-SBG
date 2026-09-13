"""
test_diagnosis.py — Unit tests for Phase 4 Diagnosis Lambda and runbook loader.
"""

import json
import os
import sys
import unittest
from unittest import mock

import helpers  # noqa: F401
from helpers import REPO_ROOT, Fixture

DIAGNOSIS_DIR = os.path.join(REPO_ROOT, "src", "diagnosis")
DIAGNOSIS_PATH = os.path.join(DIAGNOSIS_DIR, "app.py")


class TestDiagnosisLambda(Fixture):
    def setUp(self):
        super().setUp()
        if DIAGNOSIS_DIR not in sys.path:
            sys.path.insert(0, DIAGNOSIS_DIR)

    def test_runbook_loader(self):
        from runbook_loader import load_runbook

        content = load_runbook("resource_exhaustion")
        self.assertIn("Resource Exhaustion", content)

        content_unknown = load_runbook("unknown_class")
        self.assertIn("Default Runbook", content_unknown)

    def test_diagnosis_flow(self):
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        self.set_table(self.aws["dynamodb.resource"], mock.MagicMock())

        with (
            mock.patch.object(mod, "_fetch_s3_raw_data") as mock_s3,
            mock.patch.object(mod, "_invoke_llm_with_validation") as mock_llm,
            mock.patch.object(mod, "_update_dynamodb_diagnosis") as mock_update_db,
            mock.patch.object(mod, "_invoke_notify") as mock_notify,
        ):
            mock_s3.return_value = {"fault_class": "resource_exhaustion", "evidence": {}}
            mock_llm.return_value = (
                {
                    "root_cause": "CPU spike",
                    "confidence": 0.9,
                    "affected_resources": ["res1"],
                    "suggested_action": "scale_up",
                    "explanation": "Scale up needed",
                    "reasoning_trace": "Trace...",
                },
                None,
            )

            event = {
                "incident_id": "test-inc-123",
                "fault_class": "resource_exhaustion",
                "raw_data_s3_key": "incidents/test-inc-123/raw_data.json",
            }
            res = mod.lambda_handler(event, None)
            self.assertEqual(res["statusCode"], 200)
            self.assertTrue(mock_update_db.called)
            self.assertTrue(mock_notify.called)


if __name__ == "__main__":
    unittest.main()
