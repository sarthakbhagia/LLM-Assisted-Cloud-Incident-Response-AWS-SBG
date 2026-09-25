import json
import os
import shutil
import tempfile
import unittest

from evaluation.metrics import (
    calculate_mttr,
    classify_failure_mode,
    compute_aggregate_metrics,
    detect_hallucination,
    evaluate_rca_accuracy,
)
from evaluation.run_evaluation import export_results, generate_mock_incidents, run_evaluation
from fault_injection.inject_misconfiguration import inject_misconfiguration
from fault_injection.inject_resource_exhaustion import inject_resource_exhaustion
from fault_injection.inject_service_cascade import inject_service_cascade


class TestFaultInjection(unittest.TestCase):
    def test_inject_resource_exhaustion_dry_run(self):
        res = inject_resource_exhaustion(environment="test", dry_run=True)
        self.assertEqual(res["fault_class"], "resource_exhaustion")
        self.assertEqual(res["target_resource"], "incident-service-a-test")
        self.assertEqual(res["status"], "simulated_injection")
        self.assertTrue(res["dry_run"])

    def test_inject_misconfiguration_dry_run(self):
        res = inject_misconfiguration(environment="test", dry_run=True)
        self.assertEqual(res["fault_class"], "misconfiguration")
        self.assertEqual(res["target_resource"], "llm-incident-datalake-889081505756-test")
        self.assertEqual(res["status"], "simulated_injection")
        self.assertTrue(res["dry_run"])

    def test_inject_service_cascade_dry_run(self):
        res = inject_service_cascade(environment="test", dry_run=True)
        self.assertEqual(res["fault_class"], "service_cascade")
        self.assertEqual(res["target_resource"], "incident-service-c-test")
        self.assertEqual(res["status"], "simulated_injection")
        self.assertTrue(res["dry_run"])


class TestEvaluationMetrics(unittest.TestCase):
    def test_calculate_mttr(self):
        t1 = "2026-09-12T10:00:00Z"
        t2 = "2026-09-12T10:01:30Z"
        seconds = calculate_mttr(t1, t2)
        self.assertEqual(seconds, 90.0)

        self.assertIsNone(calculate_mttr(None, t2))
        self.assertIsNone(calculate_mttr(t1, "invalid-date"))

    def test_evaluate_rca_accuracy(self):
        rec_ex = {
            "fault_class": "resource_exhaustion",
            "diagnosis": {"root_cause": "High CPU utilization spike on Service A", "suggested_action": "scale_up"},
        }
        self.assertTrue(evaluate_rca_accuracy(rec_ex))

        rec_bad = {
            "fault_class": "misconfiguration",
            "diagnosis": {"root_cause": "Something unrelated failed", "suggested_action": "unknown_action"},
        }
        self.assertFalse(evaluate_rca_accuracy(rec_bad))

    def test_detect_hallucination(self):
        rec_clean = {
            "diagnosis": {
                "reasoning_trace": "Checked CloudWatch logs and metrics.",
                "affected_resources": ["incident-service-a"],
            }
        }
        raw_data = {"service": "incident-service-a", "logs": ["CPU elevated"]}
        self.assertFalse(detect_hallucination(rec_clean, raw_data))

        rec_hallucinated = {
            "diagnosis": {
                "reasoning_trace": "Detected hallucinated_policy not in raw logs.",
                "affected_resources": ["nonexistent-bucket-999"],
            }
        }
        self.assertTrue(detect_hallucination(rec_hallucinated, raw_data))

    def test_classify_failure_mode(self):
        mode_none = classify_failure_mode({}, is_rca_correct=True, is_hallucinated=False)
        self.assertEqual(mode_none, "none")

        rec_arn = {"diagnosis": {"reasoning_trace": "Confused metric ARN with resource ID"}}
        mode_arn = classify_failure_mode(rec_arn, is_rca_correct=False, is_hallucinated=False)
        self.assertEqual(mode_arn, "metric_arn_confusion")

    def test_compute_aggregate_metrics(self):
        records = generate_mock_incidents(num_runs=2, ablation=False)
        metrics = compute_aggregate_metrics(records)

        self.assertEqual(metrics["total_incidents"], 6)
        self.assertGreater(metrics["mttr_seconds_avg"], 0)
        self.assertGreaterEqual(metrics["rca_accuracy_pct"], 0)
        self.assertIn("failure_taxonomy", metrics)
        self.assertIn("rag_ablation_comparison", metrics)


class TestEvaluationRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_run_evaluation_mock(self):
        summary = run_evaluation(num_runs=2, mock=True, output_dir=self.temp_dir)
        self.assertEqual(summary["total_incidents"], 6)

        # Check generated output files
        summary_file = os.path.join(self.temp_dir, "summary.json")
        taxonomy_file = os.path.join(self.temp_dir, "failure_taxonomy.csv")
        gap_file = os.path.join(self.temp_dir, "diagnosis_recovery_gap.csv")
        runs_file = os.path.join(self.temp_dir, "raw_evaluation_runs.csv")

        self.assertTrue(os.path.exists(summary_file))
        self.assertTrue(os.path.exists(taxonomy_file))
        self.assertTrue(os.path.exists(gap_file))
        self.assertTrue(os.path.exists(runs_file))

        with open(summary_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["total_incidents"], 6)
            self.assertIn("diagnosis_recovery_gap_pct", data)


if __name__ == "__main__":
    unittest.main()
