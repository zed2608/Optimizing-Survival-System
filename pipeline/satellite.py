#!/usr/bin/env python3
"""
satellite.py - a "how current is the satellite picture, really" map layer (round 23, provisional).

Why this exists: the defense panel's signed revision form asks for the system to be "online / real-time"; the team's own
reading of that (confirmed with them directly) is a satellite view where changes on the ground - new buildings, cleared
land, newly planted trees - show up as currently as possible. There is no free or paid public service that streams literal
real-time satellite video; this module gets as close as is honestly possible with free data:
  - Sentinel-2 (optical, true colour): the most RECENT CLOUD-FREE pass available. In San Mateo's tropical climate a clear
    shot can genuinely be 1-4+ weeks old even though the satellite itself revisits every ~5 days, because a cloudy pass is
    simply unusable and skipped. This module never claims a date it cannot back up; see fetch_tile()'s returned "note".
  - Sentinel-1 (radar, SAR, VV polarisation): clouds do NOT block radar, so this one genuinely updates every revisit
    (~6-12 days combining both satellites) regardless of weather. It looks grayscale and speckled, not like a normal aerial
    photo - good for seeing that SOMETHING changed, not for reading fine detail. Labelled as such in the UI, never passed
    off as an optical photo.
Both come from the Copernicus Data Space Ecosystem's Sentinel Hub Process API (free, ESA-operated, the same programme this
project already cites for the 2021 ESA WorldCover ground-cover layer - see docs/DATA_SOURCES.md). Nothing here changes a
score, a rank or a plan: this is a map layer only, exactly like the existing Esri/OSM basemap toggle it sits beside.

Library module (used by api_v2.py; no web framework code here). Credentials (COPERNICUS_CLIENT_ID / COPERNICUS_CLIENT_SECRET,
an OAuth client created by the team in the Copernicus dashboard) are read from the environment ONLY - never hardcoded, never
written to a file in this repo (same rule CLAUDE.md states for every other key this project uses). Without them, every call
here returns {"available": False, ...} rather than failing loudly - this layer is optional and must degrade quietly.

Tiles are served through our own backend (GET /satellite-tile/{layer}/{z}/{x}/{y}.png in api_v2.py) rather than a direct
Leaflet-to-Copernicus WMS URL, because the Process API this module uses needs a short-lived OAuth bearer token and a
hand-written evalscript per layer (no pre-registered "Configuration/Instance ID" to manage on the Copernicus side), and
because every tile is cached on disk here so a busy map session does not burn through Sentinel Hub's free-tier request
quota one tile request at a time.
"""
import json, os, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CFG = {
    "token_url": "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
    "process_url": "https://sh.dataspace.copernicus.eu/api/v1/process",
    "request_timeout_s": 20,
    "token_margin_s": 60,          # refresh the OAuth token this many seconds before it actually expires
    "tile_px": 256,                # standard Leaflet/OSM tile size
    "tile_cache_hours": 24,        # a tile already fetched today is reused rather than re-requested (free-tier quota)
    "s2_search_days": 30,          # how far back to let the "least cloudy" mosaic look for a usable Sentinel-2 pass
    "s1_search_days": 20,          # Sentinel-1 only needs to look back far enough to catch one more revisit (~6-12 days)
    "max_zoom": 16,                # finer zooms would ask Sentinel Hub for a tiny-area, low-value image; the frontend caps the layer at this zoom
    "min_zoom": 9,
}

TRUE_COLOR_EVALSCRIPT = """//VERSION=3
function setup() {
  return { input: [{ bands: ["B02", "B03", "B04"], units: "REFLECTANCE" }], output: { bands: 3, sampleType: "AUTO" } };
}
function evaluatePixel(sample) {
  // a mild gain: raw top-of-atmosphere reflectance renders too dark to read without it
  const g = 2.8;
  return [sample.B04 * g, sample.B03 * g, sample.B02 * g];
}
"""

# Sentinel-1 VV in decibels, linearly stretched from a typical land-backscatter range (-20..0 dB) to 0..1 grayscale. This is
# a standard, widely-used visualisation choice for SAR, not a measured calibration - good enough to see "something changed
# here", not for reading an exact value. Radar can't be blocked by cloud, which is the whole reason it's offered at all.
RADAR_EVALSCRIPT = """//VERSION=3
function setup() {
  return { input: [{ bands: ["VV"], units: "DB" }], output: { bands: 1, sampleType: "AUTO" } };
}
function evaluatePixel(sample) {
  const v = Math.min(1, Math.max(0, (sample.VV + 20) / 20));
  return [v];
}
"""

LAYERS = {
    "optical": {"collection": "sentinel-2-l2a", "evalscript": TRUE_COLOR_EVALSCRIPT, "search_days": CFG["s2_search_days"],
                "mosaicking": "ORBIT", "label": "Recent satellite photo (Sentinel-2)",
                "note": "The most recent CLOUD-FREE pass available - in this climate that can genuinely be weeks old, since a cloudy pass is unusable and skipped. Not a live feed."},
    "radar": {"collection": "sentinel-1-grd", "evalscript": RADAR_EVALSCRIPT, "search_days": CFG["s1_search_days"],
              "mosaicking": "ORBIT", "label": "Radar change view (Sentinel-1)",
              "note": "Radar sees through cloud, so this updates every revisit (about 6-12 days) regardless of weather - but it looks grayscale and speckled, not like a normal photo. Good for spotting that something changed, not for reading fine detail."},
}


class SatelliteUnavailable(Exception):
    """Raised (and always caught) when a tile cannot be produced: missing credentials, the service refused the request, or
    the network failed. Never invented - the caller falls back to a plain 'not available' tile, never a guess."""


def now_utc():
    return datetime.now(timezone.utc)


def credentials():
    """(client_id, client_secret) from the environment, or (None, None) if either is missing - this layer is optional and
    must not crash the app when they are not set (e.g. a local dev run, or before the team has added them in Render)."""
    return os.environ.get("COPERNICUS_CLIENT_ID") or None, os.environ.get("COPERNICUS_CLIENT_SECRET") or None


# ---- OAuth token: one short-lived bearer token, reused across tile requests until shortly before it expires ----
_TOKEN = {"value": None, "expires_at": 0.0}


def _http(url, *, data=None, headers=None, timeout=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout or CFG["request_timeout_s"]) as r:
        body = r.read()
        if r.status >= 400:
            raise SatelliteUnavailable(f"HTTP {r.status} from {url}")
        return body


def get_token(cfg=None, *, force=False):
    """A valid OAuth bearer token (client_credentials grant), cached in memory and refreshed just before it expires.
    Raises SatelliteUnavailable if credentials are missing or the token request fails - callers always catch this."""
    c = CFG if cfg is None else cfg
    if not force and _TOKEN["value"] and time.monotonic() < _TOKEN["expires_at"]:
        return _TOKEN["value"]
    client_id, client_secret = credentials()
    if not client_id or not client_secret:
        raise SatelliteUnavailable("COPERNICUS_CLIENT_ID / COPERNICUS_CLIENT_SECRET are not set")
    body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}).encode()
    try:
        resp = json.loads(_http(c["token_url"], data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=c["request_timeout_s"]))
    except (urllib.error.URLError, TimeoutError, OSError, SatelliteUnavailable, json.JSONDecodeError) as ex:
        raise SatelliteUnavailable(f"could not get an access token: {ex}") from ex
    token, ttl = resp.get("access_token"), resp.get("expires_in")
    if not token:
        raise SatelliteUnavailable("the token response had no access_token")
    _TOKEN["value"], _TOKEN["expires_at"] = token, time.monotonic() + max(30, int(ttl or 300) - c["token_margin_s"])
    return token


# ---- slippy-map tile math: z/x/y -> a Web Mercator (EPSG:3857) bounding box, same convention Leaflet/OSM/Esri use ----
_WEB_MERCATOR_EXTENT = 20037508.342789244


def tile_bbox_3857(z, x, y):
    n = 2 ** z
    lon_left, lon_right = x / n * 360.0 - 180.0, (x + 1) / n * 360.0 - 180.0

    def lat_of(yt):
        import math
        t = math.pi * (1 - 2 * yt / n)
        return math.degrees(math.atan(math.sinh(t)))
    lat_top, lat_bottom = lat_of(y), lat_of(y + 1)

    def merc_x(lon):
        return lon / 180.0 * _WEB_MERCATOR_EXTENT

    def merc_y(lat):
        import math
        lat_rad = math.radians(lat)
        return math.log(math.tan(math.pi / 4 + lat_rad / 2)) / math.pi * _WEB_MERCATOR_EXTENT
    return [merc_x(lon_left), merc_y(lat_bottom), merc_x(lon_right), merc_y(lat_top)]


def cache_path(cache_dir, layer, z, x, y, bucket):
    return Path(cache_dir) / f"{layer}_{z}_{x}_{y}_{bucket}.png"


def _date_bucket(c):
    """Today's date (UTC): tiles are cached per day, so a busy session reuses the same file instead of re-asking
    Sentinel Hub per request, while the layer still picks up a newer pass the next day it is opened."""
    return now_utc().date().isoformat()


def fetch_tile(layer, z, x, y, cache_dir, cfg=None):
    """One PNG tile (bytes) for `layer` ("optical" or "radar") at slippy-map z/x/y, disk-cached for cfg['tile_cache_hours'].
    Returns (png_bytes, meta) on success, or raises SatelliteUnavailable (credentials missing, zoom out of range, or the
    service failed) - the API layer turns that into a plain-words 'not available' response, never a fabricated image."""
    c = CFG if cfg is None else cfg
    if layer not in LAYERS:
        raise SatelliteUnavailable(f"unknown layer '{layer}'")
    if not (c["min_zoom"] <= z <= c["max_zoom"]):
        raise SatelliteUnavailable(f"zoom {z} is outside the served range {c['min_zoom']}-{c['max_zoom']}")
    spec = LAYERS[layer]
    bucket = _date_bucket(c)
    path = cache_path(cache_dir, layer, z, x, y, bucket)
    if path.is_file():
        return path.read_bytes(), {"cached": True, "layer": layer, **{k: spec[k] for k in ("label", "note")}}

    token = get_token(c)
    bbox = tile_bbox_3857(z, x, y)
    end = now_utc()
    start = end - timedelta(days=spec["search_days"])
    payload = {
        "input": {
            "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/3857"}},
            "data": [{"type": spec["collection"], "dataFilter": {"timeRange": {"from": start.strftime("%Y-%m-%dT00:00:00Z"), "to": end.strftime("%Y-%m-%dT23:59:59Z")},
                      "mosaickingOrder": "leastCC" if layer == "optical" else "mostRecent"}}],
        },
        "output": {"width": c["tile_px"], "height": c["tile_px"], "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
        "evalscript": spec["evalscript"],
    }
    try:
        png = _http(c["process_url"], data=json.dumps(payload).encode(), timeout=c["request_timeout_s"],
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "image/png"})
    except (urllib.error.URLError, TimeoutError, OSError, SatelliteUnavailable) as ex:
        # one retry with a freshly forced token, in case the cached one had just gone stale server-side
        try:
            token = get_token(c, force=True)
            png = _http(c["process_url"], data=json.dumps(payload).encode(), timeout=c["request_timeout_s"],
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "image/png"})
        except Exception as ex2:
            raise SatelliteUnavailable(f"Sentinel Hub request failed: {ex2}") from ex2
    try:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
    except OSError:
        pass  # a cache write failure should never break serving the tile that was just fetched
    return png, {"cached": False, "layer": layer, **{k: spec[k] for k in ("label", "note")}}


def status(cache_dir=None, cfg=None):
    """For GET /health and the Map view menu: whether this layer can work at all right now (credentials present), without
    spending a Sentinel Hub request just to check - a token fetch only happens the first time a tile is actually asked for."""
    client_id, _ = credentials()
    return {"available": bool(client_id), "layers": {k: {"label": v["label"], "note": v["note"]} for k, v in LAYERS.items()},
            "note": "Needs COPERNICUS_CLIENT_ID / COPERNICUS_CLIENT_SECRET set as environment variables; unset means this layer is simply not offered, not an error." if not client_id else None}
