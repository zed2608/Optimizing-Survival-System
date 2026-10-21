"""Builds data/reference/species_ph_dataset.csv from the project species dataset the team uploaded (reports/overnight/inputs/species_dataset_uploaded.csv.csv).

The team states that this dataset is its species source. The pH range of each species (min_soil_ph, max_soil_ph) is copied as it is, with the authority and the link that the dataset lists.
Nothing is filled in: the build stops when a row is missing, a number is not numeric, min is not below max, or a name does not match the species table (data/processed/species_clean.csv).
Display only: no score reads these ranges.

    python scripts/build_species_ph_dataset.py [--input PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "reports" / "overnight" / "inputs" / "species_dataset_uploaded.csv.csv"
DEFAULT_OUT = ROOT / "data" / "reference" / "species_ph_dataset.csv"
SPECIES = ROOT / "data" / "processed" / "species_clean.csv"
SOURCE_LABEL = "Project species dataset"
COLUMNS = ["species_id", "common_name", "scientific_name", "ph_min", "ph_max", "authority_listed", "reference_url", "source_label"]


def build(src: Path, species: Path = SPECIES) -> pd.DataFrame:
    raw = pd.read_csv(src, dtype=str, keep_default_na=False)
    need = ["common_name", "scientific_name", "min_soil_ph", "max_soil_ph", "reference_authority", "reference_url"]
    missing = [c for c in need if c not in raw.columns]
    if missing:
        raise ValueError(f"the input lacks the columns {missing}")
    sp = pd.read_csv(species)
    if len(raw) != 45:
        raise ValueError(f"expected 45 rows, found {len(raw)}")
    names = raw.common_name.str.strip()
    if names.duplicated().any():
        raise ValueError(f"duplicated names: {sorted(names[names.duplicated()])}")
    by_name = dict(zip(sp.common_name.str.strip(), sp.species_id.astype(int)))
    unknown = sorted(set(names) - set(by_name))
    if unknown:
        raise ValueError(f"names that are not in the species table: {unknown}")
    out = []
    for _, r in raw.iterrows():
        try:
            lo, hi = float(r["min_soil_ph"]), float(r["max_soil_ph"])
        except ValueError as e:
            raise ValueError(f"{r['common_name']}: pH is not numeric ({r['min_soil_ph']!r}, {r['max_soil_ph']!r})") from e
        if not (0 < lo < hi <= 14):
            raise ValueError(f"{r['common_name']}: the range {lo}-{hi} is not a pH range with min below max")
        url = re.sub(r"\s+", " ", r["reference_url"]).strip()
        out.append({"species_id": by_name[r["common_name"].strip()], "common_name": r["common_name"].strip(), "scientific_name": r["scientific_name"].strip(), "ph_min": lo, "ph_max": hi,
                    "authority_listed": r["reference_authority"].strip(), "reference_url": url, "source_label": SOURCE_LABEL})
    df = pd.DataFrame(out, columns=COLUMNS).sort_values("species_id").reset_index(drop=True)
    return df


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_IN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    df = build(a.input)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8", lineterminator="\n")
    print(f"wrote {a.out} ({len(df)} species)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
