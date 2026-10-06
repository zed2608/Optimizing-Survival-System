"""Shared test set-up.

1. The tests never touch the real saved field checks: OS_FIELD_DB points at a temporary file (api_v2 reads it when it is imported, so it is set before any test module is loaded).
2. Plans are made in BLOCKS by default since round 10a. The older test suites were written for the one-tree-per-square plan, so they run in points mode (the plan of before) through
   the two defaults below. A test module that wants the real defaults sets BLOCKS_DEFAULT = True; the new block tests also name layout_mode in every request.
"""
import os, sys, tempfile
from pathlib import Path
import pytest

_TMP = tempfile.mkdtemp(prefix="os_tests_")
os.environ.setdefault("OS_FIELD_DB", str(Path(_TMP) / "field_checks.db"))
ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "pipeline")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(autouse=True)
def points_layout_unless_blocks(request, monkeypatch):
    if getattr(request.module, "BLOCKS_DEFAULT", False):
        yield
        return
    api, rp = sys.modules.get("api_v2"), sys.modules.get("run_plan")
    if api is not None:
        monkeypatch.setitem(api.API_CFG, "layout_mode", "points")
    if rp is not None:
        monkeypatch.setitem(rp.CFG, "layout_mode", "points")
    yield
