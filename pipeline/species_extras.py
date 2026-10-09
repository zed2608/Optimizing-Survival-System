#!/usr/bin/env python3
"""
species_extras.py - three small tables that sit BESIDE the species table (round 15a). The species table (species_clean.csv, species_sources.csv) is never edited, so the release hash stays the same.

    python pipeline/species_extras.py --out data/processed

  species_purpose_tags.csv  species_id, name, tag, basis       filters only (the three scored purposes urban / planting / watershed are not changed); PROVISIONAL, to be confirmed by the agriculturist
  nursery_stock.csv         listed_name, matched_species_id, match_note, in_system   the LGU nursery list (handwritten; quantities unknown)
  interview_notes.csv       species_id, note, source, provisional                    facts from the interviews of 7 Oct 2026, shown in the species card
"""
import argparse, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# =====================================================================================================================
# PURPOSE TAGS - rules over the TYPE text (use_tags, category_raw, urban_tags) + a small override table. ALL PROVISIONAL.
# =====================================================================================================================
TAGS = ["fruit-bearing", "timber/industrial", "ornamental", "vegetable", "high-value crop", "food security/livelihood", "urban greening/shade", "biodiversity"]
FRUIT_USE_TAGS = {"fruit", "fruit tree", "fruit shrub", "nut tree"}
TIMBER_USE_TAGS = {"timber", "dye"}
URBAN_PLACE_TAGS = {"parks", "roadside", "streetscape", "medians", "open spaces"}
BIODIVERSITY_URBAN_TAGS = {"biodiversity", "forest restoration"}
LIVELIHOOD_URBAN_TAGS = {"food security", "household gardens"}
PROVISIONAL_NOTE = "provisional, to be confirmed by the agriculturist"
INTERVIEW_DATE = "7 Oct 2026"
OVERRIDES = [   # (common_name, tag, basis): only where the type text cannot say it; the basis names the interview
    ("Clumping Bamboo", "food security/livelihood", f"interview {INTERVIEW_DATE}: bamboo crafts and a landfill bamboo park give a livelihood (speaker not recorded); {PROVISIONAL_NOTE}"),
]


def _tok(text, seps=r"[;,/]"):
    return {t.strip().lower() for t in re.split(seps, str(text)) if t.strip()} if isinstance(text, str) else set()


def derive_tags(row):
    """[(tag, basis)] for one species row, from rules over the type text only."""
    use, cat, urban = _tok(row.get("use_tags")), str(row.get("category_raw") or ""), _tok(row.get("urban_tags"))
    out = []
    hit = use & FRUIT_USE_TAGS
    if hit or "fruit" in cat.lower():
        out.append(("fruit-bearing", f"rule: type text says fruit (use_tags '{row.get('use_tags')}', category '{cat}')"))
    hit = use & TIMBER_USE_TAGS
    if hit or "timber" in cat.lower():
        out.append(("timber/industrial", f"rule: type text says timber or dye (use_tags '{row.get('use_tags')}', category '{cat}')"))
    if "ornamental" in use or "ornamental" in cat.lower():
        out.append(("ornamental", f"rule: type text says ornamental (use_tags '{row.get('use_tags')}', category '{cat}')"))
    if "vegetable" in use or "vegetable" in cat.lower():
        out.append(("vegetable", f"rule: type text says vegetable (use_tags '{row.get('use_tags')}', category '{cat}')"))
    if str(row.get("is_high_value_crop")).lower() == "true":
        out.append(("high-value crop", "rule: is_high_value_crop is true in the species table (a team decision, not a sourced fact)"))
    import site_rules as sr
    if sr.food_bearing(row) and (str(row.get("is_high_value_crop")).lower() == "true" or urban & LIVELIHOOD_URBAN_TAGS):
        out.append(("food security/livelihood", f"rule: a food-bearing species (type text) that is a high-value crop or has urban_tags {sorted(urban & LIVELIHOOD_URBAN_TAGS) or 'high-value'}"))
    if "shade" in use or "shade" in cat.lower() or urban & URBAN_PLACE_TAGS:
        out.append(("urban greening/shade", f"rule: type text says shade or urban_tags lists {sorted(urban & URBAN_PLACE_TAGS) or 'shade'} (not the scored urban purpose)"))
    if urban & BIODIVERSITY_URBAN_TAGS or "endemic" in cat.lower():
        out.append(("biodiversity", f"rule: urban_tags lists {sorted(urban & BIODIVERSITY_URBAN_TAGS) or 'endemic'} or the category says endemic"))
    return out


def build_purpose_tags(species):
    rows = []
    for r in species.to_dict("records"):
        for tag, basis in derive_tags(r):
            rows.append({"species_id": int(r["species_id"]), "name": r["common_name"], "tag": tag, "basis": f"{basis}; {PROVISIONAL_NOTE}"})
    by_name = {r["common_name"]: int(r["species_id"]) for r in species.to_dict("records")}
    for name, tag, basis in OVERRIDES:
        if not any(x["species_id"] == by_name[name] and x["tag"] == tag for x in rows):
            rows.append({"species_id": by_name[name], "name": name, "tag": tag, "basis": basis})
    t = pd.DataFrame(rows, columns=["species_id", "name", "tag", "basis"])
    return t.sort_values(["species_id", "tag"]).reset_index(drop=True)


# =====================================================================================================================
# NURSERY - the LGU nursery list (handwritten). Quantities are unknown.
# =====================================================================================================================
NURSERY_SOURCE = "LGU nursery list (handwritten)"
# listed name -> (species common name or None, match note)
NURSERY_MATCHES = [
    ("Guyabano", "Guyabano", ""), ("Cacao", "Cacao", ""), ("Kasoy (Kassoy)", "Kasoy", "listed as Kassoy"), ("Duhat", "Duhat", ""), ("Narra", "Narra", ""),
    ("Fire Tree", "Fire Tree", ""), ("Rambutan", "Rambutan", ""), ("Sampalok", "Sampalok", ""), ("Avocado", "Avocado", ""), ("Talisay", "Talisay", ""),
    ("Coconut", "Coconut", ""), ("Calamansi", "Calamansi", ""), ("Banaba", "Banaba", ""),
]
NURSERY_NOT_IN_SYSTEM = [
    ("Durian", ""), ("Morong(?)", "name uncertain on the handwritten list"), ("Tui/Tuai (Bischofia javanica)", ""), ("Kamatsile", ""), ("Suha (Citrus maxima)", ""), ("Banyaw", ""),
    ("Luntibani", ""), ("Balitbitan", ""), ("Eugenia", ""), ("Casimjas/Castanas(?)", "name uncertain on the handwritten list"), ("Camansi", ""), ("Atis", ""),
    ("Nymp Tree", "probably Neem; not in the system"), ("Lagundi", ""), ("Alibangbang", ""), ("Caupiyus(?)", "name uncertain on the handwritten list"), ("Dungon", ""),
]


def build_nursery(species):
    by = {r["common_name"]: r for r in species.to_dict("records")}
    rows = []
    for listed, name, note in NURSERY_MATCHES:
        rows.append({"listed_name": listed, "matched_species_id": int(by[name]["species_id"]), "match_note": (note + "; " if note else "") + f"same common name as {name} ({by[name]['scientific_name']})", "in_system": "yes"})
    k = by["Kamagong"]                                                  # Mabolo: matched only because our Kamagong carries the scientific name Diospyros blancoi
    if str(k["scientific_name"]).strip() == "Diospyros blancoi":
        rows.append({"listed_name": "Mabolo", "matched_species_id": int(k["species_id"]), "match_note": "Mabolo is the fruit tree Diospyros blancoi; our Kamagong has that scientific name, so it is matched to Kamagong", "in_system": "yes"})
    else:
        rows.append({"listed_name": "Mabolo", "matched_species_id": "", "match_note": f"not matched: our Kamagong is {k['scientific_name']}, not Diospyros blancoi", "in_system": "no"})
    rows.append({"listed_name": "Kape", "matched_species_id": int(by["Robusta (Coffee)"]["species_id"]),
                 "match_note": "Kape is in the nursery list, variety unknown", "in_system": "partial"})
    rows.append({"listed_name": "Banyan", "matched_species_id": "", "match_note": "possible Weeping Fig, confirm", "in_system": "no"})
    for listed, note in NURSERY_NOT_IN_SYSTEM:
        rows.append({"listed_name": listed, "matched_species_id": "", "match_note": note or "not in the system", "in_system": "no"})
    return pd.DataFrame(rows, columns=["listed_name", "matched_species_id", "match_note", "in_system"])


# =====================================================================================================================
# INTERVIEW NOTES - one fact per row; who said it is written where it was recorded, never guessed
# =====================================================================================================================
NOTE_SOURCE = "MAO interview, transcript, Oct 2026"      # round 15b: the source of every note (all provisional)
MAO = UNNAMED = NOTE_SOURCE
INTERVIEW_NOTES = [
    ("Cacao", "Needs about 60% shade and suits intercropping with banana or coconut.", MAO),
    ("Cacao", "Farmer groups grow cacao in Silangan and Pintong Bukawe.", UNNAMED),
    ("Clumping Bamboo", "First choice for watershed and landfill rehabilitation; it filters heavy metals.", MAO),
    ("Clumping Bamboo", "Adapts widely; a bamboo park is on the landfill; bamboo crafts give a livelihood; it is planted at Pintong Bukawe.", UNNAMED),
    ("Calamansi", "Observation only: an existing calamansi orchard in Gitnang Bayan I (Divine Mercy).", UNNAMED),
]


def build_interview_notes(species):
    by = {r["common_name"]: int(r["species_id"]) for r in species.to_dict("records")}
    return pd.DataFrame([{"species_id": by[n], "note": t, "source": s, "provisional": True} for n, t, s in INTERVIEW_NOTES], columns=["species_id", "note", "source", "provisional"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/processed")
    a = ap.parse_args(argv)
    out = Path(a.out)
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sp = pd.read_csv(out / "species_clean.csv")
    tags, nur, notes = build_purpose_tags(sp), build_nursery(sp), build_interview_notes(sp)
    tags.to_csv(out / "species_purpose_tags.csv", index=False)
    nur.to_csv(out / "nursery_stock.csv", index=False)
    notes.to_csv(out / "interview_notes.csv", index=False)
    print(f"species_purpose_tags.csv: {len(tags)} rows, {tags.species_id.nunique()} species; counts {tags.tag.value_counts().to_dict()}")
    print(f"nursery_stock.csv: {len(nur)} listed names; in_system {nur.in_system.value_counts().to_dict()}; species in the nursery: {nur.matched_species_id.replace('', pd.NA).dropna().nunique()}")
    print(f"interview_notes.csv: {len(notes)} notes")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
