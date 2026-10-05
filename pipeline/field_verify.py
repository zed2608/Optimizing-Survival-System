#!/usr/bin/env python3
"""
field_verify.py - saved field checks: what a researcher saw at a planned or ranked spot.

Library module (used by api_v2.py; no web code here). Storage is a SQLite file, data/field/field_checks.db, with ONE table of
APPEND-ONLY events (the database itself refuses UPDATE and DELETE). The latest event of a point is its current status. If the latest two
events come from different observers and disagree, the point is DISPUTED.

    status  verified_plantable | not_plantable | needs_recheck
    reason  paved | building | rock_or_ledge | creek_or_waterlogged | too_steep | existing_tree | owner_refused | other   (required for not_plantable)

Effects (decided in api_v2.py, switch FIELD_EXCLUDE_NOT_PLANTABLE): not_plantable points are left out of rankings and plans; verified_plantable
only adds a badge; needs_recheck and disputed points are shown with a warning but not excluded.
filter_context() lets any script (for example pipeline/run_plan.py) apply the same exclusion to a matching.Context.
"""
import csv, dataclasses, hashlib, io, json, math, re, sqlite3, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import field_kit as fk  # noqa: E402  (plan check code and species codes: the same rules as the kit builder)

# =====================================================================================================================
# CONFIG - every tunable number lives here. PROVISIONAL.
# =====================================================================================================================
CFG = {
    "default_db": "data/field/field_checks.db",
    "note_max_chars": 500,                  # longest note
    "observer_max_chars": 80,               # longest observer name
    "accuracy_max_m": 1000.0,               # largest GPS accuracy accepted
    "moved_max_m": 150.0,                   # a moved stake may be this far from its grid point (a cell is 100 m wide: the diagonal is ~141 m)
    "future_tolerance_hours": 24,           # observed_at may be at most this far in the future (clock differences)
    "municipality_buffer_deg": 0.0005,      # coordinates may lie this far (~50 m) outside the simplified municipal outline
    "import_max_bytes": 2_000_000,          # largest CSV accepted by the import
    "import_max_rows": 5000,                # most rows in one import
    "report_max_rows": 400,                 # rows listed in the import report (counts always cover every row)
    "disputed_bit": 4,                      # in the compact status codes, disputed = code + 4
}
# =====================================================================================================================

STATUSES = ("verified_plantable", "not_plantable", "needs_recheck")
REASONS = ("paved", "building", "rock_or_ledge", "creek_or_waterlogged", "too_steep", "existing_tree", "owner_refused", "other")
SOURCES = ("dashboard", "kit_import")
STATUS_CODE = {"verified_plantable": 1, "not_plantable": 2, "needs_recheck": 3}      # compact codes used by /grid (0 = no check)

# words a kit's status column may hold (the README says: tick it when the tree is planted)
VERIFIED_WORDS = {"verified_plantable", "verified", "plantable", "planted", "done", "yes", "y", "x", "ok", "✓", "✔", "1", "true"}
NOT_WORDS = {"not_plantable", "not plantable", "unplantable", "no", "n", "skip", "skipped", "blocked", "flagged", "cannot plant", "can't plant", "0", "false"}
RECHECK_WORDS = {"needs_recheck", "needs recheck", "recheck", "check again", "unsure", "maybe", "?"}

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS field_checks (
    check_id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN {STATUSES}),
    reason TEXT CHECK (reason IS NULL OR reason IN {REASONS}),
    note TEXT,
    observer TEXT NOT NULL CHECK (length(trim(observer)) > 0),
    observed_at TEXT NOT NULL,
    gps_lat REAL, gps_lon REAL, gps_accuracy_m REAL,
    moved_lat REAL, moved_lon REAL,
    source TEXT NOT NULL CHECK (source IN {SOURCES}),
    plan_id TEXT,
    created_at TEXT NOT NULL,
    import_key TEXT,
    CHECK (status <> 'not_plantable' OR reason IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_field_checks_point ON field_checks (point_id, check_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_field_checks_import_key ON field_checks (import_key) WHERE import_key IS NOT NULL;
CREATE TRIGGER IF NOT EXISTS field_checks_no_update BEFORE UPDATE ON field_checks BEGIN SELECT RAISE(ABORT, 'field_checks is append-only: add a new event instead'); END;
CREATE TRIGGER IF NOT EXISTS field_checks_no_delete BEFORE DELETE ON field_checks BEGIN SELECT RAISE(ABORT, 'field_checks is append-only: events are never deleted'); END;
"""
EVENT_COLUMNS = ["check_id", "point_id", "status", "reason", "note", "observer", "observed_at", "gps_lat", "gps_lon", "gps_accuracy_m",
                 "moved_lat", "moved_lon", "source", "plan_id", "created_at"]


class FieldCheckError(ValueError):
    """A field check that cannot be saved; the message says why in plain words."""


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
    """observed_at: an ISO date/time (no time zone = UTC) or None (= now). Not more than future_tolerance_hours ahead."""
    now = now or now_utc()
    if value is None or str(value).strip() == "":
        return now
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        raise FieldCheckError(f"observed_at '{value}' is not a date/time (use for example 2026-10-05 or 2026-10-05T14:30)")
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if dt > now + timedelta(hours=CFG["future_tolerance_hours"]):
        raise FieldCheckError(f"observed_at {iso(dt)} lies in the future")
    return dt


def distance_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _num(v, name):
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise FieldCheckError(f"{name} '{v}' is not a number")
    if not math.isfinite(x):
        raise FieldCheckError(f"{name} must be a finite number")
    return x


def _pair(lat, lon, what, inside):
    la, lo = _num(lat, f"{what}_lat"), _num(lon, f"{what}_lon")
    if la is None and lo is None:
        return None, None
    if la is None or lo is None:
        raise FieldCheckError(f"{what}_lat and {what}_lon must be given together")
    if not (-90 <= la <= 90 and -180 <= lo <= 180):
        raise FieldCheckError(f"{what} coordinates ({la}, {lo}) are not valid latitude/longitude values")
    if inside is not None and not inside(la, lo):
        raise FieldCheckError(f"{what} coordinates ({la}, {lo}) are outside the municipality of San Mateo")
    return la, lo


def validate_event(raw, *, point_lonlat, inside=None, previous_status=None, now=None):
    """
    Clean and check one event. raw: dict with point_id, status, reason, note, observer, observed_at, gps_lat, gps_lon, gps_accuracy_m,
    moved_lat, moved_lon, plan_id. point_lonlat = (lon, lat) of the grid point, or None if the point does not exist (-> error).
    Returns the cleaned dict (observed_at as an ISO string) or raises FieldCheckError.
    """
    if point_lonlat is None:
        raise FieldCheckError(f"point_id {raw.get('point_id')} is not a point of the planting grid")
    status = raw.get("status")
    if status not in STATUSES:
        raise FieldCheckError(f"status must be one of {', '.join(STATUSES)}")
    reason = raw.get("reason")
    reason = None if reason is None or str(reason).strip() == "" else str(reason).strip()
    if status == "not_plantable":
        if reason is None:
            raise FieldCheckError(f"a reason is required when the status is not_plantable (one of: {', '.join(REASONS)})")
        if reason not in REASONS:
            raise FieldCheckError(f"reason '{reason}' is not valid (one of: {', '.join(REASONS)})")
    elif reason is not None:
        raise FieldCheckError("a reason only applies to not_plantable")
    observer = (raw.get("observer") or "").strip()
    if not observer:
        raise FieldCheckError("observer (the name of the person who made the check) is required")
    if len(observer) > CFG["observer_max_chars"]:
        raise FieldCheckError(f"observer is too long (limit {CFG['observer_max_chars']} characters)")
    note = (raw.get("note") or "").strip() or None
    if note and len(note) > CFG["note_max_chars"]:
        raise FieldCheckError(f"note is too long ({len(note)} characters; limit {CFG['note_max_chars']})")
    if previous_status == "not_plantable" and status != "not_plantable" and not note:
        raise FieldCheckError("a note is required to clear a not_plantable point (say what you saw)")
    gps_lat, gps_lon = _pair(raw.get("gps_lat"), raw.get("gps_lon"), "gps", inside)
    moved_lat, moved_lon = _pair(raw.get("moved_lat"), raw.get("moved_lon"), "moved", inside)
    if moved_lat is not None:
        d = distance_m(point_lonlat[1], point_lonlat[0], moved_lat, moved_lon)
        if d > CFG["moved_max_m"]:
            raise FieldCheckError(f"the moved position is {d:.0f} m from the grid point (limit {CFG['moved_max_m']:.0f} m): check latitude and longitude")
    acc = _num(raw.get("gps_accuracy_m"), "gps_accuracy_m")
    if acc is not None and not (0 <= acc <= CFG["accuracy_max_m"]):
        raise FieldCheckError(f"gps_accuracy_m must be between 0 and {CFG['accuracy_max_m']:.0f}")
    plan_id = raw.get("plan_id")
    if plan_id is not None and str(plan_id).strip() != "" and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(plan_id).strip()):
        raise FieldCheckError("plan_id may contain only letters, digits, underscore and hyphen")
    plan_id = None if plan_id is None or str(plan_id).strip() == "" else str(plan_id).strip()
    return {"point_id": int(raw["point_id"]), "status": status, "reason": reason, "note": note, "observer": observer,
            "observed_at": iso(parse_time(raw.get("observed_at"), now)), "gps_lat": gps_lat, "gps_lon": gps_lon, "gps_accuracy_m": acc,
            "moved_lat": moved_lat, "moved_lon": moved_lon, "plan_id": plan_id}


def add_event(db_path, event, source="dashboard", import_key=None, con=None):
    """Append one cleaned event. Returns its check_id. Never updates or deletes anything."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}")
    own = con is None
    con = con or connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO field_checks (point_id, status, reason, note, observer, observed_at, gps_lat, gps_lon, gps_accuracy_m, moved_lat, moved_lon, "
            "source, plan_id, created_at, import_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event["point_id"], event["status"], event["reason"], event["note"], event["observer"], event["observed_at"], event["gps_lat"],
             event["gps_lon"], event["gps_accuracy_m"], event["moved_lat"], event["moved_lon"], source, event["plan_id"], iso(now_utc()), import_key))
        if own:
            con.commit()
        return int(cur.lastrowid)
    finally:
        if own:
            con.close()


def _row(r):
    return {k: r[k] for k in EVENT_COLUMNS}


def history(db_path, point_id):
    """Every event of a point, oldest first."""
    con = connect(db_path)
    try:
        return [_row(r) for r in con.execute("SELECT * FROM field_checks WHERE point_id=? ORDER BY check_id", (int(point_id),))]
    finally:
        con.close()


def n_events(db_path):
    con = connect(db_path)
    try:
        return int(con.execute("SELECT COUNT(*) FROM field_checks").fetchone()[0])
    finally:
        con.close()


def is_disputed(latest, previous):
    """The latest two events come from different observers and disagree."""
    return (previous is not None and latest["observer"].strip().lower() != previous["observer"].strip().lower()
            and latest["status"] != previous["status"])


def current_status(db_path):
    """{point_id: current status dict} from the latest event of every point (plus the disputed flag and the number of events)."""
    con = connect(db_path)
    try:
        rows = con.execute("SELECT *, ROW_NUMBER() OVER (PARTITION BY point_id ORDER BY check_id DESC) AS rn, "
                           "COUNT(*) OVER (PARTITION BY point_id) AS n FROM field_checks ORDER BY point_id").fetchall()
    finally:
        con.close()
    out, prev = {}, {}
    for r in rows:
        if r["rn"] == 1:
            out[r["point_id"]] = {**_row(r), "n_events": int(r["n"]), "disputed": False}
        elif r["rn"] == 2:
            prev[r["point_id"]] = r
    for pid, cur in out.items():
        cur["disputed"] = is_disputed(cur, prev.get(pid))
    return out


def status_code(cur):
    return STATUS_CODE[cur["status"]] + (CFG["disputed_bit"] if cur["disputed"] else 0)


def excluded_ids(current):
    return {pid for pid, c in current.items() if c["status"] == "not_plantable"}


def filter_context(ctx, ids):
    """A copy of a matching.Context without the given points (rows of sites and S). Used by scripts that plan without the API."""
    ids = set(int(i) for i in ids)
    if not ids:
        return ctx
    keep = ~ctx.sites.point_id.isin(ids).to_numpy()
    return dataclasses.replace(ctx, sites=ctx.sites[keep].reset_index(drop=True), S=ctx.S[keep])


def summary(current, barangay_of):
    """Counts of the CURRENT statuses: overall, per barangay and per reason. barangay_of(point_id) -> barangay name or None."""
    by_status = {s: 0 for s in STATUSES}
    by_reason = {r: 0 for r in REASONS}
    by_barangay = {}
    disputed = 0
    for pid, c in current.items():
        by_status[c["status"]] += 1
        if c["status"] == "not_plantable":
            by_reason[c["reason"]] += 1
        disputed += int(c["disputed"])
        b = barangay_of(pid) or "Outside every barangay"
        by_barangay.setdefault(b, {s: 0 for s in STATUSES})[c["status"]] += 1
    return {"points_checked": len(current), "by_status": by_status, "by_reason": by_reason, "by_barangay": by_barangay, "disputed_points": disputed}


def events_csv(db_path, barangay_of, current_only=False):
    """All events (or only the latest per point) as CSV text, with the barangay added."""
    con = connect(db_path)
    try:
        sql = "SELECT * FROM field_checks WHERE check_id IN (SELECT MAX(check_id) FROM field_checks GROUP BY point_id) ORDER BY point_id" if current_only \
            else "SELECT * FROM field_checks ORDER BY check_id"
        rows = [_row(r) for r in con.execute(sql)]
    finally:
        con.close()
    buf = io.StringIO()
    cols = EVENT_COLUMNS[:2] + ["barangay"] + EVENT_COLUMNS[2:]
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({**r, "barangay": barangay_of(r["point_id"]) or "", **{k: ("" if r[k] is None else r[k]) for k in EVENT_COLUMNS}})
    return buf.getvalue()


# ---------------------------------------------------------------------------------------------------------------------
# kit import
# ---------------------------------------------------------------------------------------------------------------------
def plan_point_refs(plan, species):
    """{point_ref: point_id} of a saved plan, built the way the field kit builder numbers its points (species code + number, grid id order)."""
    names = species.set_index("species_id").common_name
    codes = fk.make_codes([(int(s), names[s]) for s in sorted(plan.species_id.unique())])
    df = plan[["point_id", "species_id"]].copy()
    df["code"] = df.species_id.map(codes)
    df = df.sort_values(["code", "point_id"]).reset_index(drop=True)
    width = max(fk.CFG["min_number_digits"], len(str(df.groupby("code").size().max())))
    df["ref"] = df.code + "-" + (df.groupby("code").cumcount() + 1).astype(str).str.zfill(width)
    return dict(zip(df.ref, df.point_id.astype(int)))


def map_status(word):
    """(status, reason or None) from a word in a kit's status column, or None if it is not recognised."""
    w = str(word).strip().lower().replace("-", "_")
    if w in {x.replace("-", "_") for x in VERIFIED_WORDS}:
        return "verified_plantable", None
    if w in {x.replace("-", "_") for x in RECHECK_WORDS}:
        return "needs_recheck", None
    if w in {x.replace("-", "_") for x in NOT_WORDS}:
        return "not_plantable", "other"
    if w in REASONS:                                         # a reason written in the status column: paved, building, ...
        return "not_plantable", w
    return None


def _import_key(plan_id, point_id, status, reason, note, moved_lat, moved_lon):
    payload = json.dumps([plan_id, int(point_id), status, reason, note or "", None if moved_lat is None else round(moved_lat, 6),
                          None if moved_lon is None else round(moved_lon, 6)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def import_kit_csv(db_path, text, *, observer, species, plans_dir, point_lonlat_of, inside=None, plan_id=None, observed_at=None, now=None):
    """
    Import the point-list.csv of a field kit whose status (and moved_lat / moved_lon) columns were filled in.
    point_ref -> point_id uses the saved plan (plan_id column of the file, or the plan_id argument). Rows that are not filled in are skipped;
    bad rows are rejected with a reason; a row that was imported before (same plan, point, status, reason, note and moved position) adds nothing.
    point_lonlat_of(point_id) -> (lon, lat) or None. Returns a report dict.
    """
    now = now or now_utc()
    observer = (observer or "").strip()
    if not observer:
        raise FieldCheckError("observer (the name of the person importing the file) is required")
    if len(text.encode("utf-8")) > CFG["import_max_bytes"]:
        raise FieldCheckError(f"the file is too large (limit {CFG['import_max_bytes'] // 1000} KB)")
    text = text.lstrip("﻿")
    first = text.splitlines()[0] if text.strip() else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    cols = [(c or "").strip() for c in (reader.fieldnames or [])]
    if not text.strip() or "status" not in cols or not ({"point_ref", "point_id"} & set(cols)):
        raise FieldCheckError("this does not look like a field kit point-list.csv: it needs the columns point_ref (or point_id) and status")
    rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in reader]
    if len(rows) > CFG["import_max_rows"]:
        raise FieldCheckError(f"too many rows ({len(rows)}; limit {CFG['import_max_rows']})")
    file_plans = {r.get("plan_id", "") for r in rows if r.get("plan_id", "")}
    if plan_id is None and len(file_plans) > 1:
        raise FieldCheckError(f"the file mixes several plans ({', '.join(sorted(file_plans))}); import one kit at a time")
    pid_plan = plan_id or (next(iter(file_plans)) if file_plans else None)
    report = {"plan_id": pid_plan, "observer": observer, "rows_in_file": len(rows), "accepted": 0, "rejected": 0, "duplicates": 0, "blank": 0, "rows": [],
              "notes": []}
    if not pid_plan:
        raise FieldCheckError("the file has no plan_id column and none was given: it is needed to map point_ref to the grid point")
    refs, plan_ids, code = {}, set(), None
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", pid_plan):
        raise FieldCheckError("plan_id may contain only letters, digits, underscore and hyphen")
    plan_csv = Path(plans_dir) / f"{pid_plan}.csv"
    plan_error = None
    if plan_csv.is_file():
        plan = pd.read_csv(plan_csv)
        refs = plan_point_refs(plan, species)
        plan_ids = set(plan.point_id.astype(int))
        code = fk.check_code(plan_csv)
    else:
        plan_error = f"plan '{pid_plan}' was not found among the saved plans, so point_ref cannot be mapped to a grid point"
    con = connect(db_path)
    seen = set()
    try:
        con.execute("BEGIN")
        for n, r in enumerate(rows, start=2):                                    # line 1 is the header
            ref = r.get("point_ref", "")
            outcome = {"line": n, "point_ref": ref, "point_id": r.get("point_id", "") or None}

            def done(kind, why=""):
                report[kind] += 1
                outcome.update({"outcome": {"accepted": "accepted", "rejected": "rejected", "duplicates": "duplicate", "blank": "blank"}[kind], "reason": why})
                if len(report["rows"]) < CFG["report_max_rows"] and kind != "blank":
                    report["rows"].append(outcome)

            word, mlat, mlon = r.get("status", ""), r.get("moved_lat", ""), r.get("moved_lon", "")
            if word == "" and mlat == "" and mlon == "":
                done("blank")
                continue
            try:
                if plan_error:
                    raise FieldCheckError(plan_error)
                if r.get("plan_id", "") and r["plan_id"] != pid_plan:
                    raise FieldCheckError(f"row belongs to plan '{r['plan_id']}', not '{pid_plan}'")
                if r.get("check_code", "") and code and r["check_code"] != code:
                    raise FieldCheckError(f"the kit check code {r['check_code']} does not match the saved plan ({code}): the plan changed after the kit was built")
                point_id = refs.get(ref) if ref else None
                if ref and point_id is None:
                    raise FieldCheckError(f"point_ref '{ref}' does not belong to plan '{pid_plan}'")
                if r.get("point_id", ""):
                    try:
                        given = int(float(r["point_id"]))
                    except ValueError:
                        raise FieldCheckError(f"point_id '{r['point_id']}' is not a number")
                    if point_id is not None and given != point_id:
                        raise FieldCheckError(f"point_id {given} does not match point_ref '{ref}' (expected {point_id})")
                    point_id = given
                if point_id is None:
                    raise FieldCheckError("the row has neither a point_ref nor a point_id")
                if point_id not in plan_ids:
                    raise FieldCheckError(f"point {point_id} is not part of plan '{pid_plan}'")
                outcome["point_id"] = point_id
                if word == "":
                    raise FieldCheckError("a moved position is given but the status is empty")
                mapped = map_status(word)
                if mapped is None:
                    raise FieldCheckError(f"unrecognised status '{word}' (use planted / verified_plantable, not_plantable or needs_recheck)")
                status, reason = mapped
                reason = r.get("reason") or reason
                note = r.get("note") or None
                if status == "not_plantable" and reason == "other" and not note:
                    note = "from a kit import: no reason given"
                ev = {"point_id": point_id, "status": status, "reason": reason if status == "not_plantable" else None, "note": note,
                      "observer": r.get("observer") or observer, "observed_at": r.get("observed_at") or observed_at, "moved_lat": mlat or None,
                      "moved_lon": mlon or None, "plan_id": pid_plan}
                prev = con.execute("SELECT status FROM field_checks WHERE point_id=? ORDER BY check_id DESC LIMIT 1", (point_id,)).fetchone()
                ev = validate_event(ev, point_lonlat=point_lonlat_of(point_id), inside=inside, previous_status=prev["status"] if prev else None, now=now)
                key = _import_key(pid_plan, point_id, ev["status"], ev["reason"], ev["note"], ev["moved_lat"], ev["moved_lon"])
                if key in seen or con.execute("SELECT 1 FROM field_checks WHERE import_key=?", (key,)).fetchone():
                    seen.add(key)
                    done("duplicates", "this row was already imported (same plan, point, status and moved position)")
                    continue
                add_event(db_path, ev, source="kit_import", import_key=key, con=con)
                seen.add(key)
                done("accepted")
            except FieldCheckError as ex:
                done("rejected", str(ex))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    if len(report["rows"]) >= CFG["report_max_rows"]:
        report["notes"].append(f"only the first {CFG['report_max_rows']} non-blank rows are listed; the counts cover every row")
    return report
