"""
Field pack, Stage A1: pack ONE field kit (blocks.csv + manifest.json, a folder or the .zip the dashboard gives) into ONE self-contained web page for the planters' phones.

    python scripts/build_field_pack.py path/to/field_kit_plan_xxx.zip [--out folder]

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
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import field_kit as fk  # noqa: E402
import palettes as pal  # noqa: E402

PACK_DIR = ROOT / "fieldpack"
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
    return out, (round(sw[0], 7), round(sw[1], 7)), g


def build_pack(blocks_text, manifest):
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
                       "trees": trees, "row": {c: r.get(c, "") for c in columns}})
    ds = manifest.get("dataset") or {}
    pack = {"format": 1, "plan_id": plan_id, "check_code": check_code, "built_on": manifest.get("built_on", ""), "dataset": {"tag": ds.get("tag", ""), "hash": ds.get("hash", "")},
            "columns": columns, "blocks": blocks}
    pack["pack_id"] = hashlib.sha256(json.dumps(pack, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:8]
    return pack


def render_page(pack):
    """The single HTML file: css, data, core.js, strings.js and app.js inlined."""
    tpl = (PACK_DIR / "template.html").read_text(encoding="utf-8")
    data = json.dumps(pack, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    parts = {"CSS": (PACK_DIR / "app.css").read_text(encoding="utf-8"), "DATA": data, "CORE": (PACK_DIR / "core.js").read_text(encoding="utf-8"),
             "STRINGS": (PACK_DIR / "strings.js").read_text(encoding="utf-8"), "APP": (PACK_DIR / "app.js").read_text(encoding="utf-8")}
    for k, v in parts.items():
        tpl = tpl.replace(f"/*__{k}__*/", v)
    return tpl


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("kit", help="field kit folder or .zip (needs blocks.csv and manifest.json)")
    ap.add_argument("--out", default=".", help="folder for the page (default: here)")
    a = ap.parse_args(argv)
    text, manifest = read_kit(a.kit)
    pack = build_pack(text, manifest)
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
