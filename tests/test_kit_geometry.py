"""Round 13: the planted rectangle of a block (one shared geometry), the kit files that use it (blocks.csv, GPX, KML, README), the PDF and the plain-word warnings.
Run from the repo root: python -m pytest tests/test_kit_geometry.py"""
import csv, math, re, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT / "pipeline"))
import palettes as pal  # noqa: E402
import field_kit as fk  # noqa: E402

NEEDS_DATA = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")


# ---------------------------------------------------------------------------------------------------------------- the geometry itself
@pytest.mark.parametrize("sp", [2.5, 3.0, 4.0, 5.0, 6.5, 7.5, 10.0, 12.5, 20.0, 25.0, 40.0, 50.0])
def test_margins_are_symmetric_and_the_first_tree_sits_half_a_spacing_inside(sp):
    lay = pal.block_layout(sp)
    n = lay["trees_per_row"]
    g = pal.block_geometry(sp, n, lay["rows"], lay["capacity"])
    sw, ne = g["corners"]["SW"], g["corners"]["NE"]
    assert math.isclose(sw[0], 100 - ne[0]) and math.isclose(sw[1], 100 - ne[1]) and math.isclose(sw[0], sw[1])        # the same margin on all four sides
    assert math.isclose(g["margin_m"], (100 - n * sp) / 2) and math.isclose(g["rect_side_m"], n * sp)
    assert math.isclose(g["first_tree"][0], g["margin_m"] + sp / 2) and math.isclose(g["first_tree"][1], g["margin_m"] + sp / 2)
    for t in g["trees"]:                                                                                                  # every tree lies inside the planted rectangle
        assert sw[0] < t["x"] < ne[0] and sw[1] < t["y"] < ne[1]


def test_the_12_5_m_example_of_the_request():
    g = pal.block_geometry(12.5, 6, 6, 36)
    assert g["margin_m"] == 12.5 and g["rect_side_m"] == 75.0
    assert [t["x"] for t in g["trees"][:6]] == [18.75, 31.25, 43.75, 56.25, 68.75, 81.25]
    assert g["first_tree"] == (18.75, 18.75) and g["last_tree"] == (81.25, 81.25)


def test_a_partial_block_plants_trees_1_to_n_row_by_row_and_leaves_the_rest_empty():
    g = pal.block_geometry(12.5, 6, 6, 14)
    assert [t["k"] for t in g["trees"] if t["planted"]] == list(range(1, 15)) and g["capacity"] == 36
    assert g["last_tree"] == (31.25, 43.75)                                                                              # tree 14 = row 3, second tree
    xs = [t["x"] for t in g["trees"][:12]]
    assert xs == [18.75, 31.25, 43.75, 56.25, 68.75, 81.25] * 2                                                          # east first, then one spacing north
    assert g["trees"][6]["y"] == 31.25


def test_capacity_of_all_45_species_is_what_it_was_before_round_13():
    species = pd.read_csv(PROCESSED / "species_clean.csv")
    bt = pal.block_table(species)
    usable = 100.0 * math.sqrt(0.6)
    seen = 0
    for r in bt.itertuples(index=False):
        if math.isnan(r.spacing_m):
            continue
        n = max(1, int(math.floor(usable / r.spacing_m + 1e-9)))
        assert r.rows == n and r.trees_per_row == n and r.capacity == n * n
        g = pal.block_geometry(r.spacing_m, int(r.trees_per_row), int(r.rows))
        assert g["capacity"] == r.capacity and g["rect_side_m"] <= 100.0 + 1e-9
        seen += 1
    assert seen >= 40


def test_the_javascript_mirror_agrees_with_the_python_numbers():
    node = "node"
    js = ROOT / "frontend" / "src" / "new" / "blockGeometry.js"
    code = ("import('" + js.as_uri() + "').then(m => { const g = m.blockGeometry(12.5, 6, 6, 14); "
            "console.log(JSON.stringify([g.margin, g.rectSide, g.firstTree.x, g.firstTree.y, g.lastTree.x, g.lastTree.y, g.planted])) })")
    try:
        out = subprocess.run([node, "-e", code], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        pytest.skip("node is not installed")
    g = pal.block_geometry(12.5, 6, 6, 14)
    import json
    assert json.loads(out.stdout) == [g["margin_m"], g["rect_side_m"], g["first_tree"][0], g["first_tree"][1], g["last_tree"][0], g["last_tree"][1], 14], out.stderr


# ---------------------------------------------------------------------------------------------------------------- warnings in plain words
def test_plain_word_warnings():
    w = fk.plain_warnings("soil_provisional;ground_built_up;ground_bare;ground_water;zoning_unconfirmed;needs_both_sexes")
    assert w == ["Soil from the LGU soil map (provisional)",
                 "Looks built-up in the satellite land cover: check on the ground first",
                 "Looks bare in the satellite land cover: check on the ground first",
                 "Looks like water in the satellite land cover: check on the ground first",
                 "Outside our zoning map: Forest Reserve, coordinate with MENRO and DENR",
                 "Separate sexes: plant both"]
    assert fk.plain_warnings("") == [] and fk.plain_warnings("some_new_flag") == ["some new flag"]


# ---------------------------------------------------------------------------------------------------------------- the kit
@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    import run_plan as rp
    out = tmp_path_factory.mktemp("kit13")
    ctx = rp.load_context(PROCESSED, include_unzoned=True)
    plan, summary = rp.make_plan(ctx, "planting", 300, seed=2, layout_mode="blocks")
    f, sj = rp.write_plan(out, "planting", plan, summary, "20270101_000000")
    r = fk.make_kit(f, out / "kits", pdf=True, data_dir=PROCESSED)
    return {"plan": plan, "res": r, "dir": r["kit_dir"], "df": r["points"], "out": out, "summary": summary}


@NEEDS_DATA
def test_corner_coordinates_round_trip_and_the_centre_is_the_block_waypoint(kit):
    from pyproj import Transformer
    to_utm = Transformer.from_crs("EPSG:4326", fk.CFG["site_crs"], always_xy=True)
    for r in kit["df"].itertuples(index=False):
        n, sp = int(r.trees_per_row), float(r.spacing_m)
        c = {k: to_utm.transform(lo, la) for k, (la, lo) in r.geo["ll"].items()}
        side = n * sp
        for a, b in (("SW", "SE"), ("SE", "NE"), ("NE", "NW"), ("NW", "SW")):
            assert abs(math.dist(c[a], c[b]) - side) < 0.5
        cx, cy = sum(v[0] for v in c.values()) / 4, sum(v[1] for v in c.values()) / 4
        assert math.dist((cx, cy), (float(r.utm_e), float(r.utm_n))) < 0.5                                                # the square centre is the block waypoint
        sw = to_utm.transform(float(r.start_lon), float(r.start_lat))
        assert abs(sw[0] - float(r.start_utm_e)) < 0.5 and abs(sw[1] - float(r.start_utm_n)) < 0.5
        assert abs(sw[0] - (float(r.utm_e) - 50 + float(r.margin_m))) < 0.5


@NEEDS_DATA
def test_blocks_csv_new_columns_are_last_and_old_ones_keep_their_place(kit):
    rows = list(csv.DictReader((kit["dir"] / "blocks.csv").open(encoding="utf-8")))
    cols = list(rows[0])
    assert cols[:24] == ["block_ref", "point_id", "lat", "lon", "utm_e", "utm_n", "species_code", "common_name", "trees_planned", "spacing_m", "rows", "trees_per_row", "row_direction",
                         "start_corner", "barangay", "zone", "flags", "notes", "status", "trees_planted", "moved_lat", "moved_lon", "plan_id", "check_code"]
    assert cols[24:] == ["start_lat", "start_lon", "start_utm_e", "start_utm_n", "first_tree_lat", "first_tree_lon", "rect_side_m", "margin_m"]
    for r in rows:
        n, sp = int(r["trees_per_row"]), float(r["spacing_m"])
        assert math.isclose(float(r["rect_side_m"]), n * sp) and math.isclose(float(r["margin_m"]), (100 - n * sp) / 2)
        assert r["status"] == r["trees_planted"] == ""


@NEEDS_DATA
def test_gpx_has_start_and_corner_waypoints_with_instructions(kit):
    root = ET.parse(kit["dir"] / "points.gpx").getroot()
    w = {next(c for c in e if c.tag.endswith("name")).text: e for e in root.iter() if e.tag.endswith("wpt")}
    for r in kit["df"].itertuples(index=False):
        for suf in ("START", "SE", "NE", "NW"):
            e = w[f"{r.point_ref}-{suf}"]
            assert abs(float(e.get("lat")) - r.geo["ll"]["SW" if suf == "START" else suf][0]) < 1e-6
        d = next(c for c in w[f"{r.point_ref}-START"] if c.tag.endswith("desc")).text
        assert "stake" in d and "south-west corner" in d and "GPS is good to a few metres" in d


@NEEDS_DATA
def test_kml_has_a_polygon_of_the_planted_rectangle_and_a_start_placemark_per_block(kit):
    root = ET.parse(kit["dir"] / "points.kml").getroot()
    polys = [e for e in root.iter() if e.tag.endswith("Polygon")]
    assert len(polys) == len(kit["df"])
    for pg in polys:
        co = next(e for e in pg.iter() if e.tag.endswith("coordinates")).text.split()
        assert len(co) == 5 and co[0] == co[-1]
    styles = {e.get("id") for e in root.iter() if e.tag.endswith("Style")}
    assert {f"p_{c}" for c in kit["df"].species_code} <= styles
    names = [next(c for c in e if c.tag.endswith("name")).text for e in root.iter() if e.tag.endswith("Placemark")]
    assert sum(n.endswith(" START") for n in names) == len(kit["df"])


@NEEDS_DATA
def test_readme_describes_the_new_geometry(kit):
    t = (kit["dir"] / "README.txt").read_text(encoding="utf-8")
    for w in ("CENTRED", "margin", "-START", "UTM north", "assumed", "tape", "paces", "Never plant on paved or built land", "a map cell, not an exact planting spot",
              "good to a few metres and worse under trees", "house, road, creek"):
        assert w in t, w
    assert "about 39 m south" not in t and "77 m" not in t


@NEEDS_DATA
def test_footer_has_the_release_tag_and_the_12_character_hash_never_the_long_sha(kit):
    ds = fk.dataset_info(PROCESSED)
    assert re.fullmatch(r"[0-9a-f]{12}", ds["hash"]) and ds["tag"] != "unknown"
    st = fk.stamp_text(kit["res"]["meta"])
    assert ds["hash"] in st and ds["tag"] in st and kit["res"]["plan_id"] in st and kit["res"]["check_code"] in st
    assert not re.search(r"[0-9a-f]{40}", st)
    assert not re.search(r"[0-9a-f]{40}", (kit["dir"] / "README.txt").read_text(encoding="utf-8"))
    pytest.importorskip("pymupdf")
    import pymupdf
    doc = pymupdf.open(str(kit["dir"] / "field-map.pdf"))
    text = "".join(p.get_text() for p in doc)
    assert ds["hash"] in text and ds["tag"] in text and not re.search(r"[0-9a-f]{40}", text)
    assert re.search(rf"{len(kit['df'])} blocks, {int(kit['df'].trees_planned.sum())} trees", text)


@NEEDS_DATA
@pytest.mark.parametrize("n_blocks", [1, 2, 6, 30])
def test_pdf_builds_for_1_2_6_and_30_blocks(kit, n_blocks, tmp_path):
    df = pd.concat([kit["df"]] * (n_blocks // len(kit["df"]) + 1)).head(n_blocks).reset_index(drop=True).drop(columns=["geo"])
    df["utm_e"] = [float(e) + 100.0 * i for i, e in enumerate(df.utm_e)]
    df["point_ref"] = [f"{c}-B{i + 1:02d}" for i, c in enumerate(df.species_code)]
    fk.attach_geometry(df)
    path = tmp_path / "field-map.pdf"
    pages = fk.write_pdf(df, kit["res"]["meta"], kit["summary"], path, fk.CFG["landuse_shp"], PROCESSED)
    expect = 1 + n_blocks + max(1, -(-n_blocks // fk.CFG["pdf_block_rows_per_page"]))
    assert pages == expect
    assert len(re.findall(rb"/Type\s*/Page(?![s\w])", path.read_bytes())) == expect


@NEEDS_DATA
def test_pdf_is_optional_without_matplotlib(kit, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    r = fk.make_kit(next(f for f in kit["out"].rglob("plan_*.csv") if not f.name.endswith("_summary.csv")), tmp_path / "k", pdf=True, data_dir=PROCESSED)
    assert r["pdf_note"] and not (r["kit_dir"] / "field-map.pdf").exists() and (r["kit_dir"] / "blocks.csv").exists()
