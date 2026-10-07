"""Round 14 C: partner species ("Works well with"): every rule on its own, the named-in-sources bonus, the empty result, the API shape and the dataset-text fallback.
Run from the repo root: python -m pytest tests/test_partners.py"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import partners as P  # noqa: E402


def sp(**kw):
    base = {"species_id": 1, "common_name": "Main", "planting_months": "5;6;7", "drought_tol": "Medium", "waterlog_tol": "Medium", "root_urban_safety_prov": 0.7,
            "mature_height_m": 20.0, "shade_tol": "Medium", "plant_partners": "Shade-tolerant understory crops"}
    return pd.Series({**base, **kw})


A = sp()
B = sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="High")


def run(a=A, b=B, both=900, na=1000, nb=1000):
    return P.pair_rules(a, b, both, na, nb)


# ---- every rule on its own ----------------------------------------------------------------------------------------------------------------
def test_a_good_pair_is_listed_with_plain_reasons():
    x = run()
    assert x["listed"] and all(x["rules"][k] for k in ("overlap", "water", "roots", "layering")) and not x["rules"]["named"]
    assert x["score"] > 0.6 and x["overlap_share"] == 0.9 and x["shared_months"] == [5, 6, 7]
    assert any("lower tree" in r for r in x["reasons"]) and any("May, Jun, Jul" in r for r in x["reasons"])


def test_layering_needs_height_and_shade_tolerance():
    assert run(b=sp(species_id=2, common_name="Under", mature_height_m=12.0, shade_tol="Medium"))["rules"]["layering"]          # exactly 60% of 20 m
    assert not run(b=sp(species_id=2, common_name="Under", mature_height_m=12.5, shade_tol="High"))["rules"]["layering"]       # just above 60%
    assert not run(b=sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="Low"))["rules"]["layering"]        # does not tolerate shade
    x = run(b=sp(species_id=2, common_name="Under", mature_height_m=25.0, shade_tol="High"))
    assert not x["rules"]["layering"] and not x["listed"]                                                                       # taller partner, nothing named: not listed
    assert not run(a=sp(mature_height_m=np.nan))["rules"]["layering"]                                                           # a missing value never passes


def test_overlap_share_and_shared_months():
    assert run(both=500)["rules"]["overlap"] and not run(both=499)["rules"]["overlap"]                                          # 50% of the smaller set
    assert run(both=250, na=1000, nb=500)["rules"]["overlap"]                                                                   # the SMALLER set counts
    assert not run(both=0, na=0, nb=0)["rules"]["overlap"]
    assert not run(b=sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="High", planting_months="7;8"))["rules"]["overlap"]     # one shared month
    assert run(b=sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="High", planting_months="6;7;8"))["rules"]["overlap"]
    assert not run(b=sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="High", planting_months=None))["rules"]["overlap"]


def test_water_clash_is_only_high_against_low():
    mk = lambda **k: sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="High", **k)
    assert not run(a=sp(drought_tol="High"), b=mk(drought_tol="Low"))["rules"]["water"]
    assert not run(a=sp(drought_tol="Low"), b=mk(drought_tol="High"))["rules"]["water"]
    assert not run(a=sp(waterlog_tol="High"), b=mk(waterlog_tol="Low"))["rules"]["water"]
    assert run(a=sp(drought_tol="High"), b=mk(drought_tol="Medium"))["rules"]["water"]
    assert run(a=sp(drought_tol="Low"), b=mk(drought_tol="Low"))["rules"]["water"]
    assert not run(a=sp(drought_tol="High"), b=mk(drought_tol="Low"))["listed"]


def test_roots_not_both_low():
    mk = lambda r: sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="High", root_urban_safety_prov=r)
    assert not run(a=sp(root_urban_safety_prov=0.3), b=mk(0.3))["rules"]["roots"]
    assert run(a=sp(root_urban_safety_prov=0.3), b=mk(0.4))["rules"]["roots"]                  # 0.4 is not below 0.4
    assert run(a=sp(root_urban_safety_prov=0.9), b=mk(0.1))["rules"]["roots"]
    assert not run(a=sp(root_urban_safety_prov=np.nan))["rules"]["roots"]


# ---- named in the sources -----------------------------------------------------------------------------------------------------------------
def test_named_in_sources_matches_whole_words_and_parts_of_names():
    assert P.named_in_text("Narra", "Makaasim, Narra, Phoebe")
    assert not P.named_in_text("Narra", "Narrative shrubs")
    assert P.named_in_text("Banana - Saba", "Banana, Gliricidia, Coconut")                     # a part of the name
    assert P.named_in_text("Robusta (Coffee)", "Cacao, Coffee (as shade nurse)")
    assert not P.named_in_text("Duhat", "Shade-tolerant understory crops") and not P.named_in_text("Duhat", None)


def test_named_bonus_adds_to_the_score_and_lets_a_taller_partner_in():
    plain = run(b=sp(species_id=2, common_name="Narra", mature_height_m=10.0, shade_tol="High"))
    named = run(a=sp(plant_partners="Makaasim, Narra, Phoebe"), b=sp(species_id=2, common_name="Narra", mature_height_m=10.0, shade_tol="High"))
    assert named["rules"]["named"] and not plain["rules"]["named"]
    assert named["score"] == pytest.approx(plain["score"] + P.PARTNER_CFG["weights"]["named"]) and named["source_named"]
    assert any("names Narra as a partner" in r for r in named["reasons"])
    tall = run(a=sp(plant_partners="Makaasim, Narra, Phoebe"), b=sp(species_id=2, common_name="Narra", mature_height_m=30.0, shade_tol="Low"))
    assert tall["listed"] and not tall["rules"]["layering"]                                     # named pairs need no layering, only overlap, water and roots


def test_batikuling_names_narra_but_the_water_rule_still_applies():
    s = pd.read_csv(PROCESSED / "species_clean.csv")
    bat, narra = s[s.common_name == "Batikuling"].iloc[0], s[s.common_name == "Narra"].iloc[0]
    assert "Narra" in bat.plant_partners and P.named_in_text("Narra", bat.plant_partners)
    x = P.pair_rules(bat, narra, 5000, 6793, 5174)
    assert x["rules"]["named"] and not x["rules"]["water"] and not x["listed"]               # Low against High drought tolerance: an honest "no"


# ---- the table and the API ----------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def table():
    f = PROCESSED / "species_partners.csv"
    if not f.exists():
        pytest.skip("run python pipeline/partners.py first")
    return pd.read_csv(f)


def test_table_shape_and_no_unlisted_pairs(table):
    assert list(table.columns) == P.OUT_COLUMNS
    assert (table.species_id != table.partner_id).all() and table.score.between(0, 1).all() and table.overlap_share.between(0.5, 1).all()
    assert not table.duplicated(["species_id", "partner_id"]).any()
    s = pd.read_csv(PROCESSED / "species_clean.csv").set_index("species_id")
    for r in table.itertuples(index=False):
        a, b = s.loc[r.species_id], s.loc[r.partner_id]
        assert (a.drought_tol, b.drought_tol) not in (("High", "Low"), ("Low", "High")) and (a.waterlog_tol, b.waterlog_tol) not in (("High", "Low"), ("Low", "High"))
        assert not (a.root_urban_safety_prov < 0.4 and b.root_urban_safety_prov < 0.4)
        assert len(P.pal.parse_months(a.planting_months) & P.pal.parse_months(b.planting_months)) >= 2
        assert bool(r.source_named) == P.named_in_text(b.common_name, a.plant_partners)
    assert table.source_named.any()


@pytest.fixture(scope="module")
def client():
    sys.path.insert(0, str(ROOT))
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield c


def test_api_shape_with_partners(client, table):
    sid = int(table.species_id.value_counts().index[0])
    r = client.get(f"/species/{sid}/partners", params={"purpose": "urban", "barangay": "Santa Ana", "start": "2027-05-01", "end": "2027-06-29"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["provisional"] is True and j["message"] == "" and 1 <= len(j["partners"]) <= 5 and "agriculturist will check" in j["note"]
    assert j["sources_say"] and j["area"]["display_name"] == "Santa Ana"
    for p in j["partners"]:
        assert set(p) >= {"species_id", "common_name", "score", "reasons", "source_named", "overlap_share", "overlap_in_area", "season", "purpose_fit"}
        assert p["reasons"] and all("_" not in x and "=" not in x for x in p["reasons"])
        oa = p["overlap_in_area"]
        assert 0 <= oa["squares_both"] <= min(oa["squares_main"], oa["squares_partner"])
        assert p["season"]["status"] in ("in_season", "partly", "out_of_season", "unknown")
    assert [p["score"] for p in j["partners"]] == sorted((p["score"] for p in j["partners"]), reverse=True)


def test_api_empty_list_and_dataset_text_fallback(client, table):
    s = pd.read_csv(PROCESSED / "species_clean.csv")
    none = [int(i) for i in s.species_id if i not in set(table.species_id)]
    assert none, "the test needs a species without a partner"
    j = client.get(f"/species/{none[0]}/partners").json()
    assert j["partners"] == [] and j["message"] == "No good partner found in our data"
    assert j["sources_say"] == s[s.species_id == none[0]].plant_partners.iloc[0]          # the dataset text, word for word
    assert client.get("/species/999/partners").status_code == 404
    assert client.get("/species/1/partners", params={"barangay": "Nowhere"}).status_code == 400


def test_plan_gets_a_one_line_partner_note(client, table):
    pairs = table[table.species_id.isin([8, 7]) & table.partner_id.isin([8, 7])]
    body = {"purpose": "urban", "seed": 4, "campaign": {"name": "P", "unit": ""}, "barangay": "Santa Ana", "species_counts": {"8": 30, "22": 20}}
    j = client.post("/plan-event", json=body).json()
    assert "partners" in j and j["partners"]["text"] in ("These species suit each other", "Some of these species suit each other", "No partner rule applies")
    assert j["partners"]["provisional"] is True
    one = client.post("/plan-event", json={**body, "species_counts": {"8": 30}}).json()
    assert "partners" not in one                                                           # a single species has no pair
