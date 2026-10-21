"""Design v2 (Task C): the field kit with spaced points inside the selected area: trees.csv, area.geojson, GPX / KML waypoints, README, blocks.csv extras, PDF."""
import csv, json, math, sys, xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT / "pipeline"))
import field_kit as fk  # noqa: E402
import point_layout as pl  # noqa: E402
import run_plan as rp  # noqa: E402


def spaced_kit(out, plan_file, pdf):
    old = fk.CFG["point_layout"]
    fk.CFG["point_layout"] = "spaced"
    try:
        return fk.make_kit(plan_file, out / "kits", pdf=pdf, data_dir=PROCESSED)
    finally:
        fk.CFG["point_layout"] = old


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    out = tmp_path_factory.mktemp("spaced")
    ctx = rp.load_context(PROCESSED, include_unzoned=True)
    plan, summary = rp.make_plan(ctx, "planting", 300, seed=2, layout_mode="blocks")
    f, sj = rp.write_plan(out, "planting", plan, summary, "20270101_000000")
    r = spaced_kit(out, f, True)
    return {"plan": plan, "res": r, "dir": r["kit_dir"]}


def test_every_tree_has_its_own_row_and_keeps_its_distance(kit):
    rows = list(csv.DictReader((kit["dir"] / "trees.csv").open(encoding="utf-8")))
    df = kit["res"]["points"]
    assert sum(r.geo["placed"] for r in df.itertuples(index=False)) == len(rows) > 100
    rules = pl.species_rules(pd.read_csv(PROCESSED / "species_clean.csv").to_dict("records"))
    sid = {r.species_code: int(r.species_id) for r in df.itertuples(index=False)}
    pts = [(float(r["utm_e"]), float(r["utm_n"]), sid[r["species_code"]]) for r in rows]
    for i in range(0, len(pts), 7):                                                             # every 7th tree against all others: enough, and fast
        x1, y1, s1 = pts[i]
        for (x2, y2, s2) in pts:
            if (x1, y1) == (x2, y2):
                continue
            assert math.hypot(x1 - x2, y1 - y2) >= pl.pair_distance(rules[s1], rules[s2]) - 0.02


def test_gpx_has_start_and_one_waypoint_per_tree_and_kml_has_the_ground(kit):
    n_blocks = len(kit["plan"])
    rows = list(csv.DictReader((kit["dir"] / "trees.csv").open(encoding="utf-8")))
    gpx = ET.parse(kit["dir"] / "points.gpx").getroot()
    names = [next(c for c in w if c.tag.endswith("name")).text for w in gpx.iter() if w.tag.endswith("wpt")]
    assert sum(1 for n in names if n.endswith("-START")) == n_blocks and sum(1 for n in names if "-T" in n) == len(rows)
    kml = ET.parse(kit["dir"] / "points.kml").getroot()
    assert sum(1 for e in kml.iter() if e.tag.endswith("Polygon")) >= n_blocks


def test_area_geojson_blocks_csv_extras_readme_and_pdf(kit):
    gj = json.loads((kit["dir"] / "area.geojson").read_text(encoding="utf-8"))
    kinds = [f["properties"]["kind"] for f in gj["features"]]
    assert "plantable" in kinds and kinds.count("block") >= 1
    rows = list(csv.DictReader((kit["dir"] / "blocks.csv").open(encoding="utf-8")))
    assert list(rows[0])[-4:] == ["layout", "min_distance_m", "trees_fit", "fit_note"] and all(r["layout"] == "spaced" and r["row_direction"] == "spaced points" for r in rows)
    assert all(int(r["trees_fit"]) <= int(r["trees_planned"]) for r in rows)
    readme = (kit["dir"] / "README.txt").read_text(encoding="utf-8")
    assert "DISTANCE RULE" in readme and "PROVISIONAL" in readme and "SPACED POINTS" in readme and "rows run" not in readme.lower()
    assert (kit["dir"] / "field-map.pdf").stat().st_size > 10_000


def test_the_drawn_area_is_used_as_drawn(tmp_path):
    ctx = rp.load_context(PROCESSED, include_unzoned=True)
    plan, summary = rp.make_plan(ctx, "planting", 60, seed=3, layout_mode="blocks")
    c = (float(plan.lon.iloc[0]), float(plan.lat.iloc[0]))                                       # around the first planned square
    d = 0.0009                                                                                  # about 100 m
    summary["request"] = {"polygon": {"type": "Polygon", "coordinates": [[[c[0] - d, c[1] - d], [c[0] + d, c[1] - d], [c[0] + d, c[1] + d], [c[0] - d, c[1] + d], [c[0] - d, c[1] - d]]]}}
    f, sj = rp.write_plan(tmp_path, "planting", plan, summary, "20270102_000000")
    r = spaced_kit(tmp_path, f, False)
    gj = json.loads((r["kit_dir"] / "area.geojson").read_text(encoding="utf-8"))
    assert "selected" in [x["properties"]["kind"] for x in gj["features"]]
    rows = list(csv.DictReader((r["kit_dir"] / "trees.csv").open(encoding="utf-8")))
    assert rows                                                                                  # the polygon covers part of the first planned square
    for x in rows:
        assert c[0] - d <= float(x["lon"]) <= c[0] + d and c[1] - d <= float(x["lat"]) <= c[1] + d
