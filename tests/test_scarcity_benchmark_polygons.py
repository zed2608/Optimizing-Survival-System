"""Task 2 (polygon scarcity benchmark, scripts/scarcity_benchmark_polygons.py).
 - polygons are compact, 4-connected, exactly the requested size, and reproducible from the seeds;
 - a polygon made from chosen squares goes through the app's own `api_v2.plan_scope` and selects exactly those squares (and no others);
 - a small hand-built polygon case: a 4-square polygon with species counts that need more blocks than there are squares: every method places at most 4 blocks, Hungarian never fewer
   than greedy, and the cross-check of the benchmark holds;
 - the settings are the ones fixed before the first run.
Run from the repo root: python -m pytest tests/test_scarcity_benchmark_polygons.py"""
import importlib.util, sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("scarcity_benchmark_polygons", ROOT / "scripts" / "scarcity_benchmark_polygons.py")
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)
sb = sp.sb

needs_data = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists(), reason="run scripts/rebuild_scores.py first")


def test_the_settings_are_the_ones_fixed_before_the_first_run():
    p = sp.POLY
    assert p["polygon_master_seed"] == 2027 and p["sizes"] == (5, 10, 25, 50, 100) and p["polygons_per_size"] == 20 and p["seed_attempts"] == 20
    assert p["same_polygons_for_both_S_sources"] is True and sb.SETTINGS["tightness_targets"] == (0.3, 0.6, 0.9) and sb.SETTINGS["solver_seed"] == 42


def toy_grid():
    """A 4 x 4 block of squares (rows 0-3, columns 0-3), index = row * 4 + column."""
    import pandas as pd
    return pd.DataFrame({"cell_row": [r for r in range(4) for _ in range(4)], "cell_col": [c for _ in range(4) for c in range(4)]})


def test_grow_region_is_compact_connected_exact_and_reproducible():
    nbrs = sp.neighbour_lists(toy_grid())
    assert sorted(nbrs[0]) == [1, 4] and sorted(nbrs[5]) == [1, 4, 6, 9]                       # corner: 2 neighbours; inner square: 4
    a = sp.grow_region(nbrs, 5, 4, np.random.default_rng([1, 2, 3]))
    b = sp.grow_region(nbrs, 5, 4, np.random.default_rng([1, 2, 3]))
    assert a == b and len(a) == 4 and 5 in a
    g = toy_grid()
    rows, cols = g.cell_row.to_numpy()[a], g.cell_col.to_numpy()[a]
    assert rows.max() - rows.min() <= 1 and cols.max() - cols.min() <= 1                       # grown by most shared neighbours: a 2 x 2 block, not a line
    assert sp.grow_region(nbrs, 0, 17, np.random.default_rng(1)) is None                       # an island of 16 cannot reach 17


@needs_data
def test_a_polygon_goes_through_plan_scope_and_selects_exactly_its_squares():
    d = sb.load_world("rules")
    sites = d.ctx.sites
    nbrs = sp.neighbour_lists(sites)
    idx = sp.grow_region(nbrs, 100, 6, np.random.default_rng([sp.POLY["polygon_master_seed"], 0, 0]))
    gj = sp.region_polygon(sites, idx)
    assert gj["type"] == "Polygon" and len(gj["coordinates"]) >= 1
    d.field_ex_ids = set()
    sc, secs = sp.scope_of(d, gj)
    assert sorted(sc.sub.sites.point_id.astype(int)) == sorted(sites.point_id.iloc[idx].astype(int)) and secs >= 0
    assert sc.area["type"] == "polygon" and len(sc.sub.sites) == 6


@needs_data
def test_a_small_hand_built_polygon_case_strands_for_every_method():
    """4 squares, three species whose counts need at least 6 blocks: unavoidable stranding. Nobody can place more than the 4 squares, Hungarian never fewer than greedy."""
    d = sb.load_world("rules")
    d.field_ex_ids = set()
    sites = d.ctx.sites
    idx = sp.grow_region(sp.neighbour_lists(sites), 2000, 4, np.random.default_rng(7))
    sc, _ = sp.scope_of(d, sp.region_polygon(sites, idx))
    sub = sc.sub
    assert len(sub.sites) == 4
    cap = sb.pal.block_table(sub.species).capacity.to_numpy(dtype=float)
    st = sb.pal.species_stats(sub.S, sub.P["urban"], sb.S_MIN)
    pool, _ = sb.pal.eligible_pool(sub.species, st, [sb.pal.parse_months(v) for v in sub.species.planting_months], sb.pal.CFG, cap)
    cols = sorted(pool[:3])
    assert len(cols) == 3
    blocks_q = [2, 2, 2]                                                                        # 6 blocks asked for 4 squares
    case = {"cols": cols, "U": int((sub.S[:, cols] >= sb.S_MIN).any(axis=1).sum()), "asked": int(sum(int(cap[c]) * b for c, b in zip(cols, blocks_q))), "blocks_asked": 6,
            "blocks_q": blocks_q, "trees_q": [int(cap[c]) * b for c, b in zip(cols, blocks_q)], "caps": [int(cap[c]) for c in cols]}
    rows, err = sb.run_case(sub, "urban", case, "blocks", sb.SETTINGS["solver_seed"])
    assert err is None, err
    by = {r["method"]: r for r in rows}
    assert by["hungarian"]["check_ok"] is True and by["greedy"]["check_ok"] is True
    for m in by:
        assert by[m]["placed_blocks"] <= 4 + 1e-9 and by[m]["blocks_asked"] == 6
    assert by["hungarian"]["placed_blocks"] >= by["greedy"]["placed_blocks"]
    assert by["hungarian"]["placed_trees"] >= by["greedy"]["placed_trees"] and by["hungarian"]["placed_trees"] < case["asked"]
