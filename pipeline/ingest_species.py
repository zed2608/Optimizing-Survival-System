#!/usr/bin/env python3
"""
ingest_species.py - Day 1 loader for the 45-species dataset.

Reads the DirectSource CSV (every cell looks like  `value [Source: url]`), splits each cell into a clean
value plus a source row, normalizes the values, and writes:

    data/processed/species_clean.csv      one row per species, clean typed values
    data/processed/species_sources.csv    one row per cited cell: value, URL, rank, flags
    data/processed/species_references.csv species-level reference URLs (old reference_url column)
    data/processed/ingest_report.csv      every issue found (format, vocabulary, ranges, off-list sources)
    data/processed/soil_map_review.csv    soil text -> texture class mapping, for the agriculturist to check
    data/processed/tag_maps_root.csv      PROVISIONAL root-type scores (proposal, to be validated)
    data/processed/tag_maps_urban.csv     PROVISIONAL urban_suitability tag -> purpose map (to be validated)
    data/processed/optimizing_survival.db SQLite: dataset_versions, species, species_sources, species_references

Rules this script follows (do not weaken them):
  * It never invents a value. Missing / "Data Unavailable" stays empty (NULL).
  * Every value keeps its source URL; nothing is dropped silently - problems go to ingest_report.csv.
  * Interpretations (soil classes, tags, scores) are labelled provisional until the agriculturist signs off.

Usage:
    python pipeline/ingest_species.py --input data/raw/species_directsource.csv \
        --sources data/raw/sources_list.csv --out data/processed
"""
import argparse, csv, hashlib, re, sqlite3, sys, datetime as dt
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse, unquote

import pandas as pd

# ----------------------------------------------------------------------------------------------
# Source ranking (edit here). Rank 1 DENR/DA/DOST-PCAARRD; 2 local academic/botanical;
# 3 international references; 4 unranked. "basis" says whether the domain was named in the
# hierarchy you gave, or assigned by us and still needs your confirmation.
# ----------------------------------------------------------------------------------------------
RANK_RULES = [
    (1, "named", ["denr.gov.ph", "da.gov.ph", "pcaarrd.dost.gov.ph", "dost.gov.ph"]),
    (2, "named", ["stuartxchange.org", "stuartxchange.com", "ateneo.edu"]),
    (2, "assigned_confirm", ["ciit.edu.ph", "journals.uplb.edu.ph", "repository.mainlib.upd.edu.ph", "mjst.ustp.edu.ph"]),
    (3, "named", ["nparks.gov.sg", "prosea.prota4u.org", "cabi.org", "powo.science.kew.org"]),
    (3, "assigned_confirm", ["apps.worldagroforestry.org", "tropical.theferns.info", "worldfloraonline.org",
                              "feedipedia.org", "ecocrop.apps.fao.org", "pfaf.org", "hear.org",
                              "portal.cybertaxonomy.org", "tandfonline.com", "aggie-horticulture.tamu.edu",
                              "uog.edu", "projects.sare.org", "ir.library.oregonstate.edu", "avocadosource.com"]),
    (4, "mirror_rerank", ["scribd.com", "studocu.com", "researchgate.net", "scispace.com"]),
]

def rank_of(url):
    """-> (rank or None, basis)"""
    if not url or not url.lower().startswith("http"):
        return None, "file_not_provided"
    host = urlparse(url).netloc.lower().replace("www.", "")
    for rank, basis, hosts in RANK_RULES:
        if any(host == h or host.endswith("." + h) for h in hosts):
            return rank, basis
    return 4, "unranked"

# ----------------------------------------------------------------------------------------------
# Header map: original DirectSource header -> internal column name
# ----------------------------------------------------------------------------------------------
RENAME = {
    "common_name": "common_name", "scientific_name": "scientific_name", "category": "category",
    "min_elevation_masl": "elev_min_m", "max_elevation_masl": "elev_max_m",
    "annual_rainfall_min_mm": "rain_min_mm", "annual_rainfall_max_mm": "rain_max_mm",
    "shade_tolerance": "shade_tol", "max_slope_percent": "max_slope_pct",
    "soil_types_allowed": "soil_raw", "min_soil_ph": "ph_min", "max_soil_ph": "ph_max",
    "drought_tolerance": "drought_tol", "waterlogging_tolerance": "waterlog_tol",
    "timber_density": "timber_density_raw", "mature_height_m": "mature_height_m",
    "canopy_spread_m": "canopy_spread_m", "root_system_type": "root_type",
    "urban_suitability": "urban_raw", "mean_annual_temp_min_c": "temp_min_c",
    "mean_annual_temp_max_c": "temp_max_c", "preferred_corona_climate": "corona_raw",
    "optimal_planting_months": "months_raw", "deployment_stage": "deployment_stage",
    "climate_risk_notes": "climate_risk_notes", "typhoon_resistance": "typhoon_res",
    "growth_rate": "growth_rate_raw", "reference_authority": "reference_authority",
    "Specialized Care / Special Notes": "special_care_notes",
    "Preferred Climate / Seasons": "preferred_climate_seasons",
    "Endangered Status": "endangered_raw", "Population / Survival": "population_survival",
    "Planting Difficulty / Site Limitation": "planting_difficulty",
    "Drought Tolerance (2nd column)": "drought_tolerance_notes",
    "Mode of Nutrition": "mode_of_nutrition", "Native Habitat / Distribution": "native_habitat",
    "Growth Form / Trunk / Foliage": "growth_form", "Sexuality": "sexuality_raw",
    "Water Preference": "water_preference", "Light Preference": "light_preference",
    "Propagation Method": "propagation_method", "Suggested Plant Partners": "plant_partners",
    "Common Problems": "common_problems", "Humidity": "humidity",
    "Spacing (min, m)": "spacing_min_m", "Spacing (max, m)": "spacing_max_m",
    "Planting Depth": "planting_depth", "Germination Days": "germination_raw",
    "Planting Method": "planting_method", "Specific Variant / Varieties": "variants",
    "Drainaige": "drainage", "Drainage": "drainage", "Nutritional Requirements": "nutritional_requirements",
    "Dry Season Threshold": "dry_season_raw", "Common Uses": "common_uses",
    "reference_url": "reference_url", "is_high_value_crop": "is_high_value_raw",
}

# ----------------------------------------------------------------------------------------------
# Cell parsing:  value [Source: url]   (+ the malformed variants found in the Batikuling row)
# ----------------------------------------------------------------------------------------------
URL_RE = re.compile(r'https?://[^\s\]\[;,<>"]+')
STD_RE = re.compile(r'^(?P<v>.*?)\s*\[\s*source\s*:\s*(?P<s>.*?)\]\s*$', re.I | re.S)
OPEN_RE = re.compile(r'^(?P<v>.*?)\s*\[\s*source\s*:\s*(?P<s>.*)$', re.I | re.S)     # closing bracket missing
ALT_RE = re.compile(r'^(?P<v>.*?)\s+Source\s*\[\s*(?P<s>https?://.*?)\]?\s*$', re.I | re.S)  # "2000 Source [url]"
MISSING_MARKERS = {"n/a", "n.a", "n.a.", "na", "none", "-"}

def clean_url(u):
    u = u.strip().rstrip(".,;")
    while u.endswith(")") and u.count(")") > u.count("("):     # keep balanced parentheses
        u = u[:-1]
    return u

def parse_cell(raw):
    """-> dict(value, urls, source_text, flags)"""
    raw = "" if raw is None else str(raw).strip()
    out = dict(value=None, urls=[], source_text="", flags=[])
    if raw == "":
        out["flags"].append("empty"); return out
    if raw.lower() == "data unavailable":
        out["flags"].append("data_unavailable"); return out
    m = STD_RE.match(raw)
    if m:
        v, s = m["v"].strip(), m["s"].strip()
        if "[Source:" not in raw: out["flags"].append("nonstandard_citation")
    else:
        m = OPEN_RE.match(raw)
        if m:
            v, s = m["v"].strip(), m["s"].strip(); out["flags"].append("nonstandard_citation")
        else:
            m = ALT_RE.match(raw)
            if m:
                v, s = m["v"].strip(), m["s"].strip(); out["flags"].append("nonstandard_citation")
            else:
                idx = raw.find("http")
                if idx > 0:
                    v, s = raw[:idx].strip(), raw[idx:].strip(); out["flags"].append("nonstandard_citation")
                else:
                    v, s = raw, ""; out["flags"].append("no_citation")
    # fused / truncated url at the end of the value  ("Dioecioushttps")
    if re.search(r'https?$', v) and not v.lower().startswith("http"):
        v = re.sub(r'https?$', '', v).strip(); out["flags"].append("truncated_url")
    # missing markers
    if v.strip().lower() in MISSING_MARKERS:
        out["flags"] = [f for f in out["flags"] if f != "no_citation"] + ["missing_marker"]; v = None
    out["value"] = v if v else None
    out["source_text"] = s
    if s.startswith("//"): s = "https:" + s; out["flags"].append("url_missing_scheme")
    urls = [clean_url(u) for u in URL_RE.findall(s)]
    if not urls and s:
        urls = [s]; out["flags"].append("file_source_not_provided")
    out["urls"] = urls
    return out

# ----------------------------------------------------------------------------------------------
# Normalizers
# ----------------------------------------------------------------------------------------------
def to_float(v):
    if v is None: return None
    try: return float(str(v).replace(",", "").strip())
    except ValueError: return None

def parse_range(v):
    if v is None: return (None, None)
    nums = re.findall(r'\d+(?:\.\d+)?', str(v))
    if not nums: return (None, None)
    a = float(nums[0]); b = float(nums[1]) if len(nums) > 1 else a
    return (min(a, b), max(a, b))

LEVELS = {"low": "Low", "medium": "Medium", "high": "High", "hgh": "High", "moderate": "Medium"}
def norm_level(v):
    return LEVELS.get(str(v).strip().lower()) if v is not None else None

GROWTH = {"very slow": "Slow", "slow": "Slow", "medium": "Medium", "medium to fast": "Medium",
          "fast": "Fast", "very fast": "Fast"}
def norm_growth(v):
    return GROWTH.get(str(v).strip().lower()) if v is not None else None

def parse_corona(v):
    if v is None: return []
    t = re.sub(r'[Tt]ype', ' ', v)
    order = {"I": 1, "II": 2, "III": 3, "IV": 4}
    found = {x for x in re.findall(r'\b(IV|III|II|I)\b', t)}
    return sorted(found, key=order.get)

def parse_months(v):
    if v is None: return []
    return sorted({int(x) for x in re.findall(r'\d+', v) if 1 <= int(x) <= 12})

def soil_classes(text):
    """Map free text to a texture vocabulary. Provisional - the agriculturist reviews soil_map_review.csv."""
    if text is None: return [], [], False
    t = " " + text.lower().replace("-", " ") + " "
    found, tags = [], []
    for key, cls in (("sandy loam", "Sandy Loam"), ("clay loam", "Clay Loam"), ("sandy clay", "Sandy Clay"), ("silty clay", "Silty Clay"), ("silt loam", "Silt Loam")):   # Silt Loam added in round 11 (no species text uses it today: nothing changes)
        if key in t: found.append(cls); t = t.replace(key, " ")
    if "loam" in t: found.append("Loam")
    if re.search(r'\bclay\b', t): found.append("Clay")
    if re.search(r'\bsand(y)?\b', t): found.append("Sandy")
    if "limestone" in t: found.append("Limestone-derived")
    for tag in ("alluvial", "volcanic", "lateritic", "rocky", "coastal", "deep", "friable", "organic", "well drained"):
        if tag in t: tags.append(tag)
    any_texture = bool(re.search(r'adaptable|tolerant of poor|poor soils|wide range', t)) and not found
    return found, tags, any_texture

URBAN_ALIAS = {"parks": "Parks", "park": "Parks", "streetscape": "Streetscape", "roadside": "Roadside",
               "roadsides": "Roadside", "household gardens": "Household Gardens", "household garden": "Household Gardens",
               "agroforestry": "Agroforestry", "orchards": "Orchards", "orchard": "Orchards",
               "forest restoration": "Forest Restoration", "biodiversity": "Biodiversity",
               "watershed": "Watershed", "riverbanks": "Riverbanks", "coastal": "Coastal",
               "riparian": "Riparian", "windbreak": "Windbreak", "understory": "Understory", "property lines": "Property Lines",
               "open spaces": "Open Spaces", "urban gardens": "Urban Gardens", "marginal lands": "Marginal Lands",
               "upland": "Upland", "slopes": "Slopes", "medians": "Medians", "understory orchards": "Understory Orchards",
               "food security": "Food Security"}
# PROVISIONAL tag -> purpose map. None = a role/placement tag with no purpose. Reviewed in tag_maps_urban.csv.
PURPOSE_OF_TAG = {"Parks": "urban", "Streetscape": "urban", "Roadside": "urban", "Household Gardens": "urban",
                  "Open Spaces": "urban", "Urban Gardens": "urban", "Medians": "urban",
                  "Agroforestry": "planting", "Orchards": "planting", "Forest Restoration": "planting", "Biodiversity": "planting",
                  "Food Security": "planting", "Marginal Lands": "planting", "Understory Orchards": "planting",
                  "Watershed": "watershed", "Riverbanks": "watershed", "Coastal": "watershed", "Riparian": "watershed",
                  "Windbreak": "watershed", "Upland": "watershed", "Slopes": "watershed",
                  "Understory": None, "Property Lines": None}

# PROVISIONAL proposals from Suitability_Framework.xlsx (tag_maps). 0-1, higher = better.
ROOT_MAP = {
    "taproot": (0.8, 0.7), "deep taproot": (0.9, 0.9), "extensive taproot": (0.7, 0.9),
    "taproot with lateral surface roots": (0.6, 0.8), "fibrous / taproot": (0.6, 0.8), "tuberous taproot": (0.7, 0.6),
    "shallow taproot / fibrous": (0.4, 0.7), "shallow corm / fibrous": (0.5, 0.6), "fibrous rhizome": (0.5, 0.8),
    "buttress": (0.3, 0.7), "small buttresses": (0.5, 0.7), "massive buttress": (0.1, 0.8),
    "shallow spreading": (0.2, 0.6), "extensive spreading": (0.2, 0.7),
    # PROVISIONAL, added by the team for the 7 root types that had no score (pending agriculturist sign-off)
    "shallow root system, highly susceptible to phytophthora": (0.4, 0.4), "taproot / fibrous": (0.7, 0.8),
    "extensive fibrous": (0.4, 0.8), "extensive shallow and aggressive surface roots": (0.1, 0.6),
    "shallow taproot, fibrous": (0.4, 0.7), "fibrous": (0.5, 0.8),
    "extensive aggressive surface roots, aerial roots": (0.1, 0.6),
}

PROBLEM_KEYWORDS = {
    "pest": ["pest", "borer", "weevil", "aphid", "mite", "scale", "caterpillar", "miner", "mealybug", "fruit fly", "thrips", "termite"],
    "disease": ["rot", "blight", "rust", "wilt", "fungal", "fungus", "anthracnose", "canker", "mildew", "virus", "dieback", "gummosis"],
    "seed_issue": ["seed recalcitrance", "recalcitrant", "low seed", "germination rate", "seed viability", "dormancy"],
    "brittle_wood": ["brittle", "branch breakage", "weak branches", "breaks", "branch drop"],
    "litter": ["litter", "messy", "fruit drop", "leaf drop"],
    "invasive": ["invasive", "weedy", "aggressive"],
    "infrastructure_risk": ["buttress", "invasive roots", "root damage", "uplift", "pavement"],
}
CARE_KEYWORDS = {"pruning": ["prun"], "staking": ["stak"], "irrigation": ["irrigat", "watering"], "mulch": ["mulch"],
                 "mycorrhiza": ["mycorrhiz"], "shade_nursery": ["shad"], "fertilizer": ["fertiliz", "npk", "manure"]}

def keyword_tags(text, table):
    if not text: return []
    t = text.lower()
    return [tag for tag, kws in table.items() if any(k in t for k in kws)]

def parse_endangered(v):
    """Returns (denr, iucn, unspecified). Scheme is rarely named in the data - that is itself a finding."""
    if v is None: return (None, None, None)
    codes = {"LC": "Least Concern", "NT": "Near Threatened", "VU": "Vulnerable", "EN": "Endangered", "CR": "Critically Endangered"}
    denr = iucn = unspec = None
    parts = [p.strip() for p in re.split(r',(?![^()]*\))', v) if p.strip()]
    for p in parts:
        base = re.sub(r'\((DENR|IUCN)\)', '', p, flags=re.I).strip()
        base = codes.get(base.upper(), base)
        if re.search(r'\(DENR\)', p, re.I): denr = base
        elif re.search(r'\(IUCN\)', p, re.I): iucn = base
        else: unspec = base
    return (denr, iucn, unspec)

# ----------------------------------------------------------------------------------------------
def norm_url_key(u):
    u = u.strip().rstrip("/?& ").replace("http://", "https://")
    u = re.sub(r';jsessionid=[^?&]*', '', u); u = re.sub(r'[?&](srsltid|utm_[a-z]+)=[^&]*', '', u)
    u = re.sub(r'https?://(www\.)?', '', u).lower().replace("stuartxchange.com", "stuartxchange.org")
    u = u.replace("apps.worldagroforestry.org/treedb2/", "apps.worldagroforestry.org/treedb/")
    u = unquote(u).replace(" ", "+"); u = re.sub(r'&ref=[^&]*', '', u)
    return u

def load_sources_list(path):
    """SOURCES.csv: header row 'common_name,LOCAL,INTL,EXTRAS' then one species per row, URLs in cells."""
    rows = list(csv.reader(open(path, encoding="utf-8-sig")))
    start = next(i for i, r in enumerate(rows) if r and r[0].strip() == "common_name")
    out = defaultdict(set)
    for r in rows[start + 1:]:
        if not r or not r[0].strip(): continue
        for cell in r[1:4]:
            for u in URL_RE.findall(cell.replace("\n", " ")):
                out[r[0].strip()].add(norm_url_key(clean_url(u)))
    return out

# ----------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="DirectSource CSV")
    ap.add_argument("--sources", help="SOURCES CSV (your list of links per species) to detect off-list citations")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--tag", default="v0.1-draft")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(a.input, dtype=str, keep_default_na=False)
    raw = raw.rename(columns=lambda c: c.strip())
    unknown = [c for c in raw.columns if c not in RENAME]
    if unknown: print("WARNING unknown columns (kept as text, not scored):", unknown, file=sys.stderr)
    file_hash = hashlib.sha256(Path(a.input).read_bytes()).hexdigest()
    listed = load_sources_list(a.sources) if a.sources else None

    issues, src_rows, ref_rows, species_rows = [], [], [], []
    urban_seen = Counter(); root_seen = Counter()
    ORIG = {}
    for k_, v_ in RENAME.items(): ORIG.setdefault(v_, k_)
    def issue(sp, field, sev, kind, detail=""):
        issues.append(dict(species=sp, field=field, severity=sev, issue=kind, detail=str(detail)[:200]))

    for idx, rr in raw.iterrows():
        cells = {}
        for col in raw.columns:
            cells[RENAME.get(col, col)] = parse_cell(rr[col])
        name_cell = cells["common_name"]
        sp = (name_cell["value"] or "").strip()
        if not sp: issue(f"row {idx+2}", "common_name", "high", "empty_species_name"); continue
        if "[" in raw.loc[idx, "common_name"]:
            issue(sp, "common_name", "info", "species_key_had_source_tag", "removed from the key; kept as a source row")
        V = {k: c["value"] for k, c in cells.items()}

        # ---- provenance rows
        n_cited = n_r12 = 0
        for field, c in cells.items():
            if field in ("reference_url",): continue
            for fl in c["flags"]:
                if fl in ("empty", "data_unavailable"): continue
                if field == "is_high_value_raw" and fl == "no_citation": continue      # team decision, not a sourced fact
                sev = "high" if fl in ("no_citation", "file_source_not_provided") else "medium"
                if fl == "missing_marker": sev = "low"
                issue(sp, field, sev, fl, rr.get(ORIG.get(field, field), ""))
            if c["value"] is None and not c["urls"]: continue
            if field == "is_high_value_raw": continue          # team decision: kept in species, not in the sources table
            url = c["urls"][0] if c["urls"] else None
            extra = "; ".join(c["urls"][1:]) if len(c["urls"]) > 1 else None
            rank, basis = rank_of(url)
            off = False
            if listed is not None and url and url.lower().startswith("http"):
                if norm_url_key(url) not in listed.get(sp, set()):
                    off = True; issue(sp, field, "medium", "off_list_source", url)
            src_rows.append(dict(species=sp, field_name=field, value_text=c["value"], source_url=url, source_extra=extra,
                                 source_rank=rank, rank_basis=basis, off_list=off, flags=";".join(c["flags"]) or None))
            if c["value"] is not None and url:
                n_cited += 1; n_r12 += 1 if rank in (1, 2) else 0
        for u in URL_RE.findall(rr.get("reference_url", "") or ""):
            ref_rows.append(dict(species=sp, reference_url=clean_url(u)))

        # ---- numeric fields
        def num(field):
            v = V.get(field); f = to_float(v)
            if v is not None and f is None: issue(sp, field, "medium", "value_not_numeric", v)
            return f
        r = dict(common_name=sp, scientific_name=V.get("scientific_name"))
        r["genus"] = (r["scientific_name"] or "").split(" ")[0] or None
        for f in ("elev_min_m", "elev_max_m", "rain_min_mm", "rain_max_mm", "temp_min_c", "temp_max_c", "ph_min", "ph_max",
                  "max_slope_pct", "mature_height_m", "canopy_spread_m", "spacing_min_m", "spacing_max_m"):
            r[f] = num(f)
        for lo, hi in (("elev_min_m", "elev_max_m"), ("rain_min_mm", "rain_max_mm"), ("temp_min_c", "temp_max_c"),
                       ("ph_min", "ph_max"), ("spacing_min_m", "spacing_max_m")):
            if r[lo] is not None and r[hi] is not None and r[lo] > r[hi]:
                issue(sp, lo, "high", "min_greater_than_max", f"{r[lo]} > {r[hi]}")
        r["timber_density_min"], r["timber_density_max"] = parse_range(V.get("timber_density_raw"))
        if V.get("timber_density_raw") and r["timber_density_min"] is None: issue(sp, "timber_density", "medium", "value_not_numeric", V["timber_density_raw"])
        r["germination_days_min"], r["germination_days_max"] = parse_range(V.get("germination_raw"))
        ds_min, ds_max = parse_range(V.get("dry_season_raw"))
        r["dry_season_months_min"], r["dry_season_months_max"] = ds_min, ds_max   # unit read as months; confirm with the team

        # ---- categories and tags
        cat = V.get("category") or ""
        r["category_raw"] = cat or None
        r["origin"] = "native" if "native" in cat.lower() else ("crop" if "crop" in cat.lower() else ("other" if cat else None))
        r["use_tags"] = ";".join(t for t in re.split(r'[\/,()]+', re.sub(r'(?i)native|high-value crop|endemic', '', cat)) if t.strip()
                                 for t in [t.strip().lower()]) or None
        r["is_high_value_crop"] = {"true": True, "false": False}.get((V.get("is_high_value_raw") or "").lower())
        for f, key in (("shade_tol", "shade_tol"), ("drought_tol", "drought_tol"), ("waterlog_tol", "waterlog_tol"), ("typhoon_res", "typhoon_res")):
            v = V.get(key); n = norm_level(v); r[f] = n
            if v is not None and n is None: issue(sp, key, "medium", "level_not_in_vocabulary", v)
            if v is not None and v.strip() == "HIgh": issue(sp, key, "low", "typo_fixed", "HIgh -> High")
        gr = V.get("growth_rate_raw"); r["growth_rate"] = norm_growth(gr); r["growth_rate_raw"] = gr
        if gr and r["growth_rate"] is None: issue(sp, "growth_rate", "medium", "growth_not_in_vocabulary", gr)
        rt = V.get("root_type"); r["root_type"] = rt
        m_ = ROOT_MAP.get((rt or "").strip().lower())
        r["root_urban_safety_prov"], r["root_soil_binding_prov"] = (m_ if m_ else (None, None))
        if rt: root_seen[rt] += 1
        if rt and not m_: issue(sp, "root_system_type", "low", "root_type_not_mapped", rt)
        # soil
        sc, stags, anyt = soil_classes(V.get("soil_raw"))
        r["soil_raw"] = V.get("soil_raw"); r["soil_textures"] = ";".join(dict.fromkeys(sc)) or None
        r["soil_tags"] = ";".join(stags) or None; r["soil_any_texture"] = anyt
        if V.get("soil_raw") and not sc and not anyt: issue(sp, "soil_types_allowed", "medium", "soil_text_unmapped", V["soil_raw"])
        # urban tags -> purposes
        tags = []
        for t in re.split(r'[,;]', V.get("urban_raw") or ""):
            t0 = t.strip()
            if not t0: continue
            t = re.sub(r'\s*\(.*?\)', '', t0).strip()          # "Parks (Philippine Cherry Blossom)" -> "Parks"
            k = URBAN_ALIAS.get(t.lower())
            if k is None: issue(sp, "urban_suitability", "low", "urban_tag_unknown", t0); k = t
            if t0 != t: issue(sp, "urban_suitability", "info", "urban_tag_qualifier_dropped", t0)
            urban_seen[(t0, k)] += 1
            if k not in tags: tags.append(k)
        r["urban_tags"] = ";".join(tags) or None
        for p in ("urban", "planting", "watershed"):
            r[f"purpose_{p}"] = any(PURPOSE_OF_TAG.get(t) == p for t in tags)
        # climate
        cor = parse_corona(V.get("corona_raw")); r["corona_raw"] = V.get("corona_raw")
        r["corona_types"] = ";".join(cor) or None; r["corona_has_type_I"] = ("I" in cor) if cor else None
        if V.get("corona_raw") and not cor: issue(sp, "preferred_corona_climate", "medium", "corona_unparsed", V["corona_raw"])
        if cor and "I" not in cor: issue(sp, "preferred_corona_climate", "info", "no_type_I_preference", V["corona_raw"])
        mo = parse_months(V.get("months_raw")); r["planting_months"] = ";".join(map(str, mo)) or None
        if V.get("months_raw") and not mo: issue(sp, "optimal_planting_months", "medium", "months_unparsed", V["months_raw"])
        # endangered
        r["endangered_raw"] = V.get("endangered_raw")
        r["endangered_denr"], r["endangered_iucn"], r["endangered_unspecified"] = parse_endangered(V.get("endangered_raw"))
        if r["endangered_unspecified"]: issue(sp, "endangered_status", "info", "scheme_not_named", V.get("endangered_raw"))
        # sexuality, nutrition, foliage, problems, care
        sx = (V.get("sexuality_raw") or "").lower(); r["sexuality_raw"] = V.get("sexuality_raw")
        r["is_dioecious"] = ("dioecious" in sx and "monoecious" not in sx) if sx else None
        r["n_fixing"] = ("n-fix" in (V.get("mode_of_nutrition") or "").lower()) if V.get("mode_of_nutrition") else None
        gf = (V.get("growth_form") or "").lower()
        r["foliage"] = "semi-deciduous" if "semi-deciduous" in gf or "semi deciduous" in gf else ("deciduous" if "deciduous" in gf else ("evergreen" if "evergreen" in gf else None))
        r["problem_tags"] = ";".join(keyword_tags(V.get("common_problems"), PROBLEM_KEYWORDS)) or None
        r["care_tags"] = ";".join(keyword_tags(V.get("special_care_notes"), CARE_KEYWORDS)) or None
        # pass-through text columns
        for f in ("deployment_stage", "climate_risk_notes", "special_care_notes", "preferred_climate_seasons", "population_survival",
                  "planting_difficulty", "drought_tolerance_notes", "mode_of_nutrition", "native_habitat", "growth_form",
                  "water_preference", "light_preference", "propagation_method", "plant_partners", "common_problems", "humidity",
                  "planting_depth", "planting_method", "variants", "drainage", "nutritional_requirements", "common_uses"):
            r[f] = V.get(f)
        r["n_cells_cited"] = n_cited; r["n_cells_rank12"] = n_r12
        r["confidence_r12"] = round(n_r12 / n_cited, 3) if n_cited else None
        species_rows.append(r)

    sp_df = pd.DataFrame(species_rows)
    sp_df.insert(0, "species_id", range(1, len(sp_df) + 1))
    sid = dict(zip(sp_df.common_name, sp_df.species_id))
    src_df = pd.DataFrame(src_rows); src_df.insert(0, "species_id", src_df.species.map(sid))
    src_df.insert(0, "source_id", range(1, len(src_df) + 1))
    ref_df = pd.DataFrame(ref_rows); ref_df["species_id"] = ref_df.species.map(sid)
    rep = pd.DataFrame(issues)
    sev = {"high": 0, "medium": 1, "low": 2, "info": 3}
    if len(rep): rep = rep.sort_values(["severity", "issue", "species"], key=lambda s: s.map(sev) if s.name == "severity" else s)

    soil_rev = sp_df[["common_name", "soil_raw", "soil_textures", "soil_tags", "soil_any_texture"]].copy()
    soil_rev["review_status"] = "unverified - agriculturist to confirm"
    soil_rev = soil_rev.merge(src_df[src_df.field_name == "soil_raw"][["species", "source_url"]], left_on="common_name", right_on="species", how="left").drop(columns="species")
    rows_ = []
    for rt_, n_ in sorted(root_seen.items(), key=lambda kv: -kv[1]):
        m__ = ROOT_MAP.get(rt_.strip().lower())
        rows_.append((rt_, n_, m__[0] if m__ else None, m__[1] if m__ else None, "proposal - validate" if m__ else "needs score from agriculturist"))
    root_map = pd.DataFrame(rows_, columns=["root_type", "species_count", "urban_infrastructure_safety", "watershed_soil_binding", "status"])
    urban_map = pd.DataFrame([(raw_, canon_, PURPOSE_OF_TAG.get(canon_), n_, "provisional" if canon_ in PURPOSE_OF_TAG else "unmapped")
                              for (raw_, canon_), n_ in sorted(urban_seen.items(), key=lambda kv: (-kv[1], kv[0][0]))],
                             columns=["tag_as_written", "canonical_tag", "purpose", "species_count", "status"])

    sp_df.to_csv(out / "species_clean.csv", index=False)
    src_df.to_csv(out / "species_sources.csv", index=False)
    ref_df.to_csv(out / "species_references.csv", index=False)
    rep.to_csv(out / "ingest_report.csv", index=False)
    soil_rev.to_csv(out / "soil_map_review.csv", index=False)
    root_map.to_csv(out / "tag_maps_root.csv", index=False)
    urban_map.to_csv(out / "tag_maps_urban.csv", index=False)

    db = out / "optimizing_survival.db"
    con = sqlite3.connect(db)
    con.executescript("DROP TABLE IF EXISTS species_sources; DROP TABLE IF EXISTS species_references; DROP TABLE IF EXISTS species; DROP TABLE IF EXISTS dataset_versions;")
    con.execute("CREATE TABLE dataset_versions (dataset_version_id INTEGER PRIMARY KEY, tag TEXT, file_hash TEXT, source_file TEXT, ingested_at TEXT, note TEXT)")
    con.execute("INSERT INTO dataset_versions VALUES (1,?,?,?,?,?)", (a.tag, file_hash, Path(a.input).name, dt.datetime.now().isoformat(timespec="seconds"), "draft - not signed by the agriculturist"))
    sp_df.assign(dataset_version_id=1).to_sql("species", con, index=False)
    src_df.assign(dataset_version_id=1).to_sql("species_sources", con, index=False)
    ref_df.to_sql("species_references", con, index=False)
    con.execute("CREATE UNIQUE INDEX ux_species_name ON species(common_name)")
    con.execute("CREATE INDEX ix_sources_species ON species_sources(species_id, field_name)")
    con.commit(); con.close()

    # ---- console summary
    print(f"species: {len(sp_df)} | cited cells: {len(src_df)} | file hash: {file_hash[:12]}")
    print("source ranks:", dict(Counter(src_df.source_rank.fillna(-1).astype(int))))
    if len(rep):
        print("issues by severity:", dict(Counter(rep.severity)))
        print(rep.groupby(["severity", "issue"]).size().to_string())
    print("written to", out)

if __name__ == "__main__":
    main()
