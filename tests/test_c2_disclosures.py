"""C2 (overnight 2026-10-15): the Known limits that the system SAYS must really be said, and their numbers must be true for the data of today. Tests only: no behaviour changed.
Each test names the limit (the number follows the list of docs/B5 in reports/overnight, kept out of git). Run from the repo root:  python -m pytest tests/test_c2_disclosures.py"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
BLOCKS_DEFAULT = True                                           # the real defaults (blocks layout), not the points layout the older suites pin
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists(), reason="run scripts/rebuild_scores.py first")

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

NEW = ROOT / "frontend" / "src" / "new"


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def limits(client):
    return client.get("/health").json()["limits"]


@pytest.fixture(scope="module")
def sites():
    return pd.read_csv(PROCESSED / "site_points_clean.csv")


def has(limits, *words):
    return any(all(w in x for w in words) for x in limits)


# ---- the limits as the API says them (the dashboard shows exactly this list: More > Known limits reads /health) ----------------------------------------------
def test_the_dashboard_reads_the_limits_from_health():
    assert "health.data.limits.map" in (NEW / "MoreMenu.jsx").read_text(encoding="utf-8") and 'title="Known limits"' in (NEW / "MoreMenu.jsx").read_text(encoding="utf-8")


def test_1_ph_rain_temperature_are_not_scored(limits):
    assert has(limits, "Soil pH is not scored", "rainfall, temperature")


def test_2_slope_is_from_100m_cells_and_the_22_percent_is_true(limits, sites):
    assert has(limits, "~100 m grid cells", "about 22%", "one-axis")
    share = (sites.slope_method == "partial").mean()
    assert 0.215 <= share <= 0.225, share                         # 1,787 of 8,088 = 22.1% today


def test_3_the_squares_without_soil_are_counted_in_the_words(limits, sites):
    n = int(sites[sites.zoning_status != "excluded"].soil_texture_lgu.isna().sum())
    assert has(limits, "LGU soil map", "not yet verified by the agriculturist", f"{n:,} of the planting squares lie outside that map", "scored without the soil term")
    assert has(limits, "soil_provisional")


def test_4_weights_caps_thresholds_are_provisional(limits):
    assert has(limits, "weights, caps, thresholds", "PROVISIONAL")


def test_5_the_release_and_its_open_issues_are_named_with_the_true_counts(limits):
    ic = pd.read_csv(PROCESSED / "ingest_report.csv").issue.value_counts()
    text = " ".join(x for x in limits if "Species data release" in x)
    assert "v1.0-review" in text and "not signed off" in text.lower()
    assert f"{ic['file_source_not_provided']} cells cite a file that was not provided" in text
    assert f"{ic['off_list_source']} cite sources outside the supplied list" in text
    assert f"{ic['nonstandard_citation']} citations are non-standard" in text
    assert f"{ic['no_type_I_preference']} species have no Type I climate preference" in text


def test_6_s_comes_from_the_random_forest_or_the_rules_and_says_so(limits):
    assert has(limits, "Random Forest") or has(limits, "expert rules") or has(limits, "rule")        # the wording follows the source in use (the tests run with the rules)


def test_7_a_cell_holds_one_block_and_the_tree_range_is_true(limits):
    import palettes as pal
    caps = pal.block_table(pd.read_csv(PROCESSED / "species_clean.csv")).capacity.dropna()
    assert has(limits, "holds at most one planting block of one species", f"{int(caps.min())} to {int(caps.max())} trees", "points layout places one tree per cell")


def test_8_species_data_unverified_is_in_the_limits_and_on_the_rankings(client, limits, sites):
    assert has(limits, "species_data_unverified", "source file that was not provided")
    p = sites[(sites.zoning_status == "confirmed") & sites.slope_pct.between(2, 12)].iloc[0]
    items = client.get("/rank", params={"purpose": "urban", "lat": p.lat, "lon": p.lon, "limit": 45}).json()["ranking"]
    batikuling = [i for i in items if i["species_id"] == 10]
    assert batikuling and "species_data_unverified" in batikuling[0]["flags"]


def test_8b_the_dashboard_has_words_for_that_flag_and_the_zoning_flag():
    pw = (NEW / "plainWords.js").read_text(encoding="utf-8")
    assert "species_data_unverified: 'Species data cites a file we do not have'" in pw
    assert "zoning_unconfirmed" in (NEW / "FlagList.jsx").read_text(encoding="utf-8")


def test_9_scores_are_not_valid_outside_san_mateo(client, limits):
    assert has(limits, "Scores are not valid outside the mapped municipality of San Mateo")
    r = client.get("/weather/week", params={"purpose": "urban", "lat": 14.0, "lon": 120.0})
    assert r.status_code == 422 and "outside the San Mateo area" in r.json()["detail"]


def test_10_the_square_counts_add_up_in_the_words(limits, sites):
    plant = int((sites.zoning_status != "excluded").sum())
    other = int((sites.zoning_status == "excluded").sum())
    assert (plant, other, plant + other) == (8010, 78, 8088)       # the numbers of today: if the data changes on purpose, update them here and in the dashboard text together
    assert has(limits, f"{plant:,} planting squares + {other:,} other squares = {plant + other:,} map squares")


def test_11_the_squares_outside_the_zoning_map_are_counted_and_flagged(client, limits, sites):
    n = int((sites.zoning_status == "unconfirmed").sum())
    assert n == 1279 and has(limits, f"{n:,} of the planting squares lie outside our zoning map", "Forest Reserve", "zoning_unconfirmed", "MENRO and DENR")
    p = sites[(sites.zoning_status == "unconfirmed") & sites.slope_pct.between(2, 20)].iloc[0]
    j = client.get("/rank", params={"purpose": "urban", "lat": p.lat, "lon": p.lon, "limit": 45}).json()
    assert j["point"]["zoning_status"] == "unconfirmed" and "zoning_note" in j["point"]
    assert any("zoning_unconfirmed" in i["flags"] for i in j["ranking"])


def test_12_field_checks_carry_a_name_only(client, limits):
    assert has(limits, "Field checks", "carry a name only", "no login")
    r = client.post("/field-checks", json={"point_id": 832, "status": "needs_recheck", "observer": "C2 disclosure test", "note": "test"})        # the saved event answers with the same limit (temporary field database: see conftest)
    assert r.status_code == 201 and r.json()["limits"] == [x for x in limits if "carry a name only" in x]


def test_13_not_plantable_points_are_left_out_and_the_switch_is_said(limits):
    assert has(limits, "field-check switch", "'not plantable' are left out of rankings and plans", "never changes a score")
    assert "Left out of plans because of a field check" in (NEW / "PointPanel.jsx").read_text(encoding="utf-8")
    assert "left_out_by_field_check" in (ROOT / "api_v2.py").read_text(encoding="utf-8")


# ---- the field kit says its three Filipino limits (C6) and the kit README keeps the limits of the plan ------------------------------------------------------------
def test_the_kit_readme_says_the_three_filipino_limits():
    import field_kit as fk
    lines = fk.kit_limit_lines({"dataset_tag": "v1.0-review"})
    assert lines[0].startswith("Hindi kasama sa score ang pH") and "walang datos ng lupa" in lines[1] and "release v1.0-review" in lines[2]
