"""Round 10a: the field kit of a plan in blocks (blocks.csv, GPX / KML descriptions, README, manifest, PDF layout pages) built straight from pipeline code.
Run from the repo root: python -m pytest tests/test_kit_blocks.py"""
import csv, json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT / "pipeline"))
import field_kit as fk  # noqa: E402
import run_plan as rp  # noqa: E402


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    out = tmp_path_factory.mktemp("kitdata")
    ctx = rp.load_context(PROCESSED, include_unzoned=True)
    plan, summary = rp.make_plan(ctx, "planting", 300, seed=2, layout_mode="blocks")
    f, sj = rp.write_plan(out, "planting", plan, summary, "20270101_000000")
    r = fk.make_kit(f, out / "kits", pdf=True, data_dir=PROCESSED)
    return {"plan": plan, "summary": summary, "res": r, "dir": r["kit_dir"], "csv": f}


def test_blocks_csv_has_the_agreed_columns_and_one_row_per_block(kit):
    rows = list(csv.DictReader((kit["dir"] / "blocks.csv").open(encoding="utf-8")))
    assert list(rows[0]) == fk.BLOCK_CSV_COLUMNS and fk.BLOCK_CSV_COLUMNS[:22][-4:] == ["status", "trees_planted", "moved_lat", "moved_lon"]
    assert len(rows) == len(kit["plan"]) and sum(int(r["trees_planned"]) for r in rows) == 300
    for r in rows:
        assert r["rows"] == r["trees_per_row"] and int(r["trees_planned"]) <= int(r["rows"]) ** 2 and r["plan_id"] == kit["res"]["plan_id"] and r["check_code"] == kit["res"]["check_code"]
        assert r["status"] == r["trees_planted"] == r["moved_lat"] == r["moved_lon"] == "" and r["row_direction"] == "east-west" and r["start_corner"] == "south-west"
        assert "-B" in r["block_ref"]


POINT_LIST_COLUMNS = ["point_ref", "point_id", "species_code", "common_name", "scientific_name", "lat", "lon", "utm_e", "utm_n", "barangay", "zone", "spacing_min_m", "planting_months",
                      "flags", "notes", "plan_id", "check_code", "status", "moved_lat", "moved_lon"]         # exactly the columns of the kit before round 10a


def test_point_list_keeps_its_columns_and_carries_the_block_summary_in_notes(kit):
    rows = list(csv.DictReader((kit["dir"] / "point-list.csv").open(encoding="utf-8")))
    assert list(rows[0]) == POINT_LIST_COLUMNS
    assert all("Block of" in r["notes"] and "trees" in r["notes"] for r in rows)


def test_gpx_and_kml_have_one_waypoint_per_block_with_the_layout(kit):
    n = len(kit["plan"])
    gpx = ET.parse(kit["dir"] / "points.gpx").getroot()
    wpts = [e for e in gpx.iter() if e.tag.endswith("wpt")]
    assert len(wpts) == n
    desc = [next(c for c in w if c.tag.endswith("desc")).text for w in wpts]
    assert all("rows of" in d and "south-west" in d and "spacing" in d for d in desc)
    kml = ET.parse(kit["dir"] / "points.kml").getroot()
    pms = [e for e in kml.iter() if e.tag.endswith("Placemark")]
    assert len(pms) == n and all("rows of" in "".join(x.itertext()) for x in pms)


def test_readme_explains_the_layout_in_plain_words(kit):
    t = (kit["dir"] / "README.txt").read_text(encoding="utf-8")
    for w in ("HOW TO LAY OUT A BLOCK", "tape", "paces", "south-west corner", "COUNT", "blocks.csv", "BRINGING THE RESULTS BACK", "Plant along the contour", kit["res"]["check_code"]):
        assert w in t, w
    for code in set(kit["res"]["points"].species_code):
        assert code in t


def test_manifest_counts_and_pdf_has_a_layout_page_per_species(kit):
    man = json.loads((kit["dir"] / "manifest.json").read_text(encoding="utf-8"))
    assert man["counts"]["blocks"] == len(kit["plan"]) and man["counts"]["trees"] == 300
    names = {f["name"] for f in man["files"]}
    assert {"blocks.csv", "point-list.csv", "points.gpx", "points.kml", "README.txt"} <= names
    pdf = kit["dir"] / "field-map.pdf"
    assert pdf.is_file() and pdf.stat().st_size > 5000
    pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf.read_bytes()))
    assert pages >= 1 + kit["plan"].species_id.nunique()                                     # the map pages plus one layout diagram per species
