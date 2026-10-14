"""
Reference values for San Mateo's rainfall, climate type, temperature and soil pH (stage C1): data/config/climate_reference.csv, read and CHECKED here.
DISPLAY ONLY: nothing in this module (or in the file) enters any score. S, P, W, the Random Forest, the matching and the pair table never read it.

Rules the file must keep (checked by validate()):
  - every row has a key, a status and a date; a row with a NUMBER also has a source (and a station or scope);
  - a row with no value has the status "pending" (asked for, not received) or "no_layer" (no data exists in the repository): it is shown as "no data yet", never as zero;
  - a number is never invented: annual_rainfall_mm is a stand-in from the nearest listed PAGASA station and says so ("provisional_proxy").
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "config" / "climate_reference.csv"
COLUMNS = ["key", "value", "unit", "source", "source_url", "station_or_scope", "accessed_date", "status", "note"]
KEYS = ["annual_rainfall_mm", "climate_type", "annual_mean_temperature_c", "soil_ph"]
STATUSES = {"provisional_proxy", "provisional", "pending", "no_layer"}
EMPTY_STATUSES = {"pending", "no_layer"}
NUMERIC_KEYS = {"annual_rainfall_mm", "annual_mean_temperature_c", "soil_ph"}


class ReferenceError(ValueError):
    pass


def validate(rows):
    """Raise ReferenceError when a rule above is broken. rows = list of dicts (as read)."""
    keys = [r.get("key", "") for r in rows]
    if sorted(keys) != sorted(KEYS):
        raise ReferenceError(f"the file must have exactly the keys {KEYS}, it has {keys}")
    for r in rows:
        k, v, st = r["key"], (r.get("value") or "").strip(), (r.get("status") or "").strip()
        if st not in STATUSES:
            raise ReferenceError(f"{k}: status '{st}' is not one of {sorted(STATUSES)}")
        if not (r.get("accessed_date") or "").strip():
            raise ReferenceError(f"{k}: accessed_date is empty")
        if v:
            if st in EMPTY_STATUSES:
                raise ReferenceError(f"{k}: it has a value but the status says there is none ({st})")
            if not (r.get("source") or "").strip():
                raise ReferenceError(f"{k}: a value without a source")
            if not (r.get("station_or_scope") or "").strip():
                raise ReferenceError(f"{k}: a value without a station or scope")
            if k in NUMERIC_KEYS:
                try:
                    float(v)
                except ValueError:
                    raise ReferenceError(f"{k}: '{v}' is not a number")
        elif st not in EMPTY_STATUSES:
            raise ReferenceError(f"{k}: no value, so the status must be pending or no_layer (it is '{st}')")
    return True


def load(path=None):
    """{key: row dict} of the checked file; the value of a number is a float (None when there is no value)."""
    p = Path(PATH if path is None else path)
    with open(p, encoding="utf-8", newline="") as f:
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
    validate(rows)
    out = {}
    for r in rows:
        v = r["value"]
        r = dict(r)
        r["value"] = (float(v) if r["key"] in NUMERIC_KEYS else v) if v else None
        out[r["key"]] = r
    return out


def rain_assessment(rain_min, rain_max, annual):
    """How the reference annual rainfall of San Mateo compares with the species' own range: 'fits' | 'below' | 'above' | 'no_data'.
    'below' = the reference rainfall is LOWER than the species' range; 'above' = HIGHER. No reference or no range at all = 'no_data' (never a guess). One missing limit: only the other one is used."""
    def ok(x):
        return x is not None and not (isinstance(x, float) and math.isnan(x))
    if not ok(annual) or not (ok(rain_min) or ok(rain_max)):
        return "no_data"
    if ok(rain_min) and annual < rain_min:
        return "below"
    if ok(rain_max) and annual > rain_max:
        return "above"
    return "fits"


def for_species(ref, row):
    """What the API sends for one species (display only): the reference rows with their source, and the rain comparison. row = a species_clean row (dict or Series)."""
    def num(k):
        v = row.get(k)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(v) else v
    items = [{k: r[k] for k in COLUMNS} for r in (ref[key] for key in KEYS)] if ref else []
    annual = ref["annual_rainfall_mm"]["value"] if ref else None
    return {"items": items,
            "rain": {"assessment": rain_assessment(num("rain_min_mm"), num("rain_max_mm"), annual), "species_min_mm": num("rain_min_mm"), "species_max_mm": num("rain_max_mm"), "reference_mm": annual},
            "temperature": {"assessment": "no_data" if not ref or ref["annual_mean_temperature_c"]["value"] is None else "not_compared"},
            "ph": {"assessment": "no_data" if not ref or ref["soil_ph"]["value"] is None else "not_compared"},
            "scored": False,
            "note": "Reference only. This is not part of the score. The nearest listed station is used, not San Mateo itself."}
