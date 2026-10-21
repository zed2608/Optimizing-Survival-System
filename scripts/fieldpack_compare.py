"""Before / after pictures of the point layout: an irregular (L-shaped) area drawn around a planting place, planned with 1 species and with 3 species, laid out in rows (before) and as
spaced points (after). Makes the kits through the API in this process (a temporary state folder), then renders page 1 and page 2 of each field-map.pdf to PNG (pymupdf).
    python scripts/fieldpack_compare.py <output folder>
Needs the processed data and the scores (like the tests). Nothing is sent anywhere and nothing in data/ is written."""
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("OS_S_SOURCE", "rules")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import field_kit as fk  # noqa: E402
import field_verify as fv  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="fp_compare_"))
    with TestClient(api_v2.app) as c:
        d = c.app.state.data
        d.field_db = work / "field" / "f.db"
        d.work = work
        fv.connect(d.field_db).close()
        api_v2.refresh_field(d)
        base = c.post("/plan-event", json={"purpose": "planting", "n_saplings": 150, "seed": 4}).json()["plan"][0]
        lon, lat = base["lon"], base["lat"]
        e, n = 0.0010, 0.0009                                              # about 110 m east-west, 100 m north-south
        L = [[lon - e, lat - n], [lon + 2.2 * e, lat - n], [lon + 2.2 * e, lat + 0.4 * n], [lon + 0.5 * e, lat + 0.4 * n], [lon + 0.5 * e, lat + 2.0 * n], [lon - e, lat + 2.0 * n], [lon - e, lat - n]]
        poly = {"type": "Polygon", "coordinates": [L]}
        ids = [int(base["species_id"])]
        r3 = c.get("/species").json()
        all_ids = [int(s["species_id"]) for s in (r3 if isinstance(r3, list) else r3.get("species", r3.get("items", [])))][:3]
        cases = {"1species": [ids[0]], "3species": all_ids}
        for name, sp in cases.items():
            for mode in ("rows", "spaced"):
                fk.CFG["point_layout"] = mode
                j = c.post("/plan-event", json={"purpose": "planting", "n_saplings": 120, "seed": 4, "polygon": poly, "species_ids": sp, "campaign": {"name": f"{name} {mode}", "unit": "QA"}})
                if j.status_code != 200:
                    print(name, mode, "plan failed:", j.status_code, j.text[:160])
                    continue
                pid = j.json()["plan_id"]
                r = c.post(f"/plans/{pid}/field-kit")
                z = zipfile.ZipFile(io.BytesIO(c.get(r.json()["download_url"]).content))
                names = [x for x in z.namelist() if x.endswith("field-map.pdf")]
                if not names:
                    print(name, mode, "no PDF in the kit")
                    continue
                import pymupdf
                doc = pymupdf.open(stream=z.read(names[0]), filetype="pdf")
                for pg in (0, 1):
                    if pg < len(doc):
                        doc[pg].get_pixmap(dpi=80).save(str(out / f"{name}_{mode}_page{pg + 1}.png"))
                print(name, mode, "ok", len(doc), "pages,", j.json()["summary"].get("saplings_placed"), "trees")
    fk.CFG["point_layout"] = "spaced"


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "reports/overnight/v2_fieldpack_shots/compare")
