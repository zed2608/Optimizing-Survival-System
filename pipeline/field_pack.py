"""
Field pack builder (stages A1 to A3, moved here in stage A2a so that the service image can use it): pack ONE field kit (blocks.csv + manifest.json, a folder or the .zip the dashboard gives)
into ONE self-contained web page for the planters' phones. The command line is scripts/build_field_pack.py (a thin wrapper); the service (api_v2.py) calls these functions.

The page has no network calls and no login. The plan is embedded as JSON; plan_id and check_code travel with it and are written into the results file.
The tree layout is NOT invented here: every tree gets its latitude and longitude from pipeline/palettes.py block_geometry (the ONE layout formula used by the kit, the PDF and the dashboard)
and the same pyproj transform as field_kit.attach_geometry. The build refuses a kit whose own first-tree and START columns disagree with that formula.
Everything is provisional: GPS accuracy has not been field-tested (the page says so on every screen).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import secrets
import string
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import field_kit as fk  # noqa: E402
import palettes as pal  # noqa: E402
import species_ph_evidence as spe  # noqa: E402

PACK_DIR = ROOT / "fieldpack"
LEAFLET_DIR = PACK_DIR / "vendor" / "leaflet-1.9.4"          # Leaflet 1.9.4 (2023-05-18), BSD-2-Clause, unmodified files from the npm package; see its README.txt
PACK_FORMAT = 3
# The map pictures. Only the openstreetmap.org tile server is on by default (its usage policy was read and is met, see docs/PENDING_DOC_UPDATES.md); the Esri satellite layer is ONLY in the page when
# the build is asked for it with --satellite, because Esri's terms for a page like this could not be read (marked RE-CHECK). Nothing is fetched until a person opens a block.
BASEMAPS = {
    "osm": {"id": "osm", "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "maxNativeZoom": 19,
            "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'},
    "sat": {"id": "sat", "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "maxNativeZoom": 19,       # the service answers a grey "no data" tile above level 19 here
            "attribution": "Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community"},
}
COORD_TOLERANCE_DEG = 2e-6      # the kit's own columns are computed from the unrounded square centre; the CSV only keeps utm_e / utm_n to 0.1 m, so they may differ by a few centimetres
NEEDED = ["block_ref", "point_id", "lat", "lon", "utm_e", "utm_n", "species_code", "common_name", "trees_planned", "spacing_m", "rows", "trees_per_row", "plan_id", "check_code",
          "start_lat", "start_lon", "first_tree_lat", "first_tree_lon", "rect_side_m", "margin_m"]


class PackError(ValueError):
    pass


def read_kit(path):
    """(blocks.csv text, manifest dict) from a kit folder or zip. The sha256 of blocks.csv must match the manifest (the kit was not edited after it was built)."""
    p = Path(path)
    if p.is_dir():
        files = {f.name: f.read_bytes() for f in p.iterdir() if f.is_file()}
    elif p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            files = {Path(i.filename).name: z.read(i) for i in z.infolist() if not i.is_dir()}
    else:
        raise PackError(f"{p} is neither a kit folder nor a .zip")
    for need in ("blocks.csv", "manifest.json"):
        if need not in files:
            raise PackError(f"{need} is missing from the kit: only a kit of a plan in blocks (with blocks.csv) can be packed")
    manifest = json.loads(files["manifest.json"].decode("utf-8"))
    manifest["_extra"] = {n: files[n].decode("utf-8-sig") for n in ("trees.csv", "area.geojson") if n in files}       # spaced kits: every tree and the area (not part of the file; added when the kit is read)
    listed_extra = {f["name"]: f["sha256"] for f in manifest.get("files", [])}
    for n, text in manifest["_extra"].items():
        if listed_extra.get(n) and listed_extra[n] != hashlib.sha256(files[n]).hexdigest():
            raise PackError(f"{n} does not match manifest.json (the file was changed after the kit was built): ask for a new kit")
    listed = {f["name"]: f["sha256"] for f in manifest.get("files", [])}
    got = hashlib.sha256(files["blocks.csv"]).hexdigest()
    if listed.get("blocks.csv") and listed["blocks.csv"] != got:
        raise PackError("blocks.csv does not match manifest.json (the file was changed after the kit was built): ask for a new kit")
    return files["blocks.csv"].decode("utf-8-sig"), manifest


def tree_positions(spacing_m, per_row, rows, n, utm_e, utm_n):
    """[[k, lat, lon, x_m, y_m], ...] for trees 1..n, from palettes.block_geometry and the transform of field_kit.attach_geometry. x, y are metres from the SW corner of the 100 m square."""
    from pyproj import Transformer
    tr = Transformer.from_crs(fk.CFG["site_crs"], "EPSG:4326", always_xy=True)
    g = pal.block_geometry(float(spacing_m), int(per_row), int(rows), int(n))
    half = g["side_m"] / 2.0

    def ll(x, y):
        lon, lat = tr.transform(float(utm_e) - half + x, float(utm_n) - half + y)
        return lat, lon

    out = []
    for t in g["trees"]:
        if not t["planted"]:
            continue
        lat, lon = ll(t["x"], t["y"])
        out.append([t["k"], round(lat, 7), round(lon, 7), round(t["x"], 3), round(t["y"], 3)])
    sw = ll(*g["corners"]["SW"])
    side = g["side_m"]
    rnd = lambda pt: [round(pt[0], 7), round(pt[1], 7)]
    g["square_ll"] = [rnd(ll(*c)) for c in ((0.0, 0.0), (side, 0.0), (side, side), (0.0, side))]                       # the 100 m grid square: SW, SE, NE, NW
    g["area_ll"] = [rnd(ll(*g["corners"][k])) for k in ("SW", "SE", "NE", "NW")]                                         # the planted rectangle
    g["first_offset"] = [round(g["first_tree"][0] - g["corners"]["SW"][0], 3), round(g["first_tree"][1] - g["corners"]["SW"][1], 3)]   # tree 1 is this far east and north of the START corner
    return out, (round(sw[0], 7), round(sw[1], 7)), g


def spaced_block(r, tree_rows, feature):
    """A block of a SPACED kit: the trees come from trees.csv (in walking order), the ground from area.geojson. Same keys as a rows block, plus layout, areas, region_m, requested, fits, fit_note."""
    from pyproj import Transformer
    crs = fk.CFG["site_crs"]
    to_ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    e0, n0 = float(r["utm_e"]) - 50.0, float(r["utm_n"]) - 50.0
    ll = lambda x, y: tuple(reversed(to_ll.transform(e0 + x, n0 + y)))
    trees = [[int(t["tree"]), round(float(t["lat"]), 7), round(float(t["lon"]), 7), round(float(t["x_m"]), 3), round(float(t["y_m"]), 3)] for t in sorted(tree_rows, key=lambda t: int(t["tree"]))]
    if [t[0] for t in trees] != list(range(1, len(trees) + 1)):
        raise PackError(f"{r['block_ref']}: the trees of trees.csv are not numbered 1 to {len(trees)}")
    if len(trees) != int(float(r.get("trees_fit") or 0)):
        raise PackError(f"{r['block_ref']}: trees.csv holds {len(trees)} trees but blocks.csv says {r.get('trees_fit')} fit")
    if trees and max(abs(trees[0][1] - float(r["first_tree_lat"])), abs(trees[0][2] - float(r["first_tree_lon"]))) > COORD_TOLERANCE_DEG * 5:
        raise PackError(f"{r['block_ref']}: tree 1 of trees.csv differs from the first_tree columns of blocks.csv: the kit was made with another layout")
    start = [float(r["start_lat"]), float(r["start_lon"])]
    sx, sy = float(r["start_utm_e"]) - e0, float(r["start_utm_n"]) - n0
    rnd = lambda pt: [round(pt[0], 7), round(pt[1], 7)]
    side = 100.0
    rings, region_m = [], []
    if feature:
        for poly in feature["geometry"]["coordinates"]:
            ring = poly[0]
            rings.append([[round(la, 7), round(lo, 7)] for lo, la in ring])
            region_m.append([[round(a - e0, 2), round(b - n0, 2)] for a, b in (to_utm.transform(lo, la) for lo, la in ring)])
    first_offset = [round(trees[0][3] - sx, 3), round(trees[0][4] - sy, 3)] if trees else [0.0, 0.0]
    g = {"side_m": side, "square_ll": [rnd(ll(*c)) for c in ((0.0, 0.0), (side, 0.0), (side, side), (0.0, side))], "area_ll": rings[0] if rings else [],
         "first_offset": first_offset}
    block = {"layout": "spaced", "requested": int(float(r["trees_planned"])), "fits": len(trees) >= int(float(r["trees_planned"])), "fit_note": r.get("fit_note", ""),
             "areas": rings, "region_m": region_m, "start_m": [round(sx, 3), round(sy, 3)]}
    return trees, tuple(start), g, block


def pack_area(area_text):
    """The area the user selected and the plantable ground for the map (simplified to about 1 m; lat/lon rings), or None."""
    if not area_text:
        return None
    from shapely.geometry import shape
    doc = json.loads(area_text)
    out = {}
    for f in doc.get("features", []):
        k = f["properties"].get("kind")
        if k in ("selected", "plantable"):
            g = shape(f["geometry"]).simplify(0.00001, preserve_topology=True)
            polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
            out[k] = [[[round(la, 6), round(lo, 6)] for lo, la in p.exterior.coords] for p in polys]
    return out or None


PH_KEYS = ("status", "verdict_kind", "verdict_min", "verdict_max", "tol_min", "tol_max", "opt_min", "opt_max", "listed_min", "listed_max", "source_name", "source_rank", "conflict", "scope")


def ph_reference_list(blocks):
    """The soil pH reference of each species of the plan (from data/reference/species_ph_evidence.csv; matched by common name). Text only: no new network call, no score. A species the file does not know
    (or no file) is listed as status none: 'walang nakumpirmang pH range'. Ranges are 'from a source, not yet signed by the agriculturist'."""
    t = spe.load() or {}
    by_name = {str(r.get("common_name", "")).strip().lower(): sid for sid, r in t.items()}
    out, seen = [], set()
    for b in blocks:
        if b["species_code"] in seen:
            continue
        seen.add(b["species_code"])
        sid = by_name.get(str(b["name"]).strip().lower())
        ref = spe.reference(sid) if sid is not None else None
        e = {"code": b["species_code"], "name": b["name"], "species_id": sid}
        e.update({k: (ref or {}).get(k) for k in PH_KEYS} if ref else {"status": "none"})
        out.append(e)
    return out


CHECKLIST_CSV = ROOT / "data" / "reference" / "site_checklist.csv"
ZONE_COND = re.compile(r"Zone condition: ([^.]+)\.")


def checklist_for_pack(blocks, path=None):
    """The "Suriin sa lugar" questions (data/reference/site_checklist.csv), the genera of the plan's species, the species' shade tolerance (species table, draft) and the zone conditions of the blocks.
    Text only: no network, no score; the planter's answers are never saved. An absent file gives no section (the pack still builds)."""
    p = Path(path or CHECKLIST_CSV)
    if not p.is_file():
        return None
    import pandas as pd
    items = []
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            ids, labels = r["options"].split("|"), r["option_labels"].split("|")
            tips = [r["tip_if_oo"]] + ([r["tip_if_middle"]] if len(ids) == 4 else []) + [r["tip_if_hindi"], r["tip_if_hindi_sigurado"]]
            kinds = ["oo", "middle", "hindi", "hindi_sigurado"] if len(ids) == 4 else ["oo", "hindi", "hindi_sigurado"]
            items.append({"id": r["item_id"], "question": r["question_fil"], "why": r["why_fil"], "options": [{"id": i, "label": l, "tip": t, "kind": k} for i, l, t, k in zip(ids, labels, tips, kinds)],
                          "genus_tip": r["genus_tip_if_oo"], "genus": [g for g in r["applies_to_genus"].split("|") if g], "note": r["note"],
                          "source": {"name": r["source_name"], "scope": r["source_scope"], "url": r["source_url"], "quotes": [q for q in r["source_quote"].split(" || ") if q] if r["quote_verified"] == "yes" else []}})
    names = {str(b["name"]).strip().lower() for b in blocks}
    sp = pd.read_csv(ROOT / "data" / "processed" / "species_clean.csv")
    sp = sp[sp.common_name.str.strip().str.lower().isin(names)]
    clean = lambda v: "" if v is None or str(v).lower() == "nan" else str(v)
    species = [{"name": r.common_name, "genus": clean(r.genus), "shade_tol": clean(r.shade_tol), "light_preference": clean(r.light_preference)} for r in sp.itertuples()]
    conds = sorted({m.group(1) for b in blocks for m in [ZONE_COND.search(b.get("note", ""))] if m})
    return {"items": items, "species": species, "genera": sorted({s["genus"] for s in species if s["genus"]}), "zone_conditions": conds}


def build_pack(blocks_text, manifest, satellite=False):
    reader = csv.DictReader(io.StringIO(blocks_text))
    columns = [c.strip() for c in (reader.fieldnames or [])]
    missing = [c for c in NEEDED if c not in columns]
    if missing:
        raise PackError(f"blocks.csv lacks columns {missing}: it is not a kit of a plan in blocks, or it is from before round 13")
    rows = [{k.strip(): (v or "") for k, v in r.items()} for r in reader]
    if not rows:
        raise PackError("blocks.csv has no rows")
    plan_ids, codes = {r["plan_id"] for r in rows}, {r["check_code"] for r in rows}
    if len(plan_ids) != 1 or len(codes) != 1:
        raise PackError("blocks.csv mixes several plans or check codes")
    plan_id, check_code = plan_ids.pop(), codes.pop()
    if manifest.get("plan_id") not in (None, plan_id) or manifest.get("check_code") not in (None, check_code):
        raise PackError("manifest.json and blocks.csv name different plans or check codes")
    blocks, skipped = [], []
    extra = manifest.get("_extra") or {}
    spaced = "layout" in columns and any(r.get("layout") == "spaced" for r in rows)
    if spaced and "trees.csv" not in extra:
        raise PackError("the kit is made of spaced points but trees.csv is missing from it")
    tree_rows = {}
    for t in csv.DictReader(io.StringIO(extra.get("trees.csv", ""))):
        tree_rows.setdefault(t["point_ref"], []).append(t)
    features = {f["properties"].get("ref"): f for f in json.loads(extra["area.geojson"]).get("features", []) if f["properties"].get("kind") == "block"} if "area.geojson" in extra else {}
    for r in rows:
        n = int(float(r["trees_planned"]))
        if r.get("layout") == "spaced":
            trees, start, g, sp_ = spaced_block(r, tree_rows.get(r["block_ref"], []), features.get(r["block_ref"]))
            if not trees:                                                # no plantable ground in this block (the selected area leaves nothing): nothing to plant, so it is not in the pack
                skipped.append(r["block_ref"])
                continue
            blocks.append({"ref": r["block_ref"], "point_id": int(r["point_id"]), "species_code": r["species_code"], "name": r["common_name"], "n": len(trees),
                           "spacing_m": float(r["min_distance_m"] or r["spacing_m"] or 0), "rows": 0, "per_row": 0, "row_direction": "spaced points", "start_corner": "",
                           "barangay": r.get("barangay", ""), "zone": r.get("zone", ""), "flags": r.get("flags", ""), "note": r.get("notes", ""),
                           "centre": [float(r["lat"]), float(r["lon"])], "start": list(start), "side_m": 100.0, "margin_m": float(r.get("margin_m") or 0),
                           "square": g["square_ll"], "area": g["area_ll"], "first_offset_m": g["first_offset"], "trees": trees, "row": {c: r.get(c, "") for c in columns}, **sp_})
            continue
        trees, sw, g = tree_positions(r["spacing_m"], r["trees_per_row"], r["rows"], n, r["utm_e"], r["utm_n"])
        first, start = trees[0], sw
        for what, got, want in (("first tree", (first[1], first[2]), (float(r["first_tree_lat"]), float(r["first_tree_lon"]))), ("START", start, (float(r["start_lat"]), float(r["start_lon"])))):
            if max(abs(got[0] - want[0]), abs(got[1] - want[1])) > COORD_TOLERANCE_DEG:
                raise PackError(f"{r['block_ref']}: the {what} of the layout formula {got} differs from the kit's own column {want}: the kit was made with another formula")
        blocks.append({"ref": r["block_ref"], "point_id": int(r["point_id"]), "species_code": r["species_code"], "name": r["common_name"], "n": n,
                       "spacing_m": float(r["spacing_m"]), "rows": int(float(r["rows"])), "per_row": int(float(r["trees_per_row"])), "row_direction": r.get("row_direction", ""),
                       "start_corner": r.get("start_corner", ""), "barangay": r.get("barangay", ""), "zone": r.get("zone", ""), "flags": r.get("flags", ""), "note": r.get("notes", ""),
                       "centre": [float(r["lat"]), float(r["lon"])], "start": list(start), "side_m": float(r["rect_side_m"]), "margin_m": float(r["margin_m"]),
                       "square": g["square_ll"], "area": g["area_ll"], "first_offset_m": g["first_offset"], "trees": trees, "row": {c: r.get(c, "") for c in columns}})
    if not blocks:
        raise PackError("no block of this kit has ground where trees fit at the required spacing: enlarge the area or reduce the trees, then make a new kit")
    ds = manifest.get("dataset") or {}
    pack_ph = ph_reference_list(blocks)
    pack = {"format": PACK_FORMAT, "plan_id": plan_id, "check_code": check_code, "built_on": manifest.get("built_on", ""), "dataset": {"tag": ds.get("tag", ""), "hash": ds.get("hash", "")},
            "ph": pack_ph, "checklist": checklist_for_pack(blocks), "columns": columns, **({"area": pack_area(extra.get("area.geojson")), "skipped_blocks": skipped} if spaced else {}), "basemaps": [BASEMAPS["osm"]] + ([BASEMAPS["sat"]] if satellite else []), "blocks": blocks}
    pack["pack_id"] = hashlib.sha256(json.dumps(pack, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:8]
    return pack


def leaflet_css():
    """Leaflet's own stylesheet. Its three picture references (layer switch icons, default marker icon) are for controls this page does not use; they are replaced by `none` so that the page
    asks for no file at all. Nothing else is changed."""
    css = (LEAFLET_DIR / "leaflet.css").read_text(encoding="utf-8")
    return re.sub(r"url\(images/[^)]*\)", "none", css)


CSS_NL = chr(10)
FONT_FACES = (("Inter Variable", "normal", "inter-latin-wght-normal.woff2"), ("Fraunces Variable", "italic", "fraunces-latin-wght-italic.woff2"))


def design_css():
    """The Canopy design tokens (a generated copy of the dashboard's token block, scripts/sync_fieldpack_tokens.py) and the two fonts as data: addresses, so that the page still asks for no file."""
    import base64
    faces = []
    for family, style, name in FONT_FACES:
        path = PACK_DIR / "vendor" / "fonts" / name
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            faces.append(f"@font-face {{ font-family: '{family}'; font-style: {style}; font-weight: 100 900; font-display: swap; src: url(data:font/woff2;base64,{data}) format('woff2'); }}")
    tokens = (PACK_DIR / "tokens.css").read_text(encoding="utf-8")
    return CSS_NL.join(faces) + CSS_NL + tokens


def render_page(pack):
    """The single HTML file: css, data, core.js, strings.js and app.js inlined."""
    tpl = (PACK_DIR / "template.html").read_text(encoding="utf-8")
    data = json.dumps(pack, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    parts = {"LEAFLET_CSS": leaflet_css(), "LEAFLET_JS": (LEAFLET_DIR / "leaflet.js").read_text(encoding="utf-8"),
             "CSS": design_css() + CSS_NL + (PACK_DIR / "app.css").read_text(encoding="utf-8"), "DATA": data, "CORE": (PACK_DIR / "core.js").read_text(encoding="utf-8"),
             "STRINGS": (PACK_DIR / "strings.js").read_text(encoding="utf-8"), "APP": (PACK_DIR / "app.js").read_text(encoding="utf-8")}
    for k, v in parts.items():
        tpl = tpl.replace(f"/*__{k}__*/", v)
    return tpl


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# A folder ready to upload (Cloudflare Pages Direct Upload): <site>/_headers, <site>/robots.txt, <site>/<random>/index.html and NOTHING else.
# The random folder name (and the suggested project name) come from the `secrets` module: never from plan_id, check_code or the time, so the address cannot be worked out from the plan.
# An unguessable address only keeps the page out of casual reach: anyone who is given the link can read the plan inside it. Take it down by deleting the project.
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
NAME_ALPHABET = string.ascii_lowercase + string.digits
NAME_LENGTH = 24                                   # 36^24 is about 2^124 possibilities
NAME_PATTERN = re.compile(r"^[a-z0-9]{20,}$")
HEADERS_TEXT = """/*
  X-Robots-Tag: noindex, nofollow
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
"""
ROBOTS_TEXT = "User-agent: *\nDisallow: /\n"
SITE_ROOT_FILES = {"_headers", "robots.txt"}


def random_name(length=NAME_LENGTH):
    return "".join(secrets.choice(NAME_ALPHABET) for _ in range(length))


def suggest_project_name():
    return "fp-" + random_name(10)                 # Cloudflare project names: lower-case letters, digits and hyphens


def check_site_folder(site):
    """A new or empty folder, or a folder this script made before (so that a second plan can be added). Anything else is refused: nothing is overwritten or deleted."""
    site = Path(site)
    if not site.exists():
        return
    if not site.is_dir():
        raise PackError(f"{site} is a file, not a folder")
    for child in site.iterdir():
        if child.is_file() and child.name in SITE_ROOT_FILES:
            continue
        if child.is_dir() and NAME_PATTERN.match(child.name) and [c.name for c in child.iterdir()] == ["index.html"]:
            continue
        raise PackError(f"{site} holds {child.name}, which is not part of a field pack site: choose an empty folder (nothing was changed)")


def write_site(pack, site, name=None):
    """Write the three kinds of file and nothing else. Returns (page path, folder name)."""
    site = Path(site)
    check_site_folder(site)
    name = name or random_name()
    if not NAME_PATTERN.match(name) or (site / name).exists():
        raise PackError("the folder name is not valid or already exists")
    (site / name).mkdir(parents=True)
    (site / "_headers").write_text(HEADERS_TEXT, encoding="utf-8", newline="\n")
    (site / "robots.txt").write_text(ROBOTS_TEXT, encoding="utf-8", newline="\n")
    page = site / name / "index.html"
    page.write_text(render_page(pack), encoding="utf-8")
    return page, name
