"""
conftest.py — pytest bootstrap for repo-root packages.

test_evaluation.py imports `evaluation` and `fault_injection`, which live at
the repository root rather than inside tests/. The bare `pytest` entry point
(used in CI) only prepends each test file's own directory to sys.path, so the
root must be added explicitly. Runs of `python -m pytest` already had the
root on sys.path, which is why the failure only showed up in CI.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
