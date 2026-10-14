"""
Make the verification form for the licensed agriculturist: a PDF to print and a CSV to fill (stage C1). Reads data/processed (never changes it) and writes NEW dated files in data/validation/.

    python scripts/make_species_verification_sheet.py [--out data/validation]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import species_verification as sv  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out", default=str(sv.VALIDATION), help="folder for the two new files (default: data/validation)")
    ap.add_argument("--processed", default=str(sv.PROCESSED), help="the processed data to read (default: data/processed; it is only read)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag, hash12 = sv.release_info(a.processed)
    rows = sv.build_rows(a.processed)
    pdf = sv.dated_path(out, "species_verification_sheet", "pdf")
    csv_path = pdf.with_suffix(".csv")
    n = 2
    while csv_path.exists():                       # never overwrite the CSV either (the number follows the PDF's name)
        csv_path = pdf.with_name(f"{pdf.stem}-{n}.csv")
        n += 1
    sv.write_pdf(rows, pdf, tag, hash12, built_on=datetime.now().strftime("%Y-%m-%d %H:%M"))
    sv.write_csv(rows, csv_path)
    print(f"{len(rows)} rows ({len({r['species_id'] for r in rows})} species) | release {tag} {hash12}")
    print(f"PDF : {pdf}")
    print(f"CSV : {csv_path}")
    return pdf, csv_path


if __name__ == "__main__":
    main()
