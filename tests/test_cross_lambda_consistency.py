"""
test_cross_lambda_consistency.py — Cross-lambda consistency tests for T1.1b.
Verifies that diagnosis_lambda and dashboard_api_lambda produce consistent
runbook alternatives for the same fault_class.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Set default env vars for tests if not present
os.environ.setdefault("INCIDENTS_TABLE", "incidents-dev")
os.environ.setdefault("DATA_LAKE_BUCKET", "llm-incident-datalake-test-account-dev")
os.environ.setdefault("ALLOWED_ORIGIN", "")

# Add backend paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "diagnosis"))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "dashboard_api"))

from backend.dashboard_api import dashboard_api_lambda
import diagnosis_lambda


@pytest.fixture
def mock_dynamodb():
    with patch.object(dashboard_api_lambda, "_dynamodb") as mock_db:
        mock_table = MagicMock()
        mock_db.Table.return_value = mock_table
        yield mock_table


@pytest.fixture
def mock_s3():
    with patch.object(dashboard_api_lambda, "_s3") as mock:
        yield mock


def test_fallback_alternatives_consistent_resource_exhaustion():
    """Test that both lambdas generate same runbook alternatives for resource_exhaustion."""
    # Diagnosis lambda fallback alternatives (used for top-up) - includes all runbook actions
    diag_fallback = diagnosis_lambda._generate_fallback_solutions("scale_up", "resource_exhaustion")
    diag_actions = {s["action"] for s in diag_fallback}

    # Dashboard API lambda runbook alternatives - excludes primary action since it's added separately
    item = {
        "incident_id": "test",
        "fault_class": "resource_exhaustion",
        "diagnosis": {"suggested_action": "scale_up", "confidence": 0.9},
    }
    dash_result = dashboard_api_lambda._derive_recommended_solutions(item)
    dash_solutions = dash_result["diagnosis"]["recommended_solutions"]
    dash_runbook_actions = {s["action"] for s in dash_solutions if s["source"] == "runbook"}

    # Diagnosis fallback includes all runbook actions for the fault_class
    expected_diag_actions = {"scale_up", "restart_service", "manual_review_required"}
    # Dashboard runbook alternatives exclude the primary action
    expected_dash_actions = {"restart_service", "manual_review_required"}
    
    assert diag_actions == expected_diag_actions
    assert dash_runbook_actions == expected_dash_actions


def test_fallback_alternatives_consistent_misconfiguration():
    """Test that both lambdas generate same runbook alternatives for misconfiguration."""
    diag_fallback = diagnosis_lambda._generate_fallback_solutions("lock_s3_bucket", "misconfiguration")
    diag_actions = {s["action"] for s in diag_fallback}

    item = {
        "incident_id": "test",
        "fault_class": "misconfiguration",
        "diagnosis": {"suggested_action": "lock_s3_bucket", "confidence": 0.9},
    }
    dash_result = dashboard_api_lambda._derive_recommended_solutions(item)
    dash_solutions = dash_result["diagnosis"]["recommended_solutions"]
    dash_runbook_actions = {s["action"] for s in dash_solutions if s["source"] == "runbook"}

    expected_diag_actions = {"lock_s3_bucket", "tighten_iam_policy", "manual_review_required"}
    expected_dash_actions = {"tighten_iam_policy", "manual_review_required"}
    assert diag_actions == expected_diag_actions
    assert dash_runbook_actions == expected_dash_actions


def test_fallback_alternatives_consistent_service_cascade():
    """Test that both lambdas generate same runbook alternatives for service_cascade."""
    diag_fallback = diagnosis_lambda._generate_fallback_solutions("restart_downstream_service", "service_cascade")
    diag_actions = {s["action"] for s in diag_fallback}

    item = {
        "incident_id": "test",
        "fault_class": "service_cascade",
        "diagnosis": {"suggested_action": "restart_downstream_service", "confidence": 0.9},
    }
    dash_result = dashboard_api_lambda._derive_recommended_solutions(item)
    dash_solutions = dash_result["diagnosis"]["recommended_solutions"]
    dash_runbook_actions = {s["action"] for s in dash_solutions if s["source"] == "runbook"}

    expected_diag_actions = {"restart_downstream_service", "restart_service", "manual_review_required"}
    expected_dash_actions = {"restart_service", "manual_review_required"}
    assert diag_actions == expected_diag_actions
    assert dash_runbook_actions == expected_dash_actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])