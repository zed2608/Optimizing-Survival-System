"""Stage C2: SoilGrids pH is a DISPLAY-ONLY reference. Nothing that scores may read it, and nothing is invented when it is missing."""
import hashlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import soilgrids_ph as sg  # noqa: E402

FILES = ["data/processed/scores/site_scores.csv", "data/processed/scores/site_scores.db", "data/processed/scores/pair_table.csv.gz",
         "data/processed/models/rf_site_suitability.joblib", "data/processed/species_clean.csv", "data/processed/species_sources.csv",
         "data/processed/dataset_release.txt", "data/processed/purpose_scores.csv", "data/processed/site_points_clean.csv"]
CSV = ROOT / "data" / "reference" / "soilgrids_ph.csv"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def test_loader_never_invents(tmp_path):
    assert sg.load(tmp_path / "missing.csv") == {}
    a = sg.site_answer({}, 5, 5.0, 7.0)
    assert a["available"] is False and a["reason"] == "no_file" and "ph_mean" not in a
    p = tmp_path / "x.csv"
    p.write_text("square_id,ph_mean_0_30,ph_q05_0_30,ph_q95_0_30,source,license,depth_note,accessed_date,status\n1,5.80,5.2,6.8,s,l,d,2026-10-15,m\n2,,,,s,l,d,2026-10-15,m\n", encoding="utf-8")
    t = sg.load(p)
    assert t[2]["mean"] is None
    b = sg.site_answer(t, 2, 5.0, 7.0)
    assert b["available"] is False and b["reason"] == "no_value_here" and "ph_mean" not in b
    assert sg.site_answer(t, 99, 5.0, 7.0)["reason"] == "no_value_here"
    ok = sg.site_answer(t, 1, 5.0, 7.0)
    assert ok["available"] and ok["verdict"] == "inside" and ok["scored"] is False and ok["attribution"].startswith("pH: SoilGrids 2.0 (ISRIC), CC BY 4.0")
    assert sg.site_answer(t, 1, 7.0, 8.0)["verdict"] == "outside"
    assert sg.site_answer(t, 1, 6.0, 7.0)["verdict"] == "uncertain"
    assert sg.site_answer(t, 1, None, None)["verdict"] == "no_range"


def test_stored_values_are_divided_by_ten_and_zero_is_empty():
    assert sg.D_FACTOR == 10 and sg.NODATA == 0
    t = sg.load(CSV)
    vals = [v["mean"] for v in t.values() if v["mean"] is not None]
    assert vals and 3.5 <= min(vals) and max(vals) <= 9.5          # a pH (not pH x 10, not 0)
    assert len(t) == 8088 and sum(v["mean"] is None for v in t.values()) == 650


def test_the_file_has_the_agreed_columns_and_labels():
    import csv
    with open(CSV, encoding="utf-8") as f:
        r = csv.DictReader(f)
        first = next(r)
        assert r.fieldnames[:9] == ["square_id", "ph_mean_0_30", "ph_q05_0_30", "ph_q95_0_30", "source", "license", "depth_note", "accessed_date", "status"]
    assert first["source"] == "SoilGrids 2.0, ISRIC" and first["license"] == "CC BY 4.0" and first["status"] == "model_estimate_not_measured"
    assert "PROVISIONAL" in first["depth_note"]


def test_squares_are_the_same_ids_as_the_site_grid():
    import pandas as pd
    ids = set(pd.read_csv(ROOT / "data/processed/site_points_clean.csv", usecols=["point_id"]).point_id)
    assert set(sg.load(CSV)) == ids


def test_no_scoring_module_reads_it():
    banned = re.compile(r"soilgrids_ph|site_ph|data/reference|climate_reference")
    scoring = ["score_sites.py", "score_purposes.py", "make_pair_table.py", "train_rf.py", "matching.py", "palettes.py", "run_plan.py", "compare_models.py", "site_rules.py", "advice.py", "partners.py", "rebuild_site_grid.py"]
    for n in scoring:
        p = ROOT / "pipeline" / n
        if p.exists():
            assert not banned.search(p.read_text(encoding="utf-8")), n
    users = [p.name for p in list((ROOT / "pipeline").glob("*.py")) + [ROOT / "api_v2.py"] if re.search(r"import soilgrids_ph|from soilgrids_ph", p.read_text(encoding="utf-8"))]
    assert users == ["api_v2.py"]


def test_the_api_adds_the_ph_to_the_species_card_only(monkeypatch):
    from fastapi.testclient import TestClient
    import api_v2
    with TestClient(api_v2.app) as c:
        a = c.get("/species/1").json()
        assert a["site_ph"]["scope"] == "municipality" and a["site_ph"]["scored"] is False
        pid = next(k for k, v in sg.load(CSV).items() if v["mean"] is not None)
        b = c.get(f"/species/1?point_id={pid}").json()["site_ph"]
        assert b["scope"] == "square" and b["available"] and 3.5 < b["ph_mean"] < 9.5
        gap = next(k for k, v in sg.load(CSV).items() if v["mean"] is None)
        g = c.get(f"/species/1?point_id={gap}").json()["site_ph"]
        assert g["available"] is False and "ph_mean" not in g
        # the ranking of the same square is the same with and without the pH file
        r1 = c.get(f"/rank?point_id={pid}&purpose=urban&limit=45").json()
        monkeypatch.setattr(api_v2.app.state.data, "soil_ph", {}, raising=False)
        r2 = c.get(f"/rank?point_id={pid}&purpose=urban&limit=45").json()
        assert r1 == r2


def test_scores_and_release_files_are_untouched_by_building_the_table(tmp_path):
    before = {f: sha(ROOT / f) for f in FILES if (ROOT / f).exists()}
    assert len(before) >= 7
    rows, extra = sg.sample()
    sg.write_csv(rows, tmp_path / "again.csv")
    assert {f: sha(ROOT / f) for f in before} == before
    assert sha(tmp_path / "again.csv") == sha(CSV) or True        # the accessed date may differ on another day: the data columns are compared next
    import pandas as pd
    a, b = pd.read_csv(tmp_path / "again.csv"), pd.read_csv(CSV)
    assert a.drop(columns=["accessed_date"]).equals(b.drop(columns=["accessed_date"]))


def test_compare_interval_rule_every_case():
    c = sg.compare_interval
    assert c(5.2, 6.8, 5.0, 7.5) == "inside"                 # whole interval inside
    assert c(5.0, 7.5, 5.0, 7.5) == "inside"                 # the limits count as inside
    assert c(3.0, 4.5, 5.0, 7.5) == "outside"                # whole interval below
    assert c(8.0, 9.0, 5.0, 7.5) == "outside"                # whole interval above
    assert c(4.9, 6.0, 5.0, 7.5) == "uncertain"              # crosses the lower edge
    assert c(6.0, 7.6, 5.0, 7.5) == "uncertain"              # crosses the upper edge
    assert c(4.0, 8.0, 5.5, 6.5) == "uncertain"              # wider than the range
    assert c(4.0, 5.0, 5.0, 7.5) == "uncertain"              # touches the edge from outside: not the whole interval outside
    assert c(None, None, 5.0, 7.5) == "no_value"             # no pH value
    assert c(float("nan"), 6.0, 5.0, 7.5) == "no_value"
    assert c(5.2, 6.8, None, None) == "no_range"             # the species has no range: nothing is made up
    assert c(5.2, 6.8, 5.0, None) == "no_range"
    assert c(5.2, 6.8, "", "") == "no_range"


def test_the_licence_evidence_file_is_kept_and_the_credit_says_verify():
    assert "[VERIFY]" in sg.ATTRIBUTION and sg.ATTRIBUTION.startswith("pH: SoilGrids 2.0 (ISRIC), CC BY 4.0")
    ev = (ROOT / "data" / "reference" / "soilgrids_license_evidence.txt").read_text(encoding="utf-8")
    assert "AccessConstraints" in ev and "CC-BY 4.0" in ev and "data-policy" in ev


def test_the_data_files_are_copied_into_the_image():
    d = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY data/reference/soilgrids_ph.csv data/reference/" in d
    ig = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "data/reference" not in ig and "data/reference/raw" in ig       # the 9 rasters stay out; the table goes in
