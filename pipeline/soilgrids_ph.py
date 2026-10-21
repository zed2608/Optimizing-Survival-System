"""
Soil pH from SoilGrids 2.0 (ISRIC) as a REFERENCE ONLY (stage C2). Display only: no score, model, weight, threshold or eligibility reads it.

  python pipeline/soilgrids_ph.py fetch     # needs the internet: downloads phh2o (pH in water) for 0-5, 5-15 and 15-30 cm, mean + Q0.05 + Q0.95, native 250 m grid -> data/reference/raw/
  python pipeline/soilgrids_ph.py sample    # offline: the cell under the centre of each of the 8,088 squares -> data/reference/soilgrids_ph.csv (+ soilgrids_ph_report.txt)

What the numbers are (read this before using them):
  - a MODEL estimate (machine learning on world soil profiles), NOT a measurement in San Mateo; its own uncertainty is shown by Q0.05 and Q0.95;
  - the native cell is 250 m x 250 m (Homolosine grid, EPSG:152160), so several 100 m squares share one cell: the pH does not change from square to square inside a cell;
  - SoilGrids stores pH x 10 as a whole number (the service says "mapped_units pH*10", d_factor 10): every value is divided by 10;
  - the service gives the value 0 where it has no data (water, built-up land, outside its mask; a pH of 0 does not exist): 0 becomes EMPTY, never a pH, and an empty value is never filled in;
  - 0-30 cm is the depth-weighted mean of the three layers with weights 5, 10 and 15 cm (PROVISIONAL choice of depth; for Q0.05 and Q0.95 it is the same weighted mean of the layers' quantiles, which is an
    approximation, not the quantile of the 0-30 cm soil);
  - a square gets a value only when ALL THREE layers have one.
Licence: CC BY 4.0 (ISRIC - World Soil Information, SoilGrids 2.0, Poggio et al. 2021, https://www.isric.org/explore/soilgrids). Attribution: "pH: SoilGrids 2.0 (ISRIC), CC BY 4.0".
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference"
RAW = REF / "raw"
OUT_CSV = REF / "soilgrids_ph.csv"
OUT_REPORT = REF / "soilgrids_ph_report.txt"
MANIFEST = REF / "soilgrids_ph_download.json"
WCS = "https://maps.isric.org/mapserv?map=/map/phh2o.map"
IGH = "+proj=igh +lat_0=0 +lon_0=0 +datum=WGS84 +units=m +no_defs +type=crs"       # SoilGrids' own grid (ISRIC lists it as EPSG:152160)
DEPTHS = [("0-5cm", 5), ("5-15cm", 10), ("15-30cm", 15)]                           # (layer, thickness in cm = its weight in the 0-30 cm mean)
STATS = [("mean", "ph_mean_0_30"), ("Q0.05", "ph_q05_0_30"), ("Q0.95", "ph_q95_0_30")]
SOURCE = "SoilGrids 2.0, ISRIC"
LICENSE = "CC BY 4.0"
DEPTH_NOTE = "0-30 cm = weighted mean of 0-5, 5-15 and 15-30 cm (weights 5, 10, 15); PROVISIONAL choice; Q0.05 and Q0.95 are the same weighted mean of the layers' quantiles (approximate); native cell 250 m; model estimate"
STATUS = "model_estimate_not_measured"
COLUMNS = ["square_id", "ph_mean_0_30", "ph_q05_0_30", "ph_q95_0_30", "source", "license", "depth_note", "accessed_date", "status", "cell_col", "cell_row"]
NODATA = 0                                                                          # what the service answers where it has no data
D_FACTOR = 10                                                                       # the service's own scale factor for pH ("mapped_units": "pH*10")
BUFFER_DEG = 0.02
ATTRIBUTION = "pH: SoilGrids 2.0 (ISRIC), CC BY 4.0 [licence to be confirmed]"      # [licence to be confirmed]: the service metadata names no licence; see data/reference/soilgrids_license_evidence.txt (stage C2b)


class SoilGridsError(RuntimeError):
    pass


def coverage_id(depth, stat):
    return f"phh2o_{depth}_{stat}"


def raw_name(depth, stat):
    return f"phh2o_{depth}_{stat}.tif"


def squares(processed=None):
    import pandas as pd
    p = Path(processed or ROOT / "data" / "processed") / "site_points_clean.csv"
    return pd.read_csv(p, usecols=["point_id", "lon", "lat"])


def bbox_igh(sq):
    """The box (x0, x1, y0, y1) in the SoilGrids grid that holds every square centre plus BUFFER_DEG, rounded outwards to the 250 m grid."""
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", IGH, always_xy=True)
    xs, ys = [], []
    for lon in (sq.lon.min() - BUFFER_DEG, sq.lon.max() + BUFFER_DEG):
        for lat in (sq.lat.min() - BUFFER_DEG, sq.lat.max() + BUFFER_DEG):
            x, y = t.transform(lon, lat)
            xs.append(x); ys.append(y)
    snap = lambda v, f: f(v / 250.0) * 250.0
    return snap(min(xs), math.floor), snap(max(xs), math.ceil), snap(min(ys), math.floor), snap(max(ys), math.ceil)


def request_url(depth, stat, box):
    x0, x1, y0, y1 = box
    q = {"SERVICE": "WCS", "VERSION": "2.0.1", "REQUEST": "GetCoverage", "COVERAGEID": coverage_id(depth, stat), "FORMAT": "image/tiff"}
    base = WCS + "&" + urllib.parse.urlencode(q) + f"&SUBSET=x({x0:.0f},{x1:.0f})&SUBSET=y({y0:.0f},{y1:.0f})&SUBSETTINGCRS=http://www.opengis.net/def/crs/EPSG/0/152160"
    return base


def fetch(processed=None, raw=None):
    """Download the nine layers (native grid) and write the manifest. Stops with an error if a layer cannot be read: nothing is made up."""
    raw = Path(raw or RAW)
    raw.mkdir(parents=True, exist_ok=True)
    box = bbox_igh(squares(processed))
    log = []
    for depth, _w in DEPTHS:
        for stat, _col in STATS:
            url = request_url(depth, stat, box)
            req = urllib.request.Request(url, headers={"User-Agent": "optimizing-survival-thesis/1.0 (reference download)"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    body, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "")
            except Exception as ex:                                              # the network, the service: report, never fill in
                raise SoilGridsError(f"{coverage_id(depth, stat)}: could not be downloaded ({ex}); nothing was made up. URL: {url}")
            if status != 200 or "tiff" not in ctype.lower() or len(body) < 200:
                raise SoilGridsError(f"{coverage_id(depth, stat)}: HTTP {status}, {ctype}, {len(body)} bytes: {body[:200]!r}")
            (raw / raw_name(depth, stat)).write_bytes(body)
            log.append({"coverage": coverage_id(depth, stat), "file": raw_name(depth, stat), "http": status, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "url": url})
            time.sleep(0.5)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"accessed_date": date.today().isoformat(), "service": WCS, "grid": "EPSG:152160 (Homolosine), 250 m", "box_x0_x1_y0_y1": list(box), "layers": log}, indent=1), encoding="utf-8")
    return log


def _read(path):
    import numpy as np
    import rasterio
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        t = s.transform
        shape = s.shape
        res = s.res
    a[a == NODATA] = np.nan
    return a / D_FACTOR, t, shape, res


def sample(processed=None, raw=None, accessed=None):
    """One row per square: the SoilGrids cell under its centre. Returns (rows, extra) where extra holds what the report needs."""
    import numpy as np
    from pyproj import Transformer
    raw = Path(raw or RAW)
    sq = squares(processed)
    grids, first = {}, None
    for depth, _w in DEPTHS:
        for stat, _c in STATS:
            a, t, shape, res = _read(raw / raw_name(depth, stat))
            if first is None:
                first = (t, shape, res)
            elif (t, shape) != first[:2]:
                raise SoilGridsError(f"{raw_name(depth, stat)} is not on the same grid as the others")
            grids[(depth, stat)] = a
    t, shape, res = first
    if tuple(round(r) for r in res) != (250, 250):
        raise SoilGridsError(f"the cells are {res} m, not 250 m: this is not the native grid")
    tr = Transformer.from_crs("EPSG:4326", IGH, always_xy=True)
    x, y = tr.transform(sq.lon.to_numpy(), sq.lat.to_numpy())
    col = np.floor((x - t.c) / t.a).astype(int)
    row = np.floor((y - t.f) / t.e).astype(int)
    inside = (row >= 0) & (row < shape[0]) & (col >= 0) & (col < shape[1])
    if not inside.all():
        raise SoilGridsError(f"{int((~inside).sum())} squares lie outside the downloaded box")
    wsum = sum(w for _d, w in DEPTHS)
    out = {}
    for stat, column in STATS:
        layers = [grids[(d, stat)][row, col] * w for d, w in DEPTHS]
        stacked = np.vstack(layers)
        v = stacked.sum(axis=0) / wsum
        v[np.isnan(stacked).any(axis=0)] = np.nan                                  # a layer is missing: the square has no value (nothing is filled in)
        out[column] = v
    day = accessed or date.today().isoformat()
    rows = []
    for i, pid in enumerate(sq.point_id.to_numpy()):
        def f(c):
            v = out[c][i]
            return "" if np.isnan(v) else f"{v:.2f}"
        rows.append({"square_id": int(pid), "ph_mean_0_30": f("ph_mean_0_30"), "ph_q05_0_30": f("ph_q05_0_30"), "ph_q95_0_30": f("ph_q95_0_30"),
                     "source": SOURCE, "license": LICENSE, "depth_note": DEPTH_NOTE, "accessed_date": day, "status": STATUS, "cell_col": int(col[i]), "cell_row": int(row[i])})
    return rows, {"cells": len({(int(c), int(r)) for c, r in zip(col, row)}), "cell_size_m": res}


def write_csv(rows, path=None):
    path = Path(path or OUT_CSV)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


# ---------------------------------------------------------------------------------------------------- reading it (the API and the tests)
def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def load(path=None):
    """{square_id: {"mean", "q05", "q95", "source", "license", "accessed_date", "status", "depth_note"}} from the CSV. A missing file or a square without a value gives NO entry
    (or None values): nothing is ever invented. The values are the file's own."""
    p = Path(path or OUT_CSV)
    if not p.is_file():
        return {}
    out = {}
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                sid = int(r["square_id"])
            except (KeyError, ValueError):
                continue
            out[sid] = {"mean": _num(r.get("ph_mean_0_30")), "q05": _num(r.get("ph_q05_0_30")), "q95": _num(r.get("ph_q95_0_30")), "source": r.get("source", ""), "license": r.get("license", ""),
                        "accessed_date": r.get("accessed_date", ""), "status": r.get("status", ""), "depth_note": r.get("depth_note", "")}
    return out


def _median(v):
    v = sorted(v)
    if not v:
        return None
    k = len(v) // 2
    return v[k] if len(v) % 2 else (v[k - 1] + v[k]) / 2


def summary(table):
    """The file as a whole (used when no square is chosen): the median of the squares' means, of their Q0.05 and of their Q0.95. Empty squares are left out, nothing is filled in."""
    ok = [v for v in table.values() if v["mean"] is not None]
    if not ok:
        return None
    return {"median": _median([v["mean"] for v in ok]), "q05": _median([v["q05"] for v in ok if v["q05"] is not None]), "q95": _median([v["q95"] for v in ok if v["q95"] is not None]),
            "n_squares": len(ok), "n_total": len(table)}


def compare_interval(q05, q95, ph_min, ph_max, kind=None):
    """THE comparison rule of the Species card (display only; it decides nothing in any score). Inputs: the model's 5th and 95th percentile of the site pH and the species' listed pH range.
      'no_value'  - the site has no Q0.05 / Q0.95 (nothing is guessed);
      'no_range'  - the species has no ph_min or no ph_max (nothing is guessed);
      'inside'    - the WHOLE interval lies in the range:        ph_min <= q05  and  q95 <= ph_max;
      'outside'   - the WHOLE interval lies outside the range:   q95 < ph_min  or  q05 > ph_max;
      'uncertain' - anything else (the interval overlaps an edge of the range, or is wider than the range).
    The limits themselves count as inside.
    kind (optional, from the evidence file species_ph_evidence.csv): 'none' = the species has no confirmed range -> 'no_confirmed_range' (no Nasa / Labas / Hindi tiyak verdict);
    'optimal_only' = the range is only the OPTIMAL one, so a whole interval outside it is 'outside_optimal' ("Labas sa pinakamainam na saklaw"), not 'outside'. Any other kind (or None) = the rules above."""
    q05, q95, lo, hi = _num(q05), _num(q95), _num(ph_min), _num(ph_max)
    if kind == "none":
        return "no_confirmed_range"
    if q05 is None or q95 is None:
        return "no_value"
    if lo is None or hi is None:
        return "no_range"
    if q05 > q95:
        q05, q95 = q95, q05
    if lo <= q05 and q95 <= hi:
        return "inside"
    if q95 < lo or q05 > hi:
        return "outside_optimal" if kind == "optimal_only" else "outside"
    return "uncertain"


def site_answer(table, point_id, ph_min, ph_max, kind=None):
    """What the Species card shows for one species and one chosen square (or the whole municipality when point_id is None). The verdict comes from compare_interval (the whole Q0.05-Q0.95 interval against the species range).
    No file, no square, no value: available False and a reason; never a number made up."""
    base = {"scored": False, "attribution": ATTRIBUTION, "note": "Reference only. A model estimate, not measured in San Mateo. Not part of the score."}
    lo, hi = _num(ph_min), _num(ph_max)
    if not table:
        return {**base, "available": False, "reason": "no_file", "scope": "none"}
    if point_id is None:
        s = summary(table)
        if s is None:
            return {**base, "available": False, "reason": "no_values", "scope": "municipality"}
        mean, q05, q95, scope = s["median"], s["q05"], s["q95"], "municipality"
        extra = {"n_squares": s["n_squares"], "n_total": s["n_total"]}
    else:
        r = table.get(int(point_id))
        if r is None or r["mean"] is None:
            return {**base, "available": False, "reason": "no_value_here", "scope": "square", "point_id": int(point_id)}
        mean, q05, q95, scope = r["mean"], r["q05"], r["q95"], "square"
        extra = {"point_id": int(point_id)}
    verdict = compare_interval(q05, q95, lo, hi, kind)
    return {**base, "available": True, "scope": scope, "ph_mean": round(mean, 2), "ph_q05": None if q05 is None else round(q05, 2), "ph_q95": None if q95 is None else round(q95, 2),
            "species_ph_min": lo, "species_ph_max": hi, "range_kind": kind, "verdict": verdict, **extra}


# ---------------------------------------------------------------------------------------------------- the report
def report(rows, extra, processed=None):
    import numpy as np
    import pandas as pd
    df = pd.DataFrame(rows)
    for c in ("ph_mean_0_30", "ph_q05_0_30", "ph_q95_0_30"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    have = df.ph_mean_0_30.notna()
    L = [f"SoilGrids pH reference (stage C2). Display only. Made {date.today().isoformat()} from {MANIFEST.name}.",
         f"Variable phh2o (pH in water), 0-5, 5-15, 15-30 cm; mean, Q0.05, Q0.95; 0-30 cm = weighted mean (weights 5, 10, 15 cm: PROVISIONAL). Stored as pH x 10 by the service: divided by 10. The service's value 0 (no data) is EMPTY here.",
         f"squares: {len(df)} | with a pH: {int(have.sum())} | without (empty, not filled): {int((~have).sum())} | coverage {100 * have.mean():.1f}%",
         f"SoilGrids cells under the 8,088 squares: {extra['cells']} different cells of {extra['cell_size_m'][0]:.0f} m x {extra['cell_size_m'][1]:.0f} m (the squares are 100 m: about {len(df) / max(extra['cells'], 1):.1f} squares share a cell)",
         f"cells that carry a pH: {df[have][['cell_col', 'cell_row']].drop_duplicates().shape[0]} | cells with no data: {df[~have][['cell_col', 'cell_row']].drop_duplicates().shape[0]}"]
    if have.any():
        m = df.loc[have, "ph_mean_0_30"]
        L.append(f"pH mean 0-30 cm: min {m.min():.2f} | median {m.median():.2f} | max {m.max():.2f}")
        w = (df.ph_q95_0_30 - df.ph_q05_0_30).dropna()
        if len(w):
            L.append(f"width of Q0.05 to Q0.95 (the model's own uncertainty): median {w.median():.2f} | min {w.min():.2f} | max {w.max():.2f} pH units, over {len(w)} squares")
    # sanity: against the LGU soil texture of the square
    p = Path(processed or ROOT / "data" / "processed") / "site_points_clean.csv"
    sc = pd.read_csv(p, usecols=["point_id", "soil_series_lgu", "soil_texture_lgu", "zone_desc"])
    j = df.merge(sc, left_on="square_id", right_on="point_id", how="left")
    L.append("")
    L.append("SANITY 1: pH against the LGU soil map (squares with a texture / series in the map; the model does not know our soil map)")
    g = j.assign(soil=j.soil_series_lgu.fillna("(outside the LGU soil map)") + " | " + j.soil_texture_lgu.fillna("-")).groupby("soil")
    for soil, k in g:
        v = k.ph_mean_0_30.dropna()
        L.append(f"  {soil:50s} squares {len(k):5d} | with pH {len(v):5d} | " + (f"mean {v.mean():.2f} min {v.min():.2f} max {v.max():.2f}" if len(v) else "no pH"))
    L.append("SANITY 2: the usual range of soil pH in water is about 3.5 to 9.5; flags below")
    flags = []
    if have.any():
        if m.min() < 3.5 or m.max() > 9.5:
            flags.append(f"FLAG: pH outside 3.5-9.5 ({m.min():.2f}-{m.max():.2f})")
        bad = int(((df.ph_q05_0_30 > df.ph_mean_0_30 + 0.3) | (df.ph_q95_0_30 < df.ph_mean_0_30 - 0.3)).sum())
        if bad:
            flags.append(f"FLAG: {bad} squares where the mean lies outside Q0.05-Q0.95 by more than 0.3 (the quantiles of the layers are averaged: an approximation)")
    L += flags or ["  no flag"]
    nodata_by_zone = j[~j.ph_mean_0_30.notna()].zone_desc.fillna("(outside zoning map)").value_counts().head(8)
    L.append("")
    L.append("Where the squares have NO pH (top zones):  " + "; ".join(f"{k} {v}" for k, v in nodata_by_zone.items()))
    return "\n".join(L) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("fetch", "sample"):
        print(__doc__)
        return 1
    if argv[0] == "fetch":
        for e in fetch():
            print(f"{e['coverage']:24s} HTTP {e['http']} {e['bytes']:6d} bytes {e['sha256'][:12]}")
        print(f"manifest: {MANIFEST}")
        return 0
    rows, extra = sample()
    write_csv(rows)
    txt = report(rows, extra)
    OUT_REPORT.write_text(txt, encoding="utf-8")
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
