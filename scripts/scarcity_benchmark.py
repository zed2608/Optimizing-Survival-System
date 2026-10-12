#!/usr/bin/env python3
"""Hungarian vs greedy vs random feasible on realistic, scarce plans (task 1 of docs/HANDOFF_2026-10-12.md).

    python scripts/scarcity_benchmark.py          # about 10 minutes; writes docs/defense/scarcity_benchmark.csv and SCARCITY_BENCHMARK.md

What it does. For each of the 15 real barangays (the area of a plan in the app), each purpose, three tightness levels and four species sets, it makes the plan the way
"I have species" mode makes it, with the production code (`run_plan.make_plan`, method "hungarian" and "greedy"), and compares them with a random feasible baseline built here
from the same matching functions (`matching.assign_random`). Production code is not changed; the only code of its own is the baseline (about 15 lines).
Main table: blocks layout with `species_counts`. Second table: points layout with `species_ids` (one tree per square, the layout of the draft). Both for S source "rf" (the app's
default) and "rules" (sensitivity). The saved scores are read, so the wetness term is in S; no planting dates are given, so the Habagat multiplier is off.

Every setting is in SETTINGS below and was fixed BEFORE the first run; nothing was tuned after looking at results.
"""
import dataclasses, subprocess, sys, time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import matching as mt  # noqa: E402
import palettes as pal  # noqa: E402
import run_plan as rp  # noqa: E402

# =====================================================================================================================
# SETTINGS: FIXED BEFORE THE FIRST RUN (round 22). Do not change them after seeing results; a change means a new, labelled run.
# =====================================================================================================================
SETTINGS = {
    "master_seed": 2026,                       # seeds the choice of species sets: np.random.default_rng([master_seed, barangay, purpose, tightness, replicate])
    "solver_seed": 42,                         # the seed of make_plan and of the matching (the project's run_plan.CFG seed)
    "random_repeats": 20,                      # random feasible is averaged over seeds solver_seed .. solver_seed + 19 (as in the existing matching benchmark)
    "tightness_targets": (0.3, 0.6, 0.9),      # target blocks (or squares) asked / squares that suit at least one chosen species
    "replicates": 4,                           # species sets per barangay x purpose x tightness; replicate r picks k = 2 + r species (2, 3, 4, 5)
    "s_sources": ("rf", "rules"),              # rf = main (the app's default), rules = sensitivity
    "layouts": ("blocks", "points"),           # blocks + species_counts = main table; points + species_ids = second table
    "purposes": ("urban", "planting", "watershed"),
    "max_trees": 2000,                         # the limit of POST /plan-event: if a case would ask for more, the blocks asked are reduced one at a time until it fits
    "area": "every one of the 15 barangays, whole barangay, include_unzoned on (the app's default), no field-check exclusions, no planting dates (Habagat off)",
    "species_choice": "k species drawn at random, without replacement, from the species that may enter a palette in that area and purpose (palettes.eligible_pool)",
    "blocks_counts": "blocks asked B = max(k, round(tightness x U)), split as evenly as possible over the k species; trees of a species = its blocks x its trees per full block",
    "points_count": "trees asked N = max(k, round(tightness x U)), at most max_trees; the palette shares them out (caps relaxed as for chosen species)",
    "U": "number of squares with S >= 0.50 for at least one of the chosen species",
}
OUT_DIR = ROOT / "docs" / "defense"
S_MIN = mt.CFG["s_min"]


# ---------------------------------------------------------------------------------------------------- the world (data of the app)
def load_world(s_source):
    """The data object of the API (same loader, same barangay join) with S from the given source. Raises if the app would have fallen back to the other source."""
    import api_v2
    cfg = dict(api_v2.API_CFG)
    cfg["s_source"] = s_source
    d = api_v2.load_data(cfg)
    if d.ctx.s_source != s_source:
        raise RuntimeError(f"S source '{s_source}' is not available (the context fell back to '{d.ctx.s_source}'): {d.ctx.s_warning}")
    if "w_mult" in d.ctx.sites:
        raise RuntimeError("the context carries a Habagat multiplier; the benchmark is meant to run without planting dates")
    return d


def area_context(d, b):
    """The planning context of one barangay (the same restriction as api_v2.plan_scope)."""
    mask = d.point_barangay == b
    if not mask.any():
        return None
    return dataclasses.replace(d.ctx, sites=d.ctx.sites[mask].reset_index(drop=True), S=d.ctx.S[mask])


# ---------------------------------------------------------------------------------------------------- one case
def trees_formula(placed_by_species, blocks_q, trees_q, cap):
    """Trees planted when `placed_by_species` blocks of each species were placed: all blocks placed = the trees asked; otherwise every placed block is a full block."""
    placed_by_species, blocks_q, trees_q, cap = (np.asarray(x) for x in (placed_by_species, blocks_q, trees_q, cap))
    return int(np.where(placed_by_species == blocks_q, trees_q, placed_by_species * cap).sum())


def split_blocks(B, k, caps):
    base, extra = divmod(int(B), int(k))
    b = [base + (1 if i < extra else 0) for i in range(k)]
    return b, [int(bi * int(c)) for bi, c in zip(b, caps)]


def make_case(sub, purpose, tightness, k, rng, layout):
    """The species set and the amount asked of one plan, or (None, reason). Deterministic given rng."""
    cap_all = pal.block_table(sub.species).capacity.to_numpy(dtype=float)
    st = pal.species_stats(sub.S, sub.P[purpose], S_MIN)
    pool, _ = pal.eligible_pool(sub.species, st, [pal.parse_months(v) for v in sub.species.planting_months], pal.CFG, cap_all if layout == "blocks" else None)
    if len(pool) < k:
        return None, f"only {len(pool)} species may enter a palette here (k = {k})"
    cols = sorted(int(c) for c in rng.choice(pool, k, replace=False))
    U = int((sub.S[:, cols] >= S_MIN).any(axis=1).sum())
    if layout == "points":
        N = min(SETTINGS["max_trees"], max(k, int(round(tightness * U))))
        return {"cols": cols, "U": U, "asked": N, "blocks_asked": None, "trees_q": None}, None
    caps = [int(cap_all[c]) for c in cols]
    B = max(k, int(round(tightness * U)))
    while True:
        b, trees = split_blocks(B, k, caps)
        if sum(trees) <= SETTINGS["max_trees"]:
            break
        if B <= k:
            return None, f"even one block per species is over {SETTINGS['max_trees']} trees"
        B -= 1
    return {"cols": cols, "U": U, "asked": int(sum(trees)), "blocks_asked": int(sum(b)), "blocks_q": b, "trees_q": trees, "caps": caps}, None


def _time(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def evaluate_matching(W, feas, quotas, seed, tiebreak, trees_info=None):
    """Hungarian, greedy and random feasible on the same matrix. Returns {method: dict}. trees_info = (blocks_q, trees_q, cap) in blocks mode, else None (one tree per square).
    The random baseline is the mean over SETTINGS['random_repeats'] seeds."""
    def tot(res):
        pi, si = res["point_idx"], res["species_idx"]
        return float(W[pi, si].sum()) if len(pi) else 0.0

    def trees(res):
        return trees_formula(res["placed"], *trees_info) if trees_info else int(len(res["point_idx"]))
    out = {}
    for name, fn in (("hungarian", lambda: mt.assign_hungarian(W, feas, quotas, seed, tiebreak=tiebreak)),
                     ("greedy", lambda: mt.assign_greedy(W, feas, quotas, seed, tiebreak=tiebreak))):
        res, dt = _time(fn)
        out[name] = {"placed_blocks": int(len(res["point_idx"])), "placed_trees": trees(res), "total_W": tot(res), "solver_seconds": dt}
    reps = []
    for r in range(SETTINGS["random_repeats"]):
        res, dt = _time(lambda r=r: mt.assign_random(W, feas, quotas, seed + r, True))
        reps.append((len(res["point_idx"]), trees(res), tot(res), dt))
    m = np.mean(reps, axis=0)
    out["random_feasible"] = {"placed_blocks": float(m[0]), "placed_trees": float(m[1]), "total_W": float(m[2]), "solver_seconds": float(m[3])}
    return out


def run_case(sub, purpose, case, layout, seed):
    """One plan, all methods. Returns (rows, error). Hungarian and greedy numbers come from the production `make_plan`; the same matrix is rebuilt here for the random baseline,
    for the solver-only timing and as a cross-check (`check_ok`: the rebuilt matching reproduces make_plan's placed blocks, trees and total W)."""
    ids = sub.species.species_id.astype(int).to_numpy()
    cols = case["cols"]
    P = np.asarray(sub.P[purpose], dtype=float)
    prod, times = {}, {}
    for method in ("hungarian", "greedy"):
        t0 = time.perf_counter()
        try:
            if layout == "blocks":
                counts = {int(ids[c]): int(t) for c, t in zip(cols, case["trees_q"])}
                plan, summ = rp.make_plan(sub, purpose, case["asked"], seed=seed, method=method, layout_mode="blocks", species_counts=counts)
            else:
                plan, summ = rp.make_plan(sub, purpose, case["asked"], seed=seed, method=method, layout_mode="points", species_ids=[int(ids[c]) for c in cols])
        except ValueError as e:
            return None, str(e)
        times[method] = time.perf_counter() - t0
        if not summ["palette"]:
            return None, "make_plan returned an empty palette"
        prod[method] = (plan, summ)
    # rebuild the matrix exactly as make_plan does
    xy = sub.sites[["utm_e", "utm_n"]].to_numpy(dtype=float)
    if layout == "blocks":
        mcols, blocks_q, trees_q, cap = cols, np.array(case["blocks_q"]), np.array(case["trees_q"]), np.array(case["caps"])
        dist = np.hypot(xy[:, 0] - xy[:, 0].mean(), xy[:, 1] - xy[:, 1].mean())
        tb = dist / dist.max() if dist.max() > 0 else np.zeros(len(dist))
        quotas, info = blocks_q, (blocks_q, trees_q, cap)
    else:
        pal_rows = prod["hungarian"][1]["palette"]
        index = {int(s): j for j, s in enumerate(ids)}
        mcols = [index[int(p["species_id"])] for p in pal_rows]
        quotas, tb, info = [int(p["quota"]) for p in pal_rows], None, None
    W, feas = mt.weights(sub.S[:, mcols], P[mcols])
    res = evaluate_matching(W, feas, quotas, seed, tb, info)
    rows = []
    for method in ("hungarian", "greedy", "random_feasible"):
        r = dict(res[method])
        if method != "random_feasible":
            plan, summ = prod[method]
            if layout == "blocks":
                pb, pt, tw = int(summ["blocks_placed"]), int(summ["layout"]["trees_placed"]), float(summ["total_W"])
            else:
                pb, pt, tw = int(len(plan)), int(len(plan)), float(plan.W.sum()) if len(plan) else 0.0
            bound = 5e-5 * max(1, pb) + 1e-9          # make_plan rounds the W of every planted row to 4 decimals, so its total can differ from the exact sum by up to 5e-5 per row
            r["check_ok"] = bool(pb == r["placed_blocks"] and pt == r["placed_trees"] and abs(tw - r["total_W"]) <= bound)
            r["total_W_production"] = tw               # the production total (sum of rounded rows); `total_W` stays the exact rebuilt sum, which is what the methods are compared on
            r["plan_seconds"] = times[method]
        else:
            r["check_ok"], r["plan_seconds"] = np.nan, np.nan
        r["method"] = method
        rows.append(r)
    extra = {"trees_asked": int(case["asked"]) if layout == "points" else int(sum(case["trees_q"])),
             "blocks_asked": case["blocks_asked"] if layout == "blocks" else int(sum(quotas)),
             "allocated": int(prod["hungarian"][1].get("saplings_allocated", case["asked"]))}
    for r in rows:
        r.update(extra)
    return rows, None


# ---------------------------------------------------------------------------------------------------- the whole benchmark
def run_benchmark(worlds=None, log=print):
    """All plans for all S sources and layouts. worlds = {s_source: data object} (loaded when None). Returns a DataFrame, one row per plan x method."""
    S = SETTINGS
    rows = []
    for s_source in S["s_sources"]:
        d = worlds[s_source] if worlds else load_world(s_source)
        for layout in S["layouts"]:
            t0 = time.time()
            for b, bname in enumerate(d.barangay_names):
                sub = area_context(d, b)
                if sub is None:
                    continue
                for pi, purpose in enumerate(S["purposes"]):
                    for ti, tau in enumerate(S["tightness_targets"]):
                        for r in range(S["replicates"]):
                            rng = np.random.default_rng([S["master_seed"], b, pi, ti, r])
                            k = 2 + r
                            base = {"s_source": s_source, "layout": layout, "barangay": d.barangay_display[b], "squares_in_area": len(sub.sites), "purpose": purpose,
                                    "tightness_target": tau, "replicate": r, "k_species": k}
                            case, why = make_case(sub, purpose, tau, k, rng, layout)
                            if case is None:
                                rows.append({**base, "method": "(none)", "status": "skipped: " + why})
                                continue
                            res, err = run_case(sub, purpose, case, layout, S["solver_seed"])
                            names = ";".join(str(sub.species.common_name.iloc[c]) for c in case["cols"])
                            info = {**base, "species_ids": ";".join(str(int(sub.species.species_id.iloc[c])) for c in case["cols"]), "species": names, "squares_suiting_any": case["U"]}
                            if res is None:
                                rows.append({**info, "method": "(none)", "status": "skipped: " + err})
                                continue
                            for x in res:
                                rows.append({**info, **x, "status": "ok", "tightness_achieved": round(x["blocks_asked"] / case["U"], 4) if layout == "blocks"
                                             else round(x["trees_asked"] / case["U"], 4)})
            log(f"  {s_source} / {layout}: {time.time() - t0:.0f} s, rows so far {len(rows)}")
    df = pd.DataFrame(rows)
    df["stranded_blocks"] = df.blocks_asked - df.placed_blocks
    df["stranded_trees"] = df.trees_asked - df.placed_trees
    df["mean_W_per_block"] = df.total_W / df.placed_blocks.where(df.placed_blocks > 0)
    return df


# ---------------------------------------------------------------------------------------------------- summary and report
def summarise(df, s_source, layout):
    """The numbers of one table (one S source, one layout), from the long table."""
    ok = df[(df.status == "ok") & (df.s_source == s_source) & (df.layout == layout)]
    wide = {m: ok[ok.method == m].set_index(["barangay", "purpose", "tightness_target", "replicate"]) for m in ("hungarian", "greedy", "random_feasible")}
    h, g, r = wide["hungarian"], wide["greedy"], wide["random_feasible"]
    n = len(h)
    s = {"plans": n}
    if n == 0:
        return s
    s["trees_asked"] = int(h.trees_asked.sum())
    for name, x in (("hungarian", h), ("greedy", g)):
        s["placed_trees_" + name], s["stranded_trees_" + name] = int(x.placed_trees.sum()), int(x.stranded_trees.sum())
    s["placed_trees_random"], s["stranded_trees_random"] = float(r.placed_trees.sum()), float(r.stranded_trees.sum())
    s["greedy_places_fewer_blocks"] = int((g.placed_blocks < h.placed_blocks).sum())
    s["hungarian_places_fewer_blocks"] = int((h.placed_blocks < g.placed_blocks).sum())
    s["greedy_strands_more_trees"] = int((g.stranded_trees > h.stranded_trees).sum())
    s["same_blocks"] = int((g.placed_blocks == h.placed_blocks).sum())
    same = h.placed_blocks == g.placed_blocks
    gap = ((h.total_W - g.total_W) / h.total_W.where(h.total_W > 0) * 100)[same]
    s["same_blocks_greedy_lower_W"] = int((gap > 1e-6).sum())
    s["same_blocks_greedy_higher_W"] = int((gap < -1e-6).sum())
    s["gap_pct_median_when_lower"] = float(gap[gap > 1e-6].median()) if (gap > 1e-6).any() else 0.0
    s["gap_pct_max"] = float(gap.max()) if len(gap) else 0.0
    s["max_stranded_trees_greedy_in_a_plan"] = int(g.stranded_trees.max())
    s["max_stranded_blocks_greedy_in_a_plan"] = int(g.stranded_blocks.max())
    s["median_solver_ms"] = {k: round(float(x.solver_seconds.median()) * 1000, 2) for k, x in (("hungarian", h), ("greedy", g), ("random_feasible", r))}
    s["median_plan_ms"] = {k: round(float(x.plan_seconds.median()) * 1000, 1) for k, x in (("hungarian", h), ("greedy", g))}
    s["check_ok"] = f"{int(h.check_ok.sum() + g.check_ok.sum())} of {2 * n}"
    s["tightness_achieved_quantiles"] = {q: round(float(h.tightness_achieved.quantile(q)), 2) for q in (0.1, 0.5, 0.9)}
    s["plans_with_unavoidable_stranding"] = int((h.stranded_blocks > 0).sum())
    by = []
    for tau, idx in h.groupby("tightness_target").groups.items():
        by.append({"tightness_target": tau, "plans": len(idx), "greedy_places_fewer_blocks": int((g.loc[idx].placed_blocks < h.loc[idx].placed_blocks).sum()),
                   "hungarian_stranded_trees": int(h.loc[idx].stranded_trees.sum()), "greedy_stranded_trees": int(g.loc[idx].stranded_trees.sum()),
                   "random_stranded_trees": round(float(r.loc[idx].stranded_trees.sum()), 1)})
    s["by_tightness"] = pd.DataFrame(by)
    return s


def git_info():
    def run(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = [l for l in run("status", "--porcelain").splitlines() if not l.startswith("??")]
    return run("rev-parse", "--short", "HEAD"), run("branch", "--show-current"), bool(dirty)


def setup_facts(worlds):
    rel = (ROOT / "data/processed/dataset_release.txt").read_text(encoding="utf-8")
    h12 = next((l.split(":")[-1].split()[0] for l in rel.splitlines() if "combined hash" in l), "UNKNOWN")
    pt = pd.read_csv(ROOT / "data/processed/scores/pair_table.csv.gz", usecols=["water_dist_m"])
    sha, branch, dirty = git_info()
    return {"release_hash": h12, "wetness_share_known": float(pt.water_dist_m.notna().mean()), "git_commit": sha, "git_branch": branch, "git_dirty": dirty, "date": date.today().isoformat(),
            "squares": {k: int(len(w.ctx.sites)) for k, w in worlds.items()}, "s_used": {k: w.ctx.s_source for k, w in worlds.items()}}


def table_md(s):
    if s.get("plans", 0) == 0:
        return "(no plans)\n"
    rows = [("Plans made", s["plans"]), ("Trees asked", s["trees_asked"]),
            ("Trees placed: Hungarian / greedy / random feasible (mean)", f"{s['placed_trees_hungarian']} / {s['placed_trees_greedy']} / {s['placed_trees_random']:.0f}"),
            ("Trees stranded (no spot): Hungarian / greedy / random feasible", f"{s['stranded_trees_hungarian']} / {s['stranded_trees_greedy']} / {s['stranded_trees_random']:.0f}"),
            ("Plans where greedy places fewer blocks than Hungarian", s["greedy_places_fewer_blocks"]),
            ("Plans where Hungarian places fewer blocks than greedy (must be 0)", s["hungarian_places_fewer_blocks"]),
            ("Largest number of trees greedy strands in one plan", s["max_stranded_trees_greedy_in_a_plan"]),
            ("Plans where both place the same number of blocks", s["same_blocks"]),
            ("... of those, greedy total W lower than Hungarian / higher", f"{s['same_blocks_greedy_lower_W']} / {s['same_blocks_greedy_higher_W']}"),
            ("... largest total-W gap (greedy below Hungarian)", f"{s['gap_pct_max']:.2f}%"),
            ("Plans where even Hungarian cannot place everything (too few suitable squares)", s["plans_with_unavoidable_stranding"]),
            ("Achieved tightness (blocks or trees asked / suitable squares), 10th / 50th / 90th percentile", " / ".join(str(s["tightness_achieved_quantiles"][q]) for q in (0.1, 0.5, 0.9))),
            ("Median solver time per plan, ms: Hungarian / greedy / random feasible", " / ".join(str(s["median_solver_ms"][k]) for k in ("hungarian", "greedy", "random_feasible"))),
            ("Median time of the whole make_plan call, ms: Hungarian / greedy", " / ".join(str(s["median_plan_ms"][k]) for k in ("hungarian", "greedy"))),
            ("Cross-check (rebuilt matching reproduces make_plan)", s["check_ok"])]
    out = "| Measure | Value |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows) + "\n\nBy the tightness level that was asked for:\n\n"
    out += "| Target tightness | Plans | Plans where greedy places fewer blocks | Trees stranded: Hungarian | greedy | random feasible |\n|---|---|---|---|---|---|\n"
    out += "\n".join(f"| {r.tightness_target} | {r.plans} | {r.greedy_places_fewer_blocks} | {r.hungarian_stranded_trees} | {r.greedy_stranded_trees} | {r.random_stranded_trees} |"
                     for r in s["by_tightness"].itertuples()) + "\n"
    return out


def write_outputs(df, facts, out_dir=OUT_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["s_source", "layout", "barangay", "squares_in_area", "purpose", "tightness_target", "replicate", "k_species", "species_ids", "species", "squares_suiting_any", "method", "status",
            "trees_asked", "blocks_asked", "tightness_achieved", "placed_blocks", "placed_trees", "stranded_blocks", "stranded_trees", "total_W", "mean_W_per_block",
            "plan_seconds", "solver_seconds", "check_ok", "total_W_production"]
    d = df.copy()
    for c in ("total_W", "mean_W_per_block", "plan_seconds", "solver_seconds", "placed_blocks", "placed_trees", "stranded_blocks", "stranded_trees"):
        d[c] = d[c].round(6)
    d[[c for c in cols if c in d.columns]].to_csv(out_dir / "scarcity_benchmark.csv", index=False)
    S = SETTINGS
    skipped = df[df.status != "ok"]
    md = ["# Scarcity benchmark: Hungarian vs greedy vs random feasible (task 1 of the 12 Oct handoff)", "",
          "Generated by `scripts/scarcity_benchmark.py`; every plan is in `scarcity_benchmark.csv`. The settings below were fixed before the first run and were not changed after seeing results.", "",
          "## Settings (fixed before the first run)", ""]
    md += [f"- **{k}**: {v}" for k, v in S.items()]
    md += ["", "## Setup (one place)", "",
           f"- **S source**: main = `rf` (the Random Forest `s_prob`, the app's default), sensitivity = `rules` (`s_rule`). Used in this run: {facts['s_used']}.",
           f"- **Wetness term**: included. The saved scores already contain it (distance to creeks and rivers is known for {facts['wetness_share_known']:.0%} of the pairs of the pair table).",
           "- **Habagat multiplier**: OFF (no planting dates are given, so no square gets `w_mult`; the script stops if it finds one).",
           "- **Slope rule**: graded (the saved scores' mode). **Zoning**: confirmed + unconfirmed squares (the app's default), 78 excluded squares never scored. No field-check exclusions, no season filter.",
           f"- **Release hash**: {facts['release_hash']} (v1.0-review). **Squares in the planning context**: {facts['squares']}.",
           f"- **Git**: branch `{facts['git_branch']}`, HEAD `{facts['git_commit']}` plus uncommitted work (this script, its test and these outputs). **Date**: {facts['date']}.",
           "- **Code**: production `run_plan.make_plan` for Hungarian and greedy (blocks: `species_counts`; points: `species_ids`); the random feasible baseline is the project's `matching.assign_random` on the same matrix, rebuilt in the script. Production code was not modified.",
           f"- **Plans skipped** (not creatable under the rules above): {len(skipped)} rows; reasons are in the CSV (`status`).", "",
           "## How to read the tables", "",
           "Tightness = blocks (or trees, in points layout) asked / squares that suit at least one chosen species. A plan is *scarce* when that number is high. 'Stranded' = asked but not placed. "
           "Total W is compared only among plans where both methods place the same number of blocks; plans where they place different numbers are counted separately, because Hungarian first places as many as possible and only then maximizes W.", ""]
    for s_source in S["s_sources"]:
        for layout in S["layouts"]:
            title = {("rf", "blocks"): "Main table: S source rf, blocks layout with species_counts",
                     ("rf", "points"): "Second table: S source rf, points layout with species_ids (one tree per square)",
                     ("rules", "blocks"): "Sensitivity: S source rules, blocks layout with species_counts",
                     ("rules", "points"): "Sensitivity: S source rules, points layout with species_ids"}[(s_source, layout)]
            md += [f"## {title}", "", table_md(summarise(df, s_source, layout))]
    (out_dir / "SCARCITY_BENCHMARK.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main():
    t0 = time.time()
    print("loading the data of the app for both S sources ...", flush=True)
    worlds = {s: load_world(s) for s in SETTINGS["s_sources"]}
    df = run_benchmark(worlds)
    write_outputs(df, setup_facts(worlds))
    ok = df[df.status == "ok"]
    print(f"done in {time.time() - t0:.0f} s: {len(ok) // 3} plans, {len(df) - len(ok)} skipped rows; wrote docs/defense/scarcity_benchmark.csv and SCARCITY_BENCHMARK.md")
    print("cross-check failures:", int((ok.check_ok == False).sum()))  # noqa: E712


if __name__ == "__main__":
    main()
