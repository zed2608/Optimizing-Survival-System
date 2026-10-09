"""Round 15b: the zoning overlay data, the field-status classes (map, progress, PDF), the species search and the colour modules.
Run from the repo root: python -m pytest tests/test_round15b.py"""
import json, subprocess, sys
from pathlib import Path
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import field_status as fst  # noqa: E402
import field_verify as fv  # noqa: E402

needs = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists(), reason="run the pipeline first")


@pytest.fixture(scope="module")
def client():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh(client, tmp_path, monkeypatch):
    import api_v2
    d = client.app.state.data
    monkeypatch.setattr(d, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(d, "work", tmp_path)
    fv.connect(d.field_db).close()
    api_v2.refresh_field(d)


# ---- the colour modules -----------------------------------------------------------------------------------------------------------------------
def test_field_status_classes_python_side():
    assert fst.ORDER == ["planted", "verified", "recheck", "not_plantable", "water", "hard"]
    assert fst.field_class("planted") == "planted" and fst.field_class("verified_plantable") == "verified" and fst.field_class("needs_recheck") == "recheck"
    assert fst.field_class("not_plantable", "too_steep") == "not_plantable" and fst.field_class("not_plantable", "existing_tree") == "not_plantable"
    assert fst.field_class("not_plantable", "creek_or_waterlogged") == "water"
    assert all(fst.field_class("not_plantable", r) == "hard" for r in ("paved", "building", "rock_or_ledge"))
    assert {c["icon"] for k, c in fst.CLASSES.items() if k in ("not_plantable", "water", "hard")} == {"close"}
    assert fst.CLASSES["planted"]["icon"] == "check" and fst.CLASSES["verified"]["icon"] == "ring" and fst.CLASSES["recheck"]["icon"] == "question"


def test_the_node_tests_of_the_colour_modules_pass():
    r = subprocess.run(["node", "--test", "src/new/fieldStatus.test.mjs", "src/new/plainWords.test.mjs"], cwd=ROOT / "frontend", capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-300:]


def test_every_reason_of_the_dashboard_maps_to_a_class():
    reasons = ["paved", "building", "rock_or_ledge", "creek_or_waterlogged", "too_steep", "existing_tree", "owner_refused", "other"]
    cls = {r: fst.field_class("not_plantable", r) for r in reasons}
    assert cls == {"paved": "hard", "building": "hard", "rock_or_ledge": "hard", "creek_or_waterlogged": "water", "too_steep": "not_plantable", "existing_tree": "not_plantable",
                   "owner_refused": "not_plantable", "other": "not_plantable"}


# ---- the zoning overlay -----------------------------------------------------------------------------------------------------------------------
@needs
def test_zoning_endpoint_has_every_zone_rule_condition_and_count(client):
    r = client.get("/geo/zoning")
    assert r.status_code == 200 and len(r.content) < 700_000
    j = r.json()
    feats = {f["properties"]["name"]: f["properties"] for f in j["features"]}
    colours = json.loads((ROOT / "frontend" / "src" / "new" / "zoneColors.json").read_text(encoding="utf-8"))["colors"]
    assert set(feats) == set(colours) and len(feats) == 19                              # one colour for every zone of the layer
    assert feats["Forest Zone"]["grid_squares"] == 4368 and feats["Cemetery Zone"]["rule"] == "excluded" and feats["Quarry Sub-Zone"]["rule"] == "excluded"
    assert feats["Sanitary Landfill"]["condition"] == "needs DENR permission" and feats["Medium Density Residential Zone"]["condition"] == "needs permission (private land)"
    assert feats["Special Reserved Zone"]["condition"] == "may be converted to other use" and feats["Forest Zone"]["condition"] == ""
    assert feats["Major Commercial Zone"]["grid_squares"] == 0 and j["outside_map"]["grid_squares"] == 1279 and "Forest Reserve" in j["outside_map"]["condition"]
    assert sum(p["grid_squares"] for p in feats.values()) + j["outside_map"]["grid_squares"] == 8088
    assert all(f["geometry"]["type"] in ("Polygon", "MultiPolygon") for f in j["features"])


@needs
def test_rank_point_carries_the_zone_condition_for_a_residential_square(client):
    d = client.app.state.data
    row = d.ctx.sites[d.ctx.sites.zone_desc == "Medium Density Residential Zone"].iloc[3]
    j = client.get("/rank", params={"purpose": "urban", "lat": float(row.lat), "lon": float(row.lon), "limit": 3}).json()
    assert j["point"]["zone"] == "Medium Density Residential Zone" and j["point"]["zone_condition"] == "needs permission (private land)"


# ---- field-status classes in /grid and in the progress report ---------------------------------------------------------------------------------
@needs
def test_grid_field_block_has_a_class_per_checked_point(client):
    d = client.app.state.data
    ids = [int(p) for p in d.ctx.sites.point_id.iloc[[10, 20, 30, 40, 50]]]
    marks = [("verified_plantable", None), ("needs_recheck", None), ("not_plantable", "creek_or_waterlogged"), ("not_plantable", "paved"), ("not_plantable", "too_steep")]
    for pid, (st, why) in zip(ids, marks):
        body = {"point_id": pid, "status": st, "observer": "Ana", **({"reason": why} if why else {})}
        assert client.post("/field-checks", json=body).status_code == 201
    g = client.get("/grid", params={"purpose": "urban", "include_unzoned": "true"}).json()
    f = g["field"]
    pos = {pid: k for k, pid in enumerate(g["columns"]["point_id"])}
    got = {pid: f["class"][list(f["index"]).index(pos[pid])] for pid in ids if pos.get(pid) in f["index"]}
    assert got[ids[0]] == "verified" and got[ids[1]] == "recheck" and got[ids[2]] == "water" and got[ids[3]] == "hard" and got[ids[4]] == "not_plantable"
    assert set(f["classes"]) == set(fst.ORDER) and len(f["class"]) == len(f["index"]) == len(f["status"])


@needs
def test_progress_counts_problem_blocks_by_class(client):
    body = {"purpose": "urban", "n_saplings": 150, "seed": 5, "barangay": "Santa Ana", "campaign": {"name": "Classes", "unit": ""}}
    j = client.post("/plan-event", json=body).json()
    plan = j["plan"]
    assert len(plan) >= 3
    for it, why in zip(plan[:3], ("creek_or_waterlogged", "rock_or_ledge", "existing_tree")):
        r = client.post("/field-checks", json={"point_id": it["point_id"], "status": "not_plantable", "reason": why, "observer": "Ana", "plan_id": j["plan_id"]})
        assert r.status_code == 201, r.text
    done = client.post("/field-checks", json={"point_id": plan[3]["point_id"], "status": "planted", "trees_planted": plan[3]["trees_planned"], "observer": "Ana", "plan_id": j["plan_id"]})
    assert done.status_code == 201
    p = client.get(f"/plans/{j['plan_id']}/progress").json()
    assert p["by_class"]["water"]["blocks"] == 1 and p["by_class"]["hard"]["blocks"] == 1 and p["by_class"]["not_plantable"]["blocks"] == 1 and p["by_class"]["planted"]["blocks"] == 1
    assert p["by_class"]["water"]["trees"] == plan[0]["trees_planned"] and set(p["classes"]) == set(fst.ORDER)
    assert p["blocks"]["problem"] == 3
    cls = {b["point_id"]: b["field_class"] for b in p["blocks_list"]}
    assert cls[plan[0]["point_id"]] == "water" and cls[plan[1]["point_id"]] == "hard" and cls[plan[3]["point_id"]] == "planted" and cls[plan[4]["point_id"]] is None


# ---- the field map PDF -------------------------------------------------------------------------------------------------------------------------
@needs
def test_the_field_map_pdf_has_the_status_key(tmp_path):
    import field_kit as fk
    plans = sorted((PROCESSED / "plans").glob("plan_*_summary.json"))
    csvs = [p.with_name(p.name.replace("_summary.json", ".csv")) for p in plans]
    blocks = [c for c in csvs if c.exists() and "trees_planned" in pd.read_csv(c, nrows=1).columns]
    if not blocks:
        pytest.skip("no saved blocks plan")
    r = fk.make_kit(blocks[-1], tmp_path, pdf=True, data_dir=PROCESSED)
    pytest.importorskip("pymupdf")
    import pymupdf
    text = "".join(p.get_text() for p in pymupdf.open(str(r["kit_dir"] / "field-map.pdf")))
    for label in ("Mark each block in the field", "Planted", "Plantable (verified)", "Needs recheck", "Not plantable: water", "Not plantable: paved, building or rock"):
        assert label in text, label


# ---- search -------------------------------------------------------------------------------------------------------------------------------------
@needs
def test_search_finds_species_and_barangays(client):
    for q, sid in (("Kasoy", 19), ("Cacao", 17), ("kamag", 8)):
        j = client.get("/search/all", params={"q": q}).json()
        assert sid in [s["species_id"] for s in j["species"]], q
    b = client.get("/search/all", params={"q": "santa"}).json()
    assert b["barangays"] and b["barangays"][0]["display_name"] == "Santa Ana"


@needs
def test_partner_cautions_never_contain_nan(client):
    for sid in (17, 19, 8, 1, 2, 3):
        j = client.get(f"/species/{sid}/partners").json()
        for p in j.get("partners", j if isinstance(j, list) else []):
            assert "nan" not in [c.lower() for c in p["cautions"]], (sid, p)


# ---- round 15c: the heavy-metals note reaches the plan result on landfill and special reserved squares ------------------------------------------
@needs
@pytest.mark.parametrize("zone", ["Sanitary Landfill", "Special Reserved Zone"])
def test_rehab_note_is_in_the_plan_summary_for_papaya_and_avocado(client, zone):
    body = {"purpose": "urban", "zone": zone, "species_counts": {30: 20, 39: 20}, "campaign": {"name": "Rehab " + zone[:8], "unit": ""}}
    r = client.post("/plan-event", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    rb = j["summary"].get("rehab")
    assert rb and rb["flagged_trees"] > 0 and "heavy metals" in rb["warning"], j["summary"].keys()
    assert any("rehab_site_food_warning" in str(it.get("flags", "")) for it in j["plan"])
