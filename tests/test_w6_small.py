"""R1 W6: what a field check says it does (per mode), the field-check legend follows the language, the Welcome entry is reachable on a phone, no Filipino in English mode (browser, gated)."""
import os, re, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
SRC = ROOT / "frontend" / "src" / "new"

needs_data = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")


@pytest.fixture(scope="module")
def client():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh(request, tmp_path, monkeypatch):
    if "client" not in request.fixturenames:
        yield
        return
    import api_v2
    import field_verify as fv
    data = request.getfixturevalue("client").app.state.data
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(data, "work", tmp_path)
    fv.connect(data.field_db).close()
    api_v2.refresh_field(data)
    yield


def post(client, point, status, **kw):
    body = {"point_id": point, "status": status, "observer": "Ana", **kw}
    return client.post("/field-checks", json=body)


@needs_data
def test_the_effect_sentence_says_exactly_what_happens_in_each_mode(client, monkeypatch):
    data = client.app.state.data
    monkeypatch.setitem(data.cfg, "field_exclude_not_plantable", True)
    local = post(client, 832, "not_plantable", reason="paved")
    assert local.status_code in (200, 201), local.text
    assert "left out of the rankings, the map colours and new plans" in local.json()["effect"] and "scores are not changed" in local.json()["effect"]
    import api_v2
    monkeypatch.setitem(data.cfg, "field_exclude_not_plantable", False)
    api_v2.refresh_field(data)
    demo = post(client, 833, "not_plantable", reason="paved").json()["effect"]
    assert demo == "Saved: recorded only. In this demo a not-plantable mark does not change the rankings or the plans."
    ok = post(client, 834, "verified_plantable").json()["effect"]
    assert "only adds a badge" in ok and "never changes a score or a ranking" in ok
    rc = post(client, 835, "needs_recheck").json()["effect"]
    assert "only adds a warning" in rc and "do not change" in rc


def test_the_field_check_legend_and_chips_follow_the_language():
    msgs = (SRC / "messages.js").read_text(encoding="utf-8")
    for cls in ("planted", "verified", "recheck", "not_plantable", "water", "hard"):
        assert msgs.count(f"'fk.l.{cls}'") == 2, cls                                   # one English and one Filipino line
    assert "fieldLabel(k, lang)" in (SRC / "FieldLegend.jsx").read_text(encoding="utf-8")
    assert "useLang" in (SRC / "FieldChip.jsx").read_text(encoding="utf-8") and "useLang" in (SRC / "PlanProgress.jsx").read_text(encoding="utf-8")


def test_the_welcome_entry_is_in_the_header_menu_and_nothing_hides_it_on_a_phone():
    assert 'data-role="welcome-open"' in (SRC / "SettingsMenu.jsx").read_text(encoding="utf-8")
    css = (SRC / "canopy.css").read_text(encoding="utf-8") + (SRC / "new.css").read_text(encoding="utf-8")
    assert not re.search(r"welcome-open[^{]*\{[^}]*display:\s*none", css)


@pytest.mark.skipif(os.environ.get("OS_BROWSER_CHECK") != "1" or shutil.which("node") is None, reason="set OS_BROWSER_CHECK=1 (Edge, node and the dashboard on OS_BROWSER_BASE)")
def test_no_filipino_words_in_the_english_mode_text_of_the_screens():
    r = subprocess.run(["node", str(ROOT / "scripts" / "english_scan.mjs"), os.environ.get("OS_BROWSER_BASE", "http://127.0.0.1:8001")], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:]
