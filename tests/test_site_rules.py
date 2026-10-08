"""Round 15a: rules from the LGU / MPDC / MAO interviews of 7 Oct 2026 (all provisional): the zone rules and conditions, the rehabilitation-site food warning and the Habagat multiplier.
Run from the repo root: python -m pytest tests/test_site_rules.py"""
import sqlite3, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import site_rules as sr  # noqa: E402
import rebuild_site_grid as rg  # noqa: E402

needs = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists(), reason="run the pipeline first")


# ---- zone rules (MPDC, 7 Oct 2026) ----------------------------------------------------------------------------------------------------------------
def test_zone_rules_follow_the_mpdc_answers():
    open_yes = ["Forest Zone", "Agricultural Zone", "Socialized Housing Zone", "Buffer Zone", "Parks and Recreation Zone", "General Institutional Zone", "General Institutional Zonec",
                "Special Reserved Zone", "Medium Industrial Zone", "Minor Commercial - Mixed Use Zone", "Light Industrial Zone"]
    with_conditions = ["High Density Residential - Mixed Use Zone", "Medium Density Residential Zone", "Institutional Research Zone", "Sanitary Landfill"]
    for z in open_yes + with_conditions:
        assert rg.ZONE_RULES[z] == "confirmed", z
    assert rg.ZONE_RULES["Cemetery Zone"] == "excluded" and rg.ZONE_RULES["Quarry Sub-Zone"] == "excluded"
    assert rg.OUTSIDE_ZONING_RULE == "unconfirmed" and rg.UNKNOWN_ZONE_RULE == "excluded"
    c = rg.ZONE_CONDITIONS
    assert all(c[z] == "needs permission (private land)" for z in ("High Density Residential - Mixed Use Zone", "Medium Density Residential Zone", "Institutional Research Zone"))
    assert c["Sanitary Landfill"] == "needs DENR permission"
    assert all(c[z] == "may be converted to other use" for z in ("Special Reserved Zone", "Medium Industrial Zone", "Minor Commercial - Mixed Use Zone", "Light Industrial Zone"))
    assert rg.OUTSIDE_ZONING_CONDITION == "inside Forest Reserve: MENRO/DENR permit" and "Forest Zone" not in c


def test_zone_condition_per_square():
    cond = rg.zone_condition(pd.Series(["Forest Zone", None, "Sanitary Landfill", "Special Reserved Zone", "Medium Density Residential Zone"]))
    assert list(cond) == ["", "inside Forest Reserve: MENRO/DENR permit", "needs DENR permission", "may be converted to other use", "needs permission (private land)"]


@needs
def test_the_grid_has_the_new_counts_and_conditions():
    d = pd.read_csv(PROCESSED / "site_points_clean.csv")
    assert d.zoning_status.value_counts().to_dict() == {"confirmed": 6731, "unconfirmed": 1279, "excluded": 78}
    z = d.groupby("zone_desc").zoning_status.first()
    assert z["Cemetery Zone"] == "excluded" and z["Quarry Sub-Zone"] == "excluded" and z["Special Reserved Zone"] == "confirmed" and z["Sanitary Landfill"] == "confirmed"
    cond = d.zone_condition.fillna("")
    assert (cond[d.zone_desc == "Sanitary Landfill"] == "needs DENR permission").all() and (cond[d.zone_desc == "Forest Zone"] == "").all()
    assert (cond[d.zone_desc.isna()] == "inside Forest Reserve: MENRO/DENR permit").all()
    assert (cond[d.zoning_status == "excluded"] == "").all()
    con = sqlite3.connect(PROCESSED / "scores" / "site_scores.db")
    n, pts = con.execute("select count(*), count(distinct point_id) from site_scores").fetchone()
    assert pts == 8010 and n == 8010 * 45


# ---- rehabilitation sites ---------------------------------------------------------------------------------------------------------------------
def test_food_bearing_comes_from_the_type_text():
    sp = pd.read_csv(PROCESSED / "species_clean.csv").set_index("species_id").common_name
    ids = sr.food_bearing_ids(pd.read_csv(PROCESSED / "species_clean.csv"))
    names = {sp[i] for i in ids}
    assert {"Cacao", "Robusta (Coffee)", "Banana - Saba", "Papaya", "Malunggay", "Coconut", "Indian/Carabao Mango", "Kamagong"} <= names
    assert not ({"Narra", "Clumping Bamboo", "Apitong", "Weeping Fig (Balete)", "Fire Tree"} & names)
    assert len(ids) == 25


def test_rehab_flag_only_for_food_species_in_the_two_zones():
    food = {8, 17}
    assert sr.rehab_flags("Sanitary Landfill", 8, food) == ["rehab_site_food_warning"]
    assert sr.rehab_flags("Special Reserved Zone", 17, food) == ["rehab_site_food_warning"]
    assert sr.rehab_flags("Forest Zone", 8, food) == [] and sr.rehab_flags("Sanitary Landfill", 1, food) == [] and sr.rehab_flags(None, 8, food) == []
    assert sr.REHAB_WARNING == "Fruit or produce from a landfill or mining site may hold heavy metals; do not plan to eat or sell it without testing."


# ---- Habagat -----------------------------------------------------------------------------------------------------------------------------------
def test_habagat_config_and_helpers():
    c = sr.HABAGAT_CFG
    assert c["months"] == (7, 8, 9) and c["multiplier"] == 0.8 and "MAO" in c["source"] and "7 Oct 2026" in c["source"]
    assert set(c["barangays"]) == {"MALY", "DULONG BAYAN I", "DULONG BAYAN II", "STA ANA"}
    assert sr.habagat_months_hit([5, 6]) == [] and sr.habagat_months_hit([6, 7, 8]) == [7, 8] and sr.habagat_months_hit([11, 12, 1, 2]) == []
    f = sr.habagat_factor(["MALY", "SILANGAN", "STA ANA", "", None], [8])
    assert list(f) == [0.8, 1.0, 0.8, 1.0, 1.0]
    assert list(sr.habagat_factor(["MALY"], [5, 6])) == [1.0]
    assert sr.habagat_info([7])["warning"] == "Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep"


@pytest.fixture(scope="module")
def client():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh(client, tmp_path, monkeypatch):
    import api_v2
    import field_verify as fv
    d = client.app.state.data
    monkeypatch.setattr(d, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(d, "work", tmp_path)
    fv.connect(d.field_db).close()
    api_v2.refresh_field(d)


def point_of(zone=None, barangay_name=None, client=None):
    d = client.app.state.data
    sites = d.ctx.sites
    if zone is not None:
        row = sites[sites.zone_desc == zone].iloc[0]
        return float(row.lat), float(row.lon)
    names = np.array([d.barangay_names[b] if b >= 0 else "" for b in d.point_barangay])
    row = sites[names == barangay_name].iloc[len(sites[names == barangay_name]) // 2]
    return float(row.lat), float(row.lon)


MAY = {"start": "2027-05-01", "end": "2027-06-29", "season_filter": "mark"}
AUG = {"start": "2027-08-01", "end": "2027-08-31", "season_filter": "mark"}


@needs
def test_rehab_warning_on_a_landfill_square_does_not_change_s_or_p(client):
    lat, lon = point_of(zone="Sanitary Landfill", client=client)
    j = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon, "limit": 45, **MAY}).json()
    pt = j["point"]
    assert pt["zone"] == "Sanitary Landfill" and pt["zone_condition"] == "needs DENR permission" and pt["rehab_site"]["warning"].startswith("Fruit or produce")
    food = {i["common_name"] for i in j["ranking"] if "rehab_site_food_warning" in i["flags"]}
    assert {"Cacao", "Kamagong", "Papaya"} & food and not ({"Narra", "Clumping Bamboo", "Apitong"} & food)
    assert not any("habagat_washout" in i["flags"] for i in j["ranking"])
    con = sqlite3.connect(PROCESSED / "scores" / "site_scores.db")
    stored = dict(con.execute("select species_id, s_rule from site_scores where point_id=?", (pt["point_id"],)).fetchall())
    for i in j["ranking"]:
        assert abs(i["S"] - round(stored[i["species_id"]], 4)) < 1e-4                 # S is exactly the stored value: the warning changes nothing
    other = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon, "limit": 3}).json()
    assert "zone_condition" in other["point"]


@needs
def test_habagat_lowers_s_by_20_percent_only_in_the_four_barangays_and_only_in_jul_sep(client):
    lat, lon = point_of(barangay_name="STA ANA", client=client)
    may = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon, "limit": 45, **MAY}).json()
    aug = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon, "limit": 45, **AUG}).json()
    plain = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon, "limit": 45}).json()
    assert may["point"].get("habagat") is None and not any("habagat" in i for i in may["ranking"])
    m = {i["species_id"]: i for i in may["ranking"]}
    p = {i["species_id"]: i for i in plain["ranking"]}
    assert all(m[k]["S"] == p[k]["S"] and m[k]["W"] == p[k]["W"] for k in m)           # no dates, or May-June: exactly the old numbers
    assert aug["point"]["habagat"]["applies_to_window"] and aug["point"]["habagat"]["multiplier"] == 0.8
    for i in aug["ranking"]:
        b = i["habagat"]
        assert b["multiplier"] == 0.8 and b["S_before"] == p[i["species_id"]]["S"] and abs(i["S"] - round(0.8 * b["S_before"], 4)) < 2e-4
        assert "habagat_washout" in i["flags"] and b["warning"].startswith("Heavy rain and flooding (Habagat)")
        if i["eligible"]:
            assert i["S"] >= 0.5
    assert aug["species_eligible"] <= may["species_eligible"]
    lat2, lon2 = point_of(barangay_name="SILANGAN", client=client)                    # an upland barangay: nothing changes
    up_aug = client.get("/rank", params={"purpose": "urban", "lat": lat2, "lon": lon2, "limit": 45, **AUG}).json()
    up_may = client.get("/rank", params={"purpose": "urban", "lat": lat2, "lon": lon2, "limit": 45, **MAY}).json()
    assert [(i["species_id"], i["S"], i["W"]) for i in up_aug["ranking"]] == [(i["species_id"], i["S"], i["W"]) for i in up_may["ranking"]]
    assert not any("habagat_washout" in i["flags"] for i in up_aug["ranking"])


@needs
def test_habagat_in_the_map_the_area_ranking_and_a_plan(client):
    g_may = client.get("/grid", params={"purpose": "urban", **MAY}).json()
    g_aug = client.get("/grid", params={"purpose": "urban", **AUG}).json()
    d = client.app.state.data
    names = [d.barangay_names[b] if b >= 0 else "" for b in d.point_barangay]
    hab = sr.habagat_square_mask(names)
    w_may, w_aug = np.array(g_may["columns"]["W"]), np.array(g_aug["columns"]["W"])
    assert (w_aug[hab] <= w_may[hab] + 1e-9).all() and (w_aug[hab] < w_may[hab]).any()
    assert np.allclose(w_aug[~hab], w_may[~hab])
    ra_may = client.post("/rank/area", params=MAY, json={"purpose": "urban", "barangay": "Santa Ana"}).json()
    ra_aug = client.post("/rank/area", params=AUG, json={"purpose": "urban", "barangay": "Santa Ana"}).json()
    top = lambda r: {x["species_id"]: x["mean_W_where_suitable"] for x in r["ranking"]}
    tm, ta = top(ra_may), top(ra_aug)
    assert all(ta[k] < tm[k] for k in ta if k in tm and tm[k] > 0 and ta[k] > 0)
    body = {"purpose": "urban", "n_saplings": 60, "seed": 3, "barangay": "Santa Ana", "campaign": {"name": "Habagat", "unit": ""}}
    p_aug = client.post("/plan-event", params=AUG, json=body).json()
    p_may = client.post("/plan-event", params=MAY, json=body).json()
    s = p_aug["summary"]
    assert s["habagat"]["multiplier"] == 0.8 and s["habagat"]["affected_trees"] == p_aug["n_placed"] > 0
    assert "Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep" in s["palette_warnings"]
    assert all("habagat_washout" in i["flags"] for i in p_aug["plan"]) and not any("habagat_washout" in i["flags"] for i in p_may["plan"])
    assert "habagat" not in p_may["summary"] and p_aug["summary"]["mean_W"] < p_may["summary"]["mean_W"]


@needs
def test_plan_flags_rehab_for_food_species_on_a_landfill_and_leaves_the_plan_alone(client):
    d = client.app.state.data
    sites = d.ctx.sites
    lf = sites[sites.zone_desc == "Sanitary Landfill"]
    lat, lon = float(lf.lat.mean()), float(lf.lon.mean())
    ring = 0.0016
    poly = {"type": "Polygon", "coordinates": [[[lon - ring, lat - ring], [lon + ring, lat - ring], [lon + ring, lat + ring], [lon - ring, lat + ring], [lon - ring, lat - ring]]]}
    r = client.post("/plan-event", params=MAY, json={"purpose": "urban", "species_counts": {"17": 40, "1": 30}, "polygon": poly, "campaign": {"name": "Rehab", "unit": ""}})
    assert r.status_code == 200, r.text
    j = r.json()
    cacao = [i for i in j["plan"] if i["species_id"] == 17 and i["zone"] in sr.REHAB_ZONES]
    narra = [i for i in j["plan"] if i["species_id"] == 1]
    assert all("rehab_site_food_warning" in i["flags"] for i in cacao)
    assert not any("rehab_site_food_warning" in i["flags"] for i in narra)
    if cacao:
        assert j["summary"]["rehab"]["flagged_trees"] == sum(i["trees_planned"] for i in cacao)


@needs
def test_plan_items_and_the_kit_carry_the_zone_condition(client, tmp_path):
    import io, zipfile, csv
    r = client.post("/plan-event", params=MAY, json={"purpose": "urban", "n_saplings": 20, "zone": "Medium Density Residential Zone", "seed": 2, "campaign": {"name": "Cond", "unit": ""}})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["plan"] and all(i["zone_condition"] == "needs permission (private land)" for i in j["plan"])
    assert client.post(f"/plans/{j['plan_id']}/field-kit").status_code == 200
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/kits/{j['plan_id']}.zip").content))
    rows = list(csv.DictReader(io.StringIO(z.read([n for n in z.namelist() if n.endswith("point-list.csv")][0]).decode("utf-8-sig"))))
    assert rows and all("Zone condition: needs permission (private land)." in x["notes"] for x in rows)
    f = client.post("/plan-event", params=MAY, json={"purpose": "urban", "n_saplings": 20, "zone": "Forest Zone", "seed": 2, "campaign": {"name": "NoCond", "unit": ""}}).json()
    assert all("zone_condition" not in i for i in f["plan"])
