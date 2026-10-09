"""Round 16: the in-app tutorial (one content file), the printable guide built from it, and the notes about obsolete browser scripts."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180)


def test_tutorial_unit_tests_pass():
    r = run(["node", "--test", "src/new/tutorial/tutorial.test.mjs"], ROOT / "frontend")
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-500:]


def test_user_guide_is_built_from_the_tour_content_and_up_to_date():
    r = run(["node", "scripts/build_user_guide.mjs", "--check"], ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    text = (ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")
    assert "check code" in text.lower() and "Needs permission" in text and "Habagat" in text


def test_readme_explains_how_to_rebuild_the_guide():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "scripts/build_user_guide.mjs" in readme and "docs/USER_GUIDE.md" in readme


def test_obsolete_browser_scripts_are_marked_in_the_docs():
    doc = (ROOT / "docs" / "BROWSER_CHECKS.md").read_text(encoding="utf-8")
    for name in ("cdp_field.mjs", "cdp_routes.mjs"):
        assert name in doc and "OBSOLETE" in doc


def test_the_tour_has_no_new_package():
    pkg = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    for bad in ("shepherd", "driver.js", "intro.js", "react-joyride", "reactour"):
        assert bad not in pkg
