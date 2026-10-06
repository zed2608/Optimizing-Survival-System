"""Round 11: the soil layer digitized from the LGU soil map (pipeline/lgu_soil.py), its use in rebuild_site_grid.py / score_sites.py, the provisional flag, and the text changes
(Forest Reserve wording, Known limits). Run from the repo root: python -m pytest tests/test_lgu_soil.py"""
import json, shutil, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT / "pipeline"))
import lgu_soil as L  # noqa: E402
import score_sites as ss  # noqa: E402

LGU_COLS = ["soil_series_lgu", "soil_texture_lgu", "soil_purity", "soil_source"]


# ---- georeferencing on a synthetic image with a known transform -------------------------------------------------------------------------------
def synthetic_frame(xs, ys, w=1255, h=887):
    img = np.full((h, w, 3), 255, np.uint8)
    for x in xs:
        img[70:300, int(round(x)) - 1:int(round(x)) + 1] = (110, 120, 110)          # thin grey meridians in the clean band above the map
        img[:, int(round(x))] = np.where(img[:, int(round(x))] == 255, 255, img[:, int(round(x))])
    for y in ys:
        img[int(round(y)) - 1:int(round(y)) + 1, 70:200] = (110, 120, 110)           # thin grey parallels in the clean band left of the map
    return img


def test_graticule_lines_are_found_and_the_fit_recovers_the_known_transform():
    xs, ys = [410.4, 655.9, 901.5], [301.2, 575.8]
    img = synthetic_frame(xs, ys)
    fx, fy = L.find_graticule(img)
    assert len(fx) == 3 and len(fy) == 2
    assert max(abs(a - b) for a, b in zip(sorted(fx), xs)) < 1.0 and max(abs(a - b) for a, b in zip(sorted(fy), ys)) < 1.0
    g = L.georeference_graticule(img)
    assert g["max_m"] < 20                                                          # the pixel positions are rounded to whole pixels in the drawing
    # the known transform: the crossing of the 3rd meridian and the 1st parallel is 121 12' E, 14 42' N
    from pyproj import Transformer
    e, n = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True).transform(121 + 12 / 60, 14 + 42 / 60)
    got = L.apply_affine(g["M"], np.array([[xs[2], ys[0]]]))[0]
    assert np.hypot(got[0] - e, got[1] - n) < 25
    assert 5 < g["m_per_pixel"] < 30 or abs(g["m_per_pixel"] - 7170 / (xs[2] - xs[0]) / 2 * 2) < 3


def test_wrong_number_of_lines_is_an_error():
    with pytest.raises(ValueError):
        L.graticule_controls([100.0, 200.0], [50.0, 90.0])


def test_affine_fit_is_exact_for_an_affine_map():
    px = np.array([[0, 0], [100, 0], [0, 50], [100, 50], [30, 20]], float)
    m = np.array([[10.0, 0.5, 300000.0], [0.2, -10.0, 1625000.0]])
    xy = px @ m[:, :2].T + m[:, 2]
    assert np.allclose(L.fit_affine(px, xy), m)
    assert np.allclose(L.apply_affine(L.fit_affine(px, xy), px), xy)


# ---- legend colours, classification, filters -------------------------------------------------------------------------------------------------------
LEGEND = np.array([[151, 160, 197], [215, 96, 86], [190, 147, 170], [214, 144, 120], [133, 172, 128], [216, 190, 131], [131, 162, 190], [203, 214, 217]], float)


def test_the_legend_has_the_eight_series_and_the_textures_of_the_specification():
    assert [n for n, _ in L.SERIES] == ["Antipolo Clay", "Antipolo Clay Loam", "Binangonan Clay", "Marikina Clay Loam", "Marikina Loam", "Marikina Silt Loam", "Novaliches Clay Loam", "Quingua Sandy Loam"]
    assert L.SERIES_TEXTURE == {"Antipolo Clay": "Clay", "Antipolo Clay Loam": "Clay Loam", "Binangonan Clay": "Clay", "Marikina Clay Loam": "Clay Loam", "Marikina Loam": "Loam",
                                "Marikina Silt Loam": "Silt Loam", "Novaliches Clay Loam": "Clay Loam", "Quingua Sandy Loam": "Sandy Loam"}
    assert L.texture_of("Marikina Silt Loam") == "Silt Loam" and L.texture_of(None) is None and L.texture_of("Unknown") is None


def test_every_legend_colour_is_classified_to_its_own_series_and_other_things_are_ignored():
    img = np.full((60, 400, 3), 255, np.uint8)
    for k, c in enumerate(LEGEND):
        img[10:50, k * 40 + 4:k * 40 + 36] = c.astype(np.uint8)
    img[:, 330:340] = (0, 0, 0)                                                    # a black line
    img[0:8, 0:50] = (20, 60, 170)                                                 # a saturated blue river
    lab, dist = L.classify(img, LEGEND, 40.0)
    for k in range(8):
        assert (lab[20:40, k * 40 + 8:k * 40 + 32] == k).all(), k
    assert (lab[:, 330:340] == -1).all() and (lab[0:8, 0:50] == -1).all() and (lab[52:, :] == -1).all()      # black, river and paper are not soil
    lab2, _ = L.classify(img, LEGEND, 40.0, ignore_boxes=[(0, 0, 40, 60)])
    assert (lab2[:, :40] == -1).all() and (lab2[20:40, 48:72] == 1).all()


def test_legend_swatches_are_read_from_the_picture():
    img = np.full((300, 1200, 3), 255, np.uint8)
    cfg = dict(L.LGU_CFG)
    for k, y in enumerate(cfg["swatch_rows"]):
        img[int(round(y)) - 4:int(round(y)) + 5, cfg["swatch_x"][0] - 3:cfg["swatch_x"][1] + 3] = LEGEND[k].astype(np.uint8)
    assert np.allclose(L.legend_colours(img, cfg), LEGEND)


def test_the_majority_filter_removes_a_thin_line_but_keeps_the_area_edge():
    lab = np.zeros((60, 60), np.int16)
    lab[:, 30:] = 2
    lab[:, 10] = 5                                                                 # a one pixel line of another class in class 0
    lab[25, :] = -1                                                                # a one pixel gap (a black road)
    out = L.majority_filter(lab, 7, 0.25, None)
    assert (out[:, 3:25] == 0).all() and (out[:, 35:55] == 2).all()                # line and gap are gone inside the areas
    assert (out[:, 5:15] != 5).all()
    assert out[10, 27] == 0 and out[10, 33] == 2                                    # the edge stays where it was (within the window)


def test_thin_red_roads_are_not_soil_but_a_solid_red_area_is():
    c = dict(L.LGU_CFG)
    lab = np.full((200, 300), -1, np.int16)
    lab[20:180, 20:280] = 5                                                        # a yellow silt loam area
    lab[100, 20:280] = 1                                                           # a red road (1 pixel thin) through it
    lab[20:180, 150] = 3                                                           # an orange road
    lab[40:140, 200:260] = 1                                                       # a real solid red area (6,000 px)
    out, region = L.clean_labels(lab, None, c)
    assert region[100, 100] and not region[5, 5]
    assert (out[95:105, 30:140] == 5).all() and (out[50:130, 145:155] == 5).all()    # roads gone, the yellow area closes over them
    assert (out[60:120, 210:250] == 1).all()                                       # the solid red area stays


def test_a_pale_grey_class_needs_a_big_blob():
    c = dict(L.LGU_CFG)
    lab = np.full((200, 300), 5, np.int16)
    lab[10:14, 10:200] = 7                                                         # a thin pale line (frame or text)
    lab[100:160, 100:200] = 7                                                      # a big pale area (6,000 px)
    out, _ = L.clean_labels(lab, None, c)
    assert (out[10:14, 20:190] == 5).all() and (out[110:150, 110:190] == 7).all()


# ---- majority per square and the filling rule -------------------------------------------------------------------------------------------------------
M10 = np.array([[10.0, 0.0, 0.0], [0.0, -10.0, 5000.0]])                           # 10 m per pixel: a 100 m square is 10 x 10 pixels


def lattice(n_e=8, n_n=4, e0=105.0, n0=4505.0):
    rows = [(i * n_n + j + 1, e0 + 100 * i, n0 + 100 * j) for i in range(n_e) for j in range(n_n)]
    return pd.DataFrame(rows, columns=["point_id", "utm_e", "utm_n"])


def test_the_majority_class_purity_and_valid_share_of_every_square():
    lab = np.full((100, 100), -1, np.int16)                                        # 1000 m x 1000 m
    lab[:, :50] = 2                                                                # E < 500: class 2
    lab[:, 50:] = 5
    lab[40:, 90:] = -1                                                             # a hole: nothing valid in the south-east corner
    sites = lattice(8, 4, e0=105.0, n0=4505.0)
    sites.loc[len(sites)] = [99, 530.0, 4800.0]                                    # straddles the class boundary: 30% class 2, 70% class 5
    out = L.squares_majority(lab, M10, sites).set_index("point_id")
    assert out.loc[1, "cls"] == 2 and out.loc[1, "purity"] == 1.0 and out.loc[1, "valid_share"] == 1.0
    assert out.loc[4 * 7 + 1, "cls"] == 5
    assert out.loc[99, "cls"] == 5 and out.loc[99, "purity"] == pytest.approx(0.7, abs=0.11) and out.loc[99, "n_pixels"] > 50
    assert (out.loc[[4 * 7 + 1, 4 * 7 + 2], "valid_share"] == 1.0).all()


def test_a_square_without_valid_pixels_has_no_class_and_an_outside_square_too():
    lab = np.full((100, 100), -1, np.int16)
    lab[:, :30] = 3
    sites = pd.DataFrame({"point_id": [1, 2], "utm_e": [105.0, 705.0], "utm_n": [4505.0, 4505.0]})
    out = L.squares_majority(lab, M10, sites).set_index("point_id")
    assert out.loc[1, "cls"] == 3 and out.loc[2, "cls"] == -1 and out.loc[2, "valid_share"] == 0.0
    far = pd.DataFrame({"point_id": [3], "utm_e": [90000.0], "utm_n": [90000.0]})
    o3 = L.squares_majority(lab, M10, far)
    assert o3.cls.iloc[0] == -1 and o3.n_pixels.iloc[0] == 0


def test_the_filling_rule_nearest_valid_square_within_300_m_else_empty():
    sites = pd.DataFrame({"point_id": [1, 2, 3, 4], "utm_e": [0.0, 100.0, 250.0, 2000.0], "utm_n": [0.0, 0.0, 0.0, 0.0]})
    sq = pd.DataFrame({"point_id": [1, 2, 3, 4], "cls": [2, 5, 4, 1], "purity": [1.0, 0.9, 1.0, 1.0], "valid_share": [1.0, 0.1, 0.1, 0.1], "n_pixels": [60, 60, 60, 60], "n_valid": [60, 6, 6, 6]})
    out = L.fill_missing(sq, sites, 0.30, 300.0).set_index("point_id")
    assert out.loc[1, "soil_filled"] == 0 and out.loc[1, "cls"] == 2
    assert out.loc[2, "soil_filled"] == 1 and out.loc[2, "cls"] == 2                  # nearest valid square is 100 m away
    assert out.loc[3, "soil_filled"] == 1 and out.loc[3, "cls"] == 2                  # 250 m away: still within 300 m (the valid squares are only square 1)
    assert out.loc[4, "cls"] == -1 and out.loc[4, "soil_filled"] == 0                 # nothing within 300 m: left empty, never guessed
    t = L.to_table(out.reset_index())
    assert t.set_index("point_id").loc[1, "soil_series"] == "Binangonan Clay" and t.set_index("point_id").loc[1, "soil_texture"] == "Clay"
    assert pd.isna(t.set_index("point_id").loc[4, "soil_series"]) and pd.isna(t.set_index("point_id").loc[4, "soil_texture"])


# ---- score_sites: texture source, compatibility table, missing texture, flags -----------------------------------------------------------------------
def species_frame():
    names = ["Clay sp", "Clay Loam sp", "Loam sp", "Sandy Loam sp", "Sandy sp", "Silt Loam sp", "Any sp", "No list sp"]
    tex = ["Clay", "Clay Loam", "Loam", "Sandy Loam", "Sandy", "Silt Loam", None, None]
    return pd.DataFrame({"species_id": range(1, 9), "common_name": names, "elev_min_m": 0.0, "elev_max_m": 1000.0, "max_slope_pct": 60.0, "soil_textures": tex,
                         "soil_any_texture": [False] * 6 + [True, False], "waterlog_tol": "Medium"})


def sites_frame(lgu, legacy):
    n = len(lgu)
    return pd.DataFrame({"point_id": range(1, n + 1), "elev_m": 100.0, "slope_pct": 5.0, "soil_texture_legacy": legacy, "soil_texture_lgu": lgu, "is_legal_zone": True,
                         "zoning_status": "confirmed", "water_dist_m": np.nan})


def test_legacy_source_gives_exactly_the_old_exact_match_rule():
    sp = species_frame()
    si = sites_frame(["Silt Loam"] * 4, ["Clay", "Clay Loam", "Clay", None])
    out = ss.score_pairs(sp, si, soil_source="legacy")
    f = out.pivot(index="point_id", columns="species_id", values="f_soil")
    assert f.loc[1, 1] == 1.0 and f.loc[1, 2] == 0.25 and f.loc[2, 2] == 1.0 and f.loc[2, 1] == 0.25            # same word matches, anything else is a soft mismatch
    assert f.loc[1, 7] == 1.0                                                                                 # any texture is fine
    assert np.isnan(f.loc[4, 1]) and np.isnan(f.loc[4, 2]) and f.loc[4, 7] == 1.0                              # no texture: the soil term is not evaluated, never a mismatch
    assert not out.soil_lgu_used.any()


def test_lgu_source_uses_the_lgu_texture_and_the_compatibility_table():
    sp = species_frame()
    si = sites_frame(["Silt Loam", "Sandy Loam", "Loam", "Clay", None], ["Clay"] * 5)
    out = ss.score_pairs(sp, si, soil_source="lgu")
    f = out.pivot(index="point_id", columns="species_id", values="f_soil")
    assert f.loc[1, 3] == 1.0 and f.loc[1, 6] == 1.0 and f.loc[1, 1] == 0.25      # Silt Loam fits species that list Loam or Silt Loam, not Clay
    assert f.loc[2, 4] == 1.0 and f.loc[2, 5] == 1.0 and f.loc[2, 3] == 0.25      # Sandy Loam fits Sandy Loam or Sandy, not plain Loam
    assert f.loc[3, 3] == 1.0 and f.loc[3, 6] == 0.25                              # Loam keeps the old rule: only the word Loam
    assert f.loc[4, 1] == 1.0 and f.loc[4, 2] == 0.25
    assert f.loc[5].isna()[[1, 2, 3, 4, 5, 6]].all() and f.loc[5, 7] == 1.0        # no texture: not evaluated
    assert ss.SOIL_COMPAT["silt loam"] == {"silt loam", "loam"} and ss.SOIL_COMPAT["sandy loam"] == {"sandy loam", "sandy"}


def test_a_square_without_texture_is_never_scored_as_a_mismatch():
    """No texture = the soil term is not evaluated (as the old 'not set'): never the mismatch factor, never a flag. (The term then leaves the weighted mean, which can move S slightly either way.)"""
    sp = species_frame()
    miss = ss.score_pairs(sp, sites_frame([None], ["Clay"]), soil_source="lgu").set_index("species_id")
    mism = ss.score_pairs(sp, sites_frame(["Clay"], ["Clay"]), soil_source="lgu").set_index("species_id")
    for sid in range(1, 7):
        assert not bool(miss.loc[sid, "soil_unverified_mismatch"]) and not bool(miss.loc[sid, "soil_lgu_used"]) and not bool(miss.loc[sid, "known_soil"])
        assert miss.loc[sid, "s_rule"] >= mism.loc[sid, "s_rule"] - 1e-12              # never below the score of a mismatching square
    assert miss.loc[2, "s_rule"] > mism.loc[2, "s_rule"]                               # a Clay square does not fit a Clay Loam species: its mismatch lowers S, no texture does not


def test_lgu_changes_only_soil_related_results():
    sp = species_frame()
    si = sites_frame(["Silt Loam", "Loam", "Clay", "Sandy Loam", None], ["Clay", "Clay Loam", "Clay Loam", "Clay", "Clay"])
    a, b = ss.score_pairs(sp, si, soil_source="legacy"), ss.score_pairs(sp, si, soil_source="lgu")
    same = ["point_id", "species_id", "f_elevation", "f_slope", "f_wetness", "gate_fail_legal_zone", "gate_fail_elevation", "gate_fail_slope", "known_elevation", "known_slope", "known_wetness"]
    pd.testing.assert_frame_equal(a[same].reset_index(drop=True), b[same].reset_index(drop=True))
    assert (a.f_soil.fillna(-1) != b.f_soil.fillna(-1)).any()


def test_the_provisional_flag_goes_to_pairs_whose_soil_term_came_from_the_lgu_map():
    sp = species_frame()
    si = sites_frame(["Clay", None], ["Clay", "Clay"])
    sc = ss.score_pairs(sp, si, soil_source="lgu")
    bd = ss.build_breakdown(sc, sp, si, {})
    flags = {(int(p), int(s)): json.loads(x)["flags"] for p, s, x in zip(sc.point_id, sc.species_id, bd)}
    assert "soil_provisional" in flags[(1, 1)] and "soil_provisional" in flags[(1, 2)]            # evaluated from the map (a mismatch also carries soil_unverified_mismatch)
    assert "soil_unverified_mismatch" in flags[(1, 2)] and "soil_unverified_mismatch" not in flags[(1, 1)]
    assert flags[(2, 1)] == [] and flags[(1, 7)] == []                                         # no texture, or any texture fine: the map was not used
    leg = ss.score_pairs(sp, si, soil_source="legacy")
    assert all("soil_provisional" not in json.loads(x)["flags"] for x in ss.build_breakdown(leg, sp, si, {}))


def test_without_the_lgu_column_the_scorer_falls_back_to_legacy():
    sp = species_frame()
    si = sites_frame(["Clay"] * 2, ["Clay Loam", "Clay"]).drop(columns="soil_texture_lgu")
    assert ss.site_texture_column(si, "lgu") == ("soil_texture_legacy", "legacy")
    out = ss.score_pairs(sp, si)
    assert not out.soil_lgu_used.any()
    with pytest.raises(ValueError):
        ss.site_texture_column(si, "bogus")


# ---- the rebuild: legacy output unchanged -----------------------------------------------------------------------------------------------------------
@pytest.mark.skipif(not (ROOT / "backend" / "Working_Points.csv").exists() or not (PROCESSED / "site_points_clean.csv").exists(), reason="needs the grid inputs")
def test_legacy_rebuild_reproduces_the_current_grid_without_the_lgu_columns(tmp_path):
    out = tmp_path / "proc"
    out.mkdir()
    r = subprocess.run([sys.executable, str(ROOT / "pipeline" / "rebuild_site_grid.py"), "--input", str(ROOT / "backend" / "Working_Points.csv"), "--landuse", str(ROOT / "data" / "LandUses.shp"),
                        "--out", str(out), "--soil-source", "legacy"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-500:]
    new = pd.read_csv(out / "site_points_clean.csv")
    cur = pd.read_csv(PROCESSED / "site_points_clean.csv")
    assert not set(LGU_COLS) & set(new.columns)                                      # legacy writes nothing new
    cur = cur.drop(columns=[c for c in LGU_COLS if c in cur.columns])
    assert set(cur.columns) == set(new.columns)
    pd.testing.assert_frame_equal(new, cur[list(new.columns)])                       # every value is the same (the file on disk was written by an earlier version of the script, which put is_legal_zone before zoning_status)
    rep = (out / "grid_report.txt").read_text()
    assert "soil source: LGU" not in rep


@pytest.mark.skipif(not (ROOT / "backend" / "Working_Points.csv").exists() or not (PROCESSED / "site_soil_lgu.csv").exists(), reason="needs site_soil_lgu.csv (python pipeline/lgu_soil.py compute)")
def test_lgu_rebuild_adds_the_four_columns_and_keeps_the_legacy_ones(tmp_path):
    out = tmp_path / "proc"
    out.mkdir()
    shutil.copyfile(PROCESSED / "site_soil_lgu.csv", out / "site_soil_lgu.csv")
    r = subprocess.run([sys.executable, str(ROOT / "pipeline" / "rebuild_site_grid.py"), "--input", str(ROOT / "backend" / "Working_Points.csv"), "--landuse", str(ROOT / "data" / "LandUses.shp"),
                        "--out", str(out), "--soil-source", "lgu"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-500:]
    g = pd.read_csv(out / "site_points_clean.csv")
    assert set(LGU_COLS) <= set(g.columns) and {"soil_code", "soil_name_legacy", "soil_texture_legacy", "soil_mapping_status"} <= set(g.columns)
    has = g.soil_series_lgu.notna()
    assert has.any() and (g.loc[has, "soil_source"] == "LGU soil map (BSWM), digitized by us, provisional").all() and g.loc[~has, "soil_source"].isna().all()
    assert g.loc[has, "soil_texture_lgu"].notna().all() and g.loc[has, "soil_purity"].dropna().between(0, 1).all()      # a square filled from a neighbour with no valid pixel of its own has no purity
    t = pd.read_csv(out / "site_soil_lgu.csv").set_index("point_id")
    assert (g.set_index("point_id").soil_series_lgu.fillna("") == t.soil_series.fillna("")).all()
    bad = subprocess.run([sys.executable, str(ROOT / "pipeline" / "rebuild_site_grid.py"), "--input", str(ROOT / "backend" / "Working_Points.csv"), "--out", str(tmp_path / "empty"), "--soil-source", "lgu"],
                         capture_output=True, text=True, cwd=ROOT)
    assert bad.returncode != 0 and "lgu_soil.py" in (bad.stderr + bad.stdout)        # a missing digitized table is an error that says what to run, never a silent fallback


# ---- text changes ----------------------------------------------------------------------------------------------------------------------------------------
def test_the_forest_reserve_wording_in_the_code_and_the_kit():
    import field_kit as fk
    import run_plan as rp
    note = "Land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting."
    assert fk.FLAG_NOTES["zoning_unconfirmed"] == note
    assert rp.UNCONFIRMED_NOTE + "." == note
    assert fk.FLAG_NOTES["soil_provisional"] == "Soil from the LGU soil map, digitized by us: provisional."
    assert fk.flag_notes("zoning_unconfirmed;soil_provisional", None) == note + " Soil from the LGU soil map, digitized by us: provisional."
    assert "Zoning Named Zone: confirm" not in fk.flag_notes("zoning_unconfirmed", "Special Reserved Zone") and fk.flag_notes("zoning_unconfirmed", "Special Reserved Zone").startswith("Special Reserved Zone: confirm with the LGU")
    src = (ROOT / "pipeline" / "field_kit.py").read_text(encoding="utf-8")
    assert src.count("shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting there.") == 2           # both README sentences (points and blocks)
    assert "soil_provisional means the soil" in src


def test_the_forest_reserve_wording_in_the_dashboard_text():
    new = ROOT / "frontend" / "src" / "new"
    loc = (new / "LocationCard.jsx").read_text(encoding="utf-8")
    assert "Zoning: outside our zoning map (CLUP: Forest Reserve, Watershed)" in loc and "coordinate with MENRO and DENR before planting" in loc
    assert "Soil: ${soil.series} (${String(soil.texture ?? '').toLowerCase()}), LGU soil map, provisional" in loc
    assert "(CLUP: Forest Reserve, Watershed)" in (new / "PlanResult.jsx").read_text(encoding="utf-8")
    assert "Dotted ring = land outside our zoning map (CLUP: Forest Reserve, Watershed)" in (new / "PlanLegend.jsx").read_text(encoding="utf-8")
    assert "Forest Reserve (Watershed): coordinate with MENRO and DENR before planting." in (new / "UnzonedToggle.jsx").read_text(encoding="utf-8")
    assert "soil_provisional" in (new / "FlagList.jsx").read_text(encoding="utf-8")


def test_the_dry_season_is_stated_correctly_wherever_it_is_stated():
    """The LCCAP (page 11): Type I climate, relatively dry from December to May and wet the rest of the year. No file may say another set of months."""
    bad = ("november to april", "nov-apr", "nov to apr", "november - april", "november-april")
    for f in list((ROOT / "pipeline").glob("*.py")) + [ROOT / "api_v2.py"] + list((ROOT / "frontend" / "src" / "new").glob("*")) + list((ROOT / "docs").glob("*.md")) + [ROOT / "CLAUDE.md"]:
        if f.is_file():
            t = f.read_text(encoding="utf-8", errors="ignore").lower()
            assert not any(b in t for b in bad), f
    ds = (ROOT / "docs" / "DATA_SOURCES.md").read_text(encoding="utf-8")
    assert "relatively dry season from December to May" in ds and "LCCAP" in ds


# ---- the data and the API (run on the regenerated data) -----------------------------------------------------------------------------------------------
def _has_lgu_data():
    p = PROCESSED / "site_points_clean.csv"
    return p.exists() and "soil_texture_lgu" in pd.read_csv(p, nrows=2).columns


needs_lgu = pytest.mark.skipif(not _has_lgu_data(), reason="the data was not rebuilt with the LGU soil layer yet")


@needs_lgu
def test_the_digitized_table_and_the_grid_agree_and_every_texture_is_in_the_table():
    g = pd.read_csv(PROCESSED / "site_points_clean.csv")
    t = pd.read_csv(PROCESSED / "site_soil_lgu.csv")
    assert len(t) == len(g) == t.point_id.nunique() and set(t.soil_series.dropna()) <= set(L.SERIES_TEXTURE)
    assert (t.dropna(subset=["soil_series"]).apply(lambda r: L.SERIES_TEXTURE[r.soil_series] == r.soil_texture, axis=1)).all()
    assert t.purity.dropna().between(0, 1).all() and t.valid_share.between(0, 1).all()
    assert set(t.soil_filled.unique()) <= {0, 1}


@needs_lgu
def test_the_scores_carry_the_flag_and_respect_the_missing_texture():
    import sqlite3
    g = pd.read_csv(PROCESSED / "site_points_clean.csv")
    con = sqlite3.connect(PROCESSED / "scores" / "site_scores.db")
    pid_with = int(g[g.soil_texture_lgu.notna() & g.is_legal_zone].point_id.iloc[0])
    pid_without = int(g[g.soil_texture_lgu.isna() & (g.zoning_status != "excluded")].point_id.iloc[0])
    f1 = [json.loads(r[0])["flags"] for r in con.execute("SELECT breakdown_json FROM site_scores WHERE point_id=?", (pid_with,))]
    f2 = [json.loads(r[0])["flags"] for r in con.execute("SELECT breakdown_json FROM site_scores WHERE point_id=?", (pid_without,))]
    assert any("soil_provisional" in f for f in f1) and not any("soil_provisional" in f for f in f2)
    assert not any("soil_unverified_mismatch" in f for f in f2)                       # no texture: no mismatch
    con.close()


# ---- the API on the regenerated data -----------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import api_v2
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


def pick(data, with_series=True, unzoned=False):
    p = data.all_points
    m = (p.soil_series_lgu.notna() if with_series else p.soil_series_lgu.isna()) & (p.zoning_status != "excluded")
    if unzoned:
        m &= p.zoning_status == "unconfirmed"
    return p[m].iloc[0]


@needs_lgu
def test_rank_gives_the_soil_series_texture_source_and_purity_and_flags_the_items(client, data):
    pt = pick(data, True)
    j = client.get("/rank", params={"purpose": "urban", "lat": float(pt.lat), "lon": float(pt.lon), "limit": 45}).json()
    s = j["point"]["soil"]
    assert s["series"] == pt.soil_series_lgu and s["texture"] == pt.soil_texture_lgu and s["source"] == "LGU soil map (BSWM), digitized by us, provisional"
    assert s["purity"] == pytest.approx(float(pt.soil_purity)) and s["status"] == "provisional" and s["note"] == "Soil from the LGU soil map, digitized by us: provisional"
    assert s["legacy_texture"] in ("Clay", "Clay Loam", None)
    assert any("soil_provisional" in it["flags"] for it in j["ranking"])
    assert "LGU soil map" in j["point"]["site_inputs_source"]


@needs_lgu
def test_a_square_outside_the_soil_map_says_data_unavailable_and_has_no_soil_flag(client, data):
    pt = pick(data, False)
    j = client.get("/rank", params={"purpose": "urban", "lat": float(pt.lat), "lon": float(pt.lon), "limit": 45}).json()
    s = j["point"]["soil"]
    assert s["series"] is None and s["texture"] is None and s["source"] is None and s["status"] == "Data Unavailable" and "outside the LGU soil map" in s["note"]
    assert not any("soil_provisional" in it["flags"] or "soil_unverified_mismatch" in it["flags"] for it in j["ranking"])


@needs_lgu
def test_the_point_search_carries_the_soil_too(client, data):
    pt = pick(data, True)
    r = client.get("/search/point", params={"q": str(int(pt.point_id))}).json()
    assert r["soil"]["series"] == pt.soil_series_lgu and r["soil"]["source"] == "LGU soil map (BSWM), digitized by us, provisional"


@needs_lgu
def test_known_limits_describe_the_lgu_soil_and_the_forest_reserve(client):
    lim = " ".join(client.get("/rank/municipal", params={"purpose": "urban"}).json()["limits"])
    assert "Soil comes from the LGU soil map (Bureau of Soils and Water Management), digitized by us" in lim and "not yet verified by the agriculturist" in lim
    assert "legacy" in lim and "outside that map" in lim
    assert "Forest Reserve (Watershed)" in lim and "Sangguniang Bayan" in lim and "MENRO and DENR" in lim


@needs_lgu
def test_the_unzoned_notes_use_the_forest_reserve_wording(client, data):
    pt = pick(data, True, unzoned=True) if ((data.all_points.zoning_status == "unconfirmed") & data.all_points.soil_series_lgu.notna()).any() else pick(data, False, unzoned=True)
    j = client.get("/rank", params={"purpose": "urban", "lat": float(pt.lat), "lon": float(pt.lon), "limit": 3}).json()
    assert j["point"]["zoning_note"] == "Land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting"
    sp = client.get("/search/point", params={"q": str(int(pt.point_id))}).json()
    assert "Forest Reserve, Watershed" in sp["note"]
    ctx = client.get("/grid", params={"purpose": "urban"}).json()
    assert "Forest Reserve, Watershed" in ctx["zoning"]["note"]
