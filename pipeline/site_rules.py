"""
site_rules.py - rules that come from interviews with the LGU, the MPDC, the MAO and the MENRO (round 15a). ALL PROVISIONAL: each one cites who said it and when.
Nothing here edits the species table; the rules are applied when a ranking or a plan is made.

  REHAB   Squares in the Sanitary Landfill and Special Reserved zones: fruit or produce from a landfill or mining site may hold heavy metals. Food-bearing species planted there get
          the flag rehab_site_food_warning (a warning only: they are not excluded and S and P do not change).
          Source: MAO (Alexis P. Santos, OIC-MAO), 7 Oct 2026.
  HABAGAT The lowland barangays Maly, Dulong Bayan I and II and Santa Ana are off-season for planting in Jul-Sep (heavy rain and flooding wash out seedlings): when the planting
          window touches those months, the site match S of those squares is multiplied by 0.8 (the MAO's example figure for about 20% lower survival).
          Source: MAO (Alexis P. Santos, OIC-MAO), 7 Oct 2026.
"""
import re
import numpy as np
import pandas as pd

# =====================================================================================================================
# CONFIG - PROVISIONAL (interviews of 7 Oct 2026); to be confirmed by the agriculturist
# =====================================================================================================================
REHAB_ZONES = ("Sanitary Landfill", "Special Reserved Zone")
REHAB_FLAG = "rehab_site_food_warning"
REHAB_WARNING = "Fruit or produce from a landfill or mining site may hold heavy metals; do not plan to eat or sell it without testing."
REHAB_SOURCE = "MAO (Alexis P. Santos, OIC-MAO), interview of 7 Oct 2026; provisional"
# a species is food-bearing when its TYPE text (use_tags / category_raw of species_clean.csv) says so; the free text of common_uses is not used
FOOD_USE_TAGS = ("fruit", "fruit tree", "fruit shrub", "nut tree", "vegetable", "palm", "beverage")
FOOD_CATEGORY_WORDS = ("fruit", "vegetable", "nut", "beverage")
FOOD_USES_PATTERN = re.compile(r"\bedible\b|\bvegetable\b", re.I)

HABAGAT_CFG = {
    "barangays": ("MALY", "DULONG BAYAN I", "DULONG BAYAN II", "STA ANA"),     # as written in data/BRGY_BOUNDARY.shp (upper case)
    "months": (7, 8, 9),                                                      # Jul, Aug, Sep
    "multiplier": 0.8,                                                        # the MAO's example figure for about 20% lower survival
    "source": "MAO (Alexis P. Santos, OIC-MAO), interview of 7 Oct 2026; provisional (the 20% is his example figure, not a measurement)",
}
HABAGAT_FLAG = "habagat_washout"
HABAGAT_WARNING = "Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep"
# =====================================================================================================================


def _tokens(text):
    return {t.strip().lower() for t in re.split(r"[;,/]", str(text)) if t.strip()} if isinstance(text, str) else set()


def food_bearing(row):
    """True when the type text of one species row says it bears food (fruit, nut, vegetable, coffee or cacao beverage crop, palm)."""
    tags = _tokens(row.get("use_tags"))
    cat = str(row.get("category_raw") or "").lower()
    return bool(tags & set(FOOD_USE_TAGS)) or any(w in cat for w in FOOD_CATEGORY_WORDS)


def food_bearing_ids(species):
    """{species_id} of the food-bearing species of a species table."""
    return {int(r["species_id"]) for r in species.to_dict("records") if food_bearing(r)}


def rehab_zone(zone_desc):
    return isinstance(zone_desc, str) and zone_desc in REHAB_ZONES


def rehab_flags(zone_desc, species_id, food_ids):
    """[REHAB_FLAG] when the square is in a rehabilitation zone and the species is food-bearing, else []."""
    return [REHAB_FLAG] if rehab_zone(zone_desc) and int(species_id) in food_ids else []


# ---- Habagat ---------------------------------------------------------------------------------------------------------
def habagat_months_hit(window_months, cfg=None):
    """The months of the planting window that are Habagat months (sorted); empty = the multiplier does not apply."""
    c = HABAGAT_CFG if cfg is None else cfg
    return sorted(set(int(m) for m in (window_months or [])) & set(c["months"]))


def habagat_square_mask(barangay_names, cfg=None):
    """Boolean array: which squares lie in a Habagat barangay (barangay_names = the shapefile name of each square, '' or None when outside)."""
    c = HABAGAT_CFG if cfg is None else cfg
    b = {x.upper() for x in c["barangays"]}
    return np.array([isinstance(n, str) and n.strip().upper() in b for n in barangay_names], dtype=bool)


def habagat_factor(barangay_names, window_months, cfg=None):
    """Multiplier per square: cfg multiplier for squares of the Habagat barangays when the window touches Jul-Sep, else 1."""
    c = HABAGAT_CFG if cfg is None else cfg
    f = np.ones(len(barangay_names))
    if habagat_months_hit(window_months, c):
        f[habagat_square_mask(barangay_names, c)] = float(c["multiplier"])
    return f


def habagat_info(window_months, cfg=None):
    """The block shown with a score (and saved in a plan summary): what applies, why, from whom."""
    c = HABAGAT_CFG if cfg is None else cfg
    hit = habagat_months_hit(window_months, c)
    return {"applies_to_window": bool(hit), "months_hit": hit, "multiplier": float(c["multiplier"]), "barangays": list(c["barangays"]), "months": list(c["months"]),
            "warning": HABAGAT_WARNING, "source": c["source"], "provisional": True}
