"""Tests for pipeline/score_sites.py. Run from the repo root:  python -m pytest tests/test_score_sites.py"""
import json, sqlite3, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import score_sites as ss  # noqa: E402

PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data


def species(**kw):
    base = dict(species_id=1, elev_min_m=0.0, elev_max_m=600.0, max_slope_pct=30.0, soil_textures="Clay Loam;Clay",
                soil_any_texture=False, waterlog_tol="High")
    base.update(kw)
    return pd.DataFrame([base])


def site(**kw):
    base = dict(point_id=1, elev_m=200.0, slope_pct=5.0, soil_texture_legacy="Clay Loam", is_legal_zone=1, water_dist_m=500.0)
    base.update(kw)
    return pd.DataFrame([base])


def score(sp=None, st=None, **kw):
    return ss.score_pairs(sp if sp is not None else species(), st if st is not None else site(), **kw).iloc[0]


def test_baseline_fully_suitable_site_scores_one():
    r = score()
    assert r.s_rule == pytest.approx(1.0) and r.confidence == pytest.approx(1.0)


# ---- acceptance criterion: outside the elevation range -> S = 0
@pytest.mark.parametrize("elev", [601.0, 1000.0])
def test_species_above_its_elevation_range_gets_zero(elev):
    r = score(st=site(elev_m=elev))
    assert r.s_rule == 0.0 and r.gate_fail_elevation


def test_species_below_its_elevation_range_gets_zero():
    r = score(sp=species(elev_min_m=300.0, elev_max_m=800.0), st=site(elev_m=299.0))
    assert r.s_rule == 0.0 and r.gate_fail_elevation


def test_elevation_on_the_limit_passes_the_gate_but_is_penalised():
    r = score(st=site(elev_m=600.0))
    assert not r.gate_fail_elevation and r.f_elevation == 0.0 and 0 < r.s_rule < 1


def test_lower_limit_of_zero_metres_has_no_falloff():
    assert score(st=site(elev_m=6.0)).f_elevation == 1.0


def test_elevation_falloff_uses_the_margin_setting():
    # range 0..600, margin 10% = 60 m: 30 m below the max -> 0.5 ; with a 20% margin (120 m) -> 0.25
    assert score(st=site(elev_m=570.0)).f_elevation == pytest.approx(0.5)
    assert score(st=site(elev_m=570.0), margin_fraction=0.20).f_elevation == pytest.approx(0.25)
    assert ss.MARGIN_FRACTION == 0.10


def test_lower_edge_falloff_when_min_above_zero():
    r = score(sp=species(elev_min_m=300.0, elev_max_m=800.0), st=site(elev_m=325.0))   # margin 50 m
    assert r.f_elevation == pytest.approx(0.5)


# ---- other gates
def test_slope_above_max_gets_zero_and_inside_margin_is_penalised():
    assert score(st=site(slope_pct=31.0)).s_rule == 0.0
    assert score(st=site(slope_pct=28.5)).f_slope == pytest.approx(0.5)      # margin 3 %, 1.5 below max
    assert score(st=site(slope_pct=10.0)).f_slope == 1.0


def test_illegal_zone_gets_zero():
    r = score(st=site(is_legal_zone=0))
    assert r.s_rule == 0.0 and r.gate_fail_legal_zone


def test_default_soil_gate_mode_is_soft():
    assert ss.SOIL_GATE_MODE == "soft" and ss.SOIL_MISMATCH_FACTOR == 0.25


def test_hard_mode_soil_mismatch_gets_zero_match_passes():
    r = score(st=site(soil_texture_legacy="Loam"), soil_gate_mode="hard")
    assert r.s_rule == 0.0 and r.gate_fail_soil and not r.soil_unverified_mismatch
    assert score(st=site(soil_texture_legacy="clay loam"), soil_gate_mode="hard").s_rule == pytest.approx(1.0)


def test_soft_mode_soil_mismatch_is_penalised_flagged_and_less_confident_not_zeroed():
    r = score(st=site(soil_texture_legacy="Loam"), soil_gate_mode="soft")
    assert r.s_rule == pytest.approx((0.25 * 3 + 0.25 * ss.SOIL_MISMATCH_FACTOR) / 1.0)      # 3 perfect terms + soil 0.25
    assert r.f_soil == ss.SOIL_MISMATCH_FACTOR and r.soil_unverified_mismatch and not r.gate_fail_soil
    assert r.confidence == pytest.approx(0.75)                                              # soil term not counted as evaluated
    assert score(st=site(soil_texture_legacy="Clay Loam"), soil_gate_mode="soft").confidence == pytest.approx(1.0)


def test_soft_mode_still_applies_the_other_gates_and_uses_the_config_default():
    assert score(st=site(soil_texture_legacy="Loam", elev_m=700.0), soil_gate_mode="soft").s_rule == 0.0
    assert score(st=site(soil_texture_legacy="Loam")).soil_unverified_mismatch          # no argument -> SOIL_GATE_MODE (soft)


def test_unknown_soil_gate_mode_is_rejected():
    with pytest.raises(ValueError):
        score(soil_gate_mode="medium")


def test_soil_any_texture_passes_any_site():
    r = score(sp=species(soil_textures=np.nan, soil_any_texture=True), st=site(soil_texture_legacy="Loam"))
    assert r.s_rule == pytest.approx(1.0) and r.known_soil


def test_unknown_site_texture_is_not_excluded_but_lowers_confidence():
    r = score(st=site(soil_texture_legacy=np.nan))
    assert r.s_rule == pytest.approx(1.0) and not r.known_soil and not r.gate_fail_soil
    assert r.confidence == pytest.approx(0.75)


def test_species_without_texture_list_is_unknown_not_excluded():
    r = score(sp=species(soil_textures=np.nan, soil_any_texture=False))
    assert r.s_rule > 0 and not r.known_soil and r.confidence == pytest.approx(0.75)


def test_missing_slope_is_unknown_not_excluded():
    r = score(st=site(slope_pct=np.nan))
    assert r.s_rule > 0 and not r.known_slope and r.confidence == pytest.approx(0.75)


# ---- wetness
def test_wetness_depends_on_tolerance_and_distance_to_water():
    near = site(water_dist_m=0.0)
    assert score(sp=species(waterlog_tol="Low"), st=near).f_wetness == 0.0
    assert score(sp=species(waterlog_tol="Medium"), st=near).f_wetness == 0.5
    assert score(sp=species(waterlog_tol="High"), st=near).f_wetness == 1.0
    half = site(water_dist_m=ss.WETNESS_RISK_DISTANCE_M / 2)
    assert score(sp=species(waterlog_tol="Low"), st=half).f_wetness == pytest.approx(0.5)
    assert score(sp=species(waterlog_tol="Low"), st=site(water_dist_m=ss.WETNESS_RISK_DISTANCE_M * 3)).f_wetness == 1.0


def test_unknown_water_distance_is_not_scored():
    r = score(st=site(water_dist_m=np.nan))
    assert not r.known_wetness and r.confidence == pytest.approx(0.75)


def test_s_is_always_within_unit_interval_and_s_prob_is_null():
    rng = np.random.default_rng(0)
    st = pd.DataFrame(dict(point_id=range(200), elev_m=rng.uniform(0, 900, 200), slope_pct=rng.uniform(0, 60, 200),
                           soil_texture_legacy=rng.choice(["Clay", "Clay Loam", None], 200), is_legal_zone=1,
                           water_dist_m=rng.uniform(0, 300, 200)))
    r = ss.score_pairs(species(), st)
    assert r.s_rule.between(0, 1).all() and r.confidence.between(0, 1).all() and r.s_prob.isna().all()


# ---- breakdown carries sources
def test_breakdown_lists_terms_weights_values_and_source_ids():
    sp, st = species(), site(soil_texture_legacy=np.nan)
    sc = ss.score_pairs(sp, st)
    fields = ("elev_min_m", "elev_max_m", "max_slope_pct", "soil_raw", "waterlog_tol")
    src = pd.DataFrame([dict(source_id=100 + i, species_id=1, field_name=f, source_url=f"https://example.org/{f}", source_rank=2.0)
                        for i, f in enumerate(fields)])
    b = json.loads(ss.build_breakdown(sc, sp, st, ss.source_lookup(src))[0])
    assert set(b["terms"]) == {"elevation", "slope", "soil", "wetness"} and b["gate_failed"] == []
    assert all(t["weight"] == 0.25 for t in b["terms"].values())
    assert b["terms"]["elevation"]["src"] == [100, 101] and b["terms"]["soil"]["src"] == [103]
    assert b["terms"]["soil"]["value"] is None                       # unknown texture: not scored
    assert b["terms"]["wetness"]["value"] == 1.0


def test_hard_mode_failed_soil_gate_shows_zero_in_breakdown_and_is_listed():
    sp, st = species(), site(soil_texture_legacy="Loam")
    b = json.loads(ss.build_breakdown(ss.score_pairs(sp, st, soil_gate_mode="hard"), sp, st, {})[0])
    assert b["gate_failed"] == ["soil"] and b["flags"] == [] and b["terms"]["soil"]["value"] == 0.0


def test_soft_mode_breakdown_carries_the_soil_unverified_mismatch_flag():
    sp, st = species(), site(soil_texture_legacy="Loam")
    b = json.loads(ss.build_breakdown(ss.score_pairs(sp, st, soil_gate_mode="soft"), sp, st, {})[0])
    assert b["gate_failed"] == [] and b["flags"] == ["soil_unverified_mismatch"] and b["terms"]["soil"]["value"] == 0.25
    ok = json.loads(ss.build_breakdown(ss.score_pairs(sp, site(), soil_gate_mode="soft"), sp, site(), {})[0])
    assert ok["flags"] == []


# ---- real Day 1 data (skipped if the outputs are not there)
needs_data = pytest.mark.skipif(not (PROCESSED / "site_points_clean.csv").exists(), reason="Day 1 outputs not generated")


@needs_data
def test_real_data_covers_all_legal_points_times_45_species():
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    st = pd.read_csv(PROCESSED / "site_points_clean.csv")
    st = st[st.is_legal_zone.astype(bool)].assign(water_dist_m=np.nan)
    r = ss.score_pairs(sp, st)
    assert len(sp) == 45 and len(r) == len(st) * 45
    assert not r.duplicated(["point_id", "species_id"]).any()
    assert r.s_rule.between(0, 1).all()
    # every pair whose site elevation lies outside the species range is 0
    m = r.merge(st[["point_id", "elev_m"]], on="point_id").merge(sp[["species_id", "elev_min_m", "elev_max_m"]], on="species_id")
    out = (m.elev_m < m.elev_min_m) | (m.elev_m > m.elev_max_m)
    assert (m.loc[out, "s_rule"] == 0).all()


@needs_data
def test_run_writes_csv_and_db_table(tmp_path):
    for f in ("species_clean.csv", "species_sources.csv"):
        (tmp_path / f).write_bytes((PROCESSED / f).read_bytes())
    st = pd.read_csv(PROCESSED / "site_points_clean.csv")
    st = st[st.is_legal_zone.astype(bool)].head(40)
    st.to_csv(tmp_path / "site_points_clean.csv", index=False)
    ss.run(tmp_path, str(ROOT / "data" / "SMR_WATERBODIES_POLY.shp"))
    assert not (tmp_path / "site_scores.csv").exists() and not (tmp_path / "optimizing_survival.db").exists()
    out = pd.read_csv(tmp_path / "scores" / "site_scores.csv")
    assert len(out) == 40 * 45 and list(out.columns) == ["point_id", "species_id", "s_rule", "s_prob", "breakdown_json", "confidence"]
    con = sqlite3.connect(tmp_path / "scores" / "site_scores.db")
    assert con.execute("select count(*) from site_scores").fetchone()[0] == 40 * 45
    con.close()
    b = json.loads(out.breakdown_json.iloc[0])
    ids = {i for t in b["terms"].values() for i in t["src"]}
    known = set(pd.read_csv(PROCESSED / "species_sources.csv").source_id)
    assert ids and ids <= known                                      # every cited id resolves in species_sources
