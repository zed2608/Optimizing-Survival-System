#!/usr/bin/env python3
"""
kit_spaced.py - the field kit with SPACED planting points (see point_layout.py) instead of rows.

field_kit.make_kit calls this when the plan is made in blocks and CFG["point_layout"] is "spaced" (the default). It
  1. finds the area the user selected (the drawn polygon or the barangay outline saved in the plan summary; None = the planned squares),
  2. lays the trees out with point_layout.layout_plan (one formula for the distance between two trees, see that module),
  3. gives every block a `geo` dict with the same keys the kit writers already use (corners, trees, first_tree ...) plus `spaced`, `region_ll`, `points_ll`,
  4. writes trees.csv (one row per tree: reference, number in the walking order, species, lat, lon, UTM, metres in the square) and area.geojson (the selected
     area, the plantable area and the region of every block, lon/lat) next to the other kit files.
The numbers of trees per block and per species are the plan's: nothing is added or moved between blocks. A block that does not fit keeps the trees that fit and says so.
"""
import json
from pathlib import Path

import pandas as pd

import point_layout as pl


def _transformers(crs):
    from pyproj import Transformer
    return Transformer.from_crs(crs, "EPSG:4326", always_xy=True), Transformer.from_crs("EPSG:4326", crs, always_xy=True)


def _norm(name):
    import re
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower().replace("sta.", "santa").replace("sto.", "santo")).strip()


def area_shape(request, crs, brgy_shp=None):
    """The selected area as a shapely geometry in UTM metres, or None (zone / whole municipality: the planned squares are the area).
    A drawn polygon (GeoJSON lon/lat) is used as drawn; a barangay is its outline from the barangay shapefile."""
    from shapely.geometry import shape
    from shapely.ops import transform
    to_ll, to_utm = _transformers(crs)
    request = request or {}
    poly = request.get("polygon")
    geom = None
    if poly:
        gj = poly.get("geometry") if poly.get("type") == "Feature" else poly
        try:
            geom = shape(gj)
        except Exception:                                               # an invalid area is not drawn: the squares stay the area
            geom = None
    elif request.get("barangay") and brgy_shp and Path(brgy_shp).is_file():
        try:
            import geopandas as gpd
            gdf = gpd.read_file(brgy_shp).to_crs("EPSG:4326")
            col = "BRGY_NAME" if "BRGY_NAME" in gdf.columns else gdf.columns[0]
            want = _norm(request["barangay"])
            hit = gdf[[(_norm(n) == want or _norm(n).replace(" ", "") == want.replace(" ", "")) for n in gdf[col]]]
            geom = hit.geometry.unary_union if len(hit) else None
        except Exception:
            geom = None
    if geom is None or geom.is_empty:
        return None
    return transform(lambda x, y, z=None: to_utm.transform(x, y), geom)


def species_table(species):
    return pl.species_rules(species.to_dict("records"))


def compute(df, species, summary, crs, brgy_shp=None, seed=None):
    """The layout of every block of the kit table `df` (ordered as written) -> point_layout result; df gets nothing yet."""
    shape_utm = area_shape(summary.get("request"), crs, brgy_shp)
    blocks = [{"ref": r.point_ref, "species_id": int(r.species_id), "n": int(r.trees_planned), "e": float(r.utm_e), "n_utm": float(r.utm_n)} for r in df.itertuples(index=False)]
    res = pl.layout_plan(blocks, species_table(species), shape_utm, seed=seed)
    res["shape"] = shape_utm
    return res


def apply(df, res, crs):
    """Give every block its `geo` dict and the START / first tree columns (the columns attach_geometry made for rows). Returns df."""
    to_ll, _ = _transformers(crs)
    geos = []
    for r in df.itertuples(index=False):
        info = res["blocks"][r.point_ref]
        half = 50.0
        e0, n0 = float(r.utm_e) - half, float(r.utm_n) - half

        def ll(x, y, e0=e0, n0=n0):
            lon, lat = to_ll.transform(e0 + x, n0 + y)
            return lat, lon

        pts = info["points"]
        start = info["start"] if info["start"] is not None else (0.0, 0.0)
        rings = info["region"]
        allx = [x for ring in rings for x, _ in ring] or [start[0]]
        ally = [y for ring in rings for _, y in ring] or [start[1]]
        x0, x1, y0, y1 = min(allx), max(allx), min(ally), max(ally)
        g = {"spaced": True, "side_m": 100.0, "spacing_m": info["min_distance_m"] or 0.0, "min_distance_m": info["min_distance_m"],
             "capacity": int(r.trees_planned), "trees_planned": len(pts), "requested": info["requested"], "placed": info["placed"], "fits": info["fits"], "fit_note": info["reason"],
             "rect_w_m": x1 - x0, "rect_h_m": y1 - y0, "rect_side_m": max(x1 - x0, y1 - y0), "margin_m": res["cfg"]["edge_margin_m"], "margin_y_m": res["cfg"]["edge_margin_m"],
             "trees": [{"k": k + 1, "x": x, "y": y, "planted": True} for k, (x, y) in enumerate(pts)],
             "corners": {"SW": start, "SE": (x1, y0), "NE": (x1, y1), "NW": (x0, y1)}, "start": start,
             "first_tree": pts[0] if pts else start, "last_tree": pts[-1] if pts else None, "region": rings}
        g["ll"] = {k: ll(*v) for k, v in g["corners"].items()}
        g["first_ll"] = ll(*g["first_tree"])
        g["utm_sw"] = (e0 + start[0], n0 + start[1])
        g["region_ll"] = [[[round(v, 7) for v in ll(x, y)] for x, y in ring] for ring in rings]          # [[lat, lon], ...] per ring
        g["points_ll"] = [[k + 1, round(ll(x, y)[0], 7), round(ll(x, y)[1], 7), round(x, 3), round(y, 3)] for k, (x, y) in enumerate(pts)]
        geos.append(g)
    df["geo"] = geos
    fmt = lambda v: f"{v:g}" if abs(v - round(v)) > 1e-9 else f"{int(round(v))}"
    df["start_lat"] = [f"{g['ll']['SW'][0]:.6f}" for g in geos]
    df["start_lon"] = [f"{g['ll']['SW'][1]:.6f}" for g in geos]
    df["start_utm_e"] = [f"{g['utm_sw'][0]:.1f}" for g in geos]
    df["start_utm_n"] = [f"{g['utm_sw'][1]:.1f}" for g in geos]
    df["first_tree_lat"] = [f"{g['first_ll'][0]:.6f}" for g in geos]
    df["first_tree_lon"] = [f"{g['first_ll'][1]:.6f}" for g in geos]
    df["rect_side_m"] = [fmt(round(g["rect_side_m"], 1)) for g in geos]
    df["margin_m"] = [fmt(g["margin_m"]) for g in geos]
    df["layout"] = "spaced"
    df["min_distance_m"] = [fmt(g["min_distance_m"]) if g["min_distance_m"] else "" for g in geos]
    df["trees_fit"] = [g["placed"] for g in geos]
    df["fit_note"] = [g["fit_note"] for g in geos]
    return df


def write_trees_csv(df, path):
    rows = []
    for r in df.itertuples(index=False):
        g = r.geo
        e0, n0 = float(r.utm_e) - 50.0, float(r.utm_n) - 50.0
        for k, la, lo, x, y in g["points_ll"]:
            rows.append({"point_ref": r.point_ref, "tree": k, "species_code": r.species_code, "common_name": r.common_name, "lat": f"{la:.7f}", "lon": f"{lo:.7f}",
                         "utm_e": f"{e0 + x:.2f}", "utm_n": f"{n0 + y:.2f}", "x_m": f"{x:.2f}", "y_m": f"{y:.2f}"})
    pd.DataFrame(rows, columns=["point_ref", "tree", "species_code", "common_name", "lat", "lon", "utm_e", "utm_n", "x_m", "y_m"]).to_csv(path, index=False)


def write_area_geojson(df, res, crs, path, meta):
    from shapely.geometry import mapping
    from shapely.ops import transform
    to_ll, _ = _transformers(crs)
    conv = lambda g: mapping(transform(lambda x, y, z=None: to_ll.transform(x, y), g)) if g is not None and not g.is_empty else None
    feats = []
    for name, g in (("selected", res.get("shape")), ("plantable", res["inner"])):
        gj = conv(g)
        if gj:
            feats.append({"type": "Feature", "properties": {"kind": name}, "geometry": gj})
    for r in df.itertuples(index=False):
        rings = r.geo["region_ll"]
        if rings:
            feats.append({"type": "Feature", "properties": {"kind": "block", "ref": r.point_ref, "species": r.species_code, "placed": r.geo["placed"], "requested": r.geo["requested"], "fits": r.geo["fits"]},
                          "geometry": {"type": "MultiPolygon", "coordinates": [[[[lo, la] for la, lo in ring]] for ring in rings]}})
    doc = {"type": "FeatureCollection", "name": f"{meta['plan_id']} area", "properties": {"check_code": meta["check_code"], "edge_margin_m": res["cfg"]["edge_margin_m"],
           "note": "selected = the area chosen in the dashboard (absent when the planned squares are the area); plantable = the planned squares clipped to it and pulled in from the edge; block = the plantable ground of one block"},
           "features": feats}
    Path(path).write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")


_CACHE = {}


def layout_for_plan(plan, refs, summary, species, crs, brgy_shp=None, max_cache=24):
    """The layout of a saved or fresh plan for the API (the same call as the kit: same blocks, same refs, same seed -> the same points). `refs` = {point_id: block ref}.
    Returns {ref: block result}. Cached by the content of the plan and of its request, so a plan that is shown again is not laid out again."""
    import hashlib
    cols = plan[["point_id", "species_id", "trees_planned", "utm_e", "utm_n"]]
    key = hashlib.sha1(cols.to_csv(index=False).encode("utf-8") + json.dumps(summary.get("request"), sort_keys=True, default=str).encode("utf-8")).hexdigest()
    if key in _CACHE:
        return _CACHE[key]
    tmp = cols.copy()
    tmp["point_ref"] = [refs[int(p)] for p in tmp.point_id]
    res = compute(tmp, species, summary, crs, brgy_shp)
    out = res["blocks"]
    if len(_CACHE) >= max_cache:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = out
    return out
