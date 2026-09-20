"""
helpers.py — shared test scaffolding for the Phase 5 Lambda unit tests.

Loads each handler module by path (mirroring how a Lambda container imports
`app.py`) with a stdlib-only stub of boto3/botocore injected into sys.modules.
No AWS calls, no third-party dependencies — runs on plain Python 3.9+.
"""

import importlib.util
import os
import sys
import types
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Minimal botocore stub (boto3 depends on this symbol)
# ---------------------------------------------------------------------------
_botocore = types.ModuleType("botocore")


class _ClientError(Exception):
    def __init__(self, error_response, operation_name):
        super().__init__(str(error_response))
        self.response = error_response
        self.operation_name = operation_name


_botocore.ClientError = _ClientError
_botocore.exceptions = types.ModuleType("botocore.exceptions")
_botocore.exceptions.ClientError = _ClientError
_botocore.exceptions.BotoCoreError = Exception
_botocore.exceptions.DataNotFoundError = Exception
sys.modules.setdefault("botocore", _botocore)
sys.modules.setdefault("botocore.exceptions", _botocore.exceptions)

# ---------------------------------------------------------------------------
# Minimal boto3 stub — replaced per-test by Fixture with recording fakes
# ---------------------------------------------------------------------------


class _FakeAWSClient:
    """Attribute-missing recorder used until a test installs behaviour."""

    def __init__(self):
        object.__setattr__(self, "_calls", [])

    def __getattr__(self, name):
        def _record(*args, **kwargs):
            calls = object.__getattribute__(self, "_calls")
            calls.append((name, args, kwargs))
            raise AssertionError(
                f"unexpected AWS call {name!r} in this test — install a stub first"
            )

        return _record


class Fixture(unittest.TestCase):
    """Base case: fresh AWS-client fakes and clean state per test."""

    def setUp(self):
        self.aws = {}  # service-name -> _FakeAWSClient

        def fake_client(service, *args, **kwargs):
            self.aws.setdefault(service, _FakeAWSClient())
            return self.aws[service]

        def fake_resource(service, *args, **kwargs):
            self.aws.setdefault(service + ".resource", _FakeAWSClient())
            return self.aws[service + ".resource"]

        # Swap in the boto3 stub WITHOUT mock.patch.dict(sys.modules, ...):
        # patch.dict restores the entire dict on exit, which DELETES any module
        # first imported during a test (e.g. urllib.request, imported when a
        # handler first makes an HTTP call). Those purges poison later tests —
        # mock.patch("urllib.request.urlopen") would patch an orphaned module
        # while freshly-loaded handlers bind a different instance. Save/restore
        # only the stub keys instead; everything else stays cached as usual.
        self._saved_modules = {
            name: sys.modules.get(name)
            for name in ("boto3", "botocore", "botocore.exceptions")
        }
        sys.modules["boto3"] = types.SimpleNamespace(client=fake_client, resource=fake_resource)
        self.addCleanup(self._restore_stub_modules)

        # Fresh module import per test so module-level env reads re-execute.
        for name in list(sys.modules):
            if name in ("app", "fakeapp"):
                del sys.modules[name]

    # -- helpers -----------------------------------------------------------

    def _restore_stub_modules(self):
        for name, previous in self._saved_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def load_handler(self, path, env=None):
        """Import a handler module by path with the given env vars set."""
        env = env or {}
        for key, value in env.items():
            self.setenv(key, value)
        spec = importlib.util.spec_from_file_location("app", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        self.addCleanup(self._unload, "app")
        return module

    def setenv(self, key, value):
        self._env_stack = getattr(self, "_env_stack", [])
        self._env_stack.append((key, os.environ.get(key)))
        os.environ[key] = value

    def _unload(self, name):
        sys.modules.pop(name, None)
        for key, old in reversed(getattr(self, "_env_stack", [])):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def set_ssm(self, service_client, parameters):
        service_client.__setattr__(
            "get_parameter",
            lambda Name, WithDecryption=False: (
                {"Parameter": {"Value": parameters[Name]}}
                if Name in parameters
                else (_raise_client_error())
            ),
        )

    def set_table(self, dynamodb_resource, table):
        dynamodb_resource.__setattr__("Table", lambda TableName: table)

    def set_bucket(self, s3_client, objects):
        s3_client.__setattr__(
            "get_object",
            lambda Bucket, Key: (
                {"Body": _FakeBody(objects[Key])} if Key in objects else _raise_client_error()
            ),
        )


class _FakeBody:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text.encode("utf-8")


def _raise_client_error():
    raise _ClientError({"Error": {"Code": "ParameterNotFound", "Message": "not found"}}, "GetParameter")
