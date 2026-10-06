"""Tests for the planting window (season): optional start / end / season_filter on the endpoints of api_v2.py that list species or points.
Run from the repo root: python -m pytest tests/test_api_season.py"""
import shutil, subprocess, sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import palettes as pal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

MAY = {"start": "2026-05-01", "end": "2026-05-31"}          # month 5
SUMMER = {"start": "2026-05-01", "end": "2026-07-31"}       # months 5, 6, 7
JUNE = {"start": "2026-06-01", "end": "2026-06-30"}
DEFAULT = {"start": "2026-10-05", "end": "2026-11-04"}      # "today to +30 days" in early October: months 10, 11


@pytest.fixture(scope="module")
def client():
    api_v2.API_CFG["include_unzoned"] = False            # these tests pin the behaviour of include_unzoned=false (the squares outside the zoning map are not planting squares)
    try:
        with TestClient(api_v2.app) as c:
            yield c
    finally:
        api_v2.API_CFG["include_unzoned"] = True


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def fresh(data, tmp_path, monkeypatch):
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(data, "work", tmp_path)
    api_v2.fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


def months_of(data):
    """{species_id: set of planting months or None}, read independently from the species table."""
    sp = data.ctx.species
    return {int(s): pal.parse_months(v) for s, v in zip(sp.species_id, sp.planting_months)}


def expected(data, window):
    """(in, partly, out) species id sets for a window given as a list of month numbers."""
    win, inn, par, out = set(window), set(), set(), set()
    for sid, m in months_of(data).items():
        if m is None:
            continue
        (inn if win <= m else par if win & m else out).add(sid)
    return inn, par, out


def spot(data):
    r = data.ctx.sites.iloc[100]
    return {"lat": float(r.lat), "lon": float(r.lon)}


# ---- status words -----------------------------------------------------------------------------------------------------------------
def test_status_in_partly_out_and_unknown_for_a_window():
    s = api_v2.parse_season(api_v2.API_CFG, "2026-06-10", "2026-07-20")
    assert s.months == [6, 7] and s.filter == "mark"
    assert api_v2.season_object({5, 6, 7, 8}, s)["status"] == "in_season"
    assert api_v2.season_object({7, 8}, s)["status"] == "partly"
    assert api_v2.season_object({1, 2}, s)["status"] == "out_of_season"
    u = api_v2.season_object(None, s)
    assert u["status"] == "unknown" and u["species_months"] == [] and u["months_in_window"] == []
    o = api_v2.season_object({7, 8}, s)
    assert o["window_months"] == [6, 7] and o["species_months"] == [7, 8] and o["months_in_window"] == [7]


def test_windows_that_cross_the_year_end():
    s = api_v2.parse_season(api_v2.API_CFG, "2026-11-10", "2027-02-20")
    assert s.months == [11, 12, 1, 2] and s.days == 103
    assert api_v2.season_object({11, 12, 1, 2, 3}, s)["status"] == "in_season"
    assert api_v2.season_object({12, 1}, s)["status"] == "partly"
    assert api_v2.season_object({5, 6}, s)["status"] == "out_of_season"
    assert api_v2.season_object({12, 1}, s)["months_in_window"] == [12, 1]
    assert api_v2.parse_season(api_v2.API_CFG, "2026-12-31", "2027-01-01").months == [12, 1]
    assert api_v2.parse_season(api_v2.API_CFG, "2026-03-05", "2026-03-05").months == [3]       # a one-day window
    full = api_v2.parse_season(api_v2.API_CFG, "2026-01-15", "2027-01-15")                      # 366 days: every month, none twice
    assert full.days == 366 and sorted(full.months) == list(range(1, 13)) and len(full.months) == 12


def test_the_species_list_gives_every_species_a_season_object_including_year_end_windows(client, data, monkeypatch):
    n = len(data.ctx.species)
    synthetic = [{12, 1}] * 10 + [{11, 12, 1, 2}] * 10 + [{5}] * 10 + [None] * (n - 30)
    monkeypatch.setattr(data, "species_months", synthetic)
    j = client.get("/species", params={"start": "2026-11-10", "end": "2027-02-20"}).json()
    st = [s["season"]["status"] for s in j["species"]]
    assert st[:10] == ["partly"] * 10 and st[10:20] == ["in_season"] * 10 and st[20:30] == ["out_of_season"] * 10 and set(st[30:]) == {"unknown"}
    assert j["species"][0]["season"]["window_months"] == [11, 12, 1, 2]
    b = j["season"]
    assert (b["in_season"], b["partly"], b["out_of_season"], b["unknown"]) == (10, 10, 10, n - 30) and b["removed"] == 0 and b["filter"] == "mark"


# ---- no dates = exactly as today ------------------------------------------------------------------------------------------------------
def test_without_dates_nothing_changes_and_the_filter_alone_is_ignored(client, data):
    p = {"purpose": "urban", **spot(data)}
    base = client.get("/rank", params=p).json()
    assert "season" not in base and all("season" not in r for r in base["ranking"])
    assert client.get("/rank", params={**p, "season_filter": "only"}).json() == base
    assert "season" not in client.get("/species").json() and all("season" not in s for s in client.get("/species").json()["species"])
    assert b"season" not in client.get("/grid", params={"purpose": "urban"}).content
    assert b"season" not in client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1,2"}).content
    assert "season" not in client.get("/nearest-viable", params=p).json()
    assert "season" not in client.post("/rank/area", json={"purpose": "urban", "barangay": "STA ANA"}).json()
    plan = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 30, "seed": 1}).json()
    assert "season" not in plan and "season" not in plan["summary"] and all("season" not in x for x in plan["palette"])


# ---- scores never change -------------------------------------------------------------------------------------------------------------------
def test_dates_never_change_the_scores(client, data):
    p = {"purpose": "urban", **spot(data), "limit": 45}
    base = {r["species_id"]: (r["S"], r["P"], r["W"], r["eligible"]) for r in client.get("/rank", params=p).json()["ranking"]}
    for window in (SUMMER, DEFAULT):
        for mode in ("mark", "only"):
            j = client.get("/rank", params={**p, **window, "season_filter": mode}).json()
            for r in j["ranking"]:
                assert (r["S"], r["P"], r["W"], r["eligible"]) == base[r["species_id"]], (window, mode, r["species_id"])
    g0 = client.get("/grid", params={"purpose": "urban", "species_id": 1}).json()["columns"]["W"]
    assert client.get("/grid", params={"purpose": "urban", "species_id": 1, **MAY, "season_filter": "mark"}).json()["columns"]["W"] == g0
    a0 = client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1,2,3", "mode": "any"}).json()["areas"]
    assert client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1,2,3", "mode": "any", **MAY}).json()["areas"] == a0


# ---- season_filter=only removes the right species and reports counts ---------------------------------------------------------------------
def test_rank_only_removes_out_of_season_species_and_reports_counts(client, data):
    inn, par, out = expected(data, [5])
    p = {"purpose": "urban", **spot(data), "limit": 45}
    j = client.get("/rank", params={**p, **MAY, "season_filter": "only"}).json()
    ids = {r["species_id"] for r in j["ranking"]}
    assert ids == inn | par and not ids & out
    b = j["season"]
    assert (b["in_season"], b["partly"], b["out_of_season"]) == (len(inn), len(par), len(out)) and b["removed"] == len(out) and b["kept"] == len(ids)
    assert set(b["removed_species_ids"]) == out and "out_of_season" in b["removed_reason"] and b["message"].startswith(f"Only {len(ids)} of {j['species_total']} species")
    assert j["species_total"] == len(data.ctx.species)
    for r in j["ranking"]:                                            # window = month 5 only, so a species is in season or partly never; each row says which
        assert r["season"]["status"] in ("in_season", "unknown")
    mark = client.get("/rank", params={**p, **MAY}).json()
    assert {r["species_id"] for r in mark["ranking"]} == set(months_of(data)) and mark["season"]["removed"] == 0
    assert {r["species_id"]: r["season"]["status"] for r in mark["ranking"]}.keys() >= out


def test_species_list_only_and_the_detail_carry_the_season(client, data):
    inn, par, out = expected(data, [5, 6, 7])
    j = client.get("/species", params={**SUMMER, "season_filter": "only"}).json()
    assert {s["species_id"] for s in j["species"]} == inn | par and j["count"] == len(inn | par) and j["season"]["removed"] == len(out)
    sid = sorted(inn)[0]
    d = client.get(f"/species/{sid}", params=SUMMER).json()
    assert d["season"]["status"] == "in_season" and d["season"]["window_months"] == [5, 6, 7] and d["season_window"]["start"] == "2026-05-01"
    assert "season" not in client.get(f"/species/{sid}").json()
    out_id = sorted(out)[0] if out else None
    if out_id:
        assert client.get(f"/species/{out_id}", params={**SUMMER, "season_filter": "only"}).json()["season"]["status"] == "out_of_season"   # a detail is never hidden


def test_grid_and_area_tables_leave_out_removed_species(client, data):
    inn, par, out = expected(data, [5])
    assert out, "the data must have species that are out of season in May for this test"
    ids = sorted(out)[:2] + sorted(inn)[:1]
    q = {"purpose": "urban", "species_ids": ",".join(map(str, ids)), "mode": "any"}
    g = client.get("/grid", params={**q, **MAY, "season_filter": "only"}).json()
    assert g["species_ids"] == sorted(inn)[:1] and g["season"]["selected_removed_ids"] == sorted(out)[:2]
    only_in = client.get("/grid", params={**q, "species_ids": str(sorted(inn)[0])}).json()
    assert g["columns"]["W"] == only_in["columns"]["W"]                # the removed species no longer colour the map
    best = set(client.get("/grid", params={"purpose": "urban", **MAY, "season_filter": "only"}).json()["columns"]["best_species_id"]) - {-1}
    assert best and not best & out
    one = client.get("/grid", params={"purpose": "urban", "species_id": sorted(out)[0], **MAY, "season_filter": "only"}).json()
    assert set(one["columns"]["W"]) == {0.0} and set(one["columns"]["best_species_id"]) == {-1}       # a removed species colours nothing
    a = client.get("/areas/rank", params={**q, **MAY, "season_filter": "only"}).json()
    assert a["species_ids"] == sorted(inn)[:1] and a["season"]["selected_removed_ids"] == sorted(out)[:2]
    all_gone = client.get("/areas/rank", params={"purpose": "urban", "species_ids": str(sorted(out)[0]), **MAY, "season_filter": "only"}).json()
    assert all_gone["species_ids"] == [] and all(r["mean_W"] == 0 and r["suitable_points"] == 0 for r in all_gone["areas"])
    assert len(client.get("/grid", params={"purpose": "urban", **MAY, "season_filter": "only"}).content) < 250_000


def test_rank_area_only_ranks_and_mixes_the_species_that_can_be_planted(client, data):
    inn, par, out = expected(data, [6])
    j = client.post("/rank/area", params={**JUNE, "season_filter": "only"}, json={"purpose": "urban", "zone": data.zone_names[0], "limit": 45}).json()
    assert {r["species_id"] for r in j["ranking"]} <= inn | par and all(r["season"]["status"] != "out_of_season" for r in j["ranking"])
    assert j["season"]["removed"] == len(out) and {m["species_id"] for m in j["mix"]["species"]} <= inn | par
    assert j["mix"]["common_planting_months"] and set(j["mix"]["common_planting_months"]) <= {6}
    assert j["mix"]["common_months_in_window"] == j["mix"]["common_planting_months"]
    assert all("season" in m for m in j["mix"]["species"])
    none_left = client.post("/rank/area", params={**DEFAULT, "season_filter": "only"}, json={"purpose": "urban", "barangay": "STA ANA"})
    assert none_left.status_code == 200
    n = none_left.json()
    assert n["ranking"] == [] and n["mix"]["species"] == [] and n["season"]["removed"] == len(data.ctx.species) and "planting-window filter" in " ".join(n["mix"]["warnings"])
    marked = client.post("/rank/area", params={**DEFAULT}, json={"purpose": "urban", "barangay": "STA ANA", "limit": 45}).json()
    assert marked["returned"] > 0 and all(r["season"]["status"] == "out_of_season" for r in marked["ranking"])


def test_nearest_viable_only_uses_species_that_can_be_planted(client, data):
    inn, par, out = expected(data, [6])
    p = {"purpose": "urban", **spot(data)}
    j = client.get("/nearest-viable", params={**p, **JUNE, "season_filter": "only"}).json()
    assert j["best_species"]["species_id"] in inn | par and j["best_species"]["season"]["status"] != "out_of_season" and j["season"]["removed"] == len(out)
    r = client.get("/nearest-viable", params={**p, **DEFAULT, "season_filter": "only"})
    assert r.status_code == 404 and "No species can be planted between 5 Oct and 4 Nov" in r.json()["detail"]
    assert client.get("/nearest-viable", params={**p, **DEFAULT}).status_code == 200      # mark: still answers, with the season label


# ---- plans ---------------------------------------------------------------------------------------------------------------------------------
def test_plan_palette_months_lie_inside_the_window(client, data):
    inn, par, out = expected(data, [6])
    r = client.post("/plan-event", params={**JUNE, "season_filter": "only"}, json={"purpose": "urban", "n_saplings": 60, "seed": 1})
    assert r.status_code == 200
    j = r.json()
    assert j["palette"], "a June plan must find a palette"
    sb = j["summary"]["season"]
    assert sb["palette_common_months_in_window"] and set(sb["palette_common_months"]) <= {6}
    assert j["summary"]["palette_common_planting_months"] == sb["palette_common_months"] and j["season"] == sb
    months = months_of(data)
    for p in j["palette"]:
        assert 6 in months[p["species_id"]] and p["season"]["status"] in ("in_season",) and p["species_id"] not in out
    assert {x["species_id"] for x in j["plan"]} <= {p["species_id"] for p in j["palette"]}
    saved = client.get(f"/plans/{j['plan_id']}").json()
    assert saved["summary"]["season"]["palette_common_months_in_window"] == sb["palette_common_months_in_window"]
    wide = client.post("/plan-event", params={**SUMMER, "season_filter": "only"}, json={"purpose": "urban", "n_saplings": 60, "seed": 1}).json()
    assert set(wide["summary"]["season"]["palette_common_months"]) <= {5, 6, 7}


def test_plan_with_every_species_out_of_season_is_refused_in_plain_words_unless_only_marking(client):
    r = client.post("/plan-event", params={**DEFAULT, "season_filter": "only"}, json={"purpose": "urban", "n_saplings": 30, "seed": 1})
    assert r.status_code == 400 and "out of season between 5 Oct and 4 Nov" in r.json()["detail"] and "season_filter=mark" in r.json()["detail"]
    m = client.post("/plan-event", params=DEFAULT, json={"purpose": "urban", "n_saplings": 30, "seed": 1})
    if m.status_code == 200:                                          # marking only: no species is removed, the palette is the old one
        j = m.json()
        assert j["season"]["removed"] == 0 and all(p["season"]["status"] == "out_of_season" for p in j["palette"])
        assert any(w.startswith("season:") for w in j["summary"]["palette_warnings"])
        old = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 30, "seed": 1}).json()
        assert [p["species_id"] for p in j["palette"]] == [p["species_id"] for p in old["palette"]]
        assert [(x["point_id"], x["species_id"]) for x in j["plan"]] == [(x["point_id"], x["species_id"]) for x in old["plan"]]


def test_in_early_october_no_species_is_in_season_for_the_default_dates(client, data):
    j = client.get("/species", params=DEFAULT).json()["season"]
    assert j["window_months"] == [10, 11]
    inn, par, out = expected(data, [10, 11])
    assert (j["in_season"], j["partly"], j["out_of_season"], j["unknown"]) == (len(inn), len(par), len(out), 0)
    assert j["in_season"] == 0 and j["out_of_season"] == len(data.ctx.species)


# ---- bad dates ---------------------------------------------------------------------------------------------------------------------------------
BAD = [({"start": "2026-10-05"}, "both start and end"), ({"end": "2026-10-05"}, "both start and end"),
       ({"start": "10/05/2026", "end": "2026-11-01"}, "YYYY-MM-DD"), ({"start": "2026-2-3", "end": "2026-11-01"}, "YYYY-MM-DD"),
       ({"start": "2026-02-30", "end": "2026-03-10"}, "not a real calendar date"), ({"start": "tomorrow", "end": "2026-11-01"}, "YYYY-MM-DD"),
       ({"start": "2026-11-05", "end": "2026-11-01"}, "before the start"), ({"start": "2026-01-01", "end": "2027-01-02"}, "367 days"),
       ({"start": "2026-10-05", "end": "2026-11-04", "season_filter": "sometimes"}, None)]


@pytest.mark.parametrize("params,words", BAD)
def test_bad_dates_are_a_422_with_a_plain_message_on_every_endpoint(client, data, params, words):
    sp = spot(data)
    calls = [lambda: client.get("/grid", params={"purpose": "urban", **params}), lambda: client.get("/species", params=params),
             lambda: client.get("/species/1", params=params), lambda: client.get("/rank", params={"purpose": "urban", **sp, **params}),
             lambda: client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1", **params}),
             lambda: client.get("/nearest-viable", params={"purpose": "urban", **sp, **params}),
             lambda: client.post("/rank/area", params=params, json={"purpose": "urban", "barangay": "STA ANA"}),
             lambda: client.post("/plan-event", params=params, json={"purpose": "urban", "n_saplings": 30})]
    for call in calls:
        r = call()
        assert r.status_code == 422, r.text
        if words:
            assert words in str(r.json()["detail"])


def test_the_longest_window_is_accepted_and_the_limit_is_in_the_config(client):
    assert api_v2.API_CFG["season_max_days"] == 366
    assert client.get("/species", params={"start": "2026-01-15", "end": "2027-01-15"}).status_code == 200      # 366 days
    assert client.get("/species", params={"start": "2024-02-29", "end": "2024-02-29"}).status_code == 200      # a leap day


# ---- the dashboard's date helpers (JavaScript, run with node) ---------------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_dashboard_date_helpers_javascript_tests_pass():
    r = subprocess.run(["node", "--test", str(ROOT / "frontend" / "src" / "new" / "season.test.mjs")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
