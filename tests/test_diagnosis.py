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

DIAGNOSIS_DIR = os.path.join(REPO_ROOT, "backend", "diagnosis")
DIAGNOSIS_PATH = os.path.join(DIAGNOSIS_DIR, "diagnosis_lambda.py")


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

    def test_parse_fenced_json(self):
        """Test that fenced JSON (```json ... ```) is properly extracted."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        
        fenced_response = '''```json
{
    "root_cause": "CPU spike",
    "confidence": 0.9,
    "affected_resources": ["service-a"],
    "suggested_action": "scale_up",
    "explanation": "Service A needs scaling",
    "reasoning_trace": "High CPU detected"
}
```'''
        result = mod._parse_and_validate_json(fenced_response)
        self.assertEqual(result["root_cause"], "CPU spike")
        self.assertEqual(result["confidence"], 0.9)
        self.assertEqual(result["suggested_action"], "scale_up")

    def test_parse_fenced_json_no_language_spec(self):
        """Test that fenced JSON without language specifier is handled."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        
        fenced_response = '''```
{
    "root_cause": "Memory leak",
    "confidence": 0.85,
    "affected_resources": ["service-b"],
    "suggested_action": "restart_service",
    "explanation": "Service B needs restart",
    "reasoning_trace": "Memory increasing over time"
}
```'''
        result = mod._parse_and_validate_json(fenced_response)
        self.assertEqual(result["root_cause"], "Memory leak")
        self.assertEqual(result["suggested_action"], "restart_service")

    def test_parse_invalid_json_raises(self):
        """Test that invalid JSON raises ValueError."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        
        invalid_json = '{"root_cause": "test", "confidence": 0.9, "affected_resources": ["a"], "suggested_action": "scale_up", "explanation": "test", "reasoning_trace": "test"'
        # Missing closing brace
        with self.assertRaises(ValueError):
            mod._parse_and_validate_json(invalid_json)

    def test_parse_truncated_json_raises(self):
        """Test that truncated JSON (missing fields) raises ValueError."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        
        # Missing required fields
        truncated = '{"root_cause": "test"}'
        with self.assertRaises(ValueError):
            mod._parse_and_validate_json(truncated)

    def test_parse_json_with_string_confidence(self):
        """Test that string confidence values are normalized."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        
        response = '''{
            "root_cause": "CPU spike",
            "confidence": "High",
            "affected_resources": ["service-a"],
            "suggested_action": "scale_up",
            "explanation": "Service A needs scaling",
            "reasoning_trace": "High CPU detected"
        }'''
        result = mod._parse_and_validate_json(response)
        self.assertEqual(result["confidence"], 0.9)

    def test_parse_json_with_array_reasoning_trace(self):
        """Test that array reasoning_trace is converted to string."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        
        response = '''{
            "root_cause": "CPU spike",
            "confidence": 0.9,
            "affected_resources": ["service-a"],
            "suggested_action": "scale_up",
            "explanation": "Service A needs scaling",
            "reasoning_trace": ["Step 1: Check CPU", "Step 2: Check memory"]
        }'''
        result = mod._parse_and_validate_json(response)
        self.assertIsInstance(result["reasoning_trace"], str)
        self.assertIn("Step 1", result["reasoning_trace"])
        self.assertIn("Step 2", result["reasoning_trace"])

    def test_parse_json_invalid_action_raises(self):
        """Test that invalid suggested_action raises ValueError."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        
        response = '''{
            "root_cause": "CPU spike",
            "confidence": 0.9,
            "affected_resources": ["service-a"],
            "suggested_action": "invalid_action",
            "explanation": "Service A needs scaling",
            "reasoning_trace": "High CPU detected"
        }'''
        with self.assertRaises(ValueError):
            mod._parse_and_validate_json(response)

    def test_parse_json_action_normalization(self):
        """Test that action synonyms are normalized to valid actions."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        
        test_cases = [
            ("increase instance type", "scale_up"),
            ("scale out", "scale_up"),
            ("restart", "restart_service"),
            ("restart service", "restart_service"),
            ("lock bucket", "lock_s3_bucket"),
            ("block public access", "lock_s3_bucket"),
            ("tighten policy", "tighten_iam_policy"),
            ("restrict permissions", "tighten_iam_policy"),
            ("restart downstream", "restart_service"),
            ("manual review", "manual_review_required"),
            ("investigate manually", "manual_review_required"),
        ]
        
        for input_action, expected_action in test_cases:
            with self.subTest(input_action=input_action):
                response = f'''{{
                    "root_cause": "Test",
                    "confidence": 0.9,
                    "affected_resources": ["service-a"],
                    "suggested_action": "{input_action}",
                    "explanation": "Test explanation",
                    "reasoning_trace": "Test trace"
                }}'''
                result = mod._parse_and_validate_json(response)
                self.assertEqual(result["suggested_action"], expected_action)

    def test_invoke_llm_with_validation_truncated_handling(self):
        """Test that truncated LLM output is handled with retry and S3 save."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        self.set_table(self.aws["dynamodb.resource"], mock.MagicMock())
        
        # Mock S3 client for saving raw response
        mock_s3_client = mock.MagicMock()
        mod._s3 = mock_s3_client
        
        with (
            mock.patch.object(mod, "_fetch_s3_raw_data") as mock_s3,
            mock.patch.object(mod, "_call_bedrock") as mock_bedrock,
            mock.patch.object(mod, "_update_dynamodb_diagnosis") as mock_update_db,
            mock.patch.object(mod, "_invoke_notify") as mock_notify,
        ):
            mock_s3.return_value = {"fault_class": "resource_exhaustion", "evidence": {}}
            
            # _call_bedrock returns (text, stop_reason, is_truncated)
            # First call: truncated JSON response
            # Second call (retry): also truncated
            truncated_json = '{"root_cause": "test", "confidence": 0.9, "affected_resources": ["a"], "suggested_action": "scale_up", "explanation": "test", "reasoning_trace": "test"'
            mock_bedrock.side_effect = [
                (truncated_json, "max_tokens", True),  # initial call - truncated
                (truncated_json, "max_tokens", True),  # retry call - also truncated
            ]
            
            event = {
                "incident_id": "test-inc-truncated",
                "fault_class": "resource_exhaustion",
                "raw_data_s3_key": "incidents/test-inc-truncated/raw_data.json",
            }
            
            res = mod.lambda_handler(event, None)
            self.assertEqual(res["statusCode"], 200)
            
            # Should have saved raw response to S3 twice (initial + retry)
            self.assertEqual(mock_s3_client.put_object.call_count, 2)
            
            # Verify fallback diagnosis with parse_failed status
            body = json.loads(res["body"])
            self.assertEqual(body["diagnosis"]["diagnosis_status"], "parse_failed")
            self.assertIn("truncated", body["failure_mode"])
            
            # Verify DynamoDB update was called with parse_failed status
            self.assertTrue(mock_update_db.called)
            call_args = mock_update_db.call_args
            self.assertEqual(call_args[0][1].get("diagnosis_status"), "parse_failed")


if __name__ == "__main__":
    unittest.main()
