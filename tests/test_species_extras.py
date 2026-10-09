"""Round 15a: purpose tags (filters only), the LGU nursery list, interview notes, the name fix "Pintong Bukawe", the validation record, and the release hash that must not change.
Run from the repo root: python -m pytest tests/test_species_extras.py"""
import hashlib, re, sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import species_extras as ex  # noqa: E402
from names import fix_barangay  # noqa: E402

SP = pd.read_csv(PROCESSED / "species_clean.csv")
NAME = dict(zip(SP.species_id, SP.common_name))
ID = {v: k for k, v in NAME.items()}


# ---- the release hash ---------------------------------------------------------------------------------------------------------------------------
def test_the_release_hash_is_unchanged():
    sha = lambda f: hashlib.sha256((ROOT / "data" / "raw" / f).read_bytes()).hexdigest()
    combined = hashlib.sha256((sha("species_directsource.csv") + "\n" + sha("sources_list.csv")).encode()).hexdigest()[:12]
    assert combined == "34964a09fe44"
    assert "34964a09fe44" in (PROCESSED / "dataset_release.txt").read_text(encoding="utf-8")
    assert len(SP) == 45                                                                            # no species was added


# ---- purpose tags ---------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def tags():
    return pd.read_csv(PROCESSED / "species_purpose_tags.csv")


def test_tags_use_the_eight_names_and_every_row_has_a_basis(tags):
    assert list(tags.columns) == ["species_id", "name", "tag", "basis"]
    assert set(tags.tag) <= set(ex.TAGS) and len(ex.TAGS) == 8
    assert tags.basis.notna().all() and tags.basis.str.len().gt(20).all()
    assert tags.basis.str.contains("provisional").all() and tags.basis.str.contains("rule:|interview").all()
    assert not tags.duplicated(["species_id", "tag"]).any() and set(tags.species_id) == set(SP.species_id)
    assert (tags.name == tags.species_id.map(NAME)).all()


def test_tag_rules_from_the_type_text(tags):
    t = lambda n: set(tags[tags.name == n].tag)
    assert {"fruit-bearing", "high-value crop", "food security/livelihood"} <= t("Cacao")
    assert "vegetable" in t("Malunggay") and "timber/industrial" in t("Narra") and "ornamental" in t("Weeping Fig (Balete)") and "urban greening/shade" in t("Fire Tree")
    assert "biodiversity" in t("Kamagong") and "fruit-bearing" in t("Kamagong") and "fruit-bearing" not in t("Narra")
    assert "timber/industrial" in t("Atsuete")                                                       # dye: industrial
    assert t("Clumping Bamboo") == {"food security/livelihood"}
    row = tags[(tags.name == "Clumping Bamboo")].iloc[0]
    assert "interview 7 Oct 2026" in row.basis and "provisional" in row.basis                        # the only override names its interview
    assert not any(tags.basis.str.contains("interview") & (tags.name != "Clumping Bamboo"))


def test_tags_are_filters_only_the_scored_purposes_are_untouched():
    ps = pd.read_csv(PROCESSED / "purpose_scores.csv")
    assert set(ps.purpose) == {"urban", "planting", "watershed"} and len(ps) == 45 * 3
    assert not (set(ex.TAGS) & set(ps.purpose))


# ---- nursery -----------------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def nursery():
    return pd.read_csv(PROCESSED / "nursery_stock.csv", keep_default_na=False)


def test_nursery_matches_and_non_matches(nursery):
    assert list(nursery.columns) == ["listed_name", "matched_species_id", "match_note", "in_system"]
    n = nursery.set_index("listed_name")
    for listed, sp in (("Guyabano", "Guyabano"), ("Cacao", "Cacao"), ("Kasoy (Kassoy)", "Kasoy"), ("Duhat", "Duhat"), ("Narra", "Narra"), ("Fire Tree", "Fire Tree"), ("Rambutan", "Rambutan"),
                       ("Sampalok", "Sampalok"), ("Avocado", "Avocado"), ("Talisay", "Talisay"), ("Coconut", "Coconut"), ("Calamansi", "Calamansi"), ("Banaba", "Banaba")):
        assert int(n.matched_species_id[listed]) == ID[sp] and n.in_system[listed] == "yes", listed
    assert SP[SP.common_name == "Kamagong"].scientific_name.iloc[0] == "Diospyros blancoi"
    assert int(n.matched_species_id["Mabolo"]) == ID["Kamagong"] and "Diospyros blancoi" in n.match_note["Mabolo"]
    assert int(n.matched_species_id["Kape"]) == ID["Robusta (Coffee)"] and n.in_system["Kape"] == "partial" and n.match_note["Kape"] == "Kape is in the nursery list, variety unknown"
    assert n.matched_species_id["Banyan"] == "" and n.in_system["Banyan"] == "no" and n.match_note["Banyan"] == "possible Weeping Fig, confirm"
    gone = ["Durian", "Morong(?)", "Tui/Tuai (Bischofia javanica)", "Kamatsile", "Suha (Citrus maxima)", "Banyaw", "Luntibani", "Balitbitan", "Eugenia", "Casimjas/Castanas(?)", "Camansi", "Atis",
            "Nymp Tree", "Lagundi", "Alibangbang", "Caupiyus(?)", "Dungon"]
    assert all(n.matched_species_id[g] == "" and n.in_system[g] == "no" for g in gone)
    assert n.match_note["Nymp Tree"] == "probably Neem; not in the system"
    assert len(nursery) == 13 + 1 + 1 + 1 + len(gone) and (nursery.in_system.value_counts().to_dict() == {"yes": 14, "partial": 1, "no": 18})


def test_a_non_matching_scientific_name_is_not_matched():
    sp = SP.copy()
    sp.loc[sp.common_name == "Kamagong", "scientific_name"] = "Diospyros philippensis"
    t = ex.build_nursery(sp).set_index("listed_name")
    assert t.matched_species_id["Mabolo"] == "" and t.in_system["Mabolo"] == "no" and "not matched" in t.match_note["Mabolo"]


# ---- interview notes ------------------------------------------------------------------------------------------------------------------------------
def test_interview_notes_cite_who_and_when():
    n = pd.read_csv(PROCESSED / "interview_notes.csv")
    assert list(n.columns) == ["species_id", "note", "source", "provisional"] and n.provisional.all()
    assert set(n.species_id) == {ID["Cacao"], ID["Clumping Bamboo"], ID["Calamansi"]}
    assert (n.source == "MAO interview, transcript, Oct 2026").all()                                  # round 15b: one source for every note
    cacao = n[n.species_id == ID["Cacao"]]
    assert cacao.note.str.contains("60% shade").any() and cacao.note.str.contains("banana or coconut").any() and cacao.note.str.contains("Silangan and Pintong Bukawe").any()
    bam = n[n.species_id == ID["Clumping Bamboo"]].note.str.cat(sep=" ")
    assert "landfill" in bam and "filters heavy metals" in bam and "Pintong Bukawe" in bam and "crafts" in bam
    assert "Gitnang Bayan I" in n[n.species_id == ID["Calamansi"]].note.iloc[0] and "Observation only" in n[n.species_id == ID["Calamansi"]].note.iloc[0]


# ---- API ---------------------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield c


def test_the_species_endpoints_carry_tags_nursery_and_notes(client):
    j = client.get("/species").json()
    by = {s["species_id"]: s for s in j["species"]}
    assert all(set(s["purpose_tags"]) <= set(ex.TAGS) and isinstance(s["in_nursery"], bool) for s in j["species"])
    assert sum(s["in_nursery"] for s in j["species"]) == 14 and by[ID["Kamagong"]]["in_nursery"] and not by[ID["Molave"]]["in_nursery"]
    rob = by[ID["Robusta (Coffee)"]]
    assert rob["in_nursery"] is False and rob["nursery_match"] == "partial" and rob["nursery_note"] == "Kape is in the nursery list, variety unknown"      # round 15b
    assert all(s["nursery_quantities"] == "Stock quantities unknown" for s in j["species"])
    d = client.get(f"/species/{ID['Cacao']}").json()
    assert d["in_nursery"] is True and d["nursery"][0]["listed_name"] == "Cacao" and "quantities unknown" in d["nursery"][0]["source"]
    assert {"fruit-bearing", "high-value crop"} <= set(d["purpose_tags"]) and d["purpose_tag_details"][0]["basis"] and "filters only" in d["tags_note"]
    assert len(d["interview_notes"]) == 2 and all(n["provisional"] for n in d["interview_notes"]) and d["interview_notes"][0]["source"] == "MAO interview, transcript, Oct 2026"
    k = client.get(f"/species/{ID['Kamagong']}").json()
    assert k["nursery"][0]["listed_name"] == "Mabolo"
    assert client.get(f"/species/{ID['Molave']}").json()["in_nursery"] is False
    assert client.get(f"/species/{ID['Molave']}").json()["interview_notes"] == []
    assert len(client.get("/species").json()["species"]) == 45


# ---- the name fix ---------------------------------------------------------------------------------------------------------------------------------
def test_pintong_bukawe_everywhere_we_control(client):
    assert fix_barangay("PINTUNG BUKAWE") == "PINTONG BUKAWE" and fix_barangay("pintung bukawe") == "PINTONG BUKAWE" and fix_barangay("MALY") == "MALY"
    j = client.get("/geo/boundaries").json()
    names = {f["properties"]["name"]: f["properties"]["display_name"] for f in j["features"][1:]}
    assert names["PINTONG BUKAWE"] == "Pintong Bukawe" and "PINTUNG BUKAWE" not in names
    assert client.get("/search/place", params={"q": "pintong"}).json()["results"][0]["display_name"] == "Pintong Bukawe"
    assert client.get("/search/place", params={"q": "bukawe"}).json()["count"] == 1
    bad = []
    files = [f for f in (ROOT / "frontend" / "src").rglob("*") if f.suffix in (".js", ".jsx", ".mjs", ".css")] + list((ROOT / "docs").glob("*.md")) + list(PROCESSED.glob("*.csv")) + list(PROCESSED.glob("*.txt")) \
        + [ROOT / "CLAUDE.md", ROOT / "README.md"] + [f for f in (ROOT / "pipeline").glob("*.py")] + [f for f in (ROOT / "tests").rglob("*") if f.suffix in (".py", ".json", ".mjs")]
    for f in files:
        if f.name in ("test_species_extras.py", "test_api_geo.py"):                                 # these two name the OLD spelling on purpose, to say it is gone
            continue
        if re.search(r"pintung", f.read_text(encoding="utf-8", errors="ignore"), re.I) and f.name not in ("names.py", "CLAUDE.md"):
            bad.append(str(f.relative_to(ROOT)))
    assert not bad, bad


def test_the_field_kit_uses_the_corrected_name():
    import field_kit as fk
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv")
    names = set(fk.assign_barangay(sites[["lon", "lat"]].iloc[::50].reset_index(drop=True), "data/BRGY_BOUNDARY.shp")[0])
    assert "PINTUNG BUKAWE" not in names and "PINTONG BUKAWE" in names


# ---- the validation record ---------------------------------------------------------------------------------------------------------------------
def test_the_signed_marks_are_saved_unchanged():
    f = ROOT / "data" / "validation" / "agri_sample_marks_20261007.csv"
    text = f.read_text(encoding="utf-8")
    assert "Alexis P. Santos, OIC-MAO" in text and "7 Oct 2026" in text and "3483e2b668e8" in text and "7 of the 8 pages" in text
    m = pd.read_csv(f, comment="#")
    assert list(m.columns) == ["sample_id", "grid", "species", "mark"] and len(m) == 40 and m.sample_id.tolist() == [f"S{i:02d}" for i in range(1, 41)]
    assert m.mark.value_counts().to_dict() == {"S": 25, "M": 11, "X": 4}
    assert set(m.species) <= set(SP.common_name)
    assert m[m.sample_id == "S20"].iloc[0].tolist() == ["S20", 10365, "Robusta (Coffee)", "S"]
    assert m[m.sample_id == "S24"].iloc[0].grid == 13896


def test_the_sample_script_reproduces_the_stored_scores_and_the_old_base():
    sys.path.insert(0, str(ROOT / "scripts"))
    import score_agri_sample as sc
    assert sc.cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == pytest.approx(1.0)
    assert sc.cohen_kappa([1, 0, 1, 0], [1, 1, 0, 0]) == pytest.approx(0.0)
    assert sc.cohen_kappa([1, 1, 1], [1, 0, 1]) == pytest.approx(0.0)
    assert sc.cohen_kappa([1, 1], [1, 1]) is None
    species, sites, pairs = sc.load_scores(sites_needed=[5845, 6977])
    s_new, over = sc.alt_slope_scores(species, sites, pairs)
    prod = pairs.s_rule.to_numpy()
    assert (s_new[prod > 0] == prod[prod > 0]).all()                                                   # where production S is above 0 the alternative rule changes nothing
    lemon = pairs[(pairs.point_id == 6977) & (pairs.species_id == ID["Lemon"])].index[0]
    assert prod[lemon] == 0 and over[lemon] == pytest.approx(21.9, abs=0.05) and s_new[lemon] == pytest.approx(0.562, abs=0.001)
