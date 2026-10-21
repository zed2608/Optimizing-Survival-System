"""Site checklist ("Suriin sa lugar") of the Field Pack: the data file, its quotations, the pack and the page. Display / advice only: nothing here touches a score, a field check or a plan."""
import csv
import re
import subprocess
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import field_pack as bfp  # noqa: E402

CL = ROOT / "data" / "reference" / "site_checklist.csv"
CHK = ROOT / "data" / "reference" / "site_checklist_quote_check.csv"
FIXTURE = ROOT / "tests" / "fixtures" / "field_pack" / "field_kit_plan_urban_20261013_032648"
BANNED = re.compile(r"verified|ligtas|aprubado|kinumpirma|pirmado", re.I)


def rows(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig", newline="")))


def test_ten_items_c1_to_c10():
    r = rows(CL)
    assert [x["item_id"] for x in r] == [f"C{i}" for i in range(1, 11)]
    assert all(x["question_fil"] and x["tip_if_oo"] and x["tip_if_hindi"] and x["tip_if_hindi_sigurado"] for x in r)


def test_quotations_exist_only_when_verified_and_are_in_the_check_file():
    chk = {x["id"]: x for x in rows(CHK)}
    assert len(chk) == 17 and all(x["found_exact"] == "yes" and x["quote"] for x in chk.values())
    for x in rows(CL):
        if x["quote_verified"] == "yes":
            ids = x["quote_ids"].split("|")
            assert ids and x["source_quote"].split(" || ") == [chk[i]["quote"] for i in ids]
            assert all(chk[i]["found_exact"] == "yes" for i in ids)
            assert x["source_url"].startswith("https://")
        else:
            assert x["source_quote"] == ""
    assert [x["item_id"] for x in rows(CL) if x["quote_verified"] == "no"] == ["C8"]          # C8 has no outside source by design


def test_scope_and_the_us_manual_is_not_shown_as_a_philippine_standard():
    for x in rows(CL):
        if "Urban Forestry" in x["source_name"]:
            assert x["source_scope"] == "international (US)"
        if x["source_url"].startswith(("https://apidb.denr", "https://faolex")):
            assert x["source_scope"] == "Philippines (DENR)"


def test_no_forbidden_wording():
    for x in rows(CL):
        text = " ".join(v for k, v in x.items() if k != "source_quote" and k != "source_name")
        assert not BANNED.search(text), x["item_id"]


def test_the_6m_tip_has_its_genera_and_numbers_come_from_quotations():
    c1 = rows(CL)[0]
    assert "6 m" in c1["genus_tip_if_oo"] and c1["applies_to_genus"] == "Bambusa|Cocos" and "6 meters" in c1["source_quote"]
    for x in rows(CL):
        tips = " ".join([x["tip_if_oo"], x["tip_if_middle"], x["tip_if_hindi"], x["tip_if_hindi_sigurado"], x["genus_tip_if_oo"]])
        nums = set(re.findall(r"\d+", tips)) - {"1", "2", "3", "4", "5"}      # small counts of the questions themselves are not measurements
        quote = x["source_quote"] + " " + x["why_fil"] + " " + x["question_fil"]
        for n in nums:
            assert n in quote or n in "12 6 85 97 34 2019 03", (x["item_id"], n)
    c10 = rows(CL)[9]
    assert "85%" in c10["why_fil"] and "Expanded National Greening Program" in c10["why_fil"] and "hindi ng proyektong ito" in c10["why_fil"]
    assert "Walang nahanap na pamantayang Pilipino para sa laki ng butas, mulching at staking" in c10["note"]


def test_the_pack_carries_the_checklist_and_the_genus_tip_depends_on_the_plan():
    text, manifest = bfp.read_kit(FIXTURE)
    pack = bfp.build_pack(text, manifest)
    cl = pack["checklist"]
    assert len(cl["items"]) == 10 and cl["genera"] and all(s["genus"] in cl["genera"] for s in cl["species"])
    assert "Bambusa" not in cl["genera"] and "Cocos" not in cl["genera"]           # the sample plan has neither: the 6 m tip would stay hidden
    c4 = next(i for i in cl["items"] if i["id"] == "C4")
    assert [o["id"] for o in c4["options"]] == ["6_plus", "3_hanggang_6", "mas_mababa_sa_3", "hindi_sigurado"] and all(o["tip"] for o in c4["options"])
    assert cl["items"][0]["genus"] == ["Bambusa", "Cocos"]
    # a plan that has a Coconut block gets the genus
    text2 = text.replace(text.splitlines()[1].split(",")[7], "Coconut", 1)
    assert "Cocos" in bfp.build_pack(text2, manifest)["checklist"]["genera"]


def test_the_page_has_the_section_no_network_call_and_stays_one_small_file():
    text, manifest = bfp.read_kit(FIXTURE)
    page = bfp.render_page(bfp.build_pack(text, manifest))
    assert "Suriin sa lugar" in page and "Hindi ito sinusuri ng system at hindi bahagi ng score" in page and "Ang mga sagot ay hindi sine-save." in page
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    section = app.split("function checklistSection()")[1].split("function homeScreen()")[0]
    assert not re.search(r"\bfetch\(|XMLHttpRequest|sendBeacon|localStorage|save\(\)|store\.", section)       # no network, nothing saved
    assert len(page.encode("utf-8")) < 350_000


def test_the_docker_image_has_the_checklist_file():
    d = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ig = [x.strip() for x in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    assert "site_checklist.csv" in d and (ROOT / "data" / "reference" / "site_checklist.csv").is_file()
    f = "data/reference/site_checklist.csv"
    for pat in ig:
        rx = re.escape(pat).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        assert not (re.fullmatch(rx, f) or f.startswith(pat.rstrip("/") + "/")), pat


def test_the_builder_reproduces_the_file(tmp_path):
    out = tmp_path / "c.csv"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_site_checklist.py"), "--out", str(out)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert out.read_bytes().replace(b"\r\n", b"\n") == CL.read_bytes().replace(b"\r\n", b"\n")
