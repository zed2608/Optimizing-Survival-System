"""Tests for the survival-rate threshold (pipeline/survival.py: checks_at_round, threshold_summary) - the defense panel's
signed Revision Form item "identify threshold survival of trees". The benchmark (85%, measured at the 1_year round) is
grounded in DENR's own stated National Greening Program survival-rate requirement (see the CFG comment in survival.py for
the citation); it is a provisional starting point, not a number this project measured, and is reported as such everywhere
it appears (GET /plans/{id}/survival, GET /plans/{id}/report, and the Known Limits text in api_v2.py).

Pure storage/pipeline layer only (uses a real temp SQLite file, no API/pandas/fastapi needed), same style as
test_survival.py and test_point_history.py - runs even in a sandbox with no network to install those. Run directly:
    python3 tests/test_survival_threshold.py
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import survival as sv  # noqa: E402


def add(db, plan_id, point_id, round_label, trees_total, trees_alive, trees_dead, cause=None, now=None):
    now = now or sv.now_utc()
    ev = sv.validate_event({"plan_id": plan_id, "point_id": point_id, "round_label": round_label, "status": "survived" if trees_alive else "dead",
                             "trees_total": trees_total, "trees_alive": trees_alive, "trees_dead": trees_dead, "cause": cause,
                             "observer": "Tester", "observed_at": sv.iso(now)}, trees_total_known=trees_total)
    return sv.add_event(db, ev)


def test_threshold_not_guessed_with_no_data():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "sv.db")
        out = sv.threshold_summary(db, "P1", {101: 10, 102: 8})
        assert out["points_at_round"] == 0
        assert out["measured_pct"] is None
        assert out["met"] is None
        assert out["round_label"] == "1_year" and out["threshold_pct"] == 85.0


def test_threshold_met_when_above_benchmark():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "sv.db")
        add(db, "P1", 101, "1_year", 10, 9, 1, cause="drought")
        out = sv.threshold_summary(db, "P1", {101: 10})
        assert out["points_at_round"] == 1
        assert out["measured_pct"] == 90.0
        assert out["met"] is True


def test_threshold_ignores_checks_at_other_rounds():
    # a point checked only at 3_month must not count toward the 1_year threshold calculation
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "sv.db")
        add(db, "P1", 101, "1_year", 10, 9, 1, cause="drought")
        add(db, "P1", 102, "3_month", 8, 8, 0)
        out = sv.threshold_summary(db, "P1", {101: 10, 102: 8})
        assert out["points_at_round"] == 1          # point 102's 3_month check is excluded
        assert out["trees_checked_at_round"] == 10   # only point 101's trees
        assert out["measured_pct"] == 90.0


def test_threshold_not_met_below_benchmark():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "sv.db")
        add(db, "P1", 101, "1_year", 10, 9, 1, cause="drought")
        add(db, "P1", 102, "1_year", 8, 4, 4, cause="typhoon_wind")
        out = sv.threshold_summary(db, "P1", {101: 10, 102: 8})
        assert out["points_at_round"] == 2
        assert out["trees_checked_at_round"] == 18 and out["trees_alive_at_round"] == 13
        assert out["measured_pct"] == 72.2
        assert out["met"] is False


def test_checks_at_round_keeps_only_the_latest_event_per_point():
    # a point re-checked twice at the same round: only the newest event should count
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "sv.db")
        add(db, "P1", 101, "1_year", 10, 10, 0)
        add(db, "P1", 101, "1_year", 10, 7, 3, cause="pest_disease")  # a correction / later recheck at the same round
        at_round = sv.checks_at_round(db, "P1", "1_year")
        assert len(at_round) == 1
        assert at_round[101]["trees_alive"] == 7


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


def main():
    passed, failed = 0, 0
    for t in TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except AssertionError:
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
            failed += 1
        except Exception:
            print(f"ERROR {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {len(TESTS)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
