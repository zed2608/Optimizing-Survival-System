"""Tests for pipeline/score_purposes.py. Run from the repo root:  python -m pytest tests/test_score_purposes.py"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import score_purposes as sp_mod  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
WEIGHTS = ROOT / "data" / "config" / "purpose_weights.csv"
TAGS = {"parks": "urban", "agroforestry": "planting", "watershed": "watershed"}


def species(**cols):
    """Three species A, B, C; cols maps column -> list of 3 values."""
    df = pd.DataFrame({"species_id": [1, 2, 3], "common_name": list("ABC")})
    for k, v in cols.items():
        df[k] = v
    return df


def comp(df, col, purpose="urban"):
    return sp_mod.component_scores(df, col, purpose, TAGS).tolist()


# ---- component rules
def test_ordinal_levels_low_medium_high_are_0_half_1():
    assert comp(species(drought_tol=["Low", "Medium", "High"]), "drought_tol") == [0.0, 0.5, 1.0]


def test_growth_rate_levels_and_missing_is_nan_not_a_guess():
    r = comp(species(growth_rate=["Slow", None, "Fast"]), "growth_rate")
    assert r[0] == 0.0 and r[2] == 1.0 and np.isnan(r[1])


def test_minmax_runs_across_species_and_inverts_when_lower_is_better():
    df = species(canopy_spread_m=[4.0, 14.0, 24.0], mature_height_m=[4.0, 14.0, 24.0])
    assert comp(df, "canopy_spread_m") == [0.0, 0.5, 1.0]            # higher is better
    assert comp(df, "mature_height_m") == [1.0, 0.5, 0.0]            # lower is better (infrastructure safety)


def test_minmax_derived_midpoint_requires_both_ends():
    df = species(timber_density_min=[0.2, 0.4, np.nan], timber_density_max=[0.4, 0.6, 0.9])
    r = comp(df, "timber_density")
    assert r[0] == 0.0 and r[1] == 1.0 and np.isnan(r[2])


def test_flag_and_unit_scores():
    assert comp(species(n_fixing=[True, False, True]), "n_fixing") == [1.0, 0.0, 1.0]
    r = comp(species(root_soil_binding_prov=[0.6, 0.9, np.nan]), "root_soil_binding_prov")
    assert r[:2] == [0.6, 0.9] and np.isnan(r[2])


def test_tag_present_is_1_absent_is_0_depending_on_the_purpose():
    df = species(urban_tags=["Parks;Agroforestry", "Agroforestry", "Watershed"])
    assert comp(df, "urban_tags", "urban") == [1.0, 0.0, 0.0]
    assert comp(df, "urban_tags", "planting") == [1.0, 1.0, 0.0]
    assert comp(df, "urban_tags", "watershed") == [0.0, 0.0, 1.0]


def test_text_rules_read_known_phrases_and_leave_the_rest_as_missing():
    r = comp(species(planting_difficulty=["Low infrastructure risk", "High infrastructure damage risk", "Poor drainage is lethal"]),
             "planting_difficulty")
    assert r[0] == 1.0 and r[1] == 0.0 and np.isnan(r[2])
    assert comp(species(propagation_method=["Seeds, Grafting", "Grafting, Marcotting", "Suckers, Tissue Culture"]), "propagation_method") == [1.0, 0.0, 1.0]
    assert comp(species(native_habitat=["Forest edges, river banks", "Primary forests", None]), "native_habitat")[:2] == [1.0, 0.0]


def test_blank_problem_or_care_tags_are_unknown_not_zero_problems():
    r = comp(species(problem_tags=["pest;disease", None, "pest"]), "problem_tags")
    assert r[0] == pytest.approx(1 / 3) and np.isnan(r[1]) and r[2] == pytest.approx(2 / 3)


def test_threat_takes_the_most_threatened_status_given():
    df = species(endangered_unspecified=["Least Concern", None, "Critically Endangered"],
                 endangered_denr=[None, "Endangered", None], endangered_iucn=[None, "Vulnerable", None])
    r = comp(df, "endangered")
    assert r[0] == 0.0 and r[1] == pytest.approx(2 / 3) and r[2] == 1.0
    assert np.isnan(comp(species(endangered_unspecified=[None] * 3, endangered_denr=[None] * 3, endangered_iucn=[None] * 3), "endangered")[0])


# ---- criterion / purpose scoring on a tiny hand-checkable config
TINY = pd.DataFrame([("urban", "shade", "canopy_spread_m;growth_rate", 0.6), ("urban", "storm", "typhoon_res", 0.4)],
                    columns=["purpose", "criterion", "species_columns", "weight_provisional"])


def tiny_species(growth):
    return species(canopy_spread_m=[4.0, 14.0, 24.0], growth_rate=growth, typhoon_res=["High", "Medium", "Low"])


def test_p_is_the_weighted_sum_of_criterion_means_by_hand():
    scores, _ = sp_mod.score_species(tiny_species(["Fast", "Medium", "Slow"]), TINY, TAGS)
    p = sp_mod.aggregate(scores).set_index("species_id")
    # A: shade mean(0,1)=0.5 ; storm 1.0  -> 0.6*0.5 + 0.4*1 = 0.7
    assert p.p_score[1] == pytest.approx(0.7)
    # B: shade mean(0.5,0.5)=0.5 ; storm 0.5 -> 0.5 ;  C: shade mean(1,0)=0.5 ; storm 0 -> 0.3
    assert p.p_score[2] == pytest.approx(0.5) and p.p_score[3] == pytest.approx(0.3)
    assert list(p["rank"]) == [1, 2, 3] and (p.confidence == 1.0).all()


def test_missing_component_scores_half_and_lowers_confidence():
    scores, parts = sp_mod.score_species(tiny_species([None, "Medium", "Slow"]), TINY, TAGS)
    p = sp_mod.aggregate(scores).set_index("species_id")
    assert parts[(1, "urban", "shade")] == {"canopy_spread_m": 0.0, "growth_rate": None}      # shown as missing, never invented
    assert p.p_score[1] == pytest.approx(0.6 * np.mean([0.0, 0.5]) + 0.4 * 1.0)               # missing part = 0.5
    assert p.confidence[1] == pytest.approx(1 - 0.6 * 0.5)                                    # half of the 'shade' weight is unknown
    assert p.confidence[2] == 1.0 and p.n_missing[1] == 1


def test_unscorable_column_in_weights_file_is_rejected(tmp_path):
    bad = TINY.copy(); bad.loc[0, "species_columns"] = "pH_level"
    f = tmp_path / "w.csv"; bad.to_csv(f, index=False)
    with pytest.raises(ValueError, match="no scoring rule"):
        sp_mod.load_weights(f)


def test_weights_that_do_not_sum_to_one_are_rejected(tmp_path):
    bad = TINY.copy(); bad.loc[0, "weight_provisional"] = 0.7
    f = tmp_path / "w.csv"; bad.to_csv(f, index=False)
    with pytest.raises(ValueError, match="sum"):
        sp_mod.load_weights(f)


def test_real_weights_file_sums_to_one_per_purpose_and_every_column_has_a_rule():
    w = sp_mod.load_weights(WEIGHTS)
    assert set(w.purpose) == {"urban", "planting", "watershed"}
    assert w.groupby("purpose").weight_provisional.sum().round(9).eq(1.0).all()


# ---- sensitivity
def test_sensitivity_rank_flips_when_a_weight_moves_25_percent():
    # A is better on 'x', B on 'y'. Weights 0.52 / 0.48 -> A first; x -25% (0.39) vs y 0.48 -> B first.
    scores = pd.DataFrame([(1, "urban", "x", 0.52, 1.0, 1, 0), (2, "urban", "x", 0.52, 0.0, 1, 0),
                           (1, "urban", "y", 0.48, 0.0, 1, 0), (2, "urban", "y", 0.48, 1.0, 1, 0)],
                          columns=["species_id", "purpose", "criterion", "weight", "score", "n_parts", "n_missing"])
    s = sp_mod.sensitivity(scores, perturbation=0.25, top_n=1).set_index("species_id")
    assert s.base_rank[1] == 1 and s.base_rank[2] == 2
    assert s.rank_worst[1] == 2 and s.rank_best[2] == 1 and s.max_rank_shift[1] == 1
    assert s.worst_single_change[1] == "x -25%" and bool(s.top1_in_all_scenarios[1]) is False and bool(s.top1_in_any_scenario[2]) is True


def test_sensitivity_zero_perturbation_changes_nothing():
    scores, _ = sp_mod.score_species(tiny_species(["Fast", "Medium", "Slow"]), TINY, TAGS)
    s = sp_mod.sensitivity(scores, perturbation=0.0)
    assert (s.max_rank_shift == 0).all() and (s.rank_best == s.base_rank).all() and (s.rank_worst == s.base_rank).all()


def test_sensitivity_scenario_count_is_2n_single_plus_2_to_the_n_combined():
    scores, _ = sp_mod.score_species(tiny_species(["Fast", "Medium", "Slow"]), TINY, TAGS)
    assert (sp_mod.sensitivity(scores).n_scenarios == 2 * 2 + 2 ** 2).all()


# ---- real Day 1 data (skipped if the outputs are not there)
needs_data = pytest.mark.skipif(not (PROCESSED / "species_clean.csv").exists(), reason="Day 1 outputs not generated")


@needs_data
def test_real_run_writes_small_files_with_one_row_per_species_and_purpose(tmp_path):
    for f in ("species_clean.csv", "species_sources.csv", "tag_maps_urban.csv"):
        (tmp_path / f).write_bytes((PROCESSED / f).read_bytes())
    res, sens = sp_mod.run(tmp_path, WEIGHTS)
    assert len(res) == 45 * 3 and len(sens) == 45 * 3
    assert not res.duplicated(["species_id", "purpose"]).any()
    assert res.p_score.between(0, 1).all() and res.confidence.between(0, 1).all()
    assert (res.weights_status == "provisional").all()
    for f in ("purpose_scores.csv", "purpose_sensitivity.csv"):
        assert (tmp_path / f).stat().st_size < 1_000_000
    # ranks 1..n within each purpose and breakdown weights sum to 1
    assert (res.groupby("purpose")["rank"].min() == 1).all()
    for b in res.breakdown_json.head(30):
        d = json.loads(b)
        assert sum(c["weight"] for c in d.values()) == pytest.approx(1.0)


@needs_data
def test_real_data_missing_values_are_reported_never_filled():
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    w = sp_mod.load_weights(WEIGHTS)
    scores, parts = sp_mod.score_species(sp, w, sp_mod.load_tag_purpose(PROCESSED / "tag_maps_urban.csv"))
    # species with no foliage value: the part is null in the breakdown and the criterion mean used 0.5 for it
    sid = int(sp[sp.foliage.isna()].species_id.iloc[0])
    p = parts[(sid, "urban", "shade_provision")]
    assert p["foliage"] is None
    row = scores[(scores.species_id == sid) & (scores.purpose == "urban") & (scores.criterion == "shade_provision")].iloc[0]
    assert row.n_missing >= 1 and row.score == pytest.approx(np.mean([v if v is not None else 0.5 for v in p.values()]), abs=0.01)
