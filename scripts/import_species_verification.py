"""
Read the CSV that the agriculturist's form came back as and write a REPORT (stage C1). It checks the file (known species and attribute, a valid verdict), counts how many values were
confirmed, replaced or not answered, and writes two NEW dated files in data/validation/. It does NOT change species_clean.csv, the release hash or any score: a replaced value goes into a
new release of the species data, decided by the team.

    python scripts/import_species_verification.py returned.csv [--out data/validation]
Exit code 2 and nothing written when the file has a problem (every problem is listed).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import species_verification as sv  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("returned", help="the returned CSV (the filled copy of species_verification_sheet_<date>.csv)")
    ap.add_argument("--out", default=str(sv.VALIDATION), help="folder for the two new files (default: data/validation)")
    ap.add_argument("--processed", default=str(sv.PROCESSED), help="the processed data to compare with (default: data/processed; it is only read)")
    a = ap.parse_args(argv)
    returned = sv.read_returned(a.returned)
    checked, problems = sv.check_returned(returned, a.processed)
    if problems:
        print(f"The file was NOT accepted ({len(problems)} problems); nothing was written:")
        for p in problems[:50]:
            print("  -", p)
        if len(problems) > 50:
            print(f"  ... and {len(problems) - 50} more")
        sys.exit(2)
    total = len(sv.build_rows(a.processed))
    s = sv.summarise(checked, total)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    csv_path = sv.dated_path(out, "species_verification", "csv")
    sv.write_csv(checked, csv_path)
    report = csv_path.with_suffix(".txt")
    n = 2
    while report.exists():
        report = csv_path.with_name(f"{csv_path.stem}-{n}.txt")
        n += 1
    tag, hash12 = sv.release_info(a.processed)
    lines = [f"Species verification report ({stamp}); form of release {tag} {hash12}; NOT applied to the species data.",
             f"rows in the form: {s['rows_in_form']} | confirmed (Tama): {s['correct']} | replaced (Palitan): {s['replaced']} | no answer: {s['no_answer']}"]
    lines += [f"  {sid} {name} {attr}: {old} -> {new}  ({remark})" for sid, name, attr, old, new, remark in s["replacements"]]
    lines.append("Nothing in data/processed was changed. Replaced values need a new release of the species data (new tag and hash), decided by the team.")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"CSV   : {csv_path}")
    print(f"Report: {report}")
    return s


if __name__ == "__main__":
    main()
