#!/usr/bin/env python3
"""
build_site_checklist.py - writes data/reference/site_checklist.csv ("Suriin sa lugar" of the Field Pack): ten yes / no / not sure questions with a short tip for each answer.

    python scripts/build_site_checklist.py [--check data/reference/site_checklist_quote_check.csv]

Display / advice only: the answers are given by the planter, the system checks nothing, nothing here is part of a score. Every quotation is COPIED from the quote-check file (Stage 0: each text was found on the page of its
document); an item has a source_quote only when quote_verified = yes. No number appears in a tip unless it is in a verified quotation. Q1/Q2 are Philippine (DENR) documents, Q3 is a US manual (international (US)).

Columns: item_id, question_fil, why_fil, options (ids, |), option_labels (Filipino, |), source_name, source_url, source_scope, source_quote (several quotations joined by ' || '), quote_ids, quote_verified (yes/no),
applies_to_genus (blank = every plan; it applies ONLY to the genus_tip_* columns), tip_if_oo (first option), tip_if_middle (second option when there are four), tip_if_hindi, tip_if_hindi_sigurado, genus_tip_if_oo, note.
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Q1 = ("DENR Administrative Order No. 97-34, Guidelines on Tree Planting Near Electric Power Line Systems (27 Nov 1997)", "Philippines (DENR)")
Q2 = ("DENR Administrative Order No. 2019-03, Revised Implementing Rules and Regulations of Executive Order No. 193, s. 2015: Expanding and Enhancing the Coverage of the National Greening Program (8 Jan 2019)", "Philippines (DENR)")
Q3 = ("Urban Forestry: A Manual for the State Forestry Agencies in the Southern Region, Unit: Site and Tree Selection (USDA Forest Service Southern Region and Southern Research Station, Southern Group of State Foresters)", "international (US)")
URLS = {"Q1": "https://apidb.denr.gov.ph/infores/uploads/policy/1997/FOR_DAO-97-34.pdf", "Q2": "https://faolex.fao.org/docs/pdf/phi190722.pdf",
        "Q3": "https://www.fao.org/uploads/media/Urban%20Forestry%20Manual_site%20and%20tree%20selection.pdf"}
NO_STANDARD = "Walang nahanap na pamantayang Pilipino para sa laki ng butas, mulching at staking; hindi sakop ng checklist na ito."
YNU = "oo|hindi|hindi_sigurado"
YNU_L = "Oo|Hindi|Hindi sigurado"
COLUMNS = ["item_id", "question_fil", "why_fil", "options", "option_labels", "source_name", "source_url", "source_scope", "source_quote", "quote_ids", "quote_verified", "applies_to_genus", "tip_if_oo", "tip_if_middle",
           "tip_if_hindi", "tip_if_hindi_sigurado", "genus_tip_if_oo", "note"]

ITEMS = [
    dict(item_id="C1", question_fil="May kable ng kuryente o poste sa ibabaw ng lugar na itatamnan?", why_fil="Ang mga puno na tumataas hanggang sa kable ay maaaring makagambala sa linya ng kuryente.", options=YNU, option_labels=YNU_L,
         src=Q1, ids=["Q1a", "Q1b"], applies_to_genus="Bambusa|Cocos",
         tip_if_oo="Pumili ng maliit na uri at ilayo sa kable. Ayon sa DENR AO 97-34, ang mga ornamental na puno ay itinatanim nang hindi bababa sa 3 m ang layo sa linya ng kuryente.",
         tip_if_hindi="Walang kable sa ibabaw. Tingnan pa rin ang paligid bago maghukay.", tip_if_hindi_sigurado="Tingnan muli ang itaas ng lugar, o itanong sa LGU o sa kumpanya ng kuryente.",
         genus_tip_if_oo="Huwag itanim ang Bamboo o Niyog sa ilalim o sa loob ng 6 m ng kable (DENR AO 97-34).", note=""),
    dict(item_id="C2", question_fil="May tubo o kable sa ilalim ng lupa (tubig, kuryente, internet) sa lugar?", why_fil="Ang paghuhukay ay maaaring makasira ng tubo o kable sa ilalim.", options=YNU, option_labels=YNU_L,
         src=Q3, ids=["Q3e"], applies_to_genus="", tip_if_oo="Itanong sa LGU o sa utility bago maghukay.", tip_if_hindi="Ituloy, pero tumigil at itanong kung may makita kang tubo o kable sa paghuhukay.",
         tip_if_hindi_sigurado="Itanong sa LGU o sa utility bago maghukay.", genus_tip_if_oo="",
         note="Ang sipi ay mula sa manwal ng Estados Unidos; ang layo roon ay para sa malalaking puno at hindi pamantayang Pilipino."),
    dict(item_id="C3", question_fil="Naiipon o bumabaha ba ang tubig pagkatapos ng ulan?", why_fil="Ang lugar na hindi umaagos ang tubig ay maaaring hindi angkop sa maraming puno.", options=YNU, option_labels=YNU_L,
         src=Q3, ids=["Q3a", "Q3b"], applies_to_genus="",
         tip_if_oo="Subukan: maghukay ng butas na 12 x 12 pulgada, punuin ng tubig, at tingnan kung maubos sa loob ng isang oras. Kung may creek o waterlogging, markahan ito sa field check ng app bilang \"creek_or_waterlogged\" (Hindi matataniman).",
         tip_if_hindi="Walang naiipong tubig na napansin. Maaari pa ring subukan ang butas na 12 x 12 pulgada.", tip_if_hindi_sigurado="Subukan: maghukay ng butas na 12 x 12 pulgada, punuin ng tubig, at tingnan kung maubos sa loob ng isang oras.",
         genus_tip_if_oo="", note="Ang pagsubok ay mula sa manwal ng Estados Unidos. Hindi binabago ng checklist na ito ang field check."),
    dict(item_id="C4", question_fil="Ilang oras ng diretsong sikat ng araw ang natatanggap ng lugar?", why_fil="Ang mga punong mahilig sa araw ay nangangailangan ng sapat na sikat; ang iba ay kayang tumubo sa lilim.",
         options="6_plus|3_hanggang_6|mas_mababa_sa_3|hindi_sigurado", option_labels="6 oras o higit pa|3 hanggang 6 oras|Mas mababa sa 3 oras|Hindi sigurado", src=Q3, ids=["Q3c"], applies_to_genus="",
         tip_if_oo="Sapat para sa mga punong mahilig sa araw (ayon sa manwal, kailangan nila ng hindi bababa sa 6 oras).", tip_if_middle="Mas bagay ang mga puno na tumatanggap ng lilim; tingnan ang shade tolerance ng species sa listahan sa ibaba.",
         tip_if_hindi="Pumili ng mga punong tumatanggap ng lilim; tingnan ang shade tolerance ng species sa listahan sa ibaba.", tip_if_hindi_sigurado="Obserbahan ang lugar sa umaga at hapon bago magtanim.", genus_tip_if_oo="",
         note="Ang shade tolerance at light preference sa listahan ay galing sa species table (draft)."),
    dict(item_id="C5", question_fil="May sapat bang espasyo para sa laki ng puno kapag mature na (taas, lapad ng sanga, ugat), malayo sa gusali at bakod?", why_fil="Ang puno ay lumalaki; kailangan ng puwang ang sanga at ugat.", options=YNU, option_labels=YNU_L,
         src=Q3, ids=["Q3f"], applies_to_genus="", tip_if_oo="Mabuti. Tingnan pa rin ang laki ng puno kapag mature na sa species card.", tip_if_hindi="Pumili ng mas maliit na species o ilipat ang lugar na tataniman.",
         tip_if_hindi_sigurado="Tingnan ang mature height at canopy spread ng species sa species card at ikumpara sa lugar.", genus_tip_if_oo="", note="Walang bilang dito: ang sipi ay walang bilang para sa layo."),
    dict(item_id="C6", question_fil="May mapagkukunan ng tubig na maaabot para sa pagdidilig sa tuyong buwan?", why_fil="Ang pagdidilig ay bahagi ng pag-aalaga ng itinanim na punla.", options=YNU, option_labels=YNU_L,
         src=Q2, ids=["Q2f", "Q2i"], applies_to_genus="", tip_if_oo="Mabuti. Planuhin kung sino ang magdidilig at gaano kadalas.",
         tip_if_hindi="Ayon sa DENR AO 2019-03, may rainwater-harvesting facilities malapit sa taniman bilang pagkukunan ng tubig sa tuyong panahon. Pag-isipan kung maaaring magtayo nito, o pumili ng mas matibay sa tagtuyot na species.",
         tip_if_hindi_sigurado="Alamin muna kung saan kukuha ng tubig bago magtanim.", genus_tip_if_oo="", note=""),
    dict(item_id="C7", question_fil="May panganib ba ng hayop na nagpapastol o ng sunog sa paligid?", why_fil="Ang hayop at sunog ay maaaring makasira ng bagong tanim.", options=YNU, option_labels=YNU_L,
         src=Q2, ids=["Q2d", "Q2e"], applies_to_genus="", tip_if_oo="Ayon sa DENR AO 2019-03, kasama sa pag-aalaga ang pagpapanatili ng fire breaks at foot patrolling. Planuhin ang bakod at ang pagbabantay.",
         tip_if_hindi="Walang napansing panganib. Bantayan pa rin ang taniman.", tip_if_hindi_sigurado="Itanong sa mga kapitbahay o sa barangay kung may nagpapastol o may sunog sa lugar.", genus_tip_if_oo="", note=""),
    dict(item_id="C8", question_fil="Alam mo ba kung sino ang may-ari ng lupa at may pahintulot na?", why_fil="Kailangan ang pahintulot ng may-ari o ng ahensiyang namamahala bago magtanim.", options=YNU, option_labels=YNU_L,
         src=("Mga kondisyon ng zone sa app (ZONE_CONDITIONS)", "app"), ids=[], applies_to_genus="", tip_if_oo="Mabuti. Itala ang pangalan ng nagbigay ng pahintulot.", tip_if_hindi="Huwag munang magtanim. Itanong muna sa LGU o sa may-ari.",
         tip_if_hindi_sigurado="Itanong sa LGU o sa MENRO kung sino ang may-ari at kung kailangan ng pahintulot.", genus_tip_if_oo="", note="Ipinapakita rin ang kondisyon ng zone ng bawat block sa planong ito kung mayroon."),
    dict(item_id="C9", question_fil="Nagsimula na ba ang tag-ulan?", why_fil="Ang pagtatanim ay nagsisimula sa simula ng tag-ulan.", options=YNU, option_labels=YNU_L, src=Q2, ids=["Q2h"], applies_to_genus="",
         tip_if_oo="Ayon sa DENR AO 2019-03, ang pagtatanim ay laging nagsisimula sa simula ng tag-ulan.", tip_if_hindi="Ayon sa DENR AO 2019-03, ang pagtatanim ay laging nagsisimula sa simula ng tag-ulan. Maghintay muna o magplano ng pagdidilig.",
         tip_if_hindi_sigurado="Tingnan ang anunsyo ng PAGASA, o ang tab na Weather ng app.", genus_tip_if_oo="", note=""),
    dict(item_id="C10", question_fil="May magbabantay, magdidilig, magbubunot ng damo at magpapalit ng patay na punla?", why_fil="Ang pag-aalaga ay tuloy-tuloy. Ang 85% na survival at 5 taon na pag-aalaga ay pamantayan ng Expanded National Greening Program, hindi ng proyektong ito.",
         options=YNU, option_labels=YNU_L, src=Q2, ids=["Q2a", "Q2b", "Q2c", "Q2f", "Q2g"], applies_to_genus="",
         tip_if_oo="Mabuti. Sa ENGP, ang pag-aalaga ay para sa limang (5) taon: ring weeding o strip brushing, replanting, watering.",
         tip_if_hindi="Magtalaga muna ng mag-aalaga bago magtanim. Sa ENGP, ang pag-aalaga ay para sa limang (5) taon.", tip_if_hindi_sigurado="Pag-usapan muna kung sino ang mag-aalaga bago magtanim.", genus_tip_if_oo="", note=NO_STANDARD),
]


def build(check_path):
    chk = {r["id"]: r for r in csv.DictReader(open(check_path, encoding="utf-8-sig", newline=""))}
    rows = []
    for it in ITEMS:
        name, scope = it["src"]
        quotes, ok = [], True
        for i in it["ids"]:
            r = chk.get(i)
            if not r or r["found_exact"] != "yes" or not r["quote"]:
                ok = False
                continue
            quotes.append(r["quote"])
        verified = bool(it["ids"]) and ok and len(quotes) == len(it["ids"])
        url = next((URLS[i[:2]] for i in it["ids"]), "")
        note = it["note"]
        if it["ids"] and not verified:
            note = (note + " " if note else "") + "walang naberipikang sipi"
        rows.append({"item_id": it["item_id"], "question_fil": it["question_fil"], "why_fil": it["why_fil"], "options": it["options"], "option_labels": it["option_labels"], "source_name": name, "source_url": url,
                     "source_scope": scope, "source_quote": " || ".join(quotes) if verified else "", "quote_ids": "|".join(it["ids"]), "quote_verified": "yes" if verified else "no", "applies_to_genus": it["applies_to_genus"],
                     "tip_if_oo": it["tip_if_oo"], "tip_if_middle": it.get("tip_if_middle", ""), "tip_if_hindi": it["tip_if_hindi"], "tip_if_hindi_sigurado": it["tip_if_hindi_sigurado"],
                     "genus_tip_if_oo": it["genus_tip_if_oo"], "note": note})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default=str(ROOT / "data" / "reference" / "site_checklist_quote_check.csv"))
    ap.add_argument("--out", default=str(ROOT / "data" / "reference" / "site_checklist.csv"))
    a = ap.parse_args()
    rows = build(a.check)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "items;", sum(r["quote_verified"] == "yes" for r in rows), "with a verified quotation")


if __name__ == "__main__":
    main()
