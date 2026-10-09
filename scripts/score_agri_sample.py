#!/usr/bin/env python3
"""
score_agri_sample.py - compare the agriculturist's signed sample marks with the S the CURRENT pipeline gives, and test one alternative slope rule (analysis only).

    python scripts/score_agri_sample.py                      # prints the results
    python scripts/score_agri_sample.py --write-doc docs/SAMPLE_VALIDATION_RESULT.md --write-csv data/validation/agri_sample_results_20261007.csv

Input : data/validation/agri_sample_marks_20261007.csv (Alexis P. Santos, OIC-MAO, signed 7 Oct 2026; S Suitable, M Marginal, N Not suitable, X Cannot judge)
Method: S is recomputed for each (grid point, species) pair with pipeline/score_sites.py score_pairs (the same function that makes site_scores.db); the model says "suitable" when S >= 0.50.
        Agreement and Cohen's kappa are worked out two ways: Marginal counted as Suitable, and Marginal counted as Not suitable. X (cannot judge) pairs are left out of both.
        Optional --sheet <csv with columns sample_id, printed_verdict (S/M/N)>: the verdicts printed on the paper sheet (dataset v0.1-draft). They are NOT in the repository, so without
        this file the comparison with the printed sheet is skipped and the script says so.
Slope sensitivity (NOT production): the production rule zeroes S where slope > max_slope_pct (a gate). The alternative lets the slope factor fall instead:
        slope factor = max(0, 1 - (slope - max) / (0.5 * max)), the gate removed for slope only; every other gate and factor is unchanged.
This does not validate the model: see the limits written into the report.
"""
import argparse, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import score_sites as ss  # noqa: E402

S_MIN = 0.50                                   # S >= this = the model says "suitable" (the cut-off of all plans)
SLOPE_MODE_SAMPLE = "hard"                        # the printed sheet was made with the hard slope gate: score it that way (round 18)
MARKS = ROOT / "data" / "validation" / "agri_sample_marks_20261007.csv"


def group_of(category):
    c = str(category)
    if c.startswith("High-Value Crop"):
        return "high-value crop"
    if c.startswith("Native Timber"):
        return "native timber"
    return "other (fruit, ornamental, grass)"


def cohen_kappa(a, b):
    """Cohen's kappa of two binary lists (None when it is undefined: both raters constant and equal)."""
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    n = len(a)
    if n == 0:
        return None
    po = float((a == b).mean())
    pe = float(a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean()))
    return None if abs(1 - pe) < 1e-12 else (po - pe) / (1 - pe)


def fmt_k(k):
    return "undefined" if k is None else f"{k:.2f}"


def load_scores(sites_needed=None):
    species = pd.read_csv(ROOT / "data" / "processed" / "species_clean.csv")
    sites = pd.read_csv(ROOT / "data" / "processed" / "site_points_clean.csv")
    if sites_needed is not None:
        sites = sites[sites.point_id.isin(sites_needed)].copy()
    water = ss.distance_to_water(sites, str(ROOT / "data" / "SMR_WATERBODIES_POLY.shp"))
    sites["water_dist_m"] = water.to_numpy()
    return species, sites, ss.score_pairs(species, sites, slope_mode=SLOPE_MODE_SAMPLE)


def alt_slope_scores(species, sites, pairs):
    """For every pair: (S under the alternative slope rule, overage = slope - max). Production S is untouched."""
    sp = species.set_index("species_id")
    st = sites.set_index("point_id")
    slope = st.slope_pct.reindex(pairs.point_id).to_numpy(dtype=float)
    smax = sp.max_slope_pct.reindex(pairs.species_id).to_numpy(dtype=float)
    over = slope - smax
    f_alt = np.where(over > 0, np.maximum(0.0, 1 - over / (0.5 * smax)), np.nan)
    w = ss.TERM_WEIGHTS
    num = np.zeros(len(pairs)); den = np.zeros(len(pairs))
    for k in ("elevation", "slope", "soil", "wetness"):
        f = pairs["f_" + k].to_numpy(dtype=float)
        if k == "slope":
            f = np.where(over > 0, f_alt, f)
        ok = ~np.isnan(f)
        num += np.where(ok, w[k] * np.nan_to_num(f), 0.0); den += np.where(ok, w[k], 0.0)
    s_alt = np.where(den > 0, num / np.where(den > 0, den, 1), 0.0)
    gates_other = ~pairs.gate_fail_legal_zone.to_numpy() & ~pairs.gate_fail_elevation.to_numpy() & ~pairs.gate_fail_soil.to_numpy()
    s_alt = np.where(gates_other, s_alt, 0.0)
    s_new = np.where(pairs.gate_fail_slope.to_numpy(), s_alt, pairs.s_rule.to_numpy())
    return s_new, over


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--marks", default=str(MARKS))
    ap.add_argument("--sheet", help="CSV of the verdicts printed on the paper sheet: sample_id, printed_verdict (S, M or N)")
    ap.add_argument("--write-doc")
    ap.add_argument("--write-csv")
    a = ap.parse_args(argv)
    marks = pd.read_csv(a.marks, comment="#")
    species, sites, pairs = load_scores()
    sp = species.set_index("common_name")
    marks["species_id"] = marks.species.map(sp.species_id)
    assert marks.species_id.notna().all(), "a species name of the sample is not in species_clean.csv"
    p = pairs.set_index(["point_id", "species_id"])
    st = sites.set_index("point_id")
    rows = []
    for r in marks.itertuples(index=False):
        x = p.loc[(r.grid, int(r.species_id))]
        sr = sp.loc[r.species]
        gates = [g for g in ("legal_zone", "elevation", "slope", "soil") if x["gate_fail_" + g]]
        rows.append({"sample_id": r.sample_id, "grid": r.grid, "species": r.species, "mark": r.mark, "S_today": round(float(x.s_rule), 4), "model_suitable": bool(x.s_rule >= S_MIN),
                     "gate_failed": ";".join(gates), "elev_m": st.elev_m[r.grid], "slope_pct": st.slope_pct[r.grid], "max_slope_pct": sr.max_slope_pct,
                     "elev_range": f"{sr.elev_min_m:g}-{sr.elev_max_m:g}", "group": group_of(sr.category_raw)})
    res = pd.DataFrame(rows)
    out = []
    P = out.append
    # ---- check against the stored table of the pipeline
    import sqlite3
    con = sqlite3.connect(ROOT / "data" / "processed" / "scores" / "site_scores.db")
    stored = {(int(a), int(b)): c for a, b, c in con.execute("select point_id, species_id, s_rule from site_scores where point_id in (%s)" % ",".join(str(int(g)) for g in res.grid.unique()))}
    diff = [(r.sample_id) for r, sid in zip(res.itertuples(index=False), marks.species_id) if abs(stored.get((int(r.grid), int(sid)), -1) - r.S_today) > 1e-6]
    P(f"S recomputed for {len(res)} pairs; identical to the stored site_scores.db value for all but {len(diff)} ({diff}).")
    if diff:
        P("These differ only because the stored site_scores.db is now made with the graded slope rule (round 18) and the sample is scored with the hard gate, as printed.")
    judged = res[res.mark != "X"].copy()
    P(f"Marks: {res.mark.value_counts().to_dict()}; judged pairs {len(judged)}, cannot judge {int((res.mark == 'X').sum())} ({', '.join(res[res.mark == 'X'].sample_id)}).")
    P(f"Model verdict today (S >= {S_MIN}): suitable {int(judged.model_suitable.sum())}, not suitable {int((~judged.model_suitable).sum())} of {len(judged)} judged pairs.")
    schemes = {"Marginal counted as Suitable": judged.mark.isin(["S", "M"]).to_numpy(), "Marginal counted as Not suitable": (judged.mark == "S").to_numpy()}
    model = judged.model_suitable.to_numpy()
    summary = {}
    for name, ex in schemes.items():
        agree = float((ex == model).mean())
        k = cohen_kappa(ex, model)
        summary[name] = (agree, k)
        P(f"{name}: agreement {agree:.1%} ({int((ex == model).sum())} of {len(judged)}), Cohen's kappa {fmt_k(k)}.")
        by = []
        for g, d in judged.assign(ex=ex).groupby("group"):
            by.append(f"{g}: {int((d.ex == d.model_suitable).sum())}/{len(d)} agree, kappa {fmt_k(cohen_kappa(d.ex, d.model_suitable))}")
        P("   by group: " + "; ".join(by))
        by = []
        for m, d in judged.assign(ex=ex).groupby("mark"):
            by.append(f"mark {m}: {int((d.ex == d.model_suitable).sum())}/{len(d)} agree")
        P("   by mark: " + "; ".join(by))
    dis = judged[(judged.mark == "S") & ~judged.model_suitable]
    P(f"Pairs the agriculturist marked Suitable but the model says not suitable (S below {S_MIN}): {len(dis)}: " + "; ".join(f"{r.sample_id} {r.species} grid {r.grid} S={r.S_today:.2f} gate {r.gate_failed or 'none'}" for r in dis.itertuples()))
    mm = judged[(judged.mark == "M") & judged.model_suitable]
    P(f"Pairs marked Marginal where the model says suitable: {len(mm)} ({', '.join(mm.sample_id)}).")
    printed_info = None
    sheet = a.sheet or str(ROOT / "data" / "validation" / "sample_printed_verdicts.csv")      # round 15b: the default place of the printed-sheet verdicts
    if Path(sheet).is_file():
        sh = pd.read_csv(sheet, comment="#")
        sh["printed_verdict"] = sh.printed_verdict.astype(str).str.strip().str[:1].str.upper().where(sh.printed_verdict.notna())          # Suitable / S -> S, Marginal / M -> M, Not suitable / N -> N
        assert set(sh.printed_verdict.dropna()) <= {"S", "M", "N"}, "printed_verdict must be Suitable, Marginal or Not suitable (or S, M, N)"
        j = res.merge(sh[["sample_id", "printed_verdict"]], on="sample_id", how="left")
        j["today_class"] = np.where(j.model_suitable, "S", "N")
        changed = j[(j.printed_verdict == "S") & ~j.model_suitable | (j.printed_verdict == "N") & j.model_suitable | (j.printed_verdict == "M")]
        P(f"Printed-sheet verdicts read from {Path(sheet).name} ({int(j.printed_verdict.notna().sum())} of {len(j)} pairs). Pairs whose verdict changed between the printed sheet and today (S now = suitable at S >= 0.50, N = not): "
          f"{int(((j.printed_verdict == 'S') & ~j.model_suitable).sum()) + int(((j.printed_verdict == 'N') & j.model_suitable).sum())} changed, {int((j.printed_verdict == 'M').sum())} printed Marginal (listed too):")
        for r in changed.itertuples():
            P(f"   {r.sample_id} {r.species} grid {r.grid}: printed {r.printed_verdict}, today {r.today_class} (S {r.S_today:.2f}, gate {r.gate_failed or 'none'}), agriculturist mark {r.mark}")
        missing = j[j.printed_verdict.isna()].sample_id.tolist()
        if missing:
            P(f"   no printed verdict given for: {', '.join(missing)}")
        # ---- the verdicts PRINTED on the sheet (the system's verdict at the time) against the agriculturist's marks
        jj = j[(j.mark != "X") & j.printed_verdict.notna()].copy()
        pr_s = (jj.printed_verdict == "S").to_numpy()
        printed_rows = []
        P(f"PRINTED SHEET against the AGRICULTURIST ({len(jj)} judged pairs; the sheet printed Suitable for {int(pr_s.sum())} and Not suitable for {int((~pr_s).sum())} of them; the sheet was made with the hard slope gate):")
        for name, ex in {"Marginal counted as Suitable": jj.mark.isin(["S", "M"]).to_numpy(), "Marginal counted as Not suitable": (jj.mark == "S").to_numpy()}.items():
            ag, kp = float((ex == pr_s).mean()), cohen_kappa(ex, pr_s)
            printed_rows.append((name, ag, int((ex == pr_s).sum()), len(jj), kp))
            P(f"   {name}: agreement {ag:.1%} ({int((ex == pr_s).sum())} of {len(jj)}), Cohen's kappa {fmt_k(kp)}")
        by_group = []
        for g, d in jj.groupby("group"):
            by_group.append((g, int(((d.mark == "S").to_numpy() == (d.printed_verdict == "S").to_numpy()).sum()), len(d)))
        P("   by group (Marginal counted as Not suitable): " + "; ".join(f"{g}: {n}/{m} agree" for g, n, m in by_group))
        printed_dis = jj[(jj.mark.isin(["S", "M"])) & (jj.printed_verdict == "N")]
        printed_yes_not = jj[(jj.mark == "M") & (jj.printed_verdict == "S")]
        P(f"   marked Suitable or Marginal by the agriculturist but printed Not suitable: {len(printed_dis)}: " + ", ".join(f"{r.sample_id} {r.species} (mark {r.mark}, today S {r.S_today:.2f}, gate {r.gate_failed or 'none'})" for r in printed_dis.itertuples()))
        P(f"   marked Marginal but printed Suitable: {len(printed_yes_not)} ({', '.join(printed_yes_not.sample_id)})")
        same_today = int(((jj.printed_verdict == "S") == jj.model_suitable).sum())
        P(f"   today's hard-gate verdict equals the printed verdict for {same_today} of {len(jj)} judged pairs (the others are listed above as changed since the sheet).")
        printed_info = {"rows": printed_rows, "by_group": by_group, "dis": printed_dis, "marg_yes": printed_yes_not, "n": len(jj), "n_yes": int(pr_s.sum()), "same_today": same_today,
                        "changed": changed, "n_changed_ns": int(((j.printed_verdict == 'S') & ~j.model_suitable).sum()) + int(((j.printed_verdict == 'N') & j.model_suitable).sum()),
                        "n_sheet": int(j.printed_verdict.notna().sum())}
    else:
        P("Pairs where today's verdict differs from the verdict printed on the sheet: NOT DONE. data/validation/sample_printed_verdicts.csv (sample_id, printed_verdict) is not there yet; put it there or pass --sheet and run again.")
    # ---- slope sensitivity
    s_new, over = alt_slope_scores(species, sites, pairs)
    pairs = pairs.assign(S_alt=s_new, overage=over)
    pa = pairs.set_index(["point_id", "species_id"])
    fail = res[res.gate_failed.str.contains("slope")]
    P(f"SLOPE SENSITIVITY (analysis only): {len(fail)} sample pairs fail on slope (the request expected 7).")
    slope_rows = []
    for r in fail.itertuples():
        x = pa.loc[(r.grid, int(sp.loc[r.species].species_id))]
        slope_rows.append({"sample_id": r.sample_id, "species": r.species, "grid": r.grid, "mark": r.mark, "slope_pct": r.slope_pct, "max_slope_pct": r.max_slope_pct, "overage": round(float(x.overage), 1),
                           "S_today": r.S_today, "S_alt": round(float(x.S_alt), 3), "crosses_050": bool(x.S_alt >= S_MIN)})
        P(f"   {r.sample_id} {r.species} grid {r.grid} (mark {r.mark}): slope {r.slope_pct:.1f}% against the limit {r.max_slope_pct:g}% -> over by {x.overage:.1f} points; S today {r.S_today:.2f}, alternative S {x.S_alt:.3f}"
          f"{' (crosses 0.50)' if x.S_alt >= S_MIN else ' (stays below 0.50)'}")
    all_sq = sites.point_id[sites.zoning_status.isin(["confirmed", "unconfirmed"])]
    scored = pairs[pairs.point_id.isin(all_sq)]
    base_all = int((scored.s_rule >= S_MIN).sum())
    gain_all = int(((scored.s_rule < S_MIN) & (scored.S_alt >= S_MIN)).sum())
    P(f"Whole grid today ({scored.point_id.nunique()} scored squares, {len(scored)} pairs): {base_all} pairs have S >= 0.50; the alternative slope rule would ADD {gain_all} (to {base_all + gain_all}).")
    # the grid before round 15a: Cemetery squares were scored then; Special Reserved, industrial, commercial and landfill squares were not (the MPDC answers of 7 Oct 2026 changed that)
    reopened = ["Special Reserved Zone", "Medium Industrial Zone", "Minor Commercial - Mixed Use Zone", "Light Industrial Zone", "Sanitary Landfill"]
    old_sites = sites[(sites.zoning_status.isin(["confirmed", "unconfirmed"]) & ~sites.zone_desc.isin(reopened)) | (sites.zone_desc == "Cemetery Zone")].copy()
    old_sites["zoning_status"] = np.where(old_sites.zone_desc == "Cemetery Zone", "confirmed", old_sites.zoning_status)
    old_pairs = ss.score_pairs(species, old_sites, slope_mode=SLOPE_MODE_SAMPLE)
    s_old_alt, _ = alt_slope_scores(species, old_sites, old_pairs)
    b2, g2 = int((old_pairs.s_rule >= S_MIN).sum()), int(((old_pairs.s_rule < S_MIN) & (s_old_alt >= S_MIN)).sum())
    P(f"On the grid before round 15a ({old_sites.point_id.nunique()} squares, the Cemetery zone still scored): {b2} pairs with S >= 0.50 (the 228,919 of before); the alternative rule would add {g2}.")
    rob = res[res.species.str.contains("Robusta")]
    P("ROBUSTA elevation: the data gives " + ", ".join(sorted(set(rob.elev_range))) + " m; the three Robusta pairs the agriculturist marked Suitable lie at "
      + ", ".join(f"{r.sample_id} {r.elev_m:g} m (model S {r.S_today:.2f}, gate {r.gate_failed or 'none'})" for r in rob.itertuples()) + ".")
    if a.write_csv:
        res.drop(columns=["group"]).to_csv(a.write_csv, index=False)
    text = "\n".join(out)
    print(text)
    if a.write_doc:
        Path(a.write_doc).write_text(render_doc(text, summary, res, judged, slope_rows, base_all, gain_all, b2, g2, rob, dis, mm, printed_info), encoding="utf-8")
        print("written", a.write_doc)


def printed_section(pi):
    """The markdown of the section 'The printed sheet against the agriculturist' (or the note that the sheet is missing)."""
    if pi is None:
        return "## The printed sheet against the agriculturist\nNOT DONE: `data/validation/sample_printed_verdicts.csv` (sample_id, printed_verdict) was not found.\n"
    ks = "\n".join(f"| {n} | {ag:.1%} ({a} of {m}) | {fmt_k(k)} |" for n, ag, a, m, k in pi["rows"])
    grp = "\n".join(f"| {g} | {n} of {m} |" for g, n, m in pi["by_group"])
    dis = "\n".join(f"| {r.sample_id} | {r.species} | {r.grid} | {r.mark} | {r.S_today:.2f} | {r.gate_failed or 'none'} |" for r in pi["dis"].itertuples()) or "| none | | | | | |"
    ch = "\n".join(f"| {r.sample_id} | {r.species} | {r.grid} | {r.printed_verdict} | {'S' if r.model_suitable else 'N'} | {r.S_today:.2f} | {r.gate_failed or 'none'} | {r.mark} |" for r in pi["changed"].itertuples())
    changed_md = ("No pair changed between the printed sheet and today (all " + str(pi["n_sheet"]) + " printed verdicts are reproduced by the hard gate)." if pi["n_changed_ns"] == 0 else "Pairs whose verdict changed between the printed sheet and today (" + str(pi["n_changed_ns"]) + " changed; printed / today / S today / gate / mark):\n\n| Sample | Species | Grid | Printed | Today | S today | Gate | Mark |\n|---|---|---|---|---|---|---|---|\n" + ch)
    return f"""## The printed sheet against the agriculturist
The verdicts that were PRINTED on the sheet (`data/validation/sample_printed_verdicts.csv`, 40 pairs: the system's verdict at the time) compared with the marks of the agriculturist. The sheet was made under the **hard slope gate**, so this part (like all the numbers in this document) is scored with SLOPE_MODE = "hard".

{pi['n']} judged pairs (the 4 marked Cannot judge are left out); the sheet printed Suitable for {pi['n_yes']} of them and Not suitable for {pi['n'] - pi['n_yes']}.

| Marginal counted as | Agreement of the printed verdict with the agriculturist | Cohen's kappa |
|---|---|---|
{ks}

By group (Marginal counted as Not suitable):

| Group | Agree |
|---|---|
{grp}

Pairs the agriculturist marked Suitable or Marginal but the sheet printed as Not suitable ({len(pi['dis'])}):

| Sample | Species | Grid | Mark | S today | Gate failed today |
|---|---|---|---|---|---|
{dis}

Pairs marked Marginal but printed Suitable: {len(pi['marg_yes'])} ({', '.join(pi['marg_yes'].sample_id) or 'none'}).

Printed verdict against today's hard-gate verdict (S >= 0.50): the same for {pi['same_today']} of {pi['n']} judged pairs. {changed_md}

"""


def render_doc(text, summary, res, judged, slope_rows, base_all, gain_all, b2, g2, rob, dis, mm, printed_info=None):
    ks = "\n".join(f"| {n} | {ag:.1%} | {fmt_k(k)} |" for n, (ag, k) in summary.items())
    sl = "\n".join(f"| {r['sample_id']} | {r['species']} | {r['grid']} | {r['mark']} | {r['slope_pct']:.1f} | {r['max_slope_pct']:g} | {r['overage']:+.1f} | {r['S_today']:.2f} | {r['S_alt']:.3f} | {'yes' if r['crosses_050'] else 'no'} |" for r in slope_rows)
    disagree = "\n".join(f"| {r.sample_id} | {r.species} | {r.grid} | {r.mark} | {r.S_today:.2f} | {r.gate_failed or 'none'} |" for r in judged[(judged.mark.isin(['S', 'M'])) & (~judged.model_suitable)].itertuples())
    rb = "\n".join(f"| {r.sample_id} | {r.grid} | {r.elev_m:g} | {r.elev_range} | {r.S_today:.2f} | {r.gate_failed or 'none'} |" for r in rob.itertuples())
    return f"""# Sample validation result (agriculturist marks, 7 Oct 2026)

**This does not validate the model.** It compares one reviewer's marks on 40 sample pairs with the site score S that the current pipeline gives. It is a first look at where the rules and a farm expert disagree, nothing more.

## What was compared
- Marks: `data/validation/agri_sample_marks_20261007.csv`: Alexis P. Santos, OIC-MAO, signed 7 Oct 2026, sheet of dataset v0.1-draft (hash 3483e2b668e8), 7 of the 8 pages signed, no comments. S = Suitable, M = Marginal, N = Not suitable, X = Cannot judge.
- Model: S recomputed for each (grid point, species) pair with `pipeline/score_sites.py` (the current pipeline, release v1.0-review, LGU soil layer, the zone rules of round 15a). The model says "suitable" when S >= 0.50.
- **Slope rule: this comparison is scored with SLOPE_MODE = "hard"** (the slope gate as it was when the sheet was printed). The graded slope rule of round 18 (the production default since then, provisional, awaiting adviser confirmation) is NOT used here, so the numbers below are the ones of the printed sheet.
- Marks given: {res.mark.value_counts().to_dict()}. Four pairs (X) were left out of every figure below.

## Agreement
| Marginal counted as | Agreement | Cohen's kappa |
|---|---|---|
{ks}

Reading: about two thirds of the judged pairs agree either way. When Marginal counts as Suitable the reviewer says "suitable" for every judged pair, so there is nothing for kappa to measure (0.00 = no better than chance); when Marginal counts as Not suitable kappa is {fmt_k(summary['Marginal counted as Not suitable'][1])}, a weak agreement.

Pairs the reviewer marked Suitable or Marginal but the model scores below 0.50:

| Sample | Species | Grid | Mark | S today | Gate failed |
|---|---|---|---|---|---|
{disagree}

## Slope sensitivity (analysis only; production scoring is unchanged)
{len(slope_rows)} of the 40 sample pairs fail on slope today ({sum(1 for r in slope_rows if r['mark'] != 'X')} judged, {sum(1 for r in slope_rows if r['mark'] == 'X')} marked Cannot judge); the request expected 7, so the list below has the two more that the script found.

Production rule: S = 0 where the slope is steeper than the species limit (a gate). Alternative: slope factor = max(0, 1 - (slope - max) / (0.5 x max)), so a slope slightly over the limit lowers S instead of zeroing it. Every other gate and factor stays the same.

| Sample | Species | Grid | Mark | Slope % | Limit % | Over | S today | S alternative | Crosses 0.50 |
|---|---|---|---|---|---|---|---|---|---|
{sl}

- On today's grid the alternative rule would add {gain_all} pairs with S >= 0.50 to the {base_all} that have it now.
- On the grid before round 15a (7,530 squares, Cemetery scored, the base of the 228,919 pairs) it would add {g2} to {b2}.

{printed_section(printed_info)}
## Robusta and elevation
The data gives Robusta an elevation range of 300 to 800 m. The reviewer marked all three Robusta pairs Suitable, at much lower places:

| Sample | Grid | Elevation (m) | Range in the data (m) | S today | Gate failed |
|---|---|---|---|---|---|
{rb}

## Limits
- One reviewer, one afternoon, 40 pairs (36 judged, 4 "cannot judge"); 7 of the 8 pages of the sheet were signed.
- There are no "Not suitable" marks at all, so the sample cannot show whether the model correctly rejects bad pairs; agreement is mostly "model also says suitable".
- The 40 pairs were chosen for review, not drawn to represent all 360,450 pairs.
- "Marginal" has no fixed meaning in the model, so it is counted both ways.
{"- The printed verdicts (data/validation/sample_printed_verdicts.csv) are compared above; the sheet was made with the dataset v0.1-draft, so its verdicts are not the verdicts of today's data." if printed_info else "- The printed sheet (dataset v0.1-draft) is not in the repository, so today's verdicts could not be compared with the verdicts printed on the sheet."}
- The marks are a judgement, not a measurement of survival. Nothing here proves that trees survive where S is high.

## Full printout
```
{text}
```
"""


if __name__ == "__main__":
    main()
