"""Round 10a: the saved field checks get the status `planted` and the column trees_planted through a safe migration of an older database.
Run from the repo root: python -m pytest tests/test_field_migration.py"""
import sqlite3, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import field_verify as fv  # noqa: E402

OLD_SCHEMA = """
CREATE TABLE field_checks (
    check_id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('verified_plantable', 'not_plantable', 'needs_recheck')),
    reason TEXT CHECK (reason IS NULL OR reason IN ('paved', 'building', 'rock_or_ledge', 'creek_or_waterlogged', 'too_steep', 'existing_tree', 'owner_refused', 'other')),
    note TEXT,
    observer TEXT NOT NULL CHECK (length(trim(observer)) > 0),
    observed_at TEXT NOT NULL,
    gps_lat REAL, gps_lon REAL, gps_accuracy_m REAL,
    moved_lat REAL, moved_lon REAL,
    source TEXT NOT NULL CHECK (source IN ('dashboard', 'kit_import')),
    plan_id TEXT,
    created_at TEXT NOT NULL,
    import_key TEXT,
    CHECK (status <> 'not_plantable' OR reason IS NOT NULL)
);
CREATE INDEX ix_field_checks_point ON field_checks (point_id, check_id);
CREATE UNIQUE INDEX ux_field_checks_import_key ON field_checks (import_key) WHERE import_key IS NOT NULL;
CREATE TRIGGER field_checks_no_update BEFORE UPDATE ON field_checks BEGIN SELECT RAISE(ABORT, 'field_checks is append-only: add a new event instead'); END;
CREATE TRIGGER field_checks_no_delete BEFORE DELETE ON field_checks BEGIN SELECT RAISE(ABORT, 'field_checks is append-only: events are never deleted'); END;
"""


def old_db(path):
    con = sqlite3.connect(path)
    con.executescript(OLD_SCHEMA)
    rows = [(10, "verified_plantable", None, "ok", "Ana", "2026-10-01T01:00:00Z", None, "plan_a", "2026-10-01T01:00:00Z", None),
            (11, "not_plantable", "paved", "road", "Ben", "2026-10-02T01:00:00Z", None, None, "2026-10-02T01:00:00Z", "key-1"),
            (10, "needs_recheck", None, None, "Cy", "2026-10-03T01:00:00Z", None, "plan_a", "2026-10-03T01:00:00Z", "key-2")]
    for r in rows:
        con.execute("INSERT INTO field_checks (point_id, status, reason, note, observer, observed_at, moved_lat, source, plan_id, created_at, import_key) "
                    "VALUES (?,?,?,?,?,?,?,'dashboard',?,?,?)", r)
    con.commit()
    before = [tuple(x) for x in con.execute("SELECT check_id, point_id, status, reason, note, observer, observed_at, plan_id, created_at, import_key FROM field_checks ORDER BY check_id")]
    con.close()
    return before


def test_an_old_database_keeps_every_event_gets_a_backup_and_stays_append_only(tmp_path):
    db = tmp_path / "field" / "field_checks.db"
    db.parent.mkdir()
    before = old_db(db)
    con = fv.connect(db)
    after = [tuple(x) for x in con.execute("SELECT check_id, point_id, status, reason, note, observer, observed_at, plan_id, created_at, import_key FROM field_checks ORDER BY check_id")]
    assert after == before                                                                    # same events, same ids
    assert "trees_planted" in con.execute("SELECT sql FROM sqlite_master WHERE name='field_checks'").fetchone()[0]
    assert all(r[0] is None for r in con.execute("SELECT trees_planted FROM field_checks"))
    bak = Path(str(db) + ".before_planted.bak")
    assert bak.is_file()
    old = sqlite3.connect(bak)
    assert [tuple(x) for x in old.execute("SELECT check_id, point_id, status, reason, note, observer, observed_at, plan_id, created_at, import_key FROM field_checks ORDER BY check_id")] == before
    assert "trees_planted" not in old.execute("SELECT sql FROM sqlite_master WHERE name='field_checks'").fetchone()[0]
    old.close()
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("UPDATE field_checks SET note='x' WHERE check_id=1")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("DELETE FROM field_checks WHERE check_id=1")
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
    assert {"ix_field_checks_point", "ux_field_checks_import_key", "field_checks_no_update", "field_checks_no_delete"} <= names
    con.close()


def test_the_migration_runs_once_and_the_new_status_works_afterwards(tmp_path):
    db = tmp_path / "f.db"
    old_db(db)
    fv.connect(db).close()
    bak = Path(str(db) + ".before_planted.bak")
    first_bytes = bak.read_bytes()
    con = fv.connect(db)                                                                      # second start: nothing to migrate, the backup is not rewritten
    assert bak.read_bytes() == first_bytes and con.execute("SELECT COUNT(*) FROM field_checks").fetchone()[0] == 3
    con.close()
    ev = fv.validate_event({"point_id": 5, "status": "planted", "trees_planted": 12, "observer": "Ana", "plan_id": "plan_x_1"}, point_lonlat=(121.1, 14.7))
    assert ev["trees_planted"] == 12
    cid = fv.add_event(db, ev)
    assert cid == 4                                                                           # ids continue after the old events
    assert fv.current_status(db)[5]["trees_planted"] == 12 and fv.summary(fv.current_status(db), lambda p: None)["trees_planted_total"] == 12


def test_the_database_itself_refuses_a_planted_event_without_a_count_and_a_count_on_another_status(tmp_path):
    db = tmp_path / "f.db"
    con = fv.connect(db)
    base = ("INSERT INTO field_checks (point_id, status, observer, observed_at, source, created_at, trees_planted) VALUES (1, ?, 'Ana', 't', 'dashboard', 't', ?)")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(base, ("planted", None))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(base, ("verified_plantable", 3))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(base, ("planted", -1))
    con.execute(base, ("planted", 0))
    con.commit()
    con.close()


def test_validation_messages(tmp_path):
    ok = {"point_id": 5, "status": "planted", "observer": "Ana", "trees_planted": 3}
    ll = (121.1, 14.7)
    for bad, text in (({"trees_planted": None}, "required"), ({"trees_planted": 2.5}, "whole number"), ({"trees_planted": "many"}, "not a number"),
                      ({"trees_planted": -1}, "whole number"), ({"reason": "paved"}, "reason")):
        with pytest.raises(fv.FieldCheckError, match=text):
            fv.validate_event({**ok, **bad}, point_lonlat=ll)
    with pytest.raises(fv.FieldCheckError, match="only applies"):
        fv.validate_event({**ok, "status": "needs_recheck"}, point_lonlat=ll)
    assert fv.validate_event({**ok, "trees_planted": "7"}, point_lonlat=ll)["trees_planted"] == 7
