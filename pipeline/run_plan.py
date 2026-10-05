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
import argparse, json, sqlite3, sys, time
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import field_verify as fv  # noqa: E402
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
}
# =====================================================================================================================

LIMITS = ("Each point is a ~100 m grid cell, so the plan places at most one tree per cell.",
          "Weights, caps and thresholds are provisional; site scores use the soft soil mode (texture mapping unverified).",
          "S comes from rules, not from field survival data.")


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


def make_plan(ctx, purpose, n_saplings, zone=None, bbox=None, trees=None, seed=None, method="hungarian", palette_cfg=None):
    """Palette + matching for one purpose and area. Returns (plan DataFrame, summary dict)."""
    seed = CFG["seed"] if seed is None else seed
    if purpose not in ctx.P:
        raise ValueError(f"purpose must be one of {sorted(ctx.P)}")
    in_area = mt.area_mask(ctx.sites, zone, bbox)
    keep = mt.exclusion_keep_mask(ctx.sites, trees)
    area_idx = np.where(in_area & keep)[0]
    if len(area_idx) == 0:
        raise ValueError("no legal-zone point left in the area")
    S_area, P = ctx.S[area_idx], ctx.P[purpose]
    palette = pal.build_palette(ctx.species, S_area, P, n_saplings, palette_cfg)
    members = palette["idx"]
    summary = {"purpose": purpose, "n_saplings_requested": int(n_saplings), "method": method, "seed": seed,
               "area": {"zone": zone, "bbox": list(bbox) if bbox else None, "legal_points_in_area": int(in_area.sum()),
                        "points_dropped_near_existing_trees": int((in_area & ~keep).sum()),
                        "candidate_points_after_exclusion": int(len(area_idx))},
               "existing_trees": (f"{len(trees)} trees given; points within {mt.CFG['exclusion_radius_m']} m dropped" if trees is not None
                                  else "no trees table given: no exclusion zone applied"),
               "palette": [], "palette_common_planting_months": palette["common_months"], "palette_warnings": list(palette["warnings"]),
               "palette_excluded_species": {str(k): v for k, v in palette["excluded"].items()},
               "dioecious_species_left_out": palette["dioecious_rejected"], "limits": list(LIMITS)}
    if not members:
        summary.update({"saplings_allocated": 0, "saplings_unallocated": int(n_saplings), "saplings_placed": 0, "saplings_unmatched": 0,
                        "unused_candidate_points": int(len(area_idx)), "mean_W": None, "total_W": 0.0})
        return pd.DataFrame(columns=PLAN_COLUMNS), summary
    sp = ctx.species.iloc[members]
    mt.assert_spacing_ok(sp.spacing_min_m.to_numpy())
    Sm, Pm = S_area[:, members], P[members]
    W, feas = mt.weights(Sm, Pm)
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
        rows.append({"point_id": pid, "lon": sites.lon[k], "lat": sites.lat[k], "utm_e": sites.utm_e[k], "utm_n": sites.utm_n[k],
                     "zone_desc": sites.zone_desc[k], "species_id": spid, "species": sp.common_name.iloc[si[k]],
                     "S": round(float(Sm[pi[k], si[k]]), 4), "P": round(float(Pm[si[k]]), 4), "W": round(float(W[pi[k], si[k]]), 4),
                     "confidence": conf, "flags": ";".join(dict.fromkeys(flags)),
                     "site_scores_src_ids": ";".join(str(i) for i in src_ids)})
    plan = pd.DataFrame(rows, columns=PLAN_COLUMNS)
    plan = plan.sort_values(["species_id", "W", "point_id"], ascending=[True, False, True]).reset_index(drop=True)
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


def run_benchmark(ctx, out_dir):
    """Hungarian vs greedy vs random (constraint-blind and feasible-only), same palette per purpose, whole municipality."""
    n = CFG["bench_saplings"]
    rows = []
    xy = ctx.sites[["utm_e", "utm_n"]].to_numpy(dtype=float)
    for purpose in mt.PURPOSES:
        palette = pal.build_palette(ctx.species, ctx.S, ctx.P[purpose], n)
        m = palette["idx"]
        sp = ctx.species.iloc[m]
        mt.assert_spacing_ok(sp.spacing_min_m.to_numpy())
        Sm, Pm = ctx.S[:, m], ctx.P[purpose][m]
        W, feas = mt.weights(Sm, Pm)
        q = np.array(palette["quota"])
        sp_cap = int(np.floor(pal.CFG["max_species_share"] * n + 1e-9)); g_cap = int(np.floor(pal.CFG["max_genus_share"] * n + 1e-9))
        methods = [("hungarian", lambda s: mt.assign_hungarian(W, feas, q, s), 1), ("greedy", lambda s: mt.assign_greedy(W, feas, q, s), 1),
                   ("random_feasible", lambda s: mt.assign_random(W, feas, q, s, True), CFG["bench_random_repeats"]),
                   ("random_blind", lambda s: mt.assign_random(W, feas, q, s, False), CFG["bench_random_repeats"])]
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
            row = {"purpose": purpose, "method": name, "n_saplings": n, "n_repeats": reps, "palette_species": len(m), **d.to_dict()}
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
    ap.add_argument("--field-db", default=str(ROOT / CFG["field_db"]), help="saved field checks; not_plantable points are left out of the plan")
    a = ap.parse_args(argv)
    ctx = mt.load_context(a.out, a.scores)
    if a.benchmark:
        bench, f = run_benchmark(ctx, a.out)
        print(bench.to_string(index=False)); print(f"written to {f}")
        return
    if not a.purpose or not a.n_saplings:
        ap.error("--purpose and --n-saplings are required (or use --benchmark)")
    trees = pd.read_csv(a.trees_csv) if a.trees_csv else None
    ctx, field_checks = apply_field_checks(ctx, a.field_db, a.zone, a.bbox)
    print(f"field checks: {field_checks['excluded_points']} not-plantable point(s) left out of this area")
    plan, s = make_plan(ctx, a.purpose, a.n_saplings, a.zone, a.bbox, trees, a.seed)
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
