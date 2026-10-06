"""Tests for pipeline/make_pair_table.py and pipeline/compare_models.py. Run from the repo root:
python -m pytest tests/test_compare_models.py"""
import copy, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import compare_models as cm  # noqa: E402
import make_pair_table as mpt  # noqa: E402

PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
FORBIDDEN = {"s_rule", "s_prob", "confidence", "breakdown_json", "suitable", "suitable_clean", "label_flipped"}


# ---- tiny synthetic inputs ------------------------------------------------------------------------------------------
def tiny_inputs(n_sites=80, n_species=6, seed=0):
    rng = np.random.default_rng(seed)
    sites = pd.DataFrame({"point_id": np.arange(n_sites), "cell_row": np.arange(n_sites) // 10 * 3, "cell_col": np.arange(n_sites) % 10 * 3,
                          "elev_m": rng.uniform(5, 500, n_sites), "slope_pct": rng.uniform(0, 50, n_sites),
                          "soil_texture_legacy": rng.choice(["Clay", "Clay Loam", None], n_sites)})
    species = pd.DataFrame({"species_id": np.arange(1, n_species + 1), "elev_min_m": 0.0, "elev_max_m": rng.uniform(200, 600, n_species),
                            "max_slope_pct": rng.uniform(15, 45, n_species), "waterlog_tol": rng.choice(["Low", "Medium", "High"], n_species),
                            "soil_any_texture": [False] * (n_species - 1) + [True],
                            "soil_textures": ["Clay Loam;Loam", "Clay", "Sandy", "Loam;Clay", None, None][:n_species]})
    pts, sps = np.meshgrid(sites.point_id, species.species_id)
    scores = pd.DataFrame({"point_id": pts.ravel(), "species_id": sps.ravel()})
    m = scores.merge(sites[["point_id", "elev_m", "slope_pct"]], on="point_id").merge(species[["species_id", "elev_max_m", "max_slope_pct"]], on="species_id")
    scores["s_rule"] = np.where((m.elev_m <= m.elev_max_m) & (m.slope_pct <= m.max_slope_pct), 0.8, 0.2)
    return sites, species, scores, pd.Series(rng.uniform(0, 300, n_sites))


@pytest.fixture(scope="module")
def tiny_table():
    return mpt.build_pair_table(*tiny_inputs())


def small_cfg(**over):
    cfg = copy.deepcopy(cm.CFG)
    cfg.update(subsample_n=None, outer_folds=3, inner_folds=2, rf_trees=8, spatial_block_cells=9, n_jobs=1, noise_levels=(0.0, 0.05),
               grids={"RandomForest": {"clf__max_depth": [3, None]}, "LogisticRegression": {"clf__C": [0.1, 1.0]},
                      "KNN": {"clf__n_neighbors": [5, 15]}, "DecisionTree": {"clf__max_depth": [3, 6]}})
    cfg.update(over)
    return cfg


# ---- label and noise -------------------------------------------------------------------------------------------------
def test_label_is_s_rule_at_the_threshold_and_s_rule_is_not_kept():
    sites, species, scores, water = tiny_inputs()
    scores = scores.copy(); scores.loc[0, "s_rule"] = 0.5; scores.loc[1, "s_rule"] = 0.4999; scores.loc[2, "s_rule"] = 0.9
    t = mpt.build_pair_table(sites, species, scores, water).set_index(["point_id", "species_id"])
    key = lambda i: (int(scores.point_id[i]), int(scores.species_id[i]))
    assert [t.suitable_clean[key(i)] for i in (0, 1, 2)] == [1, 0, 1]
    assert not (FORBIDDEN - {"suitable", "suitable_clean", "label_flipped"}) & set(t.columns) and "s_rule" not in t.columns


def test_noise_flips_the_requested_fraction_with_a_fixed_seed():
    y = np.random.default_rng(1).integers(0, 2, 1000)
    n0, f0 = mpt.apply_noise(y, 0.0, 42)
    n5a, f5a = mpt.apply_noise(y, 0.05, 42)
    n5b, f5b = mpt.apply_noise(y, 0.05, 42)
    assert (n0 == y).all() and f0.sum() == 0
    assert f5a.sum() == 50 and (n5a != y).sum() == 50 and (f5a == f5b).all() and (n5a == n5b).all()
    assert (mpt.apply_noise(y, 0.05, 7)[1] != f5a).any()                      # a different seed gives different flips
    assert (y == 0).sum() + (y == 1).sum() == 1000 and (y == mpt.apply_noise(y, 0.05, 42)[0] ^ f5a).all()


# ---- leakage ---------------------------------------------------------------------------------------------------------
def test_features_contain_no_answer_derived_columns(tiny_table):
    feats = mpt.feature_columns(tiny_table)
    assert feats and not set(feats) & FORBIDDEN
    assert not any(p in c for c in feats for p in mpt.FORBIDDEN_FEATURE_PARTS)
    assert not set(feats) & (set(mpt.ID_COLUMNS) | set(mpt.LABEL_COLUMNS))
    assert {"elev_m", "slope_pct", "water_dist_m", "elev_min_m", "elev_max_m", "max_slope_pct", "waterlog_tol_level", "soil_any_texture"} <= set(feats)
    assert any(c.startswith("site_tex_") for c in feats) and any(c.startswith("sp_tex_") for c in feats)


def test_feature_selection_rejects_a_leaky_column():
    bad = pd.DataFrame({"elev_m": [1.0], "site_tex_s_rule_copy": [1]})
    with pytest.raises(ValueError, match="leakage"):
        mpt.feature_columns(bad)


def test_leak_columns_never_reach_the_models(tiny_table):
    leaky = tiny_table.assign(s_rule=0.5, confidence=1.0, breakdown_json="{}", f_elevation=1.0)
    assert not set(mpt.feature_columns(leaky)) & {"s_rule", "confidence", "breakdown_json", "f_elevation"}


# ---- folds -----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("setting", ["random", "spatial", "species"])
def test_folds_partition_the_rows_and_are_reproducible(tiny_table, setting):
    cfg = small_cfg(); y = tiny_table.suitable_clean.to_numpy()
    a, b = cm.make_folds(tiny_table, y, setting, cfg), cm.make_folds(tiny_table, y, setting, cfg)
    assert len(a) == cfg["outer_folds"]
    assert all((x[0] == z[0]).all() and (x[1] == z[1]).all() for x, z in zip(a, b))
    tests = np.concatenate([te for _, te in a])
    assert sorted(tests) == list(range(len(tiny_table)))                       # every row tested exactly once
    assert all(not set(tr) & set(te) for tr, te in a)


def test_leave_species_out_folds_share_no_species_between_train_and_test(tiny_table):
    folds = cm.make_folds(tiny_table, tiny_table.suitable_clean.to_numpy(), "species", small_cfg())
    sp = tiny_table.species_id.to_numpy()
    for tr, te in folds:
        assert not set(sp[tr]) & set(sp[te]) and set(sp[te])


def test_spatial_folds_never_split_a_block_between_train_and_test(tiny_table):
    cfg = small_cfg(); g = cm.group_ids(tiny_table, "spatial", cfg)
    for tr, te in cm.make_folds(tiny_table, tiny_table.suitable_clean.to_numpy(), "spatial", cfg):
        assert not set(g[tr]) & set(g[te])


# ---- budget, identical folds across models, determinism --------------------------------------------------------------
def test_every_model_has_the_same_tuning_budget():
    assert cm.check_equal_budget(cm.CFG) == 4 and cm.check_equal_budget(small_cfg()) == 2
    bad = small_cfg(); bad["grids"]["KNN"] = {"clf__n_neighbors": [5]}
    with pytest.raises(ValueError, match="unequal"):
        cm.check_equal_budget(bad)


@pytest.fixture(scope="module")
def tiny_run(tiny_table):
    return cm.run_comparison(tiny_table, small_cfg())


def test_all_models_see_identical_folds(tiny_run):
    _, per_fold = tiny_run
    for (setting, noise, fold), g in per_fold.groupby(["setting", "noise", "fold"]):
        assert g.test_fingerprint.nunique() == 1 and g.n_train.nunique() == 1 and g.n_test.nunique() == 1
        assert set(g.model) == set(cm.MODELS + [cm.CAL_NAME])
    # and the folds do not change with the noise level
    fp = per_fold.groupby(["setting", "fold", "noise"]).test_fingerprint.first().unstack("noise")
    assert (fp[0.0] == fp[0.05]).all()


def test_every_model_was_tuned_and_calibrated_rf_is_reported(tiny_run):
    summary, per_fold = tiny_run
    assert per_fold.best_params.str.contains("clf__").all()
    assert set(summary.model) == set(cm.MODELS + [cm.CAL_NAME]) and set(summary.metric) == set(cm.METRICS)
    assert set(summary.setting) == {"random", "spatial", "species"} and set(summary.noise) == {0.0, 0.05}
    assert len(summary) == 5 * 3 * 2 * 6
    s = summary.set_index(["model", "setting", "noise", "metric"])
    assert s["mean"].xs("brier", level="metric").between(0, 1).all() and s["mean"].xs("accuracy", level="metric").between(0, 1).all()
    assert (s["n_folds"] == 3).all() and summary["std"].notna().all()


def test_running_twice_gives_identical_numbers(tiny_table, tiny_run):
    again, _ = cm.run_comparison(tiny_table, small_cfg())
    pd.testing.assert_frame_equal(again, tiny_run[0])


def test_shared_subsample_has_the_requested_size_and_is_used_by_all(tiny_table):
    summary, _ = cm.run_comparison(tiny_table, small_cfg(subsample_n=200, noise_levels=(0.0,), settings=("random",)))
    assert (summary.n_rows == 200).all()


def test_platt_calibration_also_runs(tiny_table):
    summary, _ = cm.run_comparison(tiny_table, small_cfg(calibration="platt", noise_levels=(0.0,), settings=("random",)))
    assert cm.CAL_NAME in set(summary.model)


# ---- real pair table (skipped if not generated) ----------------------------------------------------------------------
needs_table = pytest.mark.skipif(not (PROCESSED / mpt.TABLE_FILE).exists(), reason="run make_pair_table.py first")


@needs_table
def test_real_pair_table_has_only_raw_features_and_all_pairs():
    t = pd.read_csv(PROCESSED / mpt.TABLE_FILE)
    feats = mpt.feature_columns(t)
    assert len(t) == t.point_id.nunique() * 45 and t.species_id.nunique() == 45
    assert not set(feats) & FORBIDDEN and not {"s_rule", "confidence", "breakdown_json"} & set(t.columns)
    assert set(t.suitable_clean) == {0, 1} and (t.suitable != t.suitable_clean).sum() == t.label_flipped.sum()
