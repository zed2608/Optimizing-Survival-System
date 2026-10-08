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


def run(a=A, b=B, both=900, na=1000, nb=1000, far=None):
    return P.pair_rules(a, b, both, na, nb, None, far)


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
    assert run(a=sp(waterlog_tol="High"), b=mk(waterlog_tol="Low"))["rules"]["water"]                  # round 15a: a waterlogging mismatch is no longer a rejection ...
    assert run(a=sp(drought_tol="High"), b=mk(drought_tol="Medium"))["rules"]["water"]
    assert run(a=sp(drought_tol="Low"), b=mk(drought_tol="Low"))["rules"]["water"]
    assert not run(a=sp(drought_tol="High"), b=mk(drought_tol="Low"))["listed"]


def test_waterlogging_mismatch_is_a_caution_unless_the_shared_land_is_near_water():
    mk = lambda **k: sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="High", **k)
    a, b = sp(waterlog_tol="High"), mk(waterlog_tol="Low")
    far_ok = run(a=a, b=b, far=(900, 1000, 1000))                                                      # 90% of the smaller set lies at least 50 m from water
    assert far_ok["status"] == "fits" and far_ok["cautions"] == ["check drainage"] and any("check drainage" in r for r in far_ok["reasons"])
    near = run(a=a, b=b, far=(100, 1000, 1000))                                                        # most shared land is within 50 m of water: not a partner
    assert near["status"] is None and not near["listed"]
    unknown = run(a=a, b=b, far=None)                                                                  # distance to water unknown: nothing is guessed
    assert unknown["status"] is None
    same = run(a=sp(waterlog_tol="Low"), b=mk(waterlog_tol="Low"))
    assert same["cautions"] == [] and same["status"] == "fits"
    assert P.PARTNER_CFG["near_water_m"] == 50.0


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


def test_named_but_rejected_is_shown_with_the_label_and_the_reason():
    mk = lambda **k: sp(plant_partners="Makaasim, Narra, Phoebe", **k)
    nar = lambda **k: sp(species_id=2, common_name="Narra", mature_height_m=10.0, shade_tol="High", **k)
    x = run(a=mk(drought_tol="High"), b=nar(drought_tol="Low"))
    assert x["status"] == "named_conditions_differ" and not x["listed"] and x["source_named"]
    assert x["reasons"][0].startswith("Named in the sources, conditions differ") and any("Drought tolerance differs" in r for r in x["reasons"])
    y = run(a=mk(), b=nar(), both=100)                                                                  # too little shared land
    assert y["status"] == "named_conditions_differ" and any("suit the same land" in r for r in y["reasons"])
    z = run(a=sp(drought_tol="High"), b=sp(species_id=2, common_name="Under", mature_height_m=10.0, shade_tol="High", drought_tol="Low"))
    assert z["status"] is None                                                                          # not named: dropped as before
    w = run(a=mk(waterlog_tol="High"), b=nar(waterlog_tol="Low"), far=(100, 1000, 1000))
    assert w["status"] == "named_conditions_differ" and any("check drainage" in r for r in w["reasons"])


def test_batikuling_names_narra_but_the_water_rule_still_applies():
    s = pd.read_csv(PROCESSED / "species_clean.csv")
    bat, narra = s[s.common_name == "Batikuling"].iloc[0], s[s.common_name == "Narra"].iloc[0]
    assert "Narra" in bat.plant_partners and P.named_in_text("Narra", bat.plant_partners)
    x = P.pair_rules(bat, narra, 5000, 6793, 5174)
    assert x["rules"]["named"] and not x["rules"]["water"] and not x["listed"]               # Low against High drought tolerance: not a fit ...
    assert x["status"] == "named_conditions_differ" and "Drought tolerance differs (Batikuling Low, Narra High)." in x["reasons"]        # ... but shown, with the reason


# ---- the table and the API ----------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def table():
    f = PROCESSED / "species_partners.csv"
    if not f.exists():
        pytest.skip("run python pipeline/partners.py first")
    return pd.read_csv(f)


def test_table_shape_and_no_unlisted_pairs(table):
    assert list(table.columns) == P.OUT_COLUMNS
    assert set(table.status) <= {"fits", "named_conditions_differ"}
    assert (table.species_id != table.partner_id).all() and table.score.between(0, 1).all()
    assert table[table.status == "fits"].overlap_share.between(0.5, 1).all()
    assert not table.duplicated(["species_id", "partner_id"]).any()
    s = pd.read_csv(PROCESSED / "species_clean.csv").set_index("species_id")
    clash = (("High", "Low"), ("Low", "High"))
    for r in table.itertuples(index=False):
        a, b = s.loc[r.species_id], s.loc[r.partner_id]
        assert bool(r.source_named) == P.named_in_text(b.common_name, a.plant_partners)
        cautions = str(r.cautions) if isinstance(r.cautions, str) else ""
        assert (cautions == "check drainage") == ((a.waterlog_tol, b.waterlog_tol) in clash)       # a waterlogging mismatch is a caution, never silent
        if r.status == "fits":
            assert (a.drought_tol, b.drought_tol) not in clash
            assert not (a.root_urban_safety_prov < 0.4 and b.root_urban_safety_prov < 0.4)
            assert len(P.pal.parse_months(a.planting_months) & P.pal.parse_months(b.planting_months)) >= 2
        else:
            assert r.source_named and r.reasons.startswith("Named in the sources, conditions differ")
    assert table.source_named.any()
    named = {(s.common_name[r.species_id], s.common_name[r.partner_id]) for r in table[table.status != "fits"].itertuples()}
    assert ("Batikuling", "Narra") in named and ("Cacao", "Coconut") in named


def test_the_old_results_are_kept_and_nothing_old_was_lost(table):
    f = PROCESSED / "species_partners_before_round15a.csv"
    if not f.exists():
        pytest.skip("the comparison copy is not here")
    old = pd.read_csv(f)
    fits = table[table.status == "fits"]
    assert set(zip(old.species_id, old.partner_id)) <= set(zip(fits.species_id, fits.partner_id))
    assert fits.species_id.nunique() > old.species_id.nunique()                                       # species gain a partner (the waterlogging rule is a caution now)


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
    assert j["provisional"] is True and j["message"] == "" and 1 <= len(j["partners"]) <= 8 and sum(p["status"] == "fits" for p in j["partners"]) <= 5 and "agriculturist will check" in j["note"]
    assert j["sources_say"] and j["area"]["display_name"] == "Santa Ana"
    for p in j["partners"]:
        assert set(p) >= {"species_id", "common_name", "score", "reasons", "source_named", "overlap_share", "overlap_in_area", "season", "purpose_fit"}
        assert p["reasons"] and all("_" not in x and "=" not in x for x in p["reasons"])
        oa = p["overlap_in_area"]
        assert 0 <= oa["squares_both"] <= min(oa["squares_main"], oa["squares_partner"])
        assert p["season"]["status"] in ("in_season", "partly", "out_of_season", "unknown")
    fits = [p["score"] for p in j["partners"] if p["status"] == "fits"]
    assert fits == sorted(fits, reverse=True) and all(p["status"] == "fits" for p in j["partners"][:len(fits)])        # pairs that fit come first
    assert all(isinstance(p["cautions"], list) for p in j["partners"])


def test_api_shows_named_pairs_whose_conditions_differ(client, table):
    sid = int(pd.read_csv(PROCESSED / "species_clean.csv").set_index("common_name").species_id["Batikuling"])
    j = client.get(f"/species/{sid}/partners").json()
    named = [p for p in j["partners"] if p["status"] != "fits"]
    assert named and named[0]["common_name"] == "Narra" and named[0]["label"] == "named in the sources, conditions differ"
    assert any("Drought tolerance differs" in x for x in named[0]["reasons"])


def test_api_empty_list_and_dataset_text_fallback(client, table):
    s = pd.read_csv(PROCESSED / "species_clean.csv")
    none = [int(i) for i in s.species_id if i not in set(table.species_id)]
    assert none, "the test needs a species without a partner"
    j = client.get(f"/species/{none[0]}/partners").json()
    assert j["partners"] == [] and j["message"] == "No good partner found in our data"
    assert j["sources_say"] == s[s.species_id == none[0]].plant_partners.iloc[0]          # the dataset text, word for word
    assert client.get("/species/999/partners").status_code == 404
    assert client.get("/species/1/partners", params={"barangay": "Nowhere"}).status_code == 400


def test_plan_gets_a_one_line_partner_note(client, table, tmp_path, monkeypatch):
    monkeypatch.setattr(client.app.state.data, "work", tmp_path)                           # plans of this test go to a temporary folder, never to data/processed/plans
    pairs = table[table.species_id.isin([8, 7]) & table.partner_id.isin([8, 7])]
    body = {"purpose": "urban", "seed": 4, "campaign": {"name": "P", "unit": ""}, "barangay": "Santa Ana", "species_counts": {"8": 30, "22": 20}}
    j = client.post("/plan-event", json=body).json()
    assert "partners" in j and j["partners"]["text"] in ("These species suit each other", "Some of these species suit each other", "No partner rule applies")
    assert j["partners"]["provisional"] is True
    one = client.post("/plan-event", json={**body, "species_counts": {"8": 30}}).json()
    assert "partners" not in one                                                           # a single species has no pair
