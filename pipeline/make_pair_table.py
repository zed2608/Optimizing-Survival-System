#!/usr/bin/env python3
"""
make_pair_table.py - Day 2 task 3a: one row per (legal point, species) pair for the model comparison.

    python pipeline/make_pair_table.py --out data/processed [--noise 0.05]

Reads  <out>/site_points_clean.csv, <out>/species_clean.csv, <out>/scores/site_scores.csv (from score_sites.py).
Writes <out>/scores/pair_table.csv.gz (git-ignored).

Label: suitable_clean = 1 if s_rule >= S_THRESHOLD else 0. `suitable` is the same label after the noise rule: a fixed random
fraction NOISE_RATE of ALL pairs, drawn uniformly without replacement with a fixed seed, has its label flipped (so the noisy
label is independent of the features). `label_flipped` marks them. Noise 0.0 flips nothing.

FEATURES are ONLY raw site values (elev_m, slope_pct, soil texture as yes/no columns, distance to the nearest creek/river)
and raw species traits (elev_min_m, elev_max_m, max_slope_pct, waterlog_tol level, soil_any_texture, soil textures as yes/no
columns). s_rule, confidence, breakdown_json and every margin / factor / gate value are NEVER features and are not even
stored in the table (s_rule is dropped right after the label is made).
"""
import argparse, re, sys
from pathlib import Path
import numpy as np
import pandas as pd

# =====================================================================================================================
# CONFIG - every tunable number lives here.
# =====================================================================================================================
S_THRESHOLD = 0.50                  # label = 1 when s_rule >= this (same cut as W = S x P if S >= 0.50)
NOISE_RATE = 0.05                   # default fraction of labels flipped
NOISE_SEED = 42                     # fixed seed of the flip draw
WATER_SHP = "data/SMR_WATERBODIES_POLY.shp"
TABLE_FILE = "scores/pair_table.csv.gz"
WATERLOG_LEVEL = {"Low": 0, "Medium": 1, "High": 2}     # ordinal encoding of the raw trait
# =====================================================================================================================

ID_COLUMNS = ["point_id", "species_id", "cell_row", "cell_col"]       # identifiers / grouping only, never features
LABEL_COLUMNS = ["suitable_clean", "suitable", "label_flipped"]
SITE_NUMERIC = ["elev_m", "slope_pct", "water_dist_m"]
SPECIES_NUMERIC = ["elev_min_m", "elev_max_m", "max_slope_pct", "waterlog_tol_level", "soil_any_texture"]
SITE_TEX_PREFIX, SPECIES_TEX_PREFIX = "site_tex_", "sp_tex_"
# any column name containing one of these (or equal to one) is answer-derived and must never be a feature
FORBIDDEN_FEATURE_PARTS = ("s_rule", "s_prob", "confidence", "breakdown", "margin", "gate", "known_", "f_elevation", "f_slope",
                           "f_soil", "f_wetness", "suitable", "label", "gate_fail", "soil_unverified")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def feature_columns(table):
    """The ONLY columns models may use: raw site values, raw species traits and the texture yes/no columns."""
    cols = [c for c in SITE_NUMERIC + SPECIES_NUMERIC if c in table.columns]
    cols += sorted(c for c in table.columns if c.startswith((SITE_TEX_PREFIX, SPECIES_TEX_PREFIX)))
    bad = [c for c in cols if any(p in c for p in FORBIDDEN_FEATURE_PARTS)]
    if bad:
        raise ValueError(f"leakage: answer-derived columns among the features: {bad}")
    return cols


def build_pair_table(sites, species, scores, water_dist, threshold=None):
    """sites/species: Day 1 tables; scores: DataFrame(point_id, species_id, s_rule); water_dist: Series indexed like sites."""
    thr = S_THRESHOLD if threshold is None else threshold
    s = sites.reset_index(drop=True).copy()
    s["water_dist_m"] = pd.Series(water_dist).reset_index(drop=True).to_numpy()
    tex = s.soil_texture_legacy.fillna("").astype(str).str.strip()
    site = s[["point_id", "cell_row", "cell_col", "elev_m", "slope_pct", "water_dist_m"]].copy()
    for t in sorted(t for t in tex.unique() if t):
        site[SITE_TEX_PREFIX + slug(t)] = (tex == t).astype(int).to_numpy()
    site[SITE_TEX_PREFIX + "unknown"] = (tex == "").astype(int).to_numpy()

    sp = species.reset_index(drop=True)
    lists = sp.soil_textures.map(lambda v: {x.strip() for x in str(v).split(";") if x.strip()} if pd.notna(v) else set())
    spec = sp[["species_id", "elev_min_m", "elev_max_m", "max_slope_pct"]].copy()
    spec["waterlog_tol_level"] = sp.waterlog_tol.map(WATERLOG_LEVEL).astype(float)
    spec["soil_any_texture"] = sp.soil_any_texture.astype(bool).astype(int)
    for t in sorted(set().union(*lists)):
        spec[SPECIES_TEX_PREFIX + slug(t)] = lists.map(lambda L: int(t in L)).to_numpy()

    n = len(scores)
    pairs = (scores[["point_id", "species_id", "s_rule"]]
             .merge(site, on="point_id", how="left", validate="m:1")
             .merge(spec, on="species_id", how="left", validate="m:1"))
    if len(pairs) != n or pairs.elev_m.isna().any() or pairs.elev_min_m.isna().any():
        raise ValueError("some scored pairs have no matching site or species row")
    pairs["suitable_clean"] = (pairs.s_rule >= thr).astype(int)
    pairs = pairs.drop(columns="s_rule")                             # the answer never travels with the features
    return pairs


def apply_noise(labels, rate, seed):
    """Flip exactly round(rate * n) labels chosen uniformly at random (fixed seed). Returns (noisy_labels, flipped_mask)."""
    y = np.asarray(labels).astype(int).copy()
    flipped = np.zeros(len(y), dtype=bool)
    k = int(round(rate * len(y)))
    if k > 0:
        flipped[np.random.default_rng(seed).choice(len(y), size=k, replace=False)] = True
        y[flipped] = 1 - y[flipped]
    return y, flipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--noise", type=float, default=NOISE_RATE, help="fraction of labels flipped (0.0 = none)")
    ap.add_argument("--seed", type=int, default=NOISE_SEED)
    ap.add_argument("--water", default=WATER_SHP)
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import score_sites as ss                                         # same water-distance code as the scoring step
    out = Path(a.out)
    sites = pd.read_csv(out / "site_points_clean.csv")
    sites = sites[sites.is_legal_zone.astype(bool)].copy()
    species = pd.read_csv(out / "species_clean.csv")
    scores = pd.read_csv(out / "scores" / "site_scores.csv", usecols=["point_id", "species_id", "s_rule"])
    water = ss.distance_to_water(sites, a.water)
    table = build_pair_table(sites, species, scores, water)
    table["suitable"], flipped = apply_noise(table.suitable_clean, a.noise, a.seed)
    table["label_flipped"] = flipped.astype(int)
    feats = feature_columns(table)
    dest = out / TABLE_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(dest, index=False, compression="gzip")
    print(f"pairs: {len(table)} ({table.point_id.nunique()} points x {table.species_id.nunique()} species)")
    print(f"label suitable_clean=1: {table.suitable_clean.mean():.1%} | noise {a.noise}: {int(flipped.sum())} labels flipped")
    print(f"{len(feats)} features: {', '.join(feats)}")
    print(f"written to {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
