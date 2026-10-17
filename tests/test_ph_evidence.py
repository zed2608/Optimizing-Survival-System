"""PH integration: the species pH evidence file, the reader, the comparison kinds, the API fields and the Docker coverage. Display only: nothing here touches a score."""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import soilgrids_ph as sg  # noqa: E402
import species_ph_evidence as spe  # noqa: E402

EV = ROOT / "data" / "reference" / "species_ph_evidence.csv"
AG = ROOT / "data" / "reference" / "species_climate_agreement.csv"
NONE_IDS = {3, 4, 8, 9, 10, 11, 21, 23, 32, 33, 34, 35, 37, 40, 42, 44}
NUM = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?!\d)")


@pytest.fixture(scope="module")
def ev():
    return pd.read_csv(EV)


def test_45_rows_and_the_16_none(ev):
    assert len(ev) == 45 and ev.species_id.is_unique
    assert set(ev[ev.status == "none"].species_id) == NONE_IDS
    assert (ev.status == "sourced").sum() == 29


def test_none_rows_have_no_number_link_or_rank(ev):
    n = ev[ev.status == "none"]
    for c in ("tol_min", "tol_max", "opt_min", "opt_max", "listed_min", "listed_max", "verdict_min", "verdict_max", "source_url", "source_rank"):
        assert n[c].isna().all(), c
    assert (n.verdict_kind == "none").all()
    assert "binasa nang buo" in ev.set_index("species_id").loc[10, "note"]


def test_every_number_is_in_the_quote_and_min_le_max(ev):
    for r in ev[ev.status == "sourced"].itertuples():
        text = {float(x) for x in NUM.findall(str(r.quote) + " " + str(r.alt_sources))}
        assert r.verdict_min <= r.verdict_max
        for lo, hi in ((r.tol_min, r.tol_max), (r.opt_min, r.opt_max), (r.listed_min, r.listed_max)):
            if pd.notna(lo):
                assert lo <= hi and lo in text and hi in text, r.species_id
        assert str(r.source_url).startswith("http")


def test_rank_follows_the_host(ev):
    for r in ev[ev.status == "sourced"].itertuples():
        h = re.match(r"https?://([^/]+)", r.source_url).group(1)
        if h.endswith("da.gov.ph") or "pcaarrd" in h or "denr" in h:
            assert r.source_rank == 1
        elif h.endswith(".edu.ph"):
            assert r.source_rank == 2
        else:
            assert r.source_rank == 3, (r.species_id, h)
        assert (r.source_kind == "compilation_secondary") == (("theferns" in h) or ("pfaf" in h))


def test_manual_cases(ev):
    e = ev.set_index("species_id")
    assert (e.loc[6, "opt_min"], e.loc[6, "opt_max"], e.loc[6, "tol_min"], e.loc[6, "tol_max"]) == (5.5, 6.5, 4.5, 7.0)
    assert e.loc[43, "source_kind"] == "ecocrop" and e.loc[43, "conflict"] == "yes" and "pfaf" in e.loc[43, "alt_sources"].lower()
    assert e.loc[22, "verdict_kind"] == "listed"          # "tolerant of alkalinity" is not a tolerance range
    assert e.loc[13, "scope"] == "genus_or_group" and e.loc[13, "verdict_kind"] == "optimal_only"
    assert (ev.conflict == "yes").sum() == 1


def test_no_verified_wording(ev):
    blob = " ".join(ev.note.fillna("")).lower()
    assert "kinumpirma" not in blob and "verified" not in blob.replace("not verified", "")


def test_reader_none_and_sourced():
    assert spe.reference(10)["status"] == "none" and spe.reference(10)["source_url"] is None and spe.reference(10)["text"] == spe.NONE_TEXT
    r = spe.reference(1)
    assert r["status"] == "sourced" and (r["opt_min"], r["opt_max"]) == (5.5, 6.5) and (r["tol_min"], r["tol_max"]) == (5.0, 7.5) and r["source_rank"] == 3
    assert spe.verdict_range(10) == (None, None, "none")
    assert spe.verdict_range(1) == (5.0, 7.5, "tolerance")
    assert spe.reference(1, path=ROOT / "no_such_file.csv") is None and spe.verdict_range(1, path=ROOT / "no_such_file.csv") == (None, None, "none")


def test_compare_interval_kinds():
    c = sg.compare_interval
    assert c(5.5, 6.0, 5.0, 7.5) == "inside" and c(8, 8.5, 5.0, 7.5) == "outside" and c(4, 6, 5, 7) == "uncertain" and c(None, 6, 5, 7) == "no_value" and c(5, 6, None, 7) == "no_range"
    assert c(8, 8.5, 5.0, 6.5, "optimal_only") == "outside_optimal"
    assert c(5.5, 6.0, 5.0, 6.5, "optimal_only") == "inside" and c(4.5, 7, 5.0, 6.5, "optimal_only") == "uncertain"
    assert c(8, 8.5, 5.0, 7.5, "tolerance") == "outside" and c(8, 8.5, 5.0, 7.5, "listed") == "outside"
    assert c(5.5, 6.0, None, None, "none") == "no_confirmed_range" and c(None, None, None, None, "none") == "no_confirmed_range"


def test_climate_agreement_only_for_match():
    ag = pd.read_csv(AG)
    assert len(ag) == 90 and set(ag.parameter) == {"rain", "temp"}
    m = ag[ag.agreement == "match"]
    assert len(m) == 6 and m.source_url_if_match.str.startswith("http").all()
    assert (ag[ag.agreement != "match"].source_url_if_match.isna()).all()
    nomatch = ag[ag.agreement == "no_match"].iloc[0]
    assert spe.climate_match(int(nomatch.species_id), nomatch.parameter) is None
    hit = m.iloc[0]
    assert spe.climate_match(int(hit.species_id), hit.parameter)["source_url"] == hit.source_url_if_match


def test_api_species_detail_uses_the_evidence():
    from fastapi.testclient import TestClient
    import api_v2
    with TestClient(api_v2.app) as c:
        a = c.get("/species/1").json()
        assert a["ph_reference"]["status"] == "sourced" and a["ph_reference"]["source_url"].startswith("http")
        assert not [f for f in a["fields"] if f["field_name"] in ("ph_min", "ph_max")]
        assert "ph_min" not in a["clean_values"] and "ph_max" not in a["clean_values"]
        for f in a["fields"]:
            if f["field_name"].startswith(("rain", "temp")) and f.get("unmatched_source"):
                assert f["source_url"] is None and f["source_rank"] is None
        assert any(f.get("unmatched_source") for f in a["fields"] if f["field_name"].startswith("rain"))
        b = c.get("/species/10").json()
        assert b["ph_reference"]["status"] == "none"
        s = b["site_ph"]
        assert s.get("verdict") in (None, "no_confirmed_range") and s["scored"] is False
        allp = c.get("/species-ph-reference").json()
        assert allp["available"] and len(allp["species"]) == 45


def test_docker_copies_the_evidence_files():
    d = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ig = [x.strip() for x in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    def fnmatch_fn(path, pat):                      # Docker's rule: * does not cross a slash
        return re.fullmatch(re.escape(pat).replace(r"\*\*", ".*").replace(r"\*", "[^/]*"), path) is not None

    class fnmatch:
        fnmatch = staticmethod(fnmatch_fn)
    needed = ["data/reference/soilgrids_ph.csv", "data/reference/species_ph_evidence.csv", "data/reference/species_climate_agreement.csv"]
    for f in needed:
        assert f.split("/")[-1] in d, f + " is not copied by the Dockerfile"
        assert (ROOT / f).is_file()
        assert not any(fnmatch.fnmatch(f, p) or f.startswith(p.rstrip("/") + "/") for p in ig), f + " is excluded by .dockerignore"


def test_verification_sheet_ph_rows():
    import species_verification as sv
    rows = {r["row_id"]: r for r in sv.build_rows()}
    none_row = rows["10|ph_min"]
    assert none_row["source"] == "" and none_row["source_rank"] == "" and "kailangang magpasya ang agriculturist" in none_row["source_note"]
    narra = rows["1|ph_min"]
    assert narra["source"].startswith("http") and "hindi pa pirmado" in narra["source_note"] and narra["source_rank"] == "3"
    rain = [r for k, r in rows.items() if k.endswith("rain_min_mm") and "hindi tugma" in r["source_note"]]
    assert rain and all(r["source"] == "" for r in rain)


def test_frontend_source_wiring():
    """No JSX runner here, so the wiring is pinned in the source: the none branch has no SourceLink, the card uses PhEvidence, the plan result uses PlanPh, no 'verified' claim."""
    src = ROOT / "frontend" / "src" / "new"
    ph = (src / "PhEvidence.jsx").read_text(encoding="utf-8")
    none_branch = ph.split("row.none ? (")[1].split(") : (")[0]
    assert "SourceLink" not in none_branch and "ph-none-help" in none_branch
    assert "<SourceLink" in ph.split(") : (")[1] and "ph-conflict" in ph and "ph-tag" in ph and "PhMeasureTool" in ph
    card = (src / "SpeciesCard.jsx").read_text(encoding="utf-8")
    assert "<PhEvidence reference=" in card and "unmatched_source" in card and "F.ph_min" not in card
    assert "<PlanPh " in (src / "PlanResult.jsx").read_text(encoding="utf-8")
    tool = ph.split("export function PhMeasureTool")[1].split("export default")[0]
    assert "fetch(" not in tool and "localStorage" not in tool and "apiGet" not in tool and "apiPost" not in tool
