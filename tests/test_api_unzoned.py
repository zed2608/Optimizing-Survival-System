"""Squares outside the zoning map (zoning_status unconfirmed): scored and flagged, switchable with include_unzoned. Run from the repo root:  python -m pytest tests/test_api_unzoned.py
Data: data/processed (or the temporary copy named by OS_DATA_DIR)."""
import csv, io, json, os, sys, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
needs_data = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists(), reason="run rebuild_site_grid.py and score_sites.py first")
pytestmark = needs_data

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import field_kit as fk  # noqa: E402
import matching as mt  # noqa: E402
import palettes as pal  # noqa: E402
import run_plan as rp  # noqa: E402
import score_sites as ss  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

F = "include_unzoned=false"


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def _outputs_go_to_a_temp_folder(data, tmp_path, monkeypatch):
    monkeypatch.setattr(data, "work", tmp_path)                                  # plans and kits
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")           # saved field checks (never the real database)
    api_v2.fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


@pytest.fixture(scope="module")
def sites():
    return pd.read_csv(PROCESSED / "site_points_clean.csv")


@pytest.fixture(scope="module")
def old_ctx():
    return mt.load_context(str(PROCESSED))                                  # matching.py is unchanged: confirmed legal-zone squares only


def an_unconfirmed(sites, k=0):
    r = sites[sites.zoning_status == "unconfirmed"].iloc[k]
    return float(r.lat), float(r.lon), int(r.point_id)


def box(minlon, minlat, maxlon, maxlat):
    return {"type": "Polygon", "coordinates": [[[minlon, minlat], [maxlon, minlat], [maxlon, maxlat], [minlon, maxlat], [minlon, minlat]]]}


# ---- the data -------------------------------------------------------------------------------------------------------------------
def test_zoning_status_counts_and_is_legal_zone_keeps_its_meaning(sites):
    assert sites.zoning_status.value_counts().to_dict() == {"confirmed": 6731, "unconfirmed": 1279, "excluded": 78}
    assert int(sites.is_legal_zone.astype(bool).sum()) == 6731
    assert (sites.is_legal_zone.astype(bool) == (sites.zoning_status == "confirmed")).all()
    assert sites[sites.zoning_status == "unconfirmed"].zone_desc.isna().all()           # outside every zoning polygon
    ex = sites[sites.zoning_status == "excluded"].zone_desc
    assert ex.notna().all() and not ex.isin(["Forest Zone", "Agricultural Zone"]).any()  # a named non-planting zone


def test_unconfirmed_squares_are_scored_and_excluded_ones_are_not(sites):
    sc = pd.read_csv(PROCESSED / "scores" / "site_scores.csv", usecols=["point_id"])
    ids = set(sc.point_id)
    st = sites.set_index("point_id").zoning_status
    assert len(ids) == 8010 and {st[i] for i in ids} == {"confirmed", "unconfirmed"} and len(sc) == 8010 * 45


def test_unconfirmed_squares_are_scored_with_the_same_rules(sites, data):
    """Score a sample again with the plain rules (zone gate open) and compare with the stored S."""
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    smp = pd.concat([sites[sites.zoning_status == "unconfirmed"].iloc[::40], sites[sites.zoning_status == "confirmed"].iloc[::200]]).copy()
    smp["is_legal_zone"] = True
    smp = smp.drop(columns=["zoning_status"])
    smp["water_dist_m"] = ss.distance_to_water(smp, str(ROOT / "data" / "SMR_WATERBODIES_POLY.shp"))
    again = ss.score_pairs(sp, smp).set_index(["point_id", "species_id"]).s_rule
    ctx = data.ctx
    pos = {int(p): i for i, p in enumerate(ctx.sites.point_id)}
    sid = {int(s): k for k, s in enumerate(ctx.species.species_id)}
    stored = np.array([ctx.S[pos[int(p)], sid[int(s)]] for p, s in again.index])
    assert np.abs(stored - again.round(4).to_numpy()).max() < 1e-9 and len(again) >= 45 * 40


def test_an_excluded_zone_still_fails_the_zone_gate():
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    base = dict(point_id=1, elev_m=200.0, slope_pct=5.0, soil_texture_legacy="Clay Loam", is_legal_zone=False, water_dist_m=500.0)
    r = ss.score_pairs(sp, pd.DataFrame([{**base, "zoning_status": "excluded"}, {**base, "point_id": 2, "zoning_status": "unconfirmed"},
                                         {**base, "point_id": 3, "zoning_status": "confirmed", "is_legal_zone": True}]))
    assert (r[r.point_id == 1].s_rule == 0).all() and r[r.point_id == 1].gate_fail_legal_zone.all()
    assert (r[r.point_id == 2].s_rule.to_numpy() == r[r.point_id == 3].s_rule.to_numpy()).all() and not r[r.point_id == 2].gate_fail_legal_zone.any()


# ---- the switch -----------------------------------------------------------------------------------------------------------------
def test_the_default_is_on_and_the_toggle_switches_the_grid_counts(client, data, sites):
    assert api_v2.API_CFG["include_unzoned"] is True and data.include_unzoned is True
    on = client.get("/grid", params={"purpose": "urban"}).json()
    on2 = client.get("/grid", params={"purpose": "urban", "include_unzoned": "true"}).json()
    off = client.get(f"/grid?purpose=urban&{F}").json()
    assert on == on2 and on["n"] == 8010 and off["n"] == 6731
    z = on["zoning"]
    assert z["n_unconfirmed"] == len(z["unconfirmed_index"]) == 1279
    st = sites.set_index("point_id").zoning_status
    assert {st[on["columns"]["point_id"][i]] for i in z["unconfirmed_index"]} == {"unconfirmed"}
    assert "zoning" not in off and set(off["columns"]["point_id"]) == set(sites[sites.zoning_status == "confirmed"].point_id)
    assert len(client.get("/grid", params={"purpose": "urban"}).content) < api_v2.API_CFG["grid_max_bytes"]
    assert len(client.get(f"/grid?purpose=urban&{F}").content) < 250_000                       # the size limit of before still holds for include_unzoned=false


def test_false_gives_the_results_of_before_grid_municipal_and_context(client, old_ctx):
    P = old_ctx.P["urban"]
    W, _ = mt.weights(old_ctx.S, P)
    off = client.get(f"/grid?purpose=urban&{F}").json()
    assert off["columns"]["point_id"] == old_ctx.sites.point_id.astype(int).tolist()
    assert np.allclose(off["columns"]["W"], np.round(W.max(axis=1), 3))
    st = pal.species_stats(old_ctx.S, P, mt.CFG["s_min"])
    st.insert(0, "species_id", old_ctx.species.species_id.to_numpy())
    want = st.sort_values(["score", "species_id"], ascending=[False, True]).head(15)
    m = client.get(f"/rank/municipal?purpose=urban&{F}").json()
    assert [r["species_id"] for r in m["ranking"]] == want.species_id.tolist() and m["legal_points"] == 6731
    assert np.allclose([r["species_score"] for r in m["ranking"]], want.score.round(4))
    ctx_off = client.get(f"/grid/context?{F}").json()
    assert ctx_off["n"] == 1357 and ctx_off["legal_points"] == 6731 and "zoning" not in ctx_off
    assert ctx_off["reason_counts"]["outside_zoning"] == 1279


def test_on_changes_the_municipal_ranking_inputs_and_the_context_layer(client):
    m = client.get("/rank/municipal", params={"purpose": "urban"}).json()
    assert m["legal_points"] == 8010
    c = client.get("/grid/context").json()
    assert c["n"] == 78 and c["legal_points"] == 8010 and c["total_points"] == 8088 and c["reason_counts"]["outside_zoning"] == 0
    assert sum(c["reason_counts"].values()) == 78
    labels = {t["index"]: t["label"] for t in c["zoning"]["zone_table"]}
    assert "Outside our zoning map" in labels[-1] and all(i < 0 or "not a planting zone" in t or "not open to tree planting" in t for i, t in labels.items())


def test_health_and_known_limits_use_the_numbers_of_the_data(client):
    on = client.get("/health").json()
    off = client.get(f"/health?{F}").json()
    assert on["counts"]["legal_points"] == 8010 and off["counts"]["legal_points"] == 6731 and on["counts"]["grid_points"] == off["counts"]["grid_points"] == 8088
    assert "8,010 planting squares + 78 other squares = 8,088 map squares." in on["limits"]
    assert "6,731 planting squares + 1,357 other squares = 8,088 map squares." in off["limits"]
    assert any("1,279 of the planting squares lie outside our zoning map" in x and "Forest Reserve (Watershed)" in x and "MENRO and DENR" in x for x in on["limits"])
    assert "Land that is not covered by our zoning map (the CLUP 2021-2031 shows it as Forest Reserve, Watershed) is left out until MENRO and DENR confirm it is plantable." in off["limits"]


def test_areas_and_zone_counts_follow_the_switch(client):
    a_on = client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1,2"}).json()
    a_off = client.get(f"/areas/rank?purpose=urban&species_ids=1,2&{F}").json()
    assert a_on["legal_points"] == 8010 and a_off["legal_points"] == 6731
    assert sum(r["legal_points"] for r in a_on["areas"]) <= 8010 and sum(r["legal_points"] for r in a_off["areas"]) == 6731
    z_on = client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1", "by": "zone"}).json()
    z_off = client.get(f"/areas/rank?purpose=urban&species_ids=1&by=zone&{F}").json()
    assert {r["name"]: r["legal_points"] for r in z_on["areas"]} == {r["name"]: r["legal_points"] for r in z_off["areas"]}   # unconfirmed squares have no zone


def test_rank_area_counts_the_squares_of_a_barangay_per_switch(client, data, sites):
    on = client.post("/rank/area", json={"purpose": "urban", "barangay": "Santa Ana"}).json()
    off = client.post(f"/rank/area?{F}", json={"purpose": "urban", "barangay": "Santa Ana"}).json()
    assert on["area"]["legal_points"] >= off["area"]["legal_points"] == 59


# ---- /rank, nearest-viable ------------------------------------------------------------------------------------------------------
def test_rank_an_unconfirmed_square_is_flagged_and_off_it_is_refused(client, sites):
    lat, lon, pid = an_unconfirmed(sites, 3)
    on = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon, "limit": 45})
    assert on.status_code == 200
    j = on.json()
    assert j["point"]["point_id"] == pid and j["point"]["zoning_status"] == "unconfirmed" and "coordinate with MENRO and DENR before planting" in j["point"]["zoning_note"]
    assert j["returned"] == 45 and all("zoning_unconfirmed" in it["flags"] for it in j["ranking"])
    off = client.get(f"/rank?purpose=urban&lat={lat}&lon={lon}&{F}")
    assert off.status_code == 404 and "outside the zoning map" in off.json()["detail"]


def test_rank_a_confirmed_square_is_the_same_in_both_views(client, sites):
    r = sites[sites.zoning_status == "confirmed"].iloc[500]
    q = {"purpose": "planting", "lat": float(r.lat), "lon": float(r.lon), "limit": 45}
    on = client.get("/rank", params=q).json()
    off = client.get("/rank", params={**q, "include_unzoned": "false"}).json()
    assert not any("zoning_unconfirmed" in it["flags"] for it in on["ranking"]) and on["point"]["zoning_status"] == "confirmed"
    strip = lambda j: {k: v for k, v in j.items() if k not in ("point", "limits")}              # noqa: E731
    assert strip(on) == strip(off)
    assert {k: v for k, v in on["point"].items() if not k.startswith("zoning")} == off["point"] and "zoning_status" not in off["point"]


def test_an_excluded_square_has_no_ranking_in_either_view(client, sites):
    r = sites[sites.zoning_status == "excluded"].iloc[0]
    for q in ("", f"&{F}"):
        assert client.get(f"/rank?purpose=urban&lat={r.lat}&lon={r.lon}{q}").status_code == 404


def test_nearest_viable_marks_the_status_and_off_never_offers_an_unconfirmed_square(client, sites):
    lat, lon, pid = an_unconfirmed(sites, 10)
    off = client.get(f"/nearest-viable?purpose=urban&lat={lat}&lon={lon}&{F}").json()
    st = sites.set_index("point_id").zoning_status
    assert st[off["point"]["point_id"]] == "confirmed" and "zoning_status" not in off["point"]
    on = client.get("/nearest-viable", params={"purpose": "urban", "lat": lat, "lon": lon}).json()
    assert on["point"]["zoning_status"] == st[on["point"]["point_id"]]


def test_search_point_says_where_an_unconfirmed_square_stands(client, sites):
    _, _, pid = an_unconfirmed(sites, 5)
    on = client.get(f"/search/point?q={pid}").json()
    assert on["zoning_status"] == "unconfirmed" and on["legal_zone"] is False and "outside our zoning map" in on["note"]
    off = client.get(f"/search/point?q={pid}&{F}").json()
    assert "zoning_status" not in off and "not in a legal planting zone" in off["note"]


# ---- plans, flags, the kit ------------------------------------------------------------------------------------------------------
def dense_unconfirmed_box(sites):
    u = sites[sites.zoning_status == "unconfirmed"]
    c = u.iloc[len(u) // 2]
    near = u.assign(d=np.hypot(u.lon - c.lon, u.lat - c.lat)).nsmallest(60, "d")
    return box(near.lon.min() - 1e-4, near.lat.min() - 1e-4, near.lon.max() + 1e-4, near.lat.max() + 1e-4)


def test_plans_flag_the_unconfirmed_trees_and_count_them(client, sites):
    j = client.post("/plan-event", json={"purpose": "watershed", "n_saplings": 40, "seed": 7, "polygon": dense_unconfirmed_box(sites)})
    assert j.status_code == 200
    j = j.json()
    st = sites.set_index("point_id").zoning_status
    flagged = [it for it in j["plan"] if "zoning_unconfirmed" in it["flags"]]
    assert flagged and all(st[it["point_id"]] == "unconfirmed" for it in flagged)
    assert all(("zoning_unconfirmed" in it["flags"]) == (st[it["point_id"]] == "unconfirmed") for it in j["plan"])
    z = j["summary"]["zoning"]
    assert z["include_unzoned"] is True and z["unconfirmed_trees"] == len(flagged) and z["placed_trees"] == len(j["plan"]) and "coordinate with MENRO and DENR before planting" in z["note"]
    assert j["plan"] and "zoning" in j["summary"]
    got = client.get(f"/plans/{j['plan_id']}").json()                       # the saved plan keeps the flags and the count
    assert got["summary"]["zoning"] == z and [it["flags"] for it in got["plan"]] == [it["flags"] for it in j["plan"]]


def test_the_kit_point_list_flags_and_notes_unconfirmed_points_and_its_columns_are_unchanged(client, sites):
    j = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 40, "seed": 2, "polygon": dense_unconfirmed_box(sites)}).json()
    n_un = j["summary"]["zoning"]["unconfirmed_trees"]
    assert n_un > 0
    assert client.post(f"/plans/{j['plan_id']}/field-kit").status_code == 200
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/kits/{j['plan_id']}.zip").content))
    csv_name = [n for n in z.namelist() if n.endswith("point-list.csv")][0]
    rows = list(csv.DictReader(io.StringIO(z.read(csv_name).decode("utf-8-sig"))))
    assert list(rows[0].keys()) == ["point_ref", "point_id", "species_code", "common_name", "scientific_name", "lat", "lon", "utm_e", "utm_n", "barangay",
                                    "zone", "spacing_min_m", "planting_months", "flags", "notes", "plan_id", "check_code", "status", "moved_lat", "moved_lon"] == fk.CSV_COLUMNS
    un = [r for r in rows if "zoning_unconfirmed" in r["flags"].split(";")]
    assert len(un) == n_un and all("Land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting" in r["notes"] for r in un)
    assert all("zoning_unconfirmed" not in r["flags"] and "outside our zoning map" not in r["notes"] for r in rows if r not in un)
    readme = z.read([n for n in z.namelist() if n.endswith("README.txt")][0]).decode("utf-8")
    assert "zoning_unconfirmed is on land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting" in " ".join(readme.split())


def test_excluded_squares_are_never_planned_and_off_equals_the_old_plan(client, sites, old_ctx):
    st = sites.set_index("point_id").zoning_status
    big = client.post("/plan-event", json={"purpose": "planting", "n_saplings": 2000, "seed": 4}).json()
    assert {st[it["point_id"]] for it in big["plan"]} <= {"confirmed", "unconfirmed"} and big["summary"]["zoning"]["unconfirmed_trees"] > 0
    off = client.post(f"/plan-event?{F}", json={"purpose": "urban", "n_saplings": 60, "seed": 11}).json()
    assert "zoning" not in off["summary"] and not any("zoning_unconfirmed" in it["flags"] for it in off["plan"])
    plan, summary = rp.make_plan(old_ctx, "urban", 60, seed=11)                # the plan of before: matching.load_context, no zoning_status involved
    assert [it["point_id"] for it in off["plan"]] == plan.point_id.tolist() and [it["species_id"] for it in off["plan"]] == plan.species_id.tolist()
    assert off["summary"]["mean_W"] == summary["mean_W"]


def test_command_line_context_has_the_same_switch(old_ctx):
    on, off = rp.load_context(str(PROCESSED), include_unzoned=True), rp.load_context(str(PROCESSED), include_unzoned=False)
    assert len(on.sites) == 8010 and len(off.sites) == 6731 and (off.sites.point_id.to_numpy() == old_ctx.sites.point_id.to_numpy()).all()
    assert np.array_equal(off.S, old_ctx.S) and np.array_equal(rp.confirmed_only(on).S, off.S)
    plan, summary = rp.make_plan(on, "watershed", 200, seed=3)
    assert summary["zoning"]["unconfirmed_trees"] == int(plan["flags"].fillna("").str.contains("zoning_unconfirmed").sum())
    assert rp.UNCONFIRMED_FLAG == "zoning_unconfirmed"


def test_an_unconfirmed_point_can_be_field_checked_and_a_not_plantable_one_is_left_out(client, data, sites):
    lat, lon, pid = an_unconfirmed(sites, 20)
    r = client.post("/field-checks", json={"point_id": pid, "status": "not_plantable", "reason": "paved", "observer": "Test"})
    assert r.status_code == 201, r.text
    assert client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).status_code == 404
    g = client.get("/grid", params={"purpose": "urban"}).json()
    i = g["columns"]["point_id"].index(pid)
    assert g["columns"]["W"][i] == 0 and i in g["zoning"]["unconfirmed_index"]
