"""GET /weather/week: the week forecast, the week verdict and the two species lists. The network is always mocked.
Run from the repo root: python -m pytest tests/test_api_weather_week.py"""
import json, os, sys, urllib.request
from datetime import date, timedelta
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import advisory as adv  # noqa: E402
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

JUNE = date(2027, 6, 10)            # a day when most species are in their best months
OCT = date(2026, 10, 5)             # a day when none is


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def isolated(data, tmp_path, monkeypatch):
    monkeypatch.setattr(data, "work", tmp_path)                                  # the forecast cache goes to a temp folder
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    api_v2.fv.connect(data.field_db).close()
    api_v2.refresh_field(data)

    def blocked(*a, **k):
        raise AssertionError("the internet must not be used in tests")

    monkeypatch.setattr(adv, "http_get", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)


def set_today(monkeypatch, day):
    monkeypatch.setattr(adv, "today_local", lambda cfg=None: day)


def mock_forecast(monkeypatch, rain=None, calls=None, fail=False, tmax=None):
    today = adv.today_local()
    n = 16

    def fake(url, params, timeout):
        if calls is not None:
            calls.append(params)
        if fail:
            raise OSError("network is down")
        d = {"time": [(today + timedelta(days=i)).isoformat() for i in range(n)], "precipitation_sum": rain if rain is not None else [8.0] * n,
             "temperature_2m_max": tmax if tmax is not None else [30.0 + (i % 5) for i in range(n)], "temperature_2m_min": [23.0 - (i % 3) for i in range(n)]}
        return {"daily": d, "daily_units": {"precipitation_sum": "mm"}}

    monkeypatch.setattr(adv, "http_get", fake)


def at(i):
    """Another place for each call of one test: a fresh saved forecast of the same place (3 h) would otherwise answer instead of the new mock."""
    return {"lat": 14.60 + 0.02 * i, "lon": 121.10 + 0.02 * i}


def week(client, purpose="urban", **q):
    return client.get("/weather/week", params={"purpose": purpose, **q})


def municipal_order(client, purpose, **q):
    return [r["species_id"] for r in client.get("/rank/municipal", params={"purpose": purpose, "limit": 100, **q}).json()["ranking"]]


# ---- success, one request, numbers ----------------------------------------------------------------------------------------------
def test_one_forecast_request_seven_days_summary_and_verdict_numbers(client, monkeypatch):
    set_today(monkeypatch, OCT)
    rain = [10.0, 0.0, 95.0, 5.0, 5.0, 5.0, 5.0] + [2.0] * 9
    calls = []
    mock_forecast(monkeypatch, rain=rain, calls=calls)
    r = week(client)
    assert r.status_code == 200
    j = r.json()
    assert len(calls) == 1                                                       # ONE forecast request
    w = j["week"]
    assert w["n_days"] == 7 and w["first_day"] == "2026-10-05" and w["last_day"] == "2026-10-11" and [x["rain_mm"] for x in w["days"]] == rain[:7]
    assert set(w["days"][0]) == {"date", "rain_mm", "tmax_c", "tmin_c"}
    assert w["rain_total_mm"] == 125.0 and w["wettest_day"] == {"date": "2026-10-07", "rain_mm": 95.0}
    assert w["hottest_day"] == {"date": "2026-10-09", "tmax_c": 34.0} and w["tmax_c_max"] == 34.0 and w["tmin_c_min"] == 21.0
    v = j["verdict"]
    assert v["code"] == "avoid_this_week" and v["label"] == "Avoid this week"
    assert v["reasons"][0]["code"] == "heavy_rain" and v["reasons"][0]["numbers"]["max_daily_rain_mm"] == 95.0 and v["reasons"][0]["numbers"]["threshold_mm"] == 80.0
    assert v["thresholds"] == {"heavy_rain_mm": 80.0, "dry_spell_mm": 20.0, "dry_spell_days": 7}
    assert j["cached"] is False and j["cache_age_minutes"] == 0.0 and j["forecast_source"]["name"] == "Open-Meteo" and "planning aid" in j["disclaimer"]
    assert j["enso"]["status"] == "none" and j["enso"]["is_default"] is True and "not set" in j["enso"]["source"]
    assert j["location"]["note"] == "the centre of San Mateo" and 14.5 < j["location"]["lat"] < 14.8 and 121.0 < j["location"]["lon"] < 121.3
    assert j["include_unzoned"] is True and j["purpose"] == "urban"


def test_a_given_point_is_used_and_validated(client, monkeypatch):
    set_today(monkeypatch, OCT)
    calls = []
    mock_forecast(monkeypatch, calls=calls)
    j = week(client, lat=14.6811, lon=121.1234).json()
    assert calls[0]["latitude"] == 14.68 and calls[0]["longitude"] == 121.12 and j["location"]["note"] == "the place you chose"
    assert week(client, lat=14.68).status_code == 422                            # both or neither
    assert week(client, lat=40.0, lon=100.0).status_code == 422                  # outside San Mateo
    assert client.get("/weather/week").status_code == 422 and client.get("/weather/week", params={"purpose": "fruit"}).status_code == 422


def test_a_missing_forecast_value_is_never_invented(client, monkeypatch):
    set_today(monkeypatch, OCT)
    mock_forecast(monkeypatch, rain=[3.0, None, 3.0, 3.0, 3.0, 3.0, 3.0] + [3.0] * 9)
    j = week(client, **at(0)).json()
    assert j["week"]["rain_total_mm"] is None and "missing" in j["week"]["missing_note"]
    assert j["verdict"]["code"] == "unknown" and j["verdict"]["reasons"][0]["code"] == "rain_values_missing"
    mock_forecast(monkeypatch, rain=[None] * 16, tmax=[None] * 16)
    j2 = week(client, **at(1)).json()
    assert j2["verdict"]["code"] == "unknown" and j2["week"]["wettest_day"] is None and j2["week"]["hottest_day"] is None and j2["week"]["tmax_c_max"] is None


# ---- verdicts -------------------------------------------------------------------------------------------------------------------
def test_good_dry_and_heavy_weeks_get_their_verdicts(client, monkeypatch):
    set_today(monkeypatch, JUNE)
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    good = week(client, **at(0)).json()["verdict"]
    assert good["code"] == "good_to_plant" and good["label"] == "Good to plant" and good["reasons"][0]["numbers"]["forecast_rain_mm"] == 70.0
    mock_forecast(monkeypatch, rain=[1.0] * 16)
    dry = week(client, **at(1)).json()["verdict"]
    assert dry["code"] == "plant_with_care" and dry["reasons"][0]["code"] == "dry_spell" and dry["reasons"][0]["numbers"] == {"forecast_rain_mm": 7.0, "days": 7, "threshold_mm": 20.0}
    mock_forecast(monkeypatch, rain=[1.0, 1.0, 120.0] + [1.0] * 13)
    assert week(client, **at(2)).json()["verdict"]["code"] == "avoid_this_week"


def test_the_verdict_follows_the_configured_thresholds(client, monkeypatch):
    set_today(monkeypatch, JUNE)
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    monkeypatch.setitem(adv.CFG, "dry_spell_mm", 100.0)
    assert week(client).json()["verdict"]["code"] == "plant_with_care"             # the saved forecast is reused: the same numbers, judged with the new threshold
    monkeypatch.setitem(adv.CFG, "heavy_rain_mm", 9.0)
    assert week(client).json()["verdict"]["code"] == "avoid_this_week"


# ---- the species lists ----------------------------------------------------------------------------------------------------------
def test_in_october_no_species_is_in_its_best_months_and_the_water_list_has_only_drought_tolerant_ones(client, data, monkeypatch):
    set_today(monkeypatch, OCT)
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    j = week(client).json()
    sp = j["species"]
    assert sp["best_months"]["items"] == [] and sp["best_months"]["count"] == 0
    assert sp["best_months"]["empty_reason"] == {"code": "none_in_best_months", "message": "No species are in their best months this week. Most are best planted May to July."}
    assert sp["most_species_months"]["months"] == [5, 6, 7] and sp["week_months"] == ["Oct"]
    water = sp["only_if_you_can_water"]
    assert water["label"] == "Only if you can water" and water["count"] == len(water["items"]) > 0 and water["empty_reason"] is None
    sp_tab = data.ctx.species.set_index("species_id")
    for it in water["items"]:
        assert it["drought_tol"] == "High" == sp_tab.drought_tol[it["species_id"]] and it["season"]["status"] == "out_of_season"
        assert it["label"] == "Only if you can water" and "only if you can water" in it["reason"] and it["warnings"] == []
        assert it["source_ids"] and it["species_id"] in {int(s) for s in sp_tab.index}
    assert j["species"]["held_back"] == [] and [it["rank"] for it in water["items"]] == sorted(it["rank"] for it in water["items"])
    assert [it["species_id"] for it in water["items"]] == [s for s in municipal_order(client, "urban") if s in {i["species_id"] for i in water["items"]}]
    assert j["sources"] and all(str(i) in j["sources"] for it in water["items"] for i in it["source_ids"].values())
    # every High drought tolerance species that is outside its best months is listed, none other
    months = {int(r.species_id): api_v2.pal.parse_months(r.planting_months) for r in data.ctx.species.itertuples(index=False)}
    want = {s for s, t in sp_tab.drought_tol.items() if t == "High" and months[int(s)] is not None and 10 not in months[int(s)]}
    assert {it["species_id"] for it in water["items"]} == {int(s) for s in want}


def test_in_june_the_species_in_their_best_months_are_ranked_by_the_municipal_score(client, data, monkeypatch):
    set_today(monkeypatch, JUNE)
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    for purpose in ("urban", "planting", "watershed"):
        j = week(client, purpose).json()
        best = j["species"]["best_months"]
        assert best["items"] and best["empty_reason"] is None and all(it["season"]["status"] == "in_season" and 6 in it["season"]["species_months"] for it in best["items"])
        assert all(it["warnings"] == [] for it in best["items"]) and j["species"]["held_back"] == []
        order = municipal_order(client, purpose)
        assert [it["species_id"] for it in best["items"]] == [s for s in order if s in {i["species_id"] for i in best["items"]}]
        assert all("In its best months" in it["reason"] for it in best["items"])
        scores = {r["species_id"]: r["species_score"] for r in client.get("/rank/municipal", params={"purpose": purpose, "limit": 100}).json()["ranking"]}
        assert all(it["species_score"] == scores[it["species_id"]] for it in best["items"])
        assert not {it["species_id"] for it in best["items"]} & {it["species_id"] for it in j["species"]["only_if_you_can_water"]["items"]}


def test_a_dry_week_holds_back_species_without_high_drought_tolerance(client, monkeypatch):
    set_today(monkeypatch, JUNE)
    mock_forecast(monkeypatch, rain=[1.0] * 16)
    j = week(client).json()
    assert j["verdict"]["code"] == "plant_with_care"
    best, held = j["species"]["best_months"]["items"], j["species"]["held_back"]
    assert best and all(it["drought_tol"] == "High" for it in best)
    assert held and all(it["list"] == "best_months" and any(w["code"] == "dry_spell" for w in it["warnings"]) and it["drought_tol"] != "High" for it in held)
    w0 = next(w for w in held[0]["warnings"] if w["code"] == "dry_spell")
    assert w0["numbers"]["forecast_rain_mm"] == 7.0 and "watering" in w0["message"]


def test_a_heavy_rain_week_holds_everything_back_with_a_plain_reason(client, monkeypatch):
    set_today(monkeypatch, JUNE)
    mock_forecast(monkeypatch, rain=[5.0, 5.0, 130.0] + [5.0] * 13)
    j = week(client).json()
    assert j["verdict"]["code"] == "avoid_this_week"
    assert j["species"]["best_months"]["items"] == [] and j["species"]["best_months"]["empty_reason"]["code"] == "all_held_back_by_warnings"
    assert "Held back" in j["species"]["best_months"]["empty_reason"]["message"]
    held = j["species"]["held_back"]
    assert held and all(any(w["code"] == "heavy_rain" and w["numbers"]["max_daily_rain_mm"] == 130.0 for w in it["warnings"]) for it in held)


def test_the_el_nino_setting_holds_back_low_drought_tolerance_species(client, monkeypatch):
    set_today(monkeypatch, JUNE)
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    monkeypatch.setitem(adv.CFG, "enso_status", "watch")
    monkeypatch.setitem(adv.CFG, "enso_source", "PAGASA outlook, 1 Jun 2027")
    j = week(client).json()
    assert j["enso"]["status"] == "watch" and j["enso"]["is_default"] is False
    held = j["species"]["held_back"]
    assert held and all(it["drought_tol"] == "Low" and any(w["code"] == "enso_manual" for w in it["warnings"]) for it in held)
    assert all(it["drought_tol"] != "Low" for it in j["species"]["best_months"]["items"])


def test_a_week_that_crosses_a_month_end_marks_species_partly_in_season(client, monkeypatch):
    set_today(monkeypatch, date(2027, 8, 29))                                    # 29 Aug to 4 Sep: August and September
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    j = week(client).json()
    assert j["species"]["week_months"] == ["Aug", "Sep"]
    items = j["species"]["best_months"]["items"] + [i for i in j["species"]["held_back"] if i["list"] == "best_months"]
    assert items and {it["season"]["status"] for it in items} <= {"in_season", "partly"} and "partly" in {it["season"]["status"] for it in items}
    assert all(("Only part of this week" in it["reason"]) == (it["season"]["status"] == "partly") for it in items)


# ---- cache and network ----------------------------------------------------------------------------------------------------------
def test_a_fresh_saved_forecast_is_used_when_the_network_is_down(client, monkeypatch):
    set_today(monkeypatch, OCT)
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    first = week(client).json()
    assert first["cached"] is False
    mock_forecast(monkeypatch, fail=True)
    again = week(client)
    assert again.status_code == 200 and again.json()["cached"] is True and again.json()["week"]["days"] == first["week"]["days"]


def test_a_stale_saved_forecast_is_shown_with_its_age_and_the_network_error(client, data, monkeypatch):
    set_today(monkeypatch, OCT)
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    week(client)
    for f in (data.work / "cache").glob("openmeteo_*.json"):
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc["fetched_at"] = (adv.now_utc() - timedelta(hours=5)).isoformat()
        f.write_text(json.dumps(doc), encoding="utf-8")
    mock_forecast(monkeypatch, fail=True)
    j = week(client).json()
    assert j["cached"] is True and j["cache_stale"] is True and 295 < j["cache_age_minutes"] < 305 and "network is down" in j["network_error"]
    assert j["verdict"]["code"] == "good_to_plant" and j["week"]["n_days"] == 7


def test_no_forecast_and_no_saved_copy_is_a_503_with_a_plain_message(client, monkeypatch):
    set_today(monkeypatch, OCT)
    mock_forecast(monkeypatch, fail=True)
    r = week(client)
    assert r.status_code == 503 and "could not be reached" in r.json()["detail"] and "no cached forecast" in r.json()["detail"]


def test_a_forecast_shorter_than_a_week_is_reported_not_padded(client, monkeypatch):
    set_today(monkeypatch, OCT)
    n = 3

    def fake(url, params, timeout):
        t = adv.today_local()
        return {"daily": {"time": [(t + timedelta(days=i)).isoformat() for i in range(n)], "precipitation_sum": [1.0] * n,
                          "temperature_2m_max": [31.0] * n, "temperature_2m_min": [24.0] * n}}

    monkeypatch.setattr(adv, "http_get", fake)
    j = week(client).json()
    assert j["week"]["n_days"] == 3 and "only 3 of the next 7 days" in j["week"]["short_note"] and j["week"]["rain_total_mm"] is None and j["verdict"]["code"] == "unknown"


# ---- the switch -----------------------------------------------------------------------------------------------------------------
def test_the_species_ranking_follows_include_unzoned(client, monkeypatch):
    set_today(monkeypatch, JUNE)
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    for q in ({}, {"include_unzoned": "false"}):
        j = week(client, **q).json()
        ids = [it["species_id"] for it in j["species"]["best_months"]["items"]]
        assert ids == [s for s in municipal_order(client, "urban", **q) if s in set(ids)] and j["include_unzoned"] is (not q)
