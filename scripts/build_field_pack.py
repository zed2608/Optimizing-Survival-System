"""
Field pack, Stage A1: pack ONE field kit (blocks.csv + manifest.json, a folder or the .zip the dashboard gives) into ONE self-contained web page for the planters' phones.

    python scripts/build_field_pack.py path/to/field_kit_plan_xxx.zip [--out folder] [--satellite]
    python scripts/build_field_pack.py path/to/field_kit_plan_xxx.zip --site folder     (a folder ready to drag into Cloudflare Pages "Direct Upload": see docs/FIELD_PACK_HOSTING.md)

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

PACK_DIR = ROOT / "fieldpack"
LEAFLET_DIR = PACK_DIR / "vendor" / "leaflet-1.9.4"          # Leaflet 1.9.4 (2023-05-18), BSD-2-Clause, unmodified files from the npm package; see its README.txt
PACK_FORMAT = 2
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
    return out, (round(sw[0], 7), round(sw[1], 7)), g


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
    blocks = []
    for r in rows:
        n = int(float(r["trees_planned"]))
        trees, sw, g = tree_positions(r["spacing_m"], r["trees_per_row"], r["rows"], n, r["utm_e"], r["utm_n"])
        first, start = trees[0], sw
        for what, got, want in (("first tree", (first[1], first[2]), (float(r["first_tree_lat"]), float(r["first_tree_lon"]))), ("START", start, (float(r["start_lat"]), float(r["start_lon"])))):
            if max(abs(got[0] - want[0]), abs(got[1] - want[1])) > COORD_TOLERANCE_DEG:
                raise PackError(f"{r['block_ref']}: the {what} of the layout formula {got} differs from the kit's own column {want}: the kit was made with another formula")
        blocks.append({"ref": r["block_ref"], "point_id": int(r["point_id"]), "species_code": r["species_code"], "name": r["common_name"], "n": n,
                       "spacing_m": float(r["spacing_m"]), "rows": int(float(r["rows"])), "per_row": int(float(r["trees_per_row"])), "row_direction": r.get("row_direction", ""),
                       "start_corner": r.get("start_corner", ""), "barangay": r.get("barangay", ""), "zone": r.get("zone", ""), "flags": r.get("flags", ""), "note": r.get("notes", ""),
                       "centre": [float(r["lat"]), float(r["lon"])], "start": list(start), "side_m": float(r["rect_side_m"]), "margin_m": float(r["margin_m"]),
                       "square": g["square_ll"], "area": g["area_ll"], "trees": trees, "row": {c: r.get(c, "") for c in columns}})
    ds = manifest.get("dataset") or {}
    pack = {"format": PACK_FORMAT, "plan_id": plan_id, "check_code": check_code, "built_on": manifest.get("built_on", ""), "dataset": {"tag": ds.get("tag", ""), "hash": ds.get("hash", "")},
            "columns": columns, "basemaps": [BASEMAPS["osm"]] + ([BASEMAPS["sat"]] if satellite else []), "blocks": blocks}
    pack["pack_id"] = hashlib.sha256(json.dumps(pack, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:8]
    return pack


def leaflet_css():
    """Leaflet's own stylesheet. Its three picture references (layer switch icons, default marker icon) are for controls this page does not use; they are replaced by `none` so that the page
    asks for no file at all. Nothing else is changed."""
    css = (LEAFLET_DIR / "leaflet.css").read_text(encoding="utf-8")
    return re.sub(r"url\(images/[^)]*\)", "none", css)


def render_page(pack):
    """The single HTML file: css, data, core.js, strings.js and app.js inlined."""
    tpl = (PACK_DIR / "template.html").read_text(encoding="utf-8")
    data = json.dumps(pack, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    parts = {"LEAFLET_CSS": leaflet_css(), "LEAFLET_JS": (LEAFLET_DIR / "leaflet.js").read_text(encoding="utf-8"),
             "CSS": (PACK_DIR / "app.css").read_text(encoding="utf-8"), "DATA": data, "CORE": (PACK_DIR / "core.js").read_text(encoding="utf-8"),
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("kit", help="field kit folder or .zip (needs blocks.csv and manifest.json)")
    ap.add_argument("--out", default=".", help="folder for the page (default: here)")
    ap.add_argument("--satellite", action="store_true", help="also put the Esri World Imagery satellite layer in the page (OFF by default: its terms could not be verified)")
    ap.add_argument("--site", help="write a folder ready to drag into Cloudflare Pages (Direct Upload): _headers, robots.txt and <random name>/index.html; --out is then ignored")
    a = ap.parse_args(argv)
    text, manifest = read_kit(a.kit)
    pack = build_pack(text, manifest, satellite=a.satellite)
    if a.site:
        page, name = write_site(pack, a.site)
        n = sum(b["n"] for b in pack["blocks"])
        project = suggest_project_name()
        print(f"Pack page   : {page}  ({page.stat().st_size / 1024:.1f} KB)  plan {pack['plan_id']}  check {pack['check_code']}  pack {pack['pack_id']}  {len(pack['blocks'])} blocks, {n} trees")
        print(f"DRAG THIS FOLDER into Cloudflare Pages (Direct Upload): {Path(a.site).resolve()}")
        print(f"Suggested project name (random, from `secrets`): {project}")
        print(f"The address will be: https://<your project address>/{name}/      e.g. https://{project}.pages.dev/{name}/ for a Pages project, or https://<name>.<account>.workers.dev/{name}/ for a Workers project")
        print("Anyone with that address can read the plan inside the page. Keep it to the planters; delete the project when the planting is done.")
        return page
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"fieldpack_{pack['plan_id']}_{pack['check_code']}.html"
    page = render_page(pack)
    f.write_text(page, encoding="utf-8")
    n = sum(b["n"] for b in pack["blocks"])
    print(f"{f}  {len(page.encode('utf-8')) / 1024:.1f} KB  plan {pack['plan_id']}  check {pack['check_code']}  pack {pack['pack_id']}  {len(pack['blocks'])} blocks, {n} trees")
    return f


if __name__ == "__main__":
    main()
