"""
Stored Field Packs for the planter link (stage A2). A pack is the single HTML page of pipeline/field_pack.py, kept as <work>/packs/<token>.html with its details in <token>.json.

  - the token is secrets.token_urlsafe(16) (128 random bits, 22 characters): it is the ONLY thing that opens the page, so it is never written to a log or an error message (use short());
  - ONE live pack per plan (a new one replaces the old one), at most MAX_PACKS in all (the oldest is replaced when full);
  - every pack expires after at most TTL_HOURS (24) and never later than the next sandbox reset (the caller passes the latest allowed end); expired files are removed by cleanup();
  - lookup compares the token with EVERY stored token in constant time and answers only "found" or "not found" (unknown, expired and revoked look the same);
  - the folder lives in the throw-away state of the sandbox, so a restart or a reset removes every pack (the dashboard says so).
Nothing here reads or writes the plans, the kits or the field checks.
"""
from __future__ import annotations

import hmac
import json
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

DIR_NAME = "packs"
MAX_PACKS = 30
TTL_HOURS = 24.0
TOKEN_BYTES = 16
TOKEN_SHAPE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
NOT_FOUND_BODY = ("Hindi mabuksan ang link na ito. Humingi ng bagong link sa nagbigay nito.\n"
                  "This link cannot be opened. Ask the person who gave it to you for a new link.")   # the one body for every bad, expired, revoked or unknown token (same text, same length: it never says which)
PLAN_ID = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def packs_dir(work):
    return Path(work) / DIR_NAME


def short(token):
    """A token for logs and messages: the first 4 characters only."""
    return (token or "")[:4] + "…"


def new_token():
    return secrets.token_urlsafe(TOKEN_BYTES)


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_meta(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _drop(folder, token):
    for ext in (".html", ".json"):
        (folder / f"{token}{ext}").unlink(missing_ok=True)


def entries(work):
    """[(token, meta)] of every stored pack that has both files and readable details, oldest first."""
    folder = packs_dir(work)
    out = []
    if folder.is_dir():
        for j in folder.glob("*.json"):
            token = j.stem
            meta = _read_meta(j)
            if meta and TOKEN_SHAPE.match(token) and (folder / f"{token}.html").is_file():
                out.append((token, meta))
    return sorted(out, key=lambda e: e[1].get("created", 0))


def cleanup(work, now=None):
    """Remove expired packs and files that are not a complete pack (a half-written one). Returns how many packs were removed."""
    now = time.time() if now is None else now
    folder = packs_dir(work)
    if not folder.is_dir():
        return 0
    good = {t for t, _ in entries(work)}
    n = 0
    for f in list(folder.iterdir()):
        if f.suffix in (".html", ".json") and f.stem not in good:
            f.unlink(missing_ok=True)
    for token, meta in entries(work):
        if meta.get("expires", 0) <= now:
            _drop(folder, token)
            n += 1
    return n


def store(work, plan_id, html, *, pack_id, check_code, latest_end=None, now=None, max_packs=None, ttl_hours=None):
    """Save a pack and return its details. expires = now + ttl_hours, but never after latest_end (the next sandbox reset). Replaces the plan's old pack and, when full, the oldest one."""
    if not PLAN_ID.match(plan_id or ""):
        raise ValueError("bad plan id")
    now = time.time() if now is None else now
    max_packs = MAX_PACKS if max_packs is None else max_packs
    ttl_hours = min(TTL_HOURS, TTL_HOURS if ttl_hours is None else ttl_hours)          # never more than 24 hours, whatever the caller asks
    folder = packs_dir(work)
    folder.mkdir(parents=True, exist_ok=True)
    cleanup(work, now)
    replaced = False
    for token, meta in entries(work):
        if meta.get("plan_id") == plan_id:
            _drop(folder, token)
            replaced = True
    live = entries(work)
    while len(live) >= max_packs:                       # full: the oldest goes
        _drop(folder, live[0][0])
        live = live[1:]
    expires = now + ttl_hours * 3600
    if latest_end is not None:
        expires = min(expires, latest_end)
    if expires <= now:
        raise ValueError("the sandbox is about to reset: try again in a minute")
    token = new_token()
    meta = {"plan_id": plan_id, "created": now, "expires": expires, "pack_id": pack_id, "check_code": check_code}
    (folder / f"{token}.html").write_bytes(html.encode("utf-8"))                  # bytes: no line-ending change on Windows, the page is served exactly as built
    (folder / f"{token}.json").write_text(json.dumps(meta), encoding="utf-8")        # the details come last: a pack without them is not served
    return {"token": token, "plan_id": plan_id, "expires": expires, "expires_at": _iso(expires), "pack_id": pack_id, "check_code": check_code, "replaced": replaced}


def lookup(work, token, now=None):
    """The HTML (bytes) for a valid, unexpired token, else None. The token is compared with every stored token in constant time; nothing says why it was refused."""
    now = time.time() if now is None else now
    if not isinstance(token, str) or not TOKEN_SHAPE.match(token):
        token = "x" * 22                                # a token of the wrong shape is checked like any other (and fails)
    found = None
    for t, meta in entries(work):
        if hmac.compare_digest(t.encode("ascii"), token.encode("ascii", "ignore")) and meta.get("expires", 0) > now:
            found = t
    if found is None:
        return None
    try:
        return (packs_dir(work) / f"{found}.html").read_bytes()
    except OSError:
        return None


def info(work, plan_id, now=None):
    """The live pack of a plan: {token, expires_at, pack_id, check_code} or None."""
    now = time.time() if now is None else now
    for token, meta in entries(work):
        if meta.get("plan_id") == plan_id and meta.get("expires", 0) > now:
            return {"token": token, "expires": meta["expires"], "expires_at": _iso(meta["expires"]), "pack_id": meta.get("pack_id"), "check_code": meta.get("check_code")}
    return None


def revoke(work, plan_id):
    """Delete the plan's pack (and so its link). Returns True when there was one."""
    folder = packs_dir(work)
    gone = False
    for token, meta in entries(work):
        if meta.get("plan_id") == plan_id:
            _drop(folder, token)
            gone = True
    return gone
