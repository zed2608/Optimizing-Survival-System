"""Round 10a: the block model and the plan engine in blocks mode (pipeline/palettes.py, matching.py, run_plan.py), without the API.
Run from the repo root: python -m pytest tests/test_blocks_engine.py"""
import dataclasses, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

BLOCKS_DEFAULT = True          # tests/conftest.py: keep the real defaults (blocks) in this module
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT / "pipeline"))
import field_verify as fv  # noqa: E402
import matching as mt  # noqa: E402
import palettes as pal  # noqa: E402
import run_plan as rp  # noqa: E402

BC = pal.BLOCK_CFG
USABLE = BC["block_side_m"] * math.sqrt(BC["usable_share"])


@pytest.fixture(scope="module")
def ctx():
    return rp.load_context(PROCESSED, include_unzoned=True)


def plan_of(ctx, purpose="urban", n=300, **kw):
    kw.setdefault("seed", 1)
    return rp.make_plan(ctx, purpose, n, layout_mode="blocks", **kw)


# ---- the model -----------------------------------------------------------------------------------------------------------------------
def test_config_values_and_default_mode():
    assert BC["block_side_m"] == 100 and BC["usable_share"] == 0.6
    assert rp.CFG["layout_mode"] == "blocks"


def test_layout_formula_for_every_species(ctx):
    bt = pal.block_table(ctx.species)
    assert len(bt) == len(ctx.species) == 45
    sp = ctx.species.set_index("species_id")
    for r in bt.itertuples(index=False):
        lo, hi = sp.spacing_min_m[r.species_id], sp.spacing_max_m[r.species_id]
        if r.capacity != r.capacity:                                   # no distance at all: never guessed
            assert lo != lo and hi != hi and r.reason
            continue
        expect = (lo + hi) / 2 if lo == lo and hi == hi else (lo if lo == lo else hi)
        assert r.spacing_m == pytest.approx(round(expect * 2) / 2, abs=0.5) and (r.spacing_m * 2) == int(r.spacing_m * 2)
        n = max(1, math.floor(USABLE / r.spacing_m + 1e-9))
        assert (r.rows, r.trees_per_row, r.capacity) == (n, n, n * n)


def test_layout_dict_and_directions():
    lay = pal.block_layout(7.5)
    assert lay["usable_side_m"] == pytest.approx(77.46, abs=0.01) and lay["rows"] == 10 == lay["trees_per_row"] and lay["capacity"] == 100
    assert lay["row_direction"] == "east-west" and lay["start_corner"] == "south-west"
    assert pal.block_layout(500)["capacity"] == 1                      # at least one row of one tree


def test_spacing_uses_one_limit_when_the_other_is_missing_and_none_when_both_are():
    assert pal.species_spacing(6.0, float("nan")) == 6.0 and pal.species_spacing(float("nan"), 9.0) == 9.0
    assert pal.species_spacing(float("nan"), float("nan")) is None
    assert pal.species_spacing(5.0, 8.0) == 6.5


# ---- the plan ------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("purpose", ["urban", "planting", "watershed"])
def test_exact_tree_totals_blocks_and_per_species(ctx, purpose):
    plan, s = plan_of(ctx, purpose, 300)
    assert int(plan.trees_planned.sum()) == 300 == s["saplings_placed"] == s["layout"]["trees_placed"] and s["saplings_unmatched"] == 0
    assert sum(p["quota"] for p in s["palette"]) == 300 and sum(p["placed"] for p in s["palette"]) == 300
    assert s["layout"]["blocks"] == len(plan) == s["blocks_placed"] and s["layout"]["hectares_used"] == pytest.approx(len(plan))
    for p in s["palette"]:
        mine = plan[plan.species_id == p["species_id"]]
        assert p["blocks"] == p["blocks_placed"] == len(mine) == math.ceil(p["quota"] / p["capacity"])
        assert int(mine.trees_planned.sum()) == p["quota"]
        full = (mine.trees_planned == p["capacity"]).sum()
        assert full >= len(mine) - 1 and (mine.trees_planned <= p["capacity"]).all() and (mine.trees_planned >= 1).all()


def test_blocks_are_far_fewer_squares_than_trees(ctx):
    plan, s = plan_of(ctx, "urban", 300)
    assert len(plan) < 60 and len(plan) < 300


def test_one_block_per_square_and_none_below_s_min(ctx):
    for purpose in ("urban", "planting", "watershed"):
        plan, _ = plan_of(ctx, purpose, 500)
        assert plan.point_id.is_unique and (plan.S >= mt.CFG["s_min"]).all() and (plan.W > 0).all()


def test_capacity_columns_follow_the_species(ctx):
    plan, _ = plan_of(ctx, "planting", 300)
    bt = pal.block_table(ctx.species).set_index("species_id")
    for r in plan.itertuples(index=False):
        b = bt.loc[r.species_id]
        assert (r.spacing_m, r.rows, r.trees_per_row, r.capacity) == (b.spacing_m, b.rows, b.trees_per_row, b.capacity)
        assert r.row_direction == "east-west" and r.start_corner == "south-west" and r.usable_side_m == pytest.approx(77.46, abs=0.01)


def test_contour_note_only_on_steep_squares(ctx):
    plan, _ = plan_of(ctx, "watershed", 600)
    slope = ctx.sites.set_index("point_id").slope_pct
    for r in plan.itertuples(index=False):
        steep = slope[r.point_id] == slope[r.point_id] and slope[r.point_id] > BC["contour_slope_pct"]
        assert (r.layout_note == pal.CONTOUR_NOTE) == bool(steep)


def test_excluded_squares_are_never_used(ctx):
    plan, _ = plan_of(ctx, "urban", 300)
    gone = set(plan.point_id.astype(int)[:6])
    plan2, s2 = rp.make_plan(fv.filter_context(ctx, gone), "urban", 300, seed=1, layout_mode="blocks")
    assert not (set(plan2.point_id.astype(int)) & gone) and int(plan2.trees_planned.sum()) == 300


def test_points_mode_is_the_plan_of_before(ctx):
    plan, s = rp.make_plan(ctx, "urban", 120, seed=5, layout_mode="points")
    assert len(plan) == 120 == s["saplings_placed"] and plan.point_id.is_unique
    assert "trees_planned" not in plan.columns and "layout" not in s and "layout_mode" not in s and "blocks_placed" not in s
    again, _ = rp.make_plan(ctx, "urban", 120, seed=5, layout_mode="points")
    pd.testing.assert_frame_equal(plan, again)
    assert list(plan.columns) == rp.PLAN_COLUMNS


def test_a_species_without_spacing_is_left_out_with_a_reason(ctx):
    sp = ctx.species.copy()
    victim = int(sp.species_id.iloc[0])
    sp.loc[sp.species_id == victim, ["spacing_min_m", "spacing_max_m"]] = np.nan
    ctx2 = dataclasses.replace(ctx, species=sp)
    plan, s = rp.make_plan(ctx2, "urban", 200, seed=1, layout_mode="blocks")
    assert victim not in set(plan.species_id) and int(plan.trees_planned.sum()) == 200
    assert "spacing" in s["palette_excluded_species"][str(victim)].lower()
    bt = pal.block_table(sp).set_index("species_id")
    assert bt.loc[victim, "reason"] and bt.loc[victim, "capacity"] != bt.loc[victim, "capacity"]


def test_hungarian_and_greedy_place_the_same_trees(ctx):
    for purpose in ("urban", "watershed"):
        h, hs = plan_of(ctx, purpose, 300, method="hungarian")
        g, gs = plan_of(ctx, purpose, 300, method="greedy")
        assert hs["saplings_placed"] == gs["saplings_placed"] == 300
        assert hs["total_W"] >= gs["total_W"] - 1e-6


def test_ties_are_broken_by_distance_to_the_centre_and_cost_no_quality(ctx, monkeypatch):
    with_tb, s1 = plan_of(ctx, "urban", 300)
    again, _ = plan_of(ctx, "urban", 300)
    pd.testing.assert_frame_equal(with_tb, again)                      # deterministic
    orig = mt.assign_hungarian
    monkeypatch.setattr(mt, "assign_hungarian", lambda W, f, q, seed=None, big_cost=None, tiebreak=None: orig(W, f, q, seed, big_cost, None))
    without, s0 = plan_of(ctx, "urban", 300)
    cx, cy = s1["layout"]["centre_utm"]
    d1 = np.hypot(with_tb.utm_e - cx, with_tb.utm_n - cy).mean()
    d0 = np.hypot(without.utm_e - cx, without.utm_n - cy).mean()
    assert d1 <= d0 + 1e-6
    assert abs(s1["total_W"] - s0["total_W"]) < 1e-2
    assert "centre" in s1["layout"]["tiebreak"]


def test_a_chosen_species_list_gets_all_the_trees(ctx):
    ids = [int(x) for x in ctx.species.species_id.iloc[:6]]
    plan, s = rp.make_plan(ctx, "urban", 200, seed=1, species_ids=ids, layout_mode="blocks")
    assert set(plan.species_id) <= set(ids) and int(plan.trees_planned.sum()) == 200


def test_fixed_tree_counts_for_a_top_up(ctx):
    plan, _ = plan_of(ctx, "urban", 300)
    want = {int(plan.species_id.iloc[0]): 37, int(plan.species_id.iloc[-1]): 12}
    p2, s2 = rp.make_plan(ctx, "urban", 49, seed=1, species_ids=list(want), layout_mode="blocks", species_trees=want)
    assert {int(k): int(v) for k, v in p2.groupby("species_id").trees_planned.sum().items()} == want
    assert s2["saplings_placed"] == 49
