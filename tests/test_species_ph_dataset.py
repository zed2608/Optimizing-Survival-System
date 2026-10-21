"""Phase 0 D: the working pH range of every species is the project species dataset (data/reference/species_ph_dataset.csv, made by scripts/build_species_ph_dataset.py).
The evidence file stays as a cross-reference only. Display only: no score reads these ranges."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))
import build_species_ph_dataset as bd  # noqa: E402
import species_ph_evidence as spe  # noqa: E402


def test_the_dataset_file_has_45_valid_ranges_with_matching_names():
    d = pd.read_csv(bd.DEFAULT_OUT)
    sp = pd.read_csv(ROOT / "data" / "processed" / "species_clean.csv")
    assert list(d.columns) == bd.COLUMNS and len(d) == 45
    assert set(d.species_id) == set(sp.species_id) and d.common_name.tolist() == sp.sort_values("species_id").common_name.tolist()
    assert (d.ph_min < d.ph_max).all() and d.ph_min.between(3, 10).all() and d.ph_max.between(3, 10).all()
    assert set(d.source_label) == {"Project species dataset"} and d.authority_listed.str.len().min() > 0


def test_the_build_refuses_bad_input(tmp_path):
    src = ROOT / "reports" / "overnight" / "inputs" / "species_dataset_uploaded.csv.csv"
    if not src.is_file():
        pytest.skip("the uploaded dataset is not in this checkout (reports/ is not tracked)")
    raw = pd.read_csv(src, dtype=str, keep_default_na=False)
    bad = raw.copy()
    bad.loc[0, "min_soil_ph"] = "9"
    bad.to_csv(tmp_path / "a.csv", index=False)
    with pytest.raises(ValueError, match="min below max"):
        bd.build(tmp_path / "a.csv")
    bad = raw.copy()
    bad.loc[0, "common_name"] = "No Such Tree"
    bad.to_csv(tmp_path / "b.csv", index=False)
    with pytest.raises(ValueError, match="not in the species table"):
        bd.build(tmp_path / "b.csv")
    raw.iloc[:44].to_csv(tmp_path / "c.csv", index=False)
    with pytest.raises(ValueError, match="45 rows"):
        bd.build(tmp_path / "c.csv")
    assert bd.build(src).equals(pd.read_csv(bd.DEFAULT_OUT).astype(bd.build(src).dtypes.to_dict()))


def test_working_range_is_the_dataset_and_the_evidence_is_a_cross_reference_only():
    for sid in range(1, 46):
        lo, hi, kind = spe.working_range(sid)
        assert kind == "listed" and lo < hi
        ref = spe.dataset_reference(sid)
        assert ref["status"] == "sourced" and ref["source_label"] == "Project species dataset" and (ref["verdict_min"], ref["verdict_max"]) == (lo, hi)
    differs = [sid for sid in range(1, 46) if spe.dataset_reference(sid)["other_published"]]
    assert 0 < len(differs) < 45
    sid = differs[0]
    other = spe.dataset_reference(sid)["other_published"]
    ev = spe.reference(sid)
    assert (other["min"], other["max"]) == (ev["verdict_min"], ev["verdict_max"])
    assert spe.working_range(sid)[:2] != (other["min"], other["max"])                  # the other range is never the one used for a verdict
    assert spe.working_range(999) == (None, None, "none")


def test_no_ui_state_says_no_confirmed_range_any_more():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        allp = c.get("/species-ph-reference").json()["species"]
        assert len(allp) == 45 and all(v["status"] == "sourced" for v in allp.values())
        assert "agriculturist" not in str(c.get("/species-ph-reference").json()["tag"]).lower()
