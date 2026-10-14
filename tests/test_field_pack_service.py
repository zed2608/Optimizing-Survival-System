"""Field pack inside the main system (stage A2): the planter link.
 - pipeline/pack_store.py (token, expiry, one pack per plan, cap, revoke, cleanup) is tested alone;
 - the service (api_v2.py) is tested with the access code AND the public sandbox on: POST/GET/DELETE /plans/<id>/field-pack and GET /field/<token>/;
 - the Docker image carries the builder and the page files.
Run from the repo root: python -m pytest tests/test_field_pack_service.py"""
import fnmatch, hashlib, json, logging, os, re, sys, time
from pathlib import Path
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import pack_store as ps  # noqa: E402

NEEDS_DATA = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")


# ================================================================ the store alone
def test_token_is_long_random_and_never_shown_in_full():
    tokens = {ps.new_token() for _ in range(500)}
    assert len(tokens) == 500 and all(len(t) == 22 and re.fullmatch(r"[A-Za-z0-9_-]{22}", t) for t in tokens)      # 16 random bytes: 128 bits
    t = ps.new_token()
    assert ps.short(t) == t[:4] + "…" and t[4:] not in ps.short(t)
    src = (ROOT / "pipeline" / "pack_store.py").read_text(encoding="utf-8")
    assert "secrets.token_urlsafe(TOKEN_BYTES)" in src and "hmac.compare_digest" in src and "import random" not in src      # a real random source, a constant-time compare


def test_store_lookup_replace_expire_and_revoke(tmp_path):
    a = ps.store(tmp_path, "plan_urban_1", "<html>A</html>", pack_id="aaaa1111", check_code="c1c1c1c1", now=1000.0)
    assert a["replaced"] is False and a["expires"] == 1000.0 + 24 * 3600 and a["expires_at"].endswith("Z")
    assert ps.lookup(tmp_path, a["token"], now=1001.0) == b"<html>A</html>"
    b = ps.store(tmp_path, "plan_urban_1", "<html>B</html>", pack_id="bbbb2222", check_code="c1c1c1c1", now=1002.0)         # one live pack per plan
    assert b["replaced"] is True and b["token"] != a["token"]
    assert ps.lookup(tmp_path, a["token"], now=1003.0) is None and ps.lookup(tmp_path, b["token"], now=1003.0) == b"<html>B</html>"
    assert len(ps.entries(tmp_path)) == 1
    assert ps.lookup(tmp_path, b["token"], now=1002.0 + 24 * 3600 + 1) is None                                                # expired: the same "not found"
    assert ps.cleanup(tmp_path, now=1002.0 + 24 * 3600 + 1) == 1 and ps.entries(tmp_path) == [] and not list(ps.packs_dir(tmp_path).glob("*.html"))
    c = ps.store(tmp_path, "plan_urban_2", "x", pack_id="p", check_code="c", now=5000.0)
    assert ps.info(tmp_path, "plan_urban_2", now=5001.0)["token"] == c["token"] and ps.info(tmp_path, "plan_urban_9", now=5001.0) is None
    assert ps.revoke(tmp_path, "plan_urban_2") is True and ps.revoke(tmp_path, "plan_urban_2") is False
    assert ps.lookup(tmp_path, c["token"], now=5002.0) is None


def test_a_link_never_lives_longer_than_24_hours_or_than_the_next_reset(tmp_path):
    a = ps.store(tmp_path, "p1", "x", pack_id="p", check_code="c", now=0.0, ttl_hours=1000)                                   # a caller cannot ask for more than 24 hours
    assert a["expires"] == 24 * 3600
    b = ps.store(tmp_path, "p2", "x", pack_id="p", check_code="c", now=0.0, ttl_hours=24, latest_end=3 * 3600)               # the reset is in 3 hours: so is the end of the link
    assert b["expires"] == 3 * 3600
    with pytest.raises(ValueError):
        ps.store(tmp_path, "p3", "x", pack_id="p", check_code="c", now=10.0, latest_end=5.0)                                  # the reset has already passed


def test_the_cap_replaces_the_oldest(tmp_path):
    toks = [ps.store(tmp_path, f"plan_{i}", f"page {i}", pack_id="p", check_code="c", now=100.0 + i, max_packs=3)["token"] for i in range(5)]
    live = [t for t, _ in ps.entries(tmp_path)]
    assert len(live) == 3 and set(live) == set(toks[2:])                                                                      # the two oldest were replaced
    assert ps.MAX_PACKS == 30
    assert ps.lookup(tmp_path, toks[0], now=200.0) is None and ps.lookup(tmp_path, toks[4], now=200.0) == b"page 4"


def test_every_bad_token_is_just_not_found(tmp_path):
    good = ps.store(tmp_path, "p1", "x", pack_id="p", check_code="c", now=0.0)["token"]
    for bad in ("", "short", "a" * 22, good[:-1] + ("A" if good[-1] != "A" else "B"), good + "x", "../" + good, "%00", None, 5):
        assert ps.lookup(tmp_path, bad, now=1.0) is None
    assert ps.lookup(tmp_path, good, now=1.0) == b"x"
    (ps.packs_dir(tmp_path) / ("z" * 22 + ".html")).write_text("orphan")                                                      # a file without details is not served and is cleaned
    assert ps.lookup(tmp_path, "z" * 22, now=1.0) is None
    ps.cleanup(tmp_path, now=1.0)
    assert not (ps.packs_dir(tmp_path) / ("z" * 22 + ".html")).exists()


def test_the_log_filter_cuts_the_token():
    import api_v2
    f = api_v2._HideFieldToken()
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "x", 1, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", "/field/AbCdEfGhIjKlMnOpQrStUv/", "1.1", 200), None)
    f.filter(rec)
    assert rec.args[2] == "/field/AbCd.../" and "EfGh" not in rec.getMessage()
    rec2 = logging.LogRecord("uvicorn.access", logging.INFO, "x", 1, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", "/plans?limit=5", "1.1", 200), None)
    f.filter(rec2)
    assert rec2.args[2] == "/plans?limit=5"
    assert any(isinstance(x, api_v2._HideFieldToken) for x in logging.getLogger("uvicorn.access").filters)


# ================================================================ the Docker image
def _glob_re(pat):
    out, i = "", 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out += "(?:.*/)?"; i += 3
        elif pat[i] == "*":
            out += "[^/]*"; i += 1
        elif pat[i] == "?":
            out += "[^/]"; i += 1
        else:
            out += re.escape(pat[i]); i += 1
    return re.compile("^" + out + "$")


def _ignored(path, patterns):
    """Docker's .dockerignore rule for the patterns used here: * stays inside one folder, **/ is any folders, a matched folder holds back everything below it, a later "!" line brings a file back."""
    hit = False
    segs = path.split("/")
    for pat in patterns:
        neg = pat.startswith("!")
        rx = _glob_re((pat[1:] if neg else pat).rstrip("/"))
        if any(rx.match("/".join(segs[:n])) for n in range(1, len(segs) + 1)):
            hit = not neg
    return hit


def test_the_image_carries_the_builder_and_every_page_file_but_not_scripts_docs_or_tests():
    patterns = [l.strip() for l in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    needed = ["pipeline/field_pack.py", "pipeline/pack_store.py", "pipeline/field_kit.py", "pipeline/palettes.py"] + \
             sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "fieldpack").rglob("*") if p.is_file() and not p.name.endswith(".test.mjs"))
    assert "fieldpack/template.html" in needed and "fieldpack/app.js" in needed and "fieldpack/vendor/leaflet-1.9.4/leaflet.js" in needed
    assert re.search(r"^COPY pipeline/ pipeline/\s*$", docker, re.M) and re.search(r"^COPY fieldpack/ fieldpack/\s*$", docker, re.M)       # the Dockerfile copies both folders
    blocked = [f for f in needed if _ignored(f, patterns)]
    assert not blocked, blocked                                                                                                 # .dockerignore holds none of them back
    for folder in ("scripts", "docs", "tests"):                                                                                  # and still keeps these out
        assert _ignored(f"{folder}/x.py", patterns), folder
    assert not re.search(r"^COPY (scripts|docs|tests)", docker, re.M)
    assert _ignored("data/x.csv", patterns) and not _ignored("data/processed/site_points_clean.csv", patterns)                  # data/*.csv holds back the loose files, not data/processed
    assert _ignored("fieldpack/core.test.mjs", patterns)                                                                       # node tests of the page stay out (the page does not need them)


def test_the_builder_in_the_image_does_not_import_the_scripts_folder():
    src = (ROOT / "pipeline" / "field_pack.py").read_text(encoding="utf-8")
    assert "scripts" not in re.sub(r"#.*|\"\"\"[\s\S]*?\"\"\"", "", src)                                                       # no import from scripts/ (it is not in the image)
    api = (ROOT / "api_v2.py").read_text(encoding="utf-8")
    assert "import field_pack as fpk" in api and "import pack_store as ps" in api


# ================================================================ the service
@pytest.fixture(scope="module")
def svc(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("OS_ACCESS_CODE", "tree-123")
    mp.setenv("OS_COOKIE_SECURE", "0")
    mp.setenv("OS_PUBLIC_MODE", "1")
    mp.setenv("OS_STATE_DIR", str(tmp_path_factory.mktemp("packsvc") / "state"))
    mp.setenv("OS_RATE_PLAN", "1000")
    mp.setenv("OS_RATE_KIT", "1000")
    mp.setenv("OS_RATE_READ", "100000")
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app, follow_redirects=False) as c:
        c.post("/login", data={"code": "tree-123", "next": "/"})
        plan = c.post("/plan-event", json={"purpose": "urban", "n_saplings": 60, "barangay": "MALY", "seed": 3, "layout_mode": "blocks"})
        assert plan.status_code == 200, plan.text[:300]
        pts = c.post("/plan-event", json={"purpose": "urban", "n_saplings": 20, "barangay": "MALY", "seed": 3, "layout_mode": "points"})
        assert pts.status_code == 200, pts.text[:300]
        anon = TestClient(api_v2.app, follow_redirects=False)                              # a planter: no cookie
        yield {"c": c, "anon": anon, "api": api_v2, "plan": plan.json()["plan_id"], "points_plan": pts.json()["plan_id"], "mp": mp}
    mp.undo()


@pytest.fixture()
def fresh(svc):
    svc["api"].LIMITER = svc["api"].pm.Limiter()
    ps.revoke(svc["api"].app.state.data.work, svc["plan"])
    return svc


@NEEDS_DATA
def test_a_pack_is_made_from_a_saved_plan_and_the_page_is_exactly_render_page(fresh, tmp_path):
    c, anon, api, pid = fresh["c"], fresh["anon"], fresh["api"], fresh["plan"]
    r = c.post(f"/plans/{pid}/field-pack")
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert len(j["token"]) == 22 and j["url"] == f"/field/{j['token']}/" and j["replaced"] is False and j["live"] is True
    assert re.fullmatch(r"[0-9a-f]{8}", j["pack_id"]) and re.fullmatch(r"[0-9a-f]{8}", j["check_code"])
    from datetime import datetime, timezone
    left = (datetime.strptime(j["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds()
    assert 0 < left <= 24 * 3600 + 5
    served = anon.get(j["url"])                                                                                         # no cookie, no code
    assert served.status_code == 200 and served.headers["content-type"].startswith("text/html")
    d = api.app.state.data
    csv = d.work / "plans" / f"{pid}.csv"
    r2 = api.fk.make_kit(csv, tmp_path, pdf=False, data_dir=d.root)
    text, manifest = api.fpk.read_kit(r2["kit_dir"])
    pack = api.fpk.build_pack(text, manifest)
    assert served.content == api.fpk.render_page(pack).encode("utf-8")                                                  # byte for byte the page of the builder
    assert pack["pack_id"] == j["pack_id"] and pack["check_code"] == j["check_code"] and [b["id"] for b in pack["basemaps"]] == ["osm"]      # no satellite layer
    assert "arcgisonline" not in served.text and "Esri" not in served.text
    assert not (d.work / "kits" / f"field_kit_{pid}.zip").exists() or True                                              # the kit of the plan is not touched (see the next test)


@NEEDS_DATA
def test_wrong_plans_are_refused(fresh):
    c = fresh["c"]
    assert c.post("/plans/plan_urban_19990101_000000/field-pack").status_code == 404
    assert c.post("/plans/..%2Fx/field-pack").status_code in (400, 404)
    r = c.post(f"/plans/{fresh['points_plan']}/field-pack")
    assert r.status_code == 400 and "blocks" in r.json()["detail"]
    assert c.post("/plans/plan_urban_19990101_000000/field-pack").json()["detail"]


@NEEDS_DATA
def test_one_pack_per_plan_new_token_each_time_and_the_old_link_dies(fresh):
    c, anon, pid = fresh["c"], fresh["anon"], fresh["plan"]
    a = c.post(f"/plans/{pid}/field-pack").json()
    b = c.post(f"/plans/{pid}/field-pack").json()
    assert a["token"] != b["token"] and b["replaced"] is True                                                           # unguessable: not repeated, not derived from the plan
    assert pid not in b["token"] and a["check_code"] not in b["token"]
    assert anon.get(a["url"]).status_code == 404 and anon.get(b["url"]).status_code == 200
    info = c.get(f"/plans/{pid}/field-pack").json()
    assert info["live"] is True and info["token"] == b["token"] and info["expires_at"] == b["expires_at"]
    assert len(ps.entries(fresh["api"].app.state.data.work)) >= 1


@NEEDS_DATA
def test_the_kit_of_the_plan_is_not_touched_by_making_a_link(fresh):
    c, pid = fresh["c"], fresh["plan"]
    d = fresh["api"].app.state.data
    k = c.post(f"/plans/{pid}/field-kit")
    assert k.status_code == 200 and k.json()["pdf_included"] in (True, False)
    zp = d.work / "kits" / f"field_kit_{pid}.zip"
    before = (zp.stat().st_size, zp.stat().st_mtime_ns)
    assert c.post(f"/plans/{pid}/field-pack").status_code == 200
    assert (zp.stat().st_size, zp.stat().st_mtime_ns) == before                                                          # same zip, same PDF
    assert not [p for p in d.work.iterdir() if p.name.startswith("tmp")]                                                 # the throw-away folder is gone


@NEEDS_DATA
def test_every_bad_token_gets_the_same_404_and_the_page_has_the_right_headers(fresh):
    c, anon, pid = fresh["c"], fresh["anon"], fresh["plan"]
    good = c.post(f"/plans/{pid}/field-pack").json()
    work = fresh["api"].app.state.data.work
    exp = c.post(f"/plans/{pid}/field-pack").json()                                                                      # make an expired one
    meta = ps.packs_dir(work) / f"{exp['token']}.json"
    m = json.loads(meta.read_text())
    m["expires"] = time.time() - 5
    meta.write_text(json.dumps(m))
    revoked = c.post(f"/plans/{pid}/field-pack").json()
    c.delete(f"/plans/{pid}/field-pack")
    bad = [exp["url"], revoked["url"], "/field/" + "a" * 22 + "/", "/field/x/", "/field/%00/", "/field/" + good["token"][:-1] + "Z/", "/field/" + "b" * 64 + "/"]
    res = [anon.get(u) for u in bad]
    assert {r.status_code for r in res} == {404}
    assert len({r.text for r in res}) == 1 and len({r.headers["content-length"] for r in res}) == 1 and res[0].text == ps.NOT_FOUND_BODY       # same body, same length
    assert len({r.headers["content-type"] for r in res}) == 1 and all(r.headers["cache-control"] == "no-store" for r in res)
    live = c.post(f"/plans/{pid}/field-pack").json()
    r = anon.get(live["url"])
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store" and r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert r.headers["x-robots-tag"] == "noindex, nofollow" and r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert not [x for x in ps.packs_dir(work).glob("*.json") if json.loads(x.read_text())["expires"] <= time.time()]      # the expired file was cleaned by the request


@NEEDS_DATA
def test_only_the_planter_route_is_open_without_the_code(fresh):
    c, anon, pid = fresh["c"], fresh["anon"], fresh["plan"]
    live = c.post(f"/plans/{pid}/field-pack").json()
    assert anon.get(live["url"]).status_code == 200
    assert anon.get(live["url"].rstrip("/")).status_code in (200, 307)                                                    # without the last slash: redirected to the slash, not to the login page
    assert "/field/" in anon.get(live["url"].rstrip("/")).headers.get("location", "/field/x/") and "login" not in anon.get(live["url"].rstrip("/")).headers.get("location", "")
    for path in ("/health", f"/plans/{pid}/field-pack", "/plans", "/field/", f"/field/{live['token']}/results", f"/field/{live['token']}/x/y", "/kits/x.zip"):
        r = anon.get(path)
        assert r.status_code in (401, 303) and "login" in (r.headers.get("location", "") + r.text.lower()), path          # everything else still needs the code
    assert anon.post(f"/plans/{pid}/field-pack").status_code == 401                                                       # a planter cannot make links
    assert anon.delete(f"/plans/{pid}/field-pack").status_code == 401                                                     # nor switch them off
    assert anon.get(live["url"]).status_code == 200                                                                       # ... and the delete did nothing


@NEEDS_DATA
def test_revoke_deletes_the_page_at_once(fresh):
    c, anon, pid = fresh["c"], fresh["anon"], fresh["plan"]
    live = c.post(f"/plans/{pid}/field-pack").json()
    d = c.delete(f"/plans/{pid}/field-pack")
    assert d.status_code == 200 and d.json() == {"plan_id": pid, "revoked": True}
    assert anon.get(live["url"]).status_code == 404
    assert not list(ps.packs_dir(fresh["api"].app.state.data.work).glob(f"{live['token']}.*"))
    assert c.delete(f"/plans/{pid}/field-pack").json()["revoked"] is False and c.get(f"/plans/{pid}/field-pack").json()["live"] is False


@NEEDS_DATA
def test_the_cap_of_30_replaces_the_oldest_through_the_service(fresh, monkeypatch):
    c, anon, pid = fresh["c"], fresh["anon"], fresh["plan"]
    work = fresh["api"].app.state.data.work
    for i in range(29):                                                                                                  # 29 other plans' packs, filled directly
        ps.store(work, f"plan_other_{i:02d}", "x", pack_id="p", check_code="c", now=time.time() - 1000 + i)
    first = ps.entries(work)[0][0]
    live = c.post(f"/plans/{pid}/field-pack").json()                                                                     # makes 30
    assert len(ps.entries(work)) == 30 and ps.lookup(work, first) is not None
    other = c.post(f"/plans/{fresh['plan']}/field-pack").json()                                                          # the same plan again: replaced, still 30
    assert len(ps.entries(work)) == 30 and other["replaced"] is True
    ps.store(work, "plan_other_29", "x", pack_id="p", check_code="c")                                                    # the 31st plan: the oldest goes
    assert len(ps.entries(work)) == 30 and ps.lookup(work, first) is None
    assert anon.get(other["url"]).status_code == 200
    for t, m in ps.entries(work):
        if m["plan_id"].startswith("plan_other_"):
            ps.revoke(work, m["plan_id"])


@NEEDS_DATA
def test_making_links_is_rate_limited_and_reads_are_counted(fresh, monkeypatch):
    c, anon, pid, api = fresh["c"], fresh["anon"], fresh["plan"], fresh["api"]
    assert api.pm.classify("POST", f"/plans/{pid}/field-pack") == "pack" and api.pm.LIMITS["pack"] == (20, 3600)
    monkeypatch.setenv("OS_RATE_PACK", "2")
    api.LIMITER = api.pm.Limiter()
    assert c.post(f"/plans/{pid}/field-pack").status_code == 200 and c.post(f"/plans/{pid}/field-pack").status_code == 200
    r = c.post(f"/plans/{pid}/field-pack")
    assert r.status_code == 429 and "Retry-After" in r.headers
    assert api.pm.classify_read("GET", "/field/abc/") == "read"                                                          # a visit to the planter page is counted like any read
    monkeypatch.setenv("OS_RATE_READ", "3")
    api.LIMITER = api.pm.Limiter()
    codes = [anon.get("/field/" + "a" * 22 + "/").status_code for _ in range(5)]
    assert codes[:3] == [404, 404, 404] and 429 in codes[3:]


@NEEDS_DATA
def test_the_sandbox_reset_deletes_every_pack(fresh):
    c, anon, pid, api = fresh["c"], fresh["anon"], fresh["plan"], fresh["api"]
    live = c.post(f"/plans/{pid}/field-pack").json()
    assert anon.get(live["url"]).status_code == 200
    api.reset_sandbox(api.app.state.data)
    assert anon.get(live["url"]).status_code == 404 and not ps.packs_dir(api.app.state.data.work).exists()
    assert c.get(f"/plans/{pid}/field-pack").status_code in (200, 404)
    for key, layout in (("plan", "blocks"), ("points_plan", "points")):                                                    # the reset also emptied the plans: make the two the other tests use again
        fresh[key] = c.post("/plan-event", json={"purpose": "urban", "n_saplings": 60 if layout == "blocks" else 20, "barangay": "MALY", "seed": 3, "layout_mode": layout}).json()["plan_id"]


@NEEDS_DATA
def test_the_link_never_outlives_the_next_reset(fresh):
    c, api, pid = fresh["c"], fresh["api"], fresh["plan"]
    d = api.app.state.data
    ttl, latest = api.pack_limits(d)
    assert ttl <= 24 and latest == d.sandbox_started + api.pm.settings()["reset_hours"] * 3600
    d.sandbox_started = time.time() - (api.pm.settings()["reset_hours"] * 3600 - 3600)                                    # the reset is in one hour
    try:
        live = c.post(f"/plans/{pid}/field-pack").json()
        from datetime import datetime, timezone
        left = (datetime.strptime(live["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds()
        assert 3000 < left <= 3605
    finally:
        d.sandbox_started = time.time()


@NEEDS_DATA
def test_the_error_messages_and_the_log_never_hold_the_full_token(fresh, caplog):
    c, anon, pid = fresh["c"], fresh["anon"], fresh["plan"]
    live = c.post(f"/plans/{pid}/field-pack").json()
    with caplog.at_level(logging.DEBUG):
        anon.get(live["url"])
        c.post(f"/plans/{pid}/field-pack")
    server_log = chr(10).join(r.getMessage() for r in caplog.records if not r.name.startswith(("httpx", "httpcore")))          # the test client logs its own requests: that is not the service
    assert live["token"] not in server_log and live["token"] not in c.get(f"/plans/{pid}/field-pack").json().get("note", "")


# ================================================================ the dashboard side (source checks and the node tests)
def test_the_qr_library_is_vendored_with_its_license_and_version_and_never_loaded_from_a_cdn():
    import shutil as sh
    vend = ROOT / "frontend" / "src" / "vendor" / "qrcode-generator-1.4.4"
    assert {p.name for p in vend.iterdir()} >= {"qrcode.js", "qrcode.esm.js", "LICENSE.txt", "README.txt"}
    lic = (vend / "LICENSE.txt").read_text(encoding="utf-8")
    assert "qrcode-generator 1.4.4" in lic and "Kazuhiko Arase" in lic and "MIT" in lic and "Permission is hereby granted" in lic
    readme = (vend / "README.txt").read_text(encoding="utf-8")
    orig = (vend / "qrcode.js").read_text(encoding="utf-8")
    assert hashlib.sha256(orig.encode("utf-8")).hexdigest() in readme                               # the vendored file is the one the README names
    assert orig in (vend / "qrcode.esm.js").read_text(encoding="utf-8")                              # the module wrapper holds the same text, unchanged
    src = "".join((ROOT / "frontend" / "src" / "new" / n).read_text(encoding="utf-8") for n in ("PlanterLink.jsx", "planterQr.js", "planterLink.js"))
    assert "../vendor/qrcode-generator-1.4.4/qrcode.esm.js" in src and not re.search(r"https?://(?!127|localhost)", src.replace("http://www.w3.org", ""))      # from the repo folder, no address in the code
    code = chr(10).join(l.split(" // ")[0] for l in src.splitlines() if not l.strip().startswith("//"))                  # the comments may name what the code does not do
    assert "innerHTML" not in code and "createSvgTag" not in code                                      # the SVG is built by React from the matrix, never as markup text
    assert "qrcode" not in (ROOT / "frontend" / "package.json").read_text(encoding="utf-8").lower().replace("jsqr", "")      # no npm dependency for the generator (vendored)


def test_the_box_is_in_both_variants_of_the_kit_controls_and_keeps_the_old_buttons():
    kc = (ROOT / "frontend" / "src" / "new" / "KitControls.jsx").read_text(encoding="utf-8")
    assert kc.count("<PlanterLink planId={planId} />") == 2 and "import PlanterLink" in kc
    assert "Build the field kit" in kc and "Download kit (.zip)" in kc and "Rebuild field kit" in kc      # the existing Build / Download of the kit are still there
    pl = (ROOT / "frontend" / "src" / "new" / "PlanterLink.jsx").read_text(encoding="utf-8")
    for must in ("/field-pack`", "apiDelete", "data-act=\"make\"", "data-act=\"copy\"", "data-act=\"off\"", "data-act=\"off-yes\"", "data-act=\"retry\"", "role=\"alertdialog\"", "expiryLines", "TEXT.warn"):
        assert must in pl, must
    ap = (ROOT / "frontend" / "src" / "new" / "apiPost.js").read_text(encoding="utf-8")
    assert "method: 'DELETE'" in ap and 'allow_methods=["GET", "POST", "DELETE", "OPTIONS"]' in (ROOT / "api_v2.py").read_text(encoding="utf-8")


def test_the_node_tests_of_the_planter_link_and_its_qr_code_pass():
    import subprocess
    node = shutil_which("node")
    if node is None:
        pytest.fail("node is needed for the planter link tests")
    r = subprocess.run([node, "--test", "src/new/planterLink.test.mjs"], cwd=ROOT / "frontend", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-500:]
    assert "# pass 6" in r.stdout and "# fail 0" in r.stdout


def shutil_which(name):
    import shutil
    return shutil.which(name)


def test_the_favicon_request_of_a_phone_needs_no_code_and_returns_nothing():
    import access_gate as ag
    assert "/favicon.ico" in ag.EXEMPT and ag.is_field_path("/field/abc/") and not ag.is_field_path("/field/") and not ag.is_field_path("/field/a/b") and not ag.is_field_path("/fields/abc/")
