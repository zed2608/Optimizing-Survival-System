"""
Writes docs/FIELD_PACK_FILIPINO_REVIEW.md: every text of the field pack in English and in Filipino, side by side, for a native Filipino reader to check.
The table is made FROM fieldpack/strings.js (so it can never drift: tests/test_field_pack_languages.py compares the file with this script's output).

    python scripts/export_field_pack_strings.py            # rewrite the review file
    python scripts/export_field_pack_strings.py --check    # exit 1 if the file is out of date
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "FIELD_PACK_FILIPINO_REVIEW.md"

GROUPS = [
    ("The notice, the language switch and the text size", ("banner", "bannerChip", "bannerHide", "bannerShow", "title", "lang", "helpBtn", "helpTitle", "helpClose", "start", "back", "backLabel", "backToIntro", "size")),
    ("First page: how to use, before you go", ("how", "before", "gpsPromise")),
    ("The guided tour (first page, block list, block screen) and Help's tour button", ("helpTour", "tour", "tl", "th", "tb")),
    ("Block list and results", ("planLine", "builtLine", "storageWarn", "nameLabel", "blocksTitle", "totalsLine", "blockCard", "results", "btnDownload", "btnShare", "gpsHonest", "btnErase", "confirmErase")),
    ("Block screen: the panel and the four steps", ("topDone", "details", "sheet", "grabLabel", "stepOf", "stepPrev", "stepNextBtn", "s1", "s2", "s3", "s4", "detPaces", "approx", "skipGps", "treeName", "tgt", "aboutM", "lessThanM", "exactM", "dirLine", "notSure", "sureUnknown", "mini", "startLabel", "btn", "skip", "chips", "state", "rec", "treeAria", "reason_", "blockDone")),
    ("GPS, compass and heading", ("gps", "fixOld", "targetCoords", "dir_", "cue", "heading", "rotate", "compass", "storageFail", "needName", "shareNone")),
    ("The map", ("map", "layoutTitle", "blockLine", "orderLine", "startLine")),
    ("Help: if something goes wrong", ("trouble", "tLoc", "tNoSig", "tArrow", "tDie", "gpsTruth")),
]

# the words and lines the native reader should look at first, and why (stage A1e: plain everyday Taglish)
UNSURE = [
    ("Naitanim na", "the main button: 'Planted'. 'Naitanim' is the usual word, but would planters say 'Tanim na' or 'Tapos na'? The tour and Help use the same word."),
    ("Itanim ang puno 1 / Itanim ang puno {k}", "'Plant tree 1'. Good as an action, but check that 'Itanim' reads naturally with a number."),
    ("puno (tree)", "used for the tree: 'puno 1', 'Puno 3 · mga 12 m · Malapit'. 'Tree' would also be understood."),
    ("mga 12 m, mga 9 hakbang", "'about 12 m', 'about 9 paces'. 'Mga' = about. 'hakbang' = step, used for a pace (1 pace is about 0.75 m): is 'hakbang' clear, or would 'steps' be better?"),
    ("Malayo / Malapit / Nandito na", "Far / Close / Here (the word after the distance). Would 'Nandito na' be better as 'Andito na'?"),
    ("east, north, south-west ... (kept in English)", "the eight directions are written in English ('Pumunta sa south-west') because a phone compass shows N E S W. Would planters rather read 'timog-kanluran' (south-west)? 'kaliwa' and 'kanan' (left, right) ARE used for the turn cue."),
    ("Nailagay na ang stake", "the button for step 2, 'The stake is in'. Is 'Nailagay' (placed) the best verb for putting a stake in the ground ('Naitusok'? 'Naitayo'?)."),
    ("Stake sa START. Puno 1: ...", "the step 2 sentence is short on purpose (12 words at most); check that it still reads as an instruction."),
    ("Row {r}: {s} m north ng puno {j}", "'Row 2: 7 m north of tree 8'. 'ng' after 'north' = 'of': is that clear?"),
    ("Hindi sigurado ang phone (mga 18 m). Gamitin ang tape measure.", "the one honest line when the phone is less sure than the tree spacing. 'Hindi sigurado' = 'not sure'."),
    ("Gamitin ang tape measure", "'tape measure' is kept in English on purpose (the user's choice); 'lubid' (rope) is used once, in the checklist."),
    ("Bato o bangin", "'Rock or ledge' (a reason for skipping a tree). 'Bangin' = cliff or drop."),
    ("Sapa o baha", "'Creek or flooded'."),
    ("Naka-block ang Location. Tingnan ang Help.", "'Location is blocked. See Help.' The word 'Location' is kept in English because phones show it that way."),
    ("Mga hakbang / Step n sa 4 / Naunang step / Susunod na step", "'Step', 'Next step', 'Previous step' are kept as 'step' (English) in the labels; 'hakbang' is only used for paces."),
    ("Tour: Next / Back / Done / Skip / Help / Close / Start", "kept in English: Filipinos already use these words on phones. Tell us if any of them should be Filipino."),
    ("Laki ng letra, Paliitin / Palakihin ang letra", "'Text size', 'make the text smaller / bigger'. The buttons themselves say 'Aa -' and 'Aa +'."),
    ("Mapa, Tinatayang lugar lang ang mapa", "'The map is approximate' (the short reminder under the target)."),
    ("tLocAndroid, tLocIphone", "[RE-CHECK] the menu names (Permissions, Location, Allow, Website Settings, Location Services) are from memory and NOT verified on a phone; they are written in English because that is how phones in the Philippines usually show them."),
    ("pwesto, istaka, panukat, punla, hanay", "NOT USED any more (too deep): the page says 'spot', 'stake', 'tape measure', 'sapling', 'row'. 'spot' is used in the how-to ('Sukatin ang bawat spot'): is it clear?"),
]


# Stage A1f (appended): words that changed because of "no GPS is never a dead end" and the plain-words pass, and the questions for the native reader
A1F_CHANGES = [
    ("Continue without GPS", "Ituloy nang walang GPS (panel button) / Ituloy, walang GPS (short button in step 1)", "new"),
    ("Try GPS again / Use GPS", "Subukan ulit ang GPS / Gamitin ang GPS", "new"),
    ("GPS: working / not ready / finding you / blocked / problem / No GPS", "GPS: gumagana / hindi pa handa / hinahanap ka / naka-block / may problema / Walang GPS", "new (the GPS bar)"),
    ("Location is blocked. Allow it, then try again.", "Naka-block ang Location. Payagan ito, tapos subukan ulit.", "was: 'Location is blocked. See Help.'"),
    ("How to allow Location (Android Chrome, iPhone Safari)", "Paano payagan ang Location", "new, short; the menu names are [RE-CHECK]"),
    ("Tree 3 · row 1, spot 3", "Puno 3 · row 1, spot 3", "new (no GPS: the place of the tree in the plan)"),
    ("The compass was not allowed. The page still works.", "Hindi pinayagan ang compass. Gumagana pa rin ang page.", "was: 'Compass permission was refused.'"),
    ("This phone gave no compass.", "Walang compass na nakuha sa phone.", "was: 'No compass reading from this phone.'"),
    ("The GPS is not updating. Move a little or wait.", "Hindi nag-a-update ang GPS. Gumalaw nang kaunti o maghintay.", "was: 'The GPS reading is old.'"),
    ("GPS is not ready. Start GPS first.", "Hindi pa handa ang GPS. I-start muna ang GPS.", "was: 'No GPS reading yet.'"),
    ("GPS works only on an https link.", "Gumagana lang ang GPS sa https link.", "was: 'GPS needs a secure (https) page.'"),
    ("Map: aerial photo", "Mapa: litrato mula sa taas", "was: 'Map: satellite' (only in the build with the photo layer)"),
]
A1F_QUESTIONS = [
    ("Ituloy nang walang GPS", "Is 'Ituloy nang walang GPS' (continue without GPS) clear and polite enough? Would 'Magpatuloy kahit walang GPS' sound better?"),
    ("Subukan ulit ang GPS / Gamitin ang GPS", "Try again / Use GPS. Natural, or would 'I-on ulit ang GPS' be the everyday phrase?"),
    ("GPS: hinahanap ka", "'GPS: finding you'. Does 'hinahanap ka' (it is looking for you) read naturally for a GPS that is still searching?"),
    ("GPS: hindi pa handa", "'GPS: not ready'. Alternative: 'GPS: hindi pa naka-on' for off and 'hindi pa handa' only for searching?"),
    ("Naka-block ang Location. Payagan ito", "'Location is blocked. Allow it.' Is 'Payagan' (allow) the word people use for phone permissions, or 'I-allow'?"),
    ("row 1, spot 3", "'row' and 'spot' kept in English for the place of a tree without GPS. Would 'hanay' or 'pwesto' be understood better after all?"),
    ("Walang GPS: tape measure at hakbang ang gamit", "'No GPS: the tape measure and your steps are what you use.' Natural?"),
    ("Hindi pinayagan ang compass", "'The compass was not allowed.' Is 'pinayagan' right here, since the person pressed 'Don't allow' on the phone prompt?"),
    ("tLocAndroid, tLocIphone, gpsAllowAndroid, gpsAllowIphone", "[RE-CHECK] the menu names (Permissions, Location, Allow, Website Settings) are from memory and NOT verified on a phone."),
]


def load_strings():
    node = shutil.which("node")
    if not node:
        sys.exit("node is needed to read fieldpack/strings.js")
    r = subprocess.run([node, "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])))", str(ROOT / "fieldpack" / "strings.js")], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def esc(s):
    return s.replace("|", "\\|").replace("\n", " ")


def render(tables):
    en, fil = tables["en"], tables["fil"]
    out = ["# Field pack: every text in English and Filipino (for a native reader to check)", "",
           "Made from `fieldpack/strings.js` by `scripts/export_field_pack_strings.py`; do not edit this file by hand (a test compares it with the strings). "
           "The Filipino is plain everyday Taglish (short sentences; common English words such as GPS, block, tape measure, row, stake, Start and Skip are kept) written by Claude Code and has **not** been checked by a native reader yet. "
           "`{name}` marks a value that the page fills in (a number, a name, a direction). The page is in Filipino unless the person chooses English. "
           "The results file is always in English.", "",
           f"**{len(en)} texts.** Both languages have exactly the same keys; no text is empty.", "",
           "## Words and lines to look at first (the ones we were unsure about)", "", "| Filipino text | Question |", "|---|---|"]
    for a, b in UNSURE:
        out.append(f"| {esc(a)} | {esc(b)} |")
    out += ["", "## Stage A1f: words that changed, and questions for the native reader", "", "| English | Filipino | Note |", "|---|---|---|"]
    out += [f"| {esc(a)} | {esc(b)} | {esc(c)} |" for a, b, c in A1F_CHANGES]
    out += ["", "| Filipino text | Question |", "|---|---|"] + [f"| {esc(a)} | {esc(b)} |" for a, b in A1F_QUESTIONS]
    seen = set()
    for title, prefixes in GROUPS:
        keys = [k for k in en if k not in seen and any(k == p or k.startswith(p) for p in prefixes)]
        if not keys:
            continue
        seen.update(keys)
        out += ["", f"## {title}", "", "| key | English | Filipino |", "|---|---|---|"]
        out += [f"| `{k}` | {esc(en[k])} | {esc(fil[k])} |" for k in keys]
    rest = [k for k in en if k not in seen]
    if rest:
        out += ["", "## Other", "", "| key | English | Filipino |", "|---|---|---|"]
        out += [f"| `{k}` | {esc(en[k])} | {esc(fil[k])} |" for k in rest]
    return "\n".join(out) + "\n"


def main(argv=None):
    text = render(load_strings())
    if argv and "--check" in argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8").replace("\r\n", "\n") == text
        print("up to date" if ok else "OUT OF DATE: run python scripts/export_field_pack_strings.py")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"{OUT}  ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
