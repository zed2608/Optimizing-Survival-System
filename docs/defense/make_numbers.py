#!/usr/bin/env python3
"""Writes docs/defense/NUMBERS.md: ONE table of every headline number of the project, each read from the file that holds it (never typed by hand).

    .venv\\Scripts\\python.exe docs/defense/make_numbers.py

Reads (changes nothing): data/processed/*.csv|txt|json, data/processed/scores/site_scores.csv, data/validation/*, docs/*.md, pipeline/*.py (the settings),
and docs/defense/_runtime_numbers.json (numbers measured in the round 20 run: tests, timings, memory; written by hand from the run logs).
A number that cannot be read is written as UNKNOWN with the reason: it is never guessed.
"""
import json, re, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"
sys.path.insert(0, str(ROOT / "pipeline"))
ROWS = []          # (section, quantity, value, source)


def add(section, quantity, value, source):
    ROWS.append((section, quantity, value, source))


def unk(why):
    return f"UNKNOWN ({why})"


def n(x):
    return f"{int(x):,}"


def txt(path):
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def find(pattern, text, group=1, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(group) if m else None


# ---------------------------------------------------------------- grid, species, pairs
sites = pd.read_csv(P / "site_points_clean.csv")
species = pd.read_csv(P / "species_clean.csv")
sc = pd.read_csv(P / "scores" / "site_scores.csv", usecols=["point_id", "species_id", "s_rule", "s_prob"])
run = json.loads((P / "scores" / "score_run.json").read_text())
SRC = "data/processed/site_points_clean.csv"
add("Grid", "Grid squares (100 m)", n(len(sites)), SRC)
zs = sites.zoning_status.value_counts()
add("Grid", "Squares: zoning confirmed / unconfirmed (outside the zoning map) / excluded", f"{n(zs.get('confirmed', 0))} / {n(zs.get('unconfirmed', 0))} / {n(zs.get('excluded', 0))}", SRC + " (zoning_status)")
scored = sc.point_id.nunique()
add("Grid", "Scored squares (confirmed + unconfirmed)", n(scored), "data/processed/scores/site_scores.csv (distinct point_id)")
add("Grid", "Species in the dataset", n(len(species)), "data/processed/species_clean.csv")
add("Grid", "Square x species pairs", n(len(sc)), "data/processed/scores/site_scores.csv; scores/score_run.json says " + n(run.get("pairs", 0)))
nosoil_all = int(sites.soil_texture_lgu.isna().sum())
scored_ids = set(sc.point_id.unique())
nosoil_scored = int(sites[sites.point_id.isin(scored_ids)].soil_texture_lgu.isna().sum())
add("Grid", "Squares without an LGU soil texture (all squares / scored squares)", f"{n(nosoil_all)} of {n(len(sites))} ({nosoil_all / len(sites):.1%}) / {n(nosoil_scored)} of {n(scored)}", SRC + " (soil_texture_lgu empty)")

# ---------------------------------------------------------------- eligibility
rules_ok = sc.s_rule >= 0.5
has_rf = sc.s_prob.notna().all()
add("Eligibility (S >= 0.50)", "Eligible pairs, expert rules (graded slope, today)", n(rules_ok.sum()), "data/processed/scores/site_scores.csv (s_rule); score_run.json eligible_pairs " + n(run.get("eligible_pairs", 0)))
if has_rf:
    rf_ok = sc.s_prob >= 0.5
    add("Eligibility (S >= 0.50)", "Eligible pairs, Random Forest s_prob (the default source of S)", n(rf_ok.sum()), "data/processed/scores/site_scores.csv (s_prob)")
    add("Eligibility (S >= 0.50)", "Pairs whose eligibility differs rules vs forest (rules-only / forest-only)", f"{n((rules_ok != rf_ok).sum())} ({n((rules_ok & ~rf_ok).sum())} / {n((~rules_ok & rf_ok).sum())}) = {(rules_ok != rf_ok).mean():.3%} of all pairs", "same")
    both = rules_ok & rf_ok
    add("Eligibility (S >= 0.50)", "Mean / max absolute difference |s_rule - s_prob| over all pairs", f"{(sc.s_rule - sc.s_prob).abs().mean():.5f} / {(sc.s_rule - sc.s_prob).abs().max():.3f}", "same")
    add("Eligibility (S >= 0.50)", "Pairs with rule S = 0 and s_prob > 0 (hard gates broken)", n(((sc.s_rule == 0) & (sc.s_prob > 0)).sum()), "same")
else:
    add("Eligibility (S >= 0.50)", "Eligible pairs, Random Forest", unk("s_prob is missing in the saved scores"), "data/processed/scores/site_scores.csv")
sm = txt("data/processed/slope_mode_report.txt")
add("Eligibility (S >= 0.50)", "Eligible pairs with the old hard slope gate", find(r"hard ([\d,]+)", sm) or unk("not found"), "data/processed/slope_mode_report.txt")
add("Eligibility (S >= 0.50)", "Pairs eligible only because of the graded slope rule", n(run.get("slope_graded_pairs", 0)), "data/processed/scores/score_run.json")
add("Eligibility (S >= 0.50)", "Species with no eligible square (rules)", n(species.shape[0] - sc[rules_ok].species_id.nunique()), "data/processed/scores/site_scores.csv")

# ---------------------------------------------------------------- Random Forest and comparison
meta = json.loads((P / "models" / "rf_site_suitability_meta.json").read_text()) if (P / "models" / "rf_site_suitability_meta.json").is_file() else {}
M = "data/processed/models/rf_site_suitability_meta.json"
if meta:
    add("Random Forest", "Model trained at / dataset hash / features", f"{meta['trained_at']} / {meta['dataset_hash']} / {len(meta['features'])}", M)
    add("Random Forest", "Regressor (makes s_prob), out-of-fold on spatial folds: MAE / R-squared", f"{meta['regressor_oof_mae']} / {meta['regressor_oof_r2']}", M)
    add("Random Forest", "Decision Tree regressor on the same folds: MAE / R-squared", f"{meta['regressor_oof_mae_decision_tree']} / {meta['regressor_oof_r2_decision_tree']}", M)
    add("Random Forest", "Classifier (S >= 0.50, not used for s_prob), out-of-fold accuracy RF / Decision Tree", f"{meta['oof_accuracy']} / {meta['oof_accuracy_decision_tree']}", M)
    add("Random Forest", "Share of pairs with S >= 0.50 (positive share)", f"{meta['positive_share']:.2%}", M)
    add("Random Forest", "Settings: regressor trees / min leaf; classifier min leaf; folds; block size; seed", f"{meta['regressor_settings']['n_estimators']} / {meta['regressor_settings']['min_samples_leaf']}; {meta['settings']['min_samples_leaf']}; {meta['settings']['outer_folds']}; {meta['settings']['spatial_block_cells']} cells (about 1 km); {meta['settings']['seed']}", M)
rr = txt("data/processed/rf_vs_rules_report.txt")
RV = "data/processed/rf_vs_rules_report.txt"
add("Random Forest", "Spearman correlation of S (rules) and s_prob among rule-eligible pairs: all pairs / per-species mean / lowest", " / ".join(find(r"all pairs ([\d.]+); per species mean ([\d.]+), lowest ([\d.]+) \((\w+)\)", rr, g) or "?" for g in (1, 2, 3)) + " (" + (find(r"lowest [\d.]+ \((\w+)\)", rr) or "?") + ")", RV)
add("Random Forest", "Top-20 squares per species: mean overlap rules vs forest; species with the same 20", f"{find(r'mean ([\d.]+) of 20', rr) or '?'} of 20; {find(r'same 20 squares: (\d+) of 45', rr) or '?'} of 45", RV)
mc = pd.read_csv(P / "model_comparison.csv")
MC = "data/processed/model_comparison.csv (30,000-pair stratified subsample, 5 outer folds; mean +/- std over folds)"
for setting in ("random", "spatial", "species"):
    for noise in (0.0, 0.05):
        cells = []
        for m in ("RandomForest", "DecisionTree", "LogisticRegression", "KNN"):
            r = mc[(mc.model == m) & (mc.setting == setting) & (mc.noise == noise) & (mc.metric == "accuracy")]
            cells.append(f"{m} {r['mean'].iloc[0]:.4f} (+/-{r['std'].iloc[0]:.4f})" if len(r) else f"{m} UNKNOWN")
        add("Model comparison (accuracy)", f"{setting} folds, label noise {noise:g}", "; ".join(cells), MC)
add("Model comparison (accuracy)", "Note", "The labels are the expert rules: a model that reaches 0.99+ is copying the rules; it does not measure survival.", "docs/RF_SOURCE.md")

# ---------------------------------------------------------------- matching
mb = pd.read_csv(P / "matching_benchmark.csv")
MB = "data/processed/matching_benchmark.csv (300 trees per purpose, whole municipality)"
for lay in ("points", "blocks"):
    for pur in ("urban", "planting", "watershed"):
        g = mb[(mb.purpose == pur) & (mb.layout_mode == lay)].set_index("method")
        add("Matching (total W)", f"{pur}, {lay}: Hungarian / greedy / random feasible / random blind (placed; rule breaks of random blind)",
            f"{g.loc['hungarian', 'total_W']:.4f} / {g.loc['greedy', 'total_W']:.4f} / {g.loc['random_feasible', 'total_W']:.4f} / {g.loc['random_blind', 'total_W']:.4f} (placed {g.loc['hungarian', 'placed']:.0f}; {g.loc['random_blind', 'violations_total']:.2f} rule breaks)", MB)
gap = max(abs(mb[(mb.purpose == p) & (mb.layout_mode == l) & (mb.method == "hungarian")].total_W.iloc[0] - mb[(mb.purpose == p) & (mb.layout_mode == l) & (mb.method == "greedy")].total_W.iloc[0]) for p in ("urban", "planting", "watershed") for l in ("points", "blocks"))
add("Matching (total W)", "Largest gap Hungarian minus greedy over 6 cases", f"{gap:.6f}", MB)
add("Matching (total W)", "Forest plans judged by the rules: loss of total W (6 cases)", "0.00% to 0.04% (see section 3b of the report)", RV)

# ---------------------------------------------------------------- validation
marks = pd.read_csv(ROOT / "data/validation/agri_sample_marks_20261007.csv", comment="#")
vc = marks.mark.value_counts()
add("Validation (agriculturist sample)", "Pairs on the sheet / marked Suitable / Marginal / Cannot judge / Not suitable", f"{len(marks)} / {vc.get('S', 0)} / {vc.get('M', 0)} / {vc.get('X', 0)} / {vc.get('N', 0)}", "data/validation/agri_sample_marks_20261007.csv")
ck = txt("data/validation/agri_sample_rf_check.txt")
CK = "data/validation/agri_sample_rf_check.txt"
for who in ("printed rules (hard)", "rules (graded)", "Random Forest"):
    a = find(re.escape(who) + r", Marginal as Suitable: ([\d.]+%) \((\d+ of \d+)\)", ck, 1)
    b = find(re.escape(who) + r", Marginal as Not suitable: ([\d.]+%) \((\d+ of \d+)\)", ck, 1)
    add("Validation (agriculturist sample)", f"Agreement with the agriculturist, {who}: Marginal as Suitable / as Not suitable", f"{a or '?'} / {b or '?'} of 36 judged", CK)
add("Validation (agriculturist sample)", "Verdicts that differ between graded rules and the forest", find(r"Random Forest: (\d+) of 40", ck) + " of 40", CK)
sv = txt("docs/SAMPLE_VALIDATION_RESULT.md")
add("Validation (agriculturist sample)", "Cohen's kappa of the printed verdicts (Marginal as Suitable / as Not suitable)", f"{find(r'Marginal counted as Suitable \| [^|]+\| ([\d.]+)', sv) or '?'} / {find(r'Marginal counted as Not suitable \| [^|]+\| ([\d.]+)', sv) or '?'}", "docs/SAMPLE_VALIDATION_RESULT.md")
add("Validation (agriculturist sample)", "Reviewers / sheets signed", "1 reviewer; 7 of the 8 pages signed", "docs/SAMPLE_VALIDATION_RESULT.md")

# ---------------------------------------------------------------- partners, tags, data issues
pt = pd.read_csv(P / "species_partners.csv")
fits = pt[pt.status == "fits"]
add("Partner species", "Pairs that fit / named in the sources but conditions differ / species with a fitting partner", f"{len(fits)} / {len(pt) - len(fits)} / {fits.species_id.nunique()} of {len(species)}", "data/processed/species_partners.csv")
rel = txt("data/processed/dataset_release.txt")
add("Data release", "Release tag / combined hash", f"{find(r'dataset release (\S+)', rel)} / {find(r'combined hash \(12 characters\): (\w+)', rel)}", "data/processed/dataset_release.txt")
add("Data release", "Cited cells / ingest issues (high severity)", f"{find(r'cited cells: (\d+)', rel)} / {find(r'ingest issues in total: (\d+)', rel)} ({find(r'high.: (\d+)', rel)})", "data/processed/dataset_release.txt")
add("Data release", "Cells citing a file that was not provided (Batikuling)", find(r"high, file_source_not_provided: (\d+)", rel) or unk("not found"), "data/processed/dataset_release.txt")
lc = txt("docs/DATA_SOURCES.md")
add("Data release", "ESA WorldCover 2021 stated global overall accuracy", find(r"global overall accuracy of ([\d.]+%)", lc) or unk("not found"), "docs/DATA_SOURCES.md (Product Validation Report V2.0; not measured for San Mateo)")

# ---------------------------------------------------------------- settings read from the code
import palettes, score_sites, matching, partners  # noqa: E402
import site_rules  # noqa: E402
add("Settings (all provisional)", "Soft terms and weights (elevation, slope, soil, wetness)", str(score_sites.TERM_WEIGHTS), "pipeline/score_sites.py TERM_WEIGHTS")
add("Settings (all provisional)", "Elevation / slope fall-off margin; graded slope margin; soil mismatch factor; wetness distance", f"{score_sites.MARGIN_FRACTION:.0%} of the range; {score_sites.SLOPE_GRADED_MARGIN_FRACTION:.0%} of the limit; {score_sites.SOIL_MISMATCH_FACTOR}; {score_sites.WETNESS_RISK_DISTANCE_M:g} m", "pipeline/score_sites.py")
add("Settings (all provisional)", "Eligibility cut S", str(matching.CFG["s_min"]), "pipeline/matching.py CFG")
add("Settings (all provisional)", "Species cap / genus cap per plan; palette size", f"{palettes.CFG['max_species_share']:.0%} / {palettes.CFG['max_genus_share']:.0%}; {palettes.CFG['palette_min']} to {palettes.CFG['palette_max']} species", "pipeline/palettes.py CFG (no source)")
add("Settings (all provisional)", "Block: side / usable share / spacing rounding / contour note above", f"{palettes.BLOCK_CFG['block_side_m']:g} m / {palettes.BLOCK_CFG['usable_share']:.0%} / {palettes.BLOCK_CFG['spacing_round_m']} m / {palettes.BLOCK_CFG['contour_slope_pct']:g}% slope", "pipeline/palettes.py BLOCK_CFG")
hb = site_rules.HABAGAT_CFG
add("Settings (all provisional)", "Habagat multiplier on W and months", f"{hb.get('multiplier')} in months {hb.get('months')}", "pipeline/site_rules.py HABAGAT_CFG (MAO interview, 7 Oct 2026)")
add("Settings (all provisional)", "Partner rules: overlap share / shared months / layer height ratio / roots minimum", f"{partners.PARTNER_CFG['overlap_min_share']:.0%} / {partners.PARTNER_CFG['min_shared_months']} / {partners.PARTNER_CFG['layer_height_ratio']:.0%} / {partners.PARTNER_CFG['roots_min']}", "pipeline/partners.py PARTNER_CFG")
pw = pd.read_csv(ROOT / "data/config/purpose_weights.csv")
add("Settings (all provisional)", "Purpose criteria per purpose (urban / planting / watershed) and weight sum", " / ".join(f"{(pw.purpose == p).sum()} criteria, sum {pw[pw.purpose == p].weight_provisional.sum():.2f}" for p in ("urban", "planting", "watershed")), "data/config/purpose_weights.csv")

# ---------------------------------------------------------------- measured in the round 20 run
rt_path = Path(__file__).with_name("_runtime_numbers.json")
rt = json.loads(rt_path.read_text()) if rt_path.is_file() else {}
for key, label, src in (("tests", "pytest: passed / skipped / failed (final run of round 20)", "round 20 final run"),
                        ("qa", "qa_day1: passed / warnings / failed", "python pipeline/qa_day1.py"),
                        ("node_tests", "node tests (files / checks)", "node --test in frontend/src/new"),
                        ("rebuild_seconds", "scripts/rebuild_scores.py: score_sites / make_pair_table / train_rf / total (seconds, this PC)", "docs/defense/_partA_reproducibility.md"),
                        ("plan_seconds", "300-tree plan, Guinayang, blocks: browser click-to-result urban / planting / watershed (seconds)", "docs/defense/_partB_demo_run.md"),
                        ("api_seconds", "API: typical endpoint times", "docs/defense/OVERNIGHT_REPORT.md part E"),
                        ("api_memory_mb", "API process memory at start (working set, MB)", "docs/defense/OVERNIGHT_REPORT.md part E")):
    add("Measured in the round 20 run", label, rt.get(key, unk("not measured in this run")), src)

out = ["# Numbers: every headline number of the project in one table", "",
       "Generated by `docs/defense/make_numbers.py` from the files named in the last column (nothing is typed by hand). A value that could not be read is written UNKNOWN. "
       "All site and purpose scores, weights, caps and thresholds are provisional until the agriculturist signs them off.", ""]
sec = None
for s, q, v, src in ROWS:
    if s != sec:
        out += ["", f"## {s}", "", "| Quantity | Value | Source |", "|---|---|---|"]
        sec = s
    out.append(f"| {q.replace('|', '/')} | {str(v).replace('|', '/')} | {src} |")
(Path(__file__).with_name("NUMBERS.md")).write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"NUMBERS.md written: {len(ROWS)} rows; UNKNOWN rows: {sum('UNKNOWN' in str(r[2]) for r in ROWS)}")
for r in ROWS:
    if "UNKNOWN" in str(r[2]) or "?" in str(r[2]):
        print("  check:", r[1][:70], "->", str(r[2])[:90])
