"""Field pack in a real browser (headless Edge, 360 px wide, fake GPS, all tile requests intercepted so no map server is contacted).
Runs only with OS_BROWSER_CHECK=1 (and Edge + node installed): python -m pytest tests/test_field_pack_browser.py
It runs tests/browser/fieldpack_check.mjs (whole flow at 360x640 and 390x844), fieldpack_ui_check.mjs (stage A1e: arrow to each tree, the three panel states, text sizes 85% to 150%, word limits, layout at 360x640 / 390x844 / 412x915, guided tours), fieldpack_heading_check.mjs (heading, cone, relative cue, heading-up rotation, wake lock; simulated events) and fieldpack_map_check.mjs (map: markers = the page's coordinates for every tree of every block, Referer, zoom levels,
position and accuracy circle, line to the target, follow / re-centre, no background map, satellite only when built in)."""
import os, shutil, socket, subprocess, sys, time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "field_pack" / "field_kit_plan_urban_20261013_032648"
EDGE = os.environ.get("EDGE") or "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
pytestmark = pytest.mark.skipif(os.environ.get("OS_BROWSER_CHECK") != "1" or shutil.which("node") is None or not Path(EDGE).exists(),
                                reason="set OS_BROWSER_CHECK=1 (needs node and Microsoft Edge)")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    folder = tmp_path_factory.mktemp("pages")
    for sub, extra in (("normal", []), ("sat", ["--satellite"])):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_field_pack.py"), str(FIXTURE), "--out", str(folder / sub), *extra], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=folder, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    yield {"port": port, "folder": folder, "out": tmp_path_factory.mktemp("shots")}
    srv.terminate()


def page(site, sub):
    name = next((site["folder"] / sub).glob("fieldpack_*.html")).name
    return f"http://127.0.0.1:{site['port']}/{sub}/{name}"


def run(script, *args):
    r = subprocess.run(["node", str(ROOT / "tests" / "browser" / script), *args], capture_output=True, text=True, timeout=300)
    return r


def test_whole_flow_in_the_browser(site):
    r = run("fieldpack_check.mjs", page(site, "normal"), str(site["out"]))
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
    assert " 0 failed" in r.stdout


def test_heading_rotation_cue_and_wake_lock_in_the_browser(site):
    r = run("fieldpack_heading_check.mjs", page(site, "normal"), str(site["out"]))
    assert r.returncode == 0, r.stdout[-3500:] + r.stderr[-1000:]
    assert " 0 failed" in r.stdout and "heading across north" in r.stdout


def test_the_map_in_the_browser(site):
    r = run("fieldpack_map_check.mjs", page(site, "normal"), str(site["out"]), page(site, "sat"))
    assert r.returncode == 0, r.stdout[-3500:] + r.stderr[-1000:]
    assert " 0 failed" in r.stdout and "every tree marker equals the page's coordinates (50 trees, 6 blocks)" in r.stdout


def test_the_a1e_screen_in_the_browser(site):
    """Arrow, distance and word to each tree; panel collapsed / normal / expanded and its drag handle; the prototype chip; text size 85% to 150%; the word limits of every panel state in both languages;
    the layout at three phone sizes (no sideways scroll, buttons of 48 px or more, the main button visible); every tour step lights up a real element."""
    r = subprocess.run(["node", str(ROOT / "tests" / "browser" / "fieldpack_ui_check.mjs"), page(site, "normal"), str(site["out"])], capture_output=True, text=True, timeout=1500)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-1000:]
    assert " 0 failed" in r.stdout and "WORD LIMITS:" in r.stdout and "steps were shown" in r.stdout



def test_no_gps_is_never_a_dead_end_in_the_browser(site):
    """Stage A1f: GPS off, blocked, timeout, no signal, a GPS that never answers, and "continue without GPS": in every state a button to try GPS and one to go on without it, 48 px or more and not covered;
    row and spot instead of the arrow; the arrow is back when GPS is; nothing is saved. Three phone sizes, both languages, text 85 and 150 percent."""
    r = subprocess.run(["node", str(ROOT / "tests" / "browser" / "fieldpack_nogps_check.mjs"), page(site, "normal"), str(site["out"])], capture_output=True, text=True, timeout=1500)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-1000:]
    assert " 0 failed" in r.stdout
