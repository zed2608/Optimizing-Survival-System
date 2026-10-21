"""C3 (overnight 2026-10-15): when there is no forecast the dashboard says one plain Filipino sentence and keeps the reason under it. The node tests of the function are in frontend/src/new/weatherText.test.mjs."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "frontend" / "src" / "new"


def test_the_three_weather_places_use_the_one_message():
    for name in ("WeatherTab.jsx", "WeatherCard.jsx", "PlanWeather.jsx"):
        t = (NEW / name).read_text(encoding="utf-8")
        assert "import { weatherError } from './weatherText.js'" in t, name
        assert "weatherError(api.error)" in t, name
        assert "Weather is not available now" not in t and "no weather now" not in t and "no weather advice now" not in t, name   # the old plain English sentences are gone
    # V2: the sentence moved into messages.js so that English mode shows no Filipino: Taglish keeps the same sentence, English says the same thing in English
    msgs = (NEW / "messages.js").read_text(encoding="utf-8")
    assert "'wx.unreachable': 'Hindi maabot ang weather ngayon. Subukan ulit mamaya.'" in msgs
    assert "'wx.unreachable': 'The weather cannot be reached now. Try again later.'" in msgs
    assert "tr('wx.unreachable'" in (NEW / "weatherText.js").read_text(encoding="utf-8")


def test_the_service_still_refuses_honestly_without_a_forecast(monkeypatch, tmp_path):
    """No internet and no saved copy: the API answers 503 with its own reason (the dashboard then shows the Filipino sentence and this reason under it); it never invents a forecast."""
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    import advisory as adv

    def boom(*a, **k):
        raise OSError("no internet (test)")
    monkeypatch.setattr(adv, "http_get", boom)
    with pytest.raises(adv.ForecastUnavailable) as e:
        adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert "could not be reached" in str(e.value) and "no cached forecast" in str(e.value)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_the_node_tests_of_the_message_pass():
    r = subprocess.run([shutil.which("node"), "--test", "src/new/weatherText.test.mjs"], cwd=ROOT / "frontend", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0 and "# pass 4" in r.stdout and "# fail 0" in r.stdout, r.stdout[-800:]
