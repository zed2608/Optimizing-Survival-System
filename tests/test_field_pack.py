"""Field pack, Stage A1 (branch field-pack): one kit -> one self-contained phone page.
 - the per-tree coordinates in the page equal the ones of field_kit.py / palettes.block_geometry for EVERY tree of EVERY block of the sample kit (plan_urban_20261013_032648, check 3b2afb9e);
 - the page's maths (distance, bearing, arrival rule, honest precision, order of trees, results file, saving) is tested with node;
 - the results file the page writes is accepted by the dashboard's existing import (POST /field-checks/import).
Run from the repo root: python -m pytest tests/test_field_pack.py"""
import csv, io, json, math, os, re, shutil, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
FIXTURE = ROOT / "tests" / "fixtures" / "field_pack" / "field_kit_plan_urban_20261013_032648"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))
import build_field_pack as bfp  # noqa: E402
import field_kit as fk  # noqa: E402
import field_verify as fv  # noqa: E402
import palettes as pal  # noqa: E402
import pandas as pd  # noqa: E402

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")
needs_data = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")


@pytest.fixture(scope="module")
def kit():
    text, manifest = bfp.read_kit(FIXTURE)
    return text, manifest


@pytest.fixture(scope="module")
def pack(kit):
    return bfp.build_pack(*kit)


# ---------------------------------------------------------------- the page and its data
def strings_tables():
    """STRINGS of fieldpack/strings.js as {"en": {...}, "fil": {...}}, read with node."""
    r = subprocess.run([NODE, "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])))", str(ROOT / "fieldpack" / "strings.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_sample_kit_is_the_one_named_in_the_task(kit, pack):
    assert pack["plan_id"] == "plan_urban_20261013_032648" and pack["check_code"] == "3b2afb9e"
    assert len(pack["blocks"]) == 6 and sum(b["n"] for b in pack["blocks"]) == 50
    assert re.fullmatch(r"[0-9a-f]{8}", pack["pack_id"])


ALLOWED_HOSTS = {"www.w3.org", "leafletjs.com", "tile.openstreetmap.org", "www.openstreetmap.org",     # w3.org = the SVG name space (a name, not an address that is visited); the rest: map tiles and links
                 "bugs.chromium.org", "bugzilla.mozilla.org"}                                                 # addresses of browser bug reports inside Leaflet's own code comments (nothing is requested from them)


def page_urls(page):
    return sorted(set(re.findall(r"https?://([A-Za-z0-9.-]+)", page)))


def test_the_page_is_one_self_contained_file_and_small(pack, tmp_path):
    f = tmp_path / "p.html"
    page = bfp.render_page(pack)
    f.write_text(page, encoding="utf-8")
    assert f.stat().st_size < 300_000                                              # the sample kit: 6 blocks, 50 trees; Leaflet is about 150 KB of it (the page is about 215 KB)
    assert "Prototype. GPS accuracy not yet field-tested." in page                 # the permanent banner text is in the strings table that is inlined
    assert 'name="viewport"' in page and 'id="banner"' in page
    assert "/*__" not in page                                                      # every placeholder was filled
    assert not re.search(r"<script[^>]+src=|<link[^>]+href=|@import", page)        # nothing is loaded from outside: no CDN, no style sheet, no import
    css_urls = re.findall(r"url\(([^)]*)\)", page)
    assert set(css_urls) <= {"#default#VML"}, css_urls                              # Leaflet's picture files are cut out; only an old-Internet-Explorer line stays (it loads nothing)
    ours = "".join((ROOT / "fieldpack" / n).read_text(encoding="utf-8") for n in ("app.js", "core.js", "strings.js"))
    assert not re.search(r"\bfetch\(|XMLHttpRequest|sendBeacon|WebSocket|importScripts", ours)      # our own code never sends or fetches anything
    assert set(page_urls(page)) <= ALLOWED_HOSTS, page_urls(page)                  # the only addresses in the page: tile server, links and the SVG name
    own = "".join((ROOT / "fieldpack" / n).read_text(encoding="utf-8") for n in ("app.js", "core.js", "strings.js", "app.css", "template.html"))
    assert set(page_urls(own)) <= {"www.w3.org", "leafletjs.com"}                  # in our own files only the SVG name and the link of Leaflet's credit (the tile addresses come from the plan data)
    embedded = json.loads(re.search(r'<script type="application/json" id="pack-data">(.*?)</script>', page, re.S).group(1).replace("<\\/", "</"))
    assert embedded == pack                                                        # the plan travels inside the page: plan_id, check_code and every block


def test_the_standard_map_is_the_only_tile_source_unless_satellite_is_asked_for(pack, kit):
    assert [b["id"] for b in pack["basemaps"]] == ["osm"]
    assert pack["basemaps"][0]["url"] == "https://tile.openstreetmap.org/{z}/{x}/{y}.png" and pack["basemaps"][0]["maxNativeZoom"] == 19
    assert "OpenStreetMap" in pack["basemaps"][0]["attribution"] and "contributors" in pack["basemaps"][0]["attribution"]
    page = bfp.render_page(pack)
    assert "arcgisonline" not in page and "Esri" not in page                       # no satellite address and no satellite button text unless the build asks for it
    sat = bfp.build_pack(*kit, satellite=True)
    assert [b["id"] for b in sat["basemaps"]] == ["osm", "sat"]
    assert sat["basemaps"][1]["url"].endswith("/MapServer/tile/{z}/{y}/{x}") and sat["basemaps"][1]["maxNativeZoom"] == 19      # the Esri service answers a grey "no data" tile above level 19 here
    assert "Esri" in sat["basemaps"][1]["attribution"]
    assert set(page_urls(bfp.render_page(sat))) <= ALLOWED_HOSTS | {"server.arcgisonline.com"}


def test_the_referrer_policy_does_not_strip_the_referer_the_tile_policy_needs(pack):
    """openstreetmap.org: "Browsers are expected to send a valid Referer header ... do not strip or blank the Referer". The pack asks for the origin only (never the secret path)."""
    page = bfp.render_page(pack)
    assert '<meta name="referrer" content="strict-origin-when-cross-origin">' in page
    assert "referrerPolicy: 'strict-origin-when-cross-origin'" in page             # also set on every tile picture
    assert "no-referrer" not in bfp.HEADERS_TEXT and "Referrer-Policy: strict-origin-when-cross-origin" in bfp.HEADERS_TEXT


def test_leaflet_is_vendored_unmodified_with_its_licence_and_old_enough():
    import hashlib
    from datetime import date
    v = ROOT / "fieldpack" / "vendor" / "leaflet-1.9.4"
    digests = {n: hashlib.sha256((v / n).read_bytes()).hexdigest() for n in ("leaflet.js", "leaflet.css", "LICENSE")}
    assert digests == {"leaflet.js": "db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a",
                       "leaflet.css": "a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6",
                       "LICENSE": "53e8dc25862014e4324741ca18fbe3611e11d42ef69f59f86ea8c5389647d4cb"}      # the files of the npm package leaflet@1.9.4, not edited
    assert "BSD 2-Clause License" in (v / "LICENSE").read_text(encoding="utf-8") and "Leaflet 1.9.4" in (v / "leaflet.js").read_text(encoding="utf-8")[:200]
    assert (date.today() - date(2023, 5, 18)).days >= 14                           # released 2023-05-18: far older than the two weeks asked for
    readme = (v / "README.txt").read_text(encoding="utf-8")
    assert "BSD-2-Clause" in readme and all(d in readme for d in digests.values())
    page = bfp.render_page(bfp.build_pack(*bfp.read_kit(FIXTURE)))
    assert (v / "leaflet.js").read_text(encoding="utf-8") in page                  # the whole library is inside the page
    assert "url(images/" not in page and bfp.leaflet_css().count("url(images") == 0


def test_square_and_planted_area_corners_equal_the_field_kit_maths(kit, pack):
    """The map draws the 100 m grid square and the planted rectangle from corners given by the build (same block_geometry and transform), not from a second formula in the browser."""
    from pyproj import Transformer
    tr = Transformer.from_crs(fk.CFG["site_crs"], "EPSG:4326", always_xy=True)
    rows = list(csv.DictReader(io.StringIO(kit[0])))
    for r, b in zip(rows, pack["blocks"]):
        g = pal.block_geometry(float(r["spacing_m"]), int(float(r["trees_per_row"])), int(float(r["rows"])), int(float(r["trees_planned"])))
        half = g["side_m"] / 2.0
        ll = lambda x, y: [round(v, 7) for v in reversed(tr.transform(float(r["utm_e"]) - half + x, float(r["utm_n"]) - half + y))]
        s_ = g["side_m"]
        assert b["square"] == [ll(0, 0), ll(s_, 0), ll(s_, s_), ll(0, s_)], r["block_ref"]
        assert b["area"] == [ll(*g["corners"][k]) for k in ("SW", "SE", "NE", "NW")], r["block_ref"]
        assert b["area"][0] == b["start"]                                          # the START corner is the SW corner of the planted rectangle
        c = b["centre"]
        mid = [sum(p[0] for p in b["square"]) / 4, sum(p[1] for p in b["square"]) / 4]
        assert abs(mid[0] - c[0]) < 3e-6 and abs(mid[1] - c[1]) < 3e-6             # the square is centred on the block waypoint (within the CSV's 0.1 m rounding)


def test_the_embedded_data_cannot_close_the_script(pack):
    evil = json.loads(json.dumps(pack))
    evil["blocks"][0]["note"] = "</script><script>alert(1)</script><!-- x"
    page = bfp.render_page(evil)
    assert page.count('id="pack-data"') == 1 and "</script><script>alert(1)" not in page


def test_every_text_the_person_reads_is_in_the_strings_table():
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    keys = set(strings_tables()["en"])
    literals = set(re.findall(r"'(\w+)'", app))
    used = {k for k in re.findall(r"\bt\('(\w+)'", app) if not k.endswith("_") and k not in ("s", "how", "intro", "before")}      # 'reason_' + word, 's' + step + 'Title', 'how' + n ... are built at run time
    assert used <= keys, sorted(used - keys)                                       # every t('key') exists
    dynamic = lambda k: k.startswith(("reason_", "dir_")) or re.fullmatch(r"(s[1-4]Title|how[1-4]|before[1-5]|intro[1-3](Title)?)", k)     # built from a prefix and a number or a word at run time
    unused = {k for k in keys - literals if not dynamic(k)}
    assert not unused, sorted(unused)                                              # and every key is used
    assert {k for k in keys if k.startswith("reason_")} == {"reason_" + r for r in re.findall(r"'(\w+)'", re.search(r"const REASONS = \[(.*?)\]", (ROOT / "fieldpack" / "core.js").read_text(encoding="utf-8")).group(1))}
    assert {k for k in keys if k.startswith("dir_")} == {"dir_" + p for p in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")}                  # the eight directions, in words
    assert not re.search(r"textContent\s*=\s*'[^']|createTextNode\('[^']", app)    # no sentence is written straight into the code (an empty string is fine)
    assert "innerHTML" not in app                                                  # nothing from the plan is ever read as HTML


def test_saving_goes_through_the_guarded_wrapper():
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    core = (ROOT / "fieldpack" / "core.js").read_text(encoding="utf-8")
    # the marks and the settings (language, intro seen, steps, checklist) both go through makeStore, which wraps every read and write in try / catch
    assert app.count("window.localStorage") == 2 and app.count("makeStore(() => window.localStorage") == 2 and "localStorage." not in app
    assert "try {" in core[core.index("function makeStore"):]


def test_phone_layout_rules_in_the_css():
    css = (ROOT / "fieldpack" / "app.css").read_text(encoding="utf-8")
    assert re.search(r"\.btn \{[^}]*min-height: 5\d+px", css)                                                              # tap targets of at least 52 px
    assert re.search(r"\.chip \{[^}]*width: 48px; height: 48px", css) and re.search(r"\.rbtn \{ width: 48px; height: 48px", css)    # chips and the round map buttons: 48 px
    assert re.search(r"\.btnrow \.primary \{[^}]*min-height: 60px", css)                                                   # "Planted here": 60 px (56 px or more)
    assert "color: var(--fg)" in css and "--fg: #000" in css and "--bg: #fff" in css                                       # black on white for sunlight
    assert re.search(r"body \{[^}]*font: 18px", css) and re.search(r"input\[type=text\] \{[^}]*font-size: 16px", css)       # inputs 16 px: iOS does not zoom
    assert "height: 100dvh" in css and "height: 100vh" in css                                                              # the screen height follows the phone's address bar (100vh stays as the fallback)
    assert css.count("env(safe-area-inset-") >= 8                                                                           # notches and home bars: top bar, banner, sheet and buttons keep clear
    assert "viewport-fit=cover" in (ROOT / "fieldpack" / "template.html").read_text(encoding="utf-8")
    assert "[hidden] { display: none !important; }" in css


# ---------------------------------------------------------------- the trees: the SAME maths as field_kit.py
def independent_trees(r):
    """Per-tree lat/lon straight from palettes.block_geometry and field_kit's own transform; written here again on purpose (it is the test's reference, not the builder's code)."""
    from pyproj import Transformer
    tr = Transformer.from_crs(fk.CFG["site_crs"], "EPSG:4326", always_xy=True)
    g = pal.block_geometry(float(r["spacing_m"]), int(float(r["trees_per_row"])), int(float(r["rows"])), int(float(r["trees_planned"])))
    half = g["side_m"] / 2.0
    out = []
    for t in g["trees"][: int(float(r["trees_planned"]))]:
        lon, lat = tr.transform(float(r["utm_e"]) - half + t["x"], float(r["utm_n"]) - half + t["y"])
        out.append((t["k"], round(lat, 7), round(lon, 7)))
    return out


def test_per_tree_coordinates_equal_the_field_kit_maths_for_every_tree(kit, pack):
    rows = list(csv.DictReader(io.StringIO(kit[0])))
    checked = 0
    for r, b in zip(rows, pack["blocks"]):
        want = independent_trees(r)
        got = [(t[0], t[1], t[2]) for t in b["trees"]]
        assert got == want, r["block_ref"]                                           # exactly equal, tree by tree (7 decimals = 1 cm)
        checked += len(got)
    assert checked == 50


def test_start_and_first_tree_equal_field_kit_attach_geometry(kit, pack):
    df = pd.read_csv(io.StringIO(kit[0]))
    df = fk.attach_geometry(df)                                                       # the kit builder's own function, on the same rounded centres
    for (_, r), b in zip(df.iterrows(), pack["blocks"]):
        g = r["geo"]
        assert (b["start"][0], b["start"][1]) == (round(g["ll"]["SW"][0], 7), round(g["ll"]["SW"][1], 7)), b["ref"]
        assert (b["trees"][0][1], b["trees"][0][2]) == (round(g["first_ll"][0], 7), round(g["first_ll"][1], 7)), b["ref"]


def test_trees_also_agree_with_the_columns_the_kit_shipped(kit, pack):
    """The kit's own columns come from the unrounded centre (blocks.csv keeps 0.1 m), so they may differ by centimetres, not more."""
    rows = list(csv.DictReader(io.StringIO(kit[0])))
    worst = 0.0
    for r, b in zip(rows, pack["blocks"]):
        for got, want in (((b["trees"][0][1], b["trees"][0][2]), (float(r["first_tree_lat"]), float(r["first_tree_lon"]))), (tuple(b["start"]), (float(r["start_lat"]), float(r["start_lon"])))):
            d = fv.distance_m(got[0], got[1], want[0], want[1])
            worst = max(worst, d)
    assert worst < 0.25, worst                                                        # metres: under 25 cm (in practice a few cm)


def test_tree_order_is_the_readme_order(pack):
    """Tree 1 is half a spacing east and north of START; trees run east along the row, then one spacing north; a block with fewer trees than its capacity plants 1..N."""
    from pyproj import Transformer
    to_utm = Transformer.from_crs("EPSG:4326", fk.CFG["site_crs"], always_xy=True)
    for b in pack["blocks"]:
        sp, per, n = b["spacing_m"], b["per_row"], b["n"]
        e0, n0 = to_utm.transform(b["start"][1], b["start"][0])
        pts = [to_utm.transform(t[2], t[1]) for t in b["trees"]]
        assert len(pts) == n and [t[0] for t in b["trees"]] == list(range(1, n + 1))
        for k, (e, nn) in enumerate(pts):
            j, i = divmod(k, per)
            assert abs((e - e0) - sp * (i + 0.5)) < 0.02 and abs((nn - n0) - sp * (j + 0.5)) < 0.02, (b["ref"], k + 1)    # centimetres
        assert b["side_m"] == per * sp or abs(b["side_m"] - per * sp) < 0.51          # the kit rounds the side for display


def test_a_kit_that_was_changed_or_made_with_another_formula_is_refused(tmp_path):
    bad = tmp_path / "k"
    shutil.copytree(FIXTURE, bad)
    (bad / "blocks.csv").write_text((bad / "blocks.csv").read_text(encoding="utf-8").replace("CHE-B01,1260", "CHE-B01,1261", 1), encoding="utf-8", newline="")
    with pytest.raises(bfp.PackError, match="does not match manifest"):
        bfp.read_kit(bad)
    other = tmp_path / "k2"
    shutil.copytree(FIXTURE, other)
    text = (other / "blocks.csv").read_text(encoding="utf-8").replace("14.706013", "14.706513", 1)             # the first tree moved 55 m north in the kit's own column
    man = json.loads((other / "manifest.json").read_text(encoding="utf-8"))
    import hashlib
    for f in man["files"]:
        if f["name"] == "blocks.csv":
            f["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()                                    # a careful editor who also fixed the manifest
    (other / "blocks.csv").write_text(text, encoding="utf-8", newline="")
    (other / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(bfp.PackError, match="first tree"):
        bfp.build_pack(*bfp.read_kit(other))


# ---------------------------------------------------------------- the page's own maths, tested with node
@needs_node
@needs_node
@needs_node
def test_core_tests_in_node():
    r = subprocess.run([NODE, "--test", str(ROOT / "fieldpack" / "core.test.mjs")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-2500:] + r.stderr[-1500:]
    assert "# fail 0" in r.stdout and "# pass 19" in r.stdout


def run_sim(payload):
    r = subprocess.run([NODE, str(ROOT / "tests" / "helpers" / "fieldpack_sim.cjs")], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


@needs_node
def test_distance_matches_the_python_importer_and_bearing_matches_the_ellipsoid():
    import random
    from pyproj import Geod
    rnd = random.Random(7)
    pairs = [[14.64 + rnd.random() * 0.12, 121.08 + rnd.random() * 0.2] for _ in range(200)]
    pairs = [[a[0], a[1], b[0], b[1]] for a, b in zip(pairs[:100], pairs[100:])] + [[14.70 + rnd.random() * 0.01, 121.12 + rnd.random() * 0.01, 14.70 + rnd.random() * 0.002, 121.12 + rnd.random() * 0.002] for _ in range(100)]
    out = json.loads(run_sim({"mode": "distance", "pairs": pairs}))
    geod = Geod(ellps="WGS84")
    for p, (d, b) in zip(pairs, out):
        assert abs(d - fv.distance_m(*p)) < 1e-6                                       # the very formula the importer uses
        az, _, _ = geod.inv(p[1], p[0], p[3], p[2])
        diff = abs(((az % 360) - b + 180) % 360 - 180)
        assert diff < (0.3 if d > 50 else 3.0), (p, az, b)                               # a sphere and the ellipsoid agree on direction to a fraction of a degree (more slack for tiny distances)


# ---------------------------------------------------------------- the results file is accepted by the dashboard's existing import
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import api_v2
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture()
def fresh(client, tmp_path, monkeypatch):
    d = client.app.state.data
    monkeypatch.setattr(d, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(d, "work", tmp_path)
    monkeypatch.setitem(d.cfg, "field_exclude_not_plantable", True)
    fv.connect(d.field_db).close()
    import api_v2
    api_v2.refresh_field(d)
    return d


def iso(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


@needs_node
@needs_data
def test_the_dashboard_import_accepts_the_results_file(client, fresh, tmp_path):
    body = {"purpose": "urban", "n_saplings": 60, "barangay": "MALY", "campaign": {"name": "pack", "unit": "t"}}
    plan = client.post("/plan-event", json=body).json()
    plan_id = plan["plan_id"]
    csv_path = Path(fresh.work) / "plans" / f"{plan_id}.csv"
    kit_dir = fk.make_kit(csv_path, tmp_path / "kits", pdf=False, data_dir=fresh.root)["kit_dir"]
    pk = bfp.build_pack(*bfp.read_kit(kit_dir))                                       # the pack of a REAL kit of a real plan: plan_id and check_code come from it
    assert pk["plan_id"] == plan_id and pk["check_code"] == fk.check_code(csv_path)
    blocks = [b for b in pk["blocks"] if b["n"] >= 3]
    assert len(blocks) >= 4
    acts = []
    fix = lambda b, k: {"lat": b["trees"][k - 1][1] + 2e-6, "lon": b["trees"][k - 1][2] - 2e-6, "acc": 6.5}
    b0, b1, b2, b3 = blocks[:4]
    for k in (1, 2, 3):                                                                # block 0: three trees planted, the rest still to do
        acts.append({"ref": b0["ref"], "k": k, "s": "planted", "t": iso(50 - k), **fix(b0, k)})
    for k in range(1, b1["n"] + 1):                                                    # block 1: every tree planted
        acts.append({"ref": b1["ref"], "k": k, "s": "planted", "t": iso(40 - k % 9), **fix(b1, k)})
    for k in range(1, b2["n"] + 1):                                                    # block 2: nothing can be planted, a rock
        acts.append({"ref": b2["ref"], "k": k, "s": "skipped", "reason": "rock_or_ledge", "t": iso(30)})
    acts += [{"ref": b3["ref"], "k": 1, "s": "planted", "t": iso(20), **fix(b3, 1)}, {"ref": b3["ref"], "k": 2, "s": "planted", "t": iso(19), **fix(b3, 2)},
             {"ref": b3["ref"], "k": 3, "s": "skipped", "reason": "paved", "t": iso(18)}]       # block 3: two planted, one skipped
    text = run_sim({"mode": "csv", "pack": pk, "observer": "Ana Cruz", "actions": acts, "notice": "Prototype. GPS accuracy not yet field-tested. (pack " + pk["pack_id"] + ")"})
    rows = list(csv.DictReader(io.StringIO(text)))
    header = next(csv.reader(io.StringIO(text)))
    original = next(csv.reader(io.StringIO((kit_dir / "blocks.csv").read_text(encoding="utf-8"))))
    assert header[: len(original)] == original                                         # the SAME columns, in the same order, as blocks.csv
    by = {r["block_ref"]: r for r in rows}
    assert (by[b0["ref"]]["status"], by[b0["ref"]]["trees_planted"]) == ("planted", "3")
    assert (by[b1["ref"]]["status"], by[b1["ref"]]["trees_planted"]) == ("planted", str(b1["n"]))
    assert (by[b2["ref"]]["status"], by[b2["ref"]]["reason"]) == ("rock_or_ledge", "rock_or_ledge")
    assert (by[b3["ref"]]["status"], by[b3["ref"]]["trees_planted"]) == ("planted", "2") and "paved" in by[b3["ref"]]["note"]
    assert all(r["moved_lat"] == "" and r["moved_lon"] == "" for r in rows)            # a tree's position is not the block's centre: never filled by the page
    assert all(r["pack_notice"].startswith("Prototype. GPS accuracy not yet field-tested.") for r in rows)          # the warning travels with every row of the results file
    assert all(r["plan_id"] == plan_id and r["check_code"] == pk["check_code"] for r in rows)
    undecided = [r for r in rows if r["block_ref"] not in (b0["ref"], b1["ref"], b2["ref"], b3["ref"])]
    assert undecided and all(r["status"] == "" and r["trees_planted"] == "" for r in undecided)

    # the dashboard's own import ("Import field checks (CSV)" = POST /field-checks/import)
    r = client.post("/field-checks/import", params={"observer": "Team leader"}, content=("﻿" + text).encode("utf-8"), headers={"content-type": "text/csv"})
    assert r.status_code == 200, r.text
    rep = r.json()
    assert (rep["accepted"], rep["rejected"], rep["duplicates"]) == (4, 0, 0), rep
    assert rep["blank"] == len(rows) - 4
    cur = {x["point_id"]: x for x in client.get("/field-checks", params={"limit": 1000}).json()["points"]}
    pid = {b["ref"]: b["point_id"] for b in pk["blocks"]}
    assert cur[pid[b0["ref"]]]["status"] == "planted" and cur[pid[b0["ref"]]]["trees_planted"] == 3
    assert cur[pid[b1["ref"]]]["trees_planted"] == b1["n"]
    assert cur[pid[b2["ref"]]]["status"] == "not_plantable" and cur[pid[b2["ref"]]]["reason"] == "rock_or_ledge"
    assert cur[pid[b3["ref"]]]["trees_planted"] == 2
    assert cur[pid[b0["ref"]]]["observer"] == "Ana Cruz"                               # the name written by the page is kept (the importer's own name is only the fallback)
    again = client.post("/field-checks/import", params={"observer": "Team leader"}, content=text.encode("utf-8"), headers={"content-type": "text/csv"}).json()
    assert (again["accepted"], again["duplicates"]) == (0, 4)                          # importing the same file twice adds nothing

    # a results file of ANOTHER plan state is refused row by row (the check code protects against a changed plan)
    wrong = text.replace(pk["check_code"], "deadbeef")
    rej = client.post("/field-checks/import", params={"observer": "Team leader"}, content=wrong.encode("utf-8"), headers={"content-type": "text/csv"}).json()
    assert rej["accepted"] == 0 and rej["rejected"] == 4 and "check code" in rej["rows"][0]["reason"]

def test_nothing_null_or_undefined_can_become_text_on_the_page():
    """The first map version showed the word "null" under the Start GPS button: a null in a list given to replaceChildren becomes the text "null". Now every list goes through clean(),
    and h() skips null, undefined and true/false. (The browser checks look for the words null / undefined / NaN and for missing text keys on every screen.)"""
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    assert "const clean = (list) => list.filter((x) => x !== null && x !== undefined && typeof x !== 'boolean')" in app
    assert app.count("replaceChildren(...clean(") == 2                                                         # the chips and the whole screen
    others = [l.strip() for l in app.splitlines() if "replaceChildren(" in l and "replaceChildren(...clean(" not in l]
    assert len(others) == 2 and any("ui.attrib" in l for l in others) and any("ui.miniSvg.replaceChildren(svg)" in l for l in others)      # the credit line and the little drawing: fixed nodes, never null
    assert "for (const kid of clean(kids.flat()))" in app
    assert not re.search(r"kids\.push\(.*\?.*: null\)", app)                                                   # no conditional null pushed into a plain list
    chips = app.split("function refreshChips")[1].split("function updateTopbar")[0]
    assert chips.count("t('reason_' + r.reason)") == 1 and "r.s === 'planted' ? t('recPlanted') : t('recSkipped'" in chips     # the reason is only looked up for a skipped tree


def test_a1c_screen_has_the_parts_that_were_asked_for():
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    core = (ROOT / "fieldpack" / "core.js").read_text(encoding="utf-8")
    for must in ("class: 'topbar'", "class: 'stage'", "class: 'sheet'", "class: 'chips'", "class: 'mapbtns'", "class: 'rbtn'", "btnPlanted", "btnSkip", "detailsTitle"):
        assert must in app, must
    # the wake lock is wrapped: a missing feature or a refusal is silent
    wake = app.split("async function requestWake")[1].split("document.addEventListener('visibilitychange'")[0]
    assert "try {" in wake and "catch (e)" in wake and "navigator.wakeLock" in wake and "release" in wake
    assert "document.addEventListener('visibilitychange'" in app and "wake.want" in app
    # iOS compass permission is only asked inside the tap on Start GPS, and the listeners never wait for it
    assert app.index("startCompass() // first") < app.index("requestWake()\n    const p = gpsProblem()")
    assert "DeviceOrientationEvent.requestPermission" in app and "'deviceorientationabsolute'" in app
    assert "webkitCompassHeading" in core and "compassHeading" in core
    # map rotation: the container is turned with CSS, markers and labels are turned back; no rotation plugin is used
    css = (ROOT / "fieldpack" / "app.css").read_text(encoding="utf-8")
    assert "rotate(calc(-1 * var(--maprot, 0deg)))" in css and "--maprot" in app
    assert "leaflet-rotate" not in app and "RotatedMarker" not in app
    assert not re.search(r"\bfetch\(|XMLHttpRequest|sendBeacon|WebSocket", app)


def test_the_results_file_carries_the_prototype_notice_in_every_row(pack):
    sim = subprocess.run([NODE, "-e", "const C = require(process.argv[1]); const p = JSON.parse(require('fs').readFileSync(0, 'utf8')); process.stdout.write(C.exportCsv(p, C.emptyState(), undefined, 'Prototype. GPS accuracy not yet field-tested. (pack ' + p.pack_id + ')'))", str(ROOT / "fieldpack" / "core.js")],
                         input=json.dumps(pack), capture_output=True, text=True, timeout=60)
    assert sim.returncode == 0, sim.stderr
    rows = list(csv.DictReader(io.StringIO(sim.stdout)))
    assert len(rows) == len(pack["blocks"]) and all(r["pack_notice"].startswith("Prototype. GPS accuracy not yet field-tested.") for r in rows)
    assert all(r["status"] == "" and r["trees_planted"] == "" for r in rows)                  # nothing was marked: nothing is invented


def test_the_first_tree_offset_comes_from_the_one_layout_function(kit, pack):
    """The steps say "plant tree 1 at X m east and X m north of the stake": X comes from palettes.block_geometry through the builder, not from a formula in the browser."""
    rows = list(csv.DictReader(io.StringIO(kit[0])))
    for r, b in zip(rows, pack["blocks"]):
        g = pal.block_geometry(float(r["spacing_m"]), int(float(r["trees_per_row"])), int(float(r["rows"])), int(float(r["trees_planned"])))
        assert b["first_offset_m"] == [round(g["first_tree"][0] - g["corners"]["SW"][0], 3), round(g["first_tree"][1] - g["corners"]["SW"][1], 3)], r["block_ref"]
        assert b["first_offset_m"] == [b["spacing_m"] / 2, b["spacing_m"] / 2]                      # half a spacing east and north: what the kit README says
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    assert "first_offset_m" in app and not re.search(r"spacing\w*\s*\*\s*\(\s*\w+\s*\+\s*0\.5\s*\)", app)       # the page uses the offset it is given; no layout formula in the page
