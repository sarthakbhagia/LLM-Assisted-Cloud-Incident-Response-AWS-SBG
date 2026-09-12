"""
test_collector.py — Unit tests for Phase 3 Collector Lambda.
"""

import json
import os
import sys
import unittest
from unittest import mock

import helpers  # noqa: F401
from helpers import REPO_ROOT, Fixture

COLLECTOR_PATH = os.path.join(REPO_ROOT, "src", "collector", "app.py")


class TestCollectorLambda(Fixture):
    def test_parse_event_cloudwatch(self):
        mod = self.load_handler(
            COLLECTOR_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        parsed = mod._parse_event({
            "source": "cloudwatch",
            "fault_class": "resource_exhaustion",
            "alarm_name": "test-alarm",
            "state": "ALARM",
        })
        self.assertEqual(parsed["fault_class"], "resource_exhaustion")
        self.assertEqual(parsed["alarm_name"], "test-alarm")

    def test_parse_event_invalid(self):
        mod = self.load_handler(
            COLLECTOR_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        with self.assertRaises(ValueError):
            mod._parse_event({"invalid": "event"})

    def test_handler_flow(self):
        mod = self.load_handler(
            COLLECTOR_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
                "DIAGNOSIS_FUNCTION_NAME": "test-diag-fn",
            },
        )
        self.set_table(self.aws["dynamodb.resource"], mock.MagicMock())
        mod._s3 = mock.MagicMock()

        with (
            mock.patch.object(mod, "_collect_evidence") as mock_evidence,
            mock.patch.object(mod, "_write_incident_record") as mock_write_rec,
            mock.patch.object(mod, "_invoke_diagnosis") as mock_diag,
        ):
            mock_evidence.return_value = {"metric": "data"}

            event = {
                "source": "cloudwatch",
                "fault_class": "resource_exhaustion",
                "alarm_name": "test-alarm",
                "state": "ALARM",
            }
            res = mod.lambda_handler(event, None)
            self.assertEqual(res["statusCode"], 200)
            body = json.loads(res["body"])
            self.assertIn("incident_id", body)
            self.assertTrue(mock_write_rec.called)
            self.assertTrue(mock_diag.called)


if __name__ == "__main__":
    unittest.main()
