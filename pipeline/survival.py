#!/usr/bin/env python3
"""
survival.py - post-planting survival monitoring: periodic re-checks of what was actually planted, over years, so the system
becomes the source of San Mateo's survival-rate data going forward (defense panel, round 22: "the biggest ask").

Library module (used by api_v2.py; no web code here). Storage is a SQLite file, data/field/survival_checks.db, with ONE table
of APPEND-ONLY events (the database itself refuses UPDATE and DELETE, same pattern as field_verify.py's field_checks). A dead
tree is never erased or overwritten: it stays in history as its own event, and a later replacement is a SEPARATE new event that
may point back to it (replaces_check_id). Nothing here reads or writes S, P, W or any score.

    round_label   3_month | 6_month | 1_year | 5_year | 10_year | 50_year | other   (other = an opportunistic check not tied to
                  a scheduled round; the 10_year and 50_year rounds are the panel's own forward-looking horizons - a placeholder
                  until real data exists that far out, never guessed)
    status        survived | dead | not_found   (not_found = the stake/tree could not be located this visit: distinct from
                  dead, because "we don't know" is not the same fact as "it died" - golden rule 1, never invent data)
    cause         required when trees_dead > 0: drought | pest_disease | flooding | typhoon_wind | vandalism | construction |
                  unknown | other

due_schedule() computes which monitoring rounds are due, upcoming or overdue from the planted date and today - a schedule the
dashboard and a report can show, not a live reminder/notification system (out of scope for this iteration; documented as such).
Everything here is provisional until the agriculturist and MENRO confirm the monitoring cadence and the cause-of-death list.
"""
import math, re, sqlite3, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# =====================================================================================================================
# CONFIG - every tunable number lives here. PROVISIONAL.
# =====================================================================================================================
CFG = {
    "default_db": "data/field/survival_checks.db",
    "note_max_chars": 500,
    "observer_max_chars": 80,
    "accuracy_max_m": 1000.0,
    "future_tolerance_hours": 24,
    "trees_max": 100000,                                     # largest trees_total one event may report
    # the monitoring rounds the panel asked for (3 months and 6 months were floated explicitly; 1 and 5 years follow from
    # "survived at 1 year / survived at 5 years"; 10 and 50 years are the panel's own "what happens to mature/old trees"
    # question, kept as named future rounds rather than silently dropped).
    "rounds": [
        {"label": "3_month", "months": 3},
        {"label": "6_month", "months": 6},
        {"label": "1_year", "months": 12},
        {"label": "5_year", "months": 60},
        {"label": "10_year", "months": 120},
        {"label": "50_year", "months": 600},
    ],
    "due_window_days": 30,                                   # a round counts as "due" from this many days before its date
    "overdue_grace_days": 14,                                # ... and "overdue" once this many days have passed it
    # The defense panel's "identify threshold survival of trees" ask (signed Revision Form, item 1). 85% is the figure DENR
    # itself states as the survival-rate requirement for the National Greening Program - field officers "are required to
    # meet the 85-percent survival rate of planted tree seedlings" (philstar.com, "Underperforming environ officers face
    # ax", 7 Nov 2019: https://www.philstar.com/science-and-environment/2019/11/07/1966513/underperforming-environ-officers-face-ax).
    # That source does not pin the figure to a specific monitoring age; "1_year" is chosen here because it matches the
    # panel's own wording ("survived at 1 year") and is the conventional point in reforestation practice to call a planting
    # "established" (past first-dry-season transplant shock, before longer-horizon mortality). This is a PROVISIONAL,
    # literature-grounded starting point, not a number this project measured or that the agriculturist has confirmed for
    # San Mateo's species and sites - said so wherever it is reported (see threshold_summary()).
    "success_threshold_pct": 85.0,
    "success_threshold_round": "1_year",
}
# =====================================================================================================================

ROUND_LABELS = tuple(r["label"] for r in CFG["rounds"]) + ("other",)
ROUND_MONTHS = {r["label"]: r["months"] for r in CFG["rounds"]}
STATUSES = ("survived", "dead", "not_found")
CAUSES = ("drought", "pest_disease", "flooding", "typhoon_wind", "vandalism", "construction", "unknown", "other")
SOURCES = ("dashboard", "kit_import")


def table_sql(name="survival_checks"):
    return f"""
CREATE TABLE IF NOT EXISTS {name} (
    check_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL,
    point_id INTEGER NOT NULL,
    species_id INTEGER,
    round_label TEXT NOT NULL CHECK (round_label IN {ROUND_LABELS}),
    status TEXT NOT NULL CHECK (status IN {STATUSES}),
    trees_total INTEGER NOT NULL CHECK (trees_total >= 0),
    trees_alive INTEGER NOT NULL CHECK (trees_alive >= 0),
    trees_dead INTEGER NOT NULL CHECK (trees_dead >= 0),
    cause TEXT CHECK (cause IS NULL OR cause IN {CAUSES}),
    replaces_check_id INTEGER,
    note TEXT,
    observer TEXT NOT NULL CHECK (length(trim(observer)) > 0),
    observed_at TEXT NOT NULL,
    gps_lat REAL, gps_lon REAL, gps_accuracy_m REAL,
    source TEXT NOT NULL CHECK (source IN {SOURCES}),
    created_at TEXT NOT NULL,
    CHECK (trees_alive + trees_dead <= trees_total),
    CHECK (trees_dead = 0 OR cause IS NOT NULL)
);
"""


EXTRAS = """
CREATE INDEX IF NOT EXISTS ix_survival_checks_point ON survival_checks (plan_id, point_id, check_id);
CREATE TRIGGER IF NOT EXISTS survival_checks_no_update BEFORE UPDATE ON survival_checks BEGIN SELECT RAISE(ABORT, 'survival_checks is append-only: add a new event instead'); END;
CREATE TRIGGER IF NOT EXISTS survival_checks_no_delete BEFORE DELETE ON survival_checks BEGIN SELECT RAISE(ABORT, 'survival_checks is append-only: a dead tree stays in history, it is never deleted'); END;
"""
SCHEMA = table_sql() + EXTRAS
EVENT_COLUMNS = ["check_id", "plan_id", "point_id", "species_id", "round_label", "status", "trees_total", "trees_alive", "trees_dead",
                  "cause", "replaces_check_id", "note", "observer", "observed_at", "gps_lat", "gps_lon", "gps_accuracy_m", "source", "created_at"]


class SurvivalCheckError(ValueError):
    """A survival check that cannot be saved; the message says why in plain words."""


# ---------------------------------------------------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------------------------------------------------
def connect(db_path):
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_time(value, now=None):
    now = now or now_utc()
    if value is None or str(value).strip() == "":
        return now
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        raise SurvivalCheckError(f"observed_at '{value}' is not a date/time (use for example 2026-10-05 or 2026-10-05T14:30)")
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if dt > now + timedelta(hours=CFG["future_tolerance_hours"]):
        raise SurvivalCheckError(f"observed_at {iso(dt)} lies in the future")
    return dt


def add_months(dt, months):
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = min(dt.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return dt.replace(year=y, month=m, day=d)


def _num(v, name):
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise SurvivalCheckError(f"{name} '{v}' is not a number")
    if not math.isfinite(x):
        raise SurvivalCheckError(f"{name} must be a finite number")
    return x


def validate_event(raw, *, trees_total_known=None, now=None):
    """
    Clean and check one event. raw: dict with plan_id, point_id, species_id, round_label, status, trees_total, trees_alive,
    trees_dead, cause, replaces_check_id, note, observer, observed_at, gps_lat, gps_lon, gps_accuracy_m.
    trees_total_known: the real number of trees at this point/block if the caller knows it (from the saved plan), used only to
    give a clearer error when trees_total disagrees - never silently overridden, since the person on the ground may be
    correcting an earlier record (a tree the plan never counted, or one the plan listed that was never actually in the ground).
    Returns the cleaned dict (observed_at as an ISO string) or raises SurvivalCheckError.
    """
    plan_id = str(raw.get("plan_id") or "").strip()
    if not plan_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", plan_id):
        raise SurvivalCheckError("plan_id is required and may contain only letters, digits, underscore and hyphen")
    try:
        point_id = int(raw["point_id"])
    except (KeyError, TypeError, ValueError):
        raise SurvivalCheckError("point_id is required and must be a whole number")
    species_id = raw.get("species_id")
    species_id = None if species_id is None or str(species_id).strip() == "" else int(species_id)
    round_label = raw.get("round_label")
    if round_label not in ROUND_LABELS:
        raise SurvivalCheckError(f"round_label must be one of {', '.join(ROUND_LABELS)}")
    status = raw.get("status")
    if status not in STATUSES:
        raise SurvivalCheckError(f"status must be one of {', '.join(STATUSES)}")

    def whole(name, required=True, max_=CFG["trees_max"]):
        v = raw.get(name)
        if v is None or (isinstance(v, str) and v.strip() == ""):
            if required:
                raise SurvivalCheckError(f"{name} is required")
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise SurvivalCheckError(f"{name} '{v}' is not a number")
        if not math.isfinite(f) or f != int(f) or f < 0 or f > max_:
            raise SurvivalCheckError(f"{name} must be a whole number from 0 to {max_}")
        return int(f)

    trees_total = whole("trees_total")
    trees_alive = whole("trees_alive")
    trees_dead = whole("trees_dead")
    if trees_alive + trees_dead > trees_total:
        raise SurvivalCheckError(f"trees_alive ({trees_alive}) + trees_dead ({trees_dead}) cannot be more than trees_total ({trees_total})")
    if trees_total_known is not None and trees_total != trees_total_known and not (raw.get("note") or "").strip():
        raise SurvivalCheckError(f"trees_total ({trees_total}) does not match the {trees_total_known} trees this plan placed here; "
                                  "add a note saying why (a tree never planted, one missed by the plan, and so on)")
    if status == "dead" and trees_dead == 0:
        raise SurvivalCheckError("status is dead but trees_dead is 0: say how many trees died")
    if status == "survived" and trees_alive == 0 and trees_total > 0:
        raise SurvivalCheckError("status is survived but trees_alive is 0: use dead or not_found instead")
    cause = raw.get("cause")
    cause = None if cause is None or str(cause).strip() == "" else str(cause).strip()
    if trees_dead > 0:
        if cause is None:
            raise SurvivalCheckError(f"cause is required when trees_dead is more than 0 (one of: {', '.join(CAUSES)})")
        if cause not in CAUSES:
            raise SurvivalCheckError(f"cause '{cause}' is not valid (one of: {', '.join(CAUSES)})")
    elif cause is not None:
        raise SurvivalCheckError("cause only applies when trees_dead is more than 0")
    replaces = raw.get("replaces_check_id")
    replaces = None if replaces is None or str(replaces).strip() == "" else int(replaces)
    observer = (raw.get("observer") or "").strip()
    if not observer:
        raise SurvivalCheckError("observer (the name of the person who made the check) is required")
    if len(observer) > CFG["observer_max_chars"]:
        raise SurvivalCheckError(f"observer is too long (limit {CFG['observer_max_chars']} characters)")
    note = (raw.get("note") or "").strip() or None
    if note and len(note) > CFG["note_max_chars"]:
        raise SurvivalCheckError(f"note is too long ({len(note)} characters; limit {CFG['note_max_chars']})")
    gps_lat, gps_lon = _num(raw.get("gps_lat"), "gps_lat"), _num(raw.get("gps_lon"), "gps_lon")
    if (gps_lat is None) != (gps_lon is None):
        raise SurvivalCheckError("gps_lat and gps_lon must be given together")
    if gps_lat is not None and not (-90 <= gps_lat <= 90 and -180 <= gps_lon <= 180):
        raise SurvivalCheckError(f"gps coordinates ({gps_lat}, {gps_lon}) are not valid latitude/longitude values")
    acc = _num(raw.get("gps_accuracy_m"), "gps_accuracy_m")
    if acc is not None and not (0 <= acc <= CFG["accuracy_max_m"]):
        raise SurvivalCheckError(f"gps_accuracy_m must be between 0 and {CFG['accuracy_max_m']:.0f}")
    return {"plan_id": plan_id, "point_id": point_id, "species_id": species_id, "round_label": round_label, "status": status,
            "trees_total": trees_total, "trees_alive": trees_alive, "trees_dead": trees_dead, "cause": cause, "replaces_check_id": replaces,
            "note": note, "observer": observer, "observed_at": iso(parse_time(raw.get("observed_at"), now)),
            "gps_lat": gps_lat, "gps_lon": gps_lon, "gps_accuracy_m": acc}


def add_event(db_path, event, source="dashboard", con=None):
    """Append one cleaned event. Returns its check_id. Never updates or deletes anything."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}")
    own = con is None
    con = con or connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO survival_checks (plan_id, point_id, species_id, round_label, status, trees_total, trees_alive, trees_dead, cause, "
            "replaces_check_id, note, observer, observed_at, gps_lat, gps_lon, gps_accuracy_m, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event["plan_id"], event["point_id"], event["species_id"], event["round_label"], event["status"], event["trees_total"],
             event["trees_alive"], event["trees_dead"], event["cause"], event["replaces_check_id"], event["note"], event["observer"],
             event["observed_at"], event["gps_lat"], event["gps_lon"], event["gps_accuracy_m"], source, iso(now_utc())))
        if own:
            con.commit()
        return int(cur.lastrowid)
    finally:
        if own:
            con.close()


def _row(r):
    return {k: r[k] for k in EVENT_COLUMNS}


def history(db_path, plan_id, point_id):
    """Every event of one planted point/block of one plan, oldest first - including dead-tree events that were later replaced."""
    con = connect(db_path)
    try:
        return [_row(r) for r in con.execute("SELECT * FROM survival_checks WHERE plan_id=? AND point_id=? ORDER BY check_id", (str(plan_id), int(point_id)))]
    finally:
        con.close()


def n_events(db_path):
    con = connect(db_path)
    try:
        return int(con.execute("SELECT COUNT(*) FROM survival_checks").fetchone()[0])
    finally:
        con.close()


def current_for_plan(db_path, plan_id):
    """{point_id: latest event} for every point of one plan that has at least one survival check."""
    con = connect(db_path)
    try:
        rows = con.execute("SELECT *, ROW_NUMBER() OVER (PARTITION BY point_id ORDER BY check_id DESC) AS rn FROM survival_checks "
                           "WHERE plan_id=? ORDER BY point_id", (str(plan_id),)).fetchall()
    finally:
        con.close()
    return {r["point_id"]: _row(r) for r in rows if r["rn"] == 1}


def plan_summary(db_path, plan_id, trees_by_point):
    """Counts for one plan's survival report: how many of its points have been checked at all, current alive/dead/not_found
    trees (latest event per point), by cause, by round, and the replacement count. trees_by_point: {point_id: trees planted},
    from the saved plan - used only to report how many points are NOT YET checked (never guessed as "survived")."""
    current = current_for_plan(db_path, plan_id)
    all_points = set(int(p) for p in trees_by_point)
    checked = set(current)
    by_round = {}
    by_cause = {c: 0 for c in CAUSES}
    alive = dead = not_found = 0
    replaced_events = 0
    for pid, c in current.items():
        by_round.setdefault(c["round_label"], 0)
        by_round[c["round_label"]] += 1
        if c["status"] == "survived":
            alive += 1
        elif c["status"] == "dead":
            dead += 1
        elif c["status"] == "not_found":
            not_found += 1
        if c["cause"]:
            by_cause[c["cause"]] += 1
    con = connect(db_path)
    try:
        replaced_events = int(con.execute("SELECT COUNT(DISTINCT replaces_check_id) FROM survival_checks WHERE plan_id=? AND replaces_check_id IS NOT NULL",
                                          (str(plan_id),)).fetchone()[0])
    finally:
        con.close()
    trees_alive_total = sum(int(c["trees_alive"]) for c in current.values())
    trees_dead_total = sum(int(c["trees_dead"]) for c in current.values())
    trees_planned_total = int(sum(trees_by_point.values())) if trees_by_point else 0
    return {"plan_id": str(plan_id), "points_planned": len(all_points), "points_checked": len(checked), "points_not_yet_checked": len(all_points - checked),
            "points_survived": alive, "points_dead": dead, "points_not_found": not_found,
            "trees_planned_total": trees_planned_total, "trees_alive_latest": trees_alive_total, "trees_dead_latest": trees_dead_total,
            "by_round": by_round, "by_cause": {k: v for k, v in by_cause.items() if v}, "replacement_events": replaced_events,
            "note": "Counts use the latest survival check of each point. A point with no check yet is not assumed to have survived or died."}


# ---------------------------------------------------------------------------------------------------------------------
# monitoring schedule - which rounds are due, not a live reminder system (see module docstring)
# ---------------------------------------------------------------------------------------------------------------------
def due_schedule(planted_at, current, *, today=None):
    """One row per configured round (3_month, 6_month, ...): its due date (planted_at + the round's months) and whether it is
    `done` (a check of that round_label already exists in `current`, the {round_label: event} map built by the caller),
    `overdue`, `due` (inside the due window) or `upcoming`. planted_at: a date/datetime or ISO string of when the plan's trees
    went in the ground. Never guesses a result for a round with no check - "done" only means a check was recorded, not that
    the trees survived."""
    today = today or now_utc()
    if isinstance(today, str):
        today = parse_time(today)
    if isinstance(planted_at, str):
        planted_at = parse_time(planted_at)
    out = []
    for r in CFG["rounds"]:
        due = add_months(planted_at, r["months"])
        done = r["label"] in current
        if done:
            state = "done"
        elif today > due + timedelta(days=CFG["overdue_grace_days"]):
            state = "overdue"
        elif today >= due - timedelta(days=CFG["due_window_days"]):
            state = "due"
        else:
            state = "upcoming"
        out.append({"round_label": r["label"], "months": r["months"], "due_date": due.date().isoformat(), "state": state,
                    "check_id": current[r["label"]]["check_id"] if done else None})
    return out


def checks_at_round(db_path, plan_id, round_label):
    """{point_id: latest event} restricted to ONE round_label - the survival check(s) logged specifically at that monitoring
    round, as opposed to current_for_plan()'s "whatever the latest check was, whichever round". Used by threshold_summary()
    to measure the rate AT the benchmark round even if some points already have a later check too."""
    con = connect(db_path)
    try:
        rows = con.execute("SELECT *, ROW_NUMBER() OVER (PARTITION BY point_id ORDER BY check_id DESC) AS rn FROM survival_checks "
                           "WHERE plan_id=? AND round_label=? ORDER BY point_id", (str(plan_id), round_label)).fetchall()
    finally:
        con.close()
    return {r["point_id"]: _row(r) for r in rows if r["rn"] == 1}


def threshold_summary(db_path, plan_id, trees_by_point, cfg=None):
    """The panel's "threshold survival" ask: is this plan meeting the accepted survival-rate benchmark
    (CFG['success_threshold_pct'], measured at CFG['success_threshold_round']) - see the CFG comment for where that number
    comes from and why it is provisional. Never guesses a rate for a point not yet checked at that round: a plan that
    simply hasn't reached its 1-year mark yet is reported as "not yet due" (points_at_round=0, measured_pct=None, met=None),
    never as failing the threshold."""
    c = CFG if cfg is None else cfg
    round_label = c["success_threshold_round"]
    at_round = checks_at_round(db_path, plan_id, round_label)
    trees_total = sum(int(e["trees_total"]) for e in at_round.values())
    trees_alive = sum(int(e["trees_alive"]) for e in at_round.values())
    points_at_round, points_planned = len(at_round), len(trees_by_point)
    rate = round(100.0 * trees_alive / trees_total, 1) if trees_total else None
    return {
        "round_label": round_label, "threshold_pct": c["success_threshold_pct"],
        "basis": "DENR National Greening Program survival-rate requirement (85%); provisional, not yet confirmed by the agriculturist for this project's species and sites.",
        "points_at_round": points_at_round, "points_planned": points_planned,
        "trees_checked_at_round": trees_total, "trees_alive_at_round": trees_alive,
        "measured_pct": rate, "met": None if rate is None else rate >= c["success_threshold_pct"],
        "note": (f"No point of this plan has a {round_label} survival check recorded yet; the threshold cannot be evaluated until at least one does."
                 if points_at_round == 0 else
                 f"{points_at_round} of {points_planned} planned points have a {round_label} check recorded; the rate above covers only those, not the whole plan."),
    }


def rounds_by_label(events):
    """{round_label: latest event of that round} from a list of events (newest-first `check_id` order recommended, but this
    keeps the highest check_id per label regardless of input order)."""
    out = {}
    for e in events:
        lbl = e["round_label"]
        if lbl not in out or e["check_id"] > out[lbl]["check_id"]:
            out[lbl] = e
    return out


def order_plantings(plantings):
    """Pure helper for GET /points/{point_id}/history (api_v2.py): sort a point's plantings (one dict per plan that
    confirmed planting it, each with a `planted_observed_at` ISO string) oldest first, so a point planted more than once -
    replanted after an earlier planting died, say - lists its history in the order it actually happened. A missing or
    empty date sorts first rather than raising, since golden rule 1 says never guess a date that was not recorded."""
    return sorted(plantings, key=lambda p: p.get("planted_observed_at") or "")
