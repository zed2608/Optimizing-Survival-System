"""Round 9: the revamp (#/new) is the default dashboard; #/legacy shows the old one and #/v2 stays; the More menu has an "Old dashboard" link.
Run from the repo root: python -m pytest tests/test_dashboard_default.py"""
import hashlib, shutil, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_address_picks_the_dashboard():
    r = subprocess.run(["node", str(SRC / "dashboardConfig.test.mjs")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "all tests passed" in r.stdout


def test_the_default_is_one_setting_and_the_router_uses_it():
    cfg = (SRC / "dashboardConfig.js").read_text(encoding="utf-8")
    assert "export const DEFAULT_DASHBOARD = 'new'" in cfg and "'#/legacy'" in cfg.replace('"', "'") and "startsWith('#/v2')" in cfg
    sw = (SRC / "DashboardSwitch.jsx").read_text(encoding="utf-8")
    assert "chooseDashboard(hash)" in sw and "import Legacy from './App.legacy.jsx'" in sw


def test_the_more_menu_links_to_the_old_dashboard_and_the_legacy_files_are_untouched():
    menu = (SRC / "new" / "MoreMenu.jsx").read_text(encoding="utf-8")
    assert '<a href="#/legacy">Old dashboard</a>' in menu and '<a href="#/v2">First v2 page</a>' in menu
    assert hashlib.sha256((SRC / "App.jsx").read_bytes()).hexdigest() == hashlib.sha256((SRC / "App.legacy.jsx").read_bytes()).hexdigest()
