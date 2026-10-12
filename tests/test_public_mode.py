"""Public sandbox mode (deploy-sandbox branch). OFF by default; with OS_PUBLIC_MODE=1:
 - state (field checks, plans, kits, cache) lives in a throwaway folder that starts empty; the real field-check file is never touched;
 - the field-check exclusion switch is OFF;
 - size cap on the CSV import, cap on stored plans, per-visitor rate limits, one kit build at a time, /docs closed;
 - the dashboard can read the notice from /health.
The pure parts (limiter, folder rules) are tested without the API. Run from the repo root: python -m pytest tests/test_public_mode.py"""
import os, sys, time
from pathlib import Path
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import public_mode as pm  # noqa: E402

NEEDS_DATA = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")


# ---------------------------------------------------------------- pure parts
def test_everything_is_off_by_default(monkeypatch):
    for k in [k for k in os.environ if k.startswith("OS_") and k not in ("OS_FIELD_DB", "OS_S_SOURCE", "OS_DATA_DIR")]:
        monkeypatch.delenv(k)
    assert pm.is_on() is False and pm.settings()["on"] is False
    assert pm.state_dir() is None                                       # no OS_STATE_DIR: the normal folders are used


def test_the_limiter_slides_and_has_a_global_limit():
    t = [0.0]
    lim = pm.Limiter(clock=lambda: t[0])
    limits = {"field": (2, 10)}
    assert lim.allow("field", "a", limits)[0] and lim.allow("field", "a", limits)[0]
    ok, wait = lim.allow("field", "a", limits)
    assert not ok and 1 <= wait <= 11
    assert lim.allow("field", "b", limits)[0]                           # another visitor is not affected
    t[0] = 10.5                                                         # the first hits left the window
    assert lim.allow("field", "a", limits)[0]
    g = pm.Limiter(clock=lambda: 0.0)
    done = [g.allow("field", f"v{i}", limits)[0] for i in range(2 * pm.GLOBAL_FACTOR + 3)]
    assert done.count(True) == 2 * pm.GLOBAL_FACTOR                     # many visitors together cannot pass the global limit


def test_what_is_limited_and_who_the_visitor_is():
    assert pm.classify("POST", "/plan-event") == "plan" and pm.classify("POST", "/plans/plan_urban_1/top-up") == "plan"
    assert pm.classify("POST", "/plans/plan_urban_1/field-kit") == "kit"
    assert pm.classify("POST", "/field-checks") == "field" and pm.classify("POST", "/field-checks/import") == "field"
    assert pm.classify("POST", "/plan-event/preview") == "compute" and pm.classify("POST", "/rank/area") == "compute"
    assert pm.classify("GET", "/plans") is None and pm.classify("GET", "/field-checks") is None
    h = {"x-forwarded-for": "6.6.6.6, 1.2.3.4"}
    assert pm.visitor_of(h, "10.0.0.1", 1) == "1.2.3.4"                 # the entry added by the host's own proxy, not the one the visitor wrote
    assert pm.visitor_of(h, "10.0.0.1", 0) == "10.0.0.1" and pm.visitor_of({}, None, 1) == "unknown"


def test_the_state_folder_is_never_a_real_data_folder(tmp_path):
    data, field = tmp_path / "data" / "processed", tmp_path / "data" / "field"
    data.mkdir(parents=True), field.mkdir(parents=True)
    for bad in (data, field, tmp_path / "data", data / "sandbox"):
        with pytest.raises(ValueError):
            pm.check_state_dir(bad, [data, field])
    pm.check_state_dir(tmp_path / "other", [data, field])
    full = tmp_path / "somebody_elses"
    full.mkdir()
    (full / "keep.txt").write_text("x")
    with pytest.raises(ValueError):
        pm.empty_state(full)
    assert (full / "keep.txt").exists()                                 # nothing was deleted
    mine = pm.empty_state(tmp_path / "state")
    (mine / "plans").mkdir()
    (mine / "plans" / "a.csv").write_text("x")
    (mine / "field_checks.db").write_text("x")
    pm.empty_state(mine)
    assert sorted(p.name for p in mine.iterdir()) == [pm.SENTINEL]


# ---------------------------------------------------------------- the service in public mode
@pytest.fixture(scope="module")
def sandbox(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    state = tmp_path_factory.mktemp("sandbox") / "state"
    mp.setenv("OS_PUBLIC_MODE", "1")
    mp.setenv("OS_STATE_DIR", str(state))
    mp.setenv("OS_RATE_COMPUTE", "1000")
    mp.setenv("OS_RATE_PLAN", "1000")
    import api_v2
    from fastapi.testclient import TestClient
    real_db = ROOT / "data" / "field" / "field_checks.db"
    before = (real_db.stat().st_size, real_db.stat().st_mtime_ns) if real_db.exists() else None
    with TestClient(api_v2.app) as c:
        yield {"client": c, "state": state, "api": api_v2, "real_db": real_db, "before": before, "mp": mp}
    mp.undo()


@pytest.fixture()
def cl(sandbox):
    sandbox["api"].LIMITER = sandbox["api"].pm.Limiter()                # a clean count for every test
    return sandbox["client"]


def a_point(client, k=50):
    d = client.app.state.data
    r = d.ctx.sites[d.ctx.sites.zone_desc == "Forest Zone"].iloc[k]
    return int(r.point_id), float(r.lat), float(r.lon)


@NEEDS_DATA
def test_the_sandbox_starts_empty_and_leaves_the_real_field_file_alone(sandbox, cl):
    state, d = sandbox["state"], cl.app.state.data
    assert (state / pm.SENTINEL).exists() and Path(d.field_db).resolve() == (state / "field_checks.db").resolve()
    assert Path(d.work).resolve() == state.resolve() and cl.get("/field-checks/summary").json()["events"] == 0
    real = sandbox["real_db"]
    assert (real.stat().st_size, real.stat().st_mtime_ns) == sandbox["before"] if sandbox["before"] else True


@NEEDS_DATA
def test_the_notice_is_in_health(cl):
    p = cl.get("/health").json()["public_mode"]
    assert p["on"] is True and p["notice"] == "Demo / sandbox. Data is provisional and not yet signed off by the agriculturist. Entries reset regularly."
    assert p["reset_hours"] == 24.0


@NEEDS_DATA
def test_the_docs_pages_are_closed(cl):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert cl.get(path).status_code == 404, path


@NEEDS_DATA
def test_a_not_plantable_mark_does_not_change_what_others_see(cl):
    pid, lat, lon = a_point(cl)
    q = {"lat": lat, "lon": lon, "purpose": "urban"}
    before = cl.get("/rank", params=q)
    assert before.status_code == 200
    r = cl.post("/field-checks", json={"point_id": pid, "status": "not_plantable", "reason": "paved", "observer": "Visitor"})
    assert r.status_code == 201
    assert cl.get("/health").json()["field_checks"]["exclude_not_plantable"] is False
    assert cl.get("/rank", params=q).status_code == 200      # not left out
    assert cl.get("/field-checks/summary").json()["left_out_of_rankings"] == 0


@NEEDS_DATA
def test_the_import_has_a_size_cap(sandbox, cl):
    cap = pm.settings()["caps"]["import_bytes"]
    big = ("point_ref,status\n" + "x," * 10 + "\n") * (cap // 20 + 100)
    r = cl.post("/field-checks/import", params={"observer": "V"}, content=big.encode(), headers={"content-type": "text/csv"})
    assert r.status_code == 413 and "too large" in r.json()["message"]
    chunks = (big[i:i + 20_000].encode() for i in range(0, len(big), 20_000))      # no Content-Length: refused while reading
    r2 = cl.post("/field-checks/import", params={"observer": "V"}, content=chunks, headers={"content-type": "text/csv"})
    assert r2.status_code == 413


@NEEDS_DATA
def test_the_plan_cap_and_the_plain_message(sandbox, cl):
    api = sandbox["api"]
    body = {"purpose": "urban", "n_saplings": 10, "barangay": "GUINAYANG", "campaign": {"name": "cap", "unit": "t"}}
    sandbox["mp"].setenv("OS_MAX_PLANS", str(pm.count_files(cl.app.state.data.work / "plans", "plan_*_summary.json") + 1))
    try:
        assert cl.post("/plan-event", json=body).status_code == 200
        r = cl.post("/plan-event", json=body)
        assert r.status_code == 429 and "emptied regularly" in r.json()["message"] and "Retry-After" in r.headers
    finally:
        sandbox["mp"].delenv("OS_MAX_PLANS")
    assert api.pm.count_files(cl.app.state.data.work / "plans", "plan_*_summary.json") >= 1                 # the plan is inside the sandbox folder


@NEEDS_DATA
def test_rate_limit_per_visitor(sandbox, cl):
    pid, _, _ = a_point(cl, 70)
    sandbox["mp"].setenv("OS_RATE_FIELD", "2")
    try:
        send = lambda ip: cl.post("/field-checks", json={"point_id": pid, "status": "needs_recheck", "observer": "V"}, headers={"x-forwarded-for": f"9.9.9.9, {ip}"})
        assert send("1.1.1.1").status_code == 201 and send("1.1.1.1").status_code == 201
        r = send("1.1.1.1")
        assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1 and "wait" in r.json()["message"]
        assert send("2.2.2.2").status_code == 201                       # another visitor still works
    finally:
        sandbox["mp"].delenv("OS_RATE_FIELD")


@NEEDS_DATA
def test_one_kit_build_at_a_time(sandbox, cl):
    api = sandbox["api"]
    body = {"purpose": "urban", "n_saplings": 10, "barangay": "GUINAYANG", "campaign": {"name": "kit", "unit": "t"}}
    plan_id = cl.post("/plan-event", json=body).json()["plan_id"]
    assert api.KIT_GATE.try_enter()
    try:
        r = cl.post(f"/plans/{plan_id}/field-kit")
        assert r.status_code == 429 and "Another field kit" in r.json()["detail"]
    finally:
        api.KIT_GATE.leave()
    ok = cl.post(f"/plans/{plan_id}/field-kit")
    assert ok.status_code == 200 and (cl.app.state.data.work / "kits").is_dir()                 # kits are inside the sandbox folder
    assert not api.KIT_GATE.lock.locked()                                                         # and the gate is free again


@NEEDS_DATA
def test_the_sandbox_resets_by_itself(sandbox, cl):
    d = cl.app.state.data
    pid, _, _ = a_point(cl, 90)
    cl.post("/field-checks", json={"point_id": pid, "status": "needs_recheck", "observer": "V"})
    cl.post("/plan-event", json={"purpose": "urban", "n_saplings": 10, "barangay": "GUINAYANG", "campaign": {"name": "old", "unit": "t"}})
    assert cl.get("/field-checks/summary").json()["events"] >= 1 and cl.get("/plans").json()
    d.sandbox_started = time.time() - 25 * 3600                          # older than the 24 hours
    assert cl.get("/field-checks/summary").json()["events"] == 0         # the first request after that empties everything
    plans = cl.get("/plans").json()
    assert (plans["plans"] if isinstance(plans, dict) else plans) == []
    assert cl.get("/health").json()["public_mode"]["next_reset_in_hours"] > 23


# ---------------------------------------------------------------- the default (public mode off) is unchanged
@NEEDS_DATA
def test_with_the_mode_off_nothing_changes(monkeypatch):
    for k in ("OS_PUBLIC_MODE", "OS_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        assert c.get("/health").json()["public_mode"] == {"on": False}
        assert c.get("/docs").status_code == 200
        d = c.app.state.data
        assert d.cfg["field_exclude_not_plantable"] is True and Path(d.work) == Path(d.root)


# ---------------------------------------------------------------- the dashboard side (source checks; the browser run is a Phase 1 manual check)
def test_the_credits_list_names_every_source_and_the_notice_is_wired():
    credits = (ROOT / "frontend" / "src" / "new" / "credits.js").read_text(encoding="utf-8")
    for name in ("WorldCover", "CC BY 4.0", "10.5281/zenodo.7254221", "LGU soil map", "Bureau of Soils and Water Management", "Zoning and barangay boundaries",
                 "Species data", "Esri World Imagery", "OpenStreetMap", "ODbL", "Open-Meteo", "Elevation"):
        assert name in credits, name
    more = (ROOT / "frontend" / "src" / "new" / "MoreMenu.jsx").read_text(encoding="utf-8")
    assert "CREDITS.map" in more and "isSandbox" in more                 # the list is shown, and the old-dashboard links are hidden in the sandbox
    app = (ROOT / "frontend" / "src" / "new" / "AppNew.jsx").read_text(encoding="utf-8")
    assert "<PublicNotice health={healthData} />" in app
    assert pm.NOTICE in (ROOT / "frontend" / "src" / "new" / "PublicNotice.jsx").read_text(encoding="utf-8")      # same words as the service sends (fallback text)
