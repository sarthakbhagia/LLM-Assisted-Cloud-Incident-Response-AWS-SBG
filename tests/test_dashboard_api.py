"""
test_dashboard_api.py — Unit tests for Phase 8 Dashboard API Lambda.
Covers T1.2 _derive_recommended_solutions for old incidents.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Set default env vars for tests if not present
os.environ.setdefault("INCIDENTS_TABLE", "incidents-dev")
os.environ.setdefault("DATA_LAKE_BUCKET", "llm-incident-datalake-test-account-dev")
os.environ.setdefault("ALLOWED_ORIGIN", "")

from backend.dashboard_api import dashboard_api_lambda


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


def test_derive_recommended_solutions_resource_exhaustion():
    """Test derive function for resource_exhaustion fault class."""
    item = {
        "incident_id": "old-inc-1",
        "fault_class": "resource_exhaustion",
        "diagnosis": {
            "suggested_action": "scale_up",
            "confidence": 0.85,
        },
    }

    result = dashboard_api_lambda._derive_recommended_solutions(item)

    assert "recommended_solutions" in result["diagnosis"]
    solutions = result["diagnosis"]["recommended_solutions"]
    assert len(solutions) >= 2
    assert len(solutions) <= 3

    # First solution should be the primary action
    assert solutions[0]["action"] == "scale_up"
    assert solutions[0]["source"] == "llm"
    assert solutions[0]["confidence"] == 0.9

    # Should include runbook alternatives
    actions = [s["action"] for s in solutions]
    assert "restart_service" in actions
    assert "manual_review_required" in actions

    # All solutions should have required fields
    for sol in solutions:
        assert "id" in sol
        assert "title" in sol
        assert "description" in sol
        assert "risk" in sol
        assert "expected_outcome" in sol
        assert "rationale" in sol
        assert "confidence" in sol
        assert "source" in sol
        assert sol["risk"] in ("low", "medium", "high")
        assert sol["source"] in ("llm", "runbook")
        assert 0.0 <= sol["confidence"] <= 1.0


def test_derive_recommended_solutions_misconfiguration():
    """Test derive function for misconfiguration fault class."""
    item = {
        "incident_id": "old-inc-2",
        "fault_class": "misconfiguration",
        "diagnosis": {
            "suggested_action": "lock_s3_bucket",
            "confidence": 0.9,
        },
    }

    result = dashboard_api_lambda._derive_recommended_solutions(item)

    solutions = result["diagnosis"]["recommended_solutions"]
    assert len(solutions) >= 2

    assert solutions[0]["action"] == "lock_s3_bucket"
    assert solutions[0]["source"] == "llm"

    actions = [s["action"] for s in solutions]
    assert "tighten_iam_policy" in actions
    assert "manual_review_required" in actions


def test_derive_recommended_solutions_service_cascade():
    """Test derive function for service_cascade fault class."""
    item = {
        "incident_id": "old-inc-3",
        "fault_class": "service_cascade",
        "diagnosis": {
            "suggested_action": "restart_downstream_service",
            "confidence": 0.88,
        },
    }

    result = dashboard_api_lambda._derive_recommended_solutions(item)

    solutions = result["diagnosis"]["recommended_solutions"]
    assert len(solutions) >= 2

    assert solutions[0]["action"] == "restart_downstream_service"
    assert solutions[0]["source"] == "llm"

    actions = [s["action"] for s in solutions]
    assert "restart_service" in actions
    assert "manual_review_required" in actions


def test_derive_recommended_solutions_unknown_fault_class():
    """Test derive function for unknown fault class falls back gracefully."""
    item = {
        "incident_id": "old-inc-4",
        "fault_class": "unknown_class",
        "diagnosis": {
            "suggested_action": "manual_review_required",
            "confidence": 0.5,
        },
    }

    result = dashboard_api_lambda._derive_recommended_solutions(item)

    solutions = result["diagnosis"]["recommended_solutions"]
    assert len(solutions) >= 1
    assert solutions[0]["action"] == "manual_review_required"


def test_derive_recommended_solutions_preserves_other_fields():
    """Test derive function preserves all other fields in the item."""
    item = {
        "incident_id": "old-inc-5",
        "fault_class": "resource_exhaustion",
        "detected_at": "2024-01-01T00:00:00Z",
        "resource_id": "alarm-name",
        "raw_data_s3_key": "incidents/old-inc-5/raw_data.json",
        "diagnosis": {
            "suggested_action": "scale_up",
            "confidence": 0.85,
            "root_cause": "High CPU",
            "explanation": "CPU spike detected",
            "reasoning_trace": "Trace...",
        },
        "remediation": {"status": "pending_approval"},
    }

    result = dashboard_api_lambda._derive_recommended_solutions(item)

    # All original fields should be preserved
    assert result["incident_id"] == "old-inc-5"
    assert result["fault_class"] == "resource_exhaustion"
    assert result["detected_at"] == "2024-01-01T00:00:00Z"
    assert result["resource_id"] == "alarm-name"
    assert result["raw_data_s3_key"] == "incidents/old-inc-5/raw_data.json"
    assert result["diagnosis"]["root_cause"] == "High CPU"
    assert result["diagnosis"]["confidence"] == 0.85
    assert result["remediation"]["status"] == "pending_approval"

    # New field added
    assert "recommended_solutions" in result["diagnosis"]


def test_derive_recommended_solutions_caps_at_three():
    """Test derive function caps solutions at 3."""
    item = {
        "incident_id": "old-inc-6",
        "fault_class": "resource_exhaustion",
        "diagnosis": {
            "suggested_action": "scale_up",
            "confidence": 0.85,
        },
    }

    result = dashboard_api_lambda._derive_recommended_solutions(item)

    solutions = result["diagnosis"]["recommended_solutions"]
    assert len(solutions) <= 3


def test_derive_recommended_solutions_duplicate_actions_deduped():
    """Test derive function deduplicates by action."""
    # Create item where primary action also appears in runbook alternatives
    item = {
        "incident_id": "old-inc-7",
        "fault_class": "resource_exhaustion",
        "diagnosis": {
            "suggested_action": "scale_up",
            "confidence": 0.85,
        },
    }

    result = dashboard_api_lambda._derive_recommended_solutions(item)

    solutions = result["diagnosis"]["recommended_solutions"]
    actions = [s["action"] for s in solutions]
    # scale_up should appear only once
    assert actions.count("scale_up") == 1


def test_derive_recommended_solutions_unknown_action_fallback():
    """Test derive function handles unknown suggested_action gracefully."""
    item = {
        "incident_id": "old-inc-8",
        "fault_class": "resource_exhaustion",
        "diagnosis": {
            "suggested_action": "unknown_action",
            "confidence": 0.5,
        },
    }

    result = dashboard_api_lambda._derive_recommended_solutions(item)

    solutions = result["diagnosis"]["recommended_solutions"]
    # Should still generate runbook alternatives for the fault_class
    assert len(solutions) >= 1
    actions = [s["action"] for s in solutions]
    # Runbook alternatives for resource_exhaustion
    assert "scale_up" in actions
    assert "restart_service" in actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])