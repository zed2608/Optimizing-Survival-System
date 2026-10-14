"""
Field pack, Stage A1: pack ONE field kit (blocks.csv + manifest.json, a folder or the .zip the dashboard gives) into ONE self-contained web page for the planters' phones.

    python scripts/build_field_pack.py path/to/field_kit_plan_xxx.zip [--out folder] [--satellite]
    python scripts/build_field_pack.py path/to/field_kit_plan_xxx.zip --site folder     (a folder ready to drag into Cloudflare Pages "Direct Upload": see docs/FIELD_PACK_HOSTING.md)

A thin wrapper: the logic (read_kit, build_pack, render_page, write_site ...) lives in pipeline/field_pack.py, which the service image also contains (stage A2a).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from field_pack import *  # noqa: E402,F401,F403  (the same names as before: read_kit, build_pack, render_page, write_site, random_name, HEADERS_TEXT, PackError, secrets ...)
from field_pack import PACK_DIR, build_pack, read_kit, render_page, suggest_project_name, write_site  # noqa: E402,F401


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
