"""Round 9: make_pair_table.py uses the same squares and species as the scores (confirmed AND unconfirmed squares, never the excluded ones) and the same site texture.
It used to fail with "some scored pairs have no matching site or species row" once the scores included the unconfirmed squares (round 7a).
Run from the repo root: python -m pytest tests/test_pair_table_scored_squares.py"""
import subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT / "pipeline"))
import make_pair_table as mpt  # noqa: E402
import score_sites as ss  # noqa: E402

pytestmark = pytest.mark.skipif(not (PROCESSED / "species_clean.csv").exists(), reason="needs species_clean.csv")


def make_sites(n=36, lgu=True):
    rng = np.random.default_rng(3)
    status = np.array(["confirmed", "unconfirmed", "excluded"])[np.arange(n) % 3]
    s = pd.DataFrame({"point_id": np.arange(1, n + 1), "cell_row": np.arange(n) // 6, "cell_col": np.arange(n) % 6, "elev_m": rng.uniform(20, 400, n).round(1),
                      "slope_pct": rng.uniform(0, 40, n).round(1), "soil_texture_legacy": np.where(np.arange(n) % 2 == 0, "Clay", "Clay Loam"),
                      "zoning_status": status, "is_legal_zone": status == "confirmed", "utm_e": 300000 + np.arange(n) * 100.0, "utm_n": 1625000.0})
    if lgu:
        s["soil_texture_lgu"] = np.array(["Silt Loam", "Loam", "Sandy Loam", None], dtype=object)[np.arange(n) % 4]       # 4 and 3 are coprime: every texture occurs in every zoning status
    return s


def test_scored_sites_follow_the_scoring_rule():
    s = make_sites()
    got = mpt.scored_sites(s)
    assert set(got.zoning_status) == {"confirmed", "unconfirmed"} and len(got) == 24 and (got.point_id.isin(s[s.zoning_status != "excluded"].point_id)).all()
    old = s.drop(columns="zoning_status")                                          # an older grid without zoning_status: the legal squares
    assert len(mpt.scored_sites(old)) == int(old.is_legal_zone.sum())


def test_the_pair_table_covers_every_scored_pair_and_uses_the_scoring_texture():
    sp = pd.read_csv(PROCESSED / "species_clean.csv").head(6)
    sites = mpt.scored_sites(make_sites())
    sites["water_dist_m"] = np.nan
    scores = ss.score_pairs(sp, sites)[["point_id", "species_id", "s_rule"]]
    table = mpt.build_pair_table(sites, sp, scores, sites["water_dist_m"])
    assert len(table) == len(sites) * len(sp) == len(scores) and set(table.point_id) == set(sites.point_id)
    feats = mpt.feature_columns(table)
    assert "site_tex_silt_loam" in feats and "site_tex_sandy_loam" in feats and "site_tex_unknown" in feats            # the LGU textures, as in the scores
    assert table["site_tex_unknown"].sum() == int(sites.soil_texture_lgu.isna().sum()) * len(sp)
    legacy = mpt.build_pair_table(sites.drop(columns="soil_texture_lgu"), sp, scores, sites["water_dist_m"])
    assert "site_tex_silt_loam" not in legacy.columns and "site_tex_clay" in legacy.columns                          # without the LGU column: the legacy texture
    with pytest.raises(ValueError):                                                                                    # scores for squares the table does not have still fail loudly
        mpt.build_pair_table(sites[sites.zoning_status == "confirmed"], sp, scores, sites[sites.zoning_status == "confirmed"]["water_dist_m"])


def test_the_script_runs_on_a_grid_with_unconfirmed_squares(tmp_path):
    out = tmp_path / "proc"
    (out / "scores").mkdir(parents=True)
    sp = pd.read_csv(PROCESSED / "species_clean.csv").head(6)
    sp.to_csv(out / "species_clean.csv", index=False)
    sites = make_sites()
    sites.to_csv(out / "site_points_clean.csv", index=False)
    sc = mpt.scored_sites(sites).assign(water_dist_m=np.nan)
    ss.score_pairs(sp, sc)[["point_id", "species_id", "s_rule"]].to_csv(out / "scores" / "site_scores.csv", index=False)
    r = subprocess.run([sys.executable, str(ROOT / "pipeline" / "make_pair_table.py"), "--out", str(out), "--water", str(tmp_path / "no_such_water.shp")], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-600:]
    t = pd.read_csv(out / "scores" / "pair_table.csv.gz")
    assert len(t) == 24 * 6 and t.point_id.nunique() == 24 and "excluded" not in r.stdout
    assert "pairs: 144 (24 points x 6 species)" in r.stdout
