"""Tests for the pure helpers behind GET /points/{point_id}/history (api_v2.py, added to answer: "when a planted or
not-plantable point is clicked on the map, show who planted it and its full survival history" - not just a point that
happens to belong to the plan presently open).

Pure storage/pipeline layer only, like test_survival.py and test_field_verify.py: no API, no pandas/numpy, so this runs even
in an environment with no network access to install fastapi (this repo's sandbox is exactly such an environment). Written
as plain asserts rather than pytest fixtures/parametrize, because pytest itself is not installable here either - this file
is run directly:
    python3 tests/test_point_history.py
and prints PASS/FAIL per test plus a summary; it exits 1 on any failure so it still works as a CI gate once pytest is back.
"""
import sys
import traceback
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

# field_verify.py imports field_kit (for plan check-codes), which in turn imports kit_spaced -> point_layout -> shapely.
# shapely is a native geo dependency this sandbox cannot install (no network); planted_plan_ids() never touches field_kit,
# so a stub with the three attributes field_verify.py actually references is enough to import the real module and test the
# real function, without needing the heavy geo stack installed. This stub is test-only scaffolding, never shipped code.
if "field_kit" not in sys.modules:
    stub = types.ModuleType("field_kit")
    stub.make_codes = lambda *a, **k: (_ for _ in ()).throw(NotImplementedError("stub: not needed by the functions under test"))
    stub.make_refs = stub.make_codes
    stub.check_code = stub.make_codes
    sys.modules["field_kit"] = stub

import field_verify as fv  # noqa: E402
import survival as sv  # noqa: E402


def fc_event(**kw):
    """A minimal field_checks row, shaped like fv.history()'s _row() output (only the keys planted_plan_ids() reads)."""
    base = {"check_id": 1, "point_id": 101, "status": "verified_plantable", "plan_id": None}
    base.update(kw)
    return base


def test_planted_plan_ids_finds_only_planted_events_with_a_plan():
    history = [
        fc_event(check_id=1, status="verified_plantable", plan_id=None),
        fc_event(check_id=2, status="planted", plan_id="PLAN-A", trees_planted=5),
        fc_event(check_id=3, status="not_plantable", plan_id=None, reason="paved"),
    ]
    assert fv.planted_plan_ids(history) == ["PLAN-A"]


def test_planted_plan_ids_is_empty_when_never_planted():
    history = [fc_event(check_id=1, status="verified_plantable", plan_id=None), fc_event(check_id=2, status="needs_recheck", plan_id=None)]
    assert fv.planted_plan_ids(history) == []


def test_planted_plan_ids_lists_every_plan_that_ever_planted_it():
    # the replant-after-death scenario the panel specifically asked for (round 22 / signed form item 1): a point planted
    # under one plan, later replanted under a different plan after the first planting died, must show BOTH plans - no
    # planting is dropped just because a later field-check event moved the point's current status on.
    history = [
        fc_event(check_id=1, status="planted", plan_id="PLAN-OLD", trees_planted=10),
        fc_event(check_id=2, status="not_plantable", plan_id=None, reason="existing_tree"),  # the old planting died, marked unusable in between
        fc_event(check_id=3, status="planted", plan_id="PLAN-NEW", trees_planted=8),
    ]
    assert fv.planted_plan_ids(history) == ["PLAN-NEW", "PLAN-OLD"]  # sorted, not call-order - both present, neither dropped


def test_planted_plan_ids_ignores_a_planted_event_with_no_plan_id():
    # defensive: the schema requires plan_id for a 'planted' event, but the helper must not crash or silently invent one
    # if it is ever missing (golden rule 1), and must not count it as a planting.
    history = [fc_event(check_id=1, status="planted", plan_id=None, trees_planted=3)]
    assert fv.planted_plan_ids(history) == []


def planting(**kw):
    base = {"plan_id": "P", "planted_observed_at": "2026-01-01T00:00:00+00:00"}
    base.update(kw)
    return base


def test_order_plantings_sorts_oldest_first():
    plantings = [planting(plan_id="NEW", planted_observed_at="2026-06-01T00:00:00+00:00"), planting(plan_id="OLD", planted_observed_at="2026-01-01T00:00:00+00:00")]
    ordered = sv.order_plantings(plantings)
    assert [p["plan_id"] for p in ordered] == ["OLD", "NEW"]


def test_order_plantings_never_crashes_on_a_missing_date():
    # never invent a date (golden rule 1): a missing planted_observed_at sorts first (empty string) rather than raising.
    plantings = [planting(plan_id="HAS_DATE", planted_observed_at="2026-01-01T00:00:00+00:00"), planting(plan_id="NO_DATE", planted_observed_at=None)]
    ordered = sv.order_plantings(plantings)
    assert [p["plan_id"] for p in ordered] == ["NO_DATE", "HAS_DATE"]


def test_due_schedule_and_rounds_by_label_still_agree_with_an_empty_history():
    # the point-history endpoint calls sv.due_schedule(planted_at, sv.rounds_by_label(events)) for every planting, including
    # one with zero survival checks yet (just planted, nothing logged) - must not crash, and every round must show as not done.
    schedule = sv.due_schedule("2026-01-01T00:00:00+00:00", sv.rounds_by_label([]))
    assert all(r["state"] != "done" for r in schedule)
    assert {r["round_label"] for r in schedule} >= {"3_month", "6_month", "1_year"}


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
