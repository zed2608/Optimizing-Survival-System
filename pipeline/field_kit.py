#!/usr/bin/env python3
"""
field_kit.py - Day 4 part 1: build a level-1 field kit from an approved plan.

    python pipeline/field_kit.py --plan data/processed/plans/plan_urban_20261005_021810.csv --out data/processed/kits [--pdf]

Input : a plan CSV and its summary JSON (made by pipeline/run_plan.py; the JSON sits next to the CSV as <plan>_summary.json).
Output: <out>/field_kit_<plan_id>/ with points.gpx, points.kml, point-list.csv, README.txt, manifest.json [, field-map.pdf]
        and <out>/field_kit_<plan_id>.zip with the same files.

Every file is stamped with the plan id and the check code (first 8 characters of the sha256 of the plan CSV, so any change to
the plan changes the code). GPX / KML / README / manifest / PDF also carry the dataset hash and the build date.
Each point is the CENTER of a ~100 m grid cell; the team may move the stake up to NUDGE_MAX_M metres and records the real
position in moved_lat / moved_lon. Nothing is invented: a missing value stays empty, the dataset hash is "unknown" if the
database has no version row.
"""
import argparse, csv, hashlib, json, re, sqlite3, sys, unicodedata, zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import palettes as pal  # noqa: E402
from names import fix_barangay_column  # noqa: E402
import field_status as fst  # noqa: E402

# =====================================================================================================================
# CONFIG - every tunable number lives here. PROVISIONAL until the LGU / agriculturist sign off.
# =====================================================================================================================
CFG = {
    "nudge_max_m": 10.0,                # the team may move a stake this far from the point (provisional)
    "cell_m": 100.0,                    # a point is the center of a grid cell this wide
    "check_code_len": 8,                # characters of the plan sha256 used as check code
    "code_letters": 3,                  # species code length
    "min_number_digits": 3,             # NAR-001
    "kml_colors": ["e6194B", "3cb44b", "4363d8", "f58231", "911eb4", "42d4f4", "f032e6", "9A6324", "808000", "000075", "469990", "800000"],
    "kml_icon_scale": 1.1,
    "pdf_markers": ["o", "s", "^", "v", "D", "P", "X", "*", "<", ">", "p", "h"],   # one shape per species (works in black and white)
    "pdf_page_inches": (11.69, 8.27),   # A4 landscape
    "pdf_rows_per_page": 26,
    "pdf_label_fontsize": 5.5,
    "pdf_marker_size": 22,
    "pdf_block_rows_per_page": 9,       # block table rows per page
    "pdf_overview_margin_m": 300.0,     # overview map margin around the blocks
    "pdf_block_window_m": 300.0,        # local map window of a block page
    "pdf_margin_m": 500.0,              # map margin around the planned points
    "pdf_scale_bar_options_m": [100, 200, 500, 1000, 2000, 5000],
    "pdf_scale_bar_target_fraction": 0.22,
    "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "site_crs": "EPSG:32651",           # UTM 51N, the CRS of utm_e / utm_n
    "barangay_shp": "data/BRGY_BOUNDARY.shp",
    "landuse_shp": "data/LandUses.shp",
    "gps_accuracy_text": "a few metres in the open, and worse under tree cover, near buildings or in a gully",
}
FLAG_NOTES = {
    "needs_both_sexes": "Dioecious species: plant both male and female trees of this species near each other.",
    "soil_unverified_mismatch": "Soil texture of this cell is unverified and may not suit the species: check the soil on site.",
    "species_data_unverified": "The species data for this tree cites a source file that was not provided.",
    "low_confidence": "Some inputs for this point were missing, so the suitability score is less certain.",
    "barangay_nearest": "The point is outside every barangay polygon; the nearest barangay is listed.",
    "zoning_unconfirmed": "Land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting.",
    "soil_provisional": "Soil from the LGU soil map, digitized by us: provisional.",
    "ground_bare": "Satellite land cover (2021) looks bare: check on the ground before planting.",
    "rehab_site_food_warning": "Fruit or produce from a landfill or mining site may hold heavy metals; do not plan to eat or sell it without testing.",
    "habagat_washout": "Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep.",
    "slope_graded": "Slope is steeper than this tree's usual limit. Plant on terraces or use contour planting, or choose another tree.",
    "ground_built_up": "Satellite land cover (2021) looks built-up: check on the ground before planting.",
    "ground_water": "Satellite land cover (2021) looks like water or wetland: check on the ground before planting.",
}
PLAIN_WARNINGS = {
    "slope_graded": "Slope is steeper than this tree's usual limit. Plant on terraces or use contour planting, or choose another tree.",
    "soil_provisional": "Soil from the LGU soil map (provisional)",
    "ground_built_up": "Looks built-up in the satellite land cover: check on the ground first",
    "ground_bare": "Looks bare in the satellite land cover: check on the ground first",
    "ground_water": "Looks like water in the satellite land cover: check on the ground first",
    "zoning_unconfirmed": "Outside our zoning map: Forest Reserve, coordinate with MENRO and DENR",
    "needs_both_sexes": "Separate sexes: plant both",
    "soil_unverified_mismatch": "Soil may not suit the species: check on site",
    "species_data_unverified": "Species data cites a file we do not have",
    "low_confidence": "Some inputs were missing: less certain score",
    "barangay_nearest": "Outside every barangay outline: nearest one listed",
    "rehab_site_food_warning": "Fruit or produce from a landfill or mining site may hold heavy metals; do not plan to eat or sell it without testing",
    "habagat_washout": "Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep",
}
GROUND_WARN = ("ground_built_up", "ground_bare", "ground_water")
# =====================================================================================================================

CSV_COLUMNS = ["point_ref", "point_id", "species_code", "common_name", "scientific_name", "lat", "lon", "utm_e", "utm_n", "barangay",
               "zone", "spacing_min_m", "planting_months", "flags", "notes", "plan_id", "check_code", "status", "moved_lat", "moved_lon"]
GPX_NS, KML_NS = "http://www.topografix.com/GPX/1/1", "http://www.opengis.net/kml/2.2"
KIT_FILES = ["points.gpx", "points.kml", "point-list.csv", "README.txt"]
BLOCK_CSV_COLUMNS = ["block_ref", "point_id", "lat", "lon", "utm_e", "utm_n", "species_code", "common_name", "trees_planned", "spacing_m", "rows", "trees_per_row", "row_direction",
                     "start_corner", "barangay", "zone", "flags", "notes", "status", "trees_planted", "moved_lat", "moved_lon", "plan_id", "check_code",
                     "start_lat", "start_lon", "start_utm_e", "start_utm_n", "first_tree_lat", "first_tree_lon", "rect_side_m", "margin_m"]   # plan_id and check_code tie a filled file to its plan; the round 13 columns are only appended


def plain_warnings(flags):
    """Flag codes -> plain words (unknown flags are kept as written, never dropped)."""
    out = []
    for f in (flags or "").split(";"):
        f = f.strip()
        if f:
            out.append(PLAIN_WARNINGS.get(f, f.replace("_", " ")))
    return out


def _abs(p):
    """Paths in CFG are relative to the repo root."""
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def safe_name(text, max_len=80):
    """File-name safe version of a text (letters, digits, dot, dash, underscore)."""
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._-")
    return (s or "plan")[:max_len]


def check_code(plan_csv_path, n=None):
    return hashlib.sha256(Path(plan_csv_path).read_bytes()).hexdigest()[:CFG["check_code_len"] if n is None else n]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_codes(species_rows):
    """{species_id: code}: 3 uppercase letters from the common name, unique; a clash gets two letters + a digit (2..9), then a letter + 2 digits."""
    used, out = set(), {}
    for sid, name in sorted(species_rows):
        ascii_name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().upper()
        base = (re.sub(r"[^A-Z]", "", ascii_name) + "X" * CFG["code_letters"])[:CFG["code_letters"]]
        code = base
        if code in used:
            cands = [base[:2] + str(d) for d in range(2, 10)] + [base[0] + f"{k:02d}" for k in range(10, 100)]
            code = next(c for c in cands if c not in used)
        used.add(code); out[sid] = code
    return out


def is_blocks(plan):
    """A plan made in blocks mode has the column trees_planned (one row = one block)."""
    return "trees_planned" in plan.columns


def make_refs(codes, blocks=False):
    """References of a Series of species codes already sorted by (code, point_id): DUH-012 for points, DUH-B03 for blocks (the number counts per species)."""
    n = codes.groupby(codes).cumcount() + 1
    top = int(codes.groupby(codes).size().max())
    if blocks:
        return codes + "-B" + n.astype(str).str.zfill(max(2, len(str(top))))
    return codes + "-" + n.astype(str).str.zfill(max(CFG["min_number_digits"], len(str(top))))


def fmt_m(v):
    return f"{float(v):g}" if abs(float(v) - round(float(v))) < 1e-9 else f"{float(v):.2f}".rstrip("0").rstrip(".")


def block_text(r):
    """The layout of one block in plain words (GPX / KML description)."""
    n, cap, tpr, rows = int(r.trees_planned), int(r.capacity), int(r.trees_per_row), int(r.rows)
    side, mg, sp = float(r.rect_side_m), float(r.margin_m), float(r.spacing_m)
    s = (f"Block {r.point_ref}: {n} {r.common_name} trees at {fmt_m(sp)} m spacing. Layout: {rows} rows of {tpr} trees (capacity {cap}). "
         f"Planted area {fmt_m(side)} m x {fmt_m(side)} m in the middle of the 100 m square, {fmt_m(mg)} m from each edge. "
         f"Start at the START corner (south-west corner of the planted area); tree 1 is {fmt_m(sp / 2)} m east and {fmt_m(sp / 2)} m north of it. "
         f"Rows run {r.row_direction}: plant trees 1 to {n} row by row, east first, then one spacing north for the next row.")
    if n < cap:
        s += f" This block holds {n} of {cap} trees: leave the rest empty."
    if isinstance(r.layout_note, str) and r.layout_note:
        s += f" {r.layout_note}."
    return s


def block_note_short(r):
    n = int(r.trees_planned)
    return (f"Block of {n} trees: {int(r.rows)} rows x {int(r.trees_per_row)} at {fmt_m(r.spacing_m)} m, planted area {fmt_m(r.rect_side_m)} m square centred ({fmt_m(r.margin_m)} m margin), "
            f"start {r.start_corner} corner of it, rows {r.row_direction}."
            + (f" {r.layout_note}." if isinstance(r.layout_note, str) and r.layout_note else ""))


def month_names(value):
    if value is None or (isinstance(value, float) and np.isnan(value)) or str(value).strip() == "":
        return ""
    return ";".join(CFG["months"][int(m) - 1] for m in str(value).replace(",", ";").split(";") if m.strip())


def dataset_info(data_dir):
    """Release tag and the combined 12-character hash, read from dataset_release.txt (never the long sha256); falls back to the database row."""
    f = Path(data_dir) / "dataset_release.txt"
    if f.exists():
        txt = f.read_text(encoding="utf-8")
        t = re.search(r"dataset release (\S+)", txt)
        h = re.search(r"combined hash[^:]*:\s*([0-9a-f]{12})", txt)
        if t and h:
            return {"tag": t.group(1), "hash": h.group(1)}
    db = Path(data_dir) / "optimizing_survival.db"
    try:
        con = sqlite3.connect(db)
        row = con.execute("SELECT tag, combined_hash12 FROM dataset_versions ORDER BY dataset_version_id DESC LIMIT 1").fetchone()
        con.close()
        if row and row[1]:
            return {"tag": row[0], "hash": row[1]}
    except sqlite3.Error:
        pass
    return {"tag": "unknown", "hash": "unknown"}


def assign_barangay(df, shp):
    """Barangay per point by spatial join; a point outside every polygon gets the nearest one and the flag barangay_nearest."""
    import geopandas as gpd
    b = fix_barangay_column(gpd.read_file(_abs(shp))[["BRGY_NAME", "geometry"]]).sort_values("BRGY_NAME").reset_index(drop=True)
    pts = gpd.GeoDataFrame({"i": np.arange(len(df))}, geometry=gpd.points_from_xy(df.lon, df.lat), crs=b.crs)
    j = gpd.sjoin(pts, b, how="left", predicate="intersects").drop_duplicates("i", keep="first").set_index("i").BRGY_NAME.reindex(range(len(df)))
    names, nearest = j.to_numpy(dtype=object), np.zeros(len(df), dtype=bool)
    miss = pd.isna(j).to_numpy()
    if miss.any():
        pm, bm = pts[miss].to_crs(CFG["site_crs"]), b.to_crs(CFG["site_crs"])
        nn = gpd.sjoin_nearest(pm, bm, how="left").drop_duplicates("i", keep="first").set_index("i").BRGY_NAME
        for i in np.where(miss)[0]:
            names[i] = nn.loc[i]; nearest[i] = True
    return names, nearest


def flag_notes(flags, zone):
    """The note text of a flag list. zoning_unconfirmed names the zone when the square lies in a named zone the LGU has not cleared (see ZONE_RULES in rebuild_site_grid.py)."""
    out = []
    for f in flags.split(";"):
        if f == "zoning_unconfirmed" and zone:
            out.append(f"{zone}: confirm with the LGU before planting.")
        elif f in FLAG_NOTES:
            out.append(FLAG_NOTES[f])
    return " ".join(out)


def attach_geometry(df):
    """Blocks only: the planted rectangle of every block from the ONE shared function (palettes.block_geometry), with lat/lon of its corners and of tree 1.
    Local metres are from the south-west corner of the 100 m square; the square centre is (utm_e, utm_n); the grid is assumed aligned to UTM north."""
    from pyproj import Transformer
    tr = Transformer.from_crs(CFG["site_crs"], "EPSG:4326", always_xy=True)
    geos = []
    for r in df.itertuples(index=False):
        g = pal.block_geometry(float(r.spacing_m), int(r.trees_per_row), int(r.rows), int(r.trees_planned))
        half = g["side_m"] / 2.0
        def ll(x, y):
            lon, lat = tr.transform(float(r.utm_e) - half + x, float(r.utm_n) - half + y)
            return lat, lon
        g["ll"] = {k: ll(*v) for k, v in g["corners"].items()}
        g["first_ll"] = ll(*g["first_tree"])
        g["utm_sw"] = (float(r.utm_e) - half + g["corners"]["SW"][0], float(r.utm_n) - half + g["corners"]["SW"][1])
        geos.append(g)
    df["geo"] = geos
    df["start_lat"] = [f"{g['ll']['SW'][0]:.6f}" for g in geos]
    df["start_lon"] = [f"{g['ll']['SW'][1]:.6f}" for g in geos]
    df["start_utm_e"] = [f"{g['utm_sw'][0]:.1f}" for g in geos]
    df["start_utm_n"] = [f"{g['utm_sw'][1]:.1f}" for g in geos]
    df["first_tree_lat"] = [f"{g['first_ll'][0]:.6f}" for g in geos]
    df["first_tree_lon"] = [f"{g['first_ll'][1]:.6f}" for g in geos]
    df["rect_side_m"] = [fmt_m(g["rect_side_m"]) for g in geos]
    df["margin_m"] = [fmt_m(g["margin_m"]) for g in geos]
    return df


def build_point_table(plan, species, code_by_id, plan_id, check, brgy_shp, conditions=None):
    """One row per planned point with every CSV column; ordered by species code then grid point id."""
    sp = species.set_index("species_id")
    missing = set(plan.species_id) - set(sp.index)
    if missing:
        raise ValueError(f"species_id {sorted(missing)} of the plan are not in species_clean.csv")
    df = plan.copy()
    df["flags"] = df["flags"].fillna("").astype(str)
    names, nearest = assign_barangay(df, brgy_shp)
    df["barangay"] = names
    df["flags"] = [";".join(f for f in (fl.split(";") if fl else []) + (["barangay_nearest"] if nr else []) if f) for fl, nr in zip(df["flags"], nearest)]
    df["species_code"] = df.species_id.map(code_by_id)
    df["common_name"] = df.species_id.map(sp.common_name)
    df["scientific_name"] = df.species_id.map(sp.scientific_name)
    df["spacing_min_m"] = df.species_id.map(sp.spacing_min_m)
    df["planting_months"] = df.species_id.map(sp.planting_months).map(month_names)
    df = df.sort_values(["species_code", "point_id"]).reset_index(drop=True)
    blocks = is_blocks(df)
    df["point_ref"] = make_refs(df.species_code, blocks)
    if blocks:
        attach_geometry(df)
    df["zone"] = df.zone_desc.fillna("")
    df["notes"] = [flag_notes(fl, z) for fl, z in zip(df["flags"], df["zone"])]
    if conditions:                                                                  # round 15a: the MPDC condition of the zone (permission needed ...), in plain words, in the notes column
        df["notes"] = [(n + f" Zone condition: {conditions[int(p)]}.").strip() if conditions.get(int(p)) else n for n, p in zip(df["notes"], df["point_id"])]
    if blocks:
        df["block_ref"] = df.point_ref
        df["layout_note"] = df["layout_note"].fillna("")
        df["notes"] = [(block_note_short(r) + " " + n).strip() for r, n in zip(df.itertuples(index=False), df["notes"])]
    df["plan_id"], df["check_code"] = plan_id, check
    df["status"], df["moved_lat"], df["moved_lon"] = "", "", ""
    df["lat_s"], df["lon_s"] = df.lat.map(lambda v: f"{v:.6f}"), df.lon.map(lambda v: f"{v:.6f}")
    return df


def cell_note():
    return (f"The coordinate is the CENTER of a {CFG['cell_m']:.0f} m grid cell. You may move the stake up to {CFG['nudge_max_m']:.0f} m "
            "if the exact spot is a rock, a tree, a creek bank or a path, and must write the real position in moved_lat and moved_lon.")


def describe(r):
    parts = [f"{r.common_name} ({r.scientific_name}).", f"Planting months: {r.planting_months.replace(';', ', ') or 'not stated'}.",
             f"Flags: {r.flags.replace(';', ', ') or 'none'}."]
    if hasattr(r, "trees_planned"):
        parts.insert(0, block_text(r))
    if r.notes:
        parts.append(r.notes)
    parts.append(cell_note())
    return " ".join(parts)


def stamp_text(meta):
    return (f"Plan {meta['plan_id']} | check code {meta['check_code']} | dataset {meta['dataset_tag']} hash {meta['dataset_hash']} | "
            f"built {meta['built_on']}")


# ---------------------------------------------------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------------------------------------------------
def _write_xml(root, path):
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_gpx(df, meta, path):
    ET.register_namespace("", GPX_NS)
    q = lambda t: f"{{{GPX_NS}}}{t}"
    root = ET.Element(q("gpx"), {"version": "1.1", "creator": "Optimizing Survival field_kit.py"})
    md = ET.SubElement(root, q("metadata"))
    ET.SubElement(md, q("name")).text = f"{meta['plan_id']} (check {meta['check_code']})"
    ET.SubElement(md, q("desc")).text = f"{stamp_text(meta)}. {cell_note()}"
    ET.SubElement(md, q("time")).text = f"{meta['built_on']}T00:00:00Z"
    ET.SubElement(md, q("keywords")).text = f"plan:{meta['plan_id']}; check:{meta['check_code']}; dataset:{meta['dataset_hash']}"
    for r in df.itertuples(index=False):
        w = ET.SubElement(root, q("wpt"), {"lat": r.lat_s, "lon": r.lon_s})
        ET.SubElement(w, q("name")).text = r.point_ref
        ET.SubElement(w, q("desc")).text = describe(r)
        ET.SubElement(w, q("type")).text = r.species_code
        if hasattr(r, "geo"):
            sw, se, ne, nw = (r.geo["ll"][k] for k in ("SW", "SE", "NE", "NW"))
            for suffix, (la, lo), text in (
                    ("START", sw, f"START of block {r.point_ref}: south-west corner of the planted area ({fmt_m(r.rect_side_m)} m square, {fmt_m(r.margin_m)} m inside the grid square). "
                                  f"Put a stake here and plant tree 1 {fmt_m(r.geo['spacing_m'] / 2)} m east and north of it. Then walk east along the row."),
                    ("SE", se, f"South-east corner of the planted area of block {r.point_ref}: end of the first side ({fmt_m(r.rect_side_m)} m east of START). Use it to line up the rows."),
                    ("NE", ne, f"North-east corner of the planted area of block {r.point_ref}. Use it to check the square: {fmt_m(r.rect_side_m)} m north of the SE corner."),
                    ("NW", nw, f"North-west corner of the planted area of block {r.point_ref}: {fmt_m(r.rect_side_m)} m north of START. Use it to line up the rows.")):
                c = ET.SubElement(root, q("wpt"), {"lat": f"{la:.6f}", "lon": f"{lo:.6f}"})
                ET.SubElement(c, q("name")).text = f"{r.point_ref}-{suffix}"
                ET.SubElement(c, q("desc")).text = text + " GPS is good to a few metres and worse under trees; the square is a map cell, not an exact planting spot."
                ET.SubElement(c, q("type")).text = r.species_code
    _write_xml(root, path)


def kml_color(hex_rgb):
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"ff{b}{g}{r}"                                            # KML is aabbggrr


def write_kml(df, meta, path, color_by_code):
    ET.register_namespace("", KML_NS)
    q = lambda t: f"{{{KML_NS}}}{t}"
    root = ET.Element(q("kml"))
    doc = ET.SubElement(root, q("Document"))
    ET.SubElement(doc, q("name")).text = f"{meta['plan_id']} (check {meta['check_code']})"
    ET.SubElement(doc, q("description")).text = f"{stamp_text(meta)}. {cell_note()}"
    for code, col in color_by_code.items():
        st = ET.SubElement(doc, q("Style"), {"id": f"s_{code}"})
        ic = ET.SubElement(st, q("IconStyle"))
        ET.SubElement(ic, q("color")).text = kml_color(col)
        ET.SubElement(ic, q("scale")).text = str(CFG["kml_icon_scale"])
        ET.SubElement(ET.SubElement(st, q("LabelStyle")), q("color")).text = kml_color(col)
        ps = ET.SubElement(doc, q("Style"), {"id": f"p_{code}"})
        ET.SubElement(ET.SubElement(ps, q("LineStyle")), q("color")).text = kml_color(col)
        ET.SubElement(ET.SubElement(ps, q("PolyStyle")), q("color")).text = "66" + kml_color(col)[2:]    # semi-transparent fill, the species colour
    for code, g in df.groupby("species_code", sort=True):
        f = ET.SubElement(doc, q("Folder"))
        ET.SubElement(f, q("name")).text = f"{code} - {g.common_name.iloc[0]} ({len(g)})"
        for r in g.itertuples(index=False):
            p = ET.SubElement(f, q("Placemark"))
            ET.SubElement(p, q("name")).text = r.point_ref
            ET.SubElement(p, q("description")).text = describe(r)
            ET.SubElement(p, q("styleUrl")).text = f"#s_{code}"
            ET.SubElement(ET.SubElement(p, q("Point")), q("coordinates")).text = f"{r.lon_s},{r.lat_s},0"
            if hasattr(r, "geo"):
                pa = ET.SubElement(f, q("Placemark"))
                ET.SubElement(pa, q("name")).text = f"{r.point_ref} planted area"
                ET.SubElement(pa, q("description")).text = (f"Planted area of block {r.point_ref}: {fmt_m(r.rect_side_m)} m x {fmt_m(r.rect_side_m)} m, centred in the 100 m square "
                                                            f"({fmt_m(r.margin_m)} m margin). {r.trees_planned} trees of {r.capacity}.")
                ET.SubElement(pa, q("styleUrl")).text = f"#p_{code}"
                ring = [r.geo["ll"][k] for k in ("SW", "SE", "NE", "NW", "SW")]
                ET.SubElement(ET.SubElement(ET.SubElement(ET.SubElement(pa, q("Polygon")), q("outerBoundaryIs")), q("LinearRing")), q("coordinates")).text =                     " ".join(f"{lo:.6f},{la:.6f},0" for la, lo in ring)
                st_ = ET.SubElement(f, q("Placemark"))
                ET.SubElement(st_, q("name")).text = f"{r.point_ref} START"
                ET.SubElement(st_, q("description")).text = f"START corner of block {r.point_ref}: south-west corner of the planted area. Tree 1 is {fmt_m(r.geo['spacing_m'] / 2)} m east and north of it."
                ET.SubElement(st_, q("styleUrl")).text = f"#s_{code}"
                ET.SubElement(ET.SubElement(st_, q("Point")), q("coordinates")).text = f"{r.start_lon},{r.start_lat},0"
    _write_xml(root, path)


def write_csv(df, path):
    out = df[CSV_COLUMNS].copy()
    out["lat"], out["lon"] = df.lat_s, df.lon_s
    out["utm_e"], out["utm_n"] = df.utm_e.round(1), df.utm_n.round(1)
    out.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")


def write_blocks_csv(df, path):
    """blocks.csv: one row per block, with the columns the volunteers fill (status, trees_planted, moved_lat, moved_lon)."""
    out = df.copy()
    out["lat"], out["lon"] = df.lat_s, df.lon_s
    out["utm_e"], out["utm_n"] = df.utm_e.round(1), df.utm_n.round(1)
    out["spacing_m"] = df.spacing_m.map(lambda v: f"{float(v):g}")
    out["trees_planted"] = ""
    out[BLOCK_CSV_COLUMNS].to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")


def palette_rows(df):
    if "trees_planned" in df.columns:                                  # blocks: the number is trees, not rows
        g = df.groupby(["species_code", "common_name"], sort=True).trees_planned.sum().reset_index(name="n")
        dio = set(df[df["flags"].str.contains("needs_both_sexes")].species_code)
        return [(r.species_code, r.common_name, int(r.n), r.species_code in dio) for r in g.itertuples(index=False)]
    g = df.groupby(["species_code", "common_name"], sort=True).size().reset_index(name="n")
    dio = set(df[df["flags"].str.contains("needs_both_sexes")].species_code)
    return [(r.species_code, r.common_name, int(r.n), r.species_code in dio) for r in g.itertuples(index=False)]


def write_readme_blocks(df, meta, summary, path):
    pal = "\n".join(f"  {c}  {n:<26} {k:>4} trees{'   <- plant BOTH male and female trees' if d else ''}" for c, n, k, d in palette_rows(df))
    limits = "\n".join(f"  - {x}" for x in summary.get("limits", []))
    s = summary
    lay = s.get("layout", {})
    ex = df.drop_duplicates("species_code")
    spec = "\n".join(f"  {r.species_code}  {r.common_name:<26} every {float(r.spacing_m):g} m, {int(r.rows)} rows of {int(r.trees_per_row)} trees = {int(r.capacity)} trees in a full block"
                      for r in ex.itertuples(index=False))
    extra = []
    if s.get("saplings_unmatched") or s.get("saplings_unallocated"):
        extra.append(f"  - The plan could not place every tree: {s.get('saplings_unmatched', 0)} unmatched and {s.get('saplings_unallocated', 0)} not allocated (see manifest.json).")
    extra.append(f"  - Existing trees: {s.get('existing_trees', 'not stated')}.")
    first = df.point_ref.iloc[0]
    ex0 = df.iloc[0]
    txt = f"""FIELD KIT (PLANTING BLOCKS) - {meta['plan_id']}
{'=' * 78}
Plan id      : {meta['plan_id']}
Check code   : {meta['check_code']}   (first {CFG['check_code_len']} characters of the sha256 of the plan CSV;
               if the plan changes, the code changes. Only use files with the same code.)
Dataset      : {meta['dataset_tag']}   hash {meta['dataset_hash']}
Built on     : {meta['built_on']}      Purpose: {s.get('purpose', '?')}
Trees        : {int(df.trees_planned.sum())} trees in {len(df)} blocks (about {lay.get('hectares_used', len(df))} ha of planting squares)

WHAT IS IN THIS KIT
  points.gpx      one waypoint per BLOCK for a phone map app     blocks.csv      the sheet to fill in the field (open in Excel)
  points.kml      same blocks, one folder per species             point-list.csv  the same blocks in the older sheet format
  field-map.pdf   printed map, one page per block, table (only if made)     manifest.json   every file with its size and sha256

WHAT IS A BLOCK
  A block is one 100 m x 100 m grid square planted at the species spacing, so that many trees stand close together. The planted area is a square of
  (trees per row x spacing) metres on each side, CENTRED in the grid square, so the same margin is left on all four sides for paths, boundaries and rocks.
  For {ex0.species_code} that is {fmt_m(ex0.rect_side_m)} m x {fmt_m(ex0.rect_side_m)} m with a margin of {fmt_m(ex0.margin_m)} m. Each waypoint is named like {first} (species code, B for block, number) and
  is the CENTRE of the grid square. Tap it to read the layout. The corners of the planted area are waypoints too: {first}-START (south-west), -SE, -NE, -NW.

HOW TO LAY OUT A BLOCK (a tape measure or pacing is enough)
  1. Walk to the {first}-START waypoint (or to the block waypoint and then go to the corner). START is the south-west corner of the planted area.
     In blocks.csv the same corner is in start_lat / start_lon; first_tree_lat / first_tree_lon is tree 1. Put a stake at START.
  2. Tree 1 is half a spacing east and half a spacing north of START (for {ex0.species_code}: {fmt_m(float(ex0.spacing_m) / 2)} m each). Trees stand at the CENTRES of the cells of the planted area,
     so the first tree is {fmt_m(float(ex0.margin_m) + float(ex0.spacing_m) / 2)} m from the south and west edges of the grid square.
  3. Rows run east-west (the grid is assumed to be aligned to UTM north: this is an assumption, check it with the compass of the phone). Plant tree 1, then walk east and plant a tree
     every spacing (a tape, a marked rope, or count paces: one adult pace is about 0.75 m, so a spacing of 7.5 m is 10 paces). The row is full after the number of trees per row.
  4. Go north by one spacing and plant the next row from the west end. Number the trees in your head row by row. A block that holds fewer trees than its capacity plants trees
     1 to N in that order, so the last row may be short: leave the rest empty (the printed page of each block shows which).
  5. Use the other corners (SE, NE, NW) to check that the area is square: the sides are the same length. With two tapes or a rope you can set out the corners first and then divide the sides.
  6. If a house, road, creek or an existing tree is in the way, move the tree or the block (up to {CFG['nudge_max_m']:.0f} m) and write the real position in moved_lat and moved_lon. Never plant on paved or built land.
  7. If the notes say "Plant along the contour" (slope above 30%), run the rows along the contour lines instead of straight east-west.
  8. COUNT the trees you really planted in each block (do not count missing or dead saplings) and write the number in blocks.csv.

SPACING AND CAPACITY OF THE SPECIES IN THIS PLAN
{spec}

GPS AND THE 100 m SQUARE
  - GPS accuracy is {CFG['gps_accuracy_text']}: GPS is good to a few metres and worse under trees, and the square is a map cell, not an exact planting spot.
  - The waypoint is the centre of the square, not a surveyed spot. If the planted area meets a rock, a tree, a creek bank or a path, you may shift the block by up to
    {CFG['nudge_max_m']:.0f} m. Write the REAL position of the block's centre in moved_lat and moved_lon (decimal degrees, from the phone).
  - Dioecious species need BOTH sexes: plant male and female trees of that species in the same block.
  - Plant only in the planting months listed for the species.
  - A block flagged zoning_unconfirmed is on land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting there.
  - The flag soil_provisional means the soil of the block comes from the LGU soil map, digitized by us: provisional, not yet verified by the agriculturist.
  - A block flagged ground_bare, ground_built_up or ground_water looks bare, built-up or like water in satellite land cover (ESA WorldCover 2021, 76.7% accurate worldwide): check it on the ground first.

BRINGING THE RESULTS BACK
  When you are done, fill blocks.csv: write "planted" in the status column and the number of trees you planted in trees_planted (from 0 up to trees_planned; fewer trees means the
  block is only partly done). For a block that cannot be planted write the reason in status (paved, building, rock_or_ledge, creek_or_waterlogged, too_steep, existing_tree,
  owner_refused or other). If you moved the block, also fill moved_lat and moved_lon. Then open the dashboard, type your name, and press "Import field checks (CSV)" and choose
  blocks.csv. The plan id and the check code in the file must match this kit, or it is refused. Importing the same file twice adds nothing. (point-list.csv works too: "planted"
  means all the trees of the block.)

SPECIES CODES AND TREES
{pal}

KNOWN LIMITS (from the plan)
{limits}
{chr(10).join(extra)}
"""
    Path(path).write_text(txt, encoding="utf-8")


def write_readme(df, meta, summary, path):
    if "trees_planned" in df.columns:
        return write_readme_blocks(df, meta, summary, path)
    pal = "\n".join(f"  {c}  {n:<26} {k:>4} trees{'   <- plant BOTH male and female trees' if d else ''}" for c, n, k, d in palette_rows(df))
    limits = "\n".join(f"  - {x}" for x in summary.get("limits", []))
    s = summary
    extra = []
    if s.get("saplings_unmatched") or s.get("saplings_unallocated"):
        extra.append(f"  - The plan could not place every sapling: {s.get('saplings_unmatched', 0)} unmatched and "
                     f"{s.get('saplings_unallocated', 0)} not allocated (see manifest.json).")
    extra.append(f"  - Existing trees: {s.get('existing_trees', 'not stated')}.")
    txt = f"""FIELD KIT - {meta['plan_id']}
{'=' * 78}
Plan id      : {meta['plan_id']}
Check code   : {meta['check_code']}   (first {CFG['check_code_len']} characters of the sha256 of the plan CSV;
               if the plan changes, the code changes. Only use files with the same code.)
Dataset      : {meta['dataset_tag']}   hash {meta['dataset_hash']}
Built on     : {meta['built_on']}      Purpose: {s.get('purpose', '?')}      Points: {len(df)}

WHAT IS IN THIS KIT
  points.gpx      waypoints for a phone map app      point-list.csv  the tick-sheet (open in Excel)
  points.kml      same points, one folder per species   field-map.pdf   printed map (only if made)
  manifest.json   every file with its size and sha256

HOW TO USE THE POINTS ON A PHONE (works without signal)
  1. Before going out, with internet: copy points.gpx (or points.kml) to the phone and open it
     with an offline map app (for example OsmAnd, Organic Maps or Gaia GPS). Download the map
     area of San Mateo, Rizal inside that app. Test it once in airplane mode.
  2. Each waypoint is named like {df.point_ref.iloc[0]} (species code + number). Tap it to read the common name,
     planting months and any flags. Use "navigate to" or the compass arrow to walk to it.
  3. Find the same point in point-list.csv by its point_ref. Tick the status column when the tree
     is planted.

GPS AND THE 100 m CELL
  - GPS accuracy is {CFG['gps_accuracy_text']}.
  - Each point is the CENTER of a {CFG['cell_m']:.0f} m grid cell, not a surveyed spot. If the exact spot is a rock, a
    tree, a creek bank or a path, you may move the stake up to {CFG['nudge_max_m']:.0f} m. Write the REAL position of the
    stake in moved_lat and moved_lon (decimal degrees, from the phone) in point-list.csv.
  - Dioecious species need BOTH sexes: plant male and female trees near each other.
  - Plant only in the planting months listed for the species.
  - A point flagged zoning_unconfirmed is on land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting there.
  - The flag soil_provisional means the soil of the point comes from the LGU soil map, digitized by us: provisional, not yet verified by the agriculturist.
  - A point flagged ground_bare, ground_built_up or ground_water looks bare, built-up or like water in satellite land cover (ESA WorldCover 2021, 76.7% accurate worldwide): check it on the ground first.

BRINGING THE RESULTS BACK
  When you are done, fill the status column of point-list.csv: write "planted" for a spot you planted,
  or the reason (paved, building, rock_or_ledge, creek_or_waterlogged, too_steep, existing_tree,
  owner_refused or other) for a spot that cannot be planted; "not plantable" alone is saved as
  "other". If you moved the stake, also fill moved_lat and moved_lon. Then open the dashboard, type your name, and press "Import field checks
  (CSV)". The plan id and the check code at the top of this file must match the ones in the file you
  import, or it is refused. Importing the same file twice adds nothing.

SPECIES CODES
{pal}

KNOWN LIMITS (from the plan)
{limits}
{chr(10).join(extra)}
"""
    Path(path).write_text(txt, encoding="utf-8")


def write_manifest(kit_dir, df, meta, summary, plan_csv, path):
    files = []
    for p in sorted(Path(kit_dir).iterdir()):
        if p.name != "manifest.json" and p.is_file():
            files.append({"name": p.name, "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    per = {c: {"common_name": n, "points": k, "needs_both_sexes": d} for c, n, k, d in palette_rows(df)}
    if "trees_planned" in df.columns:
        per = {c: {"common_name": n, "trees": k, "blocks": int((df.species_code == c).sum()), "points": int((df.species_code == c).sum()), "needs_both_sexes": d} for c, n, k, d in palette_rows(df)}
    m = {"plan_id": meta["plan_id"], "check_code": meta["check_code"], "built_on": meta["built_on"],
         "dataset": {"tag": meta["dataset_tag"], "hash": meta["dataset_hash"]},
         "plan_file": {"name": Path(plan_csv).name, "sha256": sha256_file(plan_csv)},
         "counts": {"points": int(len(df)), "species": len(per), "per_species": per,
                    **({"blocks": int(len(df)), "trees": int(df.trees_planned.sum())} if "trees_planned" in df.columns else {})},
         "files": files, "nudge_max_m": CFG["nudge_max_m"], "cell_m": CFG["cell_m"],
         "limits": summary.get("limits", []), "plan_summary": summary,
         "note": "manifest.json lists every other file of the kit; it cannot list its own hash."}
    Path(path).write_text(json.dumps(m, indent=2, default=str), encoding="utf-8")
    return m


# ---------------------------------------------------------------------------------------------------------------------
# field-map.pdf for blocks (round 13): overview to scale, one page per block, table
# ---------------------------------------------------------------------------------------------------------------------
GROUND_STYLE = {   # class group -> (label, face colour, hatch); the hatch keeps the meaning in a black-and-white print
    "tree": ("Trees", "#dcebd0", ""),
    "built": ("Built-up", "#d6d6d6", "///"),
    "bare": ("Bare or sparse", "#efe0bb", "..."),
    "water": ("Water", "#c9def0", "xx"),
    "other": ("Grass, crop, other", "#fbfaf3", ""),
}
GROUND_GROUP = {"tree cover": "tree", "built-up": "built", "bare or sparse vegetation": "bare", "permanent water": "water", "herbaceous wetland": "water", "mangroves": "water"}


def ground_squares(data_dir):
    """Grid squares with their dominant satellite ground class (None when the files are missing: the page then says so)."""
    try:
        d = Path(data_dir)
        pts = pd.read_csv(d / "site_points_clean.csv", usecols=["point_id", "utm_e", "utm_n"])
        lc = pd.read_csv(d / "site_landcover.csv", usecols=["point_id", "dominant_class"])
        m = pts.merge(lc, on="point_id", how="left")
        m["group"] = m.dominant_class.map(lambda v: GROUND_GROUP.get(v, "other") if isinstance(v, str) else "")
        return m
    except Exception:
        return None


def _lum(hexrgb):
    r, g, b = (int(hexrgb[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _draw_cover(ax, plt, sq, x0, x1, y0, y1):
    from matplotlib.collections import PatchCollection
    if sq is None:
        return False
    w = sq[(sq.utm_e > x0 - 100) & (sq.utm_e < x1 + 100) & (sq.utm_n > y0 - 100) & (sq.utm_n < y1 + 100) & (sq.group != "")]
    for grp, (label, fc, hatch) in GROUND_STYLE.items():
        g = w[w.group == grp]
        if g.empty:
            continue
        patches = [plt.Rectangle((e - 50, n - 50), 100, 100) for e, n in zip(g.utm_e, g.utm_n)]
        ax.add_collection(PatchCollection(patches, facecolor=fc, edgecolor=(0, 0, 0, 0.10), linewidth=0.3, hatch=hatch or None, zorder=1))
    return True


def _cover_legend(ax, plt, has_cover, loc="lower left"):
    from matplotlib.patches import Patch
    if not has_cover:
        ax.text(0.01, 0.01, "Ground cover not available", transform=ax.transAxes, fontsize=6, color="0.4")
        return
    hs = [Patch(facecolor=fc, edgecolor="0.5", hatch=h or None, linewidth=0.4, label=lab) for lab, fc, h in GROUND_STYLE.values()]
    leg = ax.legend(handles=hs, loc=loc, fontsize=5.5, title="Satellite ground cover 2021", title_fontsize=6, framealpha=0.9, borderpad=0.5)
    leg.set_zorder(9)


def _zoning(ax, lu, x0, x1, y0, y1):
    if lu is None:
        return
    try:
        from shapely.geometry import box
        lu[lu.intersects(box(x0, y0, x1, y1))].boundary.plot(ax=ax, color="0.78", linewidth=0.4, zorder=2)
    except Exception:
        pass


def _scalebar(ax, plt, x0, x1, y0, y1, length, pad=0.04):
    bx, by, h = x1 - (x1 - x0) * pad - length, y0 + (y1 - y0) * pad, (y1 - y0) * 0.012
    for k in range(4):
        ax.add_patch(plt.Rectangle((bx + k * length / 4, by), length / 4, h, facecolor="black" if k % 2 == 0 else "white", edgecolor="black", linewidth=0.5, zorder=8))
    ax.text(bx, by + h * 1.6, f"{length:g} m" if length < 1000 else f"{length / 1000:g} km", fontsize=6, zorder=8)


def _north(ax):
    ax.annotate("", xy=(0.94, 0.95), xytext=(0.94, 0.86), xycoords="axes fraction", arrowprops={"arrowstyle": "-|>", "color": "black", "lw": 1.3}, zorder=9)
    ax.text(0.94, 0.965, "N", transform=ax.transAxes, ha="center", fontsize=9, weight="bold", zorder=9)


def draw_status_key(ax, x, y, dy=0.045, fontsize=7, horizontal=False, dx=0.16, title=True, per_row=6):
    """The key of the field-check statuses, drawn with the SAME colours and icons as the dashboard (pipeline/field_status.py reads frontend/src/new/fieldStatus.json):
    planted = green disc with a check, plantable (verified) = green ring, needs recheck = amber disc with a question mark, not plantable = red cross (blue: water; gray: paved, building, rock).
    ax coordinates are axes fractions; x, y = the first entry."""
    if title:
        ax.text(x, y + dy, "Mark each block in the field", fontsize=fontsize + 1, weight="bold", transform=ax.transAxes)
    for k, cls in enumerate(fst.ORDER):
        spec = fst.CLASSES[cls]
        xx, yy = (x + (k % per_row) * dx, y - (k // per_row) * dy) if horizontal else (x, y - k * dy)
        col = spec["color"]
        shape = spec["shape"]
        if shape == "ring":
            ax.scatter([xx], [yy], s=70, marker="o", facecolors="white", edgecolors=col, linewidths=1.8, transform=ax.transAxes, clip_on=False)
        elif shape in ("check", "question"):
            ax.scatter([xx], [yy], s=80, marker="o", facecolors=col, edgecolors=col, transform=ax.transAxes, clip_on=False)
            ax.text(xx, yy, "\u2713" if shape == "check" else "?", color="white", fontsize=fontsize, ha="center", va="center", weight="bold", transform=ax.transAxes)
        else:
            ax.scatter([xx], [yy], s=70, marker="X", facecolors=col, edgecolors="white", linewidths=0.5, transform=ax.transAxes, clip_on=False)
        ax.text(xx + 0.02, yy, spec["label"], fontsize=fontsize, va="center", color="black", transform=ax.transAxes)


def pdf_footer(fig, meta, page, total):
    fig.text(0.02, 0.015, f"{stamp_text(meta)} | page {page}/{total}", fontsize=6.5)


def block_warning_lines(r):
    return plain_warnings(r.flags)


def block_has_ground_warning(r):
    return any(f in (r.flags or "").split(";") for f in GROUND_WARN)


def write_pdf_blocks(df, meta, summary, path, landuse_shp, data_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    import textwrap
    matplotlib.rcParams["hatch.linewidth"] = 0.3
    matplotlib.rcParams["hatch.color"] = "#9a9a9a"
    c = CFG
    W, H = c["pdf_page_inches"]
    codes = sorted(df.species_code.unique())
    colour = {code: "#" + c["kml_colors"][i % len(c["kml_colors"])] for i, code in enumerate(codes)}
    sq = ground_squares(data_dir)
    try:
        import geopandas as gpd
        lu = gpd.read_file(_abs(landuse_shp)).to_crs(c["site_crs"])
    except Exception:
        lu = None
    rows = list(df.itertuples(index=False))
    per = c["pdf_block_rows_per_page"]
    # table pages: a row is as tall as its wrapped warning text (round 15c: long warnings used to run into the next row); at most `per` rows or the free height of the page
    wrap_w, line_h, pad_h, free_h = 44, 0.0135, 0.014, 0.74
    row_warn = [[textwrap.fill(x, wrap_w) for x in block_warning_lines(r)] for r in rows]
    row_h = [max(3, sum(w.count("\n") + 1 for w in ws)) * line_h + pad_h for ws in row_warn]
    chunks, cur, used = [], [], 0.0
    for k in range(len(rows)):
        if cur and (len(cur) >= per or used + row_h[k] > free_h):
            chunks.append(cur); cur, used = [], 0.0
        cur.append(k); used += row_h[k]
    chunks.append(cur)
    table_pages = max(1, len(chunks))
    total = 1 + len(rows) + table_pages
    nb, nt = len(rows), int(df.trees_planned.sum())
    with PdfPages(path, metadata={"Title": f"Field map {meta['plan_id']}", "Subject": stamp_text(meta)}) as pdf:
        # ---- page 1: overview, every 100 m square and its planted rectangle to scale
        fig = plt.figure(figsize=(W, H))
        ax = fig.add_axes([0.06, 0.09, 0.64, 0.82]); lg = fig.add_axes([0.72, 0.09, 0.26, 0.82]); lg.axis("off")
        m = c["pdf_overview_margin_m"]
        x0, x1 = df.utm_e.min() - 50 - m, df.utm_e.max() + 50 + m
        y0, y1 = df.utm_n.min() - 50 - m, df.utm_n.max() + 50 + m
        ratio = (0.82 * H) / (0.64 * W)                                      # the axes box: height / width
        span = max(x1 - x0, (y1 - y0) / ratio)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x0, x1 = cx - span / 2, cx + span / 2
        y0, y1 = cy - span * ratio / 2, cy + span * ratio / 2
        has = _draw_cover(ax, plt, sq, x0, x1, y0, y1)
        _zoning(ax, lu, x0, x1, y0, y1)
        for r in rows:
            g = r.geo
            ex, ny = float(r.utm_e) - 50, float(r.utm_n) - 50
            ax.add_patch(plt.Rectangle((ex, ny), 100, 100, fill=False, edgecolor="black", linewidth=0.8, zorder=4))
            sx, sy = g["corners"]["SW"]
            ax.add_patch(plt.Rectangle((ex + sx, ny + sy), g["rect_w_m"], g["rect_h_m"], facecolor=colour[r.species_code], alpha=0.75, edgecolor="black", linewidth=0.5, zorder=5))
            ax.plot([ex + sx], [ny + sy], marker="s", color="black", markersize=2.2, zorder=6)
            label = f"{r.point_ref}\n{int(r.trees_planned)} trees"
            if block_has_ground_warning(r):
                label += "\n! check on the ground"
                ax.add_patch(plt.Rectangle((ex - 4, ny - 4), 108, 108, fill=False, edgecolor="#c0392b", linewidth=1.3, linestyle="--", zorder=6))
            ax.text(float(r.utm_e), float(r.utm_n) + 58, label, fontsize=c["pdf_label_fontsize"], ha="center", va="bottom", zorder=7,
                    bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.7})
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
        ax.ticklabel_format(useOffset=False, style="plain"); ax.tick_params(labelsize=6); ax.set_xlabel("UTM 51N easting (m)", fontsize=7); ax.set_ylabel("northing (m)", fontsize=7)
        ax.grid(True, color="0.9", linewidth=0.3, zorder=0)
        length = max((o for o in c["pdf_scale_bar_options_m"] if o <= span * 0.22), default=c["pdf_scale_bar_options_m"][0])
        _scalebar(ax, plt, x0, x1, y0, y1, length)
        _north(ax)
        ax.set_title(f"{nb} block{'s' if nb != 1 else ''}, {nt} trees - {meta['plan_id']}", fontsize=10)
        lg.text(0, 1.0, "Legend", fontsize=9, weight="bold", va="top")
        y = 0.94
        for code, name, n, d in palette_rows(df):
            lg.add_patch(plt.Rectangle((0.0, y - 0.013), 0.05, 0.026, facecolor=colour[code], edgecolor="black", linewidth=0.5, alpha=0.75, transform=lg.transAxes))
            lg.text(0.08, y, f"{code}  {name}  ({n} trees){'  M+F' if d else ''}", fontsize=7.5, va="center", transform=lg.transAxes)
            y -= 0.045
        lg.text(0, y - 0.01, "Black square = the 100 m grid square (a map cell,\nnot an exact planting spot). Coloured rectangle = the\nplanted area. Dot = START corner.\n"
                "Red dashed frame, ! check = the satellite shows built-up,\nbare or water land: check on the ground.\nGrey lines = land-use zone outlines.\nM+F = plant both sexes.", fontsize=6.8, va="top", transform=lg.transAxes)
        lgs = fig.add_axes([0.72, 0.30, 0.26, 0.22]); lgs.axis("off")
        draw_status_key(lgs, 0.02, 0.80, dy=0.14, fontsize=6.5)
        lgc = fig.add_axes([0.72, 0.09, 0.26, 0.2]); lgc.axis("off")
        _cover_legend(lgc, plt, has, loc="center left")
        pdf_footer(fig, meta, 1, total)
        pdf.savefig(fig); plt.close(fig)
        # ---- one page per block
        for bi, r in enumerate(rows, 1):
            g = r.geo
            fig = plt.figure(figsize=(W, H))
            lax = fig.add_axes([0.04, 0.12, 0.44, 0.74])
            win = c["pdf_block_window_m"] / 2
            ex, ny = float(r.utm_e), float(r.utm_n)
            _draw_cover(lax, plt, sq, ex - win, ex + win, ny - win, ny + win)
            _zoning(lax, lu, ex - win, ex + win, ny - win, ny + win)
            lax.add_patch(plt.Rectangle((ex - 50, ny - 50), 100, 100, fill=False, edgecolor="black", linewidth=1.2, zorder=4))
            sx, sy = g["corners"]["SW"]
            lax.add_patch(plt.Rectangle((ex - 50 + sx, ny - 50 + sy), g["rect_w_m"], g["rect_h_m"], facecolor=colour[r.species_code], alpha=0.7, edgecolor="black", linewidth=0.8, zorder=5))
            lax.plot([ex - 50 + sx], [ny - 50 + sy], marker="s", color="black", markersize=6, zorder=7)
            lax.annotate("START", (ex - 50 + sx, ny - 50 + sy), xytext=(-6, -10), textcoords="offset points", fontsize=7, weight="bold", ha="right", zorder=8)
            lax.set_xlim(ex - win, ex + win); lax.set_ylim(ny - win, ny + win); lax.set_aspect("equal")
            lax.ticklabel_format(useOffset=False, style="plain"); lax.tick_params(labelsize=5.5)
            lax.set_xlabel("UTM 51N easting (m)", fontsize=6.5)
            _scalebar(lax, plt, ex - win, ex + win, ny - win, ny + win, 50)
            _north(lax)
            lax.set_title(f"Local map (300 m window) - Brgy. {r.barangay}", fontsize=8.5)
            _cover_legend(lax, plt, sq is not None, loc="upper left")
            # layout diagram
            dax = fig.add_axes([0.53, 0.19, 0.44, 0.55])
            dax.add_patch(plt.Rectangle((0, 0), 100, 100, fill=False, edgecolor="0.2", lw=1.2))
            dax.add_patch(plt.Rectangle((sx, sy), g["rect_w_m"], g["rect_h_m"], facecolor="0.95", edgecolor="0.4", lw=0.8, ls="--"))
            cap, npl = g["capacity"], g["trees_planned"]
            tpr = int(r.trees_per_row)
            size = max(6, min(150, 9000 / max(1, cap) * (g["spacing_m"] / 10)))
            fc = colour[r.species_code]
            txtcol = "white" if _lum(fc[1:]) < 140 else "black"
            numfs = max(3.5, min(8, 90 / max(tpr, 1)))
            for t in g["trees"]:
                if t["planted"]:
                    dax.scatter([t["x"]], [t["y"]], s=size, facecolors=fc, edgecolors="black", linewidths=0.5, zorder=3)
                else:
                    dax.scatter([t["x"]], [t["y"]], s=size, facecolors="white", edgecolors="0.6", linewidths=0.6, zorder=3)
                if cap <= 100 or t["k"] == 1 or (t["k"] - 1) % tpr == 0 or t["k"] == npl:
                    dax.text(t["x"], t["y"], str(t["k"]), fontsize=numfs, ha="center", va="center", zorder=4, color=txtcol if t["planted"] else "0.45")
            dax.plot([sx], [sy], marker="s", color="black", markersize=6, zorder=5)
            dax.annotate("START", (sx, sy), xytext=(-4, -9), textcoords="offset points", fontsize=7, weight="bold", ha="right", zorder=6)
            dax.annotate("", xy=(sx + min(g["rect_w_m"], 3 * g["spacing_m"]), sy - 3.5), xytext=(sx, sy - 3.5), arrowprops={"arrowstyle": "->", "lw": 1.1})
            dax.text(sx + 3.2 * g["spacing_m"], sy - 5.2, "rows run east", fontsize=6.5)
            dax.annotate("", xy=(0, 50), xytext=(sx, 50), arrowprops={"arrowstyle": "<->", "lw": 0.7, "color": "0.3"})
            dax.text(sx / 2, 51.5, f"{fmt_m(g['margin_m'])} m", fontsize=6, ha="center", color="0.3")
            if tpr >= 2:
                t1, t2 = g["trees"][0], g["trees"][1]
                yy = g["rect_h_m"] + sy + 3
                dax.annotate("", xy=(t2["x"], yy), xytext=(t1["x"], yy), arrowprops={"arrowstyle": "<->", "lw": 0.7, "color": "0.3"})
                dax.text((t1["x"] + t2["x"]) / 2, yy + 1.5, f"{fmt_m(g['spacing_m'])} m", fontsize=6, ha="center", color="0.3")
            dax.annotate("", xy=(95, 98), xytext=(95, 90), arrowprops={"arrowstyle": "-|>", "lw": 1.2}); dax.text(95, 99, "N", ha="center", fontsize=8, weight="bold")
            dax.set_xlim(-8, 108); dax.set_ylim(-12, 108); dax.set_aspect("equal"); dax.set_xticks([0, 50, 100]); dax.set_yticks([0, 50, 100]); dax.tick_params(labelsize=6)
            dax.set_xlabel("metres from the south-west corner of the 100 m square", fontsize=6.5)
            dax.set_title(f"Layout - {r.point_ref} {r.common_name}", fontsize=9)
            msg = f"Plant trees 1 to {npl}" + ("" if npl >= cap else f"; leave the rest empty ({cap - npl} empty)") + ". Row by row, east first, then one spacing north."
            fig.text(0.53, 0.105, textwrap.fill(msg, 72), fontsize=8, weight="bold", va="top")
            warn = block_warning_lines(r)
            head = f"{r.point_ref}   {int(r.trees_planned)} trees of {cap}   spacing {fmt_m(g['spacing_m'])} m   {int(r.rows)} rows x {tpr} trees"
            info = [f"Planted area {fmt_m(g['rect_side_m'])} m x {fmt_m(g['rect_side_m'])} m in the middle of the square, margin {fmt_m(g['margin_m'])} m; tree 1 is {fmt_m(g['margin_m'] + g['spacing_m'] / 2)} m from the south and west edges.",
                    f"START (south-west corner): {r.start_lat}, {r.start_lon}    Zone: {str(r.zone)[:40]}"]
            fig.text(0.04, 0.955, head, fontsize=9, weight="bold", va="top")
            fig.text(0.04, 0.925, "\n".join(textwrap.fill(x, 150) for x in info), fontsize=7, va="top")
            fig.text(0.53, 0.865, "\n".join(["Warnings:"] + [textwrap.fill(f"- {x}", 92, subsequent_indent="  ") for x in warn]) if warn else "Warnings: none", fontsize=6.4, va="top", color="#8e2a1c" if warn else "0.3")
            fig.text(0.04, 0.045, "GPS is good to a few metres and worse under trees; the square is a map cell, not an exact planting spot. If a house, road, creek or tree is in the way, move and record it; never plant on paved or built land.",
                     fontsize=6.2, color="0.3")
            pdf_footer(fig, meta, 1 + bi, total)
            pdf.savefig(fig); plt.close(fig)
        # ---- table pages
        cols = [("Ref", 0.02), ("Species", 0.095), ("Trees", 0.225), ("Spacing; rows x per row", 0.27), ("Barangay, zone", 0.385), ("Start corner (lat, lon)", 0.515),
                ("Warnings", 0.63), ("Done", 0.835), ("Planted / moved", 0.875)]
        for pi in range(table_pages):
            chunk = [rows[k] for k in chunks[pi]]
            chunk_idx = chunks[pi]
            fig = plt.figure(figsize=(W, H)); ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
            ax.text(0.02, 0.95, f"Block table - {nb} blocks, {nt} trees - page {pi + 1}/{table_pages}", fontsize=10, weight="bold")
            for name, x in cols:
                ax.text(x, 0.915, name, fontsize=6.5, weight="bold")
            ax.plot([0.02, 0.98], [0.905, 0.905], color="black", lw=0.8)
            y = 0.89
            for r, ki in zip(chunk, chunk_idx):
                step = row_h[ki]
                warn = "\n".join(row_warn[ki]) or "none"
                vals = [r.point_ref, textwrap.fill(r.common_name, 16), f"{int(r.trees_planned)}/{int(r.capacity)}", f"{fmt_m(r.spacing_m)} m; {int(r.rows)} x {int(r.trees_per_row)}",
                        textwrap.fill(f"{r.barangay}, {r.zone}", 22), f"{r.start_lat}\n{r.start_lon}", warn]
                for (name, x), v in zip(cols, vals):
                    ax.text(x, y, v, fontsize=5.8, va="top")
                ax.text(0.84, y, "[   ]", fontsize=7, va="top")
                ax.text(0.875, y, "planted ____", fontsize=6, va="top")
                ax.text(0.875, y - step * 0.32, "moved lat ____", fontsize=5.5, va="top")
                ax.text(0.875, y - step * 0.58, "moved lon ____", fontsize=5.5, va="top")
                ax.plot([0.02, 0.98], [y - step + 0.004, y - step + 0.004], color="0.85", lw=0.4)
                y -= step
            draw_status_key(ax, 0.03, 0.074, fontsize=6.2, horizontal=True, dx=0.30, dy=0.026, title=False, per_row=3)
            ax.text(0.02, 0.100, "Mark each block in the field (same colours and icons as the dashboard):", fontsize=6.5, weight="bold")
            pdf_footer(fig, meta, 1 + nb + pi + 1, total)
            pdf.savefig(fig); plt.close(fig)
    return total


def write_pdf(df, meta, summary, path, landuse_shp, data_dir=None):
    """field-map.pdf, A4 landscape: overview map (shapes + labels, scale bar, north arrow, legend) and the point table."""
    if "trees_planned" in df.columns and "geo" in df.columns:
        return write_pdf_blocks(df, meta, summary, path, landuse_shp, data_dir or "data/processed")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    import geopandas as gpd
    c = CFG
    W, H = c["pdf_page_inches"]
    codes = sorted(df.species_code.unique())
    marker = {code: c["pdf_markers"][i % len(c["pdf_markers"])] for i, code in enumerate(codes)}
    foot = stamp_text(meta)
    x0, x1 = df.utm_e.min() - c["pdf_margin_m"], df.utm_e.max() + c["pdf_margin_m"]
    y0, y1 = df.utm_n.min() - c["pdf_margin_m"], df.utm_n.max() + c["pdf_margin_m"]
    with PdfPages(path, metadata={"Title": f"Field map {meta['plan_id']}", "Subject": foot}) as pdf:
        fig = plt.figure(figsize=(W, H))
        ax = fig.add_axes([0.06, 0.09, 0.64, 0.82]); lg = fig.add_axes([0.72, 0.09, 0.26, 0.82]); lg.axis("off")
        try:
            lu = gpd.read_file(_abs(landuse_shp)).to_crs(c["site_crs"])
            from shapely.geometry import box
            lu = lu[lu.intersects(box(x0, y0, x1, y1))]
            lu.boundary.plot(ax=ax, color="0.55", linewidth=0.5)
            note_zone = "grey lines: land-use zone boundaries"
        except Exception:
            note_zone = "zone outlines unavailable"
        for code in codes:
            g = df[df.species_code == code]
            ax.scatter(g.utm_e, g.utm_n, s=c["pdf_marker_size"], marker=marker[code], facecolors="white", edgecolors="black", linewidths=0.7, zorder=3)
            for r in g.itertuples(index=False):
                ax.annotate(code, (r.utm_e, r.utm_n), xytext=(3, 3), textcoords="offset points", fontsize=c["pdf_label_fontsize"], zorder=4)
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
        ax.ticklabel_format(useOffset=False, style="plain"); ax.tick_params(labelsize=6); ax.set_xlabel("UTM 51N easting (m)", fontsize=7); ax.set_ylabel("northing (m)", fontsize=7)
        ax.grid(True, color="0.88", linewidth=0.4)
        # scale bar
        span = x1 - x0
        length = max((o for o in c["pdf_scale_bar_options_m"] if o <= span * c["pdf_scale_bar_target_fraction"]), default=c["pdf_scale_bar_options_m"][0])
        bx, by, h = x0 + span * 0.03, y0 + (y1 - y0) * 0.04, (y1 - y0) * 0.012
        for k in range(4):
            ax.add_patch(plt.Rectangle((bx + k * length / 4, by), length / 4, h, facecolor="black" if k % 2 == 0 else "white", edgecolor="black", linewidth=0.6, zorder=5))
        ax.text(bx, by + h * 1.8, f"0 .. {length / 1000:g} km" if length >= 1000 else f"0 .. {length} m", fontsize=7, zorder=5)
        # north arrow
        ax.annotate("", xy=(0.95, 0.95), xytext=(0.95, 0.85), xycoords="axes fraction", arrowprops={"arrowstyle": "-|>", "color": "black", "lw": 1.5}, zorder=5)
        ax.text(0.95, 0.965, "N", transform=ax.transAxes, ha="center", fontsize=10, weight="bold")
        ax.set_title(f"Planned points - {meta['plan_id']} ({len(df)} points)", fontsize=10)
        # legend: code -> common name
        lg.text(0, 1.0, "Legend (shape + code)", fontsize=9, weight="bold", va="top")
        dio = {k: d for k, _, _, d in palette_rows(df)}
        y = 0.94
        for code, name, n, d in palette_rows(df):
            lg.scatter([0.03], [y], s=34, marker=marker[code], facecolors="white", edgecolors="black", linewidths=0.8, transform=lg.transAxes, clip_on=False)
            lg.text(0.09, y, f"{code}  {name}  ({n}){'  M+F' if d else ''}", fontsize=7.5, va="center", transform=lg.transAxes)
            y -= 0.045
        lg.text(0, y - 0.02, f"{note_zone}\nM+F = plant both sexes\nEach point = center of a {c['cell_m']:.0f} m cell;\nstake may move up to {c['nudge_max_m']:.0f} m (record it).",
                fontsize=7, va="top", transform=lg.transAxes)
        fig.text(0.02, 0.02, foot, fontsize=6.5)
        pdf.savefig(fig); plt.close(fig)
        # table pages
        rows = list(df.itertuples(index=False))
        per = c["pdf_rows_per_page"]
        pages = [rows[i:i + per] for i in range(0, len(rows), per)] or [[]]
        cols = [("Ref", 0.02), ("Grid id", 0.09), ("Species", 0.15), ("Lat", 0.30), ("Lon", 0.38), ("Barangay", 0.46), ("Zone", 0.60), ("Done", 0.83), ("Moved lat / lon", 0.89)]
        for pi, chunk in enumerate(pages, 1):
            fig = plt.figure(figsize=(W, H)); ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
            ax.text(0.02, 0.95, f"Point table - {meta['plan_id']} - page {pi}/{len(pages)}", fontsize=10, weight="bold")
            for name, x in cols:
                ax.text(x, 0.905, name, fontsize=7, weight="bold", family="monospace")
            ax.plot([0.02, 0.98], [0.895, 0.895], color="black", lw=0.8)
            step = 0.78 / per
            for k, r in enumerate(chunk):
                y = 0.875 - k * step
                vals = [r.point_ref, str(r.point_id), f"{r.species_code} {r.common_name}"[:26], r.lat_s, r.lon_s, str(r.barangay)[:16], str(r.zone)[:44]]
                for (name, x), v in zip(cols, vals):
                    ax.text(x, y, v, fontsize=6.5, family="monospace")
                ax.text(0.84, y, "[   ]", fontsize=7, family="monospace")
                ax.plot([0.89, 0.98], [y - 0.004, y - 0.004], color="0.4", lw=0.5)
                if r.flags:
                    ax.text(0.02, y - step * 0.42, "flags: " + r.flags.replace(";", ", "), fontsize=4.8, family="monospace", color="0.3")
            ax.text(0.02, 0.012, foot, fontsize=6.5)
            pdf.savefig(fig); plt.close(fig)
        n_diag = 0
        if "trees_planned" in df.columns:
            n_diag = write_block_diagrams(pdf, plt, df, meta, foot, W, H)
    return len(pages) + 1 + (n_diag if "trees_planned" in df.columns else 0)


def write_block_diagrams(pdf, plt, df, meta, foot, W, H):
    """One page per species: the layout of its block drawn to scale (the 100 m square, the planted area, every tree), the start corner, the spacing, and the list of its blocks."""
    n = 0
    for code, g in df.groupby("species_code", sort=True):
        r0 = g.iloc[0]
        rows, tpr, sp, us = int(r0.rows), int(r0.trees_per_row), float(r0.spacing_m), float(r0.usable_side_m)
        fig = plt.figure(figsize=(W, H))
        ax = fig.add_axes([0.05, 0.1, 0.5, 0.8])
        ax.add_patch(plt.Rectangle((0, 0), 100, 100, fill=False, edgecolor="0.3", lw=1.2))
        ox = (100 - us) / 2
        ax.add_patch(plt.Rectangle((ox, ox), us, us, fill=True, facecolor="0.94", edgecolor="0.5", lw=0.8, ls="--"))
        xs = [ox + k * sp for k in range(tpr)]
        for ri in range(rows):
            ax.scatter(xs, [ox + ri * sp] * tpr, s=14, facecolors="white", edgecolors="black", linewidths=0.6, zorder=3)
        ax.scatter([ox], [ox], s=60, marker="s", color="black", zorder=4)
        ax.annotate("START (south-west corner)", (ox, ox), xytext=(2, -9), textcoords="data", fontsize=7)
        ax.annotate("", xy=(ox + min(us, 3 * sp), ox + 5), xytext=(ox, ox + 5), arrowprops={"arrowstyle": "->", "lw": 1.2})
        ax.text(ox + 1.5 * sp, ox + 7, f"row direction: {r0.row_direction}", fontsize=6.5)
        ax.annotate("", xy=(95, 98), xytext=(95, 88), arrowprops={"arrowstyle": "-|>", "lw": 1.3})
        ax.text(95, 99, "N", ha="center", fontsize=9, weight="bold")
        ax.set_xlim(-6, 106); ax.set_ylim(-14, 106); ax.set_aspect("equal"); ax.set_xticks([0, 50, 100]); ax.set_yticks([0, 50, 100]); ax.tick_params(labelsize=6)
        ax.set_xlabel("metres (the 100 m square)", fontsize=7)
        ax.set_title(f"Block layout - {code} {r0.common_name}", fontsize=10)
        txt = [f"Spacing: {sp:g} m between trees and between rows", f"Layout: {rows} rows of {tpr} trees = {int(r0.capacity)} trees in a full block",
               f"Planted area: about {us:.0f} m x {us:.0f} m in the middle of the square", "Start at the south-west corner of the planted area;",
               "plant east along the first row, then go north one spacing for the next row.", "Count the trees you really plant in each block."]
        if (g.layout_note.fillna("") != "").any():
            txt.append("Plant along the contour where the slope is above 30% (see the list).")
        fig.text(0.6, 0.9, "\n".join(txt), fontsize=8, va="top")
        lines = [f"{r.point_ref:<10} grid {int(r.point_id):<6} {int(r.trees_planned):>4} trees   {str(r.barangay)[:18]:<18} {'contour' if isinstance(r.layout_note, str) and r.layout_note else ''}" for r in g.itertuples(index=False)]
        fig.text(0.6, 0.62, "Blocks of this species:\n" + "\n".join(lines[:22]) + ("\n..." if len(lines) > 22 else ""), fontsize=6.5, family="monospace", va="top")
        fig.text(0.02, 0.02, foot, fontsize=6.5)
        pdf.savefig(fig); plt.close(fig)
        n += 1
    return n


# ---------------------------------------------------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------------------------------------------------
def make_kit(plan_csv, out_dir, pdf=False, data_dir="data/processed", built_on=None, species_table=None, brgy_shp=None, landuse_shp=None):
    """Build the kit folder and the zip. Returns a dict with the paths, the check code and the manifest."""
    plan_csv = Path(plan_csv)
    summary_path = plan_csv.with_name(plan_csv.stem + "_summary.json")
    if not summary_path.exists():
        raise FileNotFoundError(f"summary JSON not found next to the plan: {summary_path.name} (run pipeline/run_plan.py to make both)")
    plan = pd.read_csv(plan_csv)
    need = {"point_id", "lon", "lat", "utm_e", "utm_n", "species_id", "zone_desc", "flags"}
    if not need <= set(plan.columns):
        raise ValueError(f"plan CSV lacks columns: {sorted(need - set(plan.columns))}")
    if plan.empty:
        raise ValueError("the plan has no rows")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    species = species_table if species_table is not None else pd.read_csv(Path(data_dir) / "species_clean.csv")
    ds = dataset_info(data_dir)
    plan_id = safe_name(plan_csv.stem)
    meta = {"plan_id": plan_id, "check_code": check_code(plan_csv), "dataset_tag": ds["tag"], "dataset_hash": ds["hash"],
            "built_on": built_on or date.today().isoformat()}
    code_by_id = make_codes([(int(s), species.set_index("species_id").common_name[s]) for s in sorted(plan.species_id.unique())])
    conditions = None
    sp_file = Path(data_dir) / "site_points_clean.csv"
    if sp_file.is_file():
        sc = pd.read_csv(sp_file, usecols=lambda c: c in ("point_id", "zone_condition"))
        if "zone_condition" in sc:
            conditions = {int(p): c for p, c in zip(sc.point_id, sc.zone_condition) if isinstance(c, str) and c}
    df = build_point_table(plan, species, code_by_id, plan_id, meta["check_code"], brgy_shp or CFG["barangay_shp"], conditions)
    kit = Path(out_dir) / f"field_kit_{plan_id}"
    kit.mkdir(parents=True, exist_ok=True)
    for old in kit.iterdir():
        if old.is_file():
            old.unlink()
    colors = {code: CFG["kml_colors"][i % len(CFG["kml_colors"])] for i, code in enumerate(sorted(df.species_code.unique()))}
    write_gpx(df, meta, kit / "points.gpx")
    write_kml(df, meta, kit / "points.kml", colors)
    write_csv(df, kit / "point-list.csv")
    if is_blocks(df):
        write_blocks_csv(df, kit / "blocks.csv")
    write_readme(df, meta, summary, kit / "README.txt")
    pdf_note = None
    if pdf:
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            pdf_note = "matplotlib is not installed: field-map.pdf was skipped (pip install matplotlib, then run again with --pdf)"
            print(pdf_note)
        else:
            write_pdf(df, meta, summary, kit / "field-map.pdf", landuse_shp or CFG["landuse_shp"], data_dir)
    manifest = write_manifest(kit, df, meta, summary, plan_csv, kit / "manifest.json")
    zpath = Path(out_dir) / f"field_kit_{plan_id}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(kit.iterdir()):
            z.write(p, f"field_kit_{plan_id}/{p.name}")
    return {"kit_dir": kit, "zip": zpath, "plan_id": plan_id, "check_code": meta["check_code"], "manifest": manifest, "points": df,
            "pdf_note": pdf_note, "meta": meta}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, help="plan CSV from data/processed/plans (its _summary.json must sit next to it)")
    ap.add_argument("--out", default="data/processed/kits")
    ap.add_argument("--data-dir", default="data/processed")
    ap.add_argument("--pdf", action="store_true", help="also make field-map.pdf (needs matplotlib)")
    a = ap.parse_args(argv)
    r = make_kit(a.plan, a.out, a.pdf, a.data_dir)
    print(f"plan {r['plan_id']} | check code {r['check_code']} | {len(r['points'])} points")
    for f in r["manifest"]["files"]:
        print(f"  {f['name']:<16} {f['size_bytes']:>9,} bytes")
    print(f"  {'manifest.json':<16} {(r['kit_dir'] / 'manifest.json').stat().st_size:>9,} bytes")
    print(f"zip: {r['zip']} ({r['zip'].stat().st_size:,} bytes)\nkit: {r['kit_dir']}")


if __name__ == "__main__":
    main()
