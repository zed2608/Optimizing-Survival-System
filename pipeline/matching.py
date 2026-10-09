#!/usr/bin/env python3
"""
matching.py - Day 3 part 1b: assign sapling slots to grid points (replaces the logic of optimization.py).

Library module (used by run_plan.py). Left nodes = sapling slots (species quota from palettes.py), right nodes = candidate
points (legal zone, S >= S_MIN for that species). W = S x P if S >= S_MIN else 0. Cost = 1 - W; infeasible pairs cost BIG_COST.
Solved with scipy.optimize.linear_sum_assignment on the rectangular slots x points matrix. Greedy and random assignment are
provided as baselines for the benchmark. Slots or points that cannot be matched are returned, never hidden.

Each point is a ~100 m grid cell (the grid spacing is exactly 100 m in UTM), so a plan places at most ONE tree per cell.
Existing trees: pass a table with utm_e/utm_n (or lon/lat); points within EXCLUSION_RADIUS_M of a tree are dropped. Without
such a table no exclusion is applied (the caller says so in its output).
Spacing: every palette species must have spacing_min_m below GRID_SPACING_M (asserted), so two different grid cells are
always far enough apart; check_assignment re-verifies the real distances.
"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

# =====================================================================================================================
# CONFIG - every tunable number lives here. PROVISIONAL.
# =====================================================================================================================
CFG = {
    "s_min": 0.50,                  # a point is feasible for a species when S >= this
    "big_cost": 1.0e6,              # cost of an infeasible (slot, point) pair; far above any feasible total cost per slot (<= 1)
    "exclusion_radius_m": 5.0,      # drop points within this distance of an existing tree (only if a trees table is given)
    "grid_spacing_m": 100.0,        # distance between neighbouring grid points (UTM metres)
    "seed": 42,                     # tie-breaking order of the points and the random baselines
    "site_crs": "EPSG:32651",       # UTM 51N, the CRS of utm_e / utm_n
    "scores_db": "scores/site_scores.db",
    "scores_csv": "scores/site_scores.csv",
}
# =====================================================================================================================

PURPOSES = ("urban", "planting", "watershed")


@dataclass
class Context:
    sites: pd.DataFrame             # legal-zone points, one row per point
    species: pd.DataFrame           # one row per species (order = columns of S)
    S: np.ndarray                   # (n_points x n_species) s_rule
    P: dict                         # purpose -> (n_species,) purpose fitness
    scores_path: Path               # site_scores.db or .csv (for the per-pair breakdown)
    species_flags: dict             # species_id -> list of data-quality flags


def load_context(out_dir="data/processed", scores_path=None):
    """Read the Day 1 / Day 2 outputs. Only legal-zone points are kept."""
    out = Path(out_dir)
    sites = pd.read_csv(out / "site_points_clean.csv")
    sites = sites[sites.is_legal_zone.astype(bool)].reset_index(drop=True)
    species = pd.read_csv(out / "species_clean.csv")
    ps = pd.read_csv(out / "purpose_scores.csv")
    P = {}
    for purpose, g in ps.groupby("purpose"):
        v = g.set_index("species_id").p_score.reindex(species.species_id)
        if v.isna().any():
            raise ValueError(f"purpose_scores.csv has no score for every species ({purpose})")
        P[purpose] = v.to_numpy(dtype=float)
    path = Path(scores_path) if scores_path else None
    if path is None:
        path = out / CFG["scores_db"] if (out / CFG["scores_db"]).exists() else out / CFG["scores_csv"]
    if path.suffix == ".db":
        con = sqlite3.connect(path)
        sc = pd.read_sql_query("SELECT point_id, species_id, s_rule FROM site_scores", con)
        con.close()
    else:
        sc = pd.read_csv(path, usecols=["point_id", "species_id", "s_rule"])
    S = sc.pivot(index="point_id", columns="species_id", values="s_rule").reindex(index=sites.point_id, columns=species.species_id)
    if S.isna().any().any():
        raise ValueError("site_scores does not cover every legal point x species pair; run score_sites.py")
    src = pd.read_csv(out / "species_sources.csv", usecols=["species_id", "flags"])
    flags = {int(sid): ["species_data_unverified"] for sid in src[src["flags"].fillna("").str.contains("file_source_not_provided")].species_id.unique()}
    return Context(sites, species, S.to_numpy(dtype=float), P, path, flags)


def area_mask(sites, zone=None, bbox=None):
    """Boolean mask of the points inside the area filter (zone_desc, case-insensitive, and/or lon/lat box)."""
    m = np.ones(len(sites), dtype=bool)
    if zone:
        zm = sites.zone_desc.fillna("").str.strip().str.lower() == zone.strip().lower()
        if not zm.any():
            raise ValueError(f"no legal point in zone '{zone}'. Zones: {sorted(sites.zone_desc.dropna().unique())}")
        m &= zm.to_numpy()
    if bbox:
        lo_lon, lo_lat, hi_lon, hi_lat = bbox
        m &= ((sites.lon >= lo_lon) & (sites.lon <= hi_lon) & (sites.lat >= lo_lat) & (sites.lat <= hi_lat)).to_numpy()
    return m


def exclusion_keep_mask(sites, trees, radius=None, crs=None):
    """True = keep. Drops points within `radius` metres of an existing tree. trees: DataFrame with utm_e/utm_n or lon/lat."""
    r = CFG["exclusion_radius_m"] if radius is None else radius
    if trees is None or len(trees) == 0:
        return np.ones(len(sites), dtype=bool)
    if {"utm_e", "utm_n"} <= set(trees.columns):
        xy = trees[["utm_e", "utm_n"]].to_numpy(dtype=float)
    elif {"lon", "lat"} <= set(trees.columns):
        from pyproj import Transformer
        tr = Transformer.from_crs("EPSG:4326", CFG["site_crs"] if crs is None else crs, always_xy=True)
        e, n = tr.transform(trees.lon.to_numpy(dtype=float), trees.lat.to_numpy(dtype=float))
        xy = np.column_stack([e, n])
    else:
        raise ValueError("trees table needs columns utm_e,utm_n or lon,lat")
    xy = xy[~np.isnan(xy).any(axis=1)]
    d, _ = cKDTree(xy).query(sites[["utm_e", "utm_n"]].to_numpy(dtype=float), k=1)
    return d > r


def assert_spacing_ok(spacing_min_m, grid_spacing_m=None):
    """Every palette species must have spacing_min_m below the grid spacing (else grid points would be too close)."""
    g = CFG["grid_spacing_m"] if grid_spacing_m is None else grid_spacing_m
    s = np.asarray(spacing_min_m, dtype=float)
    assert (s < g).all(), f"spacing_min_m must be below the {g} m grid spacing for every palette species: {s[~(s < g)]}"


def weights(S, P, s_min=None, mult=None):
    """W = S x P where S >= s_min else 0; plus the feasibility mask. mult (optional, one number per point) multiplies W only: S and the S >= s_min test are not touched
    (round 15b: the Habagat multiplier of the MAO, applied to the ranking score only)."""
    sm = CFG["s_min"] if s_min is None else s_min
    feasible = S >= sm
    W = np.where(feasible, S * np.asarray(P)[None, :], 0.0)
    if mult is not None:
        W = W * np.asarray(mult, dtype=float)[:, None]
    return W, feasible


def site_mult(sites):
    """The per-point W multiplier of a sites table (column w_mult), or None when the table has none (every plan and ranking made without the Habagat adjustment)."""
    return sites["w_mult"].to_numpy(dtype=float) if "w_mult" in sites else None


def _slots(quotas):
    return np.repeat(np.arange(len(quotas)), np.asarray(quotas, dtype=int))


def _result(point_idx, species_idx, quotas):
    pi, si = np.asarray(point_idx, dtype=int), np.asarray(species_idx, dtype=int)
    placed = np.bincount(si, minlength=len(quotas)) if len(si) else np.zeros(len(quotas), dtype=int)
    return {"point_idx": pi, "species_idx": si, "placed": placed, "unmatched_by_species": np.asarray(quotas, dtype=int) - placed,
            "unmatched_saplings": int(np.sum(quotas) - len(pi))}


TIEBREAK_EPS = 1e-6      # weight of the tie-break term in the cost (blocks mode)


def assign_hungarian(W, feasible, quotas, seed=None, big_cost=None, tiebreak=None):
    """Optimal assignment of the slots to distinct points (minimum total cost 1 - W); infeasible pairs are dropped afterwards.
    tiebreak (optional, one number in [0, 1] per point, for example the distance to the centre of the chosen area): added to the cost with the weight TIEBREAK_EPS, so it only
    separates points whose W is practically equal; without it ties fall to a seeded random order (the plan of before)."""
    big = CFG["big_cost"] if big_cost is None else big_cost
    rng = np.random.default_rng(CFG["seed"] if seed is None else seed)
    cols = np.where(feasible.any(axis=1))[0]
    if len(cols) == 0 or int(np.sum(quotas)) == 0:
        return _result([], [], quotas)
    cols = cols[rng.permutation(len(cols))]                      # seeded tie-break order
    slot_sp = _slots(quotas)
    cost = np.where(feasible[cols][:, slot_sp].T, 1.0 - W[cols][:, slot_sp].T, big)
    if tiebreak is not None:
        cost = np.where(cost < big / 2, cost + TIEBREAK_EPS * np.asarray(tiebreak, dtype=float)[cols][None, :], cost)
    r, c = linear_sum_assignment(cost)
    keep = cost[r, c] < big / 2
    return _result(cols[c[keep]], slot_sp[r[keep]], quotas)


def assign_greedy(W, feasible, quotas, seed=None, tiebreak=None):
    """Repeatedly take the best remaining (point, species) pair that is feasible and still has quota. With a tiebreak (distance to the centre of the area) equal pairs go to the nearest point first."""
    rng = np.random.default_rng(CFG["seed"] if seed is None else seed)
    perm = rng.permutation(W.shape[0]) if tiebreak is None else np.argsort(np.asarray(tiebreak, dtype=float), kind="stable")
    Wp, Fp = W[perm], feasible[perm]
    left = np.asarray(quotas, dtype=int).copy(); used = np.zeros(W.shape[0], dtype=bool)
    pts, sps = [], []
    for _ in range(int(left.sum())):
        cur = np.where(Fp & ~used[:, None] & (left > 0)[None, :], Wp, -np.inf)
        k = int(np.argmax(cur))
        i, j = divmod(k, cur.shape[1])
        if not np.isfinite(cur[i, j]):
            break
        used[i] = True; left[j] -= 1; pts.append(perm[i]); sps.append(j)
    return _result(pts, sps, quotas)


def assign_random(W, feasible, quotas, seed=None, respect_feasible=True):
    """Random baseline. respect_feasible=False ignores S >= S_MIN entirely (a blind random placement on legal points)."""
    rng = np.random.default_rng(CFG["seed"] if seed is None else seed)
    n = W.shape[0]
    used = np.zeros(n, dtype=bool)
    pts, sps = [], []
    for j in rng.permutation(_slots(quotas)):
        ok = np.where(~used & (feasible[:, j] if respect_feasible else True))[0]
        if len(ok) == 0:
            continue
        i = int(rng.choice(ok)); used[i] = True; pts.append(i); sps.append(int(j))
    return _result(pts, sps, quotas)


def check_assignment(xy, S, spacing_min_m, result, quotas, s_min=None, max_species_quota=None, max_genus_quota=None, genera=None):
    """Count constraint violations of an assignment (all should be 0 for hungarian / greedy / random-feasible)."""
    sm = CFG["s_min"] if s_min is None else s_min
    pi, si = result["point_idx"], result["species_idx"]
    quotas = np.asarray(quotas, dtype=int)
    out = {"below_threshold": int((S[pi, si] < sm).sum()) if len(pi) else 0,
           "point_reused": int(len(pi) - len(np.unique(pi))),
           "over_quota": int(np.maximum(np.bincount(si, minlength=len(quotas)) - quotas, 0).sum()) if len(si) else 0}
    if max_species_quota is not None and len(si):
        out["over_species_cap"] = int(np.maximum(np.bincount(si, minlength=len(quotas)) - max_species_quota, 0).sum())
    if max_genus_quota is not None and genera is not None and len(si):
        g = pd.Series(np.asarray(genera, dtype=object)[si]).value_counts()
        out["over_genus_cap"] = int(np.maximum(g.to_numpy() - max_genus_quota, 0).sum())
    spacing = np.asarray(spacing_min_m, dtype=float)
    conflicts = 0
    if len(pi) > 1:
        pts = xy[pi]
        r = float(spacing[np.unique(si)].max())
        for a, b in cKDTree(pts).query_pairs(r):
            if np.hypot(*(pts[a] - pts[b])) < max(spacing[si[a]], spacing[si[b]]):
                conflicts += 1
    out["spacing_conflicts"] = conflicts
    return out
