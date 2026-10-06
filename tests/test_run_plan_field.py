"""Tests for two small follow-ups of saved field verification:
 1. the field kit README explains how to bring a filled point-list.csv back;
 2. the command-line plan tool (pipeline/run_plan.py) leaves out not_plantable points and reports how many, as POST /plan-event does.
Run from the repo root: python -m pytest tests/test_run_plan_field.py"""
import itertools, json, shutil, sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
SCORES = PROCESSED / "scores" / "site_scores.db"
pytestmark = pytest.mark.skipif(not SCORES.exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT / "pipeline"))
import field_kit as fk  # noqa: E402
import field_verify as fv  # noqa: E402
import matching as mt  # noqa: E402
import run_plan as rp  # noqa: E402

ARGS = ["--purpose", "urban", "--n-saplings", "40", "--seed", "1", "--no-include-unzoned"]      # these tests pin the plan made on confirmed legal-zone squares only


@pytest.fixture(scope="module")
def ctx():
    return mt.load_context(str(PROCESSED))


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys):
    """Run the command-line tool on a temp copy of the small inputs. Returns run(extra_args) -> (plan DataFrame, summary dict, printed text)."""
    out = tmp_path / "processed"
    out.mkdir()
    for n in ("site_points_clean.csv", "species_clean.csv", "purpose_scores.csv", "species_sources.csv"):
        shutil.copy(PROCESSED / n, out / n)
    db = tmp_path / "field" / "field_checks.db"
    counter, written = itertools.count(), []
    orig = rp.write_plan

    def write_plan(out_dir, purpose, plan, summary, stamp=None):
        f, sj = orig(out_dir, purpose, plan, summary, f"t{next(counter)}")      # a unique name per run (two runs in one second must not collide)
        written.append((f, sj))
        return f, sj

    monkeypatch.setattr(rp, "write_plan", write_plan)

    def run(*extra, field_db=db):
        capsys.readouterr()
        rp.main(["--out", str(out), "--scores", str(SCORES), "--field-db", str(field_db), *ARGS, *extra])
        f, sj = written[-1]
        return pd.read_csv(f), json.loads(sj.read_text(encoding="utf-8")), capsys.readouterr().out

    run.db = db
    return run


def mark_not_plantable(ctx, db, point_id, reason="paved"):
    r = ctx.sites[ctx.sites.point_id == point_id].iloc[0]
    ev = fv.validate_event({"point_id": point_id, "status": "not_plantable", "reason": reason, "observer": "Ana"}, point_lonlat=(float(r.lon), float(r.lat)))
    fv.add_event(db, ev)


# ---- 1. the kit README ----------------------------------------------------------------------------------------------------------
def test_a_built_kit_readme_explains_how_to_bring_the_filled_csv_back(ctx, tmp_path):
    plan, summary = rp.make_plan(ctx, "urban", 30, seed=1)
    f, _ = rp.write_plan(tmp_path, "urban", plan, summary, "kit1")
    made = fk.make_kit(f, tmp_path / "kits", pdf=False, data_dir=PROCESSED, built_on="2026-10-05")
    text = (made["kit_dir"] / "README.txt").read_text(encoding="utf-8") if (made["kit_dir"] / "README.txt").exists() else next(made["kit_dir"].glob("README*")).read_text(encoding="utf-8")
    assert "BRINGING THE RESULTS BACK" in text
    flat = " ".join(text.split())                                                # the README wraps lines
    for must in ("status column", "planted", "not plantable", "moved_lat", "moved_lon", "Import field checks (CSV)", "plan id and the check code",
                 "Importing the same file twice adds nothing"):
        assert must in flat, must
    assert all(w in text for w in fv.REASONS)                                    # every reason word the import accepts is named


# ---- 2. the command-line plan ---------------------------------------------------------------------------------------------------
def test_with_no_checks_the_plan_is_identical_to_before(ctx, cli):
    plan, summary, printed = cli()
    before, before_summary = rp.make_plan(ctx, "urban", 40, seed=1)            # what the tool produced before this change
    assert plan[["point_id", "species_id"]].to_numpy().tolist() == before[["point_id", "species_id"]].to_numpy().tolist()
    assert plan.W.round(9).tolist() == before.W.round(9).tolist()
    assert {k: v for k, v in summary.items() if k not in ("field_checks", "plan_file", "timestamp")} == json.loads(json.dumps(before_summary))
    assert summary["field_checks"]["excluded_points"] == 0 and "0 not-plantable" in printed
    assert not cli.db.exists(), "a missing field database must not be created by planning"


def test_a_not_plantable_point_is_left_out_and_counted(ctx, cli):
    plan, _, _ = cli()
    pid = int(plan.point_id.iloc[0])
    mark_not_plantable(ctx, cli.db, pid)
    plan2, summary2, printed = cli()
    assert pid not in set(plan2.point_id) and len(plan2) == len(plan)
    assert summary2["field_checks"] == {"exclude_not_plantable": True, "excluded_points": 1,
                                        "note": "Points whose latest field check is not_plantable were left out of this plan."}
    assert "1 not-plantable" in printed
    assert summary2["area"]["legal_points_in_area"] == len(ctx.sites) - 1


def test_the_count_only_covers_the_chosen_area_and_clearing_brings_the_point_back(ctx, cli):
    plan, _, _ = cli()
    pid = int(plan.point_id.iloc[0])
    zone = ctx.sites.set_index("point_id").zone_desc[pid]
    other = next(z for z in ctx.sites.zone_desc.dropna().unique() if z != zone)
    mark_not_plantable(ctx, cli.db, pid)
    assert cli("--zone", zone)[1]["field_checks"]["excluded_points"] == 1
    assert cli("--zone", other)[1]["field_checks"]["excluded_points"] == 0
    r = ctx.sites[ctx.sites.point_id == pid].iloc[0]
    clear = fv.validate_event({"point_id": pid, "status": "needs_recheck", "note": "it was only a puddle", "observer": "Ben"}, point_lonlat=(float(r.lon), float(r.lat)),
                              previous_status="not_plantable")
    fv.add_event(cli.db, clear)
    assert cli()[1]["field_checks"]["excluded_points"] == 0
