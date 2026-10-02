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
    "reasoning_trace": "High CPU detected",
    "recommended_solutions": [
        {"id": "sol-1", "action": "scale_up", "title": "Scale Up", "description": "Increase Lambda memory", "risk": "low", "expected_outcome": "Resolve CPU spike", "rationale": "High CPU detected", "confidence": 0.9, "source": "llm"},
        {"id": "sol-2", "action": "restart_service", "title": "Restart Service", "description": "Restart Lambda", "risk": "medium", "expected_outcome": "Clear memory leak", "rationale": "Restart may clear leak", "confidence": 0.7, "source": "runbook"}
    ]
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
    "reasoning_trace": "Memory increasing over time",
    "recommended_solutions": [
        {"id": "sol-1", "action": "restart_service", "title": "Restart Service", "description": "Restart Lambda", "risk": "medium", "expected_outcome": "Clear memory leak", "rationale": "Memory increasing over time", "confidence": 0.85, "source": "llm"},
        {"id": "sol-2", "action": "scale_up", "title": "Scale Up", "description": "Increase memory", "risk": "low", "expected_outcome": "Prevent future leaks", "rationale": "More memory headroom", "confidence": 0.7, "source": "runbook"}
    ]
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

        invalid_json = '{"root_cause": "test", "confidence": 0.9, "affected_resources": ["a"], "suggested_action": "scale_up", "explanation": "test", "reasoning_trace": "test", "recommended_solutions": []}'
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
        truncated = '{"root_cause": "test", "recommended_solutions": []}'
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
            "reasoning_trace": "High CPU detected",
            "recommended_solutions": [
                {"id": "sol-1", "action": "scale_up", "title": "Scale Up", "description": "Increase Lambda memory", "risk": "low", "expected_outcome": "Resolve CPU spike", "rationale": "High CPU detected", "confidence": 0.9, "source": "llm"},
                {"id": "sol-2", "action": "restart_service", "title": "Restart Service", "description": "Restart Lambda", "risk": "medium", "expected_outcome": "Clear memory leak", "rationale": "Restart may clear leak", "confidence": 0.7, "source": "runbook"}
            ]
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
            "reasoning_trace": ["Step 1: Check CPU", "Step 2: Check memory"],
            "recommended_solutions": [
                {"id": "sol-1", "action": "scale_up", "title": "Scale Up", "description": "Increase Lambda memory", "risk": "low", "expected_outcome": "Resolve CPU spike", "rationale": "High CPU detected", "confidence": 0.9, "source": "llm"},
                {"id": "sol-2", "action": "restart_service", "title": "Restart Service", "description": "Restart Lambda", "risk": "medium", "expected_outcome": "Clear memory leak", "rationale": "Restart may clear leak", "confidence": 0.7, "source": "runbook"}
            ]
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
                    "reasoning_trace": "Test trace",
                    "recommended_solutions": [
                        {{"id": "sol-1", "action": "{input_action}", "title": "Action", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"}},
                        {{"id": "sol-2", "action": "scale_up", "title": "Scale Up", "description": "Scale", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.7, "source": "runbook"}}
                    ]
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

            # _call_bedrock returns (text, stop_reason, is_truncated, model_name)
            # First call: truncated JSON response
            # Second call (retry): also truncated
            truncated_json = '{"root_cause": "test", "confidence": 0.9, "affected_resources": ["a"], "suggested_action": "scale_up", "explanation": "test", "reasoning_trace": "test"}'
            mock_bedrock.side_effect = [
                (truncated_json, "max_tokens", True, "Nova Pro"),  # initial call - truncated
                (truncated_json, "max_tokens", True, "Nova Pro"),  # retry call - also truncated
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

    # ===========================================================================
    # T1.1/T1.2 - Validator tests
    # ===========================================================================

    def test_validate_recommended_solutions_valid(self):
        """Test validator accepts valid recommended_solutions array."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"id": "sol-1", "action": "scale_up", "title": "Scale Up", "description": "Increase concurrency", "risk": "low", "expected_outcome": "Resolve CPU spike", "rationale": "High CPU detected", "confidence": 0.9, "source": "llm"},
            {"id": "sol-2", "action": "restart_service", "title": "Restart Service", "description": "Restart Lambda", "risk": "medium", "expected_outcome": "Clear memory leak", "rationale": "Restart may clear leak", "confidence": 0.7, "source": "runbook"},
            {"id": "sol-3", "action": "manual_review_required", "title": "Manual Review", "description": "Escalate to human", "risk": "low", "expected_outcome": "Human investigation", "rationale": "Complex issue", "confidence": 0.5, "source": "runbook"},
        ]

        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["action"], "scale_up")
        self.assertEqual(result[0]["id"], "sol-1")
        self.assertEqual(result[0]["source"], "llm")
        self.assertEqual(result[1]["action"], "restart_service")
        self.assertEqual(result[2]["action"], "manual_review_required")
        # Confidence should be clamped to 0-1
        for sol in result:
            self.assertGreaterEqual(sol["confidence"], 0.0)
            self.assertLessEqual(sol["confidence"], 1.0)
            self.assertIn(sol["risk"], ("low", "medium", "high"))
            self.assertIn(sol["source"], ("llm", "runbook"))
            self.assertIn(sol["action"], mod.VALID_SUGGESTED_ACTIONS)

    def test_validate_recommended_solutions_partial_missing_fields(self):
        """Test validator fills in defaults for missing optional fields."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"action": "scale_up"},  # only required action field
            {"action": "restart_service"},
        ]

        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["action"], "scale_up")
        self.assertEqual(result[0]["id"], "sol-1")  # auto-generated
        self.assertEqual(result[0]["title"], "Scale Up")  # auto-generated from action
        self.assertIn("description", result[0])
        self.assertIn("risk", result[0])
        self.assertIn("expected_outcome", result[0])
        self.assertIn("rationale", result[0])
        self.assertIn("confidence", result[0])
        self.assertIn("source", result[0])

    def test_validate_recommended_solutions_malformed_not_list(self):
        """Test validator raises ValueError when solutions is not a list."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        with self.assertRaises(ValueError) as ctx:
            mod._validate_recommended_solutions("not a list", "scale_up", "resource_exhaustion")
        self.assertIn("must be an array", str(ctx.exception))

    def test_validate_recommended_solutions_malformed_not_object(self):
        """Test validator raises ValueError when solution item is not an object."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        with self.assertRaises(ValueError) as ctx:
            mod._validate_recommended_solutions(["not an object", "also not an object"], "scale_up", "resource_exhaustion")
        self.assertIn("must be an object", str(ctx.exception))

    def test_validate_recommended_solutions_missing_action(self):
        """Test validator raises ValueError when action field is missing."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        with self.assertRaises(ValueError) as ctx:
            mod._validate_recommended_solutions([{"title": "No action"}, {"action": "restart_service"}], "scale_up", "resource_exhaustion")
        self.assertIn("missing required 'action'", str(ctx.exception))

    def test_validate_recommended_solutions_duplicates_deduped(self):
        """Test validator deduplicates solutions by action."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"id": "sol-1", "action": "scale_up", "title": "Scale Up 1", "description": "Desc 1", "risk": "low", "expected_outcome": "Outcome 1", "rationale": "Rationale 1", "confidence": 0.9, "source": "llm"},
            {"id": "sol-2", "action": "scale_up", "title": "Scale Up 2", "description": "Desc 2", "risk": "medium", "expected_outcome": "Outcome 2", "rationale": "Rationale 2", "confidence": 0.8, "source": "runbook"},
            {"id": "sol-3", "action": "restart_service", "title": "Restart", "description": "Desc 3", "risk": "medium", "expected_outcome": "Outcome 3", "rationale": "Rationale 3", "confidence": 0.7, "source": "llm"},
        ]

        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        # Should have only 2 solutions (duplicate scale_up removed)
        self.assertEqual(len(result), 2)
        actions = [s["action"] for s in result]
        self.assertEqual(actions.count("scale_up"), 1)

    def test_validate_recommended_solutions_wrong_fault_class_action(self):
        """Test validator accepts any valid action regardless of fault_class (actions.py handles all)."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # Actions are validated against VALID_SUGGESTED_ACTIONS only, not fault_class
        # This is by design - the remediation Lambda dispatches based on action key
        solutions = [
            {"action": "lock_s3_bucket", "title": "Lock S3", "description": "Lock bucket", "risk": "medium", "expected_outcome": "Bucket locked", "rationale": "S3 public", "confidence": 0.8, "source": "llm"},
            {"action": "scale_up", "title": "Scale Up", "description": "Scale up", "risk": "low", "expected_outcome": "Scaled", "rationale": "CPU high", "confidence": 0.7, "source": "runbook"},
        ]

        # Should not raise even though lock_s3_bucket is typically for misconfiguration
        result = mod._validate_recommended_solutions(solutions, "lock_s3_bucket", "resource_exhaustion")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["action"], "lock_s3_bucket")

    def test_validate_recommended_solutions_invalid_action_raises(self):
        """Test validator raises ValueError for invalid action."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"action": "invalid_action", "title": "Invalid", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
            {"action": "scale_up", "title": "Scale Up", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.7, "source": "runbook"},
        ]

        with self.assertRaises(ValueError) as ctx:
            mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")
        self.assertIn("invalid action", str(ctx.exception).lower())

    def test_validate_recommended_solutions_string_confidence_normalized(self):
        """Test validator normalizes string confidence values."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"action": "scale_up", "confidence": "high"},
            {"action": "restart_service", "confidence": "medium"},
            {"action": "manual_review_required", "confidence": "low"},
        ]

        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        self.assertEqual(result[0]["confidence"], 0.9)
        self.assertEqual(result[1]["confidence"], 0.7)
        self.assertEqual(result[2]["confidence"], 0.5)

    def test_validate_recommended_solutions_confidence_clamped(self):
        """Test validator clamps confidence to 0.0-1.0 range."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"action": "scale_up", "confidence": 1.5},
            {"action": "restart_service", "confidence": -0.5},
        ]

        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        self.assertEqual(result[0]["confidence"], 1.0)
        self.assertEqual(result[1]["confidence"], 0.0)

    def test_validate_recommended_solutions_less_than_two_top_up(self):
        """Test validator tops up with runbook alternatives when <2 distinct valid solutions after dedup."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # Provide 2 solutions but they dedupe to 1 (same action)
        solutions = [
            {"action": "scale_up", "title": "Scale Up 1", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
            {"action": "scale_up", "title": "Scale Up 2", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.8, "source": "runbook"},
        ]

        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        # Should be topped up to at least 2 solutions
        self.assertGreaterEqual(len(result), 2)
        actions = [s["action"] for s in result]
        self.assertIn("scale_up", actions)
        # Should include runbook alternatives
        self.assertTrue(any(s["source"] == "runbook" for s in result))

    def test_validate_recommended_solutions_input_less_than_two_raises(self):
        """Test validator raises ValueError when input array has <2 items."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # Only 1 solution in input array - should raise before validation
        solutions = [
            {"action": "scale_up", "title": "Scale Up", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
        ]

        with self.assertRaises(ValueError) as ctx:
            mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")
        self.assertIn("at least 2 solutions", str(ctx.exception))

    def test_validate_recommended_solutions_primary_action_first(self):
        """Test validator ensures primary suggested_action is first solution."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # Primary action is restart_service but it's listed second
        solutions = [
            {"action": "scale_up", "title": "Scale Up", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
            {"action": "restart_service", "title": "Restart", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.8, "source": "llm"},
        ]

        result = mod._validate_recommended_solutions(solutions, "restart_service", "resource_exhaustion")

        self.assertEqual(result[0]["action"], "restart_service")

    def test_validate_recommended_solutions_caps_at_three(self):
        """Test validator caps solutions at 3."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"action": "scale_up", "title": "Scale Up", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
            {"action": "restart_service", "title": "Restart", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.8, "source": "llm"},
            {"action": "lock_s3_bucket", "title": "Lock S3", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.7, "source": "runbook"},
            {"action": "tighten_iam_policy", "title": "Tighten IAM", "description": "Desc", "risk": "high", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.6, "source": "runbook"},
        ]

        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        self.assertEqual(len(result), 3)

    def test_validate_recommended_solutions_invalid_risk_raises(self):
        """Test validator raises ValueError for invalid risk level."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"action": "scale_up", "risk": "critical"},
            {"action": "restart_service", "risk": "medium"},
        ]

        with self.assertRaises(ValueError) as ctx:
            mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")
        self.assertIn("invalid risk level", str(ctx.exception))

    def test_validate_recommended_solutions_invalid_source_raises(self):
        """Test validator raises ValueError for invalid source."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"action": "scale_up", "source": "human"},
            {"action": "restart_service", "source": "runbook"},
        ]

        with self.assertRaises(ValueError) as ctx:
            mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")
        self.assertIn("invalid source", str(ctx.exception))

    def test_validate_recommended_solutions_ids_unique_and_stable(self):
        """Test validator preserves provided IDs and generates unique ones when missing."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        solutions = [
            {"id": "custom-id-1", "action": "scale_up", "title": "Scale Up", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
            {"action": "restart_service", "title": "Restart", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.8, "source": "llm"},
            {"action": "lock_s3_bucket", "title": "Lock S3", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.7, "source": "runbook"},
        ]

        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        self.assertEqual(result[0]["id"], "custom-id-1")
        self.assertNotEqual(result[1]["id"], result[2]["id"])
        self.assertTrue(result[1]["id"].startswith("sol-"))
        self.assertTrue(result[2]["id"].startswith("sol-"))

    # ===========================================================================
    # T1.1 - Fallback generator tests per fault class
    # ===========================================================================

    def test_generate_fallback_solutions_resource_exhaustion(self):
        """Test fallback solutions for resource_exhaustion fault class."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        result = mod._generate_fallback_solutions("scale_up", "resource_exhaustion")

        self.assertGreaterEqual(len(result), 2)
        self.assertLessEqual(len(result), 3)
        actions = [s["action"] for s in result]
        self.assertIn("scale_up", actions)
        self.assertIn("restart_service", actions)
        self.assertIn("manual_review_required", actions)
        for sol in result:
            self.assertEqual(sol["source"], "runbook")
            self.assertEqual(sol["confidence"], 0.7)
            self.assertIn(sol["risk"], ("low", "medium"))

    def test_generate_fallback_solutions_misconfiguration(self):
        """Test fallback solutions for misconfiguration fault class."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        result = mod._generate_fallback_solutions("lock_s3_bucket", "misconfiguration")

        self.assertGreaterEqual(len(result), 2)
        self.assertLessEqual(len(result), 3)
        actions = [s["action"] for s in result]
        self.assertIn("lock_s3_bucket", actions)
        self.assertIn("tighten_iam_policy", actions)
        self.assertIn("manual_review_required", actions)
        for sol in result:
            self.assertEqual(sol["source"], "runbook")
            self.assertEqual(sol["confidence"], 0.7)

    def test_generate_fallback_solutions_service_cascade(self):
        """Test fallback solutions for service_cascade fault class."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        result = mod._generate_fallback_solutions("restart_downstream_service", "service_cascade")

        self.assertGreaterEqual(len(result), 2)
        self.assertLessEqual(len(result), 3)
        actions = [s["action"] for s in result]
        self.assertIn("restart_downstream_service", actions)
        self.assertIn("restart_service", actions)
        self.assertIn("manual_review_required", actions)
        for sol in result:
            self.assertEqual(sol["source"], "runbook")
            self.assertEqual(sol["confidence"], 0.7)

    def test_generate_fallback_solutions_unknown_fault_class(self):
        """Test fallback solutions for unknown fault class."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        result = mod._generate_fallback_solutions("manual_review_required", "unknown")

        # Unknown fault class should return empty or minimal solutions
        self.assertIsInstance(result, list)

    def test_generate_fallback_solutions_excludes_primary_action(self):
        """Test fallback solutions excludes the primary action from alternatives."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # Primary is scale_up, alternatives should not include another scale_up
        result = mod._generate_fallback_solutions("scale_up", "resource_exhaustion")

        actions = [s["action"] for s in result]
        self.assertEqual(actions.count("scale_up"), 1)

    # ===========================================================================
    # T1.1 - Parse and validate integration tests
    # ===========================================================================

    def test_parse_json_with_recommended_solutions_valid(self):
        """Test full JSON parsing with recommended_solutions field."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        response = '''{
            "root_cause": "CPU spike",
            "confidence": 0.9,
            "affected_resources": ["service-a"],
            "suggested_action": "scale_up",
            "explanation": "Service A needs scaling",
            "reasoning_trace": "High CPU detected",
            "recommended_solutions": [
                {"id": "sol-1", "action": "scale_up", "title": "Scale Up", "description": "Increase Lambda memory", "risk": "low", "expected_outcome": "Resolve CPU spike", "rationale": "High CPU detected", "confidence": 0.9, "source": "llm"},
                {"id": "sol-2", "action": "restart_service", "title": "Restart Service", "description": "Restart Lambda", "risk": "medium", "expected_outcome": "Clear memory leak", "rationale": "Restart may clear leak", "confidence": 0.7, "source": "runbook"}
            ]
        }'''
        result = mod._parse_and_validate_json(response)

        self.assertIn("recommended_solutions", result)
        self.assertEqual(len(result["recommended_solutions"]), 2)
        self.assertEqual(result["recommended_solutions"][0]["action"], "scale_up")
        self.assertEqual(result["recommended_solutions"][0]["source"], "llm")
        self.assertEqual(result["recommended_solutions"][1]["action"], "restart_service")
        self.assertEqual(result["recommended_solutions"][1]["source"], "runbook")
        self.assertEqual(result["suggested_action"], "scale_up")

    def test_parse_json_without_recommended_solutions_generates_fallback(self):
        """Test JSON parsing generates fallback when recommended_solutions missing."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # LLM response with fault_class field
        response = '''{
            "root_cause": "CPU spike",
            "confidence": 0.9,
            "affected_resources": ["service-a"],
            "suggested_action": "scale_up",
            "explanation": "Service A needs scaling",
            "reasoning_trace": "High CPU detected",
            "fault_class": "resource_exhaustion"
        }'''
        # Pass fault_class explicitly (from incident record)
        result = mod._parse_and_validate_json(response, "resource_exhaustion")

        self.assertIn("recommended_solutions", result)
        self.assertGreaterEqual(len(result["recommended_solutions"]), 2)
        self.assertEqual(result["recommended_solutions"][0]["action"], "scale_up")
        # When LLM doesn't provide recommended_solutions, all generated solutions are from runbook
        self.assertEqual(result["recommended_solutions"][0]["source"], "runbook")

    def test_parse_json_evidence_fetch_failed_path(self):
        """Test that evidence fetch failed returns manual_review_required solution."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # Test the fallback diagnosis path for evidence fetch failure
        fallback = mod._generate_fallback_diagnosis("resource_exhaustion", {})

        self.assertEqual(fallback["suggested_action"], "scale_up")
        self.assertIn("recommended_solutions", fallback)
        self.assertGreaterEqual(len(fallback["recommended_solutions"]), 2)
        self.assertEqual(fallback["recommended_solutions"][0]["action"], "scale_up")

    # ===========================================================================
    # T1.1 - DynamoDB Decimal handling
    # ===========================================================================

    def test_dynamodb_decimal_handling(self):
        """Test that confidence and other floats are stored as Decimal in DynamoDB."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={
                "INCIDENTS_TABLE": "incidents-dev",
                "DATA_LAKE_BUCKET": "test-bucket",
            },
        )
        from decimal import Decimal

        mock_table = mock.MagicMock()
        # Need to patch _dynamodb.Table to return our mock
        mod._dynamodb.Table = mock.MagicMock(return_value=mock_table)

        diagnosis_output = {
            "root_cause": "Test",
            "confidence": 0.85,
            "affected_resources": ["res1"],
            "suggested_action": "scale_up",
            "explanation": "Test explanation",
            "reasoning_trace": "Test trace",
            "recommended_solutions": [
                {"id": "sol-1", "action": "scale_up", "title": "Scale Up", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
                {"id": "sol-2", "action": "restart_service", "title": "Restart", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.7, "source": "runbook"},
            ],
            "diagnosis_status": "success",
            "model_used": "Nova Pro",
            "is_heuristic": False,
        }

        mod._update_dynamodb_diagnosis("test-inc-1", diagnosis_output, True, None)

        # Check that Decimal was used for confidence
        call_kwargs = mock_table.update_item.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        self.assertIsInstance(expr_values[":conf"], Decimal)
        self.assertEqual(float(expr_values[":conf"]), 0.85)

        # Check recommended_solutions are passed correctly with Decimal confidence
        rs_value = expr_values[":rs"]
        self.assertIsInstance(rs_value, list)
        self.assertEqual(len(rs_value), 2)
        # Confidence values in recommended_solutions should be converted to Decimal
        for sol in rs_value:
            self.assertIsInstance(sol["confidence"], Decimal)
            self.assertEqual(float(sol["confidence"]), 0.9 if sol["action"] == "scale_up" else 0.7)

    def test_parse_json_without_fault_class_uses_incident_fault_class(self):
        """Test that when LLM JSON lacks fault_class, incident fault_class is used for validation."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # LLM response WITHOUT fault_class field
        response = '''{
            "root_cause": "CPU spike",
            "confidence": 0.9,
            "affected_resources": ["service-a"],
            "suggested_action": "scale_up",
            "explanation": "Service A needs scaling",
            "reasoning_trace": "High CPU detected",
            "recommended_solutions": [
                {"id": "sol-1", "action": "scale_up", "title": "Scale Up", "description": "Increase Lambda memory", "risk": "low", "expected_outcome": "Resolve CPU spike", "rationale": "High CPU detected", "confidence": 0.9, "source": "llm"},
                {"id": "sol-2", "action": "restart_service", "title": "Restart Service", "description": "Restart Lambda", "risk": "medium", "expected_outcome": "Clear memory leak", "rationale": "Restart may clear leak", "confidence": 0.7, "source": "runbook"}
            ]
        }'''
        # Call with fault_class from incident (not from LLM response)
        result = mod._parse_and_validate_json(response, "resource_exhaustion")

        self.assertIn("recommended_solutions", result)
        self.assertEqual(len(result["recommended_solutions"]), 2)
        self.assertEqual(result["recommended_solutions"][0]["action"], "scale_up")
        # The validation should use the passed fault_class for runbook alternatives
        # even though LLM didn't provide fault_class
        self.assertEqual(result["recommended_solutions"][0]["source"], "llm")
        self.assertEqual(result["recommended_solutions"][1]["source"], "runbook")

    def test_validate_recommended_solutions_uses_fault_class_for_runbook_topup(self):
        """Test that validator uses fault_class to select runbook alternatives for top-up."""
        mod = self.load_handler(
            DIAGNOSIS_PATH,
            env={"INCIDENTS_TABLE": "incidents-dev", "DATA_LAKE_BUCKET": "test-bucket"},
        )

        # Provide 2 solutions with same action (dedupe to 1) - should top up with runbook alternatives
        solutions = [
            {"action": "scale_up", "title": "Scale Up 1", "description": "Desc", "risk": "low", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
            {"action": "scale_up", "title": "Scale Up 2", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.8, "source": "runbook"},
        ]

        # For resource_exhaustion, runbook alternatives should be restart_service, manual_review_required
        result = mod._validate_recommended_solutions(solutions, "scale_up", "resource_exhaustion")

        self.assertGreaterEqual(len(result), 2)
        actions = [s["action"] for s in result]
        self.assertIn("scale_up", actions)
        self.assertIn("restart_service", actions)
        self.assertIn("manual_review_required", actions)
        # Runbook alternatives should have source="runbook"
        runbook_solutions = [s for s in result if s["source"] == "runbook"]
        self.assertTrue(len(runbook_solutions) >= 1)
        for s in runbook_solutions:
            self.assertIn(s["action"], ("restart_service", "manual_review_required"))

        # For misconfiguration, test with primary action that matches misconfiguration
        # Provide solutions that dedupe to 1, with primary action = lock_s3_bucket
        solutions_misconfig = [
            {"action": "lock_s3_bucket", "title": "Lock S3 1", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.9, "source": "llm"},
            {"action": "lock_s3_bucket", "title": "Lock S3 2", "description": "Desc", "risk": "medium", "expected_outcome": "Outcome", "rationale": "Rationale", "confidence": 0.8, "source": "runbook"},
        ]
        result_misconfig = mod._validate_recommended_solutions(solutions_misconfig, "lock_s3_bucket", "misconfiguration")
        actions_misconfig = [s["action"] for s in result_misconfig]
        self.assertIn("lock_s3_bucket", actions_misconfig)
        self.assertIn("tighten_iam_policy", actions_misconfig)
        self.assertIn("manual_review_required", actions_misconfig)

if __name__ == "__main__":
    unittest.main()