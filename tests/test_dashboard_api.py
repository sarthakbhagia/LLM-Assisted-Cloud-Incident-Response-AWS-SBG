"""
test_dashboard_api.py — unit tests for the Phase 8 Dashboard API Lambda.

Focus: the /api/incidents listing contract. The original implementation
passed `limit` straight into DynamoDB Scan, which evaluates an arbitrary
subset of the table (effectively oldest-first) — so newly created incidents
were invisible on page 1 of the dashboard. These tests pin the corrected
behaviour: scan the whole table, sort newest-first, then slice the page.
"""

import base64
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Fixture, REPO_ROOT  # noqa: E402

HANDLER_PATH = os.path.join(REPO_ROOT, "backend", "dashboard_api", "dashboard_api_lambda.py")


class _FakeAttr:
    """Stand-in for boto3.dynamodb.conditions.Attr — just enough chaining."""

    def __init__(self, name):
        self.name = name

    def eq(self, _value):
        return self

    def exists(self):
        return self

    def __and__(self, _other):
        return self


class _FakeTable:
    """Returns pre-programmed scan pages in sequence, recording each call."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []
        self._idx = 0

    def reset(self):
        self.calls = []
        self._idx = 0

    def scan(self, **kwargs):
        self.calls.append(kwargs)
        if self._idx >= len(self.pages):
            return {"Items": []}
        resp = {"Items": self.pages[self._idx]}
        self._idx += 1
        if self._idx < len(self.pages):
            resp["LastEvaluatedKey"] = {"incident_id": f"page-{self._idx - 1}"}
        return resp


def _incident(incident_id, detected_at, fault_class="resource_exhaustion"):
    return {
        "incident_id": incident_id,
        "detected_at": detected_at,
        "fault_class": fault_class,
        "remediation": {"status": "pending_approval"},
    }


def _sorted_desc(items):
    return sorted(items, key=lambda r: r["detected_at"], reverse=True)


class DashboardApiListingTest(Fixture):
    def setUp(self):
        super().setUp()
        # dashboard_api_lambda does `from boto3.dynamodb.conditions import Attr`.
        # The import machinery needs real module entries in sys.modules for the
        # submodule chain (an attribute on the boto3 stub is not enough), so
        # register fake parent+leaf modules and clean them up afterwards.
        conditions_mod = types.ModuleType("boto3.dynamodb.conditions")
        conditions_mod.Attr = _FakeAttr
        dynamodb_mod = types.ModuleType("boto3.dynamodb")
        dynamodb_mod.conditions = conditions_mod
        for name in ("boto3.dynamodb", "boto3.dynamodb.conditions"):
            sys.modules[name] = (
                dynamodb_mod if name == "boto3.dynamodb" else conditions_mod
            )
            self.addCleanup(sys.modules.pop, name, None)

        env = {
            "INCIDENTS_TABLE": "incidents-test",
            "DATA_LAKE_BUCKET": "datalake-test",
            "AWS_REGION": "ap-south-1",
            "AWS_DEFAULT_REGION": "ap-south-1",
        }
        self.mod = self.load_handler(HANDLER_PATH, env)
        self.table = _FakeTable(pages=[])
        self.set_table(self.aws["dynamodb.resource"], self.table)

    def _get(self, params=None):
        event = {
            "httpMethod": "GET",
            "resource": "/api/incidents",
            "pathParameters": {},
            "queryStringParameters": params or {},
        }
        result = self.mod.lambda_handler(event, {})
        body = json.loads(result["body"])
        return result["statusCode"], body

    # -- the regression: newest incident must not fall off page 1 -----------

    def test_newest_incident_visible_on_first_page_despite_scan_order(self):
        # 20 incidents arrive in scan order oldest-first (DynamoDB's arbitrary
        # order puts the newest LAST). The old code scanned only `limit` items
        # from that order, so the newest never appeared.
        items = [_incident(f"inc-{i:02d}", f"2026-09-20T17:{40 - i:02d}:00+00:00")
                 for i in range(20)]
        self.table.pages = [items[:10], items[10:]]

        status, body = self._get({"limit": "5"})
        self.assertEqual(status, 200)
        page_ids = [i["incident_id"] for i in body["data"]["items"]]
        expected = [i["incident_id"] for i in _sorted_desc(items)[:5]]
        self.assertEqual(page_ids, expected)
        self.assertEqual(body["data"]["count"], 5)

    def test_limit_is_not_passed_to_scan(self):
        # Pins the fix mechanism: the handler must NOT forward `limit` to
        # DynamoDB Scan (that is what caused arbitrary-subset pagination).
        self.table.pages = [[_incident("a", "2026-09-20T10:00:00+00:00")]]
        self._get({"limit": "5"})
        self.assertEqual(len(self.table.calls), 1)
        self.assertNotIn("Limit", self.table.calls[0])

    # -- general listing contract -------------------------------------------

    def test_all_items_sorted_newest_first(self):
        items = [_incident(f"inc-{i}", f"2026-09-1{i}T12:00:00+00:00")
                 for i in range(10)]
        self.table.pages = [items[3:], items[:3]]  # arbitrary scan order

        status, body = self._get({"limit": "100"})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["count"], 10)
        self.assertEqual(
            [i["incident_id"] for i in body["data"]["items"]],
            [i["incident_id"] for i in _sorted_desc(items)],
        )
        self.assertIsNone(body["data"]["next_token"])

    def test_pagination_walks_the_full_sorted_list(self):
        items = [_incident(f"inc-{i:02d}", f"2026-09-20T{10 + i // 60:02d}:{i % 60:02d}:00+00:00")
                 for i in range(25)]
        self.table.pages = [items[:8], items[8:16], items[16:]]

        seen, token, pages = [], None, 0
        while True:
            self.table.reset()  # each API request starts its own scan sequence
            params = {"limit": "10"}
            if token:
                params["next_token"] = token
            status, body = self._get(params)
            self.assertEqual(status, 200)
            seen.extend(i["incident_id"] for i in body["data"]["items"])
            pages += 1
            token = body["data"]["next_token"]
            if not token:
                break

        self.assertEqual(pages, 3)
        self.assertEqual(seen, [i["incident_id"] for i in _sorted_desc(items)])

    def test_invalid_next_token_is_400(self):
        self.table.pages = [[_incident("a", "2026-09-20T10:00:00+00:00")]]
        status, body = self._get({"next_token": "not-valid-base64!!"})
        self.assertEqual(status, 400)
        self.assertIn("next_token", body["error"])

    def test_unknown_route_404(self):
        result = self.mod.lambda_handler(
            {"httpMethod": "GET", "resource": "/api/nope", "pathParameters": {}}, {})
        self.assertEqual(result["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()
