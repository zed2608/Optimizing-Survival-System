"""Tests for pipeline/survival.py: the post-planting survival-check storage, validation, append-only guarantee, replacement
linkage and the monitoring schedule. Pure storage/pipeline layer only (no API, no pandas/numpy): the /survival-checks endpoints
of api_v2.py are covered separately where the full data pipeline is available. Run from the repo root:
python -m pytest tests/test_survival.py"""
import sqlite3, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import survival as sv  # noqa: E402


@pytest.fixture
def db(tmp_path):
    return tmp_path / "survival.db"


def ev(**kw):
    base = {"plan_id": "PLAN1", "point_id": 101, "species_id": 7, "round_label": "3_month", "status": "survived",
            "trees_total": 10, "trees_alive": 10, "trees_dead": 0, "observer": "Ana"}
    base.update(kw)
    return base


def test_schema_created_and_append_only(db):
    con = sv.connect(db)
    con.close()
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    cur = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='survival_checks'").fetchone()
    assert cur is not None
    con.execute("INSERT INTO survival_checks (plan_id, point_id, round_label, status, trees_total, trees_alive, trees_dead, observer, observed_at, source, created_at) "
                "VALUES ('P', 1, '3_month', 'survived', 1, 1, 0, 'Ana', '2026-01-01T00:00:00+00:00', 'dashboard', '2026-01-01T00:00:00+00:00')")
    rid = con.execute("SELECT check_id FROM survival_checks").fetchone()["check_id"]
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE survival_checks SET status='dead' WHERE check_id=?", (rid,))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM survival_checks WHERE check_id=?", (rid,))
    con.close()


def test_valid_event_round_trips(db):
    cleaned = sv.validate_event(ev())
    check_id = sv.add_event(db, cleaned)
    h = sv.history(db, "PLAN1", 101)
    assert len(h) == 1 and h[0]["check_id"] == check_id and h[0]["status"] == "survived" and h[0]["trees_alive"] == 10


@pytest.mark.parametrize("bad,msg_has", [
    ({"plan_id": ""}, "plan_id"),
    ({"round_label": "2_month"}, "round_label"),
    ({"status": "ok"}, "status"),
    ({"trees_alive": 7, "trees_dead": 5, "trees_total": 10}, "cannot be more than"),
    ({"status": "dead", "trees_dead": 0}, "trees_dead is 0"),
    ({"status": "survived", "trees_alive": 0, "trees_dead": 0, "trees_total": 10}, "survived but trees_alive"),
    ({"status": "dead", "trees_dead": 2, "trees_alive": 8}, "cause is required"),
    ({"status": "dead", "trees_dead": 2, "trees_alive": 8, "cause": "flooding", "trees_total": 10}, None),  # valid: cause given, no error expected below
    ({"trees_dead": 0, "cause": "flooding"}, "only applies when trees_dead"),
    ({"observer": "  "}, "observer"),
])
def test_validation_errors(bad, msg_has):
    payload = ev(**bad)
    if msg_has is None:
        sv.validate_event(payload)  # should not raise
        return
    with pytest.raises(sv.SurvivalCheckError, match=msg_has):
        sv.validate_event(payload)


def test_trees_total_mismatch_needs_a_note(db):
    with pytest.raises(sv.SurvivalCheckError, match="does not match"):
        sv.validate_event(ev(trees_total=10, trees_alive=10), trees_total_known=12)
    # with a note explaining the discrepancy, it is accepted
    cleaned = sv.validate_event(ev(trees_total=10, trees_alive=10, note="one sapling from the plan was never actually in the ground"), trees_total_known=12)
    assert cleaned["trees_total"] == 10


def test_dead_tree_never_overwritten_replacement_is_a_new_event(db):
    dead_id = sv.add_event(db, sv.validate_event(ev(status="dead", trees_total=1, trees_alive=0, trees_dead=1, cause="drought", round_label="6_month")))
    replant_id = sv.add_event(db, sv.validate_event(ev(status="survived", trees_total=1, trees_alive=1, trees_dead=0, round_label="other",
                                                        replaces_check_id=dead_id, note="replanted after the dry spell")))
    h = sv.history(db, "PLAN1", 101)
    assert [r["check_id"] for r in h] == [dead_id, replant_id]
    assert h[0]["status"] == "dead" and h[1]["status"] == "survived" and h[1]["replaces_check_id"] == dead_id
    # the dead event is still there, untouched - nothing was overwritten
    assert h[0]["trees_dead"] == 1


def test_plan_summary_counts_latest_event_per_point_and_leaves_unchecked_points_alone(db):
    sv.add_event(db, sv.validate_event(ev(point_id=101, status="survived", trees_total=5, trees_alive=5)))
    sv.add_event(db, sv.validate_event(ev(point_id=102, status="dead", trees_total=3, trees_alive=0, trees_dead=3, cause="pest_disease")))
    # a later recheck of point 101 supersedes the first one for "current" purposes but both remain in history
    sv.add_event(db, sv.validate_event(ev(point_id=101, status="dead", trees_total=5, trees_alive=0, trees_dead=5, cause="typhoon_wind", round_label="6_month")))
    s = sv.plan_summary(db, "PLAN1", trees_by_point={101: 5, 102: 3, 103: 4})
    assert s["points_planned"] == 3
    assert s["points_checked"] == 2
    assert s["points_not_yet_checked"] == 1          # point 103 was never checked - not assumed survived or dead
    assert s["points_dead"] == 2 and s["points_survived"] == 0
    assert s["trees_dead_latest"] == 8
    assert len(sv.history(db, "PLAN1", 101)) == 2    # the first "survived" event for 101 is still in history, just not "current"


def test_due_schedule_states(db):
    planted = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = sv.due_schedule(planted, current={}, today=datetime(2026, 1, 1, tzinfo=timezone.utc))
    by_label = {r["round_label"]: r for r in rows}
    assert by_label["3_month"]["state"] == "upcoming"
    assert by_label["50_year"]["due_date"] == "2076-01-01"

    soon = datetime(2026, 3, 25, tzinfo=timezone.utc)        # within due_window_days of the 3-month mark (2026-04-01)
    rows2 = sv.due_schedule(planted, current={}, today=soon)
    assert {r["round_label"]: r for r in rows2}["3_month"]["state"] == "due"

    late = datetime(2026, 5, 1, tzinfo=timezone.utc)         # well past the 3-month mark with no check
    rows3 = sv.due_schedule(planted, current={}, today=late)
    assert {r["round_label"]: r for r in rows3}["3_month"]["state"] == "overdue"

    done_event = {"check_id": 1, "round_label": "3_month"}
    rows4 = sv.due_schedule(planted, current={"3_month": done_event}, today=late)
    row = {r["round_label"]: r for r in rows4}["3_month"]
    assert row["state"] == "done" and row["check_id"] == 1


def test_rounds_by_label_keeps_latest_check_id():
    events = [{"check_id": 1, "round_label": "3_month"}, {"check_id": 5, "round_label": "3_month"}, {"check_id": 2, "round_label": "6_month"}]
    out = sv.rounds_by_label(events)
    assert out["3_month"]["check_id"] == 5 and out["6_month"]["check_id"] == 2
