"""Round 14: nothing the Full view showed before is lost. tests/fixtures/full_view_labels_before_round14.json lists every label (lines of text, numbers replaced by #) that the
Full view of the point panel, the area panels, the plan form, the plan result, the species card and the areas panel showed before round 14 (captured in a headless browser).
tests/browser/labels_check.mjs opens the new dashboard in the Detailed view, collects the same panels and checks that every label is still there, except the documented changes:
Compact | Full details became Simple | Detailed, "Please note" became "Good to know", and lines whose value is zero are hidden on purpose.
The browser check runs here when Edge, node, the dashboard (port 5173) and the API (port 8001) are available; otherwise it is skipped (run it by hand with
`node tests/browser/labels_check.mjs after`). Run from the repo root: python -m pytest tests/test_detailed_labels.py"""
import json, os, shutil, socket, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = json.loads((ROOT / "tests" / "fixtures" / "full_view_labels_before_round14.json").read_text(encoding="utf-8"))["captured"]
EDGE = Path(os.environ.get("EDGE_PATH", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"))


def listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0 or socket.create_connection(("localhost", port), 0.5) is not None
        except OSError:
            return False


def test_the_fixture_lists_the_labels_of_every_panel():
    assert set(FIX) >= {"area_panel", "species_card", "point_panel", "plan_form", "plan_result", "areas_panel", "plan_form_species"}
    assert sum(len(v) for v in FIX.values()) > 500
    assert "Compact" in FIX["point_panel"] and "Full details" in FIX["point_panel"]            # the old switch labels, renamed on purpose


def test_the_renamed_labels_exist_in_the_code():
    blob = " ".join(f.read_text(encoding="utf-8") for f in (ROOT / "frontend" / "src" / "new").glob("*.jsx"))
    for new in ("'Simple'", "'Detailed'", "Good to know"):
        assert new in blob


@pytest.mark.skipif(not (shutil.which("node") and EDGE.exists() and listening(5173) and listening(8001)), reason="needs node, Edge, the dashboard on 5173 and the API on 8001")
def test_every_label_of_the_old_full_view_is_in_the_detailed_view_in_a_browser():
    r = subprocess.run(["node", str(ROOT / "tests" / "browser" / "labels_check.mjs"), "after"], capture_output=True, text=True, timeout=600, cwd=ROOT)
    assert "ALL PASS" in r.stdout, r.stdout[-2000:] + r.stderr[-500:]
