"""
test_demo_app.py — Unit tests for Phase 1 demo application services (A, B, C).
"""

import json
import os
import sys
import unittest
from unittest import mock

import helpers  # noqa: F401
from helpers import REPO_ROOT, Fixture

SERVICE_A_PATH = os.path.join(REPO_ROOT, "backend", "service_a", "app.py")
SERVICE_B_PATH = os.path.join(REPO_ROOT, "backend", "service_b", "app.py")
SERVICE_C_PATH = os.path.join(REPO_ROOT, "backend", "service_c", "app.py")


class TestServiceC(Fixture):
    def test_service_c_success(self):
        mod = self.load_handler(SERVICE_C_PATH)
        resp = mod.lambda_handler({}, None)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["service"], "C")
        self.assertEqual(body["status"], "success")


class TestServiceB(Fixture):
    @mock.patch("urllib.request.urlopen")
    def test_service_b_success(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "service": "C", "status": "success", "message": "Service C completed successfully"
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        mod = self.load_handler(SERVICE_B_PATH, env={"SERVICE_C_URL": "http://localhost/service-c"})
        resp = mod.lambda_handler({}, None)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["service"], "B")
        self.assertEqual(body["status"], "success")

    def test_service_b_missing_url(self):
        mod = self.load_handler(SERVICE_B_PATH, env={"SERVICE_C_URL": ""})
        resp = mod.lambda_handler({}, None)
        self.assertEqual(resp["statusCode"], 500)


class TestServiceA(Fixture):
    @mock.patch("urllib.request.urlopen")
    def test_service_a_success(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "service": "B", "status": "success"
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        mod = self.load_handler(SERVICE_A_PATH, env={"SERVICE_B_URL": "http://localhost/service-b"})
        resp = mod.lambda_handler({}, None)
        self.assertEqual(resp["statusCode"], 200)

    def test_service_a_missing_url(self):
        mod = self.load_handler(SERVICE_A_PATH, env={"SERVICE_B_URL": ""})
        resp = mod.lambda_handler({}, None)
        self.assertEqual(resp["statusCode"], 500)


if __name__ == "__main__":
    unittest.main()
