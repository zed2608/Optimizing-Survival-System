"""Tests for pipeline/advisory.py. The Open-Meteo call is always mocked: these tests never use the internet.
Run from the repo root:  python -m pytest tests/test_advisory.py"""
import copy, json, sys, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import advisory as adv  # noqa: E402

TODAY = date(2026, 6, 10)                          # June: inside the planting window of the test species below


@pytest.fixture(autouse=True)
def _no_internet(monkeypatch):
    def blocked(*a, **k):
        raise AssertionError("the tests must not use the network")
    monkeypatch.setattr(adv, "http_get", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)


def daily(rain=None, tmax=None, tmin=None, start=TODAY, n=16, drop=()):
    days = [(start + timedelta(days=i)).isoformat() for i in range(n)]
    d = {"time": days, "precipitation_sum": rain if rain is not None else [5.0] * n,
         "temperature_2m_max": tmax if tmax is not None else [32.0] * n, "temperature_2m_min": tmin if tmin is not None else [24.0] * n}
    for k in drop:
        d.pop(k)
    return d


def response(**kw):
    return {"latitude": 14.69, "longitude": 121.12, "daily_units": {"precipitation_sum": "mm"}, "daily": daily(**kw)}


def fc_of(**kw):
    return {"daily": daily(**kw), "units": {}, "fetched_at": "x", "cached": False, "cache_age_minutes": 0.0, "stale": False, "network_error": None}


def sp(months="5;6;7", tol="Low", name="Testwood"):
    return {"species_id": 1, "common_name": name, "planting_months": months, "drought_tol": tol}


def advise(species=None, forecast=None, today=TODAY, **cfg_over):
    cfg = copy.deepcopy(adv.CFG); cfg.update(cfg_over)
    return adv.build_advisory(species or sp(), forecast or fc_of(), today=today, cfg=cfg)


def codes(a):
    return {w["code"] for w in a["warnings"]}


@pytest.fixture
def clock(monkeypatch):
    t = {"now": datetime(2026, 6, 10, 4, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(adv, "now_utc", lambda: t["now"])
    return t


# ---- forecast fetching and cache -----------------------------------------------------------------------------------------
def test_success_calls_open_meteo_once_with_the_right_request_and_writes_the_cache(tmp_path, monkeypatch, clock):
    calls = []
    monkeypatch.setattr(adv, "http_get", lambda url, params, timeout: calls.append((url, params, timeout)) or response())
    f = adv.fetch_forecast(14.6912, 121.1234, tmp_path)
    assert len(calls) == 1
    url, p, to = calls[0]
    assert url == "https://api.open-meteo.com/v1/forecast" and p["latitude"] == 14.69 and p["longitude"] == 121.12
    assert p["daily"] == "precipitation_sum,temperature_2m_max,temperature_2m_min" and p["forecast_days"] == 16 and p["timezone"] == "Asia/Manila" and to == adv.CFG["request_timeout_s"]
    assert f["cached"] is False and f["cache_age_minutes"] == 0.0 and f["network_error"] is None and len(f["daily"]["time"]) == 16
    files = list(tmp_path.glob("openmeteo_14.69_121.12_16d.json"))
    assert len(files) == 1 and json.loads(files[0].read_text())["response"]["daily"]["time"][0] == TODAY.isoformat()


def test_a_fresh_cache_is_used_without_calling_the_network_and_shows_its_age(tmp_path, monkeypatch, clock):
    monkeypatch.setattr(adv, "http_get", lambda *a: response())
    adv.fetch_forecast(14.69, 121.12, tmp_path)
    clock["now"] += timedelta(minutes=90)
    monkeypatch.setattr(adv, "http_get", lambda *a: (_ for _ in ()).throw(AssertionError("network used although the cache is fresh")))
    f = adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert f["cached"] is True and f["cache_age_minutes"] == 90.0 and f["stale"] is False and f["network_error"] is None


def test_cache_older_than_the_limit_is_refreshed_and_the_limit_is_a_config_value(tmp_path, monkeypatch, clock):
    n = []
    monkeypatch.setattr(adv, "http_get", lambda *a: n.append(1) or response())
    adv.fetch_forecast(14.69, 121.12, tmp_path)
    clock["now"] += timedelta(hours=3, minutes=1)
    assert adv.fetch_forecast(14.69, 121.12, tmp_path)["cached"] is False and len(n) == 2
    monkeypatch.setitem(adv.CFG, "cache_hours", 12)
    clock["now"] += timedelta(hours=6)
    assert adv.fetch_forecast(14.69, 121.12, tmp_path)["cached"] is True and len(n) == 2


def test_network_failure_falls_back_to_the_cache_and_says_so(tmp_path, monkeypatch, clock):
    monkeypatch.setattr(adv, "http_get", lambda *a: response())
    adv.fetch_forecast(14.69, 121.12, tmp_path)
    clock["now"] += timedelta(hours=5)
    monkeypatch.setattr(adv, "http_get", lambda *a: (_ for _ in ()).throw(urllib.error.URLError("no route to host")))
    f = adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert f["cached"] is True and f["cache_age_minutes"] == 300.0 and f["stale"] is True and "URLError" in f["network_error"]
    assert f["daily"]["time"][0] == TODAY.isoformat()


def test_no_cache_and_no_network_raises_a_clear_error(tmp_path, monkeypatch, clock):
    monkeypatch.setattr(adv, "http_get", lambda *a: (_ for _ in ()).throw(TimeoutError("timed out")))
    with pytest.raises(adv.ForecastUnavailable, match="Open-Meteo"):
        adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert not list(tmp_path.glob("*.json"))                                  # nothing invented, nothing cached


@pytest.mark.parametrize("bad", [{}, {"daily": {}}, {"daily": {"time": []}}, {"daily": "x"}, None])
def test_an_unusable_response_counts_as_a_failure_and_is_not_cached(tmp_path, monkeypatch, clock, bad):
    monkeypatch.setattr(adv, "http_get", lambda *a: bad)
    with pytest.raises(adv.ForecastUnavailable):
        adv.fetch_forecast(14.69, 121.12, tmp_path)
    assert not list(tmp_path.glob("*.json"))


def test_a_corrupt_cache_file_is_ignored(tmp_path, monkeypatch, clock):
    (tmp_path / "openmeteo_14.69_121.12_16d.json").write_text("{not json")
    monkeypatch.setattr(adv, "http_get", lambda *a: response())
    assert adv.fetch_forecast(14.69, 121.12, tmp_path)["cached"] is False


def test_nearby_coordinates_share_one_cache_entry(tmp_path, monkeypatch, clock):
    n = []
    monkeypatch.setattr(adv, "http_get", lambda *a: n.append(1) or response())
    adv.fetch_forecast(14.6901, 121.1199, tmp_path); adv.fetch_forecast(14.6949, 121.1201, tmp_path)
    assert len(n) == 1 and len(list(tmp_path.glob("*.json"))) == 1


def test_missing_forecast_fields_stay_missing_and_are_never_invented():
    d = daily(rain=[None, 5.0] + [5.0] * 14, drop=("temperature_2m_min",))
    rows = adv.forecast_table(d, TODAY)
    assert rows[0]["rain_mm"] is None and rows[0]["tmin_c"] is None and rows[1]["rain_mm"] == 5.0 and rows[0]["tmax_c"] == 32.0
    assert adv.forecast_table({"time": ["2026-06-10", "bad-date"]}, None)[0]["rain_mm"] is None


# ---- warnings: each code triggers and does not trigger ---------------------------------------------------------------
def test_not_in_planting_window():
    ok = advise(sp("5;6;7"), today=date(2026, 6, 10), forecast=fc_of(start=date(2026, 6, 10)))
    assert "not_in_planting_window" not in codes(ok)
    out = advise(sp("5;6;7"), today=date(2026, 1, 15), forecast=fc_of(start=date(2026, 1, 15)))
    w = next(w for w in out["warnings"] if w["code"] == "not_in_planting_window")
    assert w["numbers"] == {"current_month": 1, "planting_months": [5, 6, 7]} and "May, Jun, Jul" in w["message"] and "Jan" in w["message"]
    miss = advise(sp(None), today=date(2026, 1, 15), forecast=fc_of(start=date(2026, 1, 15)))
    assert "not_in_planting_window" not in codes(miss) and any(n["code"] == "not_in_planting_window" for n in miss["not_assessed"])


def test_dry_spell_triggers_below_the_threshold_for_species_that_are_not_high_tolerant():
    dry = fc_of(rain=[2.0] * 16)                                               # 7-day total 14 mm < 20
    for tol in ("Low", "Medium"):
        a = advise(sp(tol=tol), dry)
        w = next(w for w in a["warnings"] if w["code"] == "dry_spell")
        assert w["numbers"]["forecast_rain_mm"] == 14.0 and w["numbers"]["threshold_mm"] == 20.0 and w["numbers"]["days"] == 7 and "14.0 mm" in w["message"]
    assert "dry_spell" not in codes(advise(sp(tol="High"), dry))               # High drought tolerance: no warning
    wet = fc_of(rain=[5.0] * 16)                                               # 35 mm
    assert "dry_spell" not in codes(advise(sp(tol="Low"), wet))
    edge = fc_of(rain=[20 / 7] * 7 + [0.0] * 9)                                # exactly 20 mm is not below the threshold
    assert "dry_spell" not in codes(advise(sp(tol="Low"), edge))


def test_dry_spell_uses_only_the_next_seven_days_and_the_threshold_is_config():
    f = fc_of(rain=[0.0] * 7 + [50.0] * 9)
    assert "dry_spell" in codes(advise(sp(tol="Low"), f))
    f2 = fc_of(rain=[10.0] * 7 + [0.0] * 9)                                    # dry later does not count
    assert "dry_spell" not in codes(advise(sp(tol="Low"), f2))
    assert "dry_spell" in codes(advise(sp(tol="Low"), f2, dry_spell_mm=100.0))


def test_dry_spell_is_not_assessed_when_rain_values_or_drought_tolerance_are_missing():
    a = advise(sp(tol="Low"), fc_of(rain=[0.0, None] + [0.0] * 14))
    assert "dry_spell" not in codes(a) and any(n["code"] == "dry_spell" and "only 6 of the next 7" in n["reason"] for n in a["not_assessed"])
    b = advise(sp(tol=None), fc_of(rain=[0.0] * 16))
    assert "dry_spell" not in codes(b) and any(n["code"] == "dry_spell" and "drought_tol" in n["reason"] for n in b["not_assessed"])
    c = advise(sp(tol="Low"), {**fc_of(), "daily": daily(drop=("precipitation_sum",))})
    assert codes(c) <= {"not_in_planting_window"} and {n["code"] for n in c["not_assessed"]} >= {"dry_spell", "heavy_rain"}
    short = advise(sp(tol="Low"), fc_of(n=4, rain=[0.0] * 4))
    assert "dry_spell" not in codes(short)


def test_heavy_rain_triggers_on_any_forecast_day_above_the_threshold():
    rain = [5.0] * 16; rain[11] = 95.0
    a = advise(sp(), fc_of(rain=rain))
    w = next(w for w in a["warnings"] if w["code"] == "heavy_rain")
    assert w["numbers"]["max_daily_rain_mm"] == 95.0 and w["numbers"]["date"] == (TODAY + timedelta(days=11)).isoformat() and w["numbers"]["threshold_mm"] == 80.0
    assert w["numbers"]["days_above_threshold"] == [{"date": (TODAY + timedelta(days=11)).isoformat(), "rain_mm": 95.0}]
    rain[11] = 80.0                                                            # exactly the threshold is not above it
    assert "heavy_rain" not in codes(advise(sp(), fc_of(rain=rain)))
    rain[11] = 80.1
    assert "heavy_rain" in codes(advise(sp(), fc_of(rain=rain)))
    assert "heavy_rain" in codes(advise(sp(), fc_of(rain=[5.0] * 16), heavy_rain_mm=4.0))


def test_heavy_rain_does_not_check_missing_days_and_says_so():
    rain = [5.0] * 16; rain[3] = None
    a = advise(sp(), fc_of(rain=rain))
    assert "heavy_rain" not in codes(a) and any(n["code"] == "heavy_rain_partial" and "1 forecast day" in n["reason"] for n in a["not_assessed"])


def test_enso_manual_needs_a_watch_or_alert_and_low_drought_tolerance():
    for status in ("watch", "alert"):
        a = advise(sp(tol="Low"), enso_status=status, enso_source="test outlook 2026-06")
        w = next(w for w in a["warnings"] if w["code"] == "enso_manual")
        assert status in w["message"] and "test outlook 2026-06" in w["message"] and w["numbers"]["drought_tol"] == "Low"
        assert a["enso"]["status"] == status and "cannot tell" in a["enso"]["note"]
        for tol in ("Medium", "High"):
            assert "enso_manual" not in codes(advise(sp(tol=tol), enso_status=status))
    assert "enso_manual" not in codes(advise(sp(tol="Low"), enso_status="none"))
    assert any(n["code"] == "enso_manual" for n in advise(sp(tol=None), enso_status="alert")["not_assessed"])
    with pytest.raises(ValueError, match="enso_status"):
        advise(enso_status="el-nino")
    assert adv.CFG["enso_status"] in adv.ENSO_VALUES


def test_a_quiet_forecast_gives_no_warnings_and_the_response_states_what_it_is():
    a = advise(sp(tol="Medium"), fc_of(rain=[10.0] * 16))
    assert a["warnings"] == [] and a["not_assessed"] == []
    assert "planning aid" in a["disclaimer"] and a["forecast_source"]["name"] == "Open-Meteo" and "open-meteo.com" in a["forecast_source"]["url"]
    assert a["thresholds"] == {"dry_spell_mm": 20.0, "dry_spell_days": 7, "heavy_rain_mm": 80.0}
    assert a["summary"]["forecast_days"] == 16 and a["summary"]["rain_next_window_mm"] == 70.0 and a["summary"]["tmax_c_max"] == 32.0


def test_days_before_today_are_ignored():
    f = fc_of(start=TODAY - timedelta(days=1), rain=[0.0] + [30.0] * 15)       # an old cached forecast starting yesterday
    a = advise(sp(tol="Low"), f)
    assert a["forecast"][0]["date"] == TODAY.isoformat() and a["summary"]["rain_next_window_mm"] == 210.0 and "dry_spell" not in codes(a)


def test_all_warning_codes_are_the_specified_ones_and_thresholds_are_config():
    assert adv.CFG["dry_spell_mm"] == 20.0 and adv.CFG["heavy_rain_mm"] == 80.0 and adv.CFG["cache_hours"] == 3 and adv.CFG["forecast_days"] == 16
    rain = [0.0] * 16; rain[2] = 120.0
    a = advise(sp("1;2", "Low"), fc_of(rain=rain), today=TODAY, enso_status="alert")
    assert codes(a) == {"not_in_planting_window", "heavy_rain", "enso_manual"}          # the 120 mm day lies inside the 7-day window: 120 mm, no dry spell
    b = advise(sp("1;2", "Low"), fc_of(rain=[0.0] * 16), today=TODAY, enso_status="alert")
    assert codes(b) == {"not_in_planting_window", "dry_spell", "enso_manual"}
    assert all({"code", "message", "numbers"} <= set(w) for w in a["warnings"])
