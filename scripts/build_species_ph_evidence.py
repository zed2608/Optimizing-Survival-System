#!/usr/bin/env python3
"""
build_species_ph_evidence.py - the pH evidence file of the 45 species (deterministic, NO network).

    python scripts/build_species_ph_evidence.py                      # reads reports/overnight/*.csv, writes data/reference/species_ph_evidence.csv (+ _report.txt)
    python scripts/build_species_ph_evidence.py --crosscheck-dir D --out-dir O

WHY: the cross-check of the species data (reports/overnight/species_ph_crosscheck.csv = what the pages named in species_sources.csv say; species_crosscheck_pass2.csv = a second pass with ICRAF PDFs, FAO EcoCrop and
other reputable pages) showed that the ph_min / ph_max of species_clean.csv cannot be traced to the sources that cite them (only 5 of 45 match exactly). This file is a SEPARATE evidence file with the quoted text; the dashboard reads
it. species_clean.csv and species_sources.csv are NOT touched. Nothing here is "verified": every range is "from a source, not yet signed by the agriculturist".

Columns: species_id, scientific_name, common_name, status (sourced | none), tol_min, tol_max (tolerance), opt_min, opt_max (optimal), listed_min, listed_max (a range the source lists without saying which kind),
verdict_min, verdict_max, verdict_kind (tolerance | listed | optimal_only | none), source_name, source_url, source_rank (1 government, 2 university, 3 international/compilation), source_kind, scope (species | genus_or_group),
quote, alt_sources, conflict (yes | no), note, system_min_draft, system_max_draft (the OLD draft values of species_clean.csv, only for the verification sheet).
"""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["species_id", "scientific_name", "common_name", "status", "tol_min", "tol_max", "opt_min", "opt_max", "listed_min", "listed_max", "verdict_min", "verdict_max", "verdict_kind", "source_name", "source_url",
           "source_rank", "source_kind", "scope", "quote", "alt_sources", "conflict", "note", "system_min_draft", "system_max_draft"]
# The 16 species for which no reputable source with a numeric pH range was found (cross-check pass 2). They stay status = none: nothing is invented.
NONE_IDS = {3: "Dao", 4: "Banaba", 8: "Kamagong", 9: "Katmon", 10: "Batikuling", 11: "Palosapis", 21: "Yakal", 23: "Santol", 32: "Salinggogon", 33: "White Lauan", 34: "Red Lauan", 35: "Bagtikan", 37: "Apitong",
            40: "Peacock Flower Tree", 42: "Weeping Fig (Balete)", 44: "Balai Lamok"}
# Mango (22): "tolerant of alkalinity" in the quote is about alkalinity, not the stated range; the range itself is "pH ranging from 5.5 to 7.5" = listed.
KIND_OVERRIDE = {22: "listed"}
CONFLICT_PH = 0.5         # another species-specific source differs by more than this at the minimum or the maximum
BATIKULING_NOTE = ("JESAM 26(1) 2023 (Engay-Gutierrez et al.) ay binasa nang buo: MaxEnt na pag-aaral; walang pH range; soil type ang pinakamahalagang predictor; "
                   "ang 2,000-3,000 mm ay klima ng rehiyon, hindi requirement")
# species whose page is about a group or the crop in general, not the exact species
GROUP_SCOPE = {13: "the page is about bamboo in general", 27: "the page is a general banana manual (no scientific name on it)", 29: "the page is about citrus in general; calamansi is one of the citrus it lists"}


def host(url):
    return (urlparse(str(url)).hostname or "").lower()


def source_info(url):
    """(source_name, source_kind, rank) from the host of the page. Rank: 1 government (DA, DENR, ERDB, PCAARRD), 2 university journal, 3 FAO, ICRAF, PROSEA, compilations."""
    h = host(url)
    if h.endswith("ecocrop.apps.fao.org"):
        return "FAO EcoCrop", "ecocrop", 3
    if h.endswith("worldagroforestry.org"):
        return "ICRAF Agroforestry Database", "icraf", 3
    if h.endswith("prosea.prota4u.org"):
        return "PROSEA", "prosea", 3
    if h.endswith("theferns.info"):
        return "Useful Tropical Plants (theferns.info)", "compilation_secondary", 3
    if h.endswith("pfaf.org"):
        return "Plants For A Future (pfaf.org)", "compilation_secondary", 3
    if h.endswith("pcaarrd.dost.gov.ph"):
        return "PCAARRD " + ("ISP page" if "ispweb" in h else "page"), "da_pcaarrd", 1
    if h.endswith("da.gov.ph") or h.endswith("denr.gov.ph") or "erdb" in h:
        return "DA/DENR page (" + h + ")", "da_pcaarrd", 1
    if h.endswith(".edu.ph"):
        return "University journal (" + h + ")", "da_pcaarrd", 2
    if h.endswith("fao.org"):
        return "FAO page", "fao_other", 3
    raise ValueError(f"no rank rule for the host {h}")


def nums(text):
    return {float(x) for x in re.findall(r"(?<![\d.])\d+(?:\.\d+)?(?!\d)", str(text))}


def kind_of_quote(q):
    """tolerance | optimal | listed, from the words of the quote (when in doubt: listed)."""
    if re.search(r"toleran|good yield|yield had been reported|can grow", q, re.I):
        return "tolerance"
    if re.search(r"prefer|optimal|optimum|ideal|most suitable", q, re.I):
        return "optimal"
    return "listed"


def parse_ecocrop(quote):
    """'Soil PH||a||b||c||d' -> ((opt_min, opt_max), (abs_min, abs_max)); '-' = missing."""
    t = [x.strip() for x in str(quote).split("||")]
    assert t[0] == "Soil PH" and len(t) == 5, quote
    v = [None if x in ("-", "") else float(x) for x in t[1:]]
    return (v[0], v[1]), (v[2], v[3])


def build(cc_dir, out_dir):
    cc_dir, out_dir = Path(cc_dir), Path(out_dir)
    p1 = pd.read_csv(cc_dir / "species_ph_crosscheck.csv").set_index("species_id")
    p2 = pd.read_csv(cc_dir / "species_crosscheck_pass2.csv")
    p2 = p2[p2.parameter == "ph"].set_index("species_id")
    sc = pd.read_csv(ROOT / "data" / "processed" / "species_clean.csv").set_index("species_id")
    rows = []
    for sid in sorted(sc.index):
        base = {c: "" for c in COLUMNS}
        base.update(species_id=int(sid), scientific_name=sc.loc[sid, "scientific_name"], common_name=sc.loc[sid, "common_name"], system_min_draft=sc.loc[sid, "ph_min"], system_max_draft=sc.loc[sid, "ph_max"])
        if sid in NONE_IDS:
            note = "walang nahanap na sanggunian na may numerong pH range; ang agriculturist ang magpapasya"
            if sid == 10:
                note = BATIKULING_NOTE
            elif sid in (23, 44):                                          # a qualitative sentence only: quoted, never turned into numbers
                q = str(p1.loc[sid, "ph_text_quote"])
                note = f"qualitative na sipi lang, walang numero: {q}"
            elif sid == 37:
                note = ("walang pH range para sa Dipterocarpus grandiflorus; ang FAO na entry na may pH 6-7.5 ay para sa Dipterocarpus alatus (synonym D. philipinensis), ibang species, kaya hindi ginamit; "
                        "ang soil pH ng isang stand ng apitong ay datos ng lugar, hindi requirement")
            elif sid in p2.index and "Checked:" in str(p2.loc[sid, "note"]):
                note = "walang nahanap na sanggunian na may numerong pH range. Binasa: " + str(p2.loc[sid, "note"]).split("Checked:", 1)[1].strip()
            base.update(status="none", verdict_kind="none", conflict="no", note=note)
            rows.append(base)
            continue
        cands = []                                                         # every species-specific numeric range found in the cross-check files: (min, max, kind, url, quote, source_kind)
        eco = None
        if sid in p2.index:
            r = p2.loc[sid]
            if r.source_kind == "ecocrop":
                eco = (parse_ecocrop(r.exact_quote), r.source_url_used, r.exact_quote, str(r.note))
            elif r.source_kind in ("primary_page", "icraf_pdf", "other_reputable") and pd.notna(r.found_min) and pd.notna(r.found_max):
                q = str(r.exact_quote)
                cands.append((float(r.found_min), float(r.found_max), kind_of_quote(q), r.source_url_used, q, r.source_kind))
        r1 = p1.loc[sid]
        if r1.ph_status in ("match", "differs") and pd.notna(r1.ph_min_page):
            q = str(r1.ph_text_quote)
            cands.append((float(r1.ph_min_page), float(r1.ph_max_page), kind_of_quote(q), r1.url, q, "primary_page"))
        base["status"] = "sourced"
        alts = []
        if sid == 6:
            # MANUAL EXCEPTION (Kalumpit): the pass 1 reading found two ranges in one sentence of the theferns page; the sentence is read as optimal 5.5-6.5, tolerance 4.5-7.
            q = str(r1.ph_text_quote)
            assert "5.5 - 6.5" in q and "4.5 - 7" in q, q
            primary = dict(opt=(5.5, 6.5), tol=(4.5, 7.0), listed=(None, None), url=r1.url, quote=q, name_kind=source_info(r1.url), scope="species", note="sipi sa theferns: 'Prefers ... 5.5 - 6.5, tolerating 4.5 - 7' (opt at tol)")
        elif eco is not None:
            (o, a), url, q, enote = eco
            primary = dict(opt=o, tol=a, listed=(None, None), url=url, quote=q, name_kind=source_info(url), scope="species", note=("FAO EcoCrop: optimal at absolute na range" + ("; ang draft ng system ay " + ("kapareho ng ABSOLUTE range ng EcoCrop" if "equals the EcoCrop ABSOLUTE" in enote else "kapareho ng OPTIMAL range ng EcoCrop" if "equals the EcoCrop OPTIMAL" in enote else "hindi kapareho ng alinman") if True else "")))
        else:
            assert cands, f"species {sid}: no numeric pH range anywhere"
            c = cands[0]
            kind = KIND_OVERRIDE.get(sid, c[2])
            primary = dict(opt=(c[0], c[1]) if kind == "optimal" else (None, None), tol=(c[0], c[1]) if kind == "tolerance" else (None, None), listed=(c[0], c[1]) if kind == "listed" else (None, None), url=c[3], quote=c[4],
                           name_kind=source_info(c[3]), scope="genus_or_group" if sid in GROUP_SCOPE else "species", note="saklaw mula sa pahina ng sanggunian" + ("; " + GROUP_SCOPE[sid] if sid in GROUP_SCOPE else ""))
            cands = cands[1:]
        # alternatives: every other species-specific numeric range (never the primary one) + the manual Lemon exception
        for c in cands:
            if (c[3], c[4]) != (primary["url"], primary["quote"]):
                alts.append((c[0], c[1], c[3], c[4]))
        if sid == 43:
            # MANUAL EXCEPTION (Lemon): EcoCrop stays the primary; the PFAF sentences go to alt_sources and the conflict is flagged.
            q = str(r1.ph_text_quote)
            assert "Prefers a pH between 5 and 6" in q and "4.8 to 8.3" in q, q
            alts.append((5.0, 6.0, r1.url, "PFAF: Prefers a pH between 5 and 6; Tolerates a pH in the range 4.8 to 8.3"))
            alts.append((4.8, 8.3, r1.url, "PFAF: Tolerates a pH in the range 4.8 to 8.3"))
        tmin, tmax = primary["tol"]
        omin, omax = primary["opt"]
        lmin, lmax = primary["listed"]
        if tmin is not None:
            vmin, vmax, vk = tmin, tmax, "tolerance"
        elif lmin is not None:
            vmin, vmax, vk = lmin, lmax, "listed"
        else:
            vmin, vmax, vk = omin, omax, "optimal_only"
        name, skind, rank = primary["name_kind"]
        conflict = "yes" if sid == 43 else "no"
        for a, b, _u, _q in alts:
            if abs(a - vmin) > CONFLICT_PH or abs(b - vmax) > CONFLICT_PH:
                conflict = "yes"
        base.update(tol_min=tmin if tmin is not None else "", tol_max=tmax if tmin is not None else "", opt_min=omin if omin is not None else "", opt_max=omax if omin is not None else "",
                    listed_min=lmin if lmin is not None else "", listed_max=lmax if lmin is not None else "", verdict_min=vmin, verdict_max=vmax, verdict_kind=vk, source_name=name, source_url=primary["url"],
                    source_rank=rank, source_kind=skind, scope=primary["scope"], quote=primary["quote"], alt_sources=" || ".join(f"{u} : {q}" for _a, _b, u, q in alts), conflict=conflict, note=primary["note"])
        rows.append(base)
    out = pd.DataFrame(rows, columns=COLUMNS)
    return out


def sanity(df):
    assert len(df) == 45 and list(df.species_id) == sorted(df.species_id)
    assert set(df[df.status == "none"].species_id) == set(NONE_IDS), "the 16 none species differ from the agreed list"
    assert (df.status == "sourced").sum() == 29 and (df.status == "none").sum() == 16, df.status.value_counts().to_dict()
    for r in df.itertuples():
        if r.status == "none":
            assert r.verdict_kind == "none" and all(str(x) == "" for x in (r.tol_min, r.tol_max, r.opt_min, r.opt_max, r.listed_min, r.listed_max, r.verdict_min, r.verdict_max)), f"{r.species_id}: a none species has a number"
            assert str(r.source_url) == "" and str(r.source_rank) == ""
            continue
        assert str(r.source_url).startswith("http"), r.species_id
        assert r.verdict_kind in ("tolerance", "listed", "optimal_only") and r.source_rank in (1, 2, 3)
        assert float(r.verdict_min) <= float(r.verdict_max), r.species_id
        text_numbers = nums(r.quote) | nums(r.alt_sources)
        for lo, hi in ((r.tol_min, r.tol_max), (r.opt_min, r.opt_max), (r.listed_min, r.listed_max)):
            if str(lo) != "":
                assert float(lo) <= float(hi), r.species_id
                for x in (lo, hi):
                    assert float(x) in text_numbers, f"species {r.species_id}: {x} is not in the quote or alt_sources"
        assert not re.search(r"verified|kinumpirma|pirmado", str(r.note) + str(r.quote), re.I) or "hindi pa" in str(r.note).lower(), r.species_id


def write(df, out_dir, cc_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "species_ph_evidence.csv", index=False, encoding="utf-8")
    s = df[df.status == "sourced"]
    same_verdict = int(((s.verdict_min.astype(float) == s.system_min_draft.astype(float)) & (s.verdict_max.astype(float) == s.system_max_draft.astype(float))).sum())
    anyrange = 0
    for r in s.itertuples():
        for lo, hi in ((r.tol_min, r.tol_max), (r.opt_min, r.opt_max), (r.listed_min, r.listed_max)):
            if str(lo) != "" and float(lo) == float(r.system_min_draft) and float(hi) == float(r.system_max_draft):
                anyrange += 1
                break
    L = ["species_ph_evidence_report (made by scripts/build_species_ph_evidence.py; no network; inputs: " + str(cc_dir) + ")", "",
         f"species: {len(df)} | sourced: {len(s)} | none: {(df.status == 'none').sum()}",
         f"verdict_kind: {s.verdict_kind.value_counts().to_dict()}", f"source_kind: {s.source_kind.value_counts().to_dict()}", f"source_rank: {s.source_rank.value_counts().sort_index().to_dict()}",
         f"scope: {s.scope.value_counts().to_dict()}", f"conflict = yes: {int((df.conflict == 'yes').sum())} ({', '.join(str(x) for x in df[df.conflict == 'yes'].species_id)})",
         f"verdict range equal to the OLD draft (species_clean ph_min/ph_max): {same_verdict} of {len(s)}", f"the OLD draft range equal to ANY range of the evidence (tolerance, optimal or listed): {anyrange} of {len(s)}",
         "none species: " + ", ".join(f"{i} {n}" for i, n in NONE_IDS.items())]
    (out_dir / "species_ph_evidence_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    return L


def build_climate_agreement(cc_dir):
    """species_climate_agreement.csv: for rain and temperature, does the page of the cited source match the draft? agreement = match when EITHER cross-check pass says match (pass 1 status, pass 2 agreement).
    The source URL and the quote are given ONLY for a match; the API shows the source link of a rain / temperature value only then."""
    cc_dir = Path(cc_dir)
    p1 = pd.read_csv(cc_dir / "species_ph_crosscheck.csv").set_index("species_id")
    p2 = pd.read_csv(cc_dir / "species_crosscheck_pass2.csv")
    sc = pd.read_csv(ROOT / "data" / "processed" / "species_clean.csv")
    rows = []
    for sid in sorted(int(x) for x in sc.species_id):
        for par, col in (("rain", "rain_status"), ("temp", "temp_status")):
            url = quote = ""
            agree = "no_match"
            if sid in p1.index and p1.loc[sid, col] == "match":
                agree, url, quote = "match", str(p1.loc[sid, "url"]), str(p1.loc[sid, par + "_text_quote"])
            q = p2[(p2.species_id == sid) & (p2.parameter == par) & (p2.agreement == "match")]
            if len(q) and agree != "match":
                agree, url, quote = "match", str(q.iloc[0].source_url_used), str(q.iloc[0].exact_quote)
            rows.append({"species_id": sid, "parameter": par, "agreement": agree, "source_url_if_match": url if agree == "match" else "", "quote_if_match": quote if agree == "match" else ""})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--crosscheck-dir", default=str(ROOT / "reports" / "overnight"))
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "reference"))
    a = ap.parse_args()
    df = build(a.crosscheck_dir, a.out_dir)
    sanity(df)
    print("\n".join(write(df, a.out_dir, a.crosscheck_dir)))
    ag = build_climate_agreement(a.crosscheck_dir)
    ag.to_csv(Path(a.out_dir) / "species_climate_agreement.csv", index=False, encoding="utf-8")
    print("climate agreement:", ag.groupby("parameter").agreement.value_counts().to_dict())


if __name__ == "__main__":
    sys.exit(main())
