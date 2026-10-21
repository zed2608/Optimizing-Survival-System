#!/usr/bin/env python3
"""
point_layout.py - spaced planting points inside the area the user selected (replaces the row-by-row layout of a block).

WHAT IT DOES
  Input : the blocks of a plan (one 100 m grid square each: species, number of trees), the species table and the shape the user selected (a drawn polygon,
          a barangay outline, ...; None = the planned squares themselves).
  Output: for every block the planting points (metres, UTM 51N, deterministic), the walking order from START, the plantable region of the block and,
          when the trees do not fit at the required spacing, how many fit and why. Nothing is invented: a block never holds more trees than fit.

THE RULES (all numbers are in LAYOUT_CFG; PROVISIONAL [VERIFY with adviser / LGU], nothing here is a measured fact)
  1. Plantable area = (union of the planned 100 m squares) clipped to the selected shape, then pulled in from its edge by `edge_margin_m`.
     Squares that are not planned (not suitable, excluded, not selected) are outside it, so no tree goes there.
  2. Minimum distance between two trees of species i and j (ONE formula, `pair_distance`):
         d(i, j) = max( spacing_min_i , spacing_min_j , canopy_floor_fraction x mean(canopy_spread_i, canopy_spread_j) )
                   x ( 1 + spreading_root_extra   if the root_type text of i or of j names spreading / aggressive / extensive roots )
     spacing_min_m, canopy_spread_m and root_type come from species_clean.csv (the species dataset). With the dataset's values the canopy floor rarely decides
     (canopy / 2 is about the spacing_min of most species); the root extra is a modest +20 %.
  3. Points are placed by best-candidate sampling (a Poisson-disk-style blue-noise method): for each new tree `candidates` random places inside the plantable area
     of the block are tried, the ones that keep d(i, j) to every tree already placed (any species, also in the neighbouring blocks) are feasible and the one
     farthest from its neighbours (in units of its own required distance) is taken. Seeded by (seed, block ref): the same plan gives the same points.
  4. If `max_misses` tries in a row find no feasible place, the block is full: it keeps the trees placed so far and reports "X of N fit at the required spacing".
  5. The walking order starts at START (the plantable corner of the block nearest its south-west corner) and goes to the nearest unvisited tree each time,
     then a few 2-opt passes remove crossings. Numbers 1..n follow that route.
"""
import hashlib
import math
import re

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

# =====================================================================================================================
# CONFIG - PROVISIONAL [VERIFY with adviser / LGU]. Every tunable number of the layout is here (no hidden constants).
# =====================================================================================================================
LAYOUT_CFG = {
    "square_side_m": 100.0,         # the grid square of one block
    "edge_margin_m": 3.0,           # trees keep this far from the edge of the plantable area (the selected shape and the squares that are not planned)
    "canopy_floor_fraction": 0.30,  # d(i, j) is never below this fraction of the mean canopy spread of the pair
    "spreading_root_extra": 0.20,   # extra distance for a pair when one species has spreading / aggressive / extensive roots
    "spreading_root_words": r"aggressive|extensive|spreading|massive buttress",   # matched in the root_type text (lower case); anything else is not "spreading"
    "candidates": 30,               # best-candidate samples per tree
    "max_misses": 60,               # rounds of candidates without a feasible place before the block counts as full
    "two_opt_passes": 3,            # route clean-up passes
    "seed": 20261021,
}


def spreading_root(root_type, cfg=None):
    c = LAYOUT_CFG if cfg is None else cfg
    return bool(root_type) and re.search(c["spreading_root_words"], str(root_type).lower()) is not None


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def species_rules(species_rows):
    """{species_id: {name, smin, canopy, spreading}} from rows with species_id, common_name, spacing_min_m, canopy_spread_m, root_type. A missing value stays None."""
    out = {}
    for r in species_rows:
        out[int(r["species_id"])] = {"name": r.get("common_name", ""), "smin": _num(r.get("spacing_min_m")), "canopy": _num(r.get("canopy_spread_m")),
                                     "spreading": spreading_root(r.get("root_type"))}
    return out


def pair_distance(a, b, cfg=None):
    """The minimum distance (m) between a tree of species a and one of species b: THE formula (see the module text). a and b are species_rules() entries."""
    c = LAYOUT_CFG if cfg is None else cfg
    parts = [a["smin"], b["smin"]]
    if a["canopy"] is not None and b["canopy"] is not None:
        parts.append(c["canopy_floor_fraction"] * (a["canopy"] + b["canopy"]) / 2.0)
    d = max(p for p in parts if p is not None)
    return d * (1.0 + c["spreading_root_extra"]) if (a["spreading"] or b["spreading"]) else d


def plantable_region(squares, shape, cfg=None):
    """(region, inner): the planned squares clipped to the selected shape, and the same pulled in from its edge. Empty geometries when nothing is left."""
    c = LAYOUT_CFG if cfg is None else cfg
    region = unary_union(squares)
    if shape is not None:
        region = region.intersection(shape)
    inner = region.buffer(-c["edge_margin_m"]) if not region.is_empty else region
    return region, inner


def _polys(g):
    if g.is_empty:
        return []
    return [g] if isinstance(g, Polygon) else [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon) and not p.is_empty]


def route_order(points, start, passes=3):
    """The points (list of (x, y)) in walking order: nearest unvisited from `start`, then 2-opt passes. Returns the indices."""
    n = len(points)
    if n <= 2:
        return sorted(range(n), key=lambda i: math.dist(points[i], start))
    left = set(range(n))
    cur = min(left, key=lambda i: (math.dist(points[i], start), i))
    order = [cur]
    left.remove(cur)
    while left:
        cur = min(left, key=lambda i: (math.dist(points[i], points[order[-1]]), i))
        order.append(cur)
        left.remove(cur)
    d = lambda i, j: math.dist(points[order[i]], points[order[j]])
    for _ in range(passes):
        improved = False
        for i in range(0, n - 2):
            for j in range(i + 2, n):
                a, b = order[i], order[i + 1]
                cc = order[j]
                dd = order[j + 1] if j + 1 < n else None
                old = math.dist(points[a], points[b]) + (math.dist(points[cc], points[dd]) if dd is not None else 0.0)
                new = math.dist(points[a], points[cc]) + (math.dist(points[b], points[dd]) if dd is not None else 0.0)
                if new + 1e-9 < old:
                    order[i + 1:j + 1] = reversed(order[i + 1:j + 1])
                    improved = True
        if not improved:
            break
    return order


def layout_plan(blocks, species, shape=None, seed=None, cfg=None):
    """
    blocks : list of {"ref", "species_id", "n", "e", "n_utm"}  (e, n_utm = centre of the 100 m square in UTM metres; n = trees to plant)
    species: species_rules() table
    shape  : a shapely geometry in UTM metres (the area the user selected) or None
    Returns {"blocks": {ref: {...}}, "region": geometry, "inner": geometry, "cfg": the numbers used}. Per block: points [(x, y)] in WALKING ORDER (metres from the block's
    south-west corner), start (x, y), region (list of rings, local metres), requested, placed, fits (bool), reason, min_distance_m.
    """
    c = dict(LAYOUT_CFG if cfg is None else cfg)
    seed = c["seed"] if seed is None else seed
    half = c["square_side_m"] / 2.0
    sq = {b["ref"]: box(b["e"] - half, b["n_utm"] - half, b["e"] + half, b["n_utm"] + half) for b in blocks}
    region, inner = plantable_region(list(sq.values()), shape, c)
    ids = sorted({int(b["species_id"]) for b in blocks})
    dmat = {}
    for i in ids:
        for j in ids:
            if species[i]["smin"] is not None and species[j]["smin"] is not None:
                dmat[(i, j)] = pair_distance(species[i], species[j], c)
    cell = max(dmat.values()) if dmat else 10.0
    grid = {}                                   # spatial hash: cell -> list of (x, y, species_id)
    placed_all = []
    out = {}

    def feasible(x, y, sid):
        cx, cy = int(x // cell), int(y // cell)
        worst = math.inf
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for (px, py, ps) in grid.get((gx, gy), ()):
                    dist = math.hypot(x - px, y - py)
                    need = dmat[(sid, ps)]
                    if dist < need - 1e-9:
                        return None
                    worst = min(worst, dist / need)
        return worst

    for b in sorted(blocks, key=lambda b: b["ref"]):
        ref, sid, want = b["ref"], int(b["species_id"]), int(b["n"])
        sw = (b["e"] - half, b["n_utm"] - half)
        rules = species[sid]
        info = {"requested": want, "placed": 0, "fits": True, "reason": "", "points": [], "start": None, "region": [], "min_distance_m": None}
        out[ref] = info
        if rules["smin"] is None:
            info.update(fits=want == 0, reason="The species has no planting distance in the dataset (spacing_min_m is missing), so no spaced layout is possible.")
            continue
        info["min_distance_m"] = round(dmat[(sid, sid)], 2)
        area = inner.intersection(sq[ref]) if not inner.is_empty else inner
        polys = _polys(area)
        polys = [p for p in polys if p.area > 1.0]
        if not polys:
            info.update(fits=want == 0, reason=("The selected area leaves no plantable ground in this square after the edge margin of "
                                               f"{c['edge_margin_m']:g} m. Enlarge the area or choose another square."))
            continue
        area = unary_union(polys)
        shapely.prepare(area)
        minx, miny, maxx, maxy = area.bounds
        rng = np.random.default_rng(int.from_bytes(hashlib.sha256(f"{seed}:{ref}".encode("utf-8")).digest()[:8], "little"))   # the same plan always gives the same points
        pts = []
        misses = 0
        while len(pts) < want and misses < c["max_misses"]:
            xs = rng.uniform(minx, maxx, c["candidates"])
            ys = rng.uniform(miny, maxy, c["candidates"])
            inside = shapely.contains_xy(area, xs, ys)
            best, best_score = None, -1.0
            for x, y, ok in zip(xs, ys, inside):
                if not ok:
                    continue
                w = feasible(float(x), float(y), sid)
                if w is None:
                    continue
                score = w if w != math.inf else 1e9
                if score > best_score:
                    best, best_score = (float(x), float(y)), score
            if best is None:
                misses += 1
                continue
            misses = 0
            pts.append(best)
            grid.setdefault((int(best[0] // cell), int(best[1] // cell)), []).append((best[0], best[1], sid))
            placed_all.append((best[0], best[1], sid))
        # START: the plantable ground nearest the south-west corner of the square
        sp = nearest_points(area, Point(sw))[0]
        start = (sp.x, sp.y)
        order = route_order(pts, start, c["two_opt_passes"])
        pts = [pts[i] for i in order]
        info["points"] = [(round(x - sw[0], 3), round(y - sw[1], 3)) for x, y in pts]
        info["start"] = (round(start[0] - sw[0], 3), round(start[1] - sw[1], 3))
        info["placed"] = len(pts)
        info["region"] = [[(round(x - sw[0], 3), round(y - sw[1], 3)) for x, y in p.exterior.coords] for p in _polys(area)]
        if len(pts) < want:
            info["fits"] = False
            info["reason"] = (f"{len(pts)} of {want} fit at the required spacing (at least {info['min_distance_m']:g} m between trees). "
                              "Reduce the number of trees or enlarge the area.")
    return {"blocks": out, "region": region, "inner": inner, "cfg": c}
