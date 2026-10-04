#!/usr/bin/env python3
"""
palettes.py - Day 3 part 1a: choose the mix of species (the palette) for an area and a purpose.

Library module (used by run_plan.py and matching.py). Inputs are plain arrays so it can be tested without files:
    species  DataFrame, one row per species, row i  <->  column i of S
    S        (n_points x n_species) site suitability of every point of the area (from site_scores)
    P        (n_species,) purpose fitness of the chosen purpose (from purpose_scores)

Species score  = mean of W = S x P over the area's points where S >= S_MIN  x  share of the area's points where S >= S_MIN.
Palette value  = sum over members of quota_i x score_i / n_saplings   (saplings that cannot be placed contribute 0).
Selection      = greedy: add the species that raises the value most (the first PALETTE_MIN additions are forced), stop at
                 PALETTE_MAX or when nothing improves; then swaps: replace one member by one non-member while the value rises.
Quotas         = saplings shared out in proportion to the species scores ("progressive filling"), never above the per-species
                 cap, the per-genus cap or the number of points where the species is eligible; whole numbers by largest remainder.
Rules          (1) all members share at least one planting month (species without planting_months are not eligible);
                 (2) a dioecious species needs a quota >= DIOECIOUS_MIN_QUOTA and carries the flag needs_both_sexes, otherwise it
                 is left out; (3) the share of saplings per species is returned (quota / n_saplings).
Note: with PALETTE_MAX_SPECIES_SHARE = 20% at least 5 species are needed to absorb every sapling, and the older plan's 10% cap
would need at least 10 species, which is why 20% (provisional) is the default here.
"""
import numpy as np
import pandas as pd

# =====================================================================================================================
# CONFIG - every tunable number lives here. ALL PROVISIONAL until the agriculturist / LGU planners sign off.
# =====================================================================================================================
CFG = {
    "s_min": 0.50,                  # a point is eligible for a species when S >= this (same cut as W = S x P if S >= 0.50)
    "palette_min": 6,               # smallest palette we try to build (provisional)
    "palette_max": 10,              # largest palette (provisional)
    "max_species_share": 0.20,      # max fraction of the saplings per species (provisional; the older plan said 10%)
    "max_genus_share": 0.30,        # max fraction of the saplings per genus (provisional)
    "dioecious_min_quota": 2,       # a dioecious species needs at least this many saplings (both sexes)
    "swap_max_rounds": 20,          # upper bound on swap passes
    "grid_spacing_m": 100.0,        # the site grid is ~100 m; species with spacing_min_m >= this are not used
    "eps": 1e-9,
}
# =====================================================================================================================


def parse_months(value):
    """'5;6;7' -> {5, 6, 7}; missing -> None (never guessed)."""
    if value is None or (isinstance(value, float) and np.isnan(value)) or str(value).strip() == "":
        return None
    return {int(x) for x in str(value).replace(",", ";").split(";") if x.strip()}


def species_stats(S, P, s_min):
    """Per species: eligible point count and share, mean W over eligible points, and the species score."""
    S = np.asarray(S, dtype=float); P = np.asarray(P, dtype=float)
    n_pts = S.shape[0]
    elig = S >= s_min
    n_el = elig.sum(axis=0)
    W = np.where(elig, S * P[None, :], 0.0)
    mean_w = np.divide(W.sum(axis=0), n_el, out=np.zeros(S.shape[1]), where=n_el > 0)
    share = n_el / n_pts if n_pts else np.zeros(S.shape[1])
    return pd.DataFrame({"n_eligible": n_el, "eligible_share": share, "mean_w": mean_w, "score": mean_w * share})


def allocate_quotas(scores, genera, capacity, n, max_species_share, max_genus_share, eps=1e-9):
    """
    Integer quotas for the members (same order as `scores`). Progressive filling: every active species grows in proportion to
    its score until it hits its cap (min of share cap and eligible-point capacity) or its genus hits the genus cap; the rest
    keeps growing. The total is n unless the caps cannot absorb n saplings (then it is smaller and the gap is reported).
    """
    scores = np.asarray(scores, dtype=float); k = len(scores)
    sp_cap = np.minimum(np.floor(max_species_share * n + eps), np.asarray(capacity, dtype=float))
    g_cap = np.floor(max_genus_share * n + eps)
    genera = np.asarray(genera, dtype=object)
    groups = {g: np.where(genera == g)[0] for g in dict.fromkeys(genera)}
    q = np.zeros(k); active = (scores > 0) & (sp_cap > 0); remaining = float(n)
    while remaining > eps and active.any():
        w = np.where(active, scores, 0.0)
        lam = remaining / w.sum()
        lam = min(lam, np.min((sp_cap - q)[active] / w[active]))
        for g, idx in groups.items():
            wg = w[idx].sum()
            if wg > 0:
                lam = min(lam, (g_cap - q[idx].sum()) / wg)
        lam = max(lam, 0.0)
        q += lam * w; remaining -= lam * w.sum()
        active &= (sp_cap - q) > eps
        for g, idx in groups.items():
            if g_cap - q[idx].sum() <= eps:
                active[idx] = False
    total = int(round(q.sum()))
    base = np.floor(q + eps).astype(int)
    left = total - int(base.sum())
    frac = q - base
    sp_cap_i = sp_cap.astype(int)
    while left > 0:
        order = np.argsort(-frac, kind="stable")
        placed = False
        for i in order:
            g_room = int(g_cap) - int(base[groups[genera[i]]].sum())
            if base[i] < sp_cap_i[i] and g_room > 0:
                base[i] += 1; frac[i] = -1.0; left -= 1; placed = True
                break
        if not placed:
            break
    return base


def _common_months(month_sets):
    out = None
    for m in month_sets:
        out = set(m) if out is None else out & m
    return out if out is not None else set()


def build_palette(species, S, P, n_saplings, cfg=None):
    """Choose the palette. Returns a dict (see keys at the end); never hides what it dropped."""
    c = CFG if cfg is None else cfg
    species = species.reset_index(drop=True)
    S = np.asarray(S, dtype=float); P = np.asarray(P, dtype=float)
    n = int(n_saplings)
    if n < 1:
        raise ValueError("n_saplings must be >= 1")
    st = species_stats(S, P, c["s_min"])
    months = [parse_months(v) for v in species.planting_months]
    genus = species.genus.fillna("?").to_numpy(dtype=object)
    dioecious = species.is_dioecious.fillna(False).astype(bool).to_numpy()
    excluded = {}
    pool = []
    for i, sid in enumerate(species.species_id):
        if st.n_eligible[i] == 0 or st.score[i] <= 0:
            excluded[int(sid)] = "no_eligible_points_in_area"
        elif months[i] is None:
            excluded[int(sid)] = "planting_months_missing"
        elif not species.spacing_min_m.iloc[i] < c["grid_spacing_m"]:
            excluded[int(sid)] = "spacing_not_below_grid_spacing"
        else:
            pool.append(i)
    rejected_dioecious = set()

    def evaluate(members):
        """(value, quotas) of a member set, or (-inf, None) if a rule is broken."""
        if _common_months([months[i] for i in members]) == set():
            return -np.inf, None
        q = allocate_quotas(st.score.to_numpy()[members], genus[members], st.n_eligible.to_numpy()[members], n,
                            c["max_species_share"], c["max_genus_share"], c["eps"])
        bad = [m for m, qi in zip(members, q) if dioecious[m] and qi < c["dioecious_min_quota"]]
        if bad:
            rejected_dioecious.update(int(species.species_id.iloc[m]) for m in bad)
            return -np.inf, None
        return float((q * st.score.to_numpy()[members]).sum() / n), q

    members, value = [], 0.0
    while len(members) < c["palette_max"]:
        best = None
        for i in pool:
            if i in members:
                continue
            v, _ = evaluate(members + [i])
            if np.isfinite(v) and (best is None or v > best[1] + c["eps"]):
                best = (i, v)
        if best is None:
            break
        if len(members) >= c["palette_min"] and best[1] <= value + c["eps"]:
            break
        members.append(best[0]); value = best[1]
    for _ in range(c["swap_max_rounds"]):                             # swaps: one out, one in, while the value rises
        best = None
        for out_i in members:
            for in_i in pool:
                if in_i in members:
                    continue
                trial = [in_i if m == out_i else m for m in members]
                v, _ = evaluate(trial)
                if np.isfinite(v) and v > value + c["eps"] and (best is None or v > best[0]):
                    best = (v, trial)
        if best is None:
            break
        value, members = best
    warnings = []
    if len(members) < c["palette_min"]:
        warnings.append(f"palette_smaller_than_min: {len(members)} species (min {c['palette_min']}) satisfy the rules for this area")
    if not members:
        return {"idx": [], "species_id": [], "common_name": [], "quota": [], "share": [], "score": [], "needs_both_sexes": [],
                "common_months": [], "excluded": excluded, "dioecious_rejected": sorted(rejected_dioecious),
                "warnings": warnings + ["no species can be placed in this area"], "objective": 0.0, "n_saplings": n,
                "allocated": 0, "unallocated": n, "eligible_points": []}
    value, q = evaluate(members)
    rejected_dioecious -= {int(species.species_id.iloc[i]) for i in members}   # only species that stayed out
    order = sorted(range(len(members)), key=lambda j: (-q[j], -st.score.to_numpy()[members[j]]))
    members = [members[j] for j in order]; q = q[order]
    allocated = int(q.sum())
    if allocated < n:
        warnings.append(f"caps_cannot_absorb_all_saplings: {allocated} of {n} saplings allocated (per-species/genus caps or eligible points)")
    return {
        "idx": members, "species_id": [int(species.species_id.iloc[i]) for i in members],
        "common_name": [str(species.common_name.iloc[i]) for i in members],
        "quota": [int(x) for x in q], "share": [float(x) / n for x in q],
        "score": [float(st.score.iloc[i]) for i in members], "eligible_points": [int(st.n_eligible.iloc[i]) for i in members],
        "needs_both_sexes": [bool(dioecious[i]) for i in members],
        "common_months": sorted(_common_months([months[i] for i in members])),
        "excluded": excluded, "dioecious_rejected": sorted(rejected_dioecious), "warnings": warnings,
        "objective": float(value), "n_saplings": n, "allocated": allocated, "unallocated": n - allocated,
    }
