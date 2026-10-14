"""
A form for the licensed agriculturist to check the climate and soil values of the 45 species (stage C1). Scripts: scripts/make_species_verification_sheet.py (makes the PDF to print and the CSV to fill)
and scripts/import_species_verification.py (reads the returned CSV and writes a REPORT).

NOTHING here changes the species table, the release hash, the scores or any file in data/processed: the sheet only READS data/processed/species_clean.csv, species_sources.csv and dataset_release.txt, and
writes new dated files in data/validation/ (an existing file is never overwritten: a number is added to the name). A corrected value from the reviewer would go into a NEW release of the species data
(a new tag and hash), decided by the team; this module never applies it.

One row per species x attribute that HAS a value (45 species x 8 attributes, minus the gaps). The attributes: ph_min, ph_max, rain_min_mm, rain_max_mm, temp_min_c, temp_max_c,
preferred_climate_seasons and corona_raw (the climate types, "Type I" and so on).
"""
from __future__ import annotations

import csv
import math
import re
import textwrap
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
VALIDATION = ROOT / "data" / "validation"
ATTRIBUTES = [  # (field name, label in English / Filipino, unit)
    ("ph_min", "Soil pH, lowest", "Pinakamababang pH ng lupa", ""),
    ("ph_max", "Soil pH, highest", "Pinakamataas na pH ng lupa", ""),
    ("rain_min_mm", "Yearly rain, least", "Pinakakaunting ulan sa isang taon", "mm"),
    ("rain_max_mm", "Yearly rain, most", "Pinakamaraming ulan sa isang taon", "mm"),
    ("temp_min_c", "Temperature, lowest", "Pinakamababang temperatura", "°C"),
    ("temp_max_c", "Temperature, highest", "Pinakamataas na temperatura", "°C"),
    ("preferred_climate_seasons", "Preferred climate", "Gustong klima", ""),
    ("corona_raw", "Climate types, Type I and others", "Mga uri ng klima (Type I at iba pa)", ""),
]
ATTR_NAMES = [a[0] for a in ATTRIBUTES]
NUMERIC = {"ph_min", "ph_max", "rain_min_mm", "rain_max_mm", "temp_min_c", "temp_max_c"}
RESPONSE_COLUMNS = ["verdict", "corrected_value", "remarks", "reviewer", "date"]
SHEET_COLUMNS = ["row_id", "species_id", "common_name", "scientific_name", "attribute", "current_value", "unit", "source_rank", "source", "source_note"] + RESPONSE_COLUMNS
VERDICTS = {"tama": "correct", "correct": "correct", "palitan": "replace", "replace": "replace", "": ""}
PROVISIONAL_LINE = "PROVISIONAL: hindi pa napatutunayan"
TITLE = "Pagsusuri ng klima at lupa ng 45 puno (para sa agriculturist)"


def release_info(processed=None):
    """(tag, combined 12-character hash) from dataset_release.txt."""
    txt = (Path(processed or PROCESSED) / "dataset_release.txt").read_text(encoding="utf-8")
    tag = re.search(r"dataset release (\S+)", txt)
    h = re.search(r"combined hash \(12 characters\): (\w{12})", txt)
    if not tag or not h:
        raise ValueError("dataset_release.txt has no release tag or no combined hash")
    return tag.group(1), h.group(1)


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _fmt_number(v):
    f = float(v)
    return str(int(f)) if f == int(f) else str(f)


def build_rows(processed=None):
    """The rows of the form (a list of dicts with SHEET_COLUMNS, the response columns empty). Reads the species table and the sources table; changes nothing."""
    processed = Path(processed or PROCESSED)
    sp = pd.read_csv(processed / "species_clean.csv")
    src = pd.read_csv(processed / "species_sources.csv")
    cell = {(int(r.species_id), r.field_name): r for r in src.itertuples(index=False)}
    rows = []
    for s in sp.itertuples(index=False):
        for name, _en, _fil, unit in ATTRIBUTES:
            raw = getattr(s, name, None)
            v = _clean(raw)
            if not v:
                continue                                              # no value: no row (nothing is invented, nothing is asked about a gap)
            if name in NUMERIC:
                v = _fmt_number(v)
            c = cell.get((int(s.species_id), name))
            if c is None:
                rank, source, note = "", "", "no source recorded"
            else:
                rank = "" if pd.isna(c.source_rank) else str(int(c.source_rank))
                source = _clean(c.source_url)
                bits = []
                if bool(c.off_list):
                    bits.append("OFF-LIST (not on the supplied source list)")
                if _clean(c.flags):
                    bits.append("FLAGGED: " + _clean(c.flags))
                note = "; ".join(bits)
            rows.append({"row_id": f"{int(s.species_id)}|{name}", "species_id": int(s.species_id), "common_name": s.common_name, "scientific_name": _clean(s.scientific_name),
                         "attribute": name, "current_value": v, "unit": unit, "source_rank": rank, "source": source, "source_note": note, **{k: "" for k in RESPONSE_COLUMNS}})
    return rows


def dated_path(folder, stem, ext, day=None):
    """data/validation/<stem>_<YYYYMMDD>.<ext>; if it exists, <stem>_<YYYYMMDD>-2.<ext>, -3 ... (an existing file is never overwritten)."""
    day = (day or date.today()).strftime("%Y%m%d")
    folder = Path(folder)
    p = folder / f"{stem}_{day}.{ext}"
    n = 2
    while p.exists():
        p = folder / f"{stem}_{day}-{n}.{ext}"
        n += 1
    return p


def write_csv(rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


# ---------------------------------------------------------------------------------------------------- the PDF (matplotlib, as the field kit does)
PAGE_W, PAGE_H = 11.69, 8.27          # A4 landscape, inches
ROWS_PER_PAGE = 11


def write_pdf(rows, path, tag, hash12, built_on=None):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["pdf.fonttype"] = 42              # real text in the PDF (it can be searched and checked)
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    built_on = built_on or datetime.now().strftime("%Y-%m-%d %H:%M")
    pages = [rows[i:i + ROWS_PER_PAGE] for i in range(0, len(rows), ROWS_PER_PAGE)] or [[]]
    labels = {a[0]: (a[1], a[2]) for a in ATTRIBUTES}
    cols = [0.025, 0.20, 0.375, 0.535, 0.715]           # x of: species, attribute, current value, source, answer
    with PdfPages(path, metadata={"Title": TITLE, "Subject": f"dataset release {tag} hash {hash12}; {PROVISIONAL_LINE}", "Creator": "pipeline/species_verification.py"}) as pdf:
        for n, chunk in enumerate(pages, 1):
            fig = plt.figure(figsize=(PAGE_W, PAGE_H))
            fig.text(0.025, 0.955, TITLE, fontsize=15, fontweight="bold", va="top")
            fig.text(0.025, 0.925, f"Dataset release {tag}   |   hash {hash12}   |   ginawa noong {built_on}   |   pahina {n} sa {len(pages)}   |   {len(rows)} hilera", fontsize=8.5, va="top")
            fig.text(0.025, 0.905, PROVISIONAL_LINE, fontsize=10, fontweight="bold", color="#8b0000", va="top")
            fig.text(0.50, 0.905, "Lagyan ng tsek ang Tama, o isulat ang tamang halaga at ang sanggunian sa Puna.", fontsize=8, va="top")
            for x, head in zip(cols, ("Puno", "Katangian", "Kasalukuyang halaga", "Sanggunian (rank)", "Sagot")):
                fig.text(x, 0.872, head, fontsize=8.5, fontweight="bold", va="top")
            fig.add_artist(plt.Line2D([0.02, 0.98], [0.86, 0.86], color="black", lw=1, transform=fig.transFigure))
            top, step = 0.852, 0.0635
            for i, r in enumerate(chunk):
                y = top - i * step
                en, fil = labels[r["attribute"]]
                fig.text(cols[0], y, "\n".join(textwrap.wrap(f"{r['common_name']}", 22)) + "\n" + "\n".join(textwrap.wrap(r["scientific_name"], 26)[:1]), fontsize=7.5, va="top")
                fig.text(cols[1], y, "\n".join(textwrap.wrap(f"{fil}\n({en})", 28)[:3]), fontsize=7, va="top")
                value = f"{r['current_value']} {r['unit']}".strip()
                fig.text(cols[2], y, "\n".join(textwrap.wrap(value, 26)[:3]), fontsize=9, fontweight="bold", va="top")
                srcline = (r["source"] or "walang sanggunian")
                srcline = re.sub(r"^https?://", "", srcline)
                s = "\n".join(textwrap.wrap(srcline, 40)[:2]) + f"\nrank {r['source_rank'] or '?'}"
                if r["source_note"]:
                    s += "  " + r["source_note"][:46]
                fig.text(cols[3], y, s, fontsize=6.5, va="top", color="#8b0000" if r["source_note"] else "black")
                fig.text(cols[4], y, "[  ] Tama     [  ] Palitan sa: ____________\nPuna: __________________________", fontsize=7.5, va="top")
                fig.add_artist(plt.Line2D([0.02, 0.98], [y - step + 0.006, y - step + 0.006], color="#bbbbbb", lw=0.5, transform=fig.transFigure))
            fig.add_artist(plt.Line2D([0.02, 0.98], [0.105, 0.105], color="black", lw=1, transform=fig.transFigure))
            fig.text(0.025, 0.085, "Pangalan ng reviewer: ______________________________", fontsize=9, va="top")
            fig.text(0.38, 0.085, "Posisyon: ____________________________", fontsize=9, va="top")
            fig.text(0.65, 0.085, "Pirma: ________________________", fontsize=9, va="top")
            fig.text(0.86, 0.085, "Petsa: ____________", fontsize=9, va="top")
            fig.text(0.025, 0.04, f"{PROVISIONAL_LINE}  |  release {tag} {hash12}  |  walang binabago ang form na ito sa datos hangga't walang bagong release", fontsize=7, color="#555555")
            pdf.savefig(fig)
            plt.close(fig)
    return path


# ---------------------------------------------------------------------------------------------------- the import (a report only)
class VerificationError(ValueError):
    pass


def read_returned(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def check_returned(returned, processed=None):
    """Check a returned CSV against the form. Returns (rows with the verdict normalised to correct / replace / '', list of problems). Nothing is written."""
    base = {r["row_id"]: r for r in build_rows(processed)}
    species = {r["species_id"] for r in base.values()}
    problems, out, seen = [], [], set()
    if not returned:
        return [], ["the file has no rows"]
    missing_cols = [c for c in ("row_id", "species_id", "attribute", *RESPONSE_COLUMNS) if c not in returned[0]]
    if missing_cols:
        return [], [f"the file lacks the columns {missing_cols}"]
    for n, r in enumerate(returned, 2):
        where = f"row {n}"
        try:
            sid = int(float(r.get("species_id", "")))
        except ValueError:
            problems.append(f"{where}: species_id '{r.get('species_id', '')}' is not a number")
            continue
        if sid not in species:
            problems.append(f"{where}: unknown species_id {sid}")
            continue
        attr = r.get("attribute", "")
        if attr not in ATTR_NAMES:
            problems.append(f"{where}: unknown attribute '{attr}'")
            continue
        rid = f"{sid}|{attr}"
        if rid not in base:
            problems.append(f"{where}: {rid} is not a row of the form (that species has no value for it)")
            continue
        if r.get("row_id", rid) != rid:
            problems.append(f"{where}: row_id '{r.get('row_id')}' does not match species_id and attribute ({rid})")
            continue
        if rid in seen:
            problems.append(f"{where}: {rid} appears twice")
            continue
        seen.add(rid)
        v = VERDICTS.get(r.get("verdict", "").strip().lower())
        if v is None:
            problems.append(f"{where}: verdict '{r.get('verdict')}' is not Tama / correct, Palitan / replace, or empty")
            continue
        corrected = r.get("corrected_value", "").strip()
        if v == "replace":
            if not corrected:
                problems.append(f"{where}: verdict replace needs a corrected_value")
                continue
            if attr in NUMERIC:
                try:
                    float(corrected)
                except ValueError:
                    problems.append(f"{where}: corrected_value '{corrected}' is not a number")
                    continue
        if v == "correct" and corrected:
            problems.append(f"{where}: verdict correct but a corrected_value is written; use replace, or clear it")
            continue
        out.append({**base[rid], "verdict": v, "corrected_value": corrected, "remarks": r.get("remarks", ""), "reviewer": r.get("reviewer", ""), "date": r.get("date", "")})
    return out, problems


def summarise(checked, total_rows):
    n_ok = sum(1 for r in checked if r["verdict"] == "correct")
    n_rep = sum(1 for r in checked if r["verdict"] == "replace")
    return {"rows_in_form": total_rows, "correct": n_ok, "replaced": n_rep, "no_answer": total_rows - n_ok - n_rep,
            "replacements": [(r["species_id"], r["common_name"], r["attribute"], r["current_value"], r["corrected_value"], r["remarks"]) for r in checked if r["verdict"] == "replace"]}
