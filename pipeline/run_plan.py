#!/usr/bin/env python3
"""
run_plan.py - Day 3 part 1c: plan where to plant, for one purpose and an area (command-line tool).

    python pipeline/run_plan.py --purpose urban --n-saplings 200
    python pipeline/run_plan.py --purpose watershed --n-saplings 100 --zone "Forest Zone"
    python pipeline/run_plan.py --purpose planting --n-saplings 50 --bbox 121.17,14.66,121.21,14.70 [--trees-csv trees.csv]
    python pipeline/run_plan.py --benchmark            # Hungarian vs greedy vs random, 300 saplings, 3 purposes, whole municipality

Reads  data/processed/{scores/site_scores.db|csv, purpose_scores.csv, species_clean.csv, site_points_clean.csv, species_sources.csv}.
Writes data/processed/plans/plan_<purpose>_<timestamp>.csv and plan_<purpose>_<timestamp>_summary.json
       (--benchmark: data/processed/matching_benchmark.csv).
Only legal-zone points count. Each point is a ~100 m grid cell, so a plan places at most ONE tree per cell.
Unmatched saplings and unused candidate points are reported in the summary, never hidden.
"""
import argparse, json, math, sqlite3, sys, time
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import field_verify as fv  # noqa: E402
import landcover as lcv  # noqa: E402
import matching as mt  # noqa: E402
import palettes as pal  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# =====================================================================================================================
# CONFIG - every tunable number lives here. PROVISIONAL.
# =====================================================================================================================
CFG = {
    "seed": 42,                     # tie-break order of equal-W points and the random baselines
    "bench_saplings": 300,          # benchmark: saplings per purpose
    "bench_random_repeats": 20,     # benchmark: random assignment is averaged over this many seeds
    "low_confidence_below": 0.75,   # plan rows with a site_scores confidence below this get the flag low_confidence
    "timestamp_format": "%Y%m%d_%H%M%S",
    "plans_dir": "plans",
    "benchmark_file": "matching_benchmark.csv",
    "field_db": "data/field/field_checks.db",   # saved field checks (same file as api_v2.py); points whose latest check is not_plantable are left out
    "layout_mode": "blocks",        # LAYOUT_MODE: "blocks" (n_saplings = total trees, planted in blocks at the species spacing) or "points" (one tree per 100 m square, the plan of before)
    "include_unzoned": True,        # INCLUDE_UNZONED: also plan on squares outside every zoning polygon (zoning_status unconfirmed); they carry the flag zoning_unconfirmed
}
# =====================================================================================================================

UNCONFIRMED_FLAG = "zoning_unconfirmed"
UNCONFIRMED_NOTE = "Land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting"

BLOCK_COLUMNS = ["trees_planned", "spacing_m", "rows", "trees_per_row", "capacity", "usable_side_m", "row_direction", "start_corner", "layout_note"]   # added to PLAN_COLUMNS in blocks mode
BLOCK_LIMITS = ("Each block is one 100 m grid square, planted at the species spacing on its usable part (provisional share of the square); a plan places at most one block per square.",
                "Block layout (usable share, spacing rounding, capacity) is provisional until the agriculturist signs it off.",
                "Weights, caps and thresholds are provisional; site scores use the soft soil mode (texture mapping unverified).",
                "S comes from rules, not from field survival data.")
LIMITS = ("Each point is a ~100 m grid cell, so the plan places at most one tree per cell.",
          "Weights, caps and thresholds are provisional; site scores use the soft soil mode (texture mapping unverified).",
          "S comes from rules, not from field survival data.")


def attach_landcover(ctx, out_dir):
    """Add the ground-cover shares and ground_flags of data/processed/site_landcover.csv to ctx.sites (information only: S, P, the squares and their order are untouched).
    Without the file the context is returned as it is."""
    f = Path(out_dir) / "site_landcover.csv"
    if not f.is_file():
        return ctx
    import dataclasses
    lc = pd.read_csv(f)
    keep = ["point_id"] + lcv.SHARE_COLS + ["lc_coverage", "dominant_code", "ground_flags"]
    sites = ctx.sites.merge(lc[keep], on="point_id", how="left")
    sites["ground_flags"] = sites["ground_flags"].fillna("")
    assert len(sites) == len(ctx.sites) and (sites.point_id.to_numpy() == ctx.sites.point_id.to_numpy()).all()
    return dataclasses.replace(ctx, sites=sites)


def load_context(out_dir="data/processed", scores_path=None, include_unzoned=None):
    return attach_landcover(_load_context(out_dir, scores_path, include_unzoned), out_dir)


def _load_context(out_dir="data/processed", scores_path=None, include_unzoned=None):
    """Like matching.load_context, but with the squares OUTSIDE the zoning map (zoning_status unconfirmed) when include_unzoned is true (default CFG["include_unzoned"]).
    include_unzoned=False returns exactly what matching.load_context returns (confirmed legal-zone squares only). Without a zoning_status column (older data) only the legal-zone
    squares exist. matching.py itself is unchanged."""
    inc = CFG["include_unzoned"] if include_unzoned is None else include_unzoned
    out = Path(out_dir)
    base = mt.load_context(out_dir, scores_path)
    all_sites = pd.read_csv(out / "site_points_clean.csv")
    if not inc or "zoning_status" not in all_sites:
        return base
    sites = all_sites[all_sites.zoning_status.isin(["confirmed", "unconfirmed"])].reset_index(drop=True)
    path = base.scores_path
    if path.suffix == ".db":
        con = sqlite3.connect(path)
        sc = pd.read_sql_query("SELECT point_id, species_id, s_rule FROM site_scores", con)
        con.close()
    else:
        sc = pd.read_csv(path, usecols=["point_id", "species_id", "s_rule"])
    S = sc.pivot(index="point_id", columns="species_id", values="s_rule").reindex(index=sites.point_id, columns=base.species.species_id)
    if S.isna().any().any():
        raise ValueError("site_scores does not cover every confirmed and unconfirmed point x species pair; run score_sites.py (or use include_unzoned=False)")
    return mt.Context(sites, base.species, S.to_numpy(dtype=float), base.P, path, base.species_flags)


def confirmed_only(ctx):
    """The same context without the unconfirmed squares (rows of sites and S): equals load_context(include_unzoned=False)."""
    if "zoning_status" not in ctx.sites:
        return ctx
    keep = (ctx.sites.zoning_status == "confirmed").to_numpy()
    if keep.all():
        return ctx
    import dataclasses
    return dataclasses.replace(ctx, sites=ctx.sites[keep].reset_index(drop=True), S=ctx.S[keep])


def fetch_pair_info(scores_path, pairs):
    """{(point_id, species_id): (confidence, [source ids], [flags])} from the per-pair breakdown in site_scores."""
    info = {}
    if not pairs:
        return info
    def parse(js):
        b = json.loads(js)
        ids = sorted({i for t in b["terms"].values() for i in t["src"]})
        return ids, list(b.get("flags", [])) + [f"gate_failed:{g}" for g in b.get("gate_failed", [])]
    if Path(scores_path).suffix == ".db":
        con = sqlite3.connect(scores_path)
        for pid, sid in pairs:
            row = con.execute("SELECT confidence, breakdown_json FROM site_scores WHERE point_id=? AND species_id=?", (int(pid), int(sid))).fetchone()
            if row:
                info[(pid, sid)] = (row[0], *parse(row[1]))
        con.close()
    else:
        df = pd.read_csv(scores_path, usecols=["point_id", "species_id", "confidence", "breakdown_json"])
        want = pd.MultiIndex.from_tuples(list(pairs))
        for r in df[pd.MultiIndex.from_frame(df[["point_id", "species_id"]]).isin(want)].itertuples(index=False):
            info[(r.point_id, r.species_id)] = (r.confidence, *parse(r.breakdown_json))
    return info


def relaxed_caps(base_cfg, n_saplings, n_species, n_genera):
    """Per-species and per-genus caps that can absorb every sapling when only a few species were chosen: the smallest cap that fits, i.e. 1 / number of species
    (1 / number of genera for the genus cap) rounded up to a whole sapling. A cap is never lowered."""
    n = int(n_saplings)
    need_sp = math.ceil(n / max(n_species, 1)) / n
    need_g = math.ceil(n / max(n_genera, 1)) / n
    return max(base_cfg["max_species_share"], need_sp), max(base_cfg["max_genus_share"], need_g)


def selection_warnings(n_species):
    if n_species == 1:
        return ["Single species planting: high pest and disease risk"]
    if n_species == 2:
        return ["Only 2 species: low diversity, higher pest risk"]
    if n_species <= 4:
        return [f"Only {n_species} species: low diversity, higher pest risk"]
    return []


def _cap(species_df, blocks):
    """Trees per block of every species of species_df (NaN = no planting distance), or None in points mode."""
    return pal.block_table(species_df).capacity.to_numpy(dtype=float) if blocks else None


def _finish_blocks(ctx, area_idx, species_df, members, sp, Sm, Pm, W, feas, palette, summary, seed, method, n_trees):
    """Blocks mode: the palette gave TREES per species; blocks per species = ceil(trees / capacity); the matching assigns BLOCKS one-to-one to squares (same solver, S >= 0.50 only,
    W = S x P). Squares whose W is practically equal are tied by their distance to the centre of the chosen area (weight 1e-6 in the cost), so that the blocks sit together.
    Per species the best squares get full blocks and the worst matched square holds the remainder."""
    bt = pal.block_table(species_df).set_index("species_id")
    sids = sp.species_id.astype(int).to_numpy()
    lay = [pal.block_layout(float(bt.loc[s, "spacing_m"])) for s in sids]
    cap = np.array([l["capacity"] for l in lay], dtype=int)
    trees_q = np.array(palette["quota"], dtype=int)
    blocks_q = np.ceil(trees_q / cap).astype(int)
    xy = ctx.sites.iloc[area_idx][["utm_e", "utm_n"]].to_numpy(dtype=float)
    centre = xy.mean(axis=0)
    dist = np.hypot(xy[:, 0] - centre[0], xy[:, 1] - centre[1])
    tb = dist / dist.max() if dist.max() > 0 else np.zeros(len(dist))
    fn = {"hungarian": mt.assign_hungarian, "greedy": mt.assign_greedy}[method]
    res = fn(W, feas, blocks_q, seed, tiebreak=tb)
    pi, si = res["point_idx"], res["species_idx"]
    sites = ctx.sites.iloc[area_idx[pi]].reset_index(drop=True)
    sid = sids[si]
    info = fetch_pair_info(ctx.scores_path, set(zip(sites.point_id.astype(int), sid.astype(int))))
    bc = pal.BLOCK_CFG
    rows = []
    trees_by_k = np.zeros(len(pi), dtype=int)
    for j in range(len(members)):                                      # trees per block: best squares full, the worst matched square holds the remainder
        ks = [k for k in range(len(pi)) if si[k] == j]
        ks.sort(key=lambda k: (-float(W[pi[k], si[k]]), int(sites.point_id[k])))
        for n_, k in enumerate(ks):
            last_of_all = len(ks) == blocks_q[j] and n_ == len(ks) - 1
            trees_by_k[k] = int(trees_q[j] - (blocks_q[j] - 1) * cap[j]) if last_of_all else int(cap[j])
    for k in range(len(pi)):
        pid, spid = int(sites.point_id[k]), int(sid[k])
        conf, src_ids, flags = info.get((pid, spid), (np.nan, [], []))
        flags = list(flags)
        if palette["needs_both_sexes"][si[k]]:
            flags.append("needs_both_sexes")
        flags += ctx.species_flags.get(spid, [])
        if conf == conf and conf < CFG["low_confidence_below"]:
            flags.append("low_confidence")
        if "zoning_status" in sites and sites.zoning_status[k] == "unconfirmed":
            flags.append(UNCONFIRMED_FLAG)
        if "ground_flags" in sites and isinstance(sites.ground_flags[k], str) and sites.ground_flags[k]:
            flags += sites.ground_flags[k].split(";")
        l = lay[si[k]]
        slope = sites.slope_pct[k] if "slope_pct" in sites else np.nan
        rows.append({"point_id": pid, "lon": sites.lon[k], "lat": sites.lat[k], "utm_e": sites.utm_e[k], "utm_n": sites.utm_n[k],
                     "zone_desc": sites.zone_desc[k], "species_id": spid, "species": sp.common_name.iloc[si[k]],
                     "S": round(float(Sm[pi[k], si[k]]), 4), "P": round(float(Pm[si[k]]), 4), "W": round(float(W[pi[k], si[k]]), 4),
                     "confidence": conf, "flags": ";".join(dict.fromkeys(flags)), "site_scores_src_ids": ";".join(str(i) for i in src_ids),
                     "trees_planned": int(trees_by_k[k]), "spacing_m": l["spacing_m"], "rows": l["rows"], "trees_per_row": l["trees_per_row"], "capacity": l["capacity"],
                     "usable_side_m": l["usable_side_m"], "row_direction": l["row_direction"], "start_corner": l["start_corner"],
                     "layout_note": pal.CONTOUR_NOTE if (slope == slope and slope > bc["contour_slope_pct"]) else ""})
    plan = pd.DataFrame(rows, columns=PLAN_COLUMNS + BLOCK_COLUMNS)
    plan = plan.sort_values(["species_id", "W", "point_id"], ascending=[True, False, True]).reset_index(drop=True)
    if "ground_flags" in ctx.sites:
        summary["ground_cover"] = ground_block(plan)
    if "zoning_status" in ctx.sites and (ctx.sites.zoning_status == "unconfirmed").any():
        summary["zoning"] = zoning_block(True, plan)
    per = []
    for j in range(len(members)):
        mine = plan[plan.species_id == sids[j]]
        placed_trees = int(mine.trees_planned.sum())
        row = {"species_id": palette["species_id"][j], "species": palette["common_name"][j], "genus": str(sp.genus.iloc[j]), "quota": int(trees_q[j]),
               "share": round(palette["share"][j], 4), "placed": placed_trees, "unmatched": int(trees_q[j]) - placed_trees, "species_score": round(palette["score"][j], 4),
               "eligible_points_in_area": palette["eligible_points"][j], "needs_both_sexes": palette["needs_both_sexes"][j], "spacing_min_m": float(sp.spacing_min_m.iloc[j]),
               "blocks": int(blocks_q[j]), "blocks_placed": int(len(mine)), "spacing_m": lay[j]["spacing_m"], "rows": lay[j]["rows"], "trees_per_row": lay[j]["trees_per_row"],
               "capacity": int(cap[j])}
        summary["palette"].append(row)
        per.append({k: row[k] for k in ("species_id", "species", "quota", "placed", "blocks", "blocks_placed", "spacing_m", "rows", "trees_per_row", "capacity")})
    trees_placed = int(plan.trees_planned.sum()) if len(plan) else 0
    n_blocks = int(len(plan))
    side = bc["block_side_m"]
    summary["layout"] = {"mode": "blocks", "trees_requested": int(n_trees), "trees_placed": trees_placed, "blocks": n_blocks,
                         "hectares_used": round(n_blocks * side * side / bc["hectare_m2"], 2), "block_side_m": side, "usable_share": bc["usable_share"],
                         "usable_side_m": round(side * bc["usable_share"] ** 0.5, 2), "per_species": per,
                         "centre_utm": [round(float(centre[0]), 1), round(float(centre[1]), 1)],
                         "tiebreak": "squares whose W is practically equal are ordered by their distance to the centre of the chosen area (weight 1e-6 in the cost), so that the blocks sit together"}
    summary.update({"saplings_allocated": palette["allocated"], "saplings_unallocated": palette["unallocated"], "saplings_placed": trees_placed,
                    "saplings_unmatched": int(trees_q.sum()) - trees_placed, "blocks_placed": n_blocks, "blocks_requested": int(blocks_q.sum()),
                    "unused_candidate_points": int(len(area_idx) - len(plan)),
                    "mean_W": round(float(plan.W.mean()), 4) if len(plan) else None, "total_W": round(float(plan.W.sum()), 4),
                    "mean_W_trees": round(float((plan.W * plan.trees_planned).sum() / plan.trees_planned.sum()), 4) if trees_placed else None,
                    "spacing_check": "blocks are separate 100 m squares; inside a block the trees stand at the species spacing"})
    return plan, summary


def make_plan(ctx, purpose, n_saplings, zone=None, bbox=None, trees=None, seed=None, method="hungarian", palette_cfg=None, species_ids=None, layout_mode=None, species_trees=None):
    """Palette + matching for one purpose and area. Returns (plan DataFrame, summary dict).
    species_ids (optional): plan with ONLY these species; the per-species and per-genus caps are relaxed to the minimum needed to place every sapling and the summary says so.
    layout_mode: "blocks" (default, CFG layout_mode): n_saplings is the number of TREES, shared out per species, planted in blocks (one block per 100 m square, species spacing);
    "points": one tree per square, exactly the plan of before. species_trees (blocks mode, optional): {species_id: trees} fixed tree counts (a top-up plan restores what a plan lost)."""
    seed = CFG["seed"] if seed is None else seed
    blocks = (CFG["layout_mode"] if layout_mode is None else layout_mode) == "blocks"
    if (CFG["layout_mode"] if layout_mode is None else layout_mode) not in ("blocks", "points"):
        raise ValueError("layout_mode must be 'blocks' or 'points'")
    if purpose not in ctx.P:
        raise ValueError(f"purpose must be one of {sorted(ctx.P)}")
    in_area = mt.area_mask(ctx.sites, zone, bbox)
    keep = mt.exclusion_keep_mask(ctx.sites, trees)
    area_idx = np.where(in_area & keep)[0]
    if len(area_idx) == 0:
        raise ValueError("no legal-zone point left in the area")
    S_area, P = ctx.S[area_idx], ctx.P[purpose]
    species_df, S_sel, P_sel, selection, cfg_used = ctx.species, S_area, P, None, palette_cfg
    if species_ids:
        ids = list(dict.fromkeys(int(i) for i in species_ids))
        have = ctx.species.species_id.astype(int).tolist()
        cols = [k for k, sid_ in enumerate(have) if sid_ in set(ids)]
        if not cols:
            raise ValueError("none of the chosen species is in the species table")
        species_df, S_sel, P_sel = ctx.species.iloc[cols].reset_index(drop=True), S_area[:, cols], P[cols]
        base = dict(pal.CFG if palette_cfg is None else palette_cfg)
        n_el, n_gen = pal.count_eligible(species_df, S_sel, P_sel, base, _cap(species_df, blocks))
        cfg_used = dict(base)
        if n_el:
            cfg_used["max_species_share"], cfg_used["max_genus_share"] = relaxed_caps(base, n_saplings, n_el, n_gen)
        relaxed = {k: {"default": base[k], "used": round(cfg_used[k], 4)} for k in ("max_species_share", "max_genus_share") if cfg_used[k] > base[k] + 1e-12}
        selection = {"species_ids_requested": ids, "species_eligible_in_area": n_el, "genera_eligible_in_area": n_gen,
                     "caps": {k: {"default": base[k], "used": round(cfg_used[k], 4)} for k in ("max_species_share", "max_genus_share")}, "caps_relaxed": relaxed,
                     "caps_note": ("The per-species and per-genus caps were raised to the minimum needed to place every sapling with only these species." if relaxed
                                   else "The default per-species and per-genus caps were enough.")}
    if blocks and species_trees:
        palette = pal.fixed_palette(species_df, S_sel, P_sel, species_trees, cfg_used)
        n_saplings = int(palette["n_saplings"])
    else:
        palette = pal.build_palette(species_df, S_sel, P_sel, n_saplings, cfg_used, _cap(species_df, blocks))
    members = palette["idx"]
    summary = {"purpose": purpose, "n_saplings_requested": int(n_saplings), "method": method, "seed": seed,
               "area": {"zone": zone, "bbox": list(bbox) if bbox else None, "legal_points_in_area": int(in_area.sum()),
                        "points_dropped_near_existing_trees": int((in_area & ~keep).sum()),
                        "candidate_points_after_exclusion": int(len(area_idx))},
               "existing_trees": (f"{len(trees)} trees given; points within {mt.CFG['exclusion_radius_m']} m dropped" if trees is not None
                                  else "no trees table given: no exclusion zone applied"),
               "palette": [], "palette_common_planting_months": palette["common_months"], "palette_warnings": list(palette["warnings"]),
               "palette_excluded_species": {str(k): v for k, v in palette["excluded"].items()},
               "dioecious_species_left_out": palette["dioecious_rejected"], "limits": list(BLOCK_LIMITS if blocks else LIMITS)}
    if blocks:
        summary["layout_mode"] = "blocks"
    if selection is not None:                                          # chosen by hand: the "palette smaller than min" note does not apply; say what is left out and the diversity risk
        in_palette = {int(species_df.species_id.iloc[i]) for i in members}
        left_out = {}
        for sid_ in selection["species_ids_requested"]:
            if sid_ in in_palette or sid_ not in set(species_df.species_id.astype(int)):
                continue
            left_out[str(sid_)] = (palette["excluded"].get(sid_) or ("dioecious_species_needs_both_sexes_quota" if sid_ in palette["dioecious_rejected"]
                                                                       else "shares_no_planting_month_with_the_others_or_not_needed"))
        selection["species_ids_left_out"] = left_out
        selection["n_species_planted"] = len(in_palette)
        summary["palette_warnings"] = [w for w in summary["palette_warnings"] if not w.startswith("palette_smaller_than_min")] + selection_warnings(len(in_palette))
        if selection["caps_relaxed"] and len(in_palette):
            summary["palette_warnings"].append("Caps relaxed: " + selection["caps_note"])
        summary["species_selection"] = selection
    if not members:
        summary.update({"saplings_allocated": 0, "saplings_unallocated": int(n_saplings), "saplings_placed": 0, "saplings_unmatched": 0,
                        "unused_candidate_points": int(len(area_idx)), "mean_W": None, "total_W": 0.0})
        return pd.DataFrame(columns=PLAN_COLUMNS), summary
    sp = species_df.iloc[members]
    mt.assert_spacing_ok(sp.spacing_min_m.to_numpy())
    Sm, Pm = S_sel[:, members], P_sel[members]
    W, feas = mt.weights(Sm, Pm)
    if blocks:
        return _finish_blocks(ctx, area_idx, species_df, members, sp, Sm, Pm, W, feas, palette, summary, seed, method, int(n_saplings))
    fn = {"hungarian": mt.assign_hungarian, "greedy": mt.assign_greedy}[method]
    res = fn(W, feas, palette["quota"], seed)
    pi, si = res["point_idx"], res["species_idx"]
    sites = ctx.sites.iloc[area_idx[pi]].reset_index(drop=True)
    sid = sp.species_id.to_numpy()[si]
    info = fetch_pair_info(ctx.scores_path, set(zip(sites.point_id.astype(int), sid.astype(int))))
    rows = []
    for k in range(len(pi)):
        pid, spid = int(sites.point_id[k]), int(sid[k])
        conf, src_ids, flags = info.get((pid, spid), (np.nan, [], []))
        flags = list(flags)
        if palette["needs_both_sexes"][si[k]]:
            flags.append("needs_both_sexes")
        flags += ctx.species_flags.get(spid, [])
        if conf == conf and conf < CFG["low_confidence_below"]:
            flags.append("low_confidence")
        if "zoning_status" in sites and sites.zoning_status[k] == "unconfirmed":
            flags.append(UNCONFIRMED_FLAG)
        if "ground_flags" in sites and isinstance(sites.ground_flags[k], str) and sites.ground_flags[k]:      # satellite land cover: information only
            flags += sites.ground_flags[k].split(";")
        rows.append({"point_id": pid, "lon": sites.lon[k], "lat": sites.lat[k], "utm_e": sites.utm_e[k], "utm_n": sites.utm_n[k],
                     "zone_desc": sites.zone_desc[k], "species_id": spid, "species": sp.common_name.iloc[si[k]],
                     "S": round(float(Sm[pi[k], si[k]]), 4), "P": round(float(Pm[si[k]]), 4), "W": round(float(W[pi[k], si[k]]), 4),
                     "confidence": conf, "flags": ";".join(dict.fromkeys(flags)),
                     "site_scores_src_ids": ";".join(str(i) for i in src_ids)})
    plan = pd.DataFrame(rows, columns=PLAN_COLUMNS)
    plan = plan.sort_values(["species_id", "W", "point_id"], ascending=[True, False, True]).reset_index(drop=True)
    if "ground_flags" in ctx.sites:
        summary["ground_cover"] = ground_block(plan)
    if "zoning_status" in ctx.sites and (ctx.sites.zoning_status == "unconfirmed").any():       # only when squares outside the zoning map were available
        summary["zoning"] = zoning_block(True, plan)
    for j in range(len(members)):
        summary["palette"].append({
            "species_id": palette["species_id"][j], "species": palette["common_name"][j], "genus": str(sp.genus.iloc[j]),
            "quota": palette["quota"][j], "share": round(palette["share"][j], 4), "placed": int(res["placed"][j]),
            "unmatched": int(res["unmatched_by_species"][j]), "species_score": round(palette["score"][j], 4),
            "eligible_points_in_area": palette["eligible_points"][j], "needs_both_sexes": palette["needs_both_sexes"][j],
            "spacing_min_m": float(sp.spacing_min_m.iloc[j])})
    summary.update({"saplings_allocated": palette["allocated"], "saplings_unallocated": palette["unallocated"],
                    "saplings_placed": int(len(plan)), "saplings_unmatched": res["unmatched_saplings"],
                    "unused_candidate_points": int(len(area_idx) - len(plan)),
                    "mean_W": round(float(plan.W.mean()), 4) if len(plan) else None, "total_W": round(float(plan.W.sum()), 4),
                    "spacing_check": "every palette species has spacing_min_m < 100 m, the grid spacing, so any two grid points are far enough apart"})
    return plan, summary


def ground_block(plan):
    """The 'ground_cover' block of the plan summary: planned trees on squares that look bare, built-up or watery in satellite land cover (ESA WorldCover 2021). Information only."""
    fl = plan["flags"].fillna("").astype(str) if len(plan) else pd.Series([], dtype=str)
    w = plan["trees_planned"].astype(int) if "trees_planned" in plan and len(plan) else pd.Series(1, index=fl.index)      # blocks plans count TREES, points plans one tree per row
    by = {f: int(w[fl.str.contains(f)].sum()) for f in lcv.FLAG_NOTES}
    n = int(w[fl.str.contains("ground_")].sum())
    return {"placed_trees": int(w.sum()), "flagged_trees": n, "flagged_blocks": int(fl.str.contains("ground_").sum()), "placed_blocks": int(len(plan)), "by_flag": by, "source": lcv.SOURCE["name"],
            "note": "Trees on squares that look bare, built-up or like water in satellite land cover (2021): check them first. Information only: no score or plan depends on it."}


def zoning_block(include_unzoned, plan):
    """The 'zoning' block of the plan summary: how many placed trees stand on land outside the zoning map (flag zoning_unconfirmed)."""
    fl = plan["flags"].fillna("").astype(str) if len(plan) else pd.Series([], dtype=str)
    w = plan["trees_planned"].astype(int) if "trees_planned" in plan and len(plan) else pd.Series(1, index=fl.index)
    n_un = int(w[fl.str.contains(UNCONFIRMED_FLAG)].sum()) if len(plan) else 0
    return {"include_unzoned": bool(include_unzoned), "placed_trees": int(w.sum()), "unconfirmed_trees": n_un, "unconfirmed_blocks": int(fl.str.contains(UNCONFIRMED_FLAG).sum()),
            "note": (UNCONFIRMED_NOTE + ". " if n_un else "") + "Unconfirmed = outside every zoning polygon of our zoning file (the CLUP 2021-2031 shows this land as Forest Reserve, Watershed); these squares are scored like the others."}


PLAN_COLUMNS = ["point_id", "lon", "lat", "utm_e", "utm_n", "zone_desc", "species_id", "species", "S", "P", "W", "confidence", "flags",
                "site_scores_src_ids"]


def write_plan(out_dir, purpose, plan, summary, stamp=None):
    stamp = stamp or datetime.now().strftime(CFG["timestamp_format"])
    d = Path(out_dir) / CFG["plans_dir"]
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"plan_{purpose}_{stamp}.csv"
    plan.to_csv(f, index=False)
    s = d / f"plan_{purpose}_{stamp}_summary.json"
    s.write_text(json.dumps({**summary, "plan_file": f.name, "timestamp": stamp}, indent=2, default=str), encoding="utf-8")
    return f, s


def run_benchmark(ctx, out_dir, layout_modes=("points", "blocks")):
    """Hungarian vs greedy vs random (constraint-blind and feasible-only), same palette per purpose, whole municipality, for each layout mode.
    points: one sapling per square (the plan of before round 10a). blocks: the saplings are TREES, the palette gives trees per species, the slots are BLOCKS (ceil(trees / capacity) per species),
    one block per square; total_W is then the sum of W over blocks and `placed` counts blocks. Column layout_mode says which."""
    n = CFG["bench_saplings"]
    rows = []
    xy = ctx.sites[["utm_e", "utm_n"]].to_numpy(dtype=float)
    for layout in layout_modes:
        blocks = layout == "blocks"
        for purpose in mt.PURPOSES:
            palette = pal.build_palette(ctx.species, ctx.S, ctx.P[purpose], n, None, _cap(ctx.species, True) if blocks else None)
            m = palette["idx"]
            sp = ctx.species.iloc[m]
            mt.assert_spacing_ok(sp.spacing_min_m.to_numpy())
            Sm, Pm = ctx.S[:, m], ctx.P[purpose][m]
            W, feas = mt.weights(Sm, Pm)
            if blocks:
                cap = pal.block_table(sp).capacity.to_numpy(dtype=float)
                q = np.ceil(np.array(palette["quota"]) / cap).astype(int)
                sp_cap = g_cap = None
            else:
                q = np.array(palette["quota"])
                sp_cap = int(np.floor(pal.CFG["max_species_share"] * n + 1e-9)); g_cap = int(np.floor(pal.CFG["max_genus_share"] * n + 1e-9))
            methods = [("hungarian", lambda s_: mt.assign_hungarian(W, feas, q, s_), 1), ("greedy", lambda s_: mt.assign_greedy(W, feas, q, s_), 1),
                       ("random_feasible", lambda s_: mt.assign_random(W, feas, q, s_, True), CFG["bench_random_repeats"]),
                       ("random_blind", lambda s_: mt.assign_random(W, feas, q, s_, False), CFG["bench_random_repeats"])]
            for name, fn, reps in methods:
                vals = []
                for r in range(reps):
                    t0 = time.perf_counter(); res = fn(CFG["seed"] + r); dt = time.perf_counter() - t0
                    v = mt.check_assignment(xy, Sm, sp.spacing_min_m.to_numpy(), res, q, max_species_quota=sp_cap, max_genus_quota=g_cap,
                                            genera=sp.genus.to_numpy())
                    pi, si = res["point_idx"], res["species_idx"]
                    tw = float(W[pi, si].sum())
                    vals.append({"total_W": tw, "mean_W_per_placed": tw / len(pi) if len(pi) else np.nan, "placed": len(pi),
                                 "unmatched_saplings": res["unmatched_saplings"], "viol_below_threshold": v["below_threshold"],
                                 "viol_point_reused": v["point_reused"], "viol_over_quota": v["over_quota"] + v.get("over_species_cap", 0) + v.get("over_genus_cap", 0),
                                 "viol_spacing": v["spacing_conflicts"], "runtime_s": dt})
                d = pd.DataFrame(vals).mean()
                row = {"purpose": purpose, "layout_mode": layout, "method": name, "n_saplings": n, "n_repeats": reps, "palette_species": len(m), **d.to_dict()}
                row["violations_total"] = sum(row[k] for k in ("viol_below_threshold", "viol_point_reused", "viol_over_quota", "viol_spacing"))
                rows.append(row)
    out = pd.DataFrame(rows)
    for c in ("total_W", "mean_W_per_placed"):
        out[c] = out[c].round(4)
    out["runtime_s"] = out.runtime_s.round(4)
    f = Path(out_dir) / CFG["benchmark_file"]
    out.to_csv(f, index=False)
    return out, f


def _bbox(text):
    v = [float(x) for x in text.split(",")]
    if len(v) != 4 or v[0] >= v[2] or v[1] >= v[3]:
        raise argparse.ArgumentTypeError("bbox must be minlon,minlat,maxlon,maxlat with min < max")
    return tuple(v)


def apply_field_checks(ctx, db_path, zone=None, bbox=None):
    """Leave out the points whose latest field check is not_plantable (the same rule as POST /plan-event in api_v2.py).
    Returns (context without those points, the 'field_checks' block for the plan summary). A missing database means no checks: nothing is created or changed."""
    ids = fv.excluded_ids(fv.current_status(db_path)) if Path(db_path).is_file() else set()
    gone = ctx.sites.point_id.isin(ids).to_numpy() if ids else np.zeros(len(ctx.sites), dtype=bool)
    in_area = mt.area_mask(ctx.sites, zone, bbox)
    block = {"exclude_not_plantable": True, "excluded_points": int((gone & in_area).sum()),
             "note": "Points whose latest field check is not_plantable were left out of this plan."}
    return fv.filter_context(ctx, ids), block


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--purpose", choices=mt.PURPOSES)
    ap.add_argument("--n-saplings", type=int)
    ap.add_argument("--zone", help="zone_desc to plant in (case-insensitive)")
    ap.add_argument("--bbox", type=_bbox, help="minlon,minlat,maxlon,maxlat")
    ap.add_argument("--trees-csv", help="existing trees (utm_e,utm_n or lon,lat); points within 5 m are dropped")
    ap.add_argument("--seed", type=int, default=CFG["seed"])
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--scores", help="site_scores.db or .csv (default: <out>/scores/site_scores.db)")
    ap.add_argument("--benchmark", action="store_true", help="write matching_benchmark.csv and exit")
    ap.add_argument("--campaign-name", help="campaign name (1-80 characters), saved in the plan summary")
    ap.add_argument("--campaign-unit", help="assigned unit (up to 80 characters), saved in the plan summary")
    ap.add_argument("--species-ids", help="plan with only these species, e.g. 1,7,8 (caps are relaxed to the minimum needed)")
    ap.add_argument("--field-db", default=str(ROOT / CFG["field_db"]), help="saved field checks; not_plantable points are left out of the plan")
    ap.add_argument("--layout-mode", choices=("blocks", "points"), default=CFG["layout_mode"], help="blocks: --n-saplings is the number of TREES planted in blocks at the species spacing; points: one tree per square")
    ap.add_argument("--include-unzoned", dest="include_unzoned", action=argparse.BooleanOptionalAction, default=CFG["include_unzoned"],
                    help="also plan on squares outside the zoning map (flagged zoning_unconfirmed); --no-include-unzoned = confirmed legal-zone squares only")
    a = ap.parse_args(argv)
    ctx = load_context(a.out, a.scores, a.include_unzoned)
    if a.benchmark:
        bench, f = run_benchmark(ctx, a.out)
        print(bench.to_string(index=False)); print(f"written to {f}")
        return
    if not a.purpose or not a.n_saplings:
        ap.error("--purpose and --n-saplings are required (or use --benchmark)")
    trees = pd.read_csv(a.trees_csv) if a.trees_csv else None
    campaign = None
    if a.campaign_name is not None or a.campaign_unit is not None:
        name, unit = (a.campaign_name or "").strip(), (a.campaign_unit or "").strip()
        if not 1 <= len(name) <= 80:
            ap.error("--campaign-name is required with a campaign and must be 1 to 80 characters")
        if len(unit) > 80:
            ap.error("--campaign-unit must be at most 80 characters")
        campaign = {"name": name, "unit": unit}
    species_ids = None
    if a.species_ids:
        try:
            species_ids = list(dict.fromkeys(int(x) for x in a.species_ids.split(",") if x.strip()))
        except ValueError:
            ap.error("--species-ids must be whole numbers separated by commas, e.g. 1,7,8")
        known = set(ctx.species.species_id.astype(int))
        if not species_ids or [i for i in species_ids if i not in known]:
            ap.error(f"--species-ids: unknown species id(s) {[i for i in species_ids if i not in known] or species_ids} (valid ids: {min(known)}-{max(known)})")
    ctx, field_checks = apply_field_checks(ctx, a.field_db, a.zone, a.bbox)
    print(f"field checks: {field_checks['excluded_points']} not-plantable point(s) left out of this area")
    plan, s = make_plan(ctx, a.purpose, a.n_saplings, a.zone, a.bbox, trees, a.seed, species_ids=species_ids, layout_mode=a.layout_mode)
    if campaign:
        s["campaign"] = campaign
    s["field_checks"] = field_checks
    f, sj = write_plan(a.out, a.purpose, plan, s)
    print(f"purpose {a.purpose} | area points {s['area']['candidate_points_after_exclusion']} | {s['existing_trees']}")
    for p in s["palette"]:
        print(f"  {p['species']:<22} {p['genus']:<14} share {p['share']:.1%}  quota {p['quota']:>4}  placed {p['placed']:>4}  "
              f"unmatched {p['unmatched']:>3}" + ("  needs_both_sexes" if p["needs_both_sexes"] else ""))
    print(f"allocated {s['saplings_allocated']} / requested {s['n_saplings_requested']} | placed {s['saplings_placed']} | "
          f"unmatched {s['saplings_unmatched']} | unallocated {s['saplings_unallocated']} | unused candidate points {s['unused_candidate_points']} | "
          f"mean W {s['mean_W']}")
    for w in s["palette_warnings"]:
        print("  WARNING:", w)
    print(f"written: {f}\n         {sj}")


if __name__ == "__main__":
    main()
