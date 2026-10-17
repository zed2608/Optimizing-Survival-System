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
