"""Design v2: the Field Pack carries a generated COPY of the dashboard's Canopy token block (one source of truth: frontend/src/new/canopy.css)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_field_pack_tokens_are_in_sync_with_canopy():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_fieldpack_tokens.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, "fieldpack/tokens.css is out of date: run python scripts/sync_fieldpack_tokens.py"


def test_the_built_page_has_tokens_dark_mode_and_both_fonts():
    sys.path.insert(0, str(ROOT / "pipeline"))
    import field_pack as fp
    css = fp.design_css()
    assert "--c-primary" in css and "prefers-color-scheme: dark" in css
    assert css.count("@font-face") == 2 and "Inter Variable" in css and "Fraunces Variable" in css
