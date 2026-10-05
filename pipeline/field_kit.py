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
}
# =====================================================================================================================

CSV_COLUMNS = ["point_ref", "point_id", "species_code", "common_name", "scientific_name", "lat", "lon", "utm_e", "utm_n", "barangay",
               "zone", "spacing_min_m", "planting_months", "flags", "notes", "plan_id", "check_code", "status", "moved_lat", "moved_lon"]
GPX_NS, KML_NS = "http://www.topografix.com/GPX/1/1", "http://www.opengis.net/kml/2.2"
KIT_FILES = ["points.gpx", "points.kml", "point-list.csv", "README.txt"]


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


def month_names(value):
    if value is None or (isinstance(value, float) and np.isnan(value)) or str(value).strip() == "":
        return ""
    return ";".join(CFG["months"][int(m) - 1] for m in str(value).replace(",", ";").split(";") if m.strip())


def dataset_info(data_dir):
    db = Path(data_dir) / "optimizing_survival.db"
    try:
        con = sqlite3.connect(db)
        row = con.execute("SELECT tag, file_hash FROM dataset_versions ORDER BY dataset_version_id DESC LIMIT 1").fetchone()
        con.close()
        if row:
            return {"tag": row[0], "hash": row[1]}
    except sqlite3.Error:
        pass
    return {"tag": "unknown", "hash": "unknown"}


def assign_barangay(df, shp):
    """Barangay per point by spatial join; a point outside every polygon gets the nearest one and the flag barangay_nearest."""
    import geopandas as gpd
    b = gpd.read_file(_abs(shp))[["BRGY_NAME", "geometry"]].sort_values("BRGY_NAME").reset_index(drop=True)
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


def build_point_table(plan, species, code_by_id, plan_id, check, brgy_shp):
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
    width = max(CFG["min_number_digits"], len(str(df.groupby("species_code").size().max())))
    df["point_ref"] = df.species_code + "-" + (df.groupby("species_code").cumcount() + 1).astype(str).str.zfill(width)
    df["zone"] = df.zone_desc.fillna("")
    df["notes"] = [" ".join(FLAG_NOTES[f] for f in fl.split(";") if f in FLAG_NOTES) for fl in df["flags"]]
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
    for code, g in df.groupby("species_code", sort=True):
        f = ET.SubElement(doc, q("Folder"))
        ET.SubElement(f, q("name")).text = f"{code} - {g.common_name.iloc[0]} ({len(g)})"
        for r in g.itertuples(index=False):
            p = ET.SubElement(f, q("Placemark"))
            ET.SubElement(p, q("name")).text = r.point_ref
            ET.SubElement(p, q("description")).text = describe(r)
            ET.SubElement(p, q("styleUrl")).text = f"#s_{code}"
            ET.SubElement(ET.SubElement(p, q("Point")), q("coordinates")).text = f"{r.lon_s},{r.lat_s},0"
    _write_xml(root, path)


def write_csv(df, path):
    out = df[CSV_COLUMNS].copy()
    out["lat"], out["lon"] = df.lat_s, df.lon_s
    out["utm_e"], out["utm_n"] = df.utm_e.round(1), df.utm_n.round(1)
    out.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")


def palette_rows(df):
    g = df.groupby(["species_code", "common_name"], sort=True).size().reset_index(name="n")
    dio = set(df[df["flags"].str.contains("needs_both_sexes")].species_code)
    return [(r.species_code, r.common_name, int(r.n), r.species_code in dio) for r in g.itertuples(index=False)]


def write_readme(df, meta, summary, path):
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
    m = {"plan_id": meta["plan_id"], "check_code": meta["check_code"], "built_on": meta["built_on"],
         "dataset": {"tag": meta["dataset_tag"], "hash": meta["dataset_hash"]},
         "plan_file": {"name": Path(plan_csv).name, "sha256": sha256_file(plan_csv)},
         "counts": {"points": int(len(df)), "species": len(per), "per_species": per},
         "files": files, "nudge_max_m": CFG["nudge_max_m"], "cell_m": CFG["cell_m"],
         "limits": summary.get("limits", []), "plan_summary": summary,
         "note": "manifest.json lists every other file of the kit; it cannot list its own hash."}
    Path(path).write_text(json.dumps(m, indent=2, default=str), encoding="utf-8")
    return m


def write_pdf(df, meta, summary, path, landuse_shp):
    """field-map.pdf, A4 landscape: overview map (shapes + labels, scale bar, north arrow, legend) and the point table."""
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
    return len(pages) + 1


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
    df = build_point_table(plan, species, code_by_id, plan_id, meta["check_code"], brgy_shp or CFG["barangay_shp"])
    kit = Path(out_dir) / f"field_kit_{plan_id}"
    kit.mkdir(parents=True, exist_ok=True)
    for old in kit.iterdir():
        if old.is_file():
            old.unlink()
    colors = {code: CFG["kml_colors"][i % len(CFG["kml_colors"])] for i, code in enumerate(sorted(df.species_code.unique()))}
    write_gpx(df, meta, kit / "points.gpx")
    write_kml(df, meta, kit / "points.kml", colors)
    write_csv(df, kit / "point-list.csv")
    write_readme(df, meta, summary, kit / "README.txt")
    pdf_note = None
    if pdf:
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            pdf_note = "matplotlib is not installed: field-map.pdf was skipped (pip install matplotlib, then run again with --pdf)"
            print(pdf_note)
        else:
            write_pdf(df, meta, summary, kit / "field-map.pdf", landuse_shp or CFG["landuse_shp"])
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
