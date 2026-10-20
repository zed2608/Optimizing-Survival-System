"""
Reader of the species pH evidence file and of the rain / temperature agreement file (display only; no score reads them; no network).

  data/reference/species_ph_evidence.csv        - made by scripts/build_species_ph_evidence.py (quoted ranges "from a source, not yet signed by the agriculturist")
  data/reference/species_climate_agreement.csv  - does the cited page match the draft rain / temperature range?

A missing file gives None / {} (the caller shows "no confirmed range"); nothing is ever invented or filled in from species_clean.csv.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "reference" / "species_ph_evidence.csv"
AGREEMENT = ROOT / "data" / "reference" / "species_climate_agreement.csv"
DATASET = ROOT / "data" / "reference" / "species_ph_dataset.csv"        # the project species dataset (scripts/build_species_ph_dataset.py): the WORKING pH range of all 45 species
DATASET_LABEL = "Project species dataset"
TAG = "mula sa sanggunian; hindi pa pirmado ng agriculturist"
NONE_TEXT = "Walang nakumpirmang pH range"


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _rank(v):
    f = _num(v)
    return None if f is None else int(f)


@lru_cache(maxsize=4)
def _load(path):
    p = Path(path)
    if not p.is_file():
        return None
    out = {}
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out[int(r["species_id"])] = r
    return out


def load(path=None):
    """{species_id: raw row (strings)} or None when the file is missing."""
    return _load(str(path or EVIDENCE))


def reference(species_id, path=None):
    """The `ph_reference` block of one species. None when there is no evidence file at all. For status none: no range, no link, no rank."""
    t = load(path)
    if t is None or int(species_id) not in t:
        return None
    r = t[int(species_id)]
    if r["status"] != "sourced":
        return {"status": "none", "verdict_kind": "none", "verdict_min": None, "verdict_max": None, "tol_min": None, "tol_max": None, "opt_min": None, "opt_max": None, "listed_min": None, "listed_max": None,
                "source_name": None, "source_url": None, "source_rank": None, "quote": None, "conflict": False, "scope": None, "text": NONE_TEXT, "note": r.get("note") or None, "provisional_tag": TAG}
    return {"status": "sourced", "verdict_kind": r["verdict_kind"], "verdict_min": _num(r["verdict_min"]), "verdict_max": _num(r["verdict_max"]),
            "tol_min": _num(r["tol_min"]), "tol_max": _num(r["tol_max"]), "opt_min": _num(r["opt_min"]), "opt_max": _num(r["opt_max"]), "listed_min": _num(r["listed_min"]), "listed_max": _num(r["listed_max"]),
            "source_name": r["source_name"], "source_url": r["source_url"], "source_rank": _rank(r["source_rank"]), "source_kind": r["source_kind"], "quote": r["quote"], "conflict": r["conflict"] == "yes",
            "scope": r["scope"], "note": r.get("note") or None, "text": None, "provisional_tag": TAG}


def verdict_range(species_id, path=None):
    """(min, max, kind) used by the Species card comparison. (None, None, 'none') when there is no confirmed range or no file: never the old species_clean values."""
    ref = reference(species_id, path)
    if ref is None or ref["status"] != "sourced":
        return None, None, "none"
    return ref["verdict_min"], ref["verdict_max"], ref["verdict_kind"]


@lru_cache(maxsize=4)
def _dataset(path):
    p = Path(path)
    if not p.is_file():
        return None
    out = {}
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out[int(r["species_id"])] = r
    return out


def dataset_range(species_id, path=None):
    """(min, max) of the project species dataset for one species, or (None, None) when the file or the species is missing (nothing is guessed)."""
    r = (_dataset(str(path or DATASET)) or {}).get(int(species_id))
    if not r:
        return None, None
    return _num(r["ph_min"]), _num(r["ph_max"])


def working_range(species_id, dataset_path=None):
    """(min, max, kind) used by every verdict: the project species dataset range, kind 'listed' (the dataset gives one range, it does not say tolerated or best). 'none' only when the dataset file is missing."""
    lo, hi = dataset_range(species_id, dataset_path)
    if lo is None or hi is None:
        return None, None, "none"
    return lo, hi, "listed"


def dataset_reference(species_id, dataset_path=None, evidence_path=None):
    """The `ph_reference` block shown by the dashboard: the dataset range (same field names as the older evidence block so that the screens keep working), the authority and link the dataset lists, and
    `other_published` = the range of the evidence file when it differs (a cross-reference only; never used for a verdict). None when the dataset has no row for the species."""
    r = (_dataset(str(dataset_path or DATASET)) or {}).get(int(species_id))
    if not r:
        return None
    lo, hi = _num(r["ph_min"]), _num(r["ph_max"])
    other = None
    ev = reference(species_id, evidence_path)
    if ev and ev["status"] == "sourced" and ev["verdict_min"] is not None and ev["verdict_max"] is not None:
        if abs(ev["verdict_min"] - lo) > 0.05 or abs(ev["verdict_max"] - hi) > 0.05:
            other = {"min": ev["verdict_min"], "max": ev["verdict_max"], "kind": ev["verdict_kind"], "source_name": ev["source_name"], "source_url": ev["source_url"]}
    return {"status": "sourced", "verdict_kind": "listed", "verdict_min": lo, "verdict_max": hi, "tol_min": None, "tol_max": None, "opt_min": None, "opt_max": None, "listed_min": lo, "listed_max": hi,
            "source_name": r["authority_listed"], "source_url": r["reference_url"], "source_rank": None, "source_kind": "dataset", "quote": None, "conflict": False, "scope": "species", "note": None, "text": None,
            "provisional_tag": DATASET_LABEL, "source_label": r["source_label"], "authority_listed": r["authority_listed"], "other_published": other}


@lru_cache(maxsize=4)
def _agreement(path):
    p = Path(path)
    if not p.is_file():
        return None
    out = {}
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out[(int(r["species_id"]), r["parameter"])] = r
    return out


def climate_match(species_id, parameter, path=None):
    """The matching page for rain ('rain') or temperature ('temp') when the cross-check found it matches the draft: {source_url, quote}; otherwise None (the caller must not show a source link)."""
    t = _agreement(str(path or AGREEMENT))
    r = (t or {}).get((int(species_id), parameter))
    if not r or r["agreement"] != "match":
        return None
    return {"source_url": r["source_url_if_match"], "quote": r["quote_if_match"]}
