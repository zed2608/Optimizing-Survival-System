"""Tests for pipeline/palettes.py, matching.py and run_plan.py. Run from the repo root:  python -m pytest tests/test_matching.py"""
import itertools, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import matching as mt  # noqa: E402
import palettes as pal  # noqa: E402
import run_plan as rp  # noqa: E402

PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
CAP_SP, CAP_GEN = pal.CFG["max_species_share"], pal.CFG["max_genus_share"]


# ---- synthetic inputs ------------------------------------------------------------------------------------------------
def make_species(n=12, genera=None, dioecious=(), months=None):
    genera = genera or [f"G{i}" for i in range(n)]
    return pd.DataFrame({"species_id": np.arange(1, n + 1), "common_name": [f"sp{i}" for i in range(1, n + 1)], "genus": genera,
                         "is_dioecious": [i in dioecious for i in range(1, n + 1)], "spacing_min_m": 10.0,
                         "planting_months": months or ["5;6;7"] * n})


def make_S(n_pts=400, n_sp=12, seed=0, p_ok=0.8):
    rng = np.random.default_rng(seed)
    return np.where(rng.random((n_pts, n_sp)) < p_ok, rng.uniform(0.5, 1.0, (n_pts, n_sp)), rng.uniform(0, 0.49, (n_pts, n_sp)))


# ---- palettes --------------------------------------------------------------------------------------------------------
def test_palette_respects_size_caps_and_sums_to_n():
    sp, S = make_species(12, genera=["A", "A", "A", "B", "B", "C", "D", "E", "F", "G", "H", "I"]), make_S()
    P = np.linspace(0.9, 0.3, 12)
    p = pal.build_palette(sp, S, P, 300)
    assert pal.CFG["palette_min"] <= len(p["species_id"]) <= pal.CFG["palette_max"]
    q, g = np.array(p["quota"]), pd.Series(sp.set_index("species_id").genus.reindex(p["species_id"]).to_numpy())
    assert q.sum() == 300 and (q <= int(CAP_SP * 300)).all()
    assert pd.Series(q).groupby(g).sum().max() <= int(CAP_GEN * 300)
    assert sum(p["share"]) == pytest.approx(1.0) and not p["warnings"]


def test_genus_cap_binds_when_one_genus_dominates():
    q = pal.allocate_quotas([0.9, 0.9, 0.9, 0.2, 0.2, 0.2, 0.2], ["A", "A", "A", "B", "C", "D", "E"], [1000] * 7, 100, 0.20, 0.30)
    assert q.sum() == 100 and q[:3].sum() <= 30 and q.max() <= 20


def test_quotas_never_exceed_eligible_points_and_shortage_is_visible():
    q = pal.allocate_quotas([0.5, 0.5, 0.5], ["A", "B", "C"], [3, 4, 5], 100, 0.5, 1.0)
    assert list(q) == [3, 4, 5]                                              # only 12 of 100 saplings can be absorbed
    sp, S = make_species(7), make_S(n_pts=10, n_sp=7)
    p = pal.build_palette(sp, S, np.full(7, 0.8), 500)
    assert p["allocated"] < 500 and p["unallocated"] == 500 - p["allocated"] and any("caps_cannot_absorb" in w for w in p["warnings"])


def test_all_palette_species_share_a_planting_month_and_missing_months_are_excluded():
    months = ["5;6", "6;7", "7;8", "5;6", "5;6", "6", "5;6", None, "5;6", "5;6"]
    sp = make_species(10, months=months)
    p = pal.build_palette(sp, make_S(n_sp=10), np.linspace(0.9, 0.5, 10), 300)
    sets = [pal.parse_months(m) for m in sp.set_index("species_id").planting_months.reindex(p["species_id"])]
    assert set.intersection(*sets) and p["common_months"] == sorted(set.intersection(*sets))
    assert p["excluded"][8] == "planting_months_missing" and 8 not in p["species_id"]
    assert 3 not in p["species_id"] or 1 not in p["species_id"]                # '7;8' and '5;6' cannot be together


def test_dioecious_species_needs_quota_two_and_carries_the_flag_otherwise_is_left_out():
    sp, S = make_species(9, dioecious=(1, 2)), make_S(n_sp=9)
    P = np.array([0.9, 0.05, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8])             # sp1 strong dioecious, sp2 weak dioecious
    p = pal.build_palette(sp, S, P, 300)
    flag = dict(zip(p["species_id"], p["needs_both_sexes"])); q = dict(zip(p["species_id"], p["quota"]))
    assert 1 in q and flag[1] and q[1] >= 2
    assert all(q[s] >= 2 for s in q if flag[s])
    # with 8 saplings the same species cannot reach quota 2 and must be left out
    small = pal.build_palette(sp, S, np.array([0.9] + [0.1] * 8), 8)
    assert all(not f or q_ >= 2 for f, q_ in zip(small["needs_both_sexes"], small["quota"]))


def test_species_whose_spacing_is_not_below_the_grid_is_excluded_and_the_assert_fires():
    sp = make_species(8); sp.loc[0, "spacing_min_m"] = 150.0
    p = pal.build_palette(sp, make_S(n_sp=8), np.full(8, 0.7), 100)
    assert p["excluded"][1] == "spacing_not_below_grid_spacing"
    with pytest.raises(AssertionError):
        mt.assert_spacing_ok([10.0, 100.0])
    mt.assert_spacing_ok([2.0, 15.0, 99.9])


# ---- matching on a synthetic grid --------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def grid():
    n = 400
    xy = np.array([[296000.0 + 100 * (i % 20), 1620000.0 + 100 * (i // 20)] for i in range(n)])
    S = make_S(n, 4, seed=3, p_ok=0.5)
    P = np.array([0.9, 0.7, 0.5, 0.3])
    W, F = mt.weights(S, P)
    return xy, S, P, W, F


@pytest.mark.parametrize("method", ["hungarian", "greedy", "random_feasible"])
def test_no_assignment_below_threshold_no_point_reused_no_quota_exceeded(grid, method):
    xy, S, P, W, F = grid
    q = np.array([30, 25, 20, 15])
    res = {"hungarian": lambda: mt.assign_hungarian(W, F, q, 1), "greedy": lambda: mt.assign_greedy(W, F, q, 1),
           "random_feasible": lambda: mt.assign_random(W, F, q, 1, True)}[method]()
    v = mt.check_assignment(xy, S, np.full(4, 10.0), res, q)
    assert v == {"below_threshold": 0, "point_reused": 0, "over_quota": 0, "spacing_conflicts": 0}
    assert (res["placed"] <= q).all() and len(res["point_idx"]) == 90


def test_hungarian_is_optimal_on_a_small_instance_and_never_worse_than_greedy_or_random():
    rng = np.random.default_rng(5)
    S = rng.uniform(0.5, 1.0, (7, 2)); S[rng.random((7, 2)) < 0.3] = 0.2
    P = np.array([0.9, 0.4]); W, F = mt.weights(S, P); q = np.array([2, 2])
    h = mt.assign_hungarian(W, F, q, 0)
    total = lambda r: W[r["point_idx"], r["species_idx"]].sum()
    best = 0.0                                                                 # brute force over every feasible assignment
    for pts in itertools.permutations(range(7), 4):
        sp = [0, 0, 1, 1]
        if all(F[p, s] for p, s in zip(pts, sp)):
            best = max(best, sum(W[p, s] for p, s in zip(pts, sp)))
    if len(h["point_idx"]) == 4:
        assert total(h) == pytest.approx(best)
    assert total(h) >= total(mt.assign_greedy(W, F, q, 0)) - 1e-9
    assert total(h) >= max(total(mt.assign_random(W, F, q, s, True)) for s in range(20)) - 1e-9


def test_shortage_is_reported_when_saplings_exceed_feasible_points(grid):
    xy, S, P, W, F = grid
    feasible_pts = F.any(axis=1).sum()
    q = np.array([200, 200, 200, 200])                                        # far more saplings than points
    for res in (mt.assign_hungarian(W, F, q, 0), mt.assign_greedy(W, F, q, 0)):
        assert len(res["point_idx"]) <= feasible_pts
        assert res["unmatched_saplings"] == q.sum() - len(res["point_idx"]) > 0
        assert (res["placed"] + res["unmatched_by_species"] == q).all()
        assert mt.check_assignment(xy, S, np.full(4, 10.0), res, q)["below_threshold"] == 0


def test_close_points_are_reported_as_spacing_conflicts():
    xy = np.array([[0.0, 0.0], [5.0, 0.0], [100.0, 0.0]])
    res = {"point_idx": np.array([0, 1, 2]), "species_idx": np.array([0, 0, 0])}
    v = mt.check_assignment(xy, np.full((3, 1), 0.9), np.array([10.0]), res, np.array([3]))
    assert v["spacing_conflicts"] == 1


def test_exclusion_zone_drops_points_within_five_metres_only_when_trees_are_given():
    sites = pd.DataFrame({"utm_e": [0.0, 100.0, 200.0], "utm_n": [0.0, 0.0, 0.0]})
    assert mt.exclusion_keep_mask(sites, None).all()
    keep = mt.exclusion_keep_mask(sites, pd.DataFrame({"utm_e": [3.0, 104.9, 215.0], "utm_n": [0.0, 0.0, 0.0]}))
    assert list(keep) == [False, False, True]                                  # 3 m and 4.9 m dropped, 15 m kept
    lonlat = pd.DataFrame({"lon": [121.15], "lat": [14.69]})
    from pyproj import Transformer
    e, n = Transformer.from_crs("EPSG:4326", mt.CFG["site_crs"], always_xy=True).transform(121.15, 14.69)
    s2 = pd.DataFrame({"utm_e": [e + 2.0, e + 50.0], "utm_n": [n, n]})
    assert list(mt.exclusion_keep_mask(s2, lonlat)) == [False, True]


# ---- real data (skipped when the Day 1 / Day 2 outputs are not there) ---------------------------------------------------
needs_data = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")


@pytest.fixture(scope="module")
def ctx():
    return mt.load_context(PROCESSED)


@needs_data
@pytest.mark.parametrize("purpose", ["urban", "planting", "watershed"])
def test_real_plan_satisfies_every_constraint(ctx, purpose):
    n = 300
    plan, s = rp.make_plan(ctx, purpose, n)
    assert len(plan) == n and s["saplings_unmatched"] == 0 and s["saplings_unallocated"] == 0
    assert (plan.S >= 0.5).all()                                               # no assignment below the threshold
    assert plan.point_id.is_unique                                             # each point used at most once
    legal = pd.read_csv(PROCESSED / "site_points_clean.csv").set_index("point_id").is_legal_zone.astype(bool)
    assert legal.reindex(plan.point_id).all()                                  # only legal-zone points
    sp = ctx.species.set_index("species_id")
    counts = plan.groupby("species_id").size()
    assert (counts <= int(CAP_SP * n)).all()                                   # per-species share cap
    assert plan.assign(g=plan.species_id.map(sp.genus)).groupby("g").size().max() <= int(CAP_GEN * n)
    assert np.allclose(plan.W, plan.S * plan.P, atol=1e-3)                    # W = S x P (all S >= 0.5 here)
    q = {p["species_id"]: p["quota"] for p in s["palette"]}
    assert all(counts[k] <= q[k] for k in counts.index)                        # no species above its quota
    # no two points closer than the larger of their species' spacing_min_m
    xy = plan[["utm_e", "utm_n"]].to_numpy(); spc = plan.species_id.map(sp.spacing_min_m).to_numpy()
    from scipy.spatial import cKDTree
    for a, b in cKDTree(xy).query_pairs(float(spc.max())):
        assert np.hypot(*(xy[a] - xy[b])) >= max(spc[a], spc[b])
    assert min(np.hypot(*(xy[a] - xy[b])) for a, b in cKDTree(xy).query_pairs(150.0)) >= 99.0     # one tree per ~100 m cell


@needs_data
@pytest.mark.parametrize("purpose", ["urban", "planting", "watershed"])
def test_real_dioecious_species_have_two_or_more_and_the_flag(ctx, purpose):
    plan, s = rp.make_plan(ctx, purpose, 300)
    dio = set(ctx.species[ctx.species.is_dioecious.astype(bool)].species_id)
    for sid, g in plan.groupby("species_id"):
        if sid in dio:
            assert len(g) >= 2 and g["flags"].str.contains("needs_both_sexes").all()
    assert all(p["needs_both_sexes"] == (p["species_id"] in dio) for p in s["palette"])
    months = [set(map(int, str(ctx.species.set_index("species_id").planting_months[p["species_id"]]).split(";"))) for p in s["palette"]]
    assert set.intersection(*months) == set(s["palette_common_planting_months"]) and s["palette_common_planting_months"]


@needs_data
def test_real_shortage_is_reported_never_hidden(ctx):
    plan, s = rp.make_plan(ctx, "urban", 500, zone="Sanitary Landfill")          # 19 legal points only (round 15a: the landfill zone, with its DENR condition)
    assert len(plan) <= 19 and len(plan) == s["saplings_placed"]
    assert s["n_saplings_requested"] == s["saplings_allocated"] + s["saplings_unallocated"]
    assert s["saplings_allocated"] == s["saplings_placed"] + s["saplings_unmatched"]
    assert s["saplings_unallocated"] + s["saplings_unmatched"] == 500 - len(plan) > 0
    assert s["unused_candidate_points"] == 19 - len(plan)


@needs_data
def test_real_area_filters_and_exclusion_statement(ctx, tmp_path):
    plan, s = rp.make_plan(ctx, "planting", 40, zone="Agricultural Zone")
    assert set(plan.zone_desc) == {"Agricultural Zone"} and "no trees table" in s["existing_trees"]
    box = (121.14, 14.66, 121.18, 14.70)
    p2, s2 = rp.make_plan(ctx, "planting", 40, bbox=box)
    assert p2.lon.between(box[0], box[2]).all() and p2.lat.between(box[1], box[3]).all()
    first = plan.iloc[0]
    trees = pd.DataFrame({"utm_e": [first.utm_e + 3.0], "utm_n": [first.utm_n]})                      # 3 m from a candidate
    p3, s3 = rp.make_plan(ctx, "planting", 40, zone="Agricultural Zone", trees=trees)
    assert first.point_id not in set(p3.point_id) and s3["area"]["points_dropped_near_existing_trees"] == 1
    assert "within 5.0 m dropped" in s3["existing_trees"]
    with pytest.raises(ValueError):
        rp.make_plan(ctx, "planting", 10, zone="No Such Zone")


@needs_data
def test_real_same_seed_gives_the_same_plan_and_files_are_written(ctx, tmp_path):
    a, sa = rp.make_plan(ctx, "watershed", 120, seed=7)
    b, sb = rp.make_plan(ctx, "watershed", 120, seed=7)
    pd.testing.assert_frame_equal(a, b)
    assert sa == sb
    f, sj = rp.write_plan(tmp_path, "watershed", a, sa, stamp="20260101_000000")
    assert f.name == "plan_watershed_20260101_000000.csv" and f.parent.name == "plans"
    out = pd.read_csv(f)
    assert list(out.columns) == rp.PLAN_COLUMNS and len(out) == 120
    js = json.loads(sj.read_text())
    assert {"palette", "saplings_placed", "saplings_unmatched", "mean_W", "limits"} <= set(js) and js["limits"][0].startswith("Each point is a ~100 m grid cell")
    assert out.site_scores_src_ids.notna().all()


@needs_data
def test_real_scores_csv_fallback_gives_the_same_S(ctx):
    csv = PROCESSED / "scores" / "site_scores.csv"
    if not csv.exists():
        pytest.skip("site_scores.csv not generated")
    c2 = mt.load_context(PROCESSED, csv)
    assert np.allclose(c2.S, ctx.S)


@needs_data
def test_real_benchmark_hungarian_is_best_and_random_blind_violates(ctx, tmp_path):
    bench, f = rp.run_benchmark(ctx, tmp_path)
    assert f.exists() and len(bench) == 2 * 3 * 4 and set(bench.n_saplings) == {300} and set(bench.layout_mode) == {"points", "blocks"}      # points and blocks (round 9)
    assert bench[bench.layout_mode == "points"].groupby("purpose").placed.max().eq(300).all()                                              # points: one sapling per square
    assert (bench[(bench.layout_mode == "blocks") & (bench.method == "hungarian")].placed < 60).all()                                      # blocks: a few squares hold the 300 trees
    for (layout, purpose), g in bench.groupby(["layout_mode", "purpose"]):
        g = g.set_index("method")
        assert g.total_W["hungarian"] >= g.total_W["greedy"] - 1e-6
        assert g.total_W["hungarian"] >= g.total_W["random_feasible"] and g.total_W["hungarian"] > g.total_W["random_blind"]
        assert g.violations_total[["hungarian", "greedy", "random_feasible"]].eq(0).all() and g.violations_total["random_blind"] > 0
