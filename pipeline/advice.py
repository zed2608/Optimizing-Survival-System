"""Ways to improve survival (round 17): short advice items for a species, a point or a plan.

ADVICE ONLY. Nothing here reads or writes a score: S, P and W are never touched (tests/test_advice.py proves it on a fixed sample of 200 pairs).
The wording and the source of every rule live in data/processed/survival_advice.csv (rule_id, trigger, text, source, provisional); this module only decides WHEN a rule
fires, from fields the system already has. Every item is provisional: advice that the agriculturist still has to confirm. No agronomy is invented: only the rules of that file.
"""
from pathlib import Path

import pandas as pd

RULES_FILE = "survival_advice.csv"
NOTE = "Advice from the agriculturist, not yet confirmed. It does not change the scores."
CACAO_NAME = "cacao"
# Order of the items in a list (plan and point rules first: they are about the place; then the species rules)
ORDER = ["habagat", "rehab_site", "spacing_multi", "low_drought", "low_wind", "shade_partner", "shade_tolerant", "fruit_grafted"]
SHADE_NEEDY = ("cacao", "robusta (coffee)")               # only these two NEED shade; the other shade-tolerant species with a partner get the softer "tolerates shade" wording
LIMIT_SPECIES_SIMPLE = 4
LIMIT_PLAN_SIMPLE = 5


def load_rules(data_dir):
    """{rule_id: row dict} from survival_advice.csv; an empty dict when the file is missing."""
    p = Path(data_dir) / RULES_FILE
    if not p.is_file():
        return {}
    t = pd.read_csv(p, dtype=str).fillna("")
    return {r["rule_id"]: r for r in t.to_dict("records")}


def _item(rules, rule_id, text=None, source=None, **extra):
    r = rules[rule_id]
    return {"rule_id": rule_id, "text": text if text is not None else r["text"], "source": source if source is not None else r["source"], "provisional": True, **extra}


def join_names(names):
    names = [str(n) for n in names]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def is_shade_needy(row):
    """High shade tolerance AND a light preference that asks for partial shade: the fields the partner rules read (shade_tol) plus light_preference."""
    return str(row.get("shade_tol")) == "High" and "partial shade" in str(row.get("light_preference") or "").lower()


def species_rule_ids(row, tags, partner_names):
    """The species-level rules that fire for one species row (a dict of species_clean.csv), its purpose tags and the names of its listed partner species."""
    fire = []
    if str(row.get("drought_tol")) == "Low":
        fire.append("low_drought")
    if str(row.get("typhoon_res")) == "Low":
        fire.append("low_wind")
    if is_shade_needy(row) and partner_names:
        fire.append("shade_partner" if str(row.get("common_name", "")).strip().lower() in SHADE_NEEDY else "shade_tolerant")
    if "fruit-bearing" in set(tags or []):
        fire.append("fruit_grafted")
    return fire


def species_advice(rules, row, tags, partner_names, habagat=False, rehab=False):
    """The advice list of one species (and of a point when habagat / rehab are given): [{rule_id, text, source, provisional}], each rule once, in ORDER."""
    if not rules:
        return []
    fire = set(species_rule_ids(row, tags, partner_names))
    if habagat:
        fire.add("habagat")
    if rehab:
        fire.add("rehab_site")
    out = []
    for rid in ORDER:
        if rid not in fire or rid not in rules:
            continue
        if rid in ("shade_partner", "shade_tolerant"):
            text = rules[rid]["text"].replace("[partner names]", join_names(partner_names))
            src = rules[rid]["source"]
            if str(row.get("common_name", "")).strip().lower() == CACAO_NAME and "shade_cacao" in rules:
                text += " " + rules["shade_cacao"]["text"]
                src += ". The cacao sentence: " + rules["shade_cacao"]["source"]
            out.append(_item(rules, rid, text, src))
        else:
            out.append(_item(rules, rid))
    return out


def plan_advice(rules, species_info, habagat_trees=0, rehab_trees=0):
    """Advice of a plan: every rule once, with the species it applies to.
    species_info: [{row, tags, partners, name}] one per species in the plan (row = species_clean row). habagat_trees / rehab_trees = how many planned trees carry that flag."""
    if not rules:
        return []
    names_by_rule = {}
    texts = {}
    for sp in species_info:
        for it in species_advice(rules, sp["row"], sp["tags"], sp["partners"]):
            names_by_rule.setdefault(it["rule_id"], []).append(sp["name"])
            texts.setdefault(it["rule_id"], []).append(it)
    out = []
    for rid in ORDER:
        if rid == "habagat" and habagat_trees > 0 and rid in rules:
            out.append(_item(rules, rid, scope="plan"))
        elif rid == "rehab_site" and rehab_trees > 0 and rid in rules:
            out.append(_item(rules, rid, scope="plan"))
        elif rid == "spacing_multi" and len(species_info) >= 2 and rid in rules:
            out.append(_item(rules, rid, scope="plan"))
        elif rid in ("shade_partner", "shade_tolerant"):                  # the partner names differ per species: one item for each species
            for it, nm in zip(texts.get(rid, []), names_by_rule.get(rid, [])):
                out.append({**it, "scope": "species", "species": [nm]})
        elif rid in names_by_rule:
            out.append({**texts[rid][0], "scope": "species", "species": names_by_rule[rid]})
    return out


def limit_simple(items, n):
    """The Simple view shows at most n items; the Detailed view shows all."""
    return items[:n]
