"""Design v2 (Task C): the Field Pack of a spaced kit: every tree from trees.csv, the ground of each block, the selected area, checks against a changed or missing file."""
import json, shutil, sys
from pathlib import Path
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT / "pipeline"))
import field_kit as fk  # noqa: E402
import field_pack as fp  # noqa: E402
import run_plan as rp  # noqa: E402


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    out = tmp_path_factory.mktemp("packsp")
    ctx = rp.load_context(PROCESSED, include_unzoned=True)
    plan, summary = rp.make_plan(ctx, "planting", 120, seed=5, layout_mode="blocks")
    c = (float(plan.lon.iloc[0]), float(plan.lat.iloc[0]))                                       # around the first planned square
    d = 0.0012
    summary["request"] = {"polygon": {"type": "Polygon", "coordinates": [[[c[0] - d, c[1] - d], [c[0] + d, c[1] - d], [c[0] + d, c[1] + d], [c[0] - d, c[1] + d], [c[0] - d, c[1] - d]]]}}
    f, sj = rp.write_plan(out, "planting", plan, summary, "20270103_000000")
    old = fk.CFG["point_layout"]
    fk.CFG["point_layout"] = "spaced"
    try:
        r = fk.make_kit(f, out / "kits", pdf=False, data_dir=PROCESSED)
    finally:
        fk.CFG["point_layout"] = old
    return r["kit_dir"]


def test_the_pack_holds_every_tree_the_ground_and_the_selected_area(kit):
    text, manifest = fp.read_kit(kit)
    pack = fp.build_pack(text, manifest)
    assert pack["area"] and "plantable" in pack["area"] and "selected" in pack["area"]
    assert pack["blocks"] and all(b["n"] > 0 for b in pack["blocks"])          # a block with no ground for any tree is not in the pack (pack["skipped_blocks"] names it)
    for b in pack["blocks"]:
        assert b["layout"] == "spaced" and b["n"] == len(b["trees"]) and [t[0] for t in b["trees"]] == list(range(1, len(b["trees"]) + 1))
        assert b["spacing_m"] > 0 and b["areas"] and b["region_m"] and b["fits"] in (True, False) and b["requested"] >= b["n"]
        assert all(0 <= t[3] <= 100 and 0 <= t[4] <= 100 for t in b["trees"])
    page = fp.render_page(pack)
    assert '"layout":"spaced"' in page and "/*__" not in page and len(page) < 700_000


def test_a_changed_trees_file_is_refused(kit, tmp_path):
    k2 = tmp_path / "k"
    shutil.copytree(kit, k2)
    t = (k2 / "trees.csv").read_text(encoding="utf-8")
    (k2 / "trees.csv").write_text(t.replace("\n", "\n", 1) + "\n", encoding="utf-8")
    with pytest.raises(fp.PackError, match="trees.csv does not match manifest.json"):
        fp.read_kit(k2)


def test_a_spaced_kit_without_trees_csv_is_refused(kit, tmp_path):
    k2 = tmp_path / "k"
    shutil.copytree(kit, k2)
    (k2 / "trees.csv").unlink()
    text, manifest = fp.read_kit(k2)
    with pytest.raises(fp.PackError, match="trees.csv is missing"):
        fp.build_pack(text, manifest)
