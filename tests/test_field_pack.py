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
def test_the_sample_kit_is_the_one_named_in_the_task(kit, pack):
    assert pack["plan_id"] == "plan_urban_20261013_032648" and pack["check_code"] == "3b2afb9e"
    assert len(pack["blocks"]) == 6 and sum(b["n"] for b in pack["blocks"]) == 50
    assert re.fullmatch(r"[0-9a-f]{8}", pack["pack_id"])


def test_the_page_is_one_self_contained_file_and_small(pack, tmp_path):
    f = tmp_path / "p.html"
    page = bfp.render_page(pack)
    f.write_text(page, encoding="utf-8")
    assert f.stat().st_size < 120_000                                              # the sample kit: 6 blocks, 50 trees (about 45 KB)
    assert "Prototype. GPS accuracy not yet field-tested." in page                 # the permanent banner text is in the strings table that is inlined
    assert 'name="viewport"' in page and 'id="banner"' in page
    assert "/*__" not in page                                                      # every placeholder was filled
    assert not re.search(r"<script[^>]+src=|<link[^>]+href=|@import|url\(", page)  # nothing is loaded from outside
    assert not re.search(r"\bfetch\(|XMLHttpRequest|sendBeacon|WebSocket", page)   # and nothing is sent anywhere
    bare = page.replace("http://www.w3.org/2000/svg", "")                          # the SVG namespace name is not an address that is visited
    assert "http://" not in bare and "https://" not in bare
    embedded = json.loads(re.search(r'<script type="application/json" id="pack-data">(.*?)</script>', page, re.S).group(1).replace("<\\/", "</"))
    assert embedded == pack                                                        # the plan travels inside the page: plan_id, check_code and every block


def test_the_embedded_data_cannot_close_the_script(pack):
    evil = json.loads(json.dumps(pack))
    evil["blocks"][0]["note"] = "</script><script>alert(1)</script><!-- x"
    page = bfp.render_page(evil)
    assert page.count('id="pack-data"') == 1 and "</script><script>alert(1)" not in page


def test_every_text_the_person_reads_is_in_the_strings_table():
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    strings = (ROOT / "fieldpack" / "strings.js").read_text(encoding="utf-8")
    keys = set(re.findall(r"^\s{2}(\w+):", strings, re.M))
    literals = set(re.findall(r"'(\w+)'", app))
    used = {k for k in re.findall(r"\bt\('(\w+)'", app) if not k.endswith("_")}                  # 'reason_' + word is built at run time
    assert used <= keys, sorted(used - keys)                                       # every t('key') exists
    dyn = {k for k in keys if k.startswith("reason_")}
    unused = {k for k in keys - literals if k not in dyn}
    assert not unused, sorted(unused)                                              # and every key is used (the reasons are built as 'reason_' + word)
    assert dyn == {"reason_" + r for r in re.findall(r"'(\w+)'", re.search(r"const REASONS = \[(.*?)\]", (ROOT / "fieldpack" / "core.js").read_text(encoding="utf-8")).group(1))}
    assert not re.search(r"textContent\s*=\s*'|createTextNode\('", app)              # no sentence is written straight into the code
    assert "innerHTML" not in app                                                  # nothing from the plan is ever read as HTML


def test_saving_goes_through_one_guarded_wrapper():
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    core = (ROOT / "fieldpack" / "core.js").read_text(encoding="utf-8")
    assert app.count("window.localStorage") == 1 and "makeStore(() => window.localStorage" in app and "localStorage." not in app
    assert "try {" in core[core.index("function makeStore"):]


def test_phone_layout_rules_in_the_css():
    css = (ROOT / "fieldpack" / "app.css").read_text(encoding="utf-8")
    assert re.search(r"\.btn \{[^}]*min-height: 5\d+px", css) and re.search(r"\.tree \{[^}]*min-height: 5\d+px", css)     # tap targets of at least 52 px
    assert "color: var(--fg)" in css and "--fg: #000" in css and "--bg: #fff" in css                                       # black on white for sunlight
    assert re.search(r"body \{[^}]*font: 18px", css)


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
def test_core_tests_in_node():
    r = subprocess.run([NODE, "--test", str(ROOT / "fieldpack" / "core.test.mjs")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-2500:] + r.stderr[-1500:]
    assert "# fail 0" in r.stdout and "# pass 10" in r.stdout


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
    text = run_sim({"mode": "csv", "pack": pk, "observer": "Ana Cruz", "actions": acts})
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
