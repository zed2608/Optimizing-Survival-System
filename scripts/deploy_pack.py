"""Refresh deploy/ from the local scores (run after scripts/rebuild_scores.py, then commit deploy/). Prints sizes and the sha256 of the database."""
import gzip, hashlib, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = {"db": ROOT / "data/processed/scores/site_scores.db", "run": ROOT / "data/processed/scores/score_run.json", "meta": ROOT / "data/processed/models/rf_site_suitability_meta.json"}
DST = ROOT / "deploy"


def main():
    missing = [str(p) for p in SRC.values() if not p.is_file()]
    if missing:
        sys.exit("Missing: " + ", ".join(missing) + "  (run python scripts/rebuild_scores.py first)")
    DST.mkdir(exist_ok=True)
    with open(SRC["db"], "rb") as f, open(DST / "site_scores.db.gz", "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as g:
        shutil.copyfileobj(f, g)                                       # no file name and no time inside: the same database always gives the same bytes
    shutil.copyfile(SRC["run"], DST / "score_run.json")
    shutil.copyfile(SRC["meta"], DST / "rf_site_suitability_meta.json")
    h = hashlib.sha256()
    with open(SRC["db"], "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print(f"site_scores.db.gz {(DST / 'site_scores.db.gz').stat().st_size / 1e6:.1f} MB | sha256 of the unpacked database {h.hexdigest()}")
    print("Now copy the first 16 characters into deploy/MANIFEST.txt and commit deploy/.")


if __name__ == "__main__":
    main()
