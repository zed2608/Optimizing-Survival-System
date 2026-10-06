#!/usr/bin/env python3
"""
lgu_soil.py - the soil series of every grid square, read from the LGU soil map (Bureau of Soils and Water Management, "Soil Map of Rizal Province",
shown as Figure 1-3 of the CLUP 2021-2031 and on page 10 of the LCCAP 2021-2025). PROVISIONAL: the map is a scan, digitized by us, and the agriculturist
has not verified it (CLAUDE.md rule 4). Raw files are only read.

  python pipeline/lgu_soil.py render                       # extract the map picture from the two PDFs (and a 300 dpi render of each page) -> data/external/lgu/
  python pipeline/lgu_soil.py compute [--qa-dir DIR]       # georeference, classify, majority per 100 m square -> data/processed/site_soil_lgu.csv (+ report, QA pictures)

Steps of `compute` (all in metres in EPSG:32651):
 1. Georeference. The frame has graticule lines 121 08' / (121 10') / 121 12' and 14 40' / 14 42'. Their pixel positions (found by line detection, sub-pixel) give a first affine fit
    pixel -> UTM. It is then refined by fitting the municipal outline drawn on the map (the filled region of coloured soil pixels) to the outline of data/BRGY_BOUNDARY.shp
    (union of the barangays): shift, rotation and scale are searched to maximise the overlap (IoU). The report gives the residual at the control points and the IoU.
    If the residual is above MAX_RESIDUAL_M the run STOPS (exit code 2) and says so.
 2. Classify. The 8 legend swatches are read from the picture; every map pixel gets the nearest legend colour in CIELAB, or "none" when no legend colour is closer than DELTA_E_MAX
    (black lines, text, red roads, blue rivers, the legend box, the landfill circle). A majority filter then removes the thin lines that cross the colour areas.
 3. Per square. Pixels whose centre lies inside the square (centre +/- 50 m) vote; the series is the majority class; purity = share of the valid pixels in it; valid_share = valid
    pixels over all pixels of the footprint. A square with valid_share below MIN_VALID_SHARE takes the series of the nearest valid square within FILL_RADIUS_M (soil_filled = 1),
    else it stays empty.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# =====================================================================================================================
# CONFIG - PROVISIONAL. Every number and the series -> texture table are to be confirmed by the agriculturist.
# =====================================================================================================================
LGU_CFG = {
    "pdf_clup": "data/external/lgu/CLUP__1_.pdf", "page_clup": 28,                       # CLUP Figure 1-3 (PDF page 28)
    "pdf_lccap": "data/external/lgu/SAN_MATEO_LCCAP_2021-2025.pdf", "page_lccap": 10,    # LCCAP page 10
    "image_file": "data/external/lgu/clup_soilmap_native.jpeg",                         # the map picture used (the CLUP one; the LCCAP one is the same scan)
    "site_crs": "EPSG:32651",
    "boundary_shp": "data/BRGY_BOUNDARY.shp",
    "half_side_m": 50.0,                 # a square is its centre +/- 50 m
    # graticule: (longitude / latitude in degrees, minutes) of the lines. The middle meridian carries no label on the map; it is found half way (checked in the report).
    "graticule_lon": [(121, 8), (121, 10), (121, 12)],
    "graticule_lat": [(14, 42), (14, 40)],
    "line_search": {"x_rows": (80, 150), "x_cols": (300, 940), "y_cols": (80, 108), "y_rows": (230, 680), "dark_below": 215, "min_fraction": 0.8},
    "max_residual_m": 150.0,             # STOP above this (residual at the control points / mean outline distance)
    # legend swatches (pixel box of the picture: x range and the centre row of each swatch), read as the median colour of the box
    "swatch_x": (965, 992), "swatch_half_h": 2,
    "swatch_rows": [131.7, 144.3, 157.7, 170.7, 183.7, 197.0, 210.0, 223.3],
    "thin_open": 5, "thin_classes": [1, 3],   # pixels of Antipolo Clay Loam (red) and Marikina Clay Loam (orange) that are not part of a solid area (5 x 5 opening) are roads, not soil
    "min_raw_share": 0.60,               # a red / orange blob must have at least this share of its raw pixels in its own class (else it is a dense road network)
    "delta_e_by_class": {},              # optional stricter colour limits per class index (none used: measured, solid red areas and road patches overlap in colour)
    "delta_e_max": 40.0,              # a pixel farther than this (CIELAB) from every legend colour is "none"
    "filter_size": 5,                    # the last (edge tidying) majority window (pixels, odd)
    "filter_min_valid": 0.25,            # a thin line pixel is filled only if at least this share of its window is valid
    "ignore_boxes": [(938, 88, 1172, 372), (845, 700, 1172, 800)],   # (x0, y0, x1, y1) in pixels: the legend box and the title box
    "min_valid_share": 0.30,             # below this a square takes the series of the nearest valid square ...
    "fill_radius_m": 300.0,              # ... within this distance, else it stays empty
    "purity_low": 0.60,                  # report: squares below this purity
    "paper_l": 93.0,                     # a pixel lighter than this (CIELAB L*) is paper, never a soil colour
    "region_open": 9, "region_close": 15,   # the map outline: opening (pixels) removes thin lines and text, closing joins the areas
    "smooth_size": 11,                   # the first majority window (pixels): the area colour outvotes roads and rivers
    "min_blob_px": 150,                  # after the smoothing every class must form a blob of at least this many pixels (3 x 3 opening) ...
    "blob_open": 3,
    # ... and more for the classes that roads imitate (red Antipolo Clay Loam, orange Marikina Clay Loam) or grey lines imitate (pale Quingua Sandy Loam). Measured on this map: the real red
    # areas are 1,513 and 10,589 px, the red road patches in the urban west are 166-1,092 px; the real orange strip is 1,422 px, the orange patches 155-289 px.
    "min_blob_px_by_class": {1: 1300, 3: 700, 7: 300},
    "blob_classes": [0, 1, 2, 3, 4, 5, 6, 7],
    "outline_match_m": 800.0,            # outline points farther than this from the other outline are not on a shared side and are left out of the distance statistics
    "refine_accept_m": 150.0,            # the outline fit is used only if its shift is at most this and it improves the IoU
    "refine_free": [1, 1, 0, 0],        # the outline fit may only SHIFT the graticule fit (the graticule fixes scale and rotation to about 2 m); set [1, 1, 1, 1] to allow rotation and scale too
    "hull_margin_m": 600.0,            # the part of the barangay union used for the outline fit: inside the hull of the coloured area plus this margin
    "fill_max_px": 14,                  # inside the map outline, an invalid pixel (road, river, dashed line, text, hole) takes the class of the nearest valid pixel within this many pixels
    "refine_bounds": {"shift_m": 600.0, "rot_deg": 1.5, "scale": 0.05},   # the outline refinement may move the graticule fit by at most this
    "outline_raster_m": 25.0,
}
# series (legend name, in the order of the legend) -> texture. PROVISIONAL: for the agriculturist to confirm.
SERIES = [
    ("Antipolo Clay", "Clay"),
    ("Antipolo Clay Loam", "Clay Loam"),
    ("Binangonan Clay", "Clay"),
    ("Marikina Clay Loam", "Clay Loam"),
    ("Marikina Loam", "Loam"),
    ("Marikina Silt Loam", "Silt Loam"),
    ("Novaliches Clay Loam", "Clay Loam"),
    ("Quingua Sandy Loam", "Sandy Loam"),
]
SERIES_TEXTURE = dict(SERIES)
SOURCE_TEXT = "LGU soil map (BSWM), digitized by us, provisional"
SOURCE = {"name": "Soil Map of Rizal Province, Bureau of Soils and Water Management (BSWM), as printed in the San Mateo CLUP 2021-2031 (Figure 1-3, 'Source: 2010 CLUP') and the LCCAP 2021-2025 (page 10)",
          "note": "scanned map picture of 1255 x 887 pixels (about 13 m per pixel), digitized by us; not verified by the agriculturist"}
# =====================================================================================================================


# ---------------------------------------------------------------------------------------------------------------------
# colours
# ---------------------------------------------------------------------------------------------------------------------
def rgb_to_lab(rgb):
    """sRGB (0..255, shape (..., 3)) -> CIELAB (D65)."""
    c = np.asarray(rgb, dtype=float) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def legend_colours(img_rgb, cfg=None):
    """Median colour (RGB) of every legend swatch, in the order of SERIES."""
    c = LGU_CFG if cfg is None else cfg
    x0, x1 = c["swatch_x"]
    out = []
    for y in c["swatch_rows"]:
        y = int(round(y))
        box = img_rgb[y - c["swatch_half_h"]:y + c["swatch_half_h"] + 1, x0:x1].reshape(-1, 3)
        out.append(np.median(box, axis=0))
    return np.array(out)


def classify(img_rgb, legend_rgb, delta_e_max=None, ignore_boxes=()):
    """Nearest legend colour per pixel (CIELAB, Euclidean = Delta E 1976). Returns (labels int, distance): label -1 = no legend colour is close enough. ignore_boxes (x0, y0, x1, y1) are -1."""
    de = LGU_CFG["delta_e_max"] if delta_e_max is None else delta_e_max
    lab = rgb_to_lab(img_rgb)
    leg = rgb_to_lab(legend_rgb)
    d = np.sqrt(((lab[:, :, None, :] - leg[None, None, :, :]) ** 2).sum(axis=3))
    lab_idx = d.argmin(axis=2)
    dist = d.min(axis=2)
    lab_idx = np.where(dist <= de, lab_idx, -1)
    for k, lim in LGU_CFG["delta_e_by_class"].items():                 # a stricter limit for the classes that roads imitate
        lab_idx = np.where((lab_idx == k) & (dist > lim), -1, lab_idx)
    lab_idx = np.where(lab[..., 0] > LGU_CFG["paper_l"], -1, lab_idx)
    for x0, y0, x1, y1 in ignore_boxes:
        lab_idx[y0:y1, x0:x1] = -1
    return lab_idx.astype(np.int16), dist


def drop_small_blobs(labels, classes=None, min_px=None):
    """Remove the pixels of the given classes that do not belong to a blob of at least min_px pixels (after a 3 x 3 opening): thin grey frame lines and text look like pale soil colours."""
    import cv2
    from scipy import ndimage as ndi
    cl = LGU_CFG["blob_classes"] if classes is None else classes
    mp = LGU_CFG["min_blob_px"] if min_px is None else min_px
    out = labels.copy()
    ko = LGU_CFG["blob_open"]
    for k in cl:
        m = cv2.morphologyEx((labels == k).astype(np.uint8), cv2.MORPH_OPEN, np.ones((ko, ko), np.uint8))
        lab, n = ndi.label(m)
        if n:
            sizes = ndi.sum(m, lab, range(1, n + 1))
            need = LGU_CFG["min_blob_px_by_class"].get(k, mp) if min_px is None else mp
            keep = np.isin(lab, 1 + np.where(sizes >= need)[0])
        else:
            keep = np.zeros_like(m, dtype=bool)
        out[(labels == k) & ~(keep | (cv2.dilate(keep.astype(np.uint8), np.ones((ko, ko), np.uint8)) > 0))] = -1   # keep the edge pixels that the opening removed next to a real blob
    return out


def drop_mixed_blobs(smoothed, raw, classes, min_share):
    """A blob of a road-confusable class (red / orange) whose RAW pixels are mostly another colour is a dense road network over another soil, not a soil area: it is dropped.
    min_share = the least share of the blob's raw pixels that must have the blob's own class (a real solid area is mostly that class)."""
    from scipy import ndimage as ndi
    out = smoothed.copy()
    for k in classes:
        lab, n = ndi.label(smoothed == k)
        if not n:
            continue
        share = ndi.mean((raw == k).astype(float), lab, range(1, n + 1))
        bad = 1 + np.where(np.asarray(share) < min_share)[0]
        out[np.isin(lab, bad)] = -1
    return out


def clean_labels(labels0, background=None, cfg=None):
    """From the raw nearest-colour labels to the soil classes of the map pixels. Returns (labels, region).
      1. region = the filled outline of the coloured area: the union of all legend-coloured pixels, opened (thin frame lines, graticule, text and rivers vanish), closed, holes filled, largest piece;
      2. only pixels inside the region keep a class; a majority filter (window smooth_size) lets the area colours outvote roads and rivers;
      3. blobs of the classes that roads imitate (red / orange) or that grey lines imitate (pale grey) must be big enough, else they are dropped;
      4. every invalid pixel inside the region takes the class of the nearest valid pixel (fill_max_px), then a small majority filter tidies the edges."""
    c = LGU_CFG if cfg is None else cfg
    import cv2
    region = region_mask(labels0, c)
    l1 = np.where(region, labels0, -1).astype(np.int16)
    kt = c["thin_open"]
    for k in c["thin_classes"]:                                        # roads are red / orange lines: thin structures of these classes are not soil, a real clay-loam area is solid
        m = (l1 == k)
        solid = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((kt, kt), np.uint8)) > 0
        l1[m & ~solid] = -1
    l2 = majority_filter(l1, c["smooth_size"], c["filter_min_valid"], background)
    l2 = np.where(region, l2, -1).astype(np.int16)
    l2 = drop_mixed_blobs(l2, labels0, c["thin_classes"], c["min_raw_share"])
    l3 = drop_small_blobs(l2, c["blob_classes"])
    l4 = fill_inside(l3, region, c["fill_max_px"])
    l5 = np.where(region, majority_filter(l4, c["filter_size"], 0.0, None), -1).astype(np.int16)
    return l5, region


def fill_inside(labels, region, max_px=None):
    """Inside the region (the filled map outline) every invalid pixel takes the class of the nearest valid pixel, if one is within max_px pixels."""
    from scipy import ndimage as ndi
    mx = LGU_CFG["fill_max_px"] if max_px is None else max_px
    inval = labels < 0
    if not inval.any() or (~inval).sum() == 0:
        return labels
    dist, (iy, ix) = ndi.distance_transform_edt(inval, return_indices=True)
    out = labels.copy()
    take = inval & region & (dist <= mx)
    out[take] = labels[iy[take], ix[take]]
    return out


def majority_filter(labels, size=None, min_valid=None, background=None):
    """Replace every pixel by the majority class of the valid pixels in its size x size window (thin lines that cross the colour areas disappear).
    A pixel is kept valid/filled only when at least `min_valid` of its window is valid AND it is not plain background (background = boolean mask of white paper)."""
    import cv2
    k = LGU_CFG["filter_size"] if size is None else size
    mv = LGU_CFG["filter_min_valid"] if min_valid is None else min_valid
    n = int(labels.max()) + 1 if labels.size else 0
    n = max(n, len(SERIES))
    counts = np.stack([cv2.boxFilter((labels == i).astype(np.float32), -1, (k, k), normalize=False, borderType=cv2.BORDER_CONSTANT) for i in range(n)], axis=-1)
    tot = counts.sum(axis=2)
    out = counts.argmax(axis=2).astype(np.int16)
    ok = tot >= mv * k * k
    if background is not None:
        ok &= ~background
    out = np.where(ok, out, -1).astype(np.int16)
    out[labels < 0] = np.where(ok[labels < 0], out[labels < 0], -1)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# georeferencing
# ---------------------------------------------------------------------------------------------------------------------
def _runs_peaks(frac, lo, min_fraction):
    """Positions (pixel index + sub-pixel centroid) of the runs of a 1-D profile where frac >= min_fraction."""
    idx = np.where(frac >= min_fraction)[0]
    if idx.size == 0:
        return []
    groups = np.split(idx, np.where(np.diff(idx) > 2)[0] + 1)
    peaks = []
    for g in groups:
        a, b = max(g[0] - 2, 0), min(g[-1] + 3, len(frac))
        w = frac[a:b] - frac[a:b].min()
        peaks.append(lo + (np.arange(a, b) * w).sum() / w.sum() if w.sum() > 0 else lo + g.mean())
    return peaks


def find_graticule(img_rgb, cfg=None):
    """Pixel positions of the graticule lines: ([x of the meridians], [y of the parallels]), sub-pixel. A line is a thin dark/grey line crossing a clean white band of the frame."""
    c = LGU_CFG if cfg is None else cfg
    s = c["line_search"]
    g = np.asarray(img_rgb, dtype=float).mean(axis=2)
    dark = g < s["dark_below"]
    r0, r1 = s["x_rows"]; c0, c1 = s["x_cols"]
    fx = dark[r0:r1, c0:c1].mean(axis=0)
    xs = _runs_peaks(fx, c0, s["min_fraction"])
    k0, k1 = s["y_cols"]; q0, q1 = s["y_rows"]
    fy = dark[q0:q1, k0:k1].mean(axis=1)
    ys = _runs_peaks(fy, q0, s["min_fraction"])
    return xs, ys


def fit_affine(px, xy):
    """Least squares affine pixel (u, v) -> (E, N): returns 2 x 3 matrix M with [E, N] = M @ [u, v, 1]."""
    px = np.asarray(px, dtype=float); xy = np.asarray(xy, dtype=float)
    a = np.column_stack([px, np.ones(len(px))])
    m, *_ = np.linalg.lstsq(a, xy, rcond=None)
    return m.T


def apply_affine(m, px):
    px = np.asarray(px, dtype=float)
    return px @ m[:, :2].T + m[:, 2]


def graticule_controls(xs, ys, cfg=None):
    """Control points: (pixel u, v) and the UTM (E, N) of every crossing of a meridian and a parallel."""
    from pyproj import Transformer
    c = LGU_CFG if cfg is None else cfg
    lons = [d + m / 60 for d, m in c["graticule_lon"]]
    lats = [d + m / 60 for d, m in c["graticule_lat"]]
    if len(xs) != len(lons) or len(ys) != len(lats):
        raise ValueError(f"expected {len(lons)} meridians and {len(lats)} parallels, found {len(xs)} and {len(ys)}")
    xs, ys = sorted(xs), sorted(ys)                     # west -> east, north -> south (rows grow downward)
    lats = sorted(lats, reverse=True)
    tr = Transformer.from_crs("EPSG:4326", c["site_crs"], always_xy=True)
    px, xy = [], []
    for u, lon in zip(xs, lons):
        for v, lat in zip(ys, lats):
            e, n = tr.transform(lon, lat)
            px.append((u, v)); xy.append((e, n))
    return np.array(px), np.array(xy)


def georeference_graticule(img_rgb, cfg=None):
    """First fit from the graticule. Returns dict(M, px, xy, residuals_m, rms_m, max_m, xs, ys, spacing_check)."""
    xs, ys = find_graticule(img_rgb, cfg)
    px, xy = graticule_controls(xs, ys, cfg)
    m = fit_affine(px, xy)
    res = np.hypot(*(apply_affine(m, px) - xy).T)
    sp = np.diff(sorted(xs))
    return {"M": m, "px": px, "xy": xy, "xs": sorted(xs), "ys": sorted(ys), "residuals_m": res, "rms_m": float(np.sqrt((res ** 2).mean())), "max_m": float(res.max()),
            "meridian_spacing_px": [float(v) for v in sp], "m_per_pixel": float(np.sqrt(abs(np.linalg.det(m[:, :2]))))}


def region_mask(labels, cfg=None):
    """The filled outline of the coloured soil area (the municipality on the map): valid pixels, closed, holes filled, the largest piece."""
    import cv2
    from scipy import ndimage as ndi
    c = LGU_CFG if cfg is None else cfg
    valid = (labels >= 0).astype(np.uint8)
    ko = c["region_open"]
    valid = cv2.morphologyEx(valid, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ko, ko)))     # thin lines, text and rivers vanish
    kc = c["region_close"]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kc, kc))
    closed = cv2.morphologyEx(valid, cv2.MORPH_CLOSE, k)
    filled = ndi.binary_fill_holes(closed)
    lab, n = ndi.label(filled)
    if n == 0:
        return filled
    sizes = ndi.sum(filled, lab, range(1, n + 1))
    return lab == (1 + int(np.argmax(sizes)))


def boundary_union(shp, crs):
    import geopandas as gpd
    g = gpd.read_file(shp).to_crs(crs)
    return g.geometry.union_all() if hasattr(g.geometry, "union_all") else g.geometry.unary_union


def _grid_for(geom, cell, pad=1500.0):
    x0, y0, x1, y1 = geom.bounds
    e0, n1 = x0 - pad, y1 + pad
    w = int(np.ceil((x1 + pad - e0) / cell)); h = int(np.ceil((n1 - (y0 - pad)) / cell))
    return e0, n1, w, h


def _refine_matrix(m, p, centre):
    """The graticule affine m followed by a similarity (shift dE, dN, rotation, scale) about `centre` (E, N)."""
    dE, dN, rot, sc = p
    c, s = np.cos(rot) * (1 + sc), np.sin(rot) * (1 + sc)
    r = np.array([[c, -s], [s, c]])
    lin = r @ m[:, :2]
    off = r @ (m[:, 2] - centre) + centre + np.array([dE, dN])
    return np.column_stack([lin, off])


def refine_with_outline(region, m, geom, cfg=None, free=None):
    """Search shift / rotation / scale that maximise the IoU between the (transformed) soil-area outline and the barangay union. Returns dict(M, iou_before, iou_after, params, mean_outline_distance_m)."""
    import cv2
    from scipy.optimize import minimize
    import shapely
    from shapely import contains_xy
    c = LGU_CFG if cfg is None else cfg
    cell = c["outline_raster_m"]
    e0, n1, w, h = _grid_for(geom, cell)
    ee = e0 + (np.arange(w) + 0.5) * cell
    nn = n1 - (np.arange(h) + 0.5) * cell
    reg = region.astype(np.uint8)
    # The map colours only part of the municipality (the upper watershed area in the north-east is drawn dashed and left white), so the fit compares the map outline with the
    # part of the barangay union that lies inside the hull of the coloured area (plus a margin); the share of the municipality that the map covers is reported separately.
    ys_, xs_ = np.where(region)
    hull_px = cv2.convexHull(np.column_stack([xs_, ys_]).astype(np.float32)).reshape(-1, 2)
    hull0 = shapely.Polygon(apply_affine(m, hull_px + 0.5)).buffer(c["hull_margin_m"])
    window = geom.intersection(hull0)
    target = contains_xy(window, *np.meshgrid(ee, nn)).astype(bool)
    centre = np.array(geom.centroid.coords[0])

    def to_grid(mm):
        # pixel -> UTM -> grid index: (E - e0)/cell - 0.5, (n1 - N)/cell - 0.5
        a = np.array([[1 / cell, 0, -e0 / cell - 0.5], [0, -1 / cell, n1 / cell - 0.5]]) @ np.vstack([mm, [0, 0, 1]])
        return a

    def warped(mm):
        return cv2.warpAffine(reg, to_grid(mm).astype(np.float64), (w, h), flags=cv2.INTER_NEAREST, borderValue=0).astype(bool)

    def iou(p):
        wm = warped(_refine_matrix(m, p, centre))
        u = (wm | target).sum()
        return (wm & target).sum() / u if u else 0.0

    b = c["refine_bounds"]
    free = np.array(c["refine_free"] if free is None else free, dtype=float)       # which of (shift E, shift N, rotation, scale) may move
    lim = np.array([b["shift_m"], b["shift_m"], np.deg2rad(b["rot_deg"]), b["scale"]]) * free
    clip = lambda p: np.clip(p, -lim, lim)
    p0 = np.zeros(4)
    before = iou(p0)
    best_p, best = p0, before
    for start in (p0, np.array([100.0, 100.0, 0.0, 0.0]), np.array([-100.0, -100.0, 0.0, 0.0])):
        r = minimize(lambda p: 1 - iou(clip(p)), start, method="Nelder-Mead",
                     options={"initial_simplex": np.vstack([start] + [start + np.eye(4)[i] * s for i, s in enumerate([120.0, 120.0, 0.004, 0.01])]), "xatol": 0.5, "fatol": 1e-6, "maxiter": 800})
        v = iou(clip(r.x))
        if v > best:
            best, best_p = v, clip(r.x)
    mm = _refine_matrix(m, best_p, centre)
    # distance between the outline of the transformed region and the outline of the union (metres): mean and 95th percentile of both directions
    from scipy.spatial import cKDTree
    import shapely
    wm = warped(mm).astype(np.uint8)
    cnts, _ = cv2.findContours(wm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cp = np.vstack([c_.reshape(-1, 2) for c_ in cnts]).astype(float)
    cp_utm = np.column_stack([e0 + (cp[:, 0] + 0.5) * cell, n1 - (cp[:, 1] + 0.5) * cell])
    d1 = shapely.distance(shapely.points(cp_utm), geom.boundary)
    b = shapely.get_coordinates(shapely.segmentize(geom.boundary, 25.0))
    b = b[contains_xy(hull0, b[:, 0], b[:, 1])]                                  # union boundary inside the hull of the coloured area
    d2 = cKDTree(cp_utm).query(b)[0] if len(b) else np.array([0.0])
    lim_m = c["outline_match_m"]
    dd = np.concatenate([d1[d1 <= lim_m], d2[d2 <= lim_m]])                      # the sides that coincide (the north-east side of the map is the edge of the coloured area, not of the municipality)
    reg_area = float(wm.sum() * cell * cell)
    inter = float((wm.astype(bool) & contains_xy(geom, *np.meshgrid(ee, nn))).sum() * cell * cell)
    return {"M": mm, "iou_before": float(before), "iou_after": float(best), "params": [float(v) for v in best_p], "target": target, "grid": (e0, n1, cell),
            "outline_mean_m": float(dd.mean()) if len(dd) else float("nan"), "outline_p95_m": float(np.percentile(dd, 95)) if len(dd) else float("nan"),
            "outline_matched_share": float(len(dd) / (len(d1) + len(d2))), "map_inside_union": inter / reg_area, "union_covered_by_map": inter / float(geom.area), "at_bound": [bool(abs(v) >= l - 1e-9) for v, l in zip(best_p, lim)]}


# ---------------------------------------------------------------------------------------------------------------------
# squares
# ---------------------------------------------------------------------------------------------------------------------
def texture_of(series):
    return SERIES_TEXTURE.get(series) if isinstance(series, str) else None


def squares_majority(labels, m, sites, cfg=None):
    """Per square (utm_e, utm_n centres): the majority class of the valid pixels whose centre is inside centre +/- half_side_m.
    Returns a DataFrame point_id, cls (or -1), purity, valid_share, n_pixels, n_valid."""
    from scipy.spatial import cKDTree
    c = LGU_CFG if cfg is None else cfg
    h, w = labels.shape
    uu, vv = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    pts = apply_affine(m, np.column_stack([uu.ravel(), vv.ravel()]))
    tree = cKDTree(pts)
    cen = sites[["utm_e", "utm_n"]].to_numpy(dtype=float)
    lab = labels.ravel()
    nser = len(SERIES)
    rows = []
    for pid, idx in zip(sites.point_id.to_numpy(), tree.query_ball_point(cen, r=c["half_side_m"], p=np.inf)):
        if len(idx) == 0:
            rows.append((pid, -1, np.nan, 0.0, 0, 0)); continue
        v = lab[idx]
        v = v[v >= 0]
        if len(v) == 0:
            rows.append((pid, -1, np.nan, 0.0, len(idx), 0)); continue
        cnt = np.bincount(v, minlength=nser)
        k = int(cnt.argmax())
        rows.append((pid, k, cnt[k] / len(v), len(v) / len(idx), len(idx), len(v)))
    return pd.DataFrame(rows, columns=["point_id", "cls", "purity", "valid_share", "n_pixels", "n_valid"])


def fill_missing(df, sites, min_valid_share=None, radius_m=None):
    """Squares with valid_share below the minimum take the class of the nearest square that has one (distance between centres <= radius_m); soil_filled = 1.
    A square with nobody within the radius stays empty (cls = -1)."""
    from scipy.spatial import cKDTree
    mv = LGU_CFG["min_valid_share"] if min_valid_share is None else min_valid_share
    rad = LGU_CFG["fill_radius_m"] if radius_m is None else radius_m
    d = df.merge(sites[["point_id", "utm_e", "utm_n"]], on="point_id").reset_index(drop=True)
    good = (d.valid_share >= mv) & (d.cls >= 0)
    d["soil_filled"] = 0
    out_cls = d.cls.to_numpy().copy()
    out_cls[~good.to_numpy()] = -1
    if good.any() and (~good).any():
        tree = cKDTree(d.loc[good, ["utm_e", "utm_n"]].to_numpy())
        dist, j = tree.query(d.loc[~good, ["utm_e", "utm_n"]].to_numpy(), distance_upper_bound=rad)
        src = d.loc[good, "cls"].to_numpy()
        hit = np.isfinite(dist)
        bad_idx = np.where(~good.to_numpy())[0]
        out_cls[bad_idx[hit]] = src[j[hit]]
        d.loc[bad_idx[hit], "soil_filled"] = 1
    d["cls"] = out_cls
    return d


def to_table(d):
    names = [s for s, _ in SERIES]
    series = d.cls.map(lambda k: names[k] if k >= 0 else None)
    return pd.DataFrame({"point_id": d.point_id, "soil_series": series, "soil_texture": series.map(texture_of), "purity": d.purity.round(3),
                         "valid_share": d.valid_share.round(3), "soil_filled": d.soil_filled.astype(int)})


# ---------------------------------------------------------------------------------------------------------------------
# rendering and the full run
# ---------------------------------------------------------------------------------------------------------------------
def render(cfg=None):
    """Extract the embedded map picture from the CLUP and the LCCAP PDFs (native size) and write a 300 dpi render of each page. Needs PyMuPDF (pip install pymupdf)."""
    import pymupdf
    c = LGU_CFG if cfg is None else cfg
    out = []
    for key, tag in (("clup", "clup"), ("lccap", "lccap")):
        pdf = ROOT / c["pdf_" + key]
        d = pymupdf.open(pdf)
        page = d[c["page_" + key] - 1]
        page.get_pixmap(dpi=300).save(pdf.parent / f"{tag}_p{c['page_' + key]}_300dpi.png")
        best = max(page.get_images(full=True), key=lambda i: d.extract_image(i[0])["width"] * d.extract_image(i[0])["height"])
        info = d.extract_image(best[0])
        f = pdf.parent / f"{tag}_soilmap_native.{info['ext']}"
        f.write_bytes(info["image"])
        out.append((str(f), info["width"], info["height"]))
    return out


def run(out_dir="data/processed", qa_dir=None, cfg=None, image=None, sites=None, boundary=None):
    import cv2
    c = LGU_CFG if cfg is None else cfg
    out = Path(out_dir)
    img = cv2.cvtColor(cv2.imread(str(ROOT / c["image_file"] if image is None else image)), cv2.COLOR_BGR2RGB)
    sites = pd.read_csv(out / "site_points_clean.csv") if sites is None else sites
    geom = boundary_union(ROOT / c["boundary_shp"], c["site_crs"]) if boundary is None else boundary
    rep = []
    g = georeference_graticule(img, c)
    rep.append(f"graticule lines found: meridians x = {[round(v, 1) for v in g['xs']]} px (spacing {[round(v, 1) for v in g['meridian_spacing_px']]} px, equal spacing confirms the unlabelled middle line), "
               f"parallels y = {[round(v, 1) for v in g['ys']]} px")
    rep.append(f"first fit (graticule only, {len(g['px'])} control points): {g['m_per_pixel']:.2f} m per pixel; residual at the control points RMS {g['rms_m']:.1f} m, max {g['max_m']:.1f} m")
    leg = legend_colours(img, c)
    rep.append("legend colours (RGB): " + "; ".join(f"{n} {tuple(int(v) for v in col)}" for (n, _), col in zip(SERIES, leg)))
    labels0, dist = classify(img, leg, c["delta_e_max"], c["ignore_boxes"])
    labels, reg = clean_labels(labels0, None, c)
    base = refine_with_outline(reg, g["M"], geom, c, free=[0, 0, 0, 0])            # the graticule fit alone, scored against the barangay outline
    cand = refine_with_outline(reg, g["M"], geom, c)                                 # the outline fit (shift only by default)
    shift = float(np.hypot(*cand["params"][:2]))
    accept = shift <= c["refine_accept_m"] and cand["iou_after"] > base["iou_after"]
    ref = cand if accept else base
    m = ref["M"]
    # residual at the control points of the FINAL transform: how far the graticule crossings fall from their true UTM positions
    res2 = np.hypot(*(apply_affine(m, g["px"]) - g["xy"]).T)
    rep.append(f"outline fit: IoU with the part of the barangay union inside the map's extent {base['iou_after']:.3f} (graticule fit alone); the outline fit would give {cand['iou_after']:.3f} with a shift of "
               f"{shift:.0f} m (dE {cand['params'][0]:.0f}, dN {cand['params'][1]:.0f}) and a mean outline distance of {cand['outline_mean_m']:.0f} m (graticule alone: {base['outline_mean_m']:.0f} m)")
    rep.append(("refinement ACCEPTED (shift within %.0f m)" % c["refine_accept_m"]) if accept else
               f"refinement REJECTED: it needs a shift of {shift:.0f} m (more than {c['refine_accept_m']:.0f} m) and gains almost nothing, so the graticule fit is kept (it is exact to {g['max_m']:.0f} m at its control points)")
    rep.append(f"final transform: graticule crossings are {res2.mean():.1f} m on average (max {res2.max():.1f} m) from their true positions; outline IoU {ref['iou_after']:.3f}")
    if ref["outline_mean_m"] > c["max_residual_m"]:
        rep.append(f"WARNING: the map outline and the barangay outline differ by {ref['outline_mean_m']:.0f} m on average on the sides they share (more than {c['max_residual_m']:.0f} m); no shift of the whole map reduces it, so it is a difference between the two drawn outlines, not a placement error")
    rep.append(f"outline distance on the shared sides ({ref['outline_matched_share']:.0%} of the outline points are within {c['outline_match_m']:.0f} m of the other outline): mean {ref['outline_mean_m']:.0f} m, 95th percentile {ref['outline_p95_m']:.0f} m")
    rep.append(f"coverage: {ref['map_inside_union']:.1%} of the coloured map area lies inside the barangay union; the map covers {ref['union_covered_by_map']:.1%} of the municipality (the rest, the upper watershed area, is left white on the map)")
    worst = float(res2.max())                                                         # STOP rule: the residual at the control points of the final transform
    stop = worst > c["max_residual_m"]
    rep.append(("STOP: residual above %.0f m (%.0f m)" % (c["max_residual_m"], worst)) if stop else f"residual check: worst control-point residual {worst:.0f} m <= {c['max_residual_m']:.0f} m: OK")
    sq = squares_majority(labels, m, sites, c)
    filled = fill_missing(sq, sites, c["min_valid_share"], c["fill_radius_m"])
    table = to_table(filled)
    names = [s for s, _ in SERIES]
    n_all = len(table)
    rep.append(f"squares: {n_all}; with a series {int(table.soil_series.notna().sum())}; filled from a neighbour (valid share < {c['min_valid_share']}): {int(table.soil_filled.sum())}; "
               f"left empty (nothing within {c['fill_radius_m']:.0f} m): {int(table.soil_series.isna().sum())}")
    rep.append("squares per series: " + json.dumps(table.soil_series.value_counts().to_dict()))
    rep.append("squares per texture: " + json.dumps(table.soil_texture.value_counts().to_dict()))
    rep.append(f"purity below {c['purity_low']}: {int((table.purity < c['purity_low']).sum())} squares; mean purity {table.purity.mean():.3f}")
    summary = {"rep": rep, "table": table, "stop": stop, "labels": labels, "labels0": labels0, "M": m, "img": img, "ref": ref, "graticule": g, "sites": sites, "geom": geom, "filled": filled}
    if not stop:
        table.to_csv(out / "site_soil_lgu.csv", index=False)
        (out / "soil_lgu_report.txt").write_text("\n".join(rep) + "\n", encoding="utf-8")
    if qa_dir:
        qa_pictures(summary, Path(qa_dir), c)
    return summary


def qa_pictures(s, qa_dir, cfg=None):
    """Side by side: the LGU map warped to UTM and our squares coloured by series at the same extent; purity; the old legacy textures."""
    import cv2
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    c = LGU_CFG if cfg is None else cfg
    qa_dir.mkdir(parents=True, exist_ok=True)
    sites, tab = s["sites"], s["table"]
    d = sites.merge(tab, on="point_id")
    leg = legend_colours(s["img"], c) / 255.0
    names = [n for n, _ in SERIES]
    e0, e1 = d.utm_e.min() - 500, d.utm_e.max() + 500
    n0, n1 = d.utm_n.min() - 500, d.utm_n.max() + 500
    cell = 12.5
    w, h = int((e1 - e0) / cell), int((n1 - n0) / cell)
    a = np.array([[1 / cell, 0, -e0 / cell - 0.5], [0, -1 / cell, n1 / cell - 0.5]]) @ np.vstack([s["M"], [0, 0, 1]])
    warped = cv2.warpAffine(s["img"], a.astype(np.float64), (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    ext = [e0, e1, n0, n1]

    def squares(ax, colour_of, title):
        ax.set_facecolor("white")
        ax.scatter(d.utm_e, d.utm_n, c=colour_of, s=2.2, marker="s", linewidths=0)
        ax.set_xlim(e0, e1); ax.set_ylim(n0, n1); ax.set_aspect("equal"); ax.set_title(title, fontsize=10); ax.tick_params(labelsize=6)

    fig, ax = plt.subplots(1, 2, figsize=(16, 7.5))
    ax[0].imshow(warped, extent=ext, origin="upper"); ax[0].set_title("LGU soil map (CLUP Figure 1-3), placed on our coordinates", fontsize=10); ax[0].tick_params(labelsize=6)
    col = [leg[k] if k is not None and k == k else (0.8, 0.8, 0.8) for k in [names.index(x) if isinstance(x, str) else None for x in d.soil_series]]
    squares(ax[1], col, "Our 100 m squares coloured by soil series (grey = no series)")
    ax[1].legend(handles=[Patch(color=leg[i], label=f"{n} ({t})") for i, (n, t) in enumerate(SERIES)], fontsize=7, loc="lower right")
    fig.suptitle("Soil: LGU map and our squares at the same extent (provisional, digitized by us)")
    fig.tight_layout(); fig.savefig(qa_dir / "01_lgu_map_and_our_squares.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 7.5))
    sc = ax.scatter(d.utm_e, d.utm_n, c=d.purity, s=2.2, marker="s", cmap="viridis", vmin=0.3, vmax=1.0, linewidths=0)
    ax.set_aspect("equal"); ax.set_title("Purity: share of the valid map pixels of a square that are in its series"); fig.colorbar(sc, ax=ax, shrink=0.7)
    fig.tight_layout(); fig.savefig(qa_dir / "02_purity.png", dpi=130); plt.close(fig)
    tex_col = {"Clay": "#6c7fc4", "Clay Loam": "#d9a066", "Loam": "#6fae6a", "Silt Loam": "#e6c84a", "Sandy Loam": "#b9cfd8"}
    fig, ax = plt.subplots(figsize=(9, 7.5))
    ax.scatter(d.utm_e, d.utm_n, c=[tex_col.get(t, "#c8c8c8") for t in d.soil_texture_legacy], s=2.2, marker="s", linewidths=0)
    ax.set_aspect("equal"); ax.set_title("OLD legacy soil textures (4 world-soil-database codes, grey = none)")
    ax.legend(handles=[Patch(color=v, label=k) for k, v in tex_col.items()], fontsize=8, loc="lower right")
    fig.tight_layout(); fig.savefig(qa_dir / "03_legacy_textures.png", dpi=130); plt.close(fig)
    lab = s["labels"]
    cls_rgb = np.full(lab.shape + (3,), 255, np.uint8)
    for i in range(len(SERIES)):
        cls_rgb[lab == i] = (leg[i] * 255).astype(np.uint8)
    cv2.imwrite(str(qa_dir / "04_classified_map_pixels.png"), cv2.cvtColor(np.hstack([s["img"], cls_rgb]), cv2.COLOR_RGB2BGR))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("render", help="extract the soil map picture from the two PDFs")
    cp = sub.add_parser("compute", help="georeference, classify and write data/processed/site_soil_lgu.csv")
    cp.add_argument("--out", default="data/processed")
    cp.add_argument("--qa-dir", default=None, help="folder (outside the repo) for the QA pictures")
    a = ap.parse_args(argv)
    if a.cmd == "render":
        for f, w, h in render():
            print(f"{f}: {w} x {h} px")
        return 0
    s = run(a.out, a.qa_dir)
    print("\n".join(s["rep"]))
    return 2 if s["stop"] else 0


if __name__ == "__main__":
    sys.exit(main())
