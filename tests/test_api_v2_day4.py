"""Day 4 part 2 tests for api_v2.py: saved plans, field kits, the weather advisory, and a smoke test of the old endpoints.
The Open-Meteo call is always mocked. Outputs go to a temp folder. Run from the repo root:  python -m pytest tests/test_api_v2_day4.py"""
import hashlib, io, json, re, sys, urllib.request, zipfile
from datetime import timedelta
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import advisory as adv  # noqa: E402
import api_v2  # noqa: E402
import run_plan as rp  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    api_v2.API_CFG["include_unzoned"] = False            # these tests pin the behaviour of include_unzoned=false (the squares outside the zoning map are not planting squares)
    try:
        with TestClient(api_v2.app) as c:
            yield c
    finally:
        api_v2.API_CFG["include_unzoned"] = True


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def _isolated(data, tmp_path, monkeypatch):
    monkeypatch.setattr(data, "work", tmp_path)                       # plans, kits and the forecast cache go to a temp folder
    def blocked(*a, **k):
        raise AssertionError("the tests must not use the network")
    monkeypatch.setattr(adv, "http_get", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)


def post_plan(client, n=60, purpose="urban", **kw):
    r = client.post("/plan-event", json={"purpose": purpose, "n_saplings": n, **kw})
    assert r.status_code == 200, r.text
    return r.json()


# ---- saved plans -----------------------------------------------------------------------------------------------------
def test_plan_event_saves_the_plan_and_summary_like_run_plan_and_returns_a_plan_id(client, tmp_path):
    j = post_plan(client, 60, "planting", seed=5)
    pid = j["plan_id"]
    assert re.fullmatch(r"plan_planting_\d{8}_\d{6}(-\d+)?", pid) and api_v2.valid_plan_id(pid)
    csv, js = tmp_path / "plans" / f"{pid}.csv", tmp_path / "plans" / f"{pid}_summary.json"
    assert csv.is_file() and js.is_file()
    saved = pd.read_csv(csv)
    assert list(saved.columns) == rp.PLAN_COLUMNS and len(saved) == len(j["plan"]) == 60            # exactly the run_plan.py format
    s = json.loads(js.read_text(encoding="utf-8"))
    assert s["purpose"] == "planting" and s["saplings_placed"] == 60 and s["plan_file"] == csv.name and s["seed"] == 5 and s["palette"] and s["limits"]
    assert j["saved"] == {"plan_csv": csv.name, "summary_json": js.name, "folder": f"{api_v2.API_CFG['data_dir']}/plans"} and j["next"]["build_field_kit"] == f"POST /plans/{pid}/field-kit"
    assert set(saved.point_id) == {i["point_id"] for i in j["plan"]}


def test_failed_plans_are_not_saved(client, tmp_path):
    assert client.post("/plan-event", json={"purpose": "urban", "n_saplings": 10, "zone": "Moon Base"}).status_code == 400
    assert client.post("/plan-event", json={"purpose": "fruit", "n_saplings": 10}).status_code == 422
    assert not list((tmp_path / "plans").glob("*")) if (tmp_path / "plans").exists() else True


def test_two_plans_in_the_same_second_get_different_ids(client, monkeypatch):
    class Fixed:
        @staticmethod
        def now():
            from datetime import datetime
            return datetime(2026, 10, 5, 12, 0, 0)
    monkeypatch.setattr(api_v2, "datetime", Fixed)
    a, b = post_plan(client, 12)["plan_id"], post_plan(client, 12)["plan_id"]
    assert a == "plan_urban_20261005_120000" and b == "plan_urban_20261005_120000-2"


def test_plans_list_shows_recent_plans_newest_first_with_purpose_count_and_date(client):
    assert client.get("/plans").json() == {"count": 0, "total_saved": 0, "plans": []}
    a = post_plan(client, 20, "urban")["plan_id"]
    b = post_plan(client, 25, "watershed")["plan_id"]
    j = client.get("/plans").json()
    assert j["total_saved"] == 2 and {p["plan_id"] for p in j["plans"]} == {a, b}
    by = {p["plan_id"]: p for p in j["plans"]}
    assert by[a]["purpose"] == "urban" and by[a]["n_placed"] == 20 and by[b]["purpose"] == "watershed" and by[b]["n_placed"] == 25
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", by[a]["date"]) and by[a]["field_kit_built"] is False
    dates = [p["date"] for p in j["plans"]]
    assert dates == sorted(dates, reverse=True)
    assert client.get("/plans", params={"limit": 1}).json()["count"] == 1
    assert client.get("/plans", params={"limit": 0}).status_code == 422


def test_plans_list_ignores_files_that_are_not_complete_plans(client, tmp_path):
    post_plan(client, 10)
    d = tmp_path / "plans"
    (d / "plan_urban_20200101_000000_summary.json").write_text("{}")             # summary without a plan csv
    (d / "plan_urban_20200101_000001.csv").write_text("x")                       # csv without a summary
    (d / "notes.txt").write_text("x")
    assert client.get("/plans").json()["total_saved"] == 1


def test_get_saved_plan_returns_the_plan_summary_and_sources(client):
    j = post_plan(client, 40, "watershed")
    g = client.get(f"/plans/{j['plan_id']}")
    assert g.status_code == 200
    k = g.json()
    assert k["plan_id"] == j["plan_id"] and k["purpose"] == "watershed" and len(k["plan"]) == 40
    assert [i["point_id"] for i in k["plan"]] == [i["point_id"] for i in j["plan"]] and k["palette"] and k["summary"]["saplings_placed"] == 40
    assert k["unmatched"]["saplings_unmatched"] == 0 and k["limits"] and k["field_kit_built"] is False
    for i in k["plan"][:5]:
        assert all(k["sources"][str(s)]["url"] for s in i["site_scores_source_ids"])
    assert client.get("/plans/plan_urban_20200101_000000").status_code == 404
    assert "GET /plans" in client.get("/plans/plan_urban_20200101_000000").json()["detail"]


BAD_IDS = ["..", "%2E%2E", "../etc/passwd", "..%2Fsecret", "%2E%2E%2Fsecret", "%2Fetc%2Fpasswd", "C%3A%5Cwindows%5Cwin.ini", "plan.csv", "a%20b",
           "plan_urban_1%00", "x" * 101, "plan%5Cx", "a%2Fb", "%E2%80%A6"]


@pytest.mark.parametrize("bad", BAD_IDS)
def test_a_bad_plan_id_never_reaches_the_file_system(client, tmp_path, bad):
    (tmp_path / "secret.csv").write_text("point_id\n1\n"); (tmp_path / "secret_summary.json").write_text("{}")   # outside plans/
    post_plan(client, 10)
    for method, url in (("get", f"/plans/{bad}"), ("post", f"/plans/{bad}/field-kit"), ("get", f"/kits/{bad}.zip")):
        r = getattr(client, method)(url)
        assert r.status_code in (400, 404, 405), (method, url, r.status_code)
        assert r.status_code != 200


def test_plan_id_validation_rules():
    ok = ["plan_urban_20261005_021810", "plan-1", "A_b-9", "x"]
    bad = ["", "../x", "..", "/etc/passwd", "C:\\x", "a b", "a.b", "a/b", "a\\b", "plan\n", "é", "x" * 101, None, 5]
    assert all(api_v2.valid_plan_id(x) for x in ok) and not any(api_v2.valid_plan_id(x) for x in bad)
    for x in ("", "../x", "/abs"):
        with pytest.raises(api_v2.HTTPException) as e:
            api_v2.check_plan_id(x)
        assert e.value.status_code == 400 and "letters, digits, underscore and hyphen" in e.value.detail


# ---- field kits ------------------------------------------------------------------------------------------------------
def test_field_kit_is_built_from_a_saved_plan_and_the_zip_downloads(client, tmp_path):
    j = post_plan(client, 40)
    pid = j["plan_id"]
    assert client.get(f"/kits/{pid}.zip").status_code == 404
    r = client.post(f"/plans/{pid}/field-kit")
    assert r.status_code == 200, r.text
    k = r.json()
    csv_bytes = (tmp_path / "plans" / f"{pid}.csv").read_bytes()
    assert k["plan_id"] == pid and k["check_code"] == hashlib.sha256(csv_bytes).hexdigest()[:8] and k["download_url"] == f"/kits/{pid}.zip"
    names = {f["name"] for f in k["manifest"]["files"]}
    assert {"points.gpx", "points.kml", "point-list.csv", "README.txt"} <= names and k["manifest"]["counts"]["points"] == 40
    assert k["manifest"]["plan_summary"]["purpose"] == "urban" and k["manifest"]["limits"]
    pytest.importorskip("matplotlib")
    assert k["pdf_included"] is True and "field-map.pdf" in names and k["pdf_note"] is None
    z = client.get(f"/kits/{pid}.zip")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip" and "attachment" in z.headers["content-disposition"]
    assert len(z.content) == k["zip_size_bytes"]
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        inside = zf.namelist()
        assert f"field_kit_{pid}/points.gpx" in inside and f"field_kit_{pid}/field-map.pdf" in inside
        gpx = zf.read(f"field_kit_{pid}/points.gpx").decode("utf-8")
        assert gpx.count("<wpt ") == 40 and k["check_code"] in gpx
        m = json.loads(zf.read(f"field_kit_{pid}/manifest.json"))
        assert m["check_code"] == k["check_code"]
    assert client.get(f"/plans/{pid}").json()["field_kit_built"] is True
    assert client.get("/plans").json()["plans"][0]["field_kit_built"] is True


def test_field_kit_skips_the_pdf_and_says_so_when_matplotlib_is_missing(client, monkeypatch):
    pid = post_plan(client, 15)["plan_id"]
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    k = client.post(f"/plans/{pid}/field-kit").json()
    assert k["pdf_included"] is False and "matplotlib is not installed" in k["pdf_note"]
    assert "field-map.pdf" not in {f["name"] for f in k["manifest"]["files"]} and "points.gpx" in {f["name"] for f in k["manifest"]["files"]}
    z = client.get(f"/kits/{pid}.zip")
    assert z.status_code == 200 and f"field_kit_{pid}/points.gpx" in zipfile.ZipFile(io.BytesIO(z.content)).namelist()


def test_kit_errors_are_clear(client):
    r = client.post("/plans/plan_urban_20200101_000000/field-kit")
    assert r.status_code == 404 and "not found" in r.json()["detail"]
    pid = post_plan(client, 10)["plan_id"]
    r = client.get(f"/kits/{pid}.zip")
    assert r.status_code == 404 and "has been built" in r.json()["detail"] and f"POST /plans/{pid}/field-kit" in r.json()["detail"]
    r = client.get(f"/kits/{pid}.pdf")
    assert r.status_code == 404 and ".zip" in r.json()["detail"]
    assert client.get("/kits/bad..id.zip").status_code == 400


def test_the_user_never_supplies_a_file_path(client):
    paths = {r.path: r for r in client.app.routes if hasattr(r, "methods")}
    for route in ("/plans/{plan_id}", "/plans/{plan_id}/field-kit", "/kits/{filename}"):
        names = {p.name for p in paths[route].dependant.path_params}
        assert names <= {"plan_id", "filename"}
    body_fields = set(api_v2.PlanRequest.model_fields)
    assert body_fields == {"purpose", "n_saplings", "polygon", "zone", "barangay", "seed", "campaign", "species_ids", "species_counts", "layout_mode"}                     # nothing that names a file


# ---- weather advisory ------------------------------------------------------------------------------------------------
@pytest.fixture
def species(data):
    sp = data.ctx.species
    return {"low": int(sp[sp.drought_tol == "Low"].species_id.iloc[0]), "high": int(sp[sp.drought_tol == "High"].species_id.iloc[0]),
            "med": int(sp[sp.drought_tol == "Medium"].species_id.iloc[0])}


def mock_forecast(monkeypatch, rain=None, drop=(), calls=None):
    today = adv.today_local()
    n = 16
    def fake(url, params, timeout):
        if calls is not None:
            calls.append(params)
        d = {"time": [(today + timedelta(days=i)).isoformat() for i in range(n)], "precipitation_sum": rain if rain is not None else [8.0] * n,
             "temperature_2m_max": [31.0] * n, "temperature_2m_min": [24.0] * n}
        for k in drop:
            d.pop(k)
        return {"daily": d, "daily_units": {"precipitation_sum": "mm"}}
    monkeypatch.setattr(adv, "http_get", fake)


def region(data):
    r = data.ctx.sites.iloc[100]
    return {"lat": float(r.lat), "lon": float(r.lon)}


def in_window(data, sid):
    months = adv.parse_months(data.ctx.species.set_index("species_id").planting_months[sid])
    return adv.today_local().month in months


def test_advisory_endpoint_returns_warnings_with_codes_sentences_numbers_and_sources(client, data, species, monkeypatch):
    calls = []
    mock_forecast(monkeypatch, rain=[1.0] * 16, calls=calls)
    r = client.get("/advisory/seasonal", params={"species_id": species["low"], **region(data)})
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(calls) == 1 and calls[0]["forecast_days"] == 16
    w = {x["code"]: x for x in j["warnings"]}
    assert "dry_spell" in w and w["dry_spell"]["numbers"]["forecast_rain_mm"] == 7.0 and "7.0 mm" in w["dry_spell"]["message"]
    assert all({"code", "message", "numbers"} <= set(x) for x in j["warnings"])
    assert "planning aid" in j["disclaimer"] and j["forecast_source"]["name"] == "Open-Meteo" and j["cached"] is False and len(j["forecast"]) == 16
    assert j["species"]["drought_tol"] == "Low" and j["species"]["planting_months_names"]
    for sid in j["species"]["source_ids"].values():
        assert j["sources"][str(sid)]["url"] and "rank" in j["sources"][str(sid)]
    assert set(j["species"]["source_ids"]) == {"months_raw", "drought_tol"} and j["thresholds"]["heavy_rain_mm"] == 80.0


def test_advisory_warnings_trigger_and_do_not_trigger_through_the_api(client, data, species, monkeypatch):
    loc = region(data)
    get = lambda sid: client.get("/advisory/seasonal", params={"species_id": sid, **loc}).json()
    mock_forecast(monkeypatch, rain=[0.0] * 16)
    assert "dry_spell" in {w["code"] for w in get(species["low"])["warnings"]}
    assert "dry_spell" in {w["code"] for w in get(species["med"])["warnings"]}
    assert "dry_spell" not in {w["code"] for w in get(species["high"])["warnings"]}
    rain = [5.0] * 16; rain[9] = 150.0
    (data.work / "cache").mkdir(exist_ok=True)
    for f in (data.work / "cache").glob("*.json"):
        f.unlink()
    mock_forecast(monkeypatch, rain=rain)
    h = {w["code"]: w for w in get(species["med"])["warnings"]}
    assert h["heavy_rain"]["numbers"]["max_daily_rain_mm"] == 150.0 and "dry_spell" not in h
    for f in (data.work / "cache").glob("*.json"):
        f.unlink()
    mock_forecast(monkeypatch, rain=[5.0] * 16)
    assert not {"heavy_rain", "dry_spell"} & {w["code"] for w in get(species["med"])["warnings"]}


def test_advisory_planting_window_warning_follows_the_current_month(client, data, species, monkeypatch):
    sid = species["med"]
    months = adv.parse_months(data.ctx.species.set_index("species_id").planting_months[sid])
    from datetime import datetime, timezone
    out_month = next(m for m in range(1, 13) if m not in months)
    in_month = months[0]
    for month, expect in ((out_month, True), (in_month, False)):
        monkeypatch.setattr(adv, "now_utc", lambda m=month: datetime(2026, m, 15, 4, 0, tzinfo=timezone.utc))
        mock_forecast(monkeypatch)
        for f in (data.work / "cache").glob("*.json") if (data.work / "cache").exists() else []:
            f.unlink()
        j = client.get("/advisory/seasonal", params={"species_id": sid, **region(data)}).json()
        got = [w for w in j["warnings"] if w["code"] == "not_in_planting_window"]
        assert bool(got) is expect
        if got:
            assert got[0]["numbers"]["current_month"] == month and got[0]["numbers"]["planting_months"] == months


def test_advisory_enso_is_set_by_hand(client, data, species, monkeypatch):
    mock_forecast(monkeypatch, rain=[10.0] * 16)
    loc = region(data)
    base = client.get("/advisory/seasonal", params={"species_id": species["low"], **loc}).json()
    assert "enso_manual" not in {w["code"] for w in base["warnings"]} and base["enso"]["status"] == "none"
    monkeypatch.setitem(adv.CFG, "enso_status", "watch")
    monkeypatch.setitem(adv.CFG, "enso_source", "test outlook")
    j = client.get("/advisory/seasonal", params={"species_id": species["low"], **loc}).json()
    assert "enso_manual" in {w["code"] for w in j["warnings"]} and j["enso"]["source"] == "test outlook"
    j2 = client.get("/advisory/seasonal", params={"species_id": species["high"], **loc}).json()
    assert "enso_manual" not in {w["code"] for w in j2["warnings"]}


def test_advisory_uses_the_cache_when_the_network_fails_and_marks_it(client, data, species, monkeypatch):
    loc = region(data)
    mock_forecast(monkeypatch)
    ok = client.get("/advisory/seasonal", params={"species_id": species["med"], **loc}).json()
    assert ok["cached"] is False and list((data.work / "cache").glob("openmeteo_*.json"))
    monkeypatch.setitem(adv.CFG, "cache_hours", 0)                                      # force a refresh attempt
    monkeypatch.setattr(adv, "http_get", lambda *a: (_ for _ in ()).throw(OSError("network is down")))
    j = client.get("/advisory/seasonal", params={"species_id": species["med"], **loc}).json()
    assert j["cached"] is True and j["cache_age_minutes"] >= 0 and "OSError" in j["network_error"] and j["cache_stale"] is True
    assert len(j["forecast"]) == 16 and j["forecast_fetched_at"] == ok["forecast_fetched_at"]


def test_advisory_without_network_and_without_cache_is_a_clear_503(client, data, species, monkeypatch):
    monkeypatch.setattr(adv, "http_get", lambda *a: (_ for _ in ()).throw(TimeoutError("timed out")))
    r = client.get("/advisory/seasonal", params={"species_id": species["low"], **region(data)})
    assert r.status_code == 503 and "Open-Meteo" in r.json()["detail"] and "no cached forecast" in r.json()["detail"]


def test_advisory_never_invents_values_for_missing_forecast_fields(client, data, species, monkeypatch):
    mock_forecast(monkeypatch, drop=("precipitation_sum", "temperature_2m_min"))
    j = client.get("/advisory/seasonal", params={"species_id": species["low"], **region(data)}).json()
    assert {w["code"] for w in j["warnings"]} <= {"not_in_planting_window", "enso_manual"}
    assert {"dry_spell", "heavy_rain"} <= {n["code"] for n in j["not_assessed"]}
    assert all(d["rain_mm"] is None and d["tmin_c"] is None and d["tmax_c"] == 31.0 for d in j["forecast"])
    assert j["summary"]["rain_next_window_mm"] is None and j["summary"]["max_daily_rain_mm"] is None and j["summary"]["tmin_c_min"] is None


def test_advisory_validation(client, data, monkeypatch):
    mock_forecast(monkeypatch)
    loc = region(data)
    r = client.get("/advisory/seasonal", params={"species_id": 999, **loc})
    assert r.status_code == 404 and "not found" in r.json()["detail"]
    r = client.get("/advisory/seasonal", params={"species_id": 1, "lat": 10.0, "lon": 120.0})
    assert r.status_code == 422 and "outside the San Mateo area" in r.json()["detail"]
    assert client.get("/advisory/seasonal", params={"species_id": 1, "lat": 95, "lon": 121}).status_code == 422
    assert client.get("/advisory/seasonal", params={"lat": 14.7, "lon": 121.1}).status_code == 422


# ---- the old endpoints still work ------------------------------------------------------------------------------------
def test_the_earlier_endpoints_still_work(client, data):
    r = data.ctx.sites[data.ctx.sites.zone_desc == "Forest Zone"].iloc[100]
    lat, lon = float(r.lat), float(r.lon)
    assert client.get("/health").json()["counts"]["species"] == 45
    assert client.get("/species").json()["count"] == 45 and client.get("/species/1").json()["common_name"] == "Narra"
    assert client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon}).json()["returned"] == 10
    assert client.get("/rank/municipal", params={"purpose": "planting"}).json()["returned"] == 15
    assert client.get("/search/species", params={"q": "narra"}).json()["count"] >= 1
    assert client.get("/search/place", params={"q": "sta ana"}).json()["count"] == 1
    assert client.get("/nearest-viable", params={"purpose": "urban", "lat": lat, "lon": lon}).json()["already_viable"] is True
    j = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 30, "seed": 1}).json()
    assert len(j["plan"]) == 30 and j["plan_id"] and j["palette"] and j["sources"]
    assert client.get("/rank", params={"purpose": "urban", "lat": 15.5, "lon": 121.5}).status_code == 404
