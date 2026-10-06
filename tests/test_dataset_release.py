"""Round 12: the species data frozen as release v1.0-review (data/raw files, dataset_versions, dataset_release.txt, /health, Known limits).
Run from the repo root: python -m pytest tests/test_dataset_release.py"""
import hashlib, re, sqlite3, sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
RAW = ROOT / "data" / "raw"
sys.path.insert(0, str(ROOT))
pytestmark = pytest.mark.skipif(not (PROCESSED / "dataset_release.txt").exists(), reason="run ingest_species.py --tag v1.0-review first")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def release():
    return {k: v for k, v in (re.match(r"\s*([^:]+):\s*(.*)", ln).groups() for ln in (PROCESSED / "dataset_release.txt").read_text(encoding="utf-8").splitlines() if re.match(r"\s*[^:]+:\s*.+", ln))}


def test_the_release_file_names_the_tag_and_both_hashes():
    txt = (PROCESSED / "dataset_release.txt").read_text(encoding="utf-8")
    sp, so = sha(RAW / "species_directsource.csv"), sha(RAW / "sources_list.csv")
    comb = hashlib.sha256((sp + "\n" + so).encode("ascii")).hexdigest()[:12]
    assert "dataset release v1.0-review" in txt and f"sha256: {sp}" in txt and f"sha256: {so}" in txt and f"(12 characters): {comb}" in txt
    assert "date:" in txt and "NOT signed off" in txt


def test_dataset_versions_holds_the_tag_both_hashes_and_the_combined_hash():
    con = sqlite3.connect(PROCESSED / "optimizing_survival.db")
    r = con.execute("SELECT tag, file_hash, source_file, sources_file, sources_file_hash, combined_hash12, note FROM dataset_versions ORDER BY dataset_version_id DESC LIMIT 1").fetchone()
    con.close()
    sp, so = sha(RAW / "species_directsource.csv"), sha(RAW / "sources_list.csv")
    assert r[0] == "v1.0-review" and r[1] == sp and r[2] == "species_directsource.csv" and r[3] == "sources_list.csv" and r[4] == so
    assert r[5] == hashlib.sha256((sp + "\n" + so).encode("ascii")).hexdigest()[:12] and "frozen" in r[6] and "not signed off" in r[6]


def test_the_release_counts_agree_with_the_data_and_the_ingest_report():
    txt = (PROCESSED / "dataset_release.txt").read_text(encoding="utf-8")
    sp, src = pd.read_csv(PROCESSED / "species_clean.csv"), pd.read_csv(PROCESSED / "species_sources.csv")
    rep = pd.read_csv(PROCESSED / "ingest_report.csv")
    assert len(sp) == 45 and f"species: {len(sp)}" in txt and f"cited cells: {len(src)}" in txt and f"ingest issues in total: {len(rep)}" in txt
    for (sev, issue), n in rep.groupby(["severity", "issue"]).size().items():
        assert f"  {sev}, {issue}: {n}" in txt
    known = rep.groupby("issue").size().to_dict()
    assert known["file_source_not_provided"] == 34 and known["off_list_source"] == 30 and known["nonstandard_citation"] == 20 and known["no_type_I_preference"] == 6 and known["soil_text_unmapped"] == 1


def test_the_two_changes_since_the_draft():
    sp = pd.read_csv(PROCESSED / "species_clean.csv").set_index("common_name")
    assert pd.isna(sp.loc["Palosapis", "rain_max_mm"])                                      # the doubtful rain_max was removed, not guessed
    assert int(sp.loc["Palosapis", "n_cells_cited"]) == 51
    src = pd.read_csv(PROCESSED / "species_sources.csv")
    assert not ((src.species == "Palosapis") & (src.field_name == "rain_max_mm")).any()
    b = src[(src.species == "Batikuling") & (src.field_name == "sexuality_raw")].iloc[0]
    assert b.source_url == "https://tropical.theferns.info/viewtropical.php?id=Litsea+leytensis"
    assert "truncated_url" not in str(b.flags) and "url_missing_scheme" not in str(b.flags)         # the citation is now a clean URL (it was flagged truncated before)
    raw = pd.read_csv(RAW / "species_directsource.csv", dtype=str, keep_default_na=False)
    assert "Dioecious [Source: https://tropical.theferns.info" in raw.loc[raw.iloc[:, 0].str.startswith("Batikuling"), "Sexuality"].iloc[0]


def test_the_raw_files_are_the_unedited_candidates():
    for f in RAW.glob("*.csv"):
        assert b"\r\r" not in f.read_bytes()
    assert (RAW / "species_directsource.csv").stat().st_size == 225352 and (RAW / "sources_list.csv").stat().st_size == 21452


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import api_v2
    with TestClient(api_v2.app) as c:
        yield c


def test_health_and_known_limits_show_the_tag_and_hash(client):
    h = client.get("/health").json()
    sp, so = sha(RAW / "species_directsource.csv"), sha(RAW / "sources_list.csv")
    comb = hashlib.sha256((sp + "\n" + so).encode("ascii")).hexdigest()[:12]
    assert h["dataset_version"] == "v1.0-review" and h["dataset_hash"] == comb and h["dataset_file_hash"] == sp == h["dataset_species_file_sha256"] and h["dataset_sources_file_sha256"] == so
    lim = " ".join(h["limits"])
    assert f"Species data release v1.0-review (hash {comb})" in lim and "not signed off" in lim
    for t in ("34 cells cite a file that was not provided", "30 cite sources outside the supplied list", "20 citations are non-standard", "6 species have no Type I climate preference", "1 species soil text is unmapped"):
        assert t in lim, t
