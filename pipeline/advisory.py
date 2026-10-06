#!/usr/bin/env python3
"""
advisory.py - Day 4 part 2: a weather advisory for planting one species at one place.

Library module (used by api_v2.py GET /advisory/seasonal). It
  1. gets a 16-day forecast (daily rain sum, max and min temperature) from Open-Meteo (https://api.open-meteo.com/v1/forecast, no key),
     caches each response on disk for CACHE_HOURS and falls back to the cache when the network fails;
  2. compares the forecast and the date with the species' planting_months and drought_tol and returns warnings, each with a
     code, a plain sentence and the numbers behind it.
Nothing is invented: a missing forecast field is reported in not_assessed and the warning that needs it is not issued.
The advisory is a PLANNING AID. The forecast source is Open-Meteo. The ENSO status is set by hand in CFG (a forecast cannot tell it).
"""
import json, os, re, tempfile, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# =====================================================================================================================
# CONFIG - every tunable number lives here. PROVISIONAL until the agriculturist / LGU sign off.
# =====================================================================================================================
CFG = {
    "open_meteo_url": "https://api.open-meteo.com/v1/forecast",
    "forecast_days": 16,                # days requested (Open-Meteo allows up to 16)
    "daily_fields": ["precipitation_sum", "temperature_2m_max", "temperature_2m_min"],
    "timezone": "Asia/Manila",          # sent to Open-Meteo so daily values are local days
    "utc_offset_hours": 8,              # Philippines, no daylight saving: used for "today" and "this month"
    "request_timeout_s": 10,            # network timeout
    "cache_hours": 3,                   # ADVISORY_CACHE_HOURS: a cached response younger than this is used without calling the network
    "cache_coord_decimals": 2,          # lat/lon rounded to this many decimals (about 1 km) for the request and the cache key
    "dry_spell_days": 7,                # window for the dry-spell check
    "dry_spell_mm": 20.0,               # DRY_SPELL_MM: rain total over the window below this = dry spell (provisional)
    "heavy_rain_mm": 80.0,              # HEAVY_RAIN_MM: any single day above this = heavy rain (provisional)
    "enso_status": "none",              # ENSO_STATUS: none | watch | alert. Set BY HAND; the forecast cannot tell us this.
    "enso_source": "not set: update by hand from an official outlook (for example PAGASA) and write the source and date here",
    "month_names": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}
# =====================================================================================================================

ENSO_VALUES = ("none", "watch", "alert")
DISCLAIMER = ("This advisory is a planning aid, not a guarantee. It compares a short weather forecast with the species' planting "
              "months and drought tolerance; local conditions on the day decide.")
SOURCE = {"name": "Open-Meteo", "url": "https://open-meteo.com/", "forecast_api": CFG["open_meteo_url"],
          "note": "16-day daily forecast: rain sum, maximum and minimum temperature (no API key)"}


class ForecastUnavailable(Exception):
    """No fresh forecast could be fetched and there is no cached one."""


def now_utc():
    return datetime.now(timezone.utc)


def today_local(cfg=None):
    c = CFG if cfg is None else cfg
    return (now_utc() + timedelta(hours=c["utc_offset_hours"])).date()


def http_get(url, params, timeout):
    """Return the parsed JSON of a GET request (tests replace this function; they never use the internet)."""
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full, timeout=timeout) as r:
        if r.status != 200:
            raise RuntimeError(f"Open-Meteo answered HTTP {r.status}")
        return json.loads(r.read().decode("utf-8"))


def _valid(resp):
    return isinstance(resp, dict) and isinstance(resp.get("daily"), dict) and isinstance(resp["daily"].get("time"), list) and bool(resp["daily"]["time"])


def cache_path(cache_dir, lat, lon, cfg=None):
    c = CFG if cfg is None else cfg
    d = c["cache_coord_decimals"]
    return Path(cache_dir) / f"openmeteo_{lat:.{d}f}_{lon:.{d}f}_{c['forecast_days']}d.json"


def fetch_forecast(lat, lon, cache_dir, cfg=None):
    """
    Forecast for (lat, lon). Returns {"daily", "units", "fetched_at", "cached", "cache_age_minutes", "stale", "network_error"}.
    Order: fresh cache (younger than cache_hours) -> network -> any cache (cached:true, stale if old) -> ForecastUnavailable.
    """
    c = CFG if cfg is None else cfg
    lat, lon = round(float(lat), c["cache_coord_decimals"]), round(float(lon), c["cache_coord_decimals"])
    path = cache_path(cache_dir, lat, lon, c)
    now = now_utc()
    cached = None
    if path.exists():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if _valid(doc.get("response")):
                cached = (doc, (now - datetime.fromisoformat(doc["fetched_at"])).total_seconds() / 60.0)
        except (ValueError, KeyError, OSError):
            cached = None
    def result(doc, age, from_cache, error=None):
        r = doc["response"]
        return {"daily": r["daily"], "units": r.get("daily_units", {}), "fetched_at": doc["fetched_at"], "cached": from_cache,
                "cache_age_minutes": round(age, 1) if from_cache else 0.0, "stale": bool(from_cache and age > c["cache_hours"] * 60),
                "network_error": error}
    if cached and cached[1] < c["cache_hours"] * 60:
        return result(cached[0], cached[1], True)
    err = None
    try:
        resp = http_get(c["open_meteo_url"], {"latitude": lat, "longitude": lon, "daily": ",".join(c["daily_fields"]),
                                              "forecast_days": c["forecast_days"], "timezone": c["timezone"]}, c["request_timeout_s"])
        if not _valid(resp):
            raise ValueError("Open-Meteo returned no daily forecast")
        doc = {"fetched_at": now.isoformat(), "lat": lat, "lon": lon, "response": resp}
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        os.replace(tmp, path)
        return result(doc, 0.0, False)
    except Exception as ex:                                              # network down, timeout, bad JSON, ...
        err = f"{type(ex).__name__}: {ex}"
    if cached:
        return result(cached[0], cached[1], True, err)
    raise ForecastUnavailable(f"The weather forecast service (Open-Meteo) could not be reached and there is no cached forecast for this "
                              f"place yet ({err}). Try again later.")


def parse_months(value):
    if value is None or (isinstance(value, float) and value != value) or str(value).strip() == "":
        return None
    return sorted({int(x) for x in re.split(r"[;,]", str(value)) if x.strip()})


def _num(v):
    return None if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or v != v else float(v)


def forecast_table(daily, today=None):
    """Rows (date, rain_mm, tmax_c, tmin_c) from today on; a missing value stays None."""
    rows = []
    t = daily["time"]
    get = lambda k, i: _num(daily[k][i]) if isinstance(daily.get(k), list) and i < len(daily[k]) else None
    for i, ds in enumerate(t):
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            continue
        if today is not None and d < today:
            continue
        rows.append({"date": ds, "rain_mm": get("precipitation_sum", i), "tmax_c": get("temperature_2m_max", i), "tmin_c": get("temperature_2m_min", i)})
    return rows


def build_advisory(species, forecast, today=None, cfg=None, window=None):
    """
    species: dict-like with species_id, common_name, planting_months ('5;6;7'), drought_tol (Low/Medium/High).
    forecast: the dict from fetch_forecast. Returns {"warnings": [...], "not_assessed": [...], "forecast": [...], "summary": {...}, ...}.
    window (optional): {"months": [5, 6], "label": "1 May - 29 Jun 2027"}: the planting dates of a plan. The planting-window warning then compares the species' planting months
    with THOSE months instead of today's month. Without it the check uses today's month, as before.
    """
    c = CFG if cfg is None else cfg
    today = today_local(c) if today is None else today
    mn = c["month_names"]
    rows = forecast_table(forecast["daily"], today)
    warnings, not_assessed = [], []
    months = parse_months(species.get("planting_months"))
    tol = species.get("drought_tol")
    tol = tol if isinstance(tol, str) and tol in ("Low", "Medium", "High") else None
    name = species.get("common_name", "This species")

    # 1. planting window
    if months is None:
        not_assessed.append({"code": "not_in_planting_window", "reason": "the species has no planting_months in the dataset"})
    elif window is not None:
        win = list(window["months"])
        inside = [m for m in win if m in months]
        if len(inside) < len(win):
            where = "outside that window" if not inside else "only partly inside that window"
            warnings.append({"code": "not_in_planting_window",
                             "message": f"{name} is usually planted in {', '.join(mn[m - 1] for m in months)}; your planting dates ({window['label']}) cover "
                                        f"{', '.join(mn[m - 1] for m in win)}, {where}.",
                             "numbers": {"window_months": win, "planting_months": months, "months_in_window": inside}})
    elif today.month not in months:
        warnings.append({"code": "not_in_planting_window",
                         "message": f"{name} is usually planted in {', '.join(mn[m - 1] for m in months)}; today is in {mn[today.month - 1]}, outside that window.",
                         "numbers": {"current_month": today.month, "planting_months": months}})

    # 2. dry spell: rain total over the next N days, all days must have a value
    win = rows[:c["dry_spell_days"]]
    rains = [r["rain_mm"] for r in win]
    total = None
    if len(win) < c["dry_spell_days"] or any(v is None for v in rains):
        not_assessed.append({"code": "dry_spell", "reason": f"the forecast has rain values for only {sum(v is not None for v in rains)} of the next "
                                                            f"{c['dry_spell_days']} days"})
    elif tol is None:
        not_assessed.append({"code": "dry_spell", "reason": "the species has no drought_tol in the dataset"})
    else:
        total = round(sum(rains), 1)
        if total < c["dry_spell_mm"] and tol != "High":
            warnings.append({"code": "dry_spell",
                             "message": f"Only {total} mm of rain is forecast for the next {c['dry_spell_days']} days (threshold {c['dry_spell_mm']:g} mm) and {name} "
                                        f"has {tol.lower()} drought tolerance: new plantings may need watering.",
                             "numbers": {"forecast_rain_mm": total, "days": c["dry_spell_days"], "threshold_mm": c["dry_spell_mm"], "drought_tol": tol}})

    # 3. heavy rain: any forecast day above the threshold
    known = [r for r in rows if r["rain_mm"] is not None]
    if not known:
        not_assessed.append({"code": "heavy_rain", "reason": "the forecast has no rain values"})
    else:
        heavy = [r for r in known if r["rain_mm"] > c["heavy_rain_mm"]]
        if heavy:
            worst = max(heavy, key=lambda r: r["rain_mm"])
            warnings.append({"code": "heavy_rain",
                             "message": f"Heavy rain is forecast: up to {worst['rain_mm']:g} mm on {worst['date']} (threshold {c['heavy_rain_mm']:g} mm in one day). "
                                        "Avoid planting on or just before those days.",
                             "numbers": {"max_daily_rain_mm": worst["rain_mm"], "date": worst["date"], "threshold_mm": c["heavy_rain_mm"],
                                         "days_above_threshold": [{"date": r["date"], "rain_mm": r["rain_mm"]} for r in heavy]}})
        if len(known) < len(rows):
            not_assessed.append({"code": "heavy_rain_partial", "reason": f"{len(rows) - len(known)} forecast day(s) have no rain value and were not checked"})

    # 4. ENSO, set by hand
    enso = {"status": c["enso_status"], "source": c["enso_source"], "note": "Set by hand in the configuration; the weather forecast cannot tell us this."}
    if c["enso_status"] not in ENSO_VALUES:
        raise ValueError(f"enso_status must be one of {ENSO_VALUES}")
    if c["enso_status"] in ("watch", "alert"):
        if tol is None:
            not_assessed.append({"code": "enso_manual", "reason": "the species has no drought_tol in the dataset"})
        elif tol == "Low":
            warnings.append({"code": "enso_manual",
                             "message": f"An ENSO {c['enso_status']} is set (source: {c['enso_source']}) and {name} has low drought tolerance: "
                                        "a drier season is possible, plan for watering or delay planting.",
                             "numbers": {"enso_status": c["enso_status"], "drought_tol": tol, "enso_source": c["enso_source"]}})

    temps = [r["tmax_c"] for r in rows if r["tmax_c"] is not None], [r["tmin_c"] for r in rows if r["tmin_c"] is not None]
    summary = {"today": today.isoformat(), "forecast_days": len(rows), "rain_next_window_mm": total, "rain_window_days": c["dry_spell_days"],
               "max_daily_rain_mm": max((r["rain_mm"] for r in known), default=None),
               "tmax_c_max": max(temps[0], default=None), "tmin_c_min": min(temps[1], default=None)}
    return {"warnings": warnings, "not_assessed": not_assessed, "forecast": rows, "summary": summary, "enso": enso,
            "thresholds": {"dry_spell_mm": c["dry_spell_mm"], "dry_spell_days": c["dry_spell_days"], "heavy_rain_mm": c["heavy_rain_mm"]},
            "disclaimer": DISCLAIMER, "forecast_source": SOURCE}
