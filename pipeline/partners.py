#!/usr/bin/env python3
"""
partners.py - "Works well with": starting rules for which species can be planted together (round 14, changed in round 15a). ALL PROVISIONAL: the thresholds below are
proposals, to be checked by the agriculturist. Nothing here changes a score, a rank or a plan; it only adds advice.

    python pipeline/partners.py --out data/processed          # writes data/processed/species_partners.csv

For every ordered pair (A, B) - B is the partner that grows with the main tree A - a pair is listed as "fits" only if it passes:
  overlap   at least `overlap_min_share` of the smaller set of suitable squares is shared (S >= `s_min`), AND the two share at least `min_shared_months` planting months;
  water     no opposite DROUGHT clash (High against Low);
  roots     the two are not both below `roots_min` on the root urban safety score;
  layering  B is at most `layer_height_ratio` of A's mature height AND B's shade tolerance is Medium or High, OR B's common name is written in A's plant_partners text ("named in the sources").
Round 15a changes:
  * A pair that is named in the sources but fails a rule is no longer dropped: it is listed with status "named_conditions_differ", the label "named in the sources, conditions differ" and the plain reasons.
  * A waterlogging mismatch (High against Low) is no longer a rejection but a caution, "check drainage" - unless the land they share lies within `near_water_m` (50 m) of a creek or river:
    the overlap is then counted only on the squares at least 50 m from water, and a pair that cannot pass there is rejected (or, if named in the sources, listed as "conditions differ").
The score (0 to 1) = weights x (layering, overlap share, water, roots, named). A missing value never passes a rule that needs it (nothing is guessed).
"""
import argparse, re, sys, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import palettes as pal  # noqa: E402

# =====================================================================================================================
# CONFIG - PROVISIONAL, to be checked by the agriculturist
# =====================================================================================================================
PARTNER_CFG = {
    "s_min": 0.50,                     # a square is suitable for a species when S >= this (the same cut-off as the plans)
    "overlap_min_share": 0.50,         # shared suitable squares must be at least this share of the SMALLER set
    "min_shared_months": 2,            # planting months the two species have in common
    "layer_height_ratio": 0.60,        # the partner is at most this share of the main tree's mature height ...
    "layer_shade_ok": ("Medium", "High"),   # ... and tolerates shade at least this much
    "roots_min": 0.40,                 # both below this root urban safety score = not a partner (pavements, pipes)
    "clash_pairs": (("High", "Low"), ("Low", "High")),    # opposite tolerance levels count as a clash
    "near_water_m": 50.0,              # round 15a: a waterlogging mismatch is only a caution on land at least this far from a creek or river
    "weights": {"layering": 0.35, "overlap": 0.25, "water": 0.15, "roots": 0.10, "named": 0.15},
    "max_partners": 5,                 # the API returns at most this many
    "name_part_min_len": 5,            # a part of a common name ("Banana" of "Banana - Saba") must be this long to be matched in the sources text
}
OUT_COLUMNS = ["species_id", "partner_id", "score", "reasons", "overlap_share", "source_named", "status", "cautions"]
STATUS_FITS, STATUS_NAMED = "fits", "named_conditions_differ"
NAMED_LABEL = "named in the sources, conditions differ"
DRAINAGE_CAUTION = "check drainage"
REASON_SEP = " | "
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# =====================================================================================================================


def _norm(text):
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def name_variants(common_name, min_len=None):
    """The ways a species name may be written in a sources text: the whole name, and each part of 'Banana - Saba', 'Robusta (Coffee)', 'Indian/Carabao Mango'."""
    m = PARTNER_CFG["name_part_min_len"] if min_len is None else min_len
    whole = _norm(common_name)
    parts = [_norm(p) for p in re.split(r"\s+-\s+|[()/]", str(common_name))]
    out = {whole} | {p for p in parts if len(p) >= m}
    return {v for v in out if v}


def named_in_text(partner_name, text):
    """True if the partner's common name (or a long enough part of it) is written in the text as a whole word."""
    if not isinstance(text, str) or not text.strip():
        return False
    hay = f" {_norm(text)} "
    return any(f" {v} " in hay for v in name_variants(partner_name))


def month_text(months):
    return ", ".join(MONTHS[m - 1] for m in sorted(months))


def pair_rules(a, b, both, n_a, n_b, cfg=None, far=None):
    """The rules for one ordered pair. a, b = species rows (Series); both / n_a / n_b = squares suitable for both / for A / for B.
    far = (both, n_a, n_b) counted only on squares at least `near_water_m` from water (used when the waterlogging tolerance of the two clashes); None = not known.
    Returns {status, listed, score, reasons, overlap_share, source_named, cautions, rules, shared_months}; status is "fits", "named_conditions_differ" or None (not listed)."""
    c = PARTNER_CFG if cfg is None else cfg
    r = {}
    ma, mb = pal.parse_months(a.planting_months), pal.parse_months(b.planting_months)
    shared = sorted((ma & mb)) if ma is not None and mb is not None else []
    waterlog_clash = (a["waterlog_tol"], b["waterlog_tol"]) in [tuple(x) for x in c["clash_pairs"]]
    cautions = []
    if waterlog_clash:
        if far is None:
            both, n_a, n_b = 0, 0, 0                                      # unknown distance to water: the shared land cannot be shown to be far from it
        else:
            both, n_a, n_b = far
        cautions.append(DRAINAGE_CAUTION)
    smaller = min(n_a, n_b)
    share = (both / smaller) if smaller else 0.0
    r["overlap"] = bool(smaller and share >= c["overlap_min_share"] and len(shared) >= c["min_shared_months"])
    r["water"] = (a["drought_tol"], b["drought_tol"]) not in [tuple(x) for x in c["clash_pairs"]]
    ra, rb = a.root_urban_safety_prov, b.root_urban_safety_prov
    r["roots"] = bool(pd.notna(ra) and pd.notna(rb) and not (ra < c["roots_min"] and rb < c["roots_min"]))
    ha, hb = a.mature_height_m, b.mature_height_m
    r["layering"] = bool(pd.notna(ha) and pd.notna(hb) and ha > 0 and hb <= c["layer_height_ratio"] * ha and b.shade_tol in c["layer_shade_ok"])
    r["named"] = named_in_text(b.common_name, a.plant_partners)
    passes = r["overlap"] and r["water"] and r["roots"]
    fits = passes and (r["layering"] or r["named"])
    status = STATUS_FITS if fits else STATUS_NAMED if r["named"] else None
    w = c["weights"]
    score = (w["layering"] * r["layering"] + w["overlap"] * min(1.0, share) + w["water"] * r["water"]
             + w["roots"] * (min(float(ra), float(rb)) if r["roots"] else 0.0) + w["named"] * r["named"])
    reasons = []
    if status == STATUS_NAMED:
        reasons.append(f"{NAMED_LABEL.capitalize()}: the species data names {b.common_name} as a partner of {a.common_name}, but our rules do not agree.")
        if not r["overlap"]:
            where = " on land at least 50 m from water" if waterlog_clash else ""
            reasons.append(f"They suit the same land{where} only {share:.0%} of the time (the rule needs {c['overlap_min_share']:.0%}) or share fewer than {c['min_shared_months']} planting months.")
        if not r["water"]:
            reasons.append(f"Drought tolerance differs ({a.common_name} {a.drought_tol}, {b.common_name} {b.drought_tol}).")
        if not r["roots"]:
            reasons.append("Both have roots that can damage pavements and pipes.")
        if waterlog_clash:
            reasons.append(f"Waterlogging tolerance differs ({a.common_name} {a.waterlog_tol}, {b.common_name} {b.waterlog_tol}): check drainage.")
    else:
        if r["layering"]:
            reasons.append(f"{b.common_name} is a lower tree (about {float(hb):g} m against {float(ha):g} m) that tolerates shade, so it can grow under {a.common_name}.")
        if r["named"]:
            reasons.append(f"The species data names {b.common_name} as a partner of {a.common_name}.")
        land = " (on land at least 50 m from water)" if waterlog_clash else ""
        reasons.append(f"Both suit the same land{land}: {share:.0%} of the squares that suit the smaller set suit both.")
        reasons.append(f"They share planting months: {month_text(shared)}.")
        reasons.append("Their drought needs do not clash." if not waterlog_clash else "Their drought needs do not clash.")
        if waterlog_clash:
            reasons.append(f"Caution: waterlogging tolerance differs ({a.common_name} {a.waterlog_tol}, {b.common_name} {b.waterlog_tol}): {DRAINAGE_CAUTION}.")
        else:
            reasons.append("Their waterlogging needs do not clash.")
        reasons.append("Their roots are not both risky for pavements and pipes.")
    return {"status": status, "listed": status == STATUS_FITS, "score": round(float(score), 4), "reasons": reasons, "overlap_share": round(float(share), 4),
            "source_named": bool(r["named"]), "cautions": cautions, "rules": r, "shared_months": shared}


def build_partners(species, S, water_dist=None, cfg=None):
    """species = species_clean rows, S = (squares x species) site suitability in the same order, water_dist = metres to the nearest creek or river per square (None = unknown).
    Returns the table of listed pairs (status fits, or named in the sources with conditions that differ)."""
    c = PARTNER_CFG if cfg is None else cfg
    species = species.reset_index(drop=True)
    G = (np.asarray(S, dtype=float) >= c["s_min"]).astype(np.int64)
    both = G.T @ G
    n = G.sum(axis=0)
    far_mask = None if water_dist is None else (np.asarray(water_dist, dtype=float) >= c["near_water_m"])
    if far_mask is not None:
        Gf = G * far_mask[:, None]
        both_f, n_f = Gf.T @ Gf, Gf.sum(axis=0)
    rows = []
    for i in range(len(species)):
        for j in range(len(species)):
            if i == j:
                continue
            far = (int(both_f[i, j]), int(n_f[i]), int(n_f[j])) if far_mask is not None else None
            x = pair_rules(species.iloc[i], species.iloc[j], int(both[i, j]), int(n[i]), int(n[j]), c, far)
            if x["status"]:
                rows.append({"species_id": int(species.species_id[i]), "partner_id": int(species.species_id[j]), "score": x["score"], "reasons": REASON_SEP.join(x["reasons"]),
                             "overlap_share": x["overlap_share"], "source_named": x["source_named"], "status": x["status"], "cautions": ";".join(x["cautions"])})
    out = pd.DataFrame(rows, columns=OUT_COLUMNS)
    out["_o"] = (out.status != STATUS_FITS).astype(int)
    out = out.sort_values(["species_id", "_o", "score", "partner_id"], ascending=[True, True, False, True]).drop(columns="_o")
    return out.reset_index(drop=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--scores", help="site_scores.db (default <out>/scores/site_scores.db)")
    ap.add_argument("--water", default="data/SMR_WATERBODIES_POLY.shp", help="waterbodies layer (distance to the nearest creek or river)")
    a = ap.parse_args(argv)
    import run_plan as rp
    import score_sites as ss
    ctx = rp.load_context(a.out, a.scores, True)
    wd = None
    try:
        wd = ss.distance_to_water(ctx.sites, str(ROOT / a.water) if not Path(a.water).is_absolute() else a.water).to_numpy(dtype=float)
        if not np.isfinite(wd).any():
            wd = None
    except Exception as e:                                               # no waterbodies layer: the waterlogging caution cannot be placed on the map
        print("water distance not available:", e)
    t = build_partners(ctx.species, ctx.S, wd)
    f = Path(a.out) / "species_partners.csv"
    t.to_csv(f, index=False)
    fits = t[t.status == STATUS_FITS]
    print(f"{len(fits)} partner pairs that fit for {fits.species_id.nunique()} of {len(ctx.species)} species; {int((t.status != STATUS_FITS).sum())} pairs named in the sources with conditions that differ; "
          f"{int((t.cautions.fillna('') != '').sum())} with the caution '{DRAINAGE_CAUTION}'; written {f}")


if __name__ == "__main__":
    main()
