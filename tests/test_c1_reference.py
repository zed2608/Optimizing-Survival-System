"""Stage C1: reference values for rain, climate type, temperature and pH (display only), the verification form for the agriculturist, and its import report.
NOTHING here may change a score: the species table, the release hash, site_scores, the model and the pair table stay as they are.
Run from the repo root: python -m pytest tests/test_c1_reference.py"""
import csv, hashlib, math, os, re, subprocess, sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import climate_reference as cref  # noqa: E402
import species_verification as sv  # noqa: E402

NEEDS_DATA = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ================================================================ step 1: the reference file
def test_the_reference_file_has_every_key_and_the_agreed_values():
    rows = list(csv.DictReader(open(cref.PATH, encoding="utf-8", newline="")))
    assert list(rows[0].keys()) == ["key", "value", "unit", "source", "source_url", "station_or_scope", "accessed_date", "status", "note"]
    by = {r["key"]: r for r in rows}
    assert sorted(by) == sorted(["annual_rainfall_mm", "climate_type", "annual_mean_temperature_c", "soil_ph"]) and len(rows) == 4
    rain = by["annual_rainfall_mm"]
    assert rain["value"] == "2574.4" and rain["unit"] == "mm" and rain["source"] == "PAGASA Climatological Normals"
    assert rain["source_url"] == "https://www.pagasa.dost.gov.ph/climate/climatological-normals" and "Science Garden, Quezon City" in rain["station_or_scope"] and "NOT San Mateo" in rain["station_or_scope"]
    assert rain["accessed_date"] == "2026-10-15" and rain["status"] == "provisional_proxy" and "30-year" in rain["note"]
    ct = by["climate_type"]
    assert ct["value"] == "Type I (tuyo mula Disyembre hanggang Mayo)" and ct["status"] == "provisional" and "LCCAP" in ct["source"] and "page 11" in ct["source"]
    assert "SAN_MATEO_LCCAP_2021-2025.pdf" in ct["note"] and "docs/DATA_SOURCES.md" in ct["note"]            # the exact place it was read
    assert by["annual_mean_temperature_c"]["value"] == "" and by["annual_mean_temperature_c"]["status"] == "pending" and "PAGASA" in by["annual_mean_temperature_c"]["note"]
    assert by["soil_ph"]["value"] == "" and by["soil_ph"]["status"] == "no_layer" and "no pH layer" in by["soil_ph"]["note"]


def test_no_number_without_a_source_and_a_status_and_no_gap_without_a_reason():
    ref = cref.load()
    assert cref.validate(list(csv.DictReader(open(cref.PATH, encoding="utf-8", newline=""))))
    for k, r in ref.items():
        assert r["status"] and r["accessed_date"], k
        if r["value"] is not None:
            assert r["source"] and r["station_or_scope"] and r["status"].startswith("provisional"), k
        else:
            assert r["status"] in ("pending", "no_layer"), k
    assert ref["annual_rainfall_mm"]["value"] == 2574.4 and isinstance(ref["annual_rainfall_mm"]["value"], float)


def base_rows():
    return [dict(r) for r in csv.DictReader(open(cref.PATH, encoding="utf-8", newline=""))]


@pytest.mark.parametrize("change, message", [
    (lambda rows: rows[0].update(source=""), "without a source"),
    (lambda rows: rows[0].update(status="verified"), "status"),
    (lambda rows: rows[0].update(station_or_scope=""), "station"),
    (lambda rows: rows[0].update(accessed_date=""), "accessed_date"),
    (lambda rows: rows[0].update(value="lots"), "not a number"),
    (lambda rows: rows[2].update(status="provisional"), "pending or no_layer"),
    (lambda rows: rows[3].update(value="6.5"), "status says there is none"),
    (lambda rows: rows.pop(), "exactly the keys"),
])
def test_the_checker_refuses_a_file_that_breaks_a_rule(change, message):
    rows = base_rows()
    change(rows)
    with pytest.raises(cref.ReferenceError, match=message):
        cref.validate(rows)


def test_the_rain_comparison_is_honest():
    a = 2574.4
    assert cref.rain_assessment(1200, 3000, a) == "fits" and cref.rain_assessment(2574.4, 3000, a) == "fits" and cref.rain_assessment(1000, 2574.4, a) == "fits"
    assert cref.rain_assessment(3000, 5000, a) == "below" and cref.rain_assessment(250, 2000, a) == "above"
    assert cref.rain_assessment(None, 3000, a) == "fits" and cref.rain_assessment(None, 2000, a) == "above" and cref.rain_assessment(3000, None, a) == "below"        # one limit is enough
    assert cref.rain_assessment(float("nan"), float("nan"), a) == "no_data" and cref.rain_assessment(1200, 3000, None) == "no_data"                             # no range, or no reference: never a guess
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    answers = {cref.rain_assessment(r.rain_min_mm, r.rain_max_mm, a) for r in sp.itertuples()}
    assert answers <= {"fits", "below", "above"}  and "fits" in answers and "above" in answers                                                                      # real answers from the species own numbers (no species needs more than 2574.4 mm a year: "below" does not occur in the data)


# ================================================================ step 2: the form
def expected_rows():
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    return sum(int(sp[a].notna().sum()) for a in sv.ATTR_NAMES)


def test_the_sheet_has_one_row_per_species_and_attribute_that_has_a_value():
    rows = sv.build_rows(PROCESSED)
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    assert len(rows) == expected_rows() == 359 and {r["species_id"] for r in rows} == set(sp.species_id)
    assert len({r["row_id"] for r in rows}) == len(rows)
    for a in sv.ATTR_NAMES:
        assert sum(1 for r in rows if r["attribute"] == a) == int(sp[a].notna().sum()), a
    assert sum(1 for r in rows if r["attribute"] == "rain_max_mm") == 44                            # Palosapis has no rain_max (removed on purpose): no row, nothing invented
    assert not [r for r in rows if r["attribute"] == "rain_max_mm" and r["common_name"] == "Palosapis"]
    narra = next(r for r in rows if r["species_id"] == 1 and r["attribute"] == "ph_min")
    assert narra["common_name"] == "Narra" and narra["scientific_name"] == "Pterocarpus indicus" and narra["current_value"] == "5" and narra["source_rank"] == "3" and narra["source"].startswith("https://prosea")
    assert all(r["verdict"] == "" and r["corrected_value"] == "" and r["remarks"] == "" and r["reviewer"] == "" and r["date"] == "" for r in rows)
    assert any("OFF-LIST" in r["source_note"] for r in rows) and any("FLAGGED" in r["source_note"] for r in rows)       # off-list and flagged sources are marked


def test_the_pdf_has_the_hash_the_provisional_line_the_signature_lines_and_every_row(tmp_path):
    import pymupdf
    before = {f: sha(PROCESSED / f) for f in ("species_clean.csv", "species_sources.csv", "dataset_release.txt")}
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_species_verification_sheet.py"), "--out", str(tmp_path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    pdfs, csvs = sorted(tmp_path.glob("species_verification_sheet_*.pdf")), sorted(tmp_path.glob("species_verification_sheet_*.csv"))
    assert len(pdfs) == 1 and len(csvs) == 1 and re.search(r"_\d{8}\.pdf$", pdfs[0].name)                                  # dated names
    doc = pymupdf.open(pdfs[0])
    n = expected_rows()
    assert doc.page_count == math.ceil(n / sv.ROWS_PER_PAGE) == 33
    text = [p.get_text() for p in doc]
    for t in text:                                                                                                   # on EVERY page
        assert "34964a09fe44" in t and "v1.0-review" in t and sv.PROVISIONAL_LINE in t and sv.PROVISIONAL_LINE == "PROVISIONAL: hindi pa napatutunayan"
        assert "Pagsusuri ng klima at lupa" in t and "ginawa noong" in t
        assert "Pangalan ng reviewer" in t and "Posisyon" in t and "Pirma" in t and "Petsa" in t                       # the reviewer lines at the end of each page
    whole = "\n".join(text)
    assert whole.count("[  ] Tama") == n and whole.count("Palitan sa:") == n                                          # one answer box per row
    assert "Narra" in whole and "Pterocarpus indicus" in whole and "Pinakamababang pH ng lupa" in whole and "Mga uri ng klima" in whole
    assert doc.metadata["title"].startswith("Pagsusuri") and "34964a09fe44" in doc.metadata["subject"]
    rows = list(csv.DictReader(open(csvs[0], encoding="utf-8-sig", newline="")))
    assert len(rows) == n and list(rows[0].keys()) == sv.SHEET_COLUMNS and {"verdict", "corrected_value", "remarks", "reviewer", "date"} <= set(rows[0])
    again = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_species_verification_sheet.py"), "--out", str(tmp_path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert again.returncode == 0 and len(list(tmp_path.glob("*.pdf"))) == 2 and len(list(tmp_path.glob("*.csv"))) == 2 and (tmp_path / pdfs[0].name).exists()      # never overwritten
    assert before == {f: sha(PROCESSED / f) for f in before}                                                          # the species data and the release did not change


def make_returned(tmp_path, edit=None, name="returned.csv"):
    rows = sv.build_rows(PROCESSED)
    if edit:
        edit(rows)
    p = tmp_path / name
    sv.write_csv(rows, p)
    return p


def run_import(path, out):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "import_species_verification.py"), str(path), "--out", str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)


def test_the_import_counts_confirmed_replaced_and_unanswered_and_writes_new_dated_files(tmp_path):
    before = {f: sha(PROCESSED / f) for f in ("species_clean.csv", "species_sources.csv", "dataset_release.txt", "purpose_scores.csv", "site_points_clean.csv")}
    def edit(rows):
        for r in rows[:10]:
            r["verdict"] = "Tama"
        rows[10].update(verdict="Palitan", corrected_value="6.5", remarks="PROSEA page 12")
        rows[11].update(verdict="replace", corrected_value="1500", remarks="local")
        rows[12].update(verdict="correct")
    p = make_returned(tmp_path, edit)
    out = tmp_path / "out"
    r = run_import(p, out)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-500:]
    assert "confirmed (Tama): 11" in r.stdout and "replaced (Palitan): 2" in r.stdout and f"no answer: {359 - 13}" in r.stdout and "NOT applied" in r.stdout
    csvs, txts = list(out.glob("species_verification_*.csv")), list(out.glob("species_verification_*.txt"))
    assert len(csvs) == 1 and len(txts) == 1 and re.search(r"species_verification_\d{8}\.csv$", csvs[0].name)
    rows = list(csv.DictReader(open(csvs[0], encoding="utf-8-sig", newline="")))
    assert sum(1 for x in rows if x["verdict"] == "correct") == 11 and sum(1 for x in rows if x["verdict"] == "replace") == 2          # Tama / Palitan are stored as correct / replace
    again = run_import(p, out)
    assert again.returncode == 0 and len(list(out.glob("species_verification_*.csv"))) == 2                                          # a second import makes new files, never overwrites
    assert before == {f: sha(PROCESSED / f) for f in before}                                                                        # nothing in data/processed changed


@pytest.mark.parametrize("edit, message", [
    (lambda rows: rows[0].update(verdict="maybe"), "verdict 'maybe'"),
    (lambda rows: rows[0].update(species_id=999), "unknown species_id 999"),
    (lambda rows: rows[0].update(attribute="potassium"), "unknown attribute 'potassium'"),
    (lambda rows: rows[0].update(verdict="replace", corrected_value=""), "needs a corrected_value"),
    (lambda rows: rows[0].update(verdict="replace", corrected_value="high"), "is not a number"),
    (lambda rows: rows[0].update(verdict="correct", corrected_value="7"), "use replace"),
    (lambda rows: rows.append(dict(rows[0])), "appears twice"),
    (lambda rows: rows[1].update(row_id="1|ph_min"), "does not match"),
])
def test_the_import_refuses_a_bad_file_and_writes_nothing(tmp_path, edit, message):
    p = make_returned(tmp_path, edit)
    out = tmp_path / "out"
    r = run_import(p, out)
    assert r.returncode == 2 and "NOT accepted" in r.stdout and message in r.stdout, r.stdout[-600:]
    assert not out.exists() or not list(out.iterdir())


def test_the_import_refuses_a_file_that_is_not_the_form(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    r = run_import(p, tmp_path / "out")
    assert r.returncode == 2 and "lacks the columns" in r.stdout


# ================================================================ nothing in the scoring reads any of it
def test_no_scoring_module_uses_the_reference_or_the_form():
    scoring = ["score_sites.py", "score_purposes.py", "matching.py", "palettes.py", "train_rf.py", "make_pair_table.py", "run_plan.py", "site_rules.py", "compare_models.py", "rebuild_site_grid.py", "advice.py", "partners.py"]
    for name in scoring:
        src = (ROOT / "pipeline" / name).read_text(encoding="utf-8")
        assert "climate_reference" not in src and "species_verification" not in src, name
    api = (ROOT / "api_v2.py").read_text(encoding="utf-8")
    assert api.count("cref.") == 3 and "d.climate_ref" in api                                    # only the loader (load, ReferenceError) and the species detail (for_species) touch it
    dock = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^COPY data/config/ data/config/\s*$", dock, re.M) and "climate_reference.csv" not in (ROOT / ".dockerignore").read_text(encoding="utf-8")        # the file reaches the image


# ================================================================ step 3: the API field (display only)
@pytest.fixture(scope="module")
def client():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield {"c": c, "api": api_v2}


@NEEDS_DATA
def test_the_species_detail_carries_the_reference_exactly_as_in_the_file(client):
    c = client["c"]
    j = c.get("/species/1").json()["climate_reference"]
    file_rows = {r["key"]: r for r in csv.DictReader(open(cref.PATH, encoding="utf-8", newline=""))}
    assert [i["key"] for i in j["items"]] == cref.KEYS
    for i in j["items"]:
        want = file_rows[i["key"]]
        assert {k: i[k] for k in cref.COLUMNS if k != "value"} == {k: want[k] for k in cref.COLUMNS if k != "value"}           # source, station, date and status are the file's, word for word
        assert (i["value"] is None and want["value"] == "") or str(i["value"]).rstrip("0").rstrip(".") == want["value"].rstrip("0").rstrip(".") or i["value"] == want["value"]
    assert j["scored"] is False and "not part of the score" in j["note"] and j["rain"]["reference_mm"] == 2574.4
    sp = pd.read_csv(PROCESSED / "species_clean.csv").set_index("species_id")
    for sid in (1, 7, 21, 40):
        r = c.get(f"/species/{sid}").json()["climate_reference"]
        row = sp.loc[sid]
        assert r["rain"]["assessment"] == cref.rain_assessment(row.rain_min_mm, row.rain_max_mm, 2574.4) and r["rain"]["species_min_mm"] == row.rain_min_mm
        assert r["temperature"]["assessment"] == "no_data" and r["ph"]["assessment"] == "no_data"                               # no number: "no data yet", no verdict


@NEEDS_DATA
def test_a_different_reference_changes_no_score_no_rank_and_no_plan(client):
    c, api = client["c"], client["api"]
    d = api.app.state.data
    first = {p: c.get(p).json() for p in ("/rank?point_id=832&purpose=urban&limit=45", "/rank?point_id=2000&purpose=watershed&limit=45", "/species")}
    saved = d.climate_ref
    try:
        d.climate_ref = {**saved, "annual_rainfall_mm": {**saved["annual_rainfall_mm"], "value": 1.0}}
        assert c.get("/species/1").json()["climate_reference"]["rain"]["assessment"] == "below"                                  # the display moves ...
        second = {p: c.get(p).json() for p in first}
    finally:
        d.climate_ref = saved
    assert first == second                                                                                                      # ... the scores, the ranks and the species list do not


@NEEDS_DATA
def test_the_species_detail_still_works_without_the_file(client):
    api, c = client["api"], client["c"]
    d = api.app.state.data
    saved = d.climate_ref
    try:
        d.climate_ref = None
        j = c.get("/species/1").json()["climate_reference"]
    finally:
        d.climate_ref = saved
    assert j["items"] == [] and j["rain"]["assessment"] == "no_data" and j["scored"] is False


# ================================================================ the dashboard side
def test_the_card_section_is_wired_and_has_the_agreed_words():
    card = (ROOT / "frontend" / "src" / "new" / "SpeciesCard.jsx").read_text(encoding="utf-8")
    assert "<ClimateReference cref={d.climate_reference} cv={cv} sitePh={d.site_ph} />" in card and "buildClimate" in card and "PROVISIONAL" in card
    js = (ROOT / "frontend" / "src" / "new" / "climateRef.js").read_text(encoding="utf-8")
    for must in ("Klima at lupa (reference lang)", "Pasok", "Mababa sa saklaw na nakalista (hindi pa verified)", "Lampas sa saklaw na nakalista (hindi pa verified)", "Walang datos pa",
                 "Hindi ito bahagi ng score. Pinakamalapit na istasyon ang gamit, hindi San Mateo mismo."):
        assert must in js, must
    assert not re.search(r"\b\d{3,}\.\d\b", js)                                                                                  # no number is typed in the code (2574.4 comes from the file)


def test_the_node_tests_of_the_section_pass():
    import shutil
    r = subprocess.run([shutil.which("node"), "--test", "src/new/climateRef.test.mjs"], cwd=ROOT / "frontend", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout[-1500:]
    assert "# pass 9" in r.stdout and "# fail 0" in r.stdout
