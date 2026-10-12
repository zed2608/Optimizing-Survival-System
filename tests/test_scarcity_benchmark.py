"""Task 1 (12 Oct handoff): the scarcity benchmark (scripts/scarcity_benchmark.py).
 - a tiny hand-built case where greedy strands a tree and Hungarian does not (pinned: it is the mechanism the benchmark measures);
 - the helper functions (trees formula, the split of blocks, the random baseline);
 - a smoke test on the smallest real barangay: the rebuilt matching reproduces `run_plan.make_plan` (the benchmark's own cross-check) and Hungarian never places fewer.
Run from the repo root: python -m pytest tests/test_scarcity_benchmark.py"""
import importlib.util, sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import matching as mt  # noqa: E402

spec = importlib.util.spec_from_file_location("scarcity_benchmark", ROOT / "scripts" / "scarcity_benchmark.py")
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)


def tiny():
    """3 squares, 2 species. Species A (flexible) suits all three squares and likes square 0 best; species B (picky) suits only square 0.
    Greedy gives square 0 to A first (W 0.9 beats 0.6) and then B has no square. Hungarian puts A on square 1 and B on square 0: both placed."""
    W = np.array([[0.9, 0.6], [0.8, 0.0], [0.7, 0.0]])
    feas = np.array([[True, True], [True, False], [True, False]])
    return W, feas, [1, 1]


def test_greedy_strands_the_picky_species_and_hungarian_does_not():
    W, feas, q = tiny()
    h, g = mt.assign_hungarian(W, feas, q, seed=1), mt.assign_greedy(W, feas, q, seed=1)
    assert len(h["point_idx"]) == 2 and h["unmatched_saplings"] == 0
    assert sorted(zip(h["species_idx"].tolist(), h["point_idx"].tolist())) == [(0, 1), (1, 0)]            # A on square 1, B on square 0
    assert len(g["point_idx"]) == 1 and g["unmatched_saplings"] == 1                                    # greedy: A took square 0, B is stranded
    assert g["unmatched_by_species"].tolist() == [0, 1]
    assert W[h["point_idx"], h["species_idx"]].sum() == pytest.approx(0.8 + 0.6) and W[g["point_idx"], g["species_idx"]].sum() == pytest.approx(0.9)


def test_the_benchmark_function_reports_the_same_on_the_tiny_case():
    W, feas, q = tiny()
    res = sb.evaluate_matching(W, feas, q, seed=42, tiebreak=None)
    assert res["hungarian"]["placed_blocks"] == 2 and res["hungarian"]["placed_trees"] == 2
    assert res["greedy"]["placed_blocks"] == 1 and res["greedy"]["placed_trees"] == 1
    assert res["hungarian"]["total_W"] == pytest.approx(1.4) and res["greedy"]["total_W"] == pytest.approx(0.9)
    r = res["random_feasible"]
    assert 1.0 <= r["placed_blocks"] <= 2.0 and r["placed_blocks"] <= res["hungarian"]["placed_blocks"]     # random never beats the optimum
    assert set(res) == {"hungarian", "greedy", "random_feasible"} and all(res[k]["solver_seconds"] >= 0 for k in res)


def test_the_random_baseline_is_reproducible():
    W, feas, q = tiny()
    a, b = sb.evaluate_matching(W, feas, q, 42, None), sb.evaluate_matching(W, feas, q, 42, None)
    assert a["random_feasible"]["placed_blocks"] == b["random_feasible"]["placed_blocks"] and a["random_feasible"]["total_W"] == b["random_feasible"]["total_W"]


def test_trees_formula_full_blocks_and_remainder():
    cap, blocks_q, trees_q = [36, 9], [3, 2], [100, 17]               # species 0: 3 blocks for 100 trees (last holds 28), species 1: 2 blocks for 17 trees (last holds 8)
    assert sb.trees_formula([3, 2], blocks_q, trees_q, cap) == 117       # everything placed: the trees asked
    assert sb.trees_formula([2, 2], blocks_q, trees_q, cap) == 72 + 17   # a block missing: the placed ones are full blocks
    assert sb.trees_formula([0, 1], blocks_q, trees_q, cap) == 9


def test_split_blocks_is_even_and_exact():
    b, trees = sb.split_blocks(7, 3, [36, 121, 9])
    assert b == [3, 2, 2] and sum(b) == 7 and trees == [108, 242, 18]
    assert sb.split_blocks(2, 2, [5, 5]) == ([1, 1], [5, 5])


def test_the_settings_are_the_ones_fixed_before_the_first_run():
    s = sb.SETTINGS
    assert s["master_seed"] == 2026 and s["solver_seed"] == 42 and s["random_repeats"] == 20 and s["replicates"] == 4
    assert s["tightness_targets"] == (0.3, 0.6, 0.9) and s["s_sources"] == ("rf", "rules") and s["layouts"] == ("blocks", "points") and s["max_trees"] == 2000


needs_data = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists(), reason="run scripts/rebuild_scores.py first")


@needs_data
@pytest.mark.parametrize("layout", ["blocks", "points"])
def test_smoke_on_the_smallest_real_barangay(layout):
    """The cross-check of the benchmark itself: the matching rebuilt in the script gives the placed blocks, trees and total W of the production make_plan."""
    d = sb.load_world("rules")                                              # explicit: the test run sets OS_S_SOURCE=rules, and 'rf' may not be saved on a fresh clone
    sizes = [(int((d.point_barangay == b).sum()), b) for b in range(len(d.barangay_names))]
    n, b = min(x for x in sizes if x[0] > 0)
    sub = sb.area_context(d, b)
    assert len(sub.sites) == n and n < 40
    done = 0
    for purpose in ("urban", "planting", "watershed"):
        rng = np.random.default_rng([sb.SETTINGS["master_seed"], b, 0, 2, 0])
        case, why = sb.make_case(sub, purpose, 0.9, 3, rng, layout)
        assert case is not None, why
        rows, err = sb.run_case(sub, purpose, case, layout, sb.SETTINGS["solver_seed"])
        assert err is None, err
        by = {r["method"]: r for r in rows}
        assert by["hungarian"]["check_ok"] is True and by["greedy"]["check_ok"] is True
        assert by["hungarian"]["placed_blocks"] >= by["greedy"]["placed_blocks"] >= 0
        assert by["random_feasible"]["placed_blocks"] <= by["hungarian"]["placed_blocks"] + 1e-9
        assert by["hungarian"]["placed_trees"] >= by["greedy"]["placed_trees"]
        done += 1
    assert done == 3


@needs_data
def test_cross_check_also_holds_for_a_large_plan():
    """The first full run flagged 694 cross-check failures because the tolerance for the 4-decimal rounding of make_plan's rows was too strict for plans with hundreds of rows."""
    d = sb.load_world("rules")
    b = d.barangay_display.index("Silangan")
    sub = sb.area_context(d, b)
    rng = np.random.default_rng([sb.SETTINGS["master_seed"], b, 0, 2, 0])
    case, why = sb.make_case(sub, "urban", 0.9, 3, rng, "points")
    rows, err = sb.run_case(sub, "urban", case, "points", sb.SETTINGS["solver_seed"])
    assert err is None, err
    by = {r["method"]: r for r in rows}
    assert by["hungarian"]["placed_blocks"] > 300 and by["hungarian"]["check_ok"] is True and by["greedy"]["check_ok"] is True
    assert abs(by["hungarian"]["total_W_production"] - by["hungarian"]["total_W"]) <= 5e-5 * by["hungarian"]["placed_blocks"]
