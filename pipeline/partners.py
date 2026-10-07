#!/usr/bin/env python3
"""
partners.py - "Works well with": starting rules for which species can be planted together (round 14). ALL PROVISIONAL: the thresholds below are
proposals, to be checked by the agriculturist. Nothing here changes a score, a rank or a plan; it only adds advice.

    python pipeline/partners.py --out data/processed          # writes data/processed/species_partners.csv

For every ordered pair (A, B) - B is the partner that grows with the main tree A - a pair is LISTED only if it passes every rule:
  overlap   at least `overlap_min_share` of the smaller set of suitable squares (S >= `s_min`) is shared, AND the two share at least `min_shared_months` planting months;
  water     no opposite clash: one species High and the other Low in drought tolerance, or in waterlogging tolerance;
  roots     the two are not both below `roots_min` on the root urban safety score (provisional score of species_clean);
  layering  B is at most `layer_height_ratio` of A's mature height AND B's shade tolerance is Medium or High, OR B's common name is written in A's plant_partners text
            ("named in the sources"). A named pair still has to pass overlap, water and roots.
The score (0 to 1) = weights x (layering, overlap share, water, roots, named). Reasons are plain sentences. A missing value never passes a rule that needs it (nothing is guessed).
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
    "weights": {"layering": 0.35, "overlap": 0.25, "water": 0.15, "roots": 0.10, "named": 0.15},
    "max_partners": 5,                 # the API returns at most this many
    "name_part_min_len": 5,            # a part of a common name ("Banana" of "Banana - Saba") must be this long to be matched in the sources text
}
OUT_COLUMNS = ["species_id", "partner_id", "score", "reasons", "overlap_share", "source_named"]
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


def pair_rules(a, b, both, n_a, n_b, cfg=None):
    """The rules for one ordered pair. a, b = species rows (Series); both / n_a / n_b = squares suitable for both / for A / for B.
    Returns {listed, score, reasons, overlap_share, source_named, rules} where rules says what each rule found."""
    c = PARTNER_CFG if cfg is None else cfg
    r = {}
    smaller = min(n_a, n_b)
    share = (both / smaller) if smaller else 0.0
    ma, mb = pal.parse_months(a.planting_months), pal.parse_months(b.planting_months)
    shared = sorted((ma & mb)) if ma is not None and mb is not None else []
    r["overlap"] = bool(smaller and share >= c["overlap_min_share"] and len(shared) >= c["min_shared_months"])
    clash = False
    for col in ("drought_tol", "waterlog_tol"):
        pair = (a[col], b[col])
        if pair in [tuple(x) for x in c["clash_pairs"]]:
            clash = True
    r["water"] = not clash
    ra, rb = a.root_urban_safety_prov, b.root_urban_safety_prov
    r["roots"] = bool(pd.notna(ra) and pd.notna(rb) and not (ra < c["roots_min"] and rb < c["roots_min"]))
    ha, hb = a.mature_height_m, b.mature_height_m
    r["layering"] = bool(pd.notna(ha) and pd.notna(hb) and ha > 0 and hb <= c["layer_height_ratio"] * ha and b.shade_tol in c["layer_shade_ok"])
    r["named"] = named_in_text(b.common_name, a.plant_partners)
    listed = r["overlap"] and r["water"] and r["roots"] and (r["layering"] or r["named"])
    w = c["weights"]
    score = (w["layering"] * r["layering"] + w["overlap"] * min(1.0, share) + w["water"] * r["water"]
             + w["roots"] * (min(float(ra), float(rb)) if r["roots"] else 0.0) + w["named"] * r["named"])
    reasons = []
    if r["layering"]:
        reasons.append(f"{b.common_name} is a lower tree (about {float(hb):g} m against {float(ha):g} m) that tolerates shade, so it can grow under {a.common_name}.")
    if r["named"]:
        reasons.append(f"The species data names {b.common_name} as a partner of {a.common_name}.")
    reasons.append(f"Both suit the same land: {share:.0%} of the squares that suit the smaller set suit both.")
    reasons.append(f"They share planting months: {month_text(shared)}.")
    reasons.append("Their drought and waterlogging needs do not clash.")
    reasons.append("Their roots are not both risky for pavements and pipes.")
    return {"listed": bool(listed), "score": round(float(score), 4), "reasons": reasons, "overlap_share": round(float(share), 4), "source_named": bool(r["named"]),
            "rules": r, "shared_months": shared}


def build_partners(species, S, cfg=None):
    """species = species_clean rows, S = (squares x species) site suitability in the same order. Returns the table of listed pairs."""
    c = PARTNER_CFG if cfg is None else cfg
    species = species.reset_index(drop=True)
    G = (np.asarray(S, dtype=float) >= c["s_min"]).astype(np.int64)
    both = G.T @ G
    n = G.sum(axis=0)
    rows = []
    for i in range(len(species)):
        for j in range(len(species)):
            if i == j:
                continue
            x = pair_rules(species.iloc[i], species.iloc[j], int(both[i, j]), int(n[i]), int(n[j]), c)
            if x["listed"]:
                rows.append({"species_id": int(species.species_id[i]), "partner_id": int(species.species_id[j]), "score": x["score"], "reasons": REASON_SEP.join(x["reasons"]),
                             "overlap_share": x["overlap_share"], "source_named": x["source_named"]})
    out = pd.DataFrame(rows, columns=OUT_COLUMNS)
    return out.sort_values(["species_id", "score", "partner_id"], ascending=[True, False, True]).reset_index(drop=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--scores", help="site_scores.db (default <out>/scores/site_scores.db)")
    a = ap.parse_args(argv)
    import run_plan as rp
    ctx = rp.load_context(a.out, a.scores, True)
    t = build_partners(ctx.species, ctx.S)
    f = Path(a.out) / "species_partners.csv"
    t.to_csv(f, index=False)
    have = t.species_id.nunique()
    print(f"{len(t)} partner pairs for {have} of {len(ctx.species)} species ({len(ctx.species) - have} without a partner); written {f}")


if __name__ == "__main__":
    main()
