"""Tests for saved field verification: pipeline/field_verify.py and the /field-checks endpoints of api_v2.py, and their effects.
Every test gets its own empty field database and a temp folder for plans and kits. Run from the repo root:
python -m pytest tests/test_field_verify.py"""
import csv, io, json, sqlite3, sys
from datetime import datetime, timedelta, timezone
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
import field_kit as fk  # noqa: E402
import field_verify as fv  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

GRID_LIMIT = 250_000


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
    """An empty field database and a temp folder for plans/kits, for every test."""
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(data, "work", tmp_path)
    monkeypatch.setitem(data.cfg, "field_exclude_not_plantable", True)
    fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


def pt(data, k=100, zone="Forest Zone"):
    r = data.ctx.sites[data.ctx.sites.zone_desc == zone].iloc[k]
    return int(r.point_id), float(r.lat), float(r.lon)


def add(client, pid, status="verified_plantable", observer="Ana", **kw):
    body = {"point_id": pid, "status": status, "observer": observer, **kw}
    if status == "not_plantable":
        body.setdefault("reason", "paved")
    return client.post("/field-checks", json=body)


def grid(client, purpose="urban", **q):
    r = client.get("/grid", params={"purpose": purpose, **q})
    assert r.status_code == 200
    return r.json()


def walk(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)
    else:
        yield o


# ---- storage: append-only events, latest wins, disputed -----------------------------------------------------------------
def test_events_are_append_only_even_for_direct_database_access(client, data):
    pid, _, _ = pt(data)
    assert add(client, pid).status_code == 201
    con = sqlite3.connect(data.field_db)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("UPDATE field_checks SET status='needs_recheck'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("DELETE FROM field_checks")
    con.close()
    assert fv.n_events(data.field_db) == 1
    assert not any(r.path.startswith("/field-checks") and ({"PUT", "PATCH", "DELETE"} & r.methods) for r in client.app.routes if hasattr(r, "methods"))


def test_the_table_has_the_specified_columns_and_a_plan_can_be_linked(client, data):
    pid, lat, lon = pt(data)
    r = add(client, pid, "not_plantable", reason="rock_or_ledge", note="ledge", gps_lat=lat, gps_lon=lon, gps_accuracy_m=6.5, plan_id="plan_urban_20260101_000000")
    assert r.status_code == 201, r.text
    con = sqlite3.connect(data.field_db)
    cols = [c[1] for c in con.execute("PRAGMA table_info(field_checks)")]
    assert cols[:15] == ["check_id", "point_id", "status", "reason", "note", "observer", "observed_at", "gps_lat", "gps_lon", "gps_accuracy_m", "moved_lat",
                         "moved_lon", "source", "plan_id", "created_at"]
    row = con.execute("SELECT status, reason, source, plan_id, gps_accuracy_m, created_at, observed_at FROM field_checks").fetchone()
    assert row[:5] == ("not_plantable", "rock_or_ledge", "dashboard", "plan_urban_20260101_000000", 6.5) and row[5] and row[6]
    con.close()


def test_the_latest_event_of_a_point_is_its_current_status_and_history_is_kept(client, data):
    pid, _, _ = pt(data)
    add(client, pid, "verified_plantable", observer="Ana")
    add(client, pid, "not_plantable", observer="Ana", reason="building", note="a wall")
    add(client, pid, "verified_plantable", observer="Ana", note="wall was a neighbour's, the cell is free")
    h = client.get(f"/field-checks/{pid}").json()
    assert [e["status"] for e in h["history"]] == ["verified_plantable", "not_plantable", "verified_plantable"]
    assert [e["check_id"] for e in h["history"]] == sorted(e["check_id"] for e in h["history"])
    assert h["current"]["status"] == "verified_plantable" and h["current"]["n_events"] == 3 and h["history"][1]["reason"] == "building"
    assert not h["left_out_of_rankings"]


def test_disputed_when_the_latest_two_events_come_from_different_observers_and_disagree(client, data):
    a, b, c, e = (pt(data, k)[0] for k in (10, 20, 30, 40))
    add(client, a, "verified_plantable", observer="Ana"); add(client, a, "not_plantable", observer="Ben", reason="paved")
    assert client.get(f"/field-checks/{a}").json()["current"]["disputed"] is True
    add(client, b, "verified_plantable", observer="Ana"); add(client, b, "needs_recheck", observer="Ana")          # same observer
    add(client, c, "verified_plantable", observer="Ana"); add(client, c, "verified_plantable", observer="Ben")      # different but agree
    add(client, e, "verified_plantable", observer="Ana"); add(client, e, "needs_recheck", observer=" ana ")        # same person, other spelling
    assert [client.get(f"/field-checks/{p}").json()["current"]["disputed"] for p in (b, c, e)] == [False, False, False]
    add(client, a, "not_plantable", observer="Cy", reason="paved")                                               # a third observer agrees with the latest
    assert client.get(f"/field-checks/{a}").json()["current"]["disputed"] is False
    assert client.get("/field-checks/summary").json()["disputed_points"] == 0


# ---- validation ---------------------------------------------------------------------------------------------------------
def test_invalid_checks_are_rejected_with_a_clear_message(client, data):
    pid, lat, lon = pt(data)
    ok = {"point_id": pid, "status": "verified_plantable", "observer": "Ana"}
    post = lambda **kw: client.post("/field-checks", json={**ok, **kw})
    cases = [({"point_id": 99999999}, "not a point of the planting grid"), ({"status": "maybe"}, "status"), ({"status": "not_plantable"}, "reason is required"),
             ({"status": "not_plantable", "reason": "magic"}, "reason"), ({"reason": "paved"}, "only applies to not_plantable"),
             ({"observer": ""}, "observer"), ({"observer": "   "}, "observer"), ({"note": "x" * 501}, "note is too long"),
             ({"gps_lat": 14.0, "gps_lon": 121.0}, "outside the municipality"), ({"gps_lat": lat}, "together"), ({"moved_lon": lon}, "together"),
             ({"moved_lat": lat + 0.0018, "moved_lon": lon}, "from the grid point"), ({"moved_lat": lat + 0.02, "moved_lon": lon}, "outside the municipality"), ({"gps_accuracy_m": -1}, "gps_accuracy_m"),
             ({"observed_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()}, "future"), ({"observed_at": "yesterday"}, "observed_at"),
             ({"plan_id": "../x"}, "plan_id"), ({"gps_lat": 95, "gps_lon": lon}, "valid latitude")]
    for body, msg in cases:
        r = post(**body)
        assert r.status_code == 422, (body, r.status_code, r.text)
        assert msg.lower() in json.dumps(r.json()).lower(), (body, r.json())
    assert client.post("/field-checks", json={"status": "verified_plantable", "observer": "Ana"}).status_code == 422     # point_id missing
    assert fv.n_events(data.field_db) == 0                                                                           # nothing was saved
    assert post(note="x" * 500).status_code == 201 and post(observed_at="2026-01-05").status_code == 201
    assert post(moved_lat=lat + 0.00005, moved_lon=lon).status_code == 201                                           # a few metres: fine


def test_clearing_a_not_plantable_point_needs_a_note(client, data):
    pid, _, _ = pt(data)
    add(client, pid, "not_plantable", reason="paved")
    r = add(client, pid, "verified_plantable")
    assert r.status_code == 422 and "note is required to clear" in r.json()["detail"]
    r = add(client, pid, "needs_recheck", note="")
    assert r.status_code == 422
    assert add(client, pid, "needs_recheck", note="not sure it is paved: ask the owner").status_code == 201


# ---- reading ------------------------------------------------------------------------------------------------------------
def test_list_filters_summary_and_export(client, data):
    maly = [int(p) for p in data.ctx.sites[data.point_barangay == data.barangay_names.index("MALY")].point_id[:3]]
    other = int(data.ctx.sites[data.point_barangay != data.barangay_names.index("MALY")].point_id.iloc[10])
    add(client, maly[0], "verified_plantable", observer="Ana")
    add(client, maly[1], "not_plantable", observer="Ben", reason="too_steep")
    add(client, maly[2], "needs_recheck", observer="Ana")
    add(client, other, "not_plantable", observer="Ana", reason="paved")
    lst = lambda **q: client.get("/field-checks", params=q).json()
    assert lst()["total_matching"] == 4 and lst(limit=2)["count"] == 2
    assert {p["point_id"] for p in lst(status="not_plantable")["points"]} == {maly[1], other}
    assert {p["point_id"] for p in lst(barangay="Maly")["points"]} == set(maly) and lst(point_id=other)["total_matching"] == 1
    assert [p["observed_at"] for p in lst()["points"]] == sorted((p["observed_at"] for p in lst()["points"]), reverse=True)
    assert client.get("/field-checks", params={"barangay": "Atlantis"}).status_code == 400 and client.get("/field-checks", params={"status": "x"}).status_code == 422
    s = client.get("/field-checks/summary").json()
    assert s["by_status"] == {"verified_plantable": 1, "not_plantable": 2, "needs_recheck": 1, "planted": 0} and s["points_checked"] == 4 and s["events"] == 4
    assert s["by_reason"]["too_steep"] == 1 and s["by_reason"]["paved"] == 1 and sum(s["by_reason"].values()) == 2
    assert s["by_barangay"]["Maly"] == {"verified_plantable": 1, "not_plantable": 1, "needs_recheck": 1, "planted": 0} and s["left_out_of_rankings"] == 2
    assert client.get("/field-checks/99999999").status_code == 404
    r = client.get("/field-checks/export.csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"] and len(rows) == 4
    assert list(rows[0].keys()) == ["check_id", "point_id", "barangay", "status", "reason", "note", "observer", "observed_at", "gps_lat", "gps_lon",
                                    "gps_accuracy_m", "moved_lat", "moved_lon", "source", "plan_id", "created_at", "trees_planted"] and rows[0]["barangay"]
    add(client, maly[1], "verified_plantable", observer="Cy", note="checked again")
    assert len(list(csv.DictReader(io.StringIO(client.get("/field-checks/export.csv").text)))) == 5                        # the history stays
    assert len(list(csv.DictReader(io.StringIO(client.get("/field-checks/export.csv", params={"scope": "current"}).text)))) == 4


# ---- effects ------------------------------------------------------------------------------------------------------------
def test_a_not_plantable_point_is_left_out_of_rank_grid_areas_and_nearest_viable(client, data):
    pid, lat, lon = pt(data)
    j = data.legal_index[pid]
    before = {p: grid(client, p) for p in ("urban", "planting", "watershed")}
    assert before["urban"]["columns"]["W"][j] > 0 and "field" not in before["urban"]
    b = data.barangay_names[data.point_barangay[j]]
    by_before = {a["name"]: a for a in client.get("/areas/rank", params={"purpose": "urban", "species_ids": "8,22", "mode": "any"}).json()["areas"]}
    area_before = client.post("/rank/area", json={"purpose": "urban", "barangay": b}).json()
    assert client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).status_code == 200
    add(client, pid, "not_plantable", observer="Ben", reason="rock_or_ledge", note="bare rock")
    # /rank
    r = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon})
    assert r.status_code == 404 and "marked not plantable" in r.json()["detail"] and "Ben" in r.json()["detail"] and "rock_or_ledge" in r.json()["detail"]
    # /grid: its own class, compact, W = 0
    for purpose in ("urban", "planting", "watershed"):
        resp = client.get("/grid", params={"purpose": purpose})
        g = resp.json()
        assert len(resp.content) < GRID_LIMIT and g["columns"]["W"][j] == 0 and g["columns"]["best_species_id"][j] == -1 and g["columns"]["n_eligible_species"][j] == 0
        assert g["field"]["index"] == [j] and g["field"]["status"] == [2] and g["field"]["left_out_of_rankings"] == [pid] and None not in list(walk(g))
        assert sum(1 for x in g["columns"]["W"] if x > 0) == sum(1 for x in before[purpose]["columns"]["W"] if x > 0) - 1
        other = [i for i in range(len(g["columns"]["W"])) if i != j]
        assert [g["columns"]["W"][i] for i in other[:500]] == [before[purpose]["columns"]["W"][i] for i in other[:500]]          # nothing else moved
    gm = grid(client, "urban", species_ids="8,22", mode="all")
    assert gm["columns"]["W"][j] == 0 and gm["field"]["index"] == [j]
    # /areas/rank and /rank/area: the point is not candidate land; its count is reported
    by_after = {a["name"]: a for a in client.get("/areas/rank", params={"purpose": "urban", "species_ids": "8,22", "mode": "any"}).json()["areas"]}
    assert by_after[b]["legal_points"] == by_before[b]["legal_points"] - 1 and by_after[b]["not_plantable_points"] == 1
    assert all(by_after[k]["legal_points"] == by_before[k]["legal_points"] for k in by_after if k != b) and "not_plantable_points" not in by_before[b]
    area_after = client.post("/rank/area", json={"purpose": "urban", "barangay": b}).json()
    assert area_after["area"]["legal_points"] == area_before["area"]["legal_points"] - 1 and area_after["area"]["not_plantable_points"] == 1
    assert "not_plantable_points" not in area_before["area"]
    # /nearest-viable never offers it
    nv = client.get("/nearest-viable", params={"purpose": "urban", "lat": lat, "lon": lon}).json()
    assert nv["already_viable"] is False and nv["point"]["point_id"] != pid and 50 < nv["distance_m"] < 400
    assert client.get("/health").json()["field_checks"] == {"events": 1, "points_checked": 1, "left_out_of_rankings": 1, "exclude_not_plantable": True}


def test_excluded_points_never_appear_in_plans_and_the_summary_reports_how_many(client, data):
    first = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 120, "seed": 4}).json()
    ids = [p["point_id"] for p in first["plan"]]
    assert first["summary"]["field_checks"] == {"exclude_not_plantable": True, "excluded_points": 0, "note": "Points whose latest field check is not_plantable were left out of this plan."}
    for p in ids:                                                                              # every point of that plan turns out not to be plantable
        fv.add_event(data.field_db, fv.validate_event({"point_id": p, "status": "not_plantable", "reason": "paved", "observer": "Ana"},
                                                      point_lonlat=api_v2.point_lonlat_of(data)(p)), source="dashboard")
    api_v2.refresh_field(data)
    again = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 120, "seed": 4}).json()
    assert not set(p["point_id"] for p in again["plan"]) & set(ids) and len(again["plan"]) == 120
    assert again["summary"]["field_checks"]["excluded_points"] == 120
    saved = json.loads((Path(data.work) / "plans" / f"{again['plan_id']}_summary.json").read_text(encoding="utf-8"))
    assert saved["field_checks"]["excluded_points"] == 120                                    # also in the saved summary
    zone_plan = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 30, "zone": "Forest Zone", "seed": 4}).json()
    forest_ex = sum(1 for p in ids if data.ctx.sites.zone_desc.iloc[data.legal_index[p]] == "Forest Zone")
    assert zone_plan["summary"]["field_checks"]["excluded_points"] == forest_ex and not set(p["point_id"] for p in zone_plan["plan"]) & set(ids)
    assert client.post("/plan-event", json={"purpose": "urban", "n_saplings": 10, "zone": "Cemetery Zone"}).json()["summary"]["field_checks"]["excluded_points"] == \
        sum(1 for p in ids if data.ctx.sites.zone_desc.iloc[data.legal_index[p]] == "Cemetery Zone")


def test_verified_plantable_adds_a_badge_but_changes_no_score(client, data):
    pid, lat, lon = pt(data)
    j = data.legal_index[pid]
    rank0 = client.get("/rank", params={"purpose": "planting", "lat": lat, "lon": lon, "limit": 45}).json()
    grid0 = {p: grid(client, p) for p in ("urban", "watershed")}
    areas0 = client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1,8", "mode": "all", "by": "zone"}).json()
    plan0 = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 60, "seed": 9}).json()
    assert "field_check" not in rank0
    assert add(client, pid, "verified_plantable", observer="Ana", note="walked it, soil is fine").status_code == 201
    rank1 = client.get("/rank", params={"purpose": "planting", "lat": lat, "lon": lon, "limit": 45}).json()
    assert rank1["field_check"]["status"] == "verified_plantable" and rank1["field_check"]["observer"] == "Ana" and not rank1["field_check"]["left_out_of_rankings"]
    strip = lambda r: [{k: v for k, v in x.items()} for x in r["ranking"]]
    assert strip(rank1) == strip(rank0)                                                       # every W, S, P, confidence is identical
    for p, g0 in grid0.items():
        g1 = grid(client, p)
        assert g1["columns"] == g0["columns"] and g1["field"]["index"] == [j] and g1["field"]["status"] == [1]
        assert len(client.get("/grid", params={"purpose": p}).content) < GRID_LIMIT
    areas1 = client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1,8", "mode": "all", "by": "zone"}).json()
    assert [{k: v for k, v in a.items() if k != "not_plantable_points"} for a in areas1["areas"]] == areas0["areas"]
    plan1 = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 60, "seed": 9}).json()
    assert [(p["point_id"], p["species_id"], p["W"]) for p in plan1["plan"]] == [(p["point_id"], p["species_id"], p["W"]) for p in plan0["plan"]]
    assert plan1["summary"]["field_checks"]["excluded_points"] == 0
    # a verified point that is planned carries the flag (and no score changes)
    planned = plan0["plan"][0]["point_id"]
    add(client, planned, "verified_plantable", observer="Ana")
    plan2 = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 60, "seed": 9}).json()
    item = next(p for p in plan2["plan"] if p["point_id"] == planned)
    assert "field_verified" in item["flags"] and item["W"] == plan0["plan"][0]["W"]


def test_needs_recheck_and_disputed_points_show_a_warning_but_are_not_excluded(client, data):
    pid, lat, lon = pt(data)
    j = data.legal_index[pid]
    w0 = grid(client)["columns"]["W"][j]
    add(client, pid, "needs_recheck", observer="Ana", note="looks wet")
    g = grid(client)
    assert g["columns"]["W"][j] == w0 > 0 and g["field"]["status"] == [3]
    assert client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).status_code == 200
    add(client, pid, "verified_plantable", observer="Ben")                                  # disagrees with Ana: disputed
    r = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).json()
    assert r["field_check"]["disputed"] is True and grid(client)["field"]["status"] == [1 + fv.CFG["disputed_bit"]] and grid(client)["columns"]["W"][j] == w0
    assert client.get("/field-checks/summary").json()["left_out_of_rankings"] == 0


def test_a_not_plantable_point_is_cleared_by_a_new_event_and_comes_back(client, data):
    pid, lat, lon = pt(data)
    j = data.legal_index[pid]
    w0 = grid(client)["columns"]["W"][j]
    add(client, pid, "not_plantable", reason="existing_tree", note="big mango")
    assert grid(client)["columns"]["W"][j] == 0 and client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).status_code == 404
    add(client, pid, "needs_recheck", observer="Ben", note="the mango was cut last month")
    assert grid(client)["columns"]["W"][j] == w0 and client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).status_code == 200
    assert len(client.get(f"/field-checks/{pid}").json()["history"]) == 2                     # the old event is still there


def test_the_switch_turns_the_exclusion_off(client, data, monkeypatch):
    pid, lat, lon = pt(data)
    j = data.legal_index[pid]
    add(client, pid, "not_plantable", reason="paved")
    assert grid(client)["columns"]["W"][j] == 0
    monkeypatch.setitem(data.cfg, "field_exclude_not_plantable", False)
    api_v2.refresh_field(data)
    g = grid(client)
    assert g["columns"]["W"][j] > 0 and g["field"]["status"] == [2] and g["field"]["left_out_of_rankings"] == [] and g["field"]["exclude_switch"] is False
    assert client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).status_code == 200
    plan = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 20, "zone": "Forest Zone"}).json()
    assert plan["summary"]["field_checks"]["excluded_points"] == 0 and "switch is off" in plan["summary"]["field_checks"]["note"]
    assert client.get("/field-checks/summary").json()["left_out_of_rankings"] == 0


def test_without_any_check_the_old_endpoints_are_unchanged(client, data):
    pid, lat, lon = pt(data)
    g = grid(client)
    assert "field" not in g and g["n"] == 6251
    W = np.where(data.ctx.S >= 0.5, data.ctx.S * data.ctx.P["urban"][None, :], 0.0)
    assert np.allclose(g["columns"]["W"], W.max(axis=1), atol=6e-4)
    r = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).json()
    assert "field_check" not in r and r["returned"] == 10
    a = client.get("/areas/rank", params={"purpose": "urban", "species_ids": "8", "mode": "any"}).json()["areas"]
    assert all("not_plantable_points" not in x for x in a) and sum(x["legal_points"] for x in a) == 6251
    area = client.post("/rank/area", json={"purpose": "urban", "zone": "Forest Zone"}).json()["area"]
    assert "not_plantable_points" not in area and area["legal_points"] == 4368
    assert client.get("/nearest-viable", params={"purpose": "urban", "lat": lat, "lon": lon}).json()["already_viable"] is True
    assert client.get("/field-checks").json() == {"count": 0, "total_matching": 0, "points": []}
    s = client.get("/field-checks/summary").json()
    assert s["points_checked"] == 0 and s["events"] == 0 and s["left_out_of_rankings"] == 0
    assert "limits" in client.get("/health").json() and any("no login yet" in x for x in client.get("/health").json()["limits"])


def test_filter_context_removes_points_for_scripts_that_plan_without_the_api(data):
    ids = {int(p) for p in data.ctx.sites.point_id[:5]}
    ctx2 = fv.filter_context(data.ctx, ids)
    assert len(ctx2.sites) == len(data.ctx.sites) - 5 and ctx2.S.shape[0] == len(ctx2.sites) and not set(ctx2.sites.point_id) & ids
    assert fv.filter_context(data.ctx, set()) is data.ctx


# ---- importing a field kit ----------------------------------------------------------------------------------------------
@pytest.fixture
def kit(client, data, tmp_path):
    """A real plan and the point-list.csv exactly as the kit builder writes it."""
    plan = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 40, "seed": 2}).json()
    plan_csv = Path(tmp_path) / "plans" / f"{plan['plan_id']}.csv"
    made = fk.make_kit(plan_csv, tmp_path / "kits", pdf=False, data_dir=PROCESSED, built_on="2026-10-05")
    return {"plan": plan, "csv": (made["kit_dir"] / "point-list.csv"), "plan_id": plan["plan_id"]}


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r), r.fieldnames


def write_csv(rows, cols, delimiter=","):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, delimiter=delimiter, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def post_import(client, text, observer="Team Alpha", **q):
    return client.post("/field-checks/import", params={"observer": observer, **q}, content=text.encode("utf-8"), headers={"Content-Type": "text/csv"})


def fill(rows, data):
    """Fill a kit like the field team would: planted, one moved stake, not plantable, a reason in the status, recheck, and a bad word."""
    near = lambda r, d=0.00004: {"moved_lat": f"{float(r['lat']) + d:.6f}", "moved_lon": f"{float(r['lon']):.6f}"}
    rows[0]["status"] = "planted"
    rows[1]["status"] = "x"; rows[1].update(near(rows[1]))
    rows[2]["status"] = "verified_plantable"
    rows[3]["status"] = "not_plantable"
    rows[4]["status"] = "paved"
    rows[5]["status"] = "recheck"
    rows[6]["status"] = "banana"
    return rows


def test_the_kit_file_as_produced_is_accepted_and_adds_nothing_when_nothing_is_filled(client, data, kit):
    rows, cols = read_rows(kit["csv"])
    assert {"point_ref", "point_id", "plan_id", "check_code", "status", "moved_lat", "moved_lon"} <= set(cols)
    r = post_import(client, kit["csv"].read_text(encoding="utf-8"))
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["accepted"] == 0 and rep["rejected"] == 0 and rep["duplicates"] == 0 and rep["blank"] == len(rows) == 40 and rep["plan_id"] == kit["plan_id"]
    assert fv.n_events(data.field_db) == 0


def test_point_refs_are_mapped_to_points_the_way_the_kit_builder_numbers_them(data, kit):
    import pandas as pd
    rows, _ = read_rows(kit["csv"])
    plan = pd.read_csv(Path(data.work) / "plans" / f"{kit['plan_id']}.csv")
    refs = fv.plan_point_refs(plan, data.ctx.species)
    assert refs == {r["point_ref"]: int(r["point_id"]) for r in rows} and len(refs) == 40


def test_import_saves_filled_rows_maps_status_words_and_reports_rejected_rows(client, data, kit):
    rows, cols = read_rows(kit["csv"])
    fill(rows, data)
    rep = post_import(client, write_csv(rows, cols)).json()
    assert (rep["accepted"], rep["rejected"], rep["duplicates"], rep["blank"]) == (6, 1, 0, 33)
    bad = [x for x in rep["rows"] if x["outcome"] == "rejected"]
    assert len(bad) == 1 and bad[0]["point_ref"] == rows[6]["point_ref"] and "unrecognised status" in bad[0]["reason"] and bad[0]["line"] == 8
    cur = {int(r["point_id"]): client.get(f"/field-checks/{r['point_id']}").json() for r in rows[:7]}
    assert [cur[int(r["point_id"])]["current"]["status"] for r in rows[:6]] == ["verified_plantable"] * 3 + ["not_plantable", "not_plantable", "needs_recheck"]
    assert cur[int(rows[4]["point_id"])]["current"]["reason"] == "paved" and cur[int(rows[3]["point_id"])]["current"]["reason"] == "other"
    assert "no reason" in cur[int(rows[3]["point_id"])]["current"]["note"] and cur[int(rows[6]["point_id"])]["history"] == []
    e = cur[int(rows[1]["point_id"])]["history"][0]
    assert e["source"] == "kit_import" and e["plan_id"] == kit["plan_id"] and e["observer"] == "Team Alpha" and abs(e["moved_lat"] - float(rows[1]["moved_lat"])) < 1e-9
    assert fv.n_events(data.field_db) == 6
    assert {int(rows[3]["point_id"]), int(rows[4]["point_id"])} <= data.field_ex_ids                    # the two not plantable points are left out now
    assert client.get("/field-checks/summary").json()["left_out_of_rankings"] == 2


def test_importing_the_same_file_twice_adds_nothing(client, data, kit):
    rows, cols = read_rows(kit["csv"])
    text = write_csv(fill(rows, data), cols)
    first = post_import(client, text).json()
    n = fv.n_events(data.field_db)
    second = post_import(client, text).json()
    assert first["accepted"] == 6 and second["accepted"] == 0 and second["duplicates"] == 6 and second["rejected"] == 1
    assert fv.n_events(data.field_db) == n == 6
    assert post_import(client, text, observer="Someone Else").json()["accepted"] == 0 and fv.n_events(data.field_db) == 6
    rows[0]["moved_lat"], rows[0]["moved_lon"] = f"{float(rows[0]['lat']) + 0.00003:.6f}", rows[0]["lon"]      # a changed row is a new event
    assert post_import(client, write_csv(rows, cols)).json()["accepted"] == 1 and fv.n_events(data.field_db) == 7


def test_import_rejects_bad_rows_with_reasons_and_never_saves_them(client, data, kit):
    rows, cols = read_rows(kit["csv"])
    r0, r1, r2, r3, r4, r5, r6 = rows[:7]
    r0["status"] = "planted"; r0["point_ref"] = "ZZZ-001"                                       # a ref that is not in the plan
    r1["status"] = "planted"; r1["point_id"] = r2["point_id"]                                    # point_id does not match the ref
    r2["status"] = "planted"; r2["check_code"] = "deadbeef"                                      # the plan changed after the kit was built
    r3["status"] = "planted"; r3["moved_lat"], r3["moved_lon"] = f"{float(r3['lat']) + 0.05:.6f}", r3["lon"]      # 5 km away
    r4["status"] = "planted"; r4["moved_lat"] = r4["lat"]                                        # latitude without longitude
    r5["moved_lat"], r5["moved_lon"] = f"{float(r5['lat']):.6f}", f"{float(r5['lon']):.6f}"        # a moved stake but no status
    r6["status"] = "planted"; r6["plan_id"] = "plan_other_20200101_000000"                       # a row of another plan
    rep = post_import(client, write_csv(rows, cols), plan_id=kit["plan_id"]).json()
    assert rep["accepted"] == 0 and rep["rejected"] == 7 and fv.n_events(data.field_db) == 0
    why = {x["point_ref"]: x["reason"] for x in rep["rows"]}
    assert "does not belong to plan" in why["ZZZ-001"] and "does not match point_ref" in why[r1["point_ref"]] and "check code" in why[r2["point_ref"]]
    assert ("from the grid point" in why[r3["point_ref"]] or "outside the municipality" in why[r3["point_ref"]]) and "together" in why[r4["point_ref"]] and "status is empty" in why[r5["point_ref"]]
    assert "belongs to plan" in why[r6["point_ref"]]


def test_import_file_level_errors(client, data, kit, tmp_path):
    good = kit["csv"].read_text(encoding="utf-8")
    assert post_import(client, "").status_code == 400
    assert post_import(client, "a,b,c\n1,2,3\n").status_code == 400 and "does not look like a field kit" in post_import(client, "a,b,c\n1,2,3\n").json()["detail"]
    assert client.post("/field-checks/import", content=good.encode()).status_code == 422                      # observer is required
    assert post_import(client, good, observer="  ").status_code == 400
    assert client.post("/field-checks/import", params={"observer": "Ana"}, content=b"\xff\xfe\x00bad").status_code == 400
    rows, cols = read_rows(kit["csv"])
    rows[0]["status"] = "planted"
    gone = write_csv([{**r, "plan_id": "plan_urban_20200101_000000"} for r in rows], cols)
    rep = post_import(client, gone).json()
    assert rep["accepted"] == 0 and rep["rejected"] == 1 and "was not found among the saved plans" in rep["rows"][0]["reason"]
    mixed = write_csv([{**rows[0]}, {**rows[1], "plan_id": "plan_x_1"}], cols)
    assert post_import(client, mixed).status_code == 400 and "mixes several plans" in post_import(client, mixed).json()["detail"]
    nocol = write_csv([{k: v for k, v in r.items() if k != "plan_id"} for r in rows], [c for c in cols if c != "plan_id"])
    assert post_import(client, nocol).status_code == 400 and "plan_id" in post_import(client, nocol).json()["detail"]
    assert post_import(client, nocol, plan_id=kit["plan_id"]).json()["accepted"] == 1                         # the plan can be given instead
    assert post_import(client, "x" * 2_100_000).status_code == 400
    assert fv.n_events(data.field_db) == 1


def test_import_accepts_excel_style_files_semicolons_and_a_bom(client, data, kit):
    rows, cols = read_rows(kit["csv"])
    rows[0]["status"] = "planted"
    rows[1]["status"] = "not plantable"
    text = "﻿" + write_csv(rows, cols, delimiter=";")
    rep = post_import(client, text).json()
    assert rep["accepted"] == 2 and rep["rejected"] == 0


def test_import_clearing_rules_apply_to_imported_rows_too(client, data, kit):
    rows, cols = read_rows(kit["csv"])
    pid = int(rows[0]["point_id"])
    add(client, pid, "not_plantable", reason="paved")                                           # the dashboard says no ...
    rows[0]["status"] = "planted"                                                              # ... the kit says planted, without a note
    rep = post_import(client, write_csv(rows, cols)).json()
    assert rep["accepted"] == 0 and "note is required to clear" in rep["rows"][0]["reason"] and pid in data.field_ex_ids


def test_grid_and_area_answers_are_never_served_from_the_browser_cache(client, data):
    """They depend on the saved field checks, so a reloaded page must always ask again (max-age=0); boundaries and zones can still be cached."""
    for r in (client.get("/grid", params={"purpose": "urban"}), client.get("/grid", params={"purpose": "urban", "species_ids": "1,2"}),
              client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1,2"})):
        assert "max-age=0" in r.headers["cache-control"] and "must-revalidate" in r.headers["cache-control"]
    assert "max-age=300" in client.get("/geo/boundaries").headers["cache-control"] and "max-age=300" in client.get("/geo/zones").headers["cache-control"]
