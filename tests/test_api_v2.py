"""Tests for api_v2.py (FastAPI TestClient, real data). Run from the repo root:  python -m pytest tests/test_api_v2.py"""
import copy, sys, time
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
needs_data = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
pytestmark = needs_data

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:                    # runs the startup (data loaded once)
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


def box(minlon, minlat, maxlon, maxlat):
    return {"type": "Polygon", "coordinates": [[[minlon, minlat], [maxlon, minlat], [maxlon, maxlat], [minlon, maxlat], [minlon, minlat]]]}


def zone_box(data, zone, pad=0.0005):
    s = data.ctx.sites[data.ctx.sites.zone_desc == zone]
    return box(s.lon.min() - pad, s.lat.min() - pad, s.lon.max() + pad, s.lat.max() + pad)


def a_legal_point(data, zone="Forest Zone", k=100):
    r = data.ctx.sites[data.ctx.sites.zone_desc == zone].iloc[k]
    return float(r.lat), float(r.lon), int(r.point_id)


# ---- startup / CORS / health ------------------------------------------------------------------------------------------
def test_data_is_loaded_once_and_kept_between_requests(client, data):
    client.get("/health"); client.get("/species")
    assert client.app.state.data is data


def test_health_reports_version_hash_counts_and_limits(client):
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok" and j["dataset_version"] == "v0.1-draft" and len(j["dataset_file_hash"]) == 64
    assert j["counts"]["species"] == 45 and j["counts"]["legal_points"] == 6251 and j["counts"]["grid_points"] == 8088
    assert j["counts"]["species_point_scores"] == 6251 * 45
    text = " ".join(j["limits"]).lower()
    for k in ("ph", "100 m", "unverified", "provisional"):
        assert k in text


def test_cors_allows_only_the_two_vite_origins(client):
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        r = client.get("/health", headers={"Origin": origin})
        assert r.headers["access-control-allow-origin"] == origin
    r = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    pre = client.options("/plan-event", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                                  "Access-Control-Request-Headers": "content-type"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == "http://localhost:5173"
    bad = client.options("/plan-event", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers
    assert api_v2.API_CFG["port"] == 8001


# ---- species ---------------------------------------------------------------------------------------------------------
def test_species_list_has_key_fields_confidence_and_resolved_sources(client):
    j = client.get("/species").json()
    assert j["count"] == 45 and len(j["species"]) == 45
    s = j["species"][0]
    assert {"species_id", "common_name", "scientific_name", "elev_min_m", "elev_max_m", "max_slope_pct", "planting_months", "confidence",
            "purpose_scores", "source_ids"} <= set(s)
    assert set(s["purpose_scores"]) == {"urban", "planting", "watershed"} and "cells_cited" in s["confidence"]
    for sid in s["source_ids"].values():
        src = j["sources"][str(sid)]
        assert src["url"] and src["rank"] is not None and src["source_id"] == sid


def test_species_detail_lists_every_field_with_url_and_rank(client, data):
    j = client.get("/species/1").json()
    assert j["common_name"] == "Narra" and set(j["purpose_scores"]) == {"urban", "planting", "watershed"}
    n_rows = int((data.sources.species_id == 1).sum())
    assert len(j["fields"]) == n_rows >= 40
    assert all(f["source_id"] and "source_url" in f and "source_rank" in f and f["field_name"] for f in j["fields"])
    assert all(f["source_url"] for f in j["fields"] if f["field_name"] == "elev_max_m")
    ub = j["purpose_scores"]["urban"]
    assert ub["weights_status"] == "provisional" and ub["criteria"]["shade_provision"]["sources"][0]["url"]
    assert j["reference_urls"] and "clean_values" in j
    nf = client.get("/species/10").json()
    assert "species_data_unverified" in nf["flags"]                     # Batikuling cites a file that was not provided


def test_unknown_species_gives_404_with_a_message(client):
    r = client.get("/species/999")
    assert r.status_code == 404 and "not found" in r.json()["detail"]
    assert client.get("/species/abc").status_code == 422


# ---- /rank -----------------------------------------------------------------------------------------------------------
def test_rank_returns_ranked_species_with_breakdown_and_resolved_sources(client, data):
    lat, lon, pid = a_legal_point(data)
    r = client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon})
    assert r.status_code == 200
    j = r.json()
    assert j["point"]["point_id"] == pid and j["point"]["distance_m"] < 1.0 and j["returned"] == 10 and j["species_total"] == 45
    ranking = j["ranking"]
    ws = [x["W"] for x in ranking if x["eligible"]]
    assert ws == sorted(ws, reverse=True) and [x["rank"] for x in ranking] == list(range(1, 11))
    top = ranking[0]
    assert top["eligible"] and top["W"] == pytest.approx(top["S"] * top["P"], abs=1e-3) and top["S"] >= 0.5
    assert {"confidence", "flags"} <= set(top) and isinstance(top["flags"], list)
    terms = top["site_breakdown"]["terms"]
    assert set(terms) == {"elevation", "slope", "soil", "wetness"}
    assert all(t["sources"] and all(s["url"] and s["rank"] is not None for s in t["sources"]) for t in terms.values())
    assert top["purpose_breakdown"]["criteria"] and top["purpose_breakdown"]["weights_status"] == "provisional"
    assert "W = S x P" in j["w_definition"] and j["limits"]


def test_rank_limit_and_purposes(client, data):
    lat, lon, _ = a_legal_point(data, "Agricultural Zone", 5)
    full = client.get("/rank", params={"purpose": "watershed", "lat": lat, "lon": lon, "limit": 45}).json()
    assert full["returned"] == 45
    elig = [x["eligible"] for x in full["ranking"]]
    assert elig == sorted(elig, reverse=True)                            # eligible species first
    assert client.get("/rank", params={"purpose": "planting", "lat": lat, "lon": lon, "limit": 3}).json()["returned"] == 3


def test_rank_404_when_the_nearest_point_is_too_far(client):
    r = client.get("/rank", params={"purpose": "urban", "lat": 15.5, "lon": 121.5})
    assert r.status_code == 404 and "150 m" in r.json()["detail"] and "outside the mapped area" in r.json()["detail"]


def test_rank_404_when_the_nearest_point_is_not_in_a_legal_zone(client, data):
    p = data.all_points[~data.all_points.is_legal_zone.astype(bool)].iloc[0]
    r = client.get("/rank", params={"purpose": "urban", "lat": float(p.lat), "lon": float(p.lon)})
    assert r.status_code == 404 and "not in a legal planting zone" in r.json()["detail"]


def test_rank_validation_errors(client):
    assert client.get("/rank", params={"purpose": "fruit", "lat": 14.7, "lon": 121.1}).status_code == 422
    assert client.get("/rank", params={"purpose": "urban", "lat": 95, "lon": 121.1}).status_code == 422
    assert client.get("/rank", params={"purpose": "urban"}).status_code == 422


# ---- /rank/municipal -------------------------------------------------------------------------------------------------
def test_municipal_rank_is_small_sorted_and_sourced(client):
    r = client.get("/rank/municipal", params={"purpose": "urban"})
    assert r.status_code == 200 and len(r.content) < 120_000
    j = r.json()
    scores = [x["species_score"] for x in j["ranking"]]
    assert j["returned"] == 15 and scores == sorted(scores, reverse=True) and j["legal_points"] == 6251
    x = j["ranking"][0]
    assert {"mean_W_where_eligible", "share_of_points_eligible", "P", "p_confidence", "mean_site_confidence", "source_ids"} <= set(x)
    assert 0 < x["share_of_points_eligible"] <= 1 and x["species_score"] == pytest.approx(x["mean_W_where_eligible"] * x["share_of_points_eligible"], abs=2e-3)
    for sid in x["source_ids"]["site_score"] + x["source_ids"]["purpose_score"]:
        assert j["sources"][str(sid)]["url"] and "rank" in j["sources"][str(sid)]
    assert client.get("/rank/municipal", params={"purpose": "planting", "limit": 45}).json()["returned"] == 45
    assert client.get("/rank/municipal", params={"purpose": "nope"}).status_code == 422


# ---- /search ---------------------------------------------------------------------------------------------------------
def test_species_search_is_case_insensitive_on_common_and_scientific_names(client):
    a = client.get("/search/species", params={"q": "narra"}).json()
    b = client.get("/search/species", params={"q": "NARRA"}).json()
    assert a["count"] == b["count"] >= 1 and a["results"][0]["common_name"] == "Narra" and "common_name" in a["results"][0]["matched_on"]
    assert a["results"][0]["source_ids"] and all(a["sources"][str(i)]["url"] for i in a["results"][0]["source_ids"])
    sci = client.get("/search/species", params={"q": "pterocarpus"}).json()
    assert any("scientific_name" in r["matched_on"] and r["species_id"] == 1 for r in sci["results"])
    assert client.get("/search/species", params={"q": "zzzzqq"}).json()["count"] == 0
    assert client.get("/search/species").status_code == 422


def test_place_search_aliases_accents_and_geometry(client):
    for q, name in (("Sta Ana", "STA ANA"), ("Santa Ana", "STA ANA"), ("sta. ana", "STA ANA"), ("Sto Nino", "STO NINO"), ("Santo Niño", "STO NINO"),
                    ("SANTO NIÑO", "STO NINO")):
        j = client.get("/search/place", params={"q": q}).json()
        assert [r["name"] for r in j["results"]] == [name], q
    r = client.get("/search/place", params={"q": "guitnang"}).json()
    assert r["count"] == 2
    for x in r["results"]:
        lo, la, hi, ha = x["bounds"]
        assert lo <= x["centroid"]["lon"] <= hi and la <= x["centroid"]["lat"] <= ha and x["source"].startswith("data/BRGY_BOUNDARY.shp")
    assert client.get("/search/place", params={"q": "atlantis"}).json()["count"] == 0
    assert client.get("/search/place", params={"q": "santa"}).json()["count"] == 1


# ---- /nearest-viable -------------------------------------------------------------------------------------------------
def test_nearest_viable_returns_the_spot_itself_when_it_is_viable(client, data):
    lat, lon, pid = a_legal_point(data)
    j = client.get("/nearest-viable", params={"purpose": "urban", "lat": lat, "lon": lon}).json()
    assert j["already_viable"] and j["point"]["point_id"] == pid and j["distance_m"] < 1 and j["direction"] is None
    b = j["best_species"]
    assert b["S"] >= 0.5 and b["W"] == pytest.approx(b["S"] * b["P"], abs=1e-3) and j["sources"]


def eligible_none_around(data, monkeypatch, pid, radius_m):
    ctx = data.ctx
    r = ctx.sites[ctx.sites.point_id == pid].iloc[0]
    near = np.hypot(ctx.sites.utm_e - r.utm_e, ctx.sites.utm_n - r.utm_n).to_numpy() <= radius_m
    S2 = ctx.S.copy(); S2[near] = 0.0
    monkeypatch.setattr(ctx, "S", S2)
    return r, near


def test_nearest_viable_scans_rings_with_direction_and_distance(client, data, monkeypatch):
    lat, lon, pid = a_legal_point(data, "Forest Zone", 300)
    r, near = eligible_none_around(data, monkeypatch, pid, 450.0)
    j = client.get("/nearest-viable", params={"purpose": "planting", "lat": lat, "lon": lon}).json()
    assert not j["already_viable"] and j["direction"] in api_v2.COMPASS
    assert 450 < j["distance_m"] <= 450 + 3 * api_v2.API_CFG["ring_step_m"] and j["search_ring"] == int(np.ceil(j["distance_m"] / 100.0))
    assert j["best_species"]["S"] >= 0.5 and j["point"]["point_id"] != pid
    # nothing closer is viable: every legal point nearer than the answer was zeroed
    e, n = r.utm_e, r.utm_n
    sites = data.ctx.sites
    d = np.hypot(sites.utm_e - e, sites.utm_n - n).to_numpy()
    viable = (data.ctx.S >= 0.5).any(axis=1)
    assert d[viable].min() == pytest.approx(j["distance_m"], abs=0.2)
    # the ring step is a config value
    monkeypatch.setitem(api_v2.API_CFG, "ring_step_m", 500.0)
    j2 = client.get("/nearest-viable", params={"purpose": "planting", "lat": lat, "lon": lon}).json()
    assert j2["ring_step_m"] == 500.0 and j2["search_ring"] == int(np.ceil(j2["distance_m"] / 500.0)) and j2["distance_m"] == j["distance_m"]


def test_nearest_viable_404_when_nothing_is_viable_within_the_limit(client, data, monkeypatch):
    monkeypatch.setattr(data.ctx, "S", np.zeros_like(data.ctx.S))
    monkeypatch.setitem(api_v2.API_CFG, "ring_max_m", 300.0)
    lat, lon, _ = a_legal_point(data)
    r = client.get("/nearest-viable", params={"purpose": "urban", "lat": lat, "lon": lon})
    assert r.status_code == 404 and "300 m" in r.json()["detail"]
    assert client.get("/nearest-viable", params={"purpose": "bad", "lat": lat, "lon": lon}).status_code == 422


# ---- POST /plan-event ------------------------------------------------------------------------------------------------
def test_plan_event_300_saplings_finishes_in_under_ten_seconds(client):
    t0 = time.perf_counter()
    r = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 300})
    dt = time.perf_counter() - t0
    assert r.status_code == 200 and dt < 10.0, f"{dt:.1f}s"
    j = r.json()
    assert len(j["plan"]) == 300 and j["unmatched"]["saplings_unmatched"] == 0 and 6 <= len(j["palette"]) <= 10
    assert abs(sum(p["share"] for p in j["palette"]) - 1.0) < 1e-6


def test_plan_event_response_content_and_sources(client):
    j = client.post("/plan-event", json={"purpose": "watershed", "n_saplings": 60, "seed": 3}).json()
    it = j["plan"][0]
    assert {"point_id", "lon", "lat", "utm_e", "utm_n", "species", "S", "P", "W", "flags", "site_scores_source_ids"} <= set(it)
    assert all(i["S"] >= 0.5 for i in j["plan"]) and len({i["point_id"] for i in j["plan"]}) == len(j["plan"])
    assert all(i["W"] == pytest.approx(i["S"] * i["P"], abs=1e-3) for i in j["plan"])
    assert j["seed"] == 3 and {"saplings_unmatched", "saplings_unallocated_by_caps", "unused_candidate_points"} <= set(j["unmatched"])
    for i in j["plan"]:
        for sid in i["site_scores_source_ids"]:
            assert j["sources"][str(sid)]["url"]
    for p in j["palette"]:
        assert {"species", "share", "quota", "placed", "unmatched", "purpose_score_source_ids", "needs_both_sexes"} <= set(p)
        assert all(j["sources"][str(s)]["url"] for s in p["purpose_score_source_ids"])
    assert any("one tree per cell" in x for x in j["limits"]) and any("pH" in x for x in j["limits"]) and any("provisional" in x.lower() for x in j["limits"])
    assert "Each point is a ~100 m grid cell" in " ".join(j["limits"])


def test_plan_event_same_seed_same_plan(client):
    body = {"purpose": "planting", "n_saplings": 80, "seed": 11}
    assert client.post("/plan-event", json=body).json()["plan"] == client.post("/plan-event", json=body).json()["plan"]


def test_plan_event_polygon_and_zone_filters(client, data):
    poly = zone_box(data, "Agricultural Zone")
    j = client.post("/plan-event", json={"purpose": "planting", "n_saplings": 40, "polygon": poly}).json()
    import shapely
    from shapely.geometry import shape
    g = shape(poly)
    assert j["plan"] and shapely.contains_xy(g, [i["lon"] for i in j["plan"]], [i["lat"] for i in j["plan"]]).all()
    feat = client.post("/plan-event", json={"purpose": "planting", "n_saplings": 20, "polygon": {"type": "Feature", "properties": {}, "geometry": poly}})
    assert feat.status_code == 200
    z = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 30, "zone": "agricultural zone", "polygon": poly}).json()
    assert {i["zone"] for i in z["plan"]} == {"Agricultural Zone"}


def test_plan_event_shortage_is_reported(client):
    j = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 500, "zone": "Cemetery Zone"}).json()
    placed = len(j["plan"])
    assert placed <= 23
    assert j["unmatched"]["saplings_unmatched"] + j["unmatched"]["saplings_unallocated_by_caps"] == 500 - placed > 0


def test_plan_event_error_messages(client, data, monkeypatch):
    ok = {"purpose": "urban", "n_saplings": 10}
    r = client.post("/plan-event", json={**ok, "purpose": "fruit"})
    assert r.status_code == 422 and "purpose" in str(r.json()["detail"])
    assert client.post("/plan-event", json={**ok, "n_saplings": 0}).status_code == 422
    assert client.post("/plan-event", json={**ok, "n_saplings": 2001}).status_code == 422
    assert client.post("/plan-event", json={"purpose": "urban"}).status_code == 422
    r = client.post("/plan-event", json={**ok, "zone": "Moon Base"})
    assert r.status_code == 400 and "Unknown zone" in r.json()["detail"] and "Forest Zone" in r.json()["detail"]
    bowtie = {"type": "Polygon", "coordinates": [[[121.1, 14.6], [121.2, 14.7], [121.2, 14.6], [121.1, 14.7], [121.1, 14.6]]]}
    for bad in (bowtie, {"type": "Point", "coordinates": [121.1, 14.6]}, {"type": "Polygon", "coordinates": []}, {"foo": 1}):
        r = client.post("/plan-event", json={**ok, "polygon": bad})
        assert r.status_code == 422 and "polygon" in r.json()["detail"], bad
    r = client.post("/plan-event", json={**ok, "polygon": box(120.0, 10.0, 120.1, 10.1)})                  # valid, but empty area
    assert r.status_code == 400 and "no legal-zone grid points" in r.json()["detail"]
    r = client.post("/plan-event", json={**ok, "zone": "Cemetery Zone", "polygon": zone_box(data, "Agricultural Zone", pad=0.0)})
    assert r.status_code == 400 or r.status_code == 200                                                    # zone may or may not overlap the box
    monkeypatch.setattr(data.ctx, "S", np.zeros_like(data.ctx.S))                                          # an area with no eligible points
    r = client.post("/plan-event", json=ok)
    assert r.status_code == 400 and "No species has eligible points" in r.json()["detail"]


def test_plan_event_zone_outside_the_polygon_is_a_400(client, data):
    tiny = zone_box(data, "Agricultural Zone", pad=0.0)
    r = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 10, "zone": "Cemetery Zone", "polygon": tiny})
    s = data.ctx.sites
    inside = ((s.zone_desc == "Cemetery Zone") & s.lon.between(tiny["coordinates"][0][0][0], tiny["coordinates"][0][1][0]) &
              s.lat.between(tiny["coordinates"][0][0][1], tiny["coordinates"][0][2][1])).any()
    assert (r.status_code == 200) if inside else (r.status_code == 400 and "polygon" in r.json()["detail"])


# ---- the old api.py is not touched ----------------------------------------------------------------------------------
def test_old_api_is_not_imported_by_the_new_one():
    assert "api" not in sys.modules or sys.modules["api"] is not api_v2
    assert "import api\n" not in (ROOT / "api_v2.py").read_text() and "from api " not in (ROOT / "api_v2.py").read_text()
