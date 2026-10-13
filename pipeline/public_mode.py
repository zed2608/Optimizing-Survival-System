"""
Public sandbox mode (deploy-sandbox branch). OFF by default: with no environment variable set, nothing in the service changes.

Switch on with OS_PUBLIC_MODE=1. Then:
  - plans, kits, the forecast cache and the saved field checks live in a THROWAWAY folder (OS_STATE_DIR; default <temp>/os_sandbox_state).
    The folder is emptied at every start and every OS_RESET_HOURS hours. The real field-check file is never opened or copied.
  - the field-check exclusion switch is OFF (an anonymous "not plantable" mark must not change what other visitors see);
  - size cap on the CSV import and on every other POST body, cap on stored plans / kits / field events;
  - per-visitor rate limits (plus a global limit for each kind) on plan, kit, field-check and compute requests; kit builds one at a time;
  - /docs, /redoc and /openapi.json answer 404.
All numbers below are PROVISIONAL settings; each can be changed with an environment variable (OS_RATE_PLAN, ...).
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

SENTINEL = ".sandbox_state"          # a folder is only ever emptied if it holds this file (or is empty): never a real data folder

NOTICE = "Demo / sandbox. Data is provisional and not yet signed off by the agriculturist. Entries reset regularly."

# defaults: (requests, window in seconds) per visitor; the global limit is GLOBAL_FACTOR times that
LIMITS = {
    "plan": (20, 3600),
    "kit": (6, 3600),
    "field": (60, 3600),
    "compute": (60, 60),
    "login": (10, 600),                  # wrong access codes (pipeline/access_gate.py)
    "read": (300, 60),                   # every other GET in public mode
    "weather": (30, 60),                 # GETs that can make the service call Open-Meteo
}
GLOBAL_FACTOR = 5
CAPS = {"import_bytes": 200_000, "body_bytes": 1_000_000, "plans": 200, "kits": 30, "field_events": 2000}
RESET_HOURS = 24.0
TRUST_PROXY_HOPS = 1                 # which X-Forwarded-For entry (counted from the right) is the visitor; 0 = ignore the header


def _env_int(name, default):
    try:
        v = int(os.environ.get(name, ""))
        return v if v > 0 else default
    except ValueError:
        return default


def _env_float(name, default):
    try:
        v = float(os.environ.get(name, ""))
        return v if v > 0 else default
    except ValueError:
        return default


def is_on():
    return os.environ.get("OS_PUBLIC_MODE", "").strip().lower() in ("1", "true", "yes", "on")


def settings():
    """The settings in force (read from the environment each time, so tests can change them)."""
    limits = {k: (_env_int(f"OS_RATE_{k.upper()}", n), w) for k, (n, w) in LIMITS.items()}
    caps = {"import_bytes": _env_int("OS_MAX_IMPORT_BYTES", CAPS["import_bytes"]), "body_bytes": _env_int("OS_MAX_BODY_BYTES", CAPS["body_bytes"]),
            "plans": _env_int("OS_MAX_PLANS", CAPS["plans"]), "kits": _env_int("OS_MAX_KITS", CAPS["kits"]),
            "field_events": _env_int("OS_MAX_FIELD_EVENTS", CAPS["field_events"])}
    hops = os.environ.get("OS_TRUST_PROXY_HOPS", "")
    return {"on": is_on(), "limits": limits, "caps": caps, "reset_hours": _env_float("OS_RESET_HOURS", RESET_HOURS),
            "proxy_hops": int(hops) if hops.strip().isdigit() else TRUST_PROXY_HOPS, "notice": NOTICE}


def default_state_dir():
    return Path(tempfile.gettempdir()) / "os_sandbox_state"


def state_dir():
    """OS_STATE_DIR as an absolute path, or None when it is not set (then the service keeps its normal folders)."""
    raw = os.environ.get("OS_STATE_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return default_state_dir().resolve() if is_on() else None


def check_state_dir(path, protected):
    """Refuse a state folder that is, holds or lies inside one of the protected folders (the real data and the real field-check folder)."""
    p = Path(path).resolve()
    for q in protected:
        q = Path(q).resolve()
        if p == q or q in p.parents or p in q.parents:
            raise ValueError(f"OS_STATE_DIR ({p}) must not be or contain the real data folder {q}.")


def empty_state(path):
    """Create the folder (with its sentinel) or empty it. A non-empty folder without the sentinel is refused: nothing is deleted."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    marker = p / SENTINEL
    if not marker.exists():
        if any(p.iterdir()):
            raise ValueError(f"{p} is not empty and was not made by the sandbox; choose an empty OS_STATE_DIR (nothing was deleted).")
    else:
        for child in p.iterdir():
            if child.name == SENTINEL:
                continue
            shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink(missing_ok=True)
    marker.write_text("Throwaway state of the public sandbox. Emptied at every start and reset.\n", encoding="utf-8")
    return p


class Limiter:
    """Sliding-window counter per (kind, visitor) plus one global counter per kind. Thread safe; memory is bounded."""

    MAX_KEYS = 5000

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.hits = {}

    def _count(self, key, window, now, add):
        q = self.hits.setdefault(key, deque())
        while q and now - q[0] >= window:
            q.popleft()
        return q, len(q)

    def allow(self, kind, visitor, limits):
        """(True, 0) and the hit is recorded, or (False, seconds to wait). Nothing is recorded when refused."""
        n, window = limits[kind]
        now = self.clock()
        with self.lock:
            if len(self.hits) > self.MAX_KEYS:
                self.hits = {k: q for k, q in self.hits.items() if q and now - q[-1] < 3600}
            qv, cv = self._count((kind, visitor), window, now, False)
            qg, cg = self._count((kind, "*"), window, now, False)
            if cv >= n:
                return False, max(1, int(window - (now - qv[0])) + 1)
            if cg >= n * GLOBAL_FACTOR:
                return False, max(1, int(window - (now - qg[0])) + 1)
            qv.append(now)
            qg.append(now)
            return True, 0


def classify(method, path):
    """Which rate-limit kind a request belongs to (None = not limited)."""
    if method != "POST":
        return None
    if path in ("/plan-event",) or re.fullmatch(r"/plans/[^/]+/top-up", path):
        return "plan"
    if re.fullmatch(r"/plans/[^/]+/field-kit", path):
        return "kit"
    if path in ("/field-checks", "/field-checks/import"):
        return "field"
    if path in ("/plan-event/preview", "/rank/area"):
        return "compute"
    return None


def classify_read(method, path):
    """Rate-limit kind of a GET in public mode: weather (can cause a call to Open-Meteo) or read; None = not limited (health check, the page's own files)."""
    if method != "GET" or path == "/ping" or path.startswith("/assets/") or path in ("/robots.txt", "/login", "/logout"):
        return None
    if path in ("/weather/week", "/advisory/seasonal") or re.fullmatch(r"/plans/[^/]+/advisory", path):
        return "weather"
    return "read"


def visitor_of(headers, client_host, hops):
    """The visitor address: the X-Forwarded-For entry `hops` from the right (the one added by the host's own proxy), else the socket address."""
    if hops > 0:
        parts = [x.strip() for x in headers.get("x-forwarded-for", "").split(",") if x.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return client_host or "unknown"


def count_files(folder, pattern):
    p = Path(folder)
    return sum(1 for _ in p.glob(pattern)) if p.is_dir() else 0


class KitGate:
    """One kit build at a time (building one uses about 150 MB and 7 to 9 seconds of CPU)."""

    def __init__(self):
        self.lock = threading.Lock()

    def try_enter(self):
        return self.lock.acquire(blocking=False)

    def leave(self):
        if self.lock.locked():
            self.lock.release()


class BodyCap:
    """Pure ASGI middleware: in public mode a request body larger than the cap is refused with 413 WHILE it is read (also when it comes in pieces with no Content-Length)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH") or not is_on():
            return await self.app(scope, receive, send)
        from fastapi import HTTPException
        caps = settings()["caps"]
        cap = caps["import_bytes"] if scope["path"] == "/field-checks/import" else caps["body_bytes"]
        total = 0

        async def capped():
            nonlocal total
            m = await receive()
            if m["type"] == "http.request":
                total += len(m.get("body", b""))
                if total > cap:
                    raise HTTPException(413, f"That request is too large for the public sandbox (limit {cap // 1000} KB).")
            return m

        await self.app(scope, capped, send)
