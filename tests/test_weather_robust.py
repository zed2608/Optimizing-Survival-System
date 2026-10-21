"""Design v2: /weather/week and the forecast fetcher when Open-Meteo answers 429 / 5xx (mocked: the tests never use the network)."""
import sys
import threading
import time
import urllib.error
from datetime import date, timedelta
from email.message import Message
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import advisory as adv  # noqa: E402

START = date(2026, 6, 10)


def om(n=16):
    days = [(START + timedelta(days=i)).isoformat() for i in range(n)]
    return {"daily": {"time": days, "precipitation_sum": [4.0] * n, "temperature_2m_max": [31.0] * n, "temperature_2m_min": [24.0] * n}, "daily_units": {"precipitation_sum": "mm"}}


def err(code, retry_after=None):
    h = Message()
    if retry_after:
        h["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("https://api.open-meteo.com", code, "x", h, None)


def met(hours=72):
    """A small MET Norway compact answer: hourly values for `hours` hours from 2026-06-10 00:00 local (16:00 UTC the day before)."""
    t0 = __import__("datetime").datetime(2026, 6, 9, 16, 0)
    ts = []
    for h in range(hours):
        t = t0 + timedelta(hours=h)
        ts.append({"time": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "data": {"instant": {"details": {"air_temperature": 25.0 + (h % 24) / 4}}, "next_1_hours": {"details": {"precipitation_amount": 0.5}}}})
    return {"properties": {"timeseries": ts}}


def test_429_is_retried_with_backoff_then_succeeds(tmp_path, monkeypatch):
    waits, calls = [], []
    monkeypatch.setattr(adv, "_sleep", waits.append)

    def fake(url, params, timeout, headers=None):
        calls.append(url)
        if len(calls) < 3:
            raise err(429)
        return om()
    monkeypatch.setattr(adv, "http_get", fake)
    f = adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert len(calls) == 3 and len(waits) == 2 and f["cached"] is False and f["provider"]["name"] == "Open-Meteo"
    assert 0.5 <= waits[0] <= 1.5 and 1.0 <= waits[1] <= 3.0 and waits[1] > waits[0] * 0.9        # exponential with jitter, at most 2 retries


def test_a_forecast_that_keeps_failing_gives_stale_data_with_a_note_and_a_cooldown(tmp_path, monkeypatch):
    monkeypatch.setattr(adv, "http_get", lambda *a, **k: om())
    adv.fetch_forecast(14.69, 121.12, tmp_path)
    saved = next(tmp_path.glob("openmeteo_*.json"))
    doc = __import__("json").loads(saved.read_text(encoding="utf-8"))
    doc["fetched_at"] = (adv.now_utc() - timedelta(hours=5)).isoformat()                          # older than the 3 hour cache
    saved.write_text(__import__("json").dumps(doc), encoding="utf-8")
    calls = []
    monkeypatch.setattr(adv, "_COOLDOWN", {})

    def fake(*a, **k):
        calls.append(1)
        raise err(429)
    monkeypatch.setattr(adv, "http_get", fake)
    f = adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert f["cached"] is True and f["stale"] is True and "HTTP Error 429" in f["network_error"] and f["stale_note"].startswith("Last updated") and "may be out of date" in f["stale_note"]
    first = len(calls)
    assert first == 6                                                                              # 3 tries each for Open-Meteo and MET Norway
    adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert len(calls) == first                                                                     # cooling down: no new request for a while


def test_nothing_cached_and_everything_failing_keeps_the_friendly_error(tmp_path, monkeypatch):
    monkeypatch.setattr(adv, "http_get", lambda *a, **k: (_ for _ in ()).throw(err(429)))
    with pytest.raises(adv.ForecastUnavailable) as e:
        adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert "could not be reached" in str(e.value) and "no cached forecast" in str(e.value)


def test_the_disk_copy_survives_a_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(adv, "http_get", lambda *a, **k: om())
    adv.fetch_forecast(14.69, 121.12, tmp_path)
    adv.reset_state()                                                                              # a restart forgets the memory
    monkeypatch.setattr(adv, "http_get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no request: the saved copy is fresh")))
    f = adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert f["cached"] is True and f["stale"] is False


def test_no_stampede_one_request_per_place_while_many_ask(tmp_path, monkeypatch):
    calls = []

    def slow(url, params, timeout, headers=None):
        calls.append(1)
        time.sleep(0.2)
        return om()
    monkeypatch.setattr(adv, "http_get", slow)
    out = []
    ts = [threading.Thread(target=lambda: out.append(adv.fetch_forecast(14.69, 121.12, tmp_path))) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(calls) == 1 and len(out) == 8
    # places within the same 0.05 degree cell share the entry; a place far away asks again
    adv.fetch_forecast(14.7049, 121.0951, tmp_path)
    assert len(calls) == 1
    adv.fetch_forecast(14.80, 121.30, tmp_path)
    assert len(calls) == 2


def test_met_norway_is_the_second_provider_and_is_named(tmp_path, monkeypatch):
    seen = []

    def fake(url, params, timeout, headers=None):
        seen.append((url, headers))
        if "open-meteo" in url:
            raise err(503)
        return met(72)
    monkeypatch.setattr(adv, "http_get", fake)
    f = adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert f["provider"]["name"].startswith("MET Norway") and adv.source_of(f)["name"].startswith("MET Norway")
    ua = [h for u, h in seen if "met.no" in u][0]["User-Agent"]
    assert "OptimizingSurvival" in ua
    d = f["daily"]
    assert d["time"][0] == "2026-06-10" and d["precipitation_sum"][0] == 12.0 and len(d["time"]) >= 2          # 24 hours x 0.5 mm; days with fewer than 20 hours are dropped, never filled in


def test_met_days_with_missing_rain_are_dropped_not_invented():
    r = met(30)
    for e in r["properties"]["timeseries"][5:12]:
        e["data"].pop("next_1_hours")
    d = adv._met_daily(r, adv.CFG)["daily"]
    assert "2026-06-10" not in d["time"]


def test_the_api_names_the_stale_copy(monkeypatch):
    import api_v2  # noqa: F401  (import check only: the field is added next to cache_stale in /weather/week)
    src = (ROOT / "api_v2.py").read_text(encoding="utf-8")
    assert '"stale_note": fc.get("stale_note", "")' in src and "adv.source_of(fc)" in src
