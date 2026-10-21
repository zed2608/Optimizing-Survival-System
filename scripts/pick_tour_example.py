"""Picks the example point of the guided tours (R1 W3) BY CODE: among confirmed-zone squares (a seeded sample of 150) the one with the most species that are Good (overall match >= 0.55)
for urban greening in the default October-November window. The tours use that point as "Example point" so that they never depend on what the person selected.
    python scripts/pick_tour_example.py          prints the best five (the result is written into frontend/src/new/tours/tourExample.js by hand)"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
os.environ.setdefault("OS_S_SOURCE", "rf")
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

with TestClient(api_v2.app) as c:
    pts = c.app.state.data.all_points
    ids = [int(i) for i in pts.point_id[pts.zoning_status == "confirmed"].sample(150, random_state=3)]
    rows = []
    for pid in ids:
        r = c.get("/search/point", params={"q": str(pid)}).json()
        if "lat" not in r:
            continue
        j = c.get("/rank", params={"lat": r["lat"], "lon": r["lon"], "purpose": "urban", "limit": 45, "start": "2026-10-22", "end": "2026-11-21", "season_filter": "mark"})
        if j.status_code == 200:
            good = sum(1 for x in j.json()["ranking"] if x["eligible"] and (x["W"] or 0) >= 0.55)
            rows.append((good, pid, r["barangay_display"], bool(j.json()["point"].get("site_ph"))))
    for row in sorted(rows, reverse=True)[:5]:
        print(row)
