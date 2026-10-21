"""R1 W1: the planting window only LABELS species. Land fit decides suitable / not suitable; dates never remove a species from a ranking, a list or a plan.
Root cause of the bug: commit 08be556 (5 Oct 2026) made "Only species for my dates" ON by default and the dashboard sent season_filter=only, and the planting_months of the 45 species are May-Sep only,
so any window in Oct-Apr removed all of them ("Only 0 of 45 species can be planted ...", "No species suits this spot")."""
import sys
from pathlib import Path
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

OCT = {"start": "2026-10-22", "end": "2026-11-21", "season_filter": "mark"}


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


def test_an_october_window_lists_every_species_with_a_season_label(client):
    j = client.get("/species", params=OCT).json()
    items = j["species"] if isinstance(j, dict) else j
    assert len(items) == 45 and all(s["season"]["status"] in ("in_season", "partly", "out_of_season", "unknown") for s in items)
    assert j["season"]["species_total"] == 45 and j["season"]["removed"] == 0 or j["season"].get("removed", 0) == 0
    assert sum(1 for s in items if s["season"]["status"] == "out_of_season") >= 40                   # October: nobody is in a planting month, and still all 45 are listed


def test_a_real_point_is_ranked_for_the_october_window(client):
    r = client.get("/rank", params={"lat": 14.691844, "lon": 121.112866, "purpose": "urban", "limit": 45, **OCT})          # grid point 832, Santa Ana
    assert r.status_code == 200, r.text
    items = r.json()["ranking"]
    assert len(items) >= 5 and all("season" in it for it in items)
    assert any(it["season"]["status"] == "out_of_season" for it in items)
    assert r.json()["season"]["removed"] == 0


def test_a_plan_with_out_of_season_species_is_made_and_carries_the_warning(client):
    j = client.post("/plan-event", params=OCT, json={"purpose": "urban", "n_saplings": 60, "seed": 3})
    assert j.status_code == 200, j.text
    body = j.json()
    assert body["plan"] and any("season" in w.lower() for w in body["summary"].get("palette_warnings", []) + body["summary"].get("warnings", []))


def test_the_dashboard_never_asks_for_season_filter_only():
    src = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "src" / "new").glob("*.js*") if ".test." not in p.name)
    assert "export function useOnlySeason() {\n  return [false" in src.replace("\r\n", "\n")
    assert "Only species for my dates" not in (ROOT / "frontend" / "src" / "new" / "PlantingWindow.jsx").read_text(encoding="utf-8")


def test_the_no_species_in_season_message_is_about_the_dates_and_says_the_species_stay_listed():
    s = (ROOT / "frontend" / "src" / "new" / "SeasonNotice.jsx").read_text(encoding="utf-8")
    assert "None of the suitable species are in their best months for your dates. They are still listed; expect more watering and more losses outside the best months." in s
    assert "Show all species" in s and "Change dates" in s
    assert "No species suits this spot" not in s                                                       # that sentence is only for land that rules every species out (plainWords.js, WhyNone)
