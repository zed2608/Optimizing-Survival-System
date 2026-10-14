"""Stage A2 in a real browser (headless Edge) against a REAL service: uvicorn with the built dashboard, the public sandbox and the access code on.
Runs only with OS_BROWSER_CHECK=1 (and Edge, node and npm installed): python -m pytest tests/test_planter_link_browser.py
 1. tests/browser/planter_link_check.mjs: the dashboard box (make, copy, QR decoded back, expiry, warning, replace, error + try again, switch off), then the planter opens the link WITHOUT the code:
    OSM tiles with the origin as Referer, no console errors.
 2. the existing Field Pack browser checks (flow, heading, map, UI, no-GPS) again, on the pack page SERVED BY THE ROUTE (/field/<token>/) and not by a file server."""
import json, os, shutil, socket, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
FIXTURE = ROOT / "tests" / "fixtures" / "field_pack" / "field_kit_plan_urban_20261013_032648"
EDGE = os.environ.get("EDGE") or "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
CODE = "tree-123"
pytestmark = pytest.mark.skipif(os.environ.get("OS_BROWSER_CHECK") != "1" or shutil.which("node") is None or shutil.which("npm") is None or not Path(EDGE).exists(),
                                reason="set OS_BROWSER_CHECK=1 (needs node, npm and Microsoft Edge)")


def call(base, path, method="GET", body=None, cookie=None, form=None):
    data = None
    headers = {}
    if body is not None:
        data, headers = json.dumps(body).encode(), {"Content-Type": "application/json"}
    if form is not None:
        data, headers = urllib.parse.urlencode(form).encode(), {"Content-Type": "application/x-www-form-urlencoded"}
    if cookie:
        headers["Cookie"] = f"os_access={cookie}"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        r = opener.open(urllib.request.Request(base + path, data=data, headers=headers, method=method), timeout=120)
    except urllib.error.HTTPError as e:
        r = e
    return r.status if hasattr(r, "status") else r.code, {k.lower(): v for k, v in r.headers.items()}, r.read()


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    dist = tmp_path_factory.mktemp("dist")                                  # the dashboard built the way the Docker image builds it: VITE_API_BASE empty = the page and the service share one address
    r = subprocess.run([shutil.which("npm"), "run", "build", "--", "--outDir", str(dist), "--emptyOutDir"], cwd=ROOT / "frontend", env={**os.environ, "VITE_API_BASE": ""},
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert r.returncode == 0 and (dist / "index.html").exists(), r.stdout[-1500:] + r.stderr[-800:]
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    state = tmp_path_factory.mktemp("srvstate") / "state"
    env = {**os.environ, "OS_PUBLIC_MODE": "1", "OS_STATE_DIR": str(state), "OS_STATIC_DIR": str(dist), "OS_ACCESS_CODE": CODE, "OS_COOKIE_SECURE": "0", "OS_RATE_READ": "100000",
           "OS_RATE_PLAN": "1000", "OS_RATE_KIT": "1000", "OS_RATE_PACK": "1000", "OS_FIELD_DB": str(tmp_path_factory.mktemp("fdb") / "f.db"), "OS_S_SOURCE": ""}
    env.pop("OS_S_SOURCE")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "api_v2:app", "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    t0 = time.time()
    while time.time() - t0 < 180:
        try:
            if call(base, "/ping")[0] == 200:
                break
        except Exception:
            time.sleep(1)
        if proc.poll() is not None:
            pytest.fail("the service did not start: " + proc.stderr.read().decode()[-1500:])
    else:
        proc.terminate()
        pytest.fail("the service did not start in 3 minutes")
    st, hdr, _ = call(base, "/login", "POST", form={"code": CODE, "next": "/"})
    cookie = hdr["set-cookie"].split(";")[0].split("=", 1)[1]
    st, _, raw = call(base, "/plan-event", "POST", body={"purpose": "urban", "n_saplings": 60, "barangay": "MALY", "seed": 3, "layout_mode": "blocks",
                                                       "campaign": {"name": "Link check", "unit": "Team A"}}, cookie=cookie)
    assert st == 200, raw[:300]
    yield {"base": base, "cookie": cookie, "plan": json.loads(raw)["plan_id"], "state": state, "out": tmp_path_factory.mktemp("shots")}
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


def node(script, *args, timeout=2400):
    return subprocess.run(["node", str(ROOT / "tests" / "browser" / script), *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def test_the_dashboard_box_and_the_planter_link_in_the_browser(server):
    r = node("planter_link_check.mjs", server["base"], server["cookie"], server["plan"], str(server["out"]), timeout=600)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-1000:]
    assert " 0 failed" in r.stdout and "read back with a QR decoder" in r.stdout and "Referer" in r.stdout


@pytest.fixture(scope="module")
def served_fixture_pack(server):
    """The fixture plan's pack, put in the service's pack folder under a token: the pages below are then served by GET /field/<token>/ (the files of the service, not a file server)."""
    import field_pack as fpk
    import pack_store as ps
    text, manifest = fpk.read_kit(FIXTURE)
    pack = fpk.build_pack(text, manifest)
    saved = ps.store(server["state"], pack["plan_id"], fpk.render_page(pack), pack_id=pack["pack_id"], check_code=pack["check_code"])
    return f"{server['base']}/field/{saved['token']}/"


@pytest.mark.parametrize("script, must", [
    ("fieldpack_check.mjs", " 0 failed"),
    ("fieldpack_heading_check.mjs", "heading across north"),
    ("fieldpack_map_check.mjs", "every tree marker equals the page's coordinates (50 trees, 6 blocks)"),
    ("fieldpack_ui_check.mjs", "WORD LIMITS:"),
    ("fieldpack_nogps_check.mjs", " 0 failed"),
])
def test_the_existing_field_pack_checks_pass_on_the_pack_served_by_the_route(server, served_fixture_pack, script, must):
    r = node(script, served_fixture_pack, str(server["out"]))
    assert r.returncode == 0, r.stdout[-3500:] + r.stderr[-1000:]
    assert " 0 failed" in r.stdout and must in r.stdout


def test_the_species_card_shows_the_climate_reference_in_the_browser(server):
    """Stage C1: the section "Climate and soil (reference only)" of the Species card, at a desktop and a phone width, in both languages, with no sideways scroll."""
    import climate_reference as cref
    rain = ("%g" % cref.load()["annual_rainfall_mm"]["value"])
    r = node("species_card_climate_check.mjs", server["base"], server["cookie"], rain, str(server["out"]), timeout=600)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-1000:]
    assert " 0 failed" in r.stdout and "no sideways scroll" in r.stdout
