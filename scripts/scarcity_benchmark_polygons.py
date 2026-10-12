#!/usr/bin/env python3
"""Polygon benchmark: Hungarian vs greedy vs random feasible in SMALL drawn areas (task 2 of the scarcity benchmark; blocks layout with species_counts).

    python scripts/scarcity_benchmark_polygons.py        # about 5 minutes; writes docs/defense/scarcity_benchmark_polygons.csv (and a generated section of the report)

The dashboard lets a user draw a polygon ("Draw an area") and plan inside it; the API takes the same polygon in POST /plan-event. This benchmark makes random compact polygons of
5, 10, 25, 50 and 100 grid squares, runs the app's own `api_v2.plan_scope` with the polygon (area + exclusions) and then the production `run_plan.make_plan` on the squares it returns
(the two calls `api_v2.create_plan` makes; nothing is saved), with species counts at three tightness levels, for Hungarian and greedy; the random feasible baseline is built from the project's
`matching.assign_random` exactly as in scripts/scarcity_benchmark.py, whose functions are reused. Production code is not changed.

Every setting is in POLY (and sb.SETTINGS) below and was fixed BEFORE the first run; nothing was tuned after looking at results.
"""
import argparse, os, sys, tempfile, time
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("OS_FIELD_DB", str(Path(tempfile.mkdtemp(prefix="scarcity_poly_")) / "field_checks.db"))   # no project field checks are read or written (set before api_v2 is imported)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scarcity_benchmark as sb  # noqa: E402  (the first benchmark: its functions are reused unchanged)

# =====================================================================================================================
# SETTINGS: FIXED BEFORE THE FIRST RUN (round 22, task 2). Do not change them after seeing results; a change means a new, labelled run.
# =====================================================================================================================
POLY = {
    "polygon_master_seed": 2027,               # seeds the polygons: np.random.default_rng([polygon_master_seed, size index, polygon index]); species sets: [.., size, polygon, purpose, tightness]
    "sizes": (5, 10, 25, 50, 100),             # target number of grid squares of a polygon (one square is about 1 ha)
    "polygons_per_size": 20,
    "seed_attempts": 20,                       # a polygon slot tries up to this many seed squares (the first of a seeded permutation of all scored squares) until a region of exactly the target size grows
    "growth_rule": "start at the seed square; repeatedly add the 4-neighbour (same row or column, scored squares only) that touches most squares already in the region, ties broken at random; stop at the target size",
    "polygon_shape": "the union of the squares' 100 m x 100 m footprints (centre +/- 50 m in UTM 51N), converted to lon/lat: a GeoJSON Polygon, as a user would send it",
    "scored_squares": "all 8,010 scored squares (confirmed zoning + outside the zoning map, the app's default); the 78 excluded squares are never in a polygon's plan",
    "species_k": "k = 2 + ((polygon index + purpose index + tightness index) mod 4), i.e. 2 to 5 chosen species",
    "species_choice": "k species drawn at random, without replacement, from the species that may enter a palette in that polygon and purpose (as in the first benchmark)",
    "counts": "blocks asked B = max(k, round(tightness x U)), split as evenly as possible over the k species, trees of a species = its blocks x its trees per full block, at most 2,000 trees (as in the first benchmark); U = squares of the polygon with S >= 0.50 for at least one chosen species",
    "plans_per_polygon": "3 purposes x 3 tightness levels = 9 (tightness targets, solver seed and random repeats are those of sb.SETTINGS)",
    "same_polygons_for_both_S_sources": True,
}
OUT_DIR = ROOT / "docs" / "defense"
HALF = 50.0                                    # half the side of a grid square, metres


# ---------------------------------------------------------------------------------------------------- polygons
def neighbour_lists(sites):
    """For every scored square the indices of its 4 neighbours (same row or column, next cell) that are scored squares too."""
    rc = list(zip(sites.cell_row.astype(int), sites.cell_col.astype(int)))
    pos = {k: i for i, k in enumerate(rc)}
    return [[pos[n] for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)) if n in pos] for r, c in rc]


def grow_region(nbrs, seed_idx, target, rng):
    """A compact 4-connected set of `target` squares grown from seed_idx, or None if it cannot reach that size (an island)."""
    region = {int(seed_idx)}
    while len(region) < target:
        cand = {}
        for i in region:
            for n in nbrs[i]:
                if n not in region:
                    cand[n] = cand.get(n, 0) + 1
        if not cand:
            return None
        best = max(cand.values())
        region.add(int(rng.choice(sorted(i for i, v in cand.items() if v == best))))
    return sorted(region)


def region_polygon(sites, idx):
    """GeoJSON Polygon (lon/lat) of the union of the footprints of the squares idx, or None if the union is not one valid polygon."""
    from pyproj import Transformer
    from shapely.geometry import box, mapping
    from shapely.ops import transform, unary_union
    boxes = [box(sites.utm_e.iloc[i] - HALF, sites.utm_n.iloc[i] - HALF, sites.utm_e.iloc[i] + HALF, sites.utm_n.iloc[i] + HALF) for i in idx]
    u = unary_union(boxes)
    if u.geom_type != "Polygon" or not u.is_valid:
        return None
    t = Transformer.from_crs("EPSG:32651", "EPSG:4326", always_xy=True)
    g = transform(lambda x, y, z=None: t.transform(x, y), u)
    rings = mapping(g)["coordinates"]
    return {"type": "Polygon", "coordinates": [[list(p) for p in ring] for ring in rings]}


def make_polygons(sites, log=print):
    """All polygons of the benchmark: [{size, id, seed_point_id, idx, geojson}], and the polygon-level skips [{size, id, reason}]. Depends only on the grid and the seeds."""
    nbrs = neighbour_lists(sites)
    out, skipped = [], []
    for si, size in enumerate(POLY["sizes"]):
        for pi in range(POLY["polygons_per_size"]):
            rng = np.random.default_rng([POLY["polygon_master_seed"], si, pi])
            order = rng.permutation(len(sites))[:POLY["seed_attempts"]]
            got, why = None, f"no region of {size} squares could be grown from {POLY['seed_attempts']} seed squares"
            for s in order:
                idx = grow_region(nbrs, int(s), size, rng)
                if idx is None:
                    continue
                gj = region_polygon(sites, idx)
                if gj is None:
                    why = "the union of the squares was not one valid polygon"
                    continue
                got = {"size": size, "id": f"{size}-{pi:02d}", "seed_point_id": int(sites.point_id.iloc[int(s)]), "idx": idx, "geojson": gj}
                break
            if got is None:
                skipped.append({"size": size, "id": f"{size}-{pi:02d}", "reason": why})
            else:
                out.append(got)
    log(f"  polygons: {len(out)} made, {len(skipped)} skipped")
    return out, skipped


def scope_of(d, geojson):
    """The planning context of a polygon through the app's own plan_scope (area + exclusions); returns (scope, seconds)."""
    import api_v2
    req = api_v2.PlanRequest(purpose="urban", n_saplings=1, polygon=geojson)
    t0 = time.perf_counter()
    sc = api_v2.plan_scope(d, req, None, strict=True)
    return sc, time.perf_counter() - t0


# ---------------------------------------------------------------------------------------------------- the benchmark
def run_polygon_benchmark(worlds, polygons, log=print):
    S = sb.SETTINGS
    rows, skipped_cases = [], []
    for s_source in S["s_sources"]:
        d = worlds[s_source]
        d.field_ex_ids = set()                                     # no field-check exclusions (the real file has none for 'not plantable' anyway)
        t0 = time.time()
        for poly in polygons:
            si = POLY["sizes"].index(poly["size"])
            pn = int(poly["id"].split("-")[1])
            sc, scope_s = scope_of(d, poly["geojson"])
            sub = sc.sub
            if len(sub.sites) != poly["size"]:
                skipped_cases.append({"s_source": s_source, "polygon": poly["id"], "reason": f"plan_scope found {len(sub.sites)} squares, not {poly['size']}"})
                continue
            for pu, purpose in enumerate(S["purposes"]):
                for ti, tau in enumerate(S["tightness_targets"]):
                    k = 2 + ((pn + pu + ti) % 4)
                    rng = np.random.default_rng([POLY["polygon_master_seed"], si, pn, pu, ti])
                    base = {"s_source": s_source, "polygon_size": poly["size"], "polygon": poly["id"], "seed_point_id": poly["seed_point_id"], "squares_in_area": len(sub.sites),
                            "purpose": purpose, "tightness_target": tau, "k_species": k, "scope_seconds": scope_s}
                    case, why = sb.make_case(sub, purpose, tau, k, rng, "blocks")
                    if case is None:
                        skipped_cases.append({**base, "reason": why})
                        continue
                    res, err = sb.run_case(sub, purpose, case, "blocks", S["solver_seed"])
                    if res is None:
                        skipped_cases.append({**base, "reason": err})
                        continue
                    info = {**base, "species_ids": ";".join(str(int(sub.species.species_id.iloc[c])) for c in case["cols"]),
                            "species": ";".join(str(sub.species.common_name.iloc[c]) for c in case["cols"]), "squares_suiting_any": case["U"]}
                    for x in res:
                        rows.append({**info, **x, "tightness_achieved": round(x["blocks_asked"] / case["U"], 4)})
        log(f"  {s_source}: {time.time() - t0:.0f} s, plans so far {len(rows) // 3}")
    df = pd.DataFrame(rows)
    df["stranded_blocks"] = df.blocks_asked - df.placed_blocks
    df["stranded_trees"] = df.trees_asked - df.placed_trees
    df["mean_W_per_block"] = df.total_W / df.placed_blocks.where(df.placed_blocks > 0)
    return df, pd.DataFrame(skipped_cases)


def summarise_size(df, s_source, size):
    ok = df[(df.s_source == s_source) & (df.polygon_size == size)]
    k = ["polygon", "purpose", "tightness_target"]
    h, g, r = (ok[ok.method == m].set_index(k) for m in ("hungarian", "greedy", "random_feasible"))
    n = len(h)
    s = {"size": size, "polygons": int(ok.polygon.nunique()), "plans": n}
    if n == 0:
        return s
    for tag, x in (("H", h), ("G", g), ("R", r)):
        s["blocks_placed_" + tag] = round(float(x.placed_blocks.sum()), 1)
        s["trees_placed_" + tag] = round(float(x.placed_trees.sum()), 1)
        s["stranded_trees_" + tag] = round(float(x.stranded_trees.sum()), 1)
    s["blocks_asked"], s["trees_asked"] = int(h.blocks_asked.sum()), int(h.trees_asked.sum())
    s["greedy_fewer_blocks"] = int((g.placed_blocks < h.placed_blocks).sum())
    s["hungarian_fewer_blocks"] = int((h.placed_blocks < g.placed_blocks).sum())
    s["max_extra_stranded_trees_greedy"] = int((g.stranded_trees - h.stranded_trees).max())
    same = h.placed_blocks == g.placed_blocks
    gap = ((h.total_W - g.total_W) / h.total_W.where(h.total_W > 0) * 100)[same]
    s["same_blocks"] = int(same.sum())
    s["same_lower"], s["same_higher"] = int((gap > 1e-6).sum()), int((gap < -1e-6).sum())
    s["gap_max"] = float(gap.max()) if len(gap) else 0.0
    s["unavoidable"] = int((h.stranded_blocks > 0).sum())
    s["tight_median"] = round(float(h.tightness_achieved.median()), 2)
    s["solver_ms"] = {t: round(float(x.solver_seconds.median()) * 1000, 2) for t, x in (("H", h), ("G", g), ("R", r))}
    s["plan_ms"] = {t: round(float(x.plan_seconds.median()) * 1000, 1) for t, x in (("H", h), ("G", g))}
    s["scope_ms"] = round(float(h.scope_seconds.median()) * 1000, 1)
    s["check"] = f"{int(h.check_ok.sum() + g.check_ok.sum())} of {2 * n}"
    return s


def tables_md(df, s_source):
    rows = [summarise_size(df, s_source, size) for size in POLY["sizes"]]
    a = ["| Squares | Polygons | Plans | Blocks asked | Blocks placed H / G / R | Trees asked | Trees placed H / G / R | Trees stranded H / G / R |", "|---|---|---|---|---|---|---|---|"]
    b = ["| Squares | Plans where greedy places fewer blocks | ... Hungarian places fewer (must be 0) | Most extra trees greedy strands in one plan | Same blocks: greedy W lower / higher | Largest W gap | Plans where even Hungarian cannot place all | Median achieved tightness |", "|---|---|---|---|---|---|---|---|"]
    c = ["| Squares | Solver ms H / G / R (median) | make_plan ms H / G (median) | plan_scope ms (median) | Cross-check |", "|---|---|---|---|---|"]
    for s in rows:
        if s["plans"] == 0:
            continue
        a.append(f"| {s['size']} | {s['polygons']} | {s['plans']} | {s['blocks_asked']} | {s['blocks_placed_H']:.0f} / {s['blocks_placed_G']:.0f} / {s['blocks_placed_R']:.0f} | {s['trees_asked']} | "
                 f"{s['trees_placed_H']:.0f} / {s['trees_placed_G']:.0f} / {s['trees_placed_R']:.0f} | {s['stranded_trees_H']:.0f} / {s['stranded_trees_G']:.0f} / {s['stranded_trees_R']:.0f} |")
        b.append(f"| {s['size']} | {s['greedy_fewer_blocks']} | {s['hungarian_fewer_blocks']} | {s['max_extra_stranded_trees_greedy']} | {s['same_lower']} / {s['same_higher']} (of {s['same_blocks']}) | {s['gap_max']:.2f}% | {s['unavoidable']} | {s['tight_median']} |")
        c.append(f"| {s['size']} | {s['solver_ms']['H']} / {s['solver_ms']['G']} / {s['solver_ms']['R']} | {s['plan_ms']['H']} / {s['plan_ms']['G']} | {s['scope_ms']} | {s['check']} |")
    return "\n".join(a) + "\n\n" + "\n".join(b) + "\n\n" + "\n".join(c) + "\n"


def section_md(df, poly_skipped, case_skipped, facts, n_polygons):
    P, S = POLY, sb.SETTINGS
    md = ["## Part 2: polygon benchmark (small drawn areas, blocks layout with species_counts)", "",
          "Generated by `scripts/scarcity_benchmark_polygons.py`; every plan is in `scarcity_benchmark_polygons.csv`. **The settings below were fixed before the first run and were not changed after seeing results.**", "",
          "### Settings (fixed before the first run)", ""]
    md += [f"- **{k}**: {v}" for k, v in P.items()]
    md += [f"- **tightness_targets / solver_seed / random_repeats / max_trees / purposes / s_sources** (from the first benchmark): {S['tightness_targets']} / {S['solver_seed']} / {S['random_repeats']} / {S['max_trees']} / {S['purposes']} / {S['s_sources']}", "",
           "### Setup", "",
           f"- **Code path**: `api_v2.plan_scope` with the polygon (the app's own area and exclusion step), then `run_plan.make_plan(..., species_counts=..., layout_mode=\"blocks\")`, the two calls `api_v2.create_plan` makes (the plan is not saved). Random feasible: `matching.assign_random` on the same matrix, as in part 1.",
           f"- **S source**: main `rf`, sensitivity `rules`; used: {facts['s_used']}. **Wetness**: included (saved scores). **Habagat**: off (no dates). **Release hash**: {facts['release_hash']}. **Git**: branch `{facts['git_branch']}`, HEAD `{facts['git_commit']}` plus uncommitted work. **Date**: {facts['date']}.",
           f"- **Polygons made**: {n_polygons} of {len(P['sizes']) * P['polygons_per_size']} slots; skipped at polygon level: {len(poly_skipped)}"
           + ("" if len(poly_skipped) == 0 else " (" + "; ".join(f"{r['id']}: {r['reason']}" for r in poly_skipped[:5]) + ")") + ". "
           f"Plans skipped at case level: {0 if case_skipped.empty else len(case_skipped)}"
           + ("" if case_skipped.empty else " (" + "; ".join(f"{k}: {v} rows" for k, v in case_skipped.reason.value_counts().items()) + ")") + ".", "",
           "### Two things to keep in mind when reading these tables", "",
           "- **One grid square is about 1 ha (100 m x 100 m).** A real school yard, a roadside strip or a garden smaller than one square cannot be represented: the smallest area here (5 squares) is about 5 ha, and a plan always uses whole squares.",
           "- **Separate plans do not exclude each other's squares; only top-ups do.** Two plans drawn over the same polygon get the same squares (and a polygon already planted is not removed from a new plan). So scarcity in these tables comes from the size of the polygon and the species chosen, not from earlier plans.", ""]
    for s_source in S["s_sources"]:
        md += [f"### S source {s_source}" + (" (main)" if s_source == "rf" else " (sensitivity)"), "", tables_md(df, s_source)]
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default=str(OUT_DIR / "_polygon_section.md"), help="where to write the generated report section")
    a = ap.parse_args()
    t0 = time.time()
    print("loading the data of the app for both S sources ...", flush=True)
    worlds = {s: sb.load_world(s) for s in sb.SETTINGS["s_sources"]}
    polygons, poly_skipped = make_polygons(worlds["rf"].ctx.sites)
    df, case_skipped = run_polygon_benchmark(worlds, polygons)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["s_source", "polygon_size", "polygon", "seed_point_id", "squares_in_area", "purpose", "tightness_target", "k_species", "species_ids", "species", "squares_suiting_any", "method",
            "trees_asked", "blocks_asked", "tightness_achieved", "placed_blocks", "placed_trees", "stranded_blocks", "stranded_trees", "total_W", "mean_W_per_block",
            "plan_seconds", "solver_seconds", "scope_seconds", "check_ok", "total_W_production"]
    d = df.copy()
    for c in ("total_W", "mean_W_per_block", "plan_seconds", "solver_seconds", "scope_seconds", "placed_blocks", "placed_trees", "stranded_blocks", "stranded_trees"):
        d[c] = d[c].round(6)
    d[[c for c in cols if c in d.columns]].to_csv(OUT_DIR / "scarcity_benchmark_polygons.csv", index=False)
    facts = sb.setup_facts(worlds)
    Path(a.section).write_text(section_md(df, poly_skipped, case_skipped, facts, len(polygons)), encoding="utf-8")
    ok = df
    print(f"done in {time.time() - t0:.0f} s: {len(ok) // 3} plans, {len(poly_skipped)} polygon slots skipped, {len(case_skipped)} plan cases skipped; wrote scarcity_benchmark_polygons.csv")
    print("cross-check failures:", int((ok.check_ok == False).sum()))  # noqa: E712


if __name__ == "__main__":
    main()
