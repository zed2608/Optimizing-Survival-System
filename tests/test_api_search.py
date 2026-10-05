"""Tests for the search endpoints of api_v2.py (/search/place, /search/point, /search/all, /plans/{id}/points, /search/geocode) and the
coordinate parser of the dashboard (frontend/src/new/coords.js, run with node). The internet is never used: the geocoder's HTTP function is replaced.
Run from the repo root: python -m pytest tests/test_api_search.py"""
import json, shutil, subprocess, sys, time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import field_kit as fk  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def fresh(data, tmp_path, monkeypatch):
    """Own plans folder, geocoder cache and field database per test; the geocoder starts disabled with a real clock."""
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(data, "work", tmp_path)
    api_v2.fv.connect(data.field_db).close()
    api_v2.refresh_field(data)
    monkeypatch.setitem(data.cfg, "geocoder_enabled", False)
    monkeypatch.setitem(data.cfg, "geocoder_contact", "")
    monkeypatch.setattr(data.geo, "last", None)
    monkeypatch.setattr(data.geo, "clock", time.monotonic)
    monkeypatch.setattr(data.geo, "sleep", time.sleep)
    data.plan_index_cache.clear()


def make_plan(client, purpose="urban", n=40, seed=1):
    r = client.post("/plan-event", json={"purpose": purpose, "n_saplings": n, "seed": seed})
    assert r.status_code == 200
    return r.json()


# ---- barangays: accents, case, Sta/Sto ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("q,expected", [("sta ana", "STA ANA"), ("STA. ANA", "STA ANA"), ("Santa Ana", "STA ANA"), ("sto nino", "STO NINO"),
                                        ("Santo Niño", "STO NINO"), ("SANTO NIÑO", "STO NINO"), ("stó niño", "STO NINO"), ("  guitnang  ", "GUITNANG BAYAN"),
                                        ("DULONG bayan", "DULONG BAYAN I")])
def test_barangay_search_ignores_accents_case_and_sta_sto(client, q, expected):
    for url in ("/search/place", "/search/all"):
        r = client.get(url, params={"q": q})
        assert r.status_code == 200, (url, q)
        hits = r.json()["results"] if url == "/search/place" else r.json()["barangays"]
        assert expected in [h["name"] for h in hits], (url, q, [h["name"] for h in hits])


def test_search_place_hits_carry_a_type_and_keep_their_old_keys(client):
    hit = client.get("/search/place", params={"q": "sta ana"}).json()["results"][0]
    assert hit["type"] == "barangay" and hit["display_name"] == "Santa Ana"
    for k in ("name", "centroid", "bounds", "bounds_order", "source"):
        assert k in hit
    assert client.get("/search/place", params={"q": "!!!"}).status_code == 422


def test_all_returns_species_by_common_or_scientific_name(client):
    r = client.get("/search/all", params={"q": "narra"}).json()
    assert [s["common_name"] for s in r["species"]][:1] == ["Narra"] and r["species"][0]["type"] == "species"
    r2 = client.get("/search/all", params={"q": "pterocarpus"}).json()
    assert any(s["common_name"] == "Narra" for s in r2["species"])


# ---- grid points -------------------------------------------------------------------------------------------------------------
def test_search_point_found_not_found_and_bad_input(client, data):
    r = client.get("/search/point", params={"q": "832"})
    assert r.status_code == 200
    j = r.json()
    assert j["point_id"] == 832 and j["type"] == "grid_point" and j["barangay_display"] and isinstance(j["legal_zone"], bool)
    assert -90 < j["lat"] < 90 and 120 < j["lon"] < 122
    nl = int(data.all_points[~data.all_points.is_legal_zone.astype(bool)].point_id.iloc[0])      # a point outside every planting zone is still found
    j2 = client.get("/search/point", params={"q": str(nl)}).json()
    assert j2["legal_zone"] is False and "not in a legal planting zone" in j2["note"]
    r404 = client.get("/search/point", params={"q": "99999999"})
    assert r404.status_code == 404 and "no grid point" in r404.json()["detail"]
    for bad in ("abc", "12a", "-5", "1.5", "832; DROP", "1234567890"):
        assert client.get("/search/point", params={"q": bad}).status_code == 422, bad


def test_all_finds_a_grid_point_by_digits(client):
    j = client.get("/search/all", params={"q": "832"}).json()
    assert [p["point_id"] for p in j["points"]] == [832]


# ---- plan points -------------------------------------------------------------------------------------------------------------
def test_plan_items_carry_point_ref_species_code_and_barangay_without_changing_the_saved_csv(client, data):
    plan = make_plan(client)
    it = plan["plan"][0]
    assert {"point_ref", "species_code", "barangay"} <= set(it)
    assert it["point_ref"].startswith(it["species_code"] + "-")
    cols = client.get(f"/plans/{plan['plan_id']}").json()["plan"][0]
    assert cols["point_ref"] == it["point_ref"]
    saved_cols = Path(data.work / "plans" / f"{plan['plan_id']}.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert saved_cols == api_v2.rp.PLAN_COLUMNS                         # the saved file is exactly as before


def test_plan_item_refs_match_the_field_kit_numbering(client, data, tmp_path):
    plan = make_plan(client)
    made = fk.make_kit(Path(data.work) / "plans" / f"{plan['plan_id']}.csv", tmp_path / "kits", pdf=False, data_dir=PROCESSED, built_on="2026-10-05")
    import csv
    with open(made["kit_dir"] / "point-list.csv", newline="", encoding="utf-8") as f:
        kit = {int(r["point_id"]): r["point_ref"] for r in csv.DictReader(f)}
    for it in plan["plan"]:
        assert kit[it["point_id"]] == it["point_ref"]


def test_plan_points_search_by_ref_code_name_and_id_case_insensitively(client):
    plan = make_plan(client)
    pid = plan["plan_id"]
    it = plan["plan"][0]
    ref = it["point_ref"]
    for q in (ref, ref.lower(), ref.replace("-", " "), ref.replace("-", "").lower()):
        j = client.get(f"/plans/{pid}/points", params={"q": q}).json()
        assert j["points"] and j["points"][0]["point_ref"] == ref, q
    j = client.get(f"/plans/{pid}/points", params={"q": it["species_code"].lower()}).json()
    assert j["total_matching"] >= 1 and all(p["species_code"] == it["species_code"] for p in j["points"] if p["point_ref"].startswith(it["species_code"] + "-"))
    j = client.get(f"/plans/{pid}/points", params={"q": it["species"].upper()}).json()
    assert j["points"] and all(it["species"].lower() in p["species"].lower() for p in j["points"])
    j = client.get(f"/plans/{pid}/points", params={"q": str(it["point_id"])}).json()
    assert any(p["point_id"] == it["point_id"] for p in j["points"])
    j = client.get(f"/plans/{pid}/points", params={"q": ref, "limit": 1}).json()
    assert j["count"] == 1
    p0 = j["points"][0]
    assert p0["plan_id"] == pid and p0["species"] and p0["lat"] and p0["lon"] and "barangay_display" in p0
    assert client.get(f"/plans/{pid}/points", params={"q": "zzzz-999"}).json()["points"] == []


def test_plan_points_errors_and_traversal_are_rejected(client):
    assert client.get("/plans/plan_urban_20200101_000000/points", params={"q": "duh"}).status_code == 404
    assert client.get("/plans/plan_x/points", params={"q": ""}).status_code == 422
    for bad in ("..%2F..%2Fetc%2Fpasswd", "..", "..%5Cwindows", "plan_x%2F..%2F..%2Fapi_v2", "plan%00x", "a b", "%2e%2e%2fsecret", "C%3A%5Cx"):
        r = client.get(f"/plans/{bad}/points", params={"q": "duh"})
        assert r.status_code in (400, 404, 422), (bad, r.status_code)
        assert r.status_code != 200


# ---- /search/all: limits, plans, speed ---------------------------------------------------------------------------------------
def test_all_limits_per_group_and_counts_the_real_total(client):
    plan = make_plan(client, n=60)
    full = client.get("/search/all", params={"q": "an", "limit": 20}).json()
    j = client.get("/search/all", params={"q": "an", "limit": 2}).json()
    for g in ("barangays", "species", "points", "plan_points"):
        assert len(j[g]) <= 2
    assert j["counts"]["barangays"] == full["counts"]["barangays"] >= 3
    assert len(client.get("/search/all", params={"q": plan["plan"][0]["species"][:3], "limit": 20}).json()["plan_points"]) >= 1
    assert client.get("/search/all", params={"q": "an", "limit": 21}).status_code == 422
    assert client.get("/search/all", params={"q": "a"}).status_code == 422          # two characters at least
    assert client.get("/search/all", params={"q": "an"}).json()["limit"] == api_v2.API_CFG["search_group_limit"]


def test_all_looks_only_in_the_most_recent_plans(client, data, monkeypatch):
    monkeypatch.setitem(data.cfg, "search_recent_plans", 2)
    plans = [make_plan(client, n=20, seed=s) for s in (1, 2, 3)]
    ids = api_v2.saved_plan_ids(data)
    assert len(ids) == 3 and set(ids[:2]) <= {p["plan_id"] for p in plans}
    ref = plans[0]["plan"][0]["point_ref"]
    j = client.get("/search/all", params={"q": ref, "limit": 20}).json()
    assert j["searched_plans"] == 2
    assert {p["plan_id"] for p in j["plan_points"]} <= set(ids[:2])


def test_all_is_fast_with_twenty_plans(client, data):
    base = make_plan(client, n=30)
    root = Path(data.work) / "plans"
    for k in range(19):                                                  # 20 saved plans in total (copies with different stamps)
        pid = f"plan_urban_2026100{k % 9 + 1}_0000{k:02d}"
        for suffix in (".csv", "_summary.json"):
            shutil.copy(root / f"{base['plan_id']}{suffix}", root / f"{pid}{suffix}")
    assert len(api_v2.saved_plan_ids(data)) == 20
    client.get("/search/all", params={"q": "narra"})                     # warm the per-plan index
    t0 = time.perf_counter()
    for q in ("narra", "sta", "832", "duh"):
        assert client.get("/search/all", params={"q": q}).status_code == 200
    assert (time.perf_counter() - t0) / 4 < 0.5, "a suggestion call must feel instant"


def test_all_with_no_plans_still_works(client):
    j = client.get("/search/all", params={"q": "narra"}).json()
    assert j["plan_points"] == [] and j["searched_plans"] == 0 and j["geocoder_enabled"] is False


# ---- the optional geocoder -------------------------------------------------------------------------------------------------
class FakeNet:
    def __init__(self, body=None, fail=None):
        self.calls, self.body, self.fail = [], body if body is not None else [], fail

    def __call__(self, url, headers, timeout):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if self.fail:
            raise self.fail
        return self.body


HIT = [{"name": "Mayon Street", "display_name": "Mayon Street, Santa Ana, San Mateo, Rizal, Philippines", "category": "highway", "type": "residential",
        "lat": "14.6915", "lon": "121.1130", "boundingbox": ["14.690", "14.692", "121.112", "121.114"]}]


@pytest.fixture
def geo_on(data, monkeypatch):
    monkeypatch.setitem(data.cfg, "geocoder_enabled", True)
    monkeypatch.setitem(data.cfg, "geocoder_contact", "thesis@example.org")
    net = FakeNet(HIT)
    monkeypatch.setattr(api_v2, "geocoder_http_get", net)
    clock = {"t": 1000.0}
    sleeps = []
    monkeypatch.setattr(data.geo, "clock", lambda: clock["t"])
    monkeypatch.setattr(data.geo, "sleep", lambda s: (sleeps.append(s), clock.__setitem__("t", clock["t"] + s)))
    return net, clock, sleeps


def test_geocoder_is_disabled_by_default_and_never_calls_the_network(client, monkeypatch):
    assert api_v2.API_CFG["geocoder_enabled"] is False and api_v2.API_CFG["geocoder_contact"] == ""
    net = FakeNet(HIT)
    monkeypatch.setattr(api_v2, "geocoder_http_get", net)
    r = client.get("/search/geocode", params={"q": "mayon street"})
    assert r.status_code == 503 and "disabled" in r.json()["detail"] and net.calls == []
    assert client.get("/search/all", params={"q": "mayon"}).json()["geocoder_enabled"] is False


def test_geocoder_without_a_contact_is_refused_before_any_request(client, data, monkeypatch):
    monkeypatch.setitem(data.cfg, "geocoder_enabled", True)
    net = FakeNet(HIT)
    monkeypatch.setattr(api_v2, "geocoder_http_get", net)
    for contact in ("", "   ", None):
        monkeypatch.setitem(data.cfg, "geocoder_contact", contact)
        r = client.get("/search/geocode", params={"q": "mayon street"})
        assert r.status_code == 503 and "geocoder_contact" in r.json()["detail"]
    assert net.calls == []


def test_geocoder_request_has_user_agent_philippines_and_a_san_mateo_box(client, geo_on):
    net, _, _ = geo_on
    r = client.get("/search/geocode", params={"q": "Mayon Street"})
    assert r.status_code == 200
    j = r.json()
    assert j["attribution"] == "Search data (c) OpenStreetMap contributors" and j["cached"] is False and j["network_error"] is None
    assert j["results"][0]["name"] == "Mayon Street" and j["results"][0]["lat"] == pytest.approx(14.6915) and j["results"][0]["bbox"] == [121.112, 14.69, 121.114, 14.692]
    call = net.calls[0]
    assert "thesis@example.org" in call["headers"]["User-Agent"] and api_v2.API_CFG["geocoder_app_name"] in call["headers"]["User-Agent"]
    q = dict(p.split("=") for p in call["url"].split("?")[1].split("&"))
    assert q["countrycodes"] == "ph" and q["bounded"] == "1" and q["format"] == "jsonv2"
    west, north, east, south = (float(x) for x in api_v2.urllib.parse.unquote(q["viewbox"]).split(","))
    assert 120.9 < west < 121.2 < east < 121.4 and 14.5 < south < 14.7 < north < 14.9      # a box around San Mateo, not the whole country
    assert call["url"].startswith(api_v2.API_CFG["geocoder_url"])


def test_geocoder_answers_are_cached_on_disk_and_expire_after_30_days(client, data, geo_on, monkeypatch):
    net, _, _ = geo_on
    assert client.get("/search/geocode", params={"q": "Mayon Street"}).json()["cached"] is False
    again = client.get("/search/geocode", params={"q": "  mayon   STREET "}).json()          # same search, different spelling of spaces and case
    assert again["cached"] is True and len(net.calls) == 1 and again["results"][0]["name"] == "Mayon Street"
    files = list((Path(data.work) / api_v2.API_CFG["geocoder_cache_dir"]).glob("*.json"))
    assert len(files) == 1
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    doc["fetched_at"] -= 31 * 86400                                      # older than 30 days: fetched again
    files[0].write_text(json.dumps(doc), encoding="utf-8")
    assert client.get("/search/geocode", params={"q": "Mayon Street"}).json()["cached"] is False
    assert len(net.calls) == 2


def test_geocoder_keeps_to_one_request_per_second_but_cache_hits_do_not_count(client, geo_on):
    net, clock, sleeps = geo_on
    client.get("/search/geocode", params={"q": "street one"})
    client.get("/search/geocode", params={"q": "street one"})            # cache hit: no wait, no request
    assert sleeps == [] and len(net.calls) == 1
    client.get("/search/geocode", params={"q": "street two"})           # a second real request right away must wait the full interval
    assert len(net.calls) == 2 and sleeps == [pytest.approx(1.0)]
    clock["t"] += 5
    client.get("/search/geocode", params={"q": "street three"})         # after enough time no wait is needed
    assert len(net.calls) == 3 and len(sleeps) == 1


def test_geocoder_network_failure_uses_the_old_answer_or_a_clear_error(client, data, geo_on, monkeypatch):
    net, _, _ = geo_on
    r = client.get("/search/geocode", params={"q": "no cache here"})
    assert r.status_code == 200
    f = list((Path(data.work) / api_v2.API_CFG["geocoder_cache_dir"]).glob("*.json"))[0]
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc["fetched_at"] -= 40 * 86400
    f.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(api_v2, "geocoder_http_get", FakeNet(fail=OSError("network is down")))
    stale = client.get("/search/geocode", params={"q": "no cache here"}).json()
    assert stale["stale"] is True and stale["cached"] is True and "network is down" in stale["network_error"] and stale["results"]
    r = client.get("/search/geocode", params={"q": "never searched"})
    assert r.status_code == 503 and "could not be reached" in r.json()["detail"]


def test_geocoder_bad_answers_and_short_queries(client, geo_on, monkeypatch):
    monkeypatch.setattr(api_v2, "geocoder_http_get", FakeNet({"error": "blocked"}))
    assert client.get("/search/geocode", params={"q": "something"}).status_code == 503
    monkeypatch.setattr(api_v2, "geocoder_http_get", FakeNet([{"lat": "x", "lon": "y"}, *HIT]))
    assert [h["name"] for h in client.get("/search/geocode", params={"q": "mixed answer"}).json()["results"]] == ["Mayon Street"]
    assert client.get("/search/geocode", params={"q": "ab"}).status_code == 422


# ---- the coordinate parser (JavaScript, run with node) -----------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_coordinate_parser_javascript_tests_pass():
    r = subprocess.run(["node", "--test", str(ROOT / "frontend" / "src" / "new" / "coords.test.mjs")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
