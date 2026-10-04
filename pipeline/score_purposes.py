#!/usr/bin/env python3
"""
score_purposes.py - Day 2 task 2: purpose fitness P(species, purpose) in [0, 1] for urban / planting / watershed.

    python pipeline/score_purposes.py --out data/processed [--weights data/config/purpose_weights.csv]

Reads  data/config/purpose_weights.csv (PROVISIONAL weights; each purpose sums to 1.00), <out>/species_clean.csv,
       <out>/species_sources.csv, <out>/tag_maps_urban.csv (provisional tag -> purpose map).
Writes <out>/purpose_scores.csv       one row per species and purpose: P, rank, confidence, per-criterion breakdown_json
       <out>/purpose_sensitivity.csv  rank range of every species when the criterion weights move by +-PERTURBATION

P = sum over criteria of weight x criterion score. A criterion score is the mean of its component scores (one per species
column named in the weights file). Component rules (scale 0..1): ordinal levels, min-max across the 45 species, flags,
tag present = 1 / absent = 0, and a few text rules. A value that is missing, or that a text rule cannot read, scores
NEUTRAL_SCORE (0.5), is marked missing in the breakdown and lowers the confidence. Nothing is guessed.
"""
import argparse, itertools, json, re
from pathlib import Path
import numpy as np
import pandas as pd

# =====================================================================================================================
# CONFIG - every tunable number and scoring rule lives here. All PROVISIONAL until the agriculturist signs off.
# =====================================================================================================================
PERTURBATION = 0.25                 # sensitivity: every weight is moved by +-25%
NEUTRAL_SCORE = 0.5                 # score for a missing / unreadable component (never a guess of the real value)
TOP_N = 5                           # "top" list size used in the sensitivity flags
SCORE_DECIMALS = 4                  # rounding of P and confidence in the CSV
PART_DECIMALS = 2                   # rounding of component scores inside breakdown_json
ORDINAL = {"Low": 0.0, "Medium": 0.5, "High": 1.0}                           # shade/drought/waterlog/typhoon levels
GROWTH = {"Slow": 0.0, "Medium": 0.5, "Fast": 1.0}
FOLIAGE = {"evergreen": 1.0, "semi-deciduous": 0.5, "deciduous": 0.0}        # canopy kept through the year = more shade / cover
THREAT = {"Least Concern": 0.0, "Vulnerable": 1 / 3, "Endangered": 2 / 3, "Critically Endangered": 1.0}   # scheme often unnamed
ORIGIN = {"native": 1.0, "crop": 0.0, "other": 0.0}                           # only native species count as native value
MAX_PROBLEM_TAGS = 3                # pest, disease, seed_issue  -> low_maintenance part = 1 - n_tags / 3
MAX_CARE_TAGS = 3                   # pruning, mycorrhiza, shade_nursery -> part = 1 - n_tags / 3

# text rules: first matching regex wins; no match = "not stated" = missing (neutral score, lowers confidence)
RULES = {
    "planting_difficulty": [(r"low infrastructure risk", 1.0), (r"infrastructure damage|lift pavement", 0.0)],
    "propagation_method": [(r"seed|cutting|sucker", 1.0), (r"graft|budding|marcott|tissue", 0.0)],   # simple vs skilled methods
    "native_habitat": [(r"river|stream|riparian|bank|ravine", 1.0), (r".", 0.0)],                  # any stated habitat w/o water = 0
    "common_uses": [(r"timber|construction|fruit|edible|nut|copra|coconut|oil|beverage|chocolate|culinary|flavoring|"
                     r"food|veneer|furniture|plywood|carving|boat|resin|banana|juice|condiment|papain|coloring", 1.0), (r".", 0.0)],
}

# column named in purpose_weights.csv -> how it is scored.  higher=True: bigger value is better.
COLUMN_SCORERS = {
    "urban_tags": {"kind": "tag_purpose"},                                       # 1 if any tag maps to the purpose being scored
    "canopy_spread_m": {"kind": "minmax", "higher": True},
    "growth_rate": {"kind": "ordinal", "levels": GROWTH},
    "foliage": {"kind": "ordinal", "levels": FOLIAGE},
    "root_urban_safety_prov": {"kind": "unit"},                                  # already 0..1 (provisional root-type map)
    "root_soil_binding_prov": {"kind": "unit"},
    "planting_difficulty": {"kind": "rules"},
    "mature_height_m": {"kind": "minmax", "higher": False},                      # taller = more risk near infrastructure
    "typhoon_res": {"kind": "ordinal", "levels": ORDINAL},
    "timber_density": {"kind": "minmax", "higher": True, "derived": ("timber_density_min", "timber_density_max")},
    "drought_tol": {"kind": "ordinal", "levels": ORDINAL},
    "problem_tags": {"kind": "count_tags", "max": MAX_PROBLEM_TAGS},
    "care_tags": {"kind": "count_tags", "max": MAX_CARE_TAGS},
    "origin": {"kind": "ordinal", "levels": ORIGIN},
    "endangered": {"kind": "threat"},
    "common_uses": {"kind": "rules"},
    "is_high_value_crop": {"kind": "flag"},
    "propagation_method": {"kind": "rules"},
    "germination_days": {"kind": "minmax", "higher": False, "derived": ("germination_days_min", "germination_days_max")},
    "dry_season_months": {"kind": "minmax", "higher": True, "derived": ("dry_season_months_min", "dry_season_months_max")},
    "n_fixing": {"kind": "flag"},
    "max_slope_pct": {"kind": "minmax", "higher": True},
    "waterlog_tol": {"kind": "ordinal", "levels": ORDINAL},
    "native_habitat": {"kind": "rules"},
}
# species column -> field_name(s) in species_sources that justify it (for the source ids in breakdown_json)
SOURCE_FIELDS = {
    "urban_tags": ["urban_raw"], "canopy_spread_m": ["canopy_spread_m"], "growth_rate": ["growth_rate_raw"], "foliage": ["growth_form"],
    "root_urban_safety_prov": ["root_type"], "root_soil_binding_prov": ["root_type"], "planting_difficulty": ["planting_difficulty"],
    "mature_height_m": ["mature_height_m"], "typhoon_res": ["typhoon_res"], "timber_density": ["timber_density_raw"],
    "drought_tol": ["drought_tol"], "problem_tags": ["common_problems"], "care_tags": ["special_care_notes"], "origin": ["category"],
    "endangered": ["endangered_raw"], "common_uses": ["common_uses"], "propagation_method": ["propagation_method"],
    "germination_days": ["germination_raw"], "dry_season_months": ["dry_season_raw"], "n_fixing": ["mode_of_nutrition"],
    "max_slope_pct": ["max_slope_pct"], "waterlog_tol": ["waterlog_tol"], "native_habitat": ["native_habitat"],
}
# inputs that are not rows of species_sources
EXTERNAL_SOURCES = {
    "is_high_value_crop": "team_decision:species_directsource.csv (not a sourced fact)",
    "root_urban_safety_prov": "provisional_map:tag_maps_root.csv", "root_soil_binding_prov": "provisional_map:tag_maps_root.csv",
    "urban_tags": "provisional_map:tag_maps_urban.csv",
}
# =====================================================================================================================


def load_weights(path):
    w = pd.read_csv(path)
    for purpose, g in w.groupby("purpose"):
        if abs(g.weight_provisional.sum() - 1.0) > 1e-6:
            raise ValueError(f"weights for '{purpose}' sum to {g.weight_provisional.sum():.4f}, expected 1.00")
    missing = {c for cols in w.species_columns for c in cols.split(";")} - set(COLUMN_SCORERS)
    if missing:
        raise ValueError(f"no scoring rule in COLUMN_SCORERS for: {sorted(missing)}")
    return w


def load_tag_purpose(path):
    """{tag (canonical or as written, lower case): purpose} from the provisional tag map; tags without a purpose are left out."""
    m = pd.read_csv(path).dropna(subset=["purpose"])
    d = {}
    for r in m.itertuples(index=False):
        d[str(r.canonical_tag).strip().lower()] = r.purpose
        d[str(r.tag_as_written).strip().lower()] = r.purpose
    return d


def _raw(sp, col):
    spec = COLUMN_SCORERS[col]
    if "derived" in spec:
        lo, hi = spec["derived"]
        return (sp[lo].astype(float) + sp[hi].astype(float)) / 2          # NaN if either end is missing
    if col == "endangered":
        return sp[["endangered_unspecified", "endangered_denr", "endangered_iucn"]]
    return sp[col]


def component_scores(sp, col, purpose, tag_purpose):
    """Score (0..1, NaN = missing / not stated) of one species column for every species."""
    spec, x = COLUMN_SCORERS[col], _raw(sp, col)
    kind = spec["kind"]
    if kind == "ordinal":
        return x.map(spec["levels"]).astype(float)
    if kind == "minmax":
        x = x.astype(float); lo, hi = x.min(), x.max()
        s = (x - lo) / (hi - lo) if hi > lo else pd.Series(np.where(x.notna(), NEUTRAL_SCORE, np.nan), index=x.index)
        return s if spec["higher"] else 1.0 - s
    if kind == "unit":
        return x.astype(float).clip(0, 1)
    if kind == "flag":
        return x.map(lambda v: np.nan if pd.isna(v) else float(bool(v)))
    if kind == "rules":
        def f(t):
            if pd.isna(t):
                return np.nan
            for pat, val in RULES[col]:
                if re.search(pat, str(t), re.I):
                    return val
            return np.nan
        return x.map(f)
    if kind == "tag_purpose":
        return x.map(lambda t: np.nan if pd.isna(t) else float(any(tag_purpose.get(a.strip().lower()) == purpose for a in str(t).split(";"))))
    if kind == "count_tags":
        # a blank tag cell means "no keyword matched" (the source text exists), not "no problem": treated as unknown
        return x.map(lambda t: np.nan if pd.isna(t) else 1.0 - min(len([a for a in str(t).split(";") if a.strip()]), spec["max"]) / spec["max"])
    if kind == "threat":
        def f(row):
            v = [THREAT[s] for s in row if pd.notna(s) and s in THREAT]
            return max(v) if v else np.nan                                  # most threatened of the statuses given
        return x.apply(f, axis=1)
    raise ValueError(kind)


def score_species(sp, weights, tag_purpose):
    """
    Returns (scores, parts): scores = DataFrame(species_id, purpose, criterion, weight, score, n_parts, n_missing),
    parts = {(species_id, purpose, criterion): {column: score or None}}.
    """
    rows, parts = [], {}
    sp = sp.reset_index(drop=True)
    for w in weights.itertuples(index=False):
        cols = w.species_columns.split(";")
        comp = pd.DataFrame({c: component_scores(sp, c, w.purpose, tag_purpose) for c in cols})
        miss = comp.isna()
        filled = comp.fillna(NEUTRAL_SCORE)
        crit = filled.mean(axis=1)
        for i, sid in enumerate(sp.species_id):
            rows.append((int(sid), w.purpose, w.criterion, float(w.weight_provisional), float(crit.iloc[i]), len(cols), int(miss.iloc[i].sum())))
            parts[(int(sid), w.purpose, w.criterion)] = {c: (None if miss.iloc[i][c] else round(float(comp.iloc[i][c]), PART_DECIMALS)) for c in cols}
    return pd.DataFrame(rows, columns=["species_id", "purpose", "criterion", "weight", "score", "n_parts", "n_missing"]), parts


def aggregate(scores):
    """P and confidence per (species, purpose). confidence = weight-weighted share of components that were not missing."""
    s = scores.assign(wp=lambda d: d.weight * d.score, wk=lambda d: d.weight * (1 - d.n_missing / d.n_parts))
    g = s.groupby(["species_id", "purpose"], sort=False).agg(p_score=("wp", "sum"), confidence=("wk", "sum"), n_missing=("n_missing", "sum")).reset_index()
    g["rank"] = g.groupby("purpose").p_score.transform(lambda x: x.round(9).rank(ascending=False, method="min")).astype(int)
    return g


def source_ids(sources):
    return {(int(r.species_id), r.field_name): int(r.source_id) for r in sources.itertuples(index=False)}


def build_breakdown(scores, parts, src, species_cols_by_criterion):
    out = {}
    for (sid, purpose), g in scores.groupby(["species_id", "purpose"], sort=False):
        crit = {}
        for r in g.itertuples(index=False):
            cols = species_cols_by_criterion[(r.purpose, r.criterion)]
            ids = sorted({src[(sid, f)] for c in cols for f in SOURCE_FIELDS.get(c, []) if (sid, f) in src})
            ext = sorted({EXTERNAL_SOURCES[c] for c in cols if c in EXTERNAL_SOURCES})
            d = {"score": round(r.score, PART_DECIMALS + 1), "weight": r.weight, "missing": f"{r.n_missing}/{r.n_parts}",
                 "parts": parts[(sid, purpose, r.criterion)], "src": ids}
            if ext:
                d["ext"] = ext
            crit[r.criterion] = d
        out[(sid, purpose)] = json.dumps(crit, separators=(",", ":"))
    return out


def sensitivity(scores, perturbation=None, top_n=None):
    """
    Rank range of each species under weight changes of +-perturbation. Scenarios per purpose: every criterion alone at x(1-p)
    and x(1+p), plus every combination with ALL criteria moved at once (2^n sign patterns). Scale does not change ranks, so
    weights are not renormalised.
    """
    p = PERTURBATION if perturbation is None else perturbation
    n_top = TOP_N if top_n is None else top_n
    out = []
    for purpose, g in scores.groupby("purpose", sort=False):
        mat = g.pivot(index="species_id", columns="criterion", values="score")
        crits = list(g.drop_duplicates("criterion").criterion)
        mat = mat[crits]
        w0 = g.drop_duplicates("criterion").set_index("criterion").weight.reindex(crits).to_numpy()

        def ranks(w):
            return pd.Series((mat.to_numpy() @ w).round(9), index=mat.index).rank(ascending=False, method="min").astype(int)

        base = ranks(w0)
        single = {}                                                   # (criterion, sign) -> rank series
        for j, c in enumerate(crits):
            for sign in (-1, +1):
                w = w0.copy(); w[j] *= 1 + sign * p
                single[(c, sign)] = ranks(w)
        allmoved = [ranks(w0 * (1 + p * np.array(s))) for s in itertools.product((-1, 1), repeat=len(crits))]
        every = list(single.values()) + allmoved
        R = pd.concat(every, axis=1)
        top_all = (R <= n_top).all(axis=1); top_ever = (R <= n_top).any(axis=1)
        S = pd.DataFrame({k: (v - base).abs() for k, v in single.items()})
        for sid in mat.index:
            worst = S.loc[sid].idxmax(); shift = int(S.loc[sid].max())
            out.append({"species_id": int(sid), "purpose": purpose, "base_rank": int(base[sid]), "rank_best": int(R.loc[sid].min()),
                        "rank_worst": int(R.loc[sid].max()), "max_rank_shift": int(R.loc[sid].sub(base[sid]).abs().max()),
                        "max_single_weight_shift": shift,
                        "worst_single_change": f"{worst[0]} {'+' if worst[1] > 0 else '-'}{int(p * 100)}%" if shift else "",
                        f"top{n_top}_base": bool(base[sid] <= n_top), f"top{n_top}_in_all_scenarios": bool(top_all[sid]),
                        f"top{n_top}_in_any_scenario": bool(top_ever[sid]), "n_scenarios": len(every)})
    return pd.DataFrame(out)


def run(out_dir, weights_path):
    out = Path(out_dir)
    sp = pd.read_csv(out / "species_clean.csv")
    src = source_ids(pd.read_csv(out / "species_sources.csv"))
    weights = load_weights(weights_path)
    tag_purpose = load_tag_purpose(out / "tag_maps_urban.csv")
    scores, parts = score_species(sp, weights, tag_purpose)
    agg = aggregate(scores)
    cols = {(r.purpose, r.criterion): r.species_columns.split(";") for r in weights.itertuples(index=False)}
    bd = build_breakdown(scores, parts, src, cols)
    agg["breakdown_json"] = [bd[(r.species_id, r.purpose)] for r in agg.itertuples(index=False)]
    agg["common_name"] = agg.species_id.map(sp.set_index("species_id").common_name)
    agg["weights_status"] = "provisional"
    res = agg[["species_id", "common_name", "purpose", "p_score", "rank", "confidence", "n_missing", "weights_status", "breakdown_json"]].copy()
    res["p_score"] = res.p_score.round(SCORE_DECIMALS); res["confidence"] = res.confidence.round(SCORE_DECIMALS)
    res = res.sort_values(["purpose", "rank", "species_id"])
    res.to_csv(out / "purpose_scores.csv", index=False)
    sens = sensitivity(scores)
    sens.insert(1, "common_name", sens.species_id.map(sp.set_index("species_id").common_name))
    sens.sort_values(["purpose", "base_rank", "species_id"]).to_csv(out / "purpose_sensitivity.csv", index=False)
    for purpose, g in res.groupby("purpose"):
        print(f"top {TOP_N} {purpose}: " + "; ".join(f"{r.rank}. {r.common_name} ({r.p_score:.3f}, conf {r.confidence:.2f})" for r in g.head(TOP_N).itertuples()))
    print(f"rows: {len(res)} scores, {len(sens)} sensitivity | written to {out}")
    return res, sens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--weights", default="data/config/purpose_weights.csv")
    a = ap.parse_args()
    run(a.out, a.weights)


if __name__ == "__main__":
    main()
