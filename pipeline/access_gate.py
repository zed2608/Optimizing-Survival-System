"""
Shared access code for the public sandbox (stage B, branch field-pack). OFF unless OS_ACCESS_CODE is set (then nothing in the service changes).

With the code set, every page and API call needs a cookie that /login gives for the right code:
  - cookie value  "<expiry epoch>.<hmac>"; the hmac key is derived from the code, so CHANGING THE CODE makes every old cookie useless at once;
  - HttpOnly, SameSite=Lax, Secure (switch off with OS_COOKIE_SECURE=0 for plain http on a laptop), lifetime OS_ACCESS_HOURS (default 12);
  - wrong codes are limited (kind "login": 10 per 10 minutes per visitor, 5 times that for everybody together);
  - open without the code: /ping (health check for the host), /login, /logout, /robots.txt.
No code is ever written to a log, a URL or a response.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import os
import re
import time
import urllib.parse

COOKIE = "os_access"
EXEMPT = ("/ping", "/login", "/logout", "/robots.txt", "/favicon.ico")       # /favicon.ico: browsers ask for it by themselves (the planter page has none); the answer is an empty 204
# Stage A2: the planter link. A planter has no access code: /field/<token>/ is opened by its TOKEN (random, expires, checked by the route). Exactly one path segment after /field/,
# so that every other /field/... path stays behind the code, and a wrong token gets the same plain 404 as any other (not a redirect to the login page).
FIELD_PATH = re.compile(r"^/field/[^/]+/?$")


def is_field_path(path):
    return bool(FIELD_PATH.match(path or ""))

HOURS = 12.0
NOTICE = "Demo / sandbox. Data is provisional and not yet signed off by the agriculturist. Entries reset regularly."


def code():
    return os.environ.get("OS_ACCESS_CODE", "").strip()


def is_on():
    return bool(code())


def hours():
    try:
        v = float(os.environ.get("OS_ACCESS_HOURS", ""))
        return v if v > 0 else HOURS
    except ValueError:
        return HOURS


def secure_cookie():
    return os.environ.get("OS_COOKIE_SECURE", "1").strip().lower() not in ("0", "false", "no", "off")


def _key(c):
    return hashlib.sha256(("os-access-v1|" + c).encode("utf-8")).digest()


def make_cookie(now=None):
    exp = int((time.time() if now is None else now) + hours() * 3600)
    sig = hmac.new(_key(code()), str(exp).encode("ascii"), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def cookie_ok(value, now=None):
    """True when the cookie was made with the CURRENT code and has not expired."""
    if not is_on() or not value or "." not in value:
        return False
    exp, _, sig = value.partition(".")
    if not exp.isdigit():
        return False
    good = hmac.new(_key(code()), exp.encode("ascii"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and int(exp) > (time.time() if now is None else now)


def code_ok(candidate):
    return is_on() and hmac.compare_digest(hashlib.sha256((candidate or "").encode("utf-8")).digest(), hashlib.sha256(code().encode("utf-8")).digest())


def safe_next(value):
    """Where to go after login: only a path on this site (no other address, no //)."""
    v = value or "/"
    if not v.startswith("/") or v.startswith("//") or "\\" in v or "\n" in v or "\r" in v:
        return "/"
    return v


def cookie_header(value, clear=False):
    parts = [f"{COOKIE}={'' if clear else value}", "Path=/", "HttpOnly", "SameSite=Lax", f"Max-Age={0 if clear else int(hours() * 3600)}"]
    if secure_cookie():
        parts.append("Secure")
    return "; ".join(parts)


def parse_form(body):
    return {k: v[0] for k, v in urllib.parse.parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True).items()}


def login_page(error="", next_path="/"):
    e = f'<p class="err" role="alert">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Access code</title>
<style>
:root {{ color-scheme: light dark; --bg:#f8fafc; --fg:#0f172a; --card:#fff; --line:#cbd5e1; --acc:#059669; --warn:#fde68a; --warnfg:#422006; --err:#b91c1c; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f172a; --fg:#f8fafc; --card:#1e293b; --line:#475569; }} }}
body {{ margin:0; font:16px/1.45 system-ui,sans-serif; background:var(--bg); color:var(--fg); }}
.notice {{ background:var(--warn); color:var(--warnfg); padding:10px 16px; font-size:13px; font-weight:600; text-align:center; }}
main {{ max-width:420px; margin:12vh auto 0; padding:0 16px; }}
form {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:20px; }}
h1 {{ font-size:20px; margin:0 0 6px; }} p {{ margin:0 0 14px; }}
input {{ width:100%; box-sizing:border-box; padding:12px; font-size:16px; border:1px solid var(--line); border-radius:8px; background:transparent; color:inherit; }}
button {{ margin-top:12px; width:100%; padding:12px; font-size:16px; font-weight:600; border:0; border-radius:8px; background:var(--acc); color:#fff; }}
.err {{ color:var(--err); font-weight:600; }}
</style></head><body>
<div class="notice">{html.escape(NOTICE)}</div>
<main><form method="post" action="/login">
<h1>Access code</h1><p>This demo is shared with the adviser, the panel and the team. Type the code you were given.</p>{e}
<input type="hidden" name="next" value="{html.escape(next_path)}">
<label for="c" style="display:block;margin-bottom:6px">Access code</label>
<input id="c" name="code" type="password" autocomplete="current-password" autofocus required>
<button type="submit">Open</button></form></main></body></html>"""
