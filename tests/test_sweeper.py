"""
test_sweeper.py — unit tests for the approved-state sweeper Lambda.

Covers the stuck-incident decision matrix (sweep / skip-recent / expire),
idempotent re-invocation bookkeeping, dry-run mode, and the per-run sweep
cap. Uses the shared stdlib-only boto3 stub (see helpers.py).
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Fixture, REPO_ROOT  # noqa: E402

HANDLER_PATH = os.path.join(REPO_ROOT, "backend", "sweeper", "sweeper_lambda.py")

NOW = datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _approved_incident(incident_id, decided_min_ago=None, detected_min_ago=None,
                       decided_at=None):
    remediation = {"status": "approved"}
    if decided_at is not None:
        remediation["decided_at"] = decided_at
    elif decided_min_ago is not None:
        remediation["decided_at"] = _iso(NOW - timedelta(minutes=decided_min_ago))
    item = {
        "incident_id": incident_id,
        "fault_class": "resource_exhaustion",
        "remediation": remediation,
        "diagnosis": {"suggested_action": "scale_up"},
    }
    if detected_min_ago is not None:
        item["detected_at"] = _iso(NOW - timedelta(minutes=detected_min_ago))
    return item


class _FakeTable:
    """Scan returns pre-programmed pages in sequence; update_item records."""

    def __init__(self, pages):
        self.pages = pages
        self.scans = []
        self.updates = []
        self._page = 0

    def reset(self):
        self.scans = []
        self.updates = []
        self._page = 0

    def scan(self, **kwargs):
        self.scans.append(kwargs)
        if self._page >= len(self.pages):
            return {"Items": []}
        resp = {"Items": self.pages[self._page]}
        self._page += 1
        if self._page < len(self.pages):
            resp["LastEvaluatedKey"] = {"incident_id": f"page-{self._page - 1}"}
        return resp

    def update_item(self, **kwargs):
        self.updates.append(kwargs)


class SweeperTest(Fixture):
    def setUp(self):
        super().setUp()
        env = {
            "INCIDENTS_TABLE": "incidents-test",
            "REMEDIATION_FUNCTION_NAME": "remediation-test",
            "AWS_REGION": "ap-south-1",
            "AWS_DEFAULT_REGION": "ap-south-1",
        }
        self.mod = self.load_handler(HANDLER_PATH, env)
        self.table = _FakeTable(pages=[])
        self.set_table(self.aws["dynamodb.resource"], self.table)
        self.invocations = []
        lambda_client = self.aws["lambda"]
        lambda_client.invoke = self._record_invoke

    def _record_invoke(self, **kwargs):
        self.invocations.append(kwargs)
        return {"StatusCode": 202}

    def _run(self, event=None):
        return self.mod.lambda_handler(event or {}, {})

    # -- core behaviour ------------------------------------------------------

    def test_sweeps_stuck_approved_incident(self):
        self.table.pages = [[_approved_incident("inc-stuck", decided_min_ago=30)]]
        result = self._run()

        self.assertEqual(result["swept"], 1)
        self.assertEqual(len(self.invocations), 1)
        invoke = self.invocations[0]
        self.assertEqual(invoke["FunctionName"], "remediation-test")
        self.assertEqual(invoke["InvocationType"], "Event")
        self.assertEqual(
            json.loads(invoke["Payload"]), {"incident_id": "inc-stuck"})
        # bookkeeping recorded, status untouched
        self.assertEqual(len(self.table.updates), 1)
        self.assertIn("swept_at", self.table.updates[0]["UpdateExpression"])
        self.assertIn("if_not_exists", self.table.updates[0]["UpdateExpression"])

    def test_skips_recently_approved_incidents(self):
        self.table.pages = [[_approved_incident("inc-fresh", decided_min_ago=2)]]
        result = self._run()

        self.assertEqual(result["skipped_recent"], 1)
        self.assertEqual(result["swept"], 0)
        self.assertEqual(self.invocations, [])
        self.assertEqual(self.table.updates, [])

    def test_expires_records_stuck_beyond_max_age(self):
        self.table.pages = [[_approved_incident("inc-ancient", decided_min_ago=60 * 72)]]
        result = self._run()

        self.assertEqual(result["expired"], 1)
        self.assertEqual(result["swept"], 0)
        self.assertEqual(self.invocations, [])

    def test_missing_timestamp_never_retried(self):
        record = _approved_incident("inc-notime")
        record["remediation"].pop("decided_at", None)
        self.table.pages = [[record]]
        result = self._run()

        self.assertEqual(result["expired"], 1)
        self.assertEqual(self.invocations, [])

    def test_falls_back_to_detected_at_when_no_decided_at(self):
        self.table.pages = [[_approved_incident("inc-nofallback-case",
                                                detected_min_ago=30)]]
        result = self._run()

        self.assertEqual(result["swept"], 1)
        self.assertEqual(len(self.invocations), 1)

    # -- guardrails -----------------------------------------------------------

    def test_dry_run_counts_but_does_not_invoke_or_write(self):
        self.table.pages = [[_approved_incident("inc-dry", decided_min_ago=30)]]
        result = self._run({"dry_run": True})

        self.assertEqual(result["swept"], 1)
        self.assertEqual(result["dry_run"], True)
        self.assertEqual(self.invocations, [])
        self.assertEqual(self.table.updates, [])

    def test_max_sweep_per_run_bounds_blast_radius(self):
        self.setenv("MAX_SWEEP_PER_RUN", "2")
        self.mod = self.load_handler(HANDLER_PATH, {
            "INCIDENTS_TABLE": "incidents-test",
            "REMEDIATION_FUNCTION_NAME": "remediation-test",
            "MAX_SWEEP_PER_RUN": "2",
        })
        self.table.pages = [[
            _approved_incident(f"inc-{i}", decided_min_ago=30) for i in range(5)
        ]]
        result = self._run()

        self.assertEqual(len(self.invocations), 2)
        self.assertEqual(result["swept"], 2)
        self.assertEqual(result["failed"], 0)

    def test_unconfigured_remediation_counts_as_failed(self):
        self.mod = self.load_handler(HANDLER_PATH, {
            "INCIDENTS_TABLE": "incidents-test",
            "REMEDIATION_FUNCTION_NAME": "",
        })
        self.table.pages = [[_approved_incident("inc-noconf", decided_min_ago=30)]]
        result = self._run()

        self.assertEqual(result["failed"], 1)
        self.assertEqual(self.invocations, [])

    # -- scan mechanics --------------------------------------------------------

    def test_scan_paginates_the_whole_table_and_filters_approved(self):
        self.table.pages = [
            [_approved_incident("inc-p1", decided_min_ago=30)],
            [_approved_incident("inc-p2", decided_min_ago=30)],
        ]
        result = self._run()

        self.assertEqual(len(self.table.scans), 2)
        self.assertEqual(result["scanned"], 2)
        self.assertEqual(result["swept"], 2)
        first_scan = self.table.scans[0]
        self.assertEqual(
            first_scan["FilterExpression"], "remediation.#st = :approved")
        self.assertEqual(
            first_scan["ExpressionAttributeValues"], {":approved": "approved"})

    def test_invoke_failure_is_counted_not_raised(self):
        lambda_client = self.aws["lambda"]
        lambda_client.invoke = mock.Mock(
            side_effect=self.mod.ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "rate"}},
                "Invoke",
            ))
        self.table.pages = [[_approved_incident("inc-throttled",
                                                decided_min_ago=30)]]
        result = self._run()

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["swept"], 0)
        self.assertEqual(self.table.updates, [])  # no bookkeeping on failure


if __name__ == "__main__":
    unittest.main()
