"""Plan tool, part 2: the plan weather advisory (GET /plans/{id}/advisory) and the field-kit information (GET /plans/{id}/field-kit). The network is always mocked.
Run from the repo root: python -m pytest tests/test_api_plan_part2.py"""
import json, sys, urllib.request, zipfile
from datetime import timedelta
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import advisory as adv  # noqa: E402
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def isolated(data, tmp_path, monkeypatch):
    """Plans, kits and the forecast cache go to a temp folder; the internet is blocked."""
    monkeypatch.setattr(data, "work", tmp_path)
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    api_v2.fv.connect(data.field_db).close()
    api_v2.refresh_field(data)

    def blocked(*a, **k):
        raise AssertionError("the internet must not be used in tests")

    monkeypatch.setattr(adv, "http_get", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)


def mock_forecast(monkeypatch, rain=None, calls=None, fail=False):
    today = adv.today_local()
    n = 16

    def fake(url, params, timeout):
        if calls is not None:
            calls.append(params)
        if fail:
            raise OSError("network is down")
        d = {"time": [(today + timedelta(days=i)).isoformat() for i in range(n)], "precipitation_sum": rain if rain is not None else [8.0] * n,
             "temperature_2m_max": [31.0 + i * 0.1 for i in range(n)], "temperature_2m_min": [24.0 - i * 0.1 for i in range(n)]}
        return {"daily": d, "daily_units": {"precipitation_sum": "mm"}}

    monkeypatch.setattr(adv, "http_get", fake)


def make_plan(client, start=None, end=None, barangay="STA ANA", n=40, campaign=True):
    q = {"start": start, "end": end} if start else {}
    body = {"purpose": "urban", "n_saplings": n, "seed": 3, "barangay": barangay}
    if campaign:
        body["campaign"] = {"name": "Test day", "unit": "MENRO"}
    r = client.post("/plan-event", params=q, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def iso(offset):
    return (adv.today_local() + timedelta(days=offset)).isoformat()


# ---- success -------------------------------------------------------------------------------------------------------------------------------
def test_the_advisory_uses_one_forecast_request_and_reports_numbers_and_every_species(client, monkeypatch):
    rain = [10.0, 0.0, 95.0, 5.0, 5.0, 5.0, 5.0] + [2.0] * 9
    plan = make_plan(client, iso(0), iso(20))
    calls = []
    mock_forecast(monkeypatch, rain=rain, calls=calls)
    r = client.get(f"/plans/{plan['plan_id']}/advisory")
    assert r.status_code == 200
    j = r.json()
    assert len(calls) == 1                                                   # ONE forecast request for the whole plan
    f = j["forecast"]
    assert f["first_day"] == iso(0) and f["last_day"] == iso(15) and f["days"] == 16
    assert f["rain_next_days"] == 7 and f["rain_next_days_mm"] == 125.0 and f["max_daily_rain_mm"] == 95.0 and f["max_daily_rain_date"] == iso(2)
    assert f["tmax_c_max"] == pytest.approx(32.5) and f["tmin_c_min"] == pytest.approx(22.5)
    placed = [p for p in plan["palette"] if p["placed"] > 0]
    assert [s["species_id"] for s in j["species"]] == [p["species_id"] for p in placed]
    codes = {x["species_code"] for x in plan["plan"]}
    assert {s["code"] for s in j["species"]} == codes
    for s in j["species"]:
        heavy = [w for w in s["warnings"] if w["code"] == "heavy_rain"]
        assert len(heavy) == 1 and heavy[0]["numbers"]["max_daily_rain_mm"] == 95.0 and "95" in heavy[0]["message"]
    assert j["n_warnings"] == sum(len(s["warnings"]) for s in j["species"]) > 0
    assert j["cached"] is False and j["cache_age_minutes"] == 0.0 and j["forecast_source"]["name"] == "Open-Meteo" and "planning aid" in j["disclaimer"]
    assert j["enso"]["status"] == "none" and j["enso"]["is_default"] is True and j["location"]["note"] == "the centre of the planned trees"
    assert j["window"]["start"] == iso(0) and j["window_covered_by_forecast"] is True and j["window_overlap"] == {"start": iso(0), "end": iso(15)}
    assert "covers" in j["window_message"]


def test_a_missing_forecast_field_is_never_invented(client, monkeypatch):
    plan = make_plan(client, iso(0), iso(20))
    rain = [None] * 16
    mock_forecast(monkeypatch, rain=rain)
    j = client.get(f"/plans/{plan['plan_id']}/advisory").json()
    f = j["forecast"]
    assert f["rain_next_days_mm"] is None and f["max_daily_rain_mm"] is None and f["max_daily_rain_date"] is None and "missing" in f["missing_note"]
    assert all(w["code"] not in ("dry_spell", "heavy_rain") for s in j["species"] for w in s["warnings"])
    assert any(n["code"] == "dry_spell" for s in j["species"] for n in s["not_assessed"])


# ---- cached fallback, no cache -----------------------------------------------------------------------------------------------------------
def test_a_cached_forecast_is_used_when_the_network_fails_and_its_age_is_reported(client, monkeypatch):
    plan = make_plan(client, iso(0), iso(20))
    mock_forecast(monkeypatch)
    first = client.get(f"/plans/{plan['plan_id']}/advisory").json()
    assert first["cached"] is False
    mock_forecast(monkeypatch, fail=True)
    again = client.get(f"/plans/{plan['plan_id']}/advisory").json()                     # fresh cache: the network is not even asked
    assert again["cached"] is True and again["cache_stale"] is False and again["forecast"] == first["forecast"]
    later = adv.now_utc() + timedelta(hours=5)
    monkeypatch.setattr(adv, "now_utc", lambda: later)                                  # the cache is old now and the network is down
    old = client.get(f"/plans/{plan['plan_id']}/advisory").json()
    assert old["cached"] is True and old["cache_stale"] is True and old["cache_age_minutes"] >= 300 and "network is down" in old["network_error"]


def test_no_forecast_and_no_cache_is_a_clear_503(client, monkeypatch):
    plan = make_plan(client, iso(0), iso(20))
    mock_forecast(monkeypatch, fail=True)
    r = client.get(f"/plans/{plan['plan_id']}/advisory")
    assert r.status_code == 503 and "could not be reached" in r.json()["detail"] and "no cached forecast" in r.json()["detail"]


# ---- the planting window against the 16-day forecast ----------------------------------------------------------------------------------
def test_a_window_beyond_the_forecast_is_said_in_plain_words(client, monkeypatch):
    plan = make_plan(client, "2027-05-01", "2027-06-29")
    mock_forecast(monkeypatch)
    j = client.get(f"/plans/{plan['plan_id']}/advisory").json()
    assert j["window_covered_by_forecast"] is False and j["window_overlap"] is None
    assert j["window_message"] == "Your planting dates (1 May - 29 Jun 2027) are beyond the 16-day forecast. The advice below is for the next 16 days only."
    assert j["window"]["label"] == "1 May - 29 Jun 2027"
    assert j["forecast"]["days"] == 16                                                  # the advice itself is still given, for the next 16 days


def test_a_window_that_partly_overlaps_says_which_part(client, monkeypatch):
    plan = make_plan(client, iso(10), iso(40))
    mock_forecast(monkeypatch)
    j = client.get(f"/plans/{plan['plan_id']}/advisory").json()
    assert j["window_covered_by_forecast"] is True and j["window_overlap"] == {"start": iso(10), "end": iso(15)}
    assert "covers" in j["window_message"] and "The rest is outside the forecast" in j["window_message"]


def test_a_window_that_has_passed_and_a_plan_without_dates(client, monkeypatch):
    past = make_plan(client, iso(-30), iso(-10))
    none = make_plan(client, campaign=False)
    mock_forecast(monkeypatch)
    p = client.get(f"/plans/{past['plan_id']}/advisory").json()
    assert p["window_covered_by_forecast"] is False and "have already passed" in p["window_message"]
    n = client.get(f"/plans/{none['plan_id']}/advisory").json()
    assert n["window"] is None and n["window_covered_by_forecast"] is None and "no planting dates saved" in n["window_message"]
    assert all(w["numbers"].get("current_month") for s in n["species"] for w in s["warnings"] if w["code"] == "not_in_planting_window")      # today's month, as before


def test_the_planting_window_warning_compares_the_plans_dates_with_the_species_months(client, monkeypatch):
    plan = make_plan(client, "2026-10-05", "2026-11-04")                                # October and November: outside every species' best months
    mock_forecast(monkeypatch)
    j = client.get(f"/plans/{plan['plan_id']}/advisory").json()
    w = [x for s in j["species"] for x in s["warnings"] if x["code"] == "not_in_planting_window"]
    assert len(w) == len(j["species"]) and all(x["numbers"]["window_months"] == [10, 11] and x["numbers"]["months_in_window"] == [] for x in w)
    assert all("Oct, Nov" in x["message"] and "outside that window" in x["message"] for x in w)
    good = make_plan(client, "2027-05-01", "2027-06-29")
    jg = client.get(f"/plans/{good['plan_id']}/advisory").json()
    for s in jg["species"]:                                                                # May-June: a species is warned only if its months do not cover both
        months = {int(m) for m in str(next(p for p in api_v2.pd.read_csv(PROCESSED / "species_clean.csv").itertuples() if p.species_id == s["species_id"]).planting_months).split(";")}
        warned = [x for x in s["warnings"] if x["code"] == "not_in_planting_window"]
        assert bool(warned) == (not {5, 6} <= months)
        for x in warned:
            assert x["numbers"]["months_in_window"] == sorted(months & {5, 6}) and ("only partly" in x["message"]) == bool(months & {5, 6})


def test_bad_and_unknown_plan_ids(client, monkeypatch):
    mock_forecast(monkeypatch)
    for bad in ("..%2Fx", "a b", "plan%00x", "C%3A%5Cx"):
        assert client.get(f"/plans/{bad}/advisory").status_code in (400, 404, 422)
    assert client.get("/plans/plan_urban_20200101_000000/advisory").status_code == 404


def test_the_seasonal_advisory_of_one_species_is_unchanged(client, data, monkeypatch):
    mock_forecast(monkeypatch)
    r = data.ctx.sites.iloc[100]
    j = client.get("/advisory/seasonal", params={"species_id": 1, "lat": float(r.lat), "lon": float(r.lon)}).json()
    assert {"warnings", "summary", "forecast", "enso", "cached"} <= set(j) and "window_covered_by_forecast" not in j


# ---- field kit information ---------------------------------------------------------------------------------------------------------------
def test_field_kit_info_before_and_after_building_and_after_rebuilding(client, data):
    plan = make_plan(client, iso(0), iso(20))
    pid = plan["plan_id"]
    assert client.get(f"/plans/{pid}/field-kit").json() == {"plan_id": pid, "built": False, "download_url": None,
                                                              "note": f"No field kit has been built for this plan yet (POST /plans/{pid}/field-kit)."}
    assert [p for p in client.get("/plans").json()["plans"] if p["plan_id"] == pid][0]["field_kit_built"] is False
    built = client.post(f"/plans/{pid}/field-kit")
    assert built.status_code == 200
    b = built.json()
    info = client.get(f"/plans/{pid}/field-kit").json()
    assert info["built"] is True and info["check_code"] == b["check_code"] and info["zip_size_bytes"] == b["zip_size_bytes"] and info["pdf_included"] == b["pdf_included"]
    assert info["download_url"] == f"/kits/{pid}.zip" and info["built_at"] and {"points.gpx", "points.kml", "point-list.csv", "manifest.json"} <= set(info["files"])
    assert (info["pdf_note"] is None) == info["pdf_included"]
    z = client.get(info["download_url"])
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    kit = next(Path(data.work / "kits").glob("*.zip"))
    with zipfile.ZipFile(kit) as zf:
        names = zf.namelist()
        assert any(n.endswith("points.gpx") for n in names)
        man = json.loads(zf.read(next(n for n in names if n.endswith("manifest.json"))))
    assert man["check_code"] == b["check_code"] == info["check_code"]
    assert [p for p in client.get("/plans").json()["plans"] if p["plan_id"] == pid][0]["field_kit_built"] is True
    again = client.post(f"/plans/{pid}/field-kit").json()                                # rebuilding replaces the old kit (still one zip, same check code)
    assert again["check_code"] == b["check_code"] and len(list(Path(data.work / "kits").glob("*.zip"))) == 1


def test_field_kit_info_rejects_bad_plan_ids(client):
    for bad in ("..%2Fx", "a b", "plan%00x"):
        assert client.get(f"/plans/{bad}/field-kit").status_code in (400, 404, 422)
    assert client.get("/plans/plan_urban_20200101_000000/field-kit").status_code == 404
