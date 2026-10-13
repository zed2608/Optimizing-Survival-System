"""Stage B (branch field-pack): shared access code, /ping, read and weather limits, weather rounding, body cap, noindex and security headers.
Everything is OFF unless OS_ACCESS_CODE / OS_PUBLIC_MODE is set; the last test checks that nothing changes by default.
Run from the repo root: python -m pytest tests/test_access_gate.py"""
import os, sys, time
from pathlib import Path
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import access_gate as ag  # noqa: E402
import public_mode as pm  # noqa: E402

NEEDS_DATA = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")


# ---------------------------------------------------------------- the pure parts
def test_the_cookie_is_signed_expires_and_follows_the_code(monkeypatch):
    monkeypatch.setenv("OS_ACCESS_CODE", "tree-123")
    c = ag.make_cookie()
    assert ag.cookie_ok(c) and not ag.cookie_ok(c + "0") and not ag.cookie_ok("") and not ag.cookie_ok("12.ab") and not ag.cookie_ok("x.y")
    exp, sig = c.split(".")
    assert not ag.cookie_ok(f"{int(exp) + 5}.{sig}")                      # a longer life cannot be written by hand
    assert not ag.cookie_ok(c, now=int(exp) + 1)                          # expired
    monkeypatch.setenv("OS_ACCESS_CODE", "another-code")
    assert not ag.cookie_ok(c)                                            # changing the code ends every old login
    assert ag.code_ok("another-code") and not ag.code_ok("tree-123") and not ag.code_ok("")
    monkeypatch.delenv("OS_ACCESS_CODE")
    assert not ag.is_on() and not ag.cookie_ok(c) and not ag.code_ok("")  # off: nothing is accepted as a login either


def test_where_to_go_after_login_stays_on_this_site():
    assert ag.safe_next("/plans?x=1") == "/plans?x=1" and ag.safe_next(None) == "/"
    for bad in ("//evil.example", "https://evil.example", "\\\\evil", "/a\r\nSet-Cookie: x=1", "evil"):
        assert ag.safe_next(bad) == "/", bad


def test_cookie_header_flags(monkeypatch):
    monkeypatch.setenv("OS_ACCESS_CODE", "x")
    h = ag.cookie_header("v")
    assert "HttpOnly" in h and "SameSite=Lax" in h and "Secure" in h and "Path=/" in h and f"Max-Age={12 * 3600}" in h
    monkeypatch.setenv("OS_COOKIE_SECURE", "0")
    assert "Secure" not in ag.cookie_header("v") and "Max-Age=0" in ag.cookie_header("", clear=True)


def test_read_limits_and_exempt_paths():
    assert pm.classify_read("GET", "/ping") is None and pm.classify_read("GET", "/assets/index-abc.js") is None and pm.classify_read("POST", "/plan-event") is None
    assert pm.classify_read("GET", "/weather/week") == "weather" and pm.classify_read("GET", "/plans/plan_urban_1/advisory") == "weather"
    assert pm.classify_read("GET", "/advisory/seasonal") == "weather" and pm.classify_read("GET", "/grid") == "read" and pm.classify_read("GET", "/plans") == "read"
    lim = pm.settings()["limits"]
    assert lim["login"] == (10, 600) and lim["read"] == (300, 60) and lim["weather"] == (30, 60)


# ---------------------------------------------------------------- the service with the access code and the sandbox on
@pytest.fixture(scope="module")
def gated(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("OS_ACCESS_CODE", "tree-123")
    mp.setenv("OS_COOKIE_SECURE", "0")
    mp.setenv("OS_PUBLIC_MODE", "1")
    mp.setenv("OS_STATE_DIR", str(tmp_path_factory.mktemp("gate") / "state"))
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app, follow_redirects=False) as c:
        yield {"client": c, "api": api_v2, "mp": mp}
    mp.undo()


@pytest.fixture()
def cl(gated):
    gated["api"].LIMITER = gated["api"].pm.Limiter()
    gated["client"].cookies.clear()
    return gated["client"]


def login(c, code="tree-123", **kw):
    return c.post("/login", data={"code": code, "next": "/"}, **kw)


@NEEDS_DATA
def test_without_the_code_nothing_opens_except_ping_login_robots(cl):
    r = cl.get("/health")
    assert r.status_code == 401 and r.headers["X-Login-Required"] == "1" and r.json()["login_required"] is True
    page = cl.get("/", headers={"accept": "text/html"})
    assert page.status_code == 303 and page.headers["location"].startswith("/login")
    assert cl.get("/plans?limit=5", headers={"sec-fetch-dest": "document"}).headers["location"].startswith("/login?next=/plans")
    assert cl.post("/plan-event", json={"purpose": "urban", "n_saplings": 10, "barangay": "MALY"}).status_code == 401
    assert cl.get("/ping").json() == {"ok": True}
    assert cl.get("/login").status_code == 200 and "Access code" in cl.get("/login").text and "provisional" in cl.get("/login").text
    assert cl.get("/robots.txt").text.startswith("User-agent: *")


@NEEDS_DATA
def test_the_wrong_code_gives_no_cookie_the_right_code_does(cl):
    bad = login(cl, "nope")
    assert bad.status_code == 401 and "not right" in bad.text and "set-cookie" not in bad.headers and "tree-123" not in bad.text
    ok = login(cl)
    assert ok.status_code == 303 and ok.headers["location"] == "/"
    sc = ok.headers["set-cookie"]
    assert sc.startswith("os_access=") and "HttpOnly" in sc and "SameSite=Lax" in sc and "Max-Age=43200" in sc
    assert cl.get("/health").status_code == 200                                      # the client now carries the cookie
    assert cl.get("/login", params={"next": "//evil.example"}).text.count('value="/"') == 1


@NEEDS_DATA
def test_a_tampered_cookie_and_a_changed_code_are_refused(gated, cl):
    login(cl)
    good = cl.cookies.get("os_access")
    cl.cookies.clear()
    cl.cookies.set("os_access", good[:-3] + "000")
    assert cl.get("/health").status_code == 401
    cl.cookies.set("os_access", good)
    assert cl.get("/health").status_code == 200
    gated["mp"].setenv("OS_ACCESS_CODE", "new-code-456")                              # the person in charge changes the code on the host
    try:
        assert cl.get("/health").status_code == 401                                  # every old login ends at once
        assert login(cl, "new-code-456").status_code == 303 and cl.get("/health").status_code == 200
    finally:
        gated["mp"].setenv("OS_ACCESS_CODE", "tree-123")


@NEEDS_DATA
def test_logout_clears_the_cookie(cl):
    login(cl)
    r = cl.get("/logout")
    assert r.status_code == 303 and "Max-Age=0" in r.headers["set-cookie"]
    cl.cookies.clear()
    assert cl.get("/health").status_code == 401


@NEEDS_DATA
def test_login_tries_are_limited(cl):
    codes = [login(cl, f"wrong{i}").status_code for i in range(12)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    again = login(cl)
    assert again.status_code == 429 and "Retry-After" in again.headers               # even the right code waits (so guessing gains nothing)


@NEEDS_DATA
def test_headers_robots_and_the_body_cap(cl):
    login(cl)
    h = cl.get("/health").headers
    assert h["x-robots-tag"] == "noindex, nofollow" and h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert cl.get("/ping").headers["x-robots-tag"].startswith("noindex")
    cap = pm.settings()["caps"]["body_bytes"]
    pieces = (b"x" * 100_000 for _ in range(cap // 100_000 + 3))                     # no Content-Length: refused while it is read
    r = cl.post("/plan-event", content=pieces, headers={"content-type": "application/json"})
    assert r.status_code == 413 and "too large" in str(r.json())


@NEEDS_DATA
def test_reads_are_limited_and_the_health_check_is_not(gated, cl):
    login(cl)
    gated["mp"].setenv("OS_RATE_READ", "5")
    try:
        got = [cl.get("/species").status_code for _ in range(7)]
        assert got[:5] == [200] * 5 and got[5] == 429
        assert all(cl.get("/ping").status_code == 200 for _ in range(30))              # the host's health check never counts
    finally:
        gated["mp"].delenv("OS_RATE_READ")


@NEEDS_DATA
def test_weather_calls_are_counted_and_rounded_to_a_coarse_place(gated, cl, monkeypatch):
    login(cl)
    seen = []
    api = gated["api"]

    def fake(lat, lon, cache_dir, cfg=None):
        seen.append((round(lat, 4), round(lon, 4), (cfg or {}).get("cache_coord_decimals")))
        raise api.adv.ForecastUnavailable("test: no network")

    monkeypatch.setattr(api.adv, "fetch_forecast", fake)
    assert cl.get("/weather/week", params={"purpose": "urban", "lat": 14.6912, "lon": 121.1234}).status_code == 503
    assert seen == [(14.6912, 121.1234, 1)]                                          # public mode asks for 1 decimal: a few cells cover San Mateo
    gated["mp"].setenv("OS_RATE_WEATHER", "2")
    try:
        codes = [cl.get("/weather/week", params={"purpose": "urban"}).status_code for _ in range(4)]
        assert codes[2:] == [429, 429]
    finally:
        gated["mp"].delenv("OS_RATE_WEATHER")


def test_the_login_redirect_and_the_health_path_are_wired():
    assert "X-Login-Required" in (ROOT / "frontend" / "src" / "loginRedirect.js").read_text(encoding="utf-8")
    assert "loginRedirect.js" in (ROOT / "frontend" / "src" / "main.jsx").read_text(encoding="utf-8")
    assert "healthCheckPath: /ping" in (ROOT / "render.yaml").read_text(encoding="utf-8")


# ---------------------------------------------------------------- the default: nothing changes
@NEEDS_DATA
def test_with_everything_off_the_service_is_as_before(monkeypatch):
    for k in ("OS_ACCESS_CODE", "OS_PUBLIC_MODE", "OS_STATE_DIR", "OS_LOG_VISITOR"):
        monkeypatch.delenv(k, raising=False)
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        r = c.get("/health")
        assert r.status_code == 200 and "x-robots-tag" not in r.headers and "x-frame-options" not in r.headers
        assert c.get("/robots.txt").status_code == 404 and c.get("/ping").json() == {"ok": True}
        assert [c.get("/species").status_code for _ in range(5)] and c.post("/login", data={"code": "x"}).status_code in (404, 405)
        assert c.get("/docs").status_code == 200
