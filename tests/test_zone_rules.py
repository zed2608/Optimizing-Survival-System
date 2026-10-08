"""ZONE_RULES in pipeline/rebuild_site_grid.py: defaults unchanged; moving a zone to unconfirmed scores it, flags it and names the zone. The full run uses a temporary copy of the data.
Run from the repo root: python -m pytest tests/test_zone_rules.py"""
import os, shutil, sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import rebuild_site_grid as rsg  # noqa: E402
import run_plan as rp  # noqa: E402
import field_kit as fk  # noqa: E402
import score_sites as ss  # noqa: E402

needs = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (ROOT / "data" / "LandUses.shp").exists(), reason="needs the processed data and the land-use layer")


def test_the_table_lists_every_zone_with_a_valid_rule_and_the_defaults_are_as_before():
    assert set(rsg.ZONE_RULES.values()) <= set(rsg.RULE_VALUES)
    assert [z for z, r in rsg.ZONE_RULES.items() if r == "confirmed"] == rsg.VALID_ZONES and len(rsg.VALID_ZONES) == 15 and "General Institutional Zonec" in rsg.VALID_ZONES     # round 15a: MPDC answers of 7 Oct 2026
    assert {z for z, r in rsg.ZONE_RULES.items() if r == "excluded"} == {"Cemetery Zone", "Quarry Sub-Zone"}
    assert rsg.OUTSIDE_ZONING_RULE == "unconfirmed" and rsg.UNKNOWN_ZONE_RULE == "excluded"


def test_zoning_status_function_follows_the_table():
    z = pd.Series(["Forest Zone", None, "Cemetery Zone", "A zone nobody listed"])
    assert list(rsg.zoning_status(z)) == ["confirmed", "unconfirmed", "excluded", "excluded"]
    assert list(rsg.zoning_status(z, {**rsg.ZONE_RULES, "Cemetery Zone": "unconfirmed"})) == ["confirmed", "unconfirmed", "unconfirmed", "excluded"]
    with pytest.raises(ValueError):
        rsg.zoning_status(z, {**rsg.ZONE_RULES, "Forest Zone": "maybe"})


@needs
def test_the_real_data_columns_equal_the_table_defaults_and_every_zone_is_in_the_table():
    s = pd.read_csv(PROCESSED / "site_points_clean.csv")
    assert set(s.zone_desc.dropna()) <= set(rsg.ZONE_RULES)
    assert list(rsg.zoning_status(s.zone_desc)) == s.zoning_status.tolist()
    assert s.zoning_status.value_counts().to_dict() == {"confirmed": 6731, "unconfirmed": 1279, "excluded": 78}
    assert (s.is_legal_zone.astype(bool) == (s.zoning_status == "confirmed")).all()


@needs
def test_moving_special_reserved_to_unconfirmed_scores_flags_and_names_the_zone(tmp_path, monkeypatch):
    out = tmp_path / "processed"
    shutil.copytree(PROCESSED, out, ignore=shutil.ignore_patterns("plans", "kits", "cache"))
    monkeypatch.setitem(rsg.ZONE_RULES, "Special Reserved Zone", "unconfirmed")
    sys.argv = ["rebuild_site_grid.py", "--input", str(ROOT / "backend" / "Working_Points.csv"), "--landuse", str(ROOT / "data" / "LandUses.shp"), "--out", str(out)]
    rsg.main()
    s = pd.read_csv(out / "site_points_clean.csv")
    assert s.zoning_status.value_counts().to_dict() == {"confirmed": 6731 - 355, "unconfirmed": 1279 + 355, "excluded": 78}      # the counts add up
    assert s.zoning_status.value_counts().sum() == 8088 and int(s.is_legal_zone.sum()) == 6731 - 355
    sr = s[s.zone_desc == "Special Reserved Zone"]
    assert len(sr) == 355 and (sr.zoning_status == "unconfirmed").all()
    ss.run(out, str(ROOT / "data" / "SMR_WATERBODIES_POLY.shp"))
    sc = pd.read_csv(out / "scores" / "site_scores.csv", usecols=["point_id"])
    assert sc.point_id.nunique() == 8010 and set(sr.point_id) <= set(sc.point_id)                                           # the 355 squares are scored
    ctx = rp.load_context(str(out), include_unzoned=True)
    assert len(ctx.sites) == 8010 and len(rp.load_context(str(out), include_unzoned=False).sites) == 6731 - 355
    plan, summary = rp.make_plan(ctx, "urban", 25, zone="Special Reserved Zone", seed=1)
    assert len(plan) == 25 and plan["flags"].str.contains("zoning_unconfirmed").all() and summary["zoning"]["unconfirmed_trees"] == 25
    assert fk.flag_notes("zoning_unconfirmed", "Special Reserved Zone") == "Special Reserved Zone: confirm with the LGU before planting."
    assert fk.flag_notes("zoning_unconfirmed", "") == "Land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting."
    # the API on this copy
    import api_v2
    from fastapi.testclient import TestClient
    monkeypatch.setitem(api_v2.API_CFG, "data_dir", str(out))
    monkeypatch.setitem(api_v2.API_CFG, "field_db", str(tmp_path / "field" / "f.db"))
    with TestClient(api_v2.app) as c:
        c.app.state.data.work = tmp_path
        p = sr.iloc[10]
        j = c.get("/rank", params={"purpose": "urban", "lat": float(p.lat), "lon": float(p.lon), "limit": 5}).json()
        assert j["point"]["zoning_status"] == "unconfirmed" and j["point"]["zoning_note"] == "Special Reserved Zone: confirm with the LGU before planting"
        assert all("zoning_unconfirmed" in it["flags"] for it in j["ranking"])
        on, off = c.get("/grid/context").json(), c.get("/grid/context?include_unzoned=false").json()
        assert on["n"] == 78 and on["legal_points"] == 8010 and off["n"] == 78 + 1634 and off["legal_points"] == 6731 - 355
        health = c.get("/health").json()["limits"]
        assert any("1,634 of the planting squares are not confirmed (1,279 outside our zoning map, 355 in a named zone" in x for x in health)
        r = c.post("/plan-event", json={"purpose": "urban", "n_saplings": 20, "zone": "Special Reserved Zone", "seed": 2}).json()
        assert r["summary"]["zoning"]["unconfirmed_trees"] == 20
        assert c.post(f"/plans/{r['plan_id']}/field-kit").status_code == 200
        import io, zipfile, csv
        z = zipfile.ZipFile(io.BytesIO(c.get(f"/kits/{r['plan_id']}.zip").content))
        rows = list(csv.DictReader(io.StringIO(z.read([n for n in z.namelist() if n.endswith("point-list.csv")][0]).decode("utf-8-sig"))))
        assert all("Special Reserved Zone: confirm with the LGU before planting." in x["notes"] for x in rows)
