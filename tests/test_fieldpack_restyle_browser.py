"""Design v2: the Field Pack screens in light and dark at 360 and 1280 px: nothing under 12 px, nothing below AA, no sideways scroll, every button and link 44 px (scripts/fieldpack_shots.mjs --ci).
Runs only with OS_BROWSER_CHECK=1 (needs Edge and node)."""
import os, shutil, socket, subprocess, sys, time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "field_pack" / "field_kit_plan_urban_20261013_032648"
EDGE = os.environ.get("EDGE") or "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
pytestmark = pytest.mark.skipif(os.environ.get("OS_BROWSER_CHECK") != "1" or shutil.which("node") is None or not Path(EDGE).exists(), reason="set OS_BROWSER_CHECK=1 (needs node and Microsoft Edge)")


def test_the_pack_screens_pass_the_text_and_phone_audit(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_field_pack.py"), str(FIXTURE), "--out", str(tmp_path / "pages")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    page = next((tmp_path / "pages").glob("fieldpack_*.html"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=tmp_path / "pages", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        out = subprocess.run(["node", str(ROOT / "scripts" / "fieldpack_shots.mjs"), f"http://127.0.0.1:{port}/{page.name}", str(tmp_path / "shots"), "--ci"], capture_output=True, text=True, timeout=900)
        assert out.returncode == 0, out.stdout[-3000:]
    finally:
        srv.terminate()
