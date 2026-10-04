"""Tests for pipeline/field_kit.py. Run from the repo root:  python -m pytest tests/test_field_kit.py"""
import hashlib, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import field_kit as fk  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
pytestmark = pytest.mark.skipif(not (PROCESSED / "species_clean.csv").exists(), reason="Day 1 outputs not generated")
GPX, KML = {"g": "http://www.topografix.com/GPX/1/1"}, {"k": "http://www.opengis.net/kml/2.2"}
SPECIAL = 'Chesa/Tiesa & <Co> "Q" \'x\' Niño'

PLAN_COLUMNS = ["point_id", "lon", "lat", "utm_e", "utm_n", "zone_desc", "species_id", "species", "S", "P", "W", "confidence", "flags", "site_scores_src_ids"]
SPECIES_IDS = [38, 22, 4, 26, 27, 8]          # Chesa/Tiesa, Indian/Carabao Mango, Banaba, Banana - Saba, Banana - Latundan, Kamagong (dioecious)


def species_table(rename_special=False):
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    if rename_special:
        sp.loc[sp.species_id == 38, "common_name"] = SPECIAL
    return sp


def write_plan(folder, name="plan_test_20260101_000000", n=24, with_outside=True, species_ids=SPECIES_IDS, edit=None):
    folder.mkdir(parents=True, exist_ok=True)
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv")
    sites = sites[sites.is_legal_zone.astype(bool)].iloc[::97].head(n).reset_index(drop=True)
    sp = species_table().set_index("species_id")
    df = pd.DataFrame({"point_id": sites.point_id, "lon": sites.lon, "lat": sites.lat, "utm_e": sites.utm_e, "utm_n": sites.utm_n,
                       "zone_desc": sites.zone_desc, "species_id": [species_ids[i % len(species_ids)] for i in range(len(sites))]})
    df["species"] = df.species_id.map(sp.common_name)
    df["S"], df["P"], df["W"], df["confidence"] = 0.9, 0.7, 0.63, 1.0
    df["flags"] = np.where(df.species_id == 8, "needs_both_sexes", "")
    df["site_scores_src_ids"] = "1;2"
    if with_outside:                                                       # a point outside every barangay polygon
        df.loc[0, ["lon", "lat", "utm_e", "utm_n"]] = [121.35, 14.60, 330000.0, 1615000.0]
    if edit:
        edit(df)
    df = df[PLAN_COLUMNS]
    csv = folder / f"{name}.csv"
    df.to_csv(csv, index=False)
    (folder / f"{name}_summary.json").write_text(json.dumps({
        "purpose": "urban", "n_saplings_requested": len(df), "saplings_unmatched": 0, "saplings_unallocated": 0,
        "existing_trees": "no trees table given: no exclusion zone applied",
        "limits": ["Each point is a ~100 m grid cell, so the plan places at most one tree per cell.", "Weights are provisional."]}), encoding="utf-8")
    return csv, df


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    d = tmp_path_factory.mktemp("kit")
    csv, plan = write_plan(d / "plans")
    r = fk.make_kit(csv, d / "out", pdf=False, built_on="2026-01-02")
    return {"csv": csv, "plan": plan, "res": r, "dir": r["kit_dir"], "tmp": d}


# ---- GPX / KML ---------------------------------------------------------------------------------------------------------
def test_gpx_parses_has_one_waypoint_per_plan_row_and_matching_coordinates(kit):
    root = ET.parse(kit["dir"] / "points.gpx").getroot()
    assert root.tag == "{%s}gpx" % GPX["g"] and root.get("version") == "1.1"
    wpts = root.findall("g:wpt", GPX)
    plan, pts = kit["plan"], kit["res"]["points"].set_index("point_ref")
    assert len(wpts) == len(plan)
    by_id = plan.set_index("point_id")
    for w in wpts:
        ref = w.find("g:name", GPX).text
        pid = int(pts.loc[ref, "point_id"])
        assert f"{by_id.lat[pid]:.6f}" == w.get("lat") and f"{by_id.lon[pid]:.6f}" == w.get("lon")
        assert abs(float(w.get("lat")) - by_id.lat[pid]) < 5e-7 and abs(float(w.get("lon")) - by_id.lon[pid]) < 5e-7
        desc = w.find("g:desc", GPX).text
        assert "CENTER of a 100 m grid cell" in desc and "Planting months:" in desc and "Flags:" in desc
    md = root.find("g:metadata", GPX)
    assert kit["res"]["plan_id"] in md.find("g:name", GPX).text and kit["res"]["check_code"] in md.find("g:desc", GPX).text


def test_kml_parses_one_folder_per_species_distinct_colours_and_matching_coordinates(kit):
    root = ET.parse(kit["dir"] / "points.kml").getroot()
    doc = root.find("k:Document", KML)
    marks = doc.findall(".//k:Placemark", KML)
    plan = kit["plan"]
    assert len(marks) == len(plan) and len(doc.findall("k:Folder", KML)) == plan.species_id.nunique()
    colors = [s.find("k:IconStyle/k:color", KML).text for s in doc.findall("k:Style", KML)]
    assert len(colors) == len(set(colors)) == plan.species_id.nunique()
    pts = kit["res"]["points"].set_index("point_ref"); by_id = plan.set_index("point_id")
    for m in marks:
        ref = m.find("k:name", KML).text
        lon, lat, _ = m.find("k:Point/k:coordinates", KML).text.split(",")
        pid = int(pts.loc[ref, "point_id"])
        assert lon == f"{by_id.lon[pid]:.6f}" and lat == f"{by_id.lat[pid]:.6f}"
        assert m.find("k:styleUrl", KML).text == "#s_" + pts.loc[ref, "species_code"]
    assert kit["res"]["check_code"] in doc.find("k:description", KML).text


def test_kml_colour_is_converted_to_aabbggrr():
    assert fk.kml_color("e6194B") == "ff4B19e6"


# ---- codes and refs ----------------------------------------------------------------------------------------------------
def test_species_codes_are_three_uppercase_unique_and_clashes_get_a_digit():
    codes = fk.make_codes([(4, "Banaba"), (26, "Banana - Saba"), (27, "Banana - Latundan"), (8, "Kamagong"), (99, "Ox")])
    assert codes[4] == "BAN" and codes[26] == "BA2" and codes[27] == "BA3" and codes[8] == "KAM" and codes[99] == "OXX"
    assert all(re.fullmatch(r"[A-Z0-9]{3}", c) for c in codes.values()) and len(set(codes.values())) == len(codes)
    many = fk.make_codes([(i, "Banana") for i in range(1, 30)])
    assert len(set(many.values())) == 29 and all(len(c) == 3 for c in many.values())


def test_every_species_has_a_code_and_point_refs_are_unique_and_stable(kit):
    pts = kit["res"]["points"]
    assert pts.species_code.notna().all() and pts.groupby("species_id").species_code.nunique().eq(1).all()
    assert pts.groupby("species_code").species_id.nunique().eq(1).all()
    assert pts.point_ref.is_unique and pts.point_ref.str.fullmatch(r"[A-Z0-9]{3}-\d{3,}").all()
    for code, g in pts.groupby("species_code"):
        assert list(g.point_id) == sorted(g.point_id)                              # numbered in grid-id order
        assert list(g.point_ref) == [f"{code}-{i:03d}" for i in range(1, len(g) + 1)]
    assert {"BAN", "BA2", "BA3"} <= set(pts.species_code)


# ---- CSV -------------------------------------------------------------------------------------------------------------
def test_csv_columns_are_exactly_as_specified_and_blank_columns_are_blank(kit):
    d = pd.read_csv(kit["dir"] / "point-list.csv", dtype=str, keep_default_na=False)
    assert list(d.columns) == ["point_ref", "point_id", "species_code", "common_name", "scientific_name", "lat", "lon", "utm_e", "utm_n", "barangay",
                               "zone", "spacing_min_m", "planting_months", "flags", "notes", "plan_id", "check_code", "status", "moved_lat", "moved_lon"]
    assert len(d) == len(kit["plan"]) and (d.status == "").all() and (d.moved_lat == "").all() and (d.moved_lon == "").all()
    assert (d.plan_id == kit["res"]["plan_id"]).all() and (d.check_code == kit["res"]["check_code"]).all()
    assert (d.barangay != "").all() and (d.scientific_name != "").all() and (d.planting_months != "").all()
    by_id = kit["plan"].set_index("point_id")
    for r in d.itertuples():
        assert r.lat == f"{by_id.lat[int(r.point_id)]:.6f}" and r.lon == f"{by_id.lon[int(r.point_id)]:.6f}"


def test_barangay_comes_from_the_shapefile_and_nearest_is_flagged(kit):
    d = pd.read_csv(kit["dir"] / "point-list.csv", dtype=str, keep_default_na=False)
    outside = d[d.point_id == str(int(kit["plan"].point_id.iloc[0]))].iloc[0]
    assert "barangay_nearest" in outside["flags"] and "outside every barangay polygon" in outside["notes"] and outside["barangay"]
    inside = d[d.point_id != outside.point_id]
    assert not inside["flags"].str.contains("barangay_nearest").any()
    pts = kit["res"]["points"]
    dio = d[d.species_code == pts[pts.species_id == 8].species_code.iloc[0]]
    assert len(dio) > 0
    assert dio["flags"].str.contains("needs_both_sexes").all() and dio["notes"].str.contains("both male and female").all()


# ---- README ----------------------------------------------------------------------------------------------------------
def test_readme_has_the_stamps_the_nudge_rule_and_the_limits(kit):
    t = (kit["dir"] / "README.txt").read_text(encoding="utf-8")
    r = kit["res"]
    for must in (r["plan_id"], r["check_code"], r["meta"]["dataset_hash"], "2026-01-02", "moved_lat", "moved_lon", "up to 10 m", "CENTER of a 100 m",
                 "BOTH sexes", "offline map app", "airplane mode", "a few metres", "KNOWN LIMITS", "at most one tree per cell"):
        assert must in t, must
    assert len(t.splitlines()) < 75                                                    # about one page
    assert len(r["meta"]["dataset_hash"]) == 64


def test_the_nudge_distance_is_a_config_value(tmp_path, monkeypatch):
    monkeypatch.setitem(fk.CFG, "nudge_max_m", 7.0)
    csv, _ = write_plan(tmp_path / "p", n=6)
    r = fk.make_kit(csv, tmp_path / "o", built_on="2026-01-02")
    assert "up to 7 m" in (r["kit_dir"] / "README.txt").read_text(encoding="utf-8") and "up to 7 m" in (r["kit_dir"] / "points.gpx").read_text(encoding="utf-8")


# ---- manifest and zip ------------------------------------------------------------------------------------------------
def test_zip_holds_every_file_and_manifest_hashes_are_correct(kit):
    kd, r = kit["dir"], kit["res"]
    files = sorted(p.name for p in kd.iterdir())
    assert files == sorted(["points.gpx", "points.kml", "point-list.csv", "README.txt", "manifest.json"])
    with zipfile.ZipFile(r["zip"]) as z:
        names = z.namelist()
        assert sorted(names) == sorted(f"field_kit_{r['plan_id']}/{f}" for f in files)
        m = json.loads(kd.joinpath("manifest.json").read_text(encoding="utf-8"))
        assert sorted(f["name"] for f in m["files"]) == sorted(f for f in files if f != "manifest.json")
        for f in m["files"]:
            on_disk = (kd / f["name"]).read_bytes()
            assert f["size_bytes"] == len(on_disk) and f["sha256"] == hashlib.sha256(on_disk).hexdigest()
            assert hashlib.sha256(z.read(f"field_kit_{r['plan_id']}/{f['name']}")).hexdigest() == f["sha256"]
        assert z.read(f"field_kit_{r['plan_id']}/manifest.json") == kd.joinpath("manifest.json").read_bytes()
    assert m["counts"]["points"] == len(kit["plan"]) and sum(v["points"] for v in m["counts"]["per_species"].values()) == len(kit["plan"])
    assert m["plan_file"]["sha256"] == hashlib.sha256(kit["csv"].read_bytes()).hexdigest() and m["limits"] and m["plan_summary"]["purpose"] == "urban"
    assert m["check_code"] == m["plan_file"]["sha256"][:8] and m["nudge_max_m"] == 10.0 and m["dataset"]["hash"] == r["meta"]["dataset_hash"]


def test_a_changed_plan_gives_a_different_check_code_everywhere(kit, tmp_path):
    def edit(df):
        df.loc[3, "species_id"] = 22
    csv2, _ = write_plan(tmp_path / "other", edit=edit)                   # same file name, one row changed
    assert csv2.name == kit["csv"].name and csv2.read_bytes() != kit["csv"].read_bytes()
    r2 = fk.make_kit(csv2, tmp_path / "out2", built_on="2026-01-02")
    assert r2["check_code"] != kit["res"]["check_code"]
    assert r2["check_code"] == hashlib.sha256(csv2.read_bytes()).hexdigest()[:8]
    for f in ("README.txt", "points.gpx", "points.kml", "point-list.csv"):
        assert r2["check_code"] in (r2["kit_dir"] / f).read_text(encoding="utf-8")
        assert kit["res"]["check_code"] not in (r2["kit_dir"] / f).read_text(encoding="utf-8")


def test_same_plan_and_date_give_identical_files(kit, tmp_path):
    r2 = fk.make_kit(kit["csv"], tmp_path / "again", built_on="2026-01-02")
    for f in ("points.gpx", "points.kml", "point-list.csv", "README.txt", "manifest.json"):
        assert (r2["kit_dir"] / f).read_bytes() == (kit["dir"] / f).read_bytes()


# ---- special characters ----------------------------------------------------------------------------------------------
def test_special_characters_do_not_break_the_files_and_file_names_are_safe(tmp_path):
    csv, plan = write_plan(tmp_path / "p", name="plan weird & name (v1) é")
    r = fk.make_kit(csv, tmp_path / "o", built_on="2026-01-02", species_table=species_table(rename_special=True))
    assert re.fullmatch(r"[A-Za-z0-9._-]+", r["kit_dir"].name) and re.fullmatch(r"[A-Za-z0-9._-]+", r["zip"].name) and re.fullmatch(r"[A-Za-z0-9._-]+", r["plan_id"])
    gpx = ET.parse(r["kit_dir"] / "points.gpx").getroot()
    kml = ET.parse(r["kit_dir"] / "points.kml").getroot()
    descs = [w.find("g:desc", GPX).text for w in gpx.findall("g:wpt", GPX)]
    assert any(SPECIAL in x for x in descs)                                  # raw text survives the round trip through XML escaping
    assert any(SPECIAL in (f.find("k:name", KML).text or "") for f in kml.findall(".//k:Folder", KML))
    raw = (r["kit_dir"] / "points.gpx").read_text(encoding="utf-8")
    assert "&amp;" in raw and "&lt;Co&gt;" in raw and "<Co>" not in raw
    d = pd.read_csv(r["kit_dir"] / "point-list.csv", dtype=str, keep_default_na=False)
    assert (d.common_name == SPECIAL).sum() == (plan.species_id == 38).sum()
    json.loads((r["kit_dir"] / "manifest.json").read_text(encoding="utf-8"))
    assert fk.safe_name("Indian/Carabao Mango: 100%?") == "Indian_Carabao_Mango_100" and fk.safe_name("///") == "plan"
    assert fk.make_codes([(1, "Niño Éclair")])[1] == "NIN"


# ---- errors and CLI --------------------------------------------------------------------------------------------------
def test_missing_summary_or_empty_plan_gives_a_clear_error(tmp_path):
    csv, _ = write_plan(tmp_path / "p")
    (csv.with_name(csv.stem + "_summary.json")).unlink()
    with pytest.raises(FileNotFoundError, match="summary JSON"):
        fk.make_kit(csv, tmp_path / "o")
    csv2, _ = write_plan(tmp_path / "q", name="empty", n=0, with_outside=False)
    with pytest.raises(ValueError, match="no rows"):
        fk.make_kit(csv2, tmp_path / "o")


def test_cli_runs_and_prints_sizes(tmp_path, capsys):
    csv, _ = write_plan(tmp_path / "p", n=8)
    fk.main(["--plan", str(csv), "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out
    assert "check code" in out and "points.gpx" in out and "zip:" in out and (tmp_path / "o" / f"field_kit_{csv.stem}.zip").exists()


# ---- PDF -------------------------------------------------------------------------------------------------------------
def test_pdf_is_skipped_with_a_clear_message_when_matplotlib_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "matplotlib", None)                       # makes `import matplotlib` raise ImportError
    csv, _ = write_plan(tmp_path / "p", n=6)
    r = fk.make_kit(csv, tmp_path / "o", pdf=True, built_on="2026-01-02")
    assert "matplotlib is not installed" in capsys.readouterr().out and "matplotlib" in r["pdf_note"]
    assert not (r["kit_dir"] / "field-map.pdf").exists() and (r["kit_dir"] / "points.gpx").exists()


def test_pdf_is_built_when_matplotlib_is_installed(tmp_path):
    pytest.importorskip("matplotlib")
    csv, plan = write_plan(tmp_path / "p", n=30)
    r = fk.make_kit(csv, tmp_path / "o", pdf=True, built_on="2026-01-02")
    pdf = r["kit_dir"] / "field-map.pdf"
    assert pdf.exists() and pdf.read_bytes()[:5] == b"%PDF-" and pdf.stat().st_size > 5000 and r["pdf_note"] is None
    assert "field-map.pdf" in {f["name"] for f in r["manifest"]["files"]}
    with zipfile.ZipFile(r["zip"]) as z:
        assert f"field_kit_{r['plan_id']}/field-map.pdf" in z.namelist()
    text = pdf.read_bytes()
    assert text.count(b"/Type /Page\n") + text.count(b"/Type /Page ") >= 2 or b"/Count" in text


# ---- the example plan made by run_plan.py ----------------------------------------------------------------------------
real_plans = sorted((PROCESSED / "plans").glob("plan_*[0-9].csv")) if (PROCESSED / "plans").exists() else []


@pytest.mark.skipif(not real_plans, reason="no plan in data/processed/plans (run pipeline/run_plan.py)")
def test_kit_from_a_real_run_plan_output(tmp_path):
    csv = real_plans[0]
    plan = pd.read_csv(csv)
    r = fk.make_kit(csv, tmp_path, built_on="2026-01-02")
    pts = r["points"]
    assert len(pts) == len(plan) and pts.point_ref.is_unique and set(pts.point_id) == set(plan.point_id)
    assert len(ET.parse(r["kit_dir"] / "points.gpx").getroot().findall("g:wpt", GPX)) == len(plan)
    assert r["manifest"]["counts"]["per_species"].keys() == set(pts.species_code)
