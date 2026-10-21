"""Browser checks of the fix round (contrast / text size audit, full-page tabs). They need Edge, node and the dashboard served with the API,
so they run only with OS_BROWSER_CHECK=1 (and OS_BROWSER_BASE, default http://127.0.0.1:8001)."""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("OS_BROWSER_BASE", "http://127.0.0.1:8001")
pytestmark = pytest.mark.skipif(os.environ.get("OS_BROWSER_CHECK") != "1", reason="set OS_BROWSER_CHECK=1 (needs Edge and the dashboard on OS_BROWSER_BASE)")


def run(*args, timeout=1500):
    return subprocess.run(["node", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def test_contrast_audit_has_nothing_below_12px_or_aa(tmp_path):
    r = run("scripts/contrast_audit.mjs", "--base", BASE, "--out", str(tmp_path), "--ci")
    assert r.returncode == 0, r.stdout[-3000:]


def test_tabs_are_full_pages():
    r = run("tests/browser/tab_pages_check.mjs", "--base", BASE, "--no-shots")
    assert r.returncode == 0, r.stdout[-3000:]
