"""Field pack, stages A1d and A1e: two languages (Filipino is the default), everyday words, short texts, and the review file for a native reader.
Run from the repo root: python -m pytest tests/test_field_pack_languages.py"""
import json, re, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# typical values the page puts into a sentence (a block of 8 trees, 7 m apart): used to count the words of a sentence as the planter reads it
SAMPLE = {"a": "3.5", "b": "3.5", "p": "9", "q": "5", "s": "7", "sp": "9", "k": "12", "j": "4", "r": "2", "l": "4", "n": "8", "deg": "40", "m": "18", "d": "about 45 m", "name": "Tree 12", "word": "Close", "dir": "south-west", "total": "8", "reason": "Paved", "state": "x", "lat": "14.1", "lon": "121.1", "done": "3", "planted": "1", "skipped": "1", "rows": "2", "per": "4", "sp2": "7"}


def words(s):
    return len([w for w in s.split() if re.search(r"[A-Za-z0-9]", w)])


def filled(s):
    return re.sub(r"\{(\w+)\}", lambda m: SAMPLE.get(m.group(1), "1"), s)


@pytest.fixture(scope="module")
def tables():
    r = subprocess.run([NODE, "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])))", str(ROOT / "fieldpack" / "strings.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_both_languages_have_exactly_the_same_keys_and_no_text_is_empty(tables):
    assert set(tables) == {"en", "fil"}
    en, fil = tables["en"], tables["fil"]
    assert set(en) == set(fil), (sorted(set(en) - set(fil)), sorted(set(fil) - set(en)))
    for lang, tab in tables.items():
        empty = [k for k, v in tab.items() if not isinstance(v, str) or not v.strip()]
        assert not empty, (lang, empty)


def test_the_values_the_page_fills_in_are_the_same_in_both_languages(tables):
    """{n}, {d}, {k} ... must be in the Filipino text exactly when they are in the English one, or a number would be missing from the sentence."""
    for k, v in tables["en"].items():
        assert sorted(re.findall(r"\{(\w+)\}", v)) == sorted(re.findall(r"\{(\w+)\}", tables["fil"][k])), k


def test_filipino_is_really_translated_and_not_a_copy(tables):
    """Plain Taglish keeps common English words (Start, Skip, Help, Next, Back, Close, Done, Undo, GPS, START, the eight directions), so some values are the same in both languages: only those."""
    same = {k for k, v in tables["en"].items() if v == tables["fil"][k]}
    kept_english = {"langFil", "langEn", "startLabel", "exactM", "helpBtn", "helpTitle", "helpClose", "start", "back", "sizeSmaller", "sizeBigger", "tourNext", "tourBack", "tourDone", "tourSkip", "tl3Title",
                    "btnSkip", "btnUndo", "skipCancel", "gpsStart", "bannerChip", "tgtNone", "tgtLine", "planLine", "detailsTitle", "dir_N", "dir_NE", "dir_E", "dir_SE", "dir_S", "dir_SW", "dir_W", "dir_NW", "helpTour", "resultsTitle"}
    assert same <= kept_english, sorted(same - kept_english)
    sentences = [k for k in tables["en"] if re.fullmatch(r"(how[1-4]|before[1-5]|gpsPromise|s1Text|s1Off|s2Text|s3First|s3Walk|s3Row|s4Text|notSure|sureUnknown|approxShort|approxMap|mapHonest|gpsHonest|blockDone|t[lhb][1-8]|t[A-Z]\w+)", k)]
    assert len(sentences) > 30 and not [k for k in sentences if k in same]
    fil = tables["fil"]
    assert "Pagtatanim" in fil["title"] and fil["btnPlanted"] == "Naitanim na"


def test_everyday_words_not_deep_tagalog(tables):
    """Stage A1e: no deep Tagalog for the things planters handle: stake, tape measure, sapling, row, spot. (The review file asks the native reader about the rest.)"""
    deep = re.compile(r"\b(istaka|tulos|panukat|punla|hanay|pwesto|taniman|lubid)\b", re.I)
    for k, v in tables["fil"].items():
        if k == "before4":                                            # "tape measure o lubid": the rope is named once, with its everyday Filipino word
            continue
        assert not deep.search(v), (k, v)
    fil = tables["fil"]
    for k in ("how2", "before4", "gpsPromise", "s2Text", "tNoSig"):                                 # the kept English words are really there
        assert re.search(r"stake|tape measure", fil[k], re.I), k
    assert "row" in fil["s3Row"].lower() and "stake" in fil["s2Text"].lower() and "sapling" in fil["before4"] and "tape measure" in fil["tNoSig"]
    assert "Itanim" in fil["s3Walk"] and "Pumunta" in fil["s1Title"] and "Pumunta" in fil["dirLine"]        # verbs for actions


def test_the_texts_of_the_panel_are_short(tables):
    """The limits of the browser check (fieldpack_ui_check.mjs), here on the sentences themselves in both languages: a step title of 4 words, ONE instruction of 12, the target line of 8, the honest line of 14."""
    limits = {"s1Title": 4, "s2Title": 4, "s3Title": 4, "s4Title": 4, "s1Off": 12, "s1Text": 12, "s2Text": 12, "s3First": 12, "s3Walk": 12, "s3Row": 12, "s4Text": 12, "tgtLine": 8, "dirLine": 4, "cueLeft": 4, "cueRight": 4, "cueAhead": 4, "cueAround": 4,
              "notSure": 14, "sureUnknown": 14, "approxShort": 10, "blockDone": 12, "s1Wait": 12, "fixOld": 12, "gpsDenied": 12, "gpsTimeout": 12, "gpsUnavailable": 12, "gpsNone": 12, "gpsInsecure": 12, "skipWhy": 6,
              "s1Go": 4, "s2Next": 4, "btnPlanted": 4, "btnSkip": 3, "btnUndo": 3, "skipGps": 3, "gpsStart": 4, "gpsRetry": 4}
    for lang, tab in tables.items():
        for k, mx in limits.items():
            assert words(filled(tab[k])) <= mx, (lang, k, words(filled(tab[k])), mx, tab[k])
        for k in ("reason_paved", "reason_building", "reason_rock_or_ledge", "reason_creek_or_waterlogged", "reason_too_steep", "reason_existing_tree", "reason_owner_refused", "reason_other"):
            assert words(tab[k]) <= 4, (lang, k)
        for k in tab:
            if re.fullmatch(r"t[lhb][1-8]Title", k):
                assert words(tab[k]) <= 6, (lang, k)
            if re.fullmatch(r"t[lhb][1-8]", k):
                assert words(tab[k]) <= 30, (lang, k, words(tab[k]))


def test_plain_words_instead_of_jargon(tables):
    """"accuracy" becomes "how sure the phone is", "bearing" becomes a direction in words; only the prototype notice keeps the words "GPS accuracy" (it is the agreed warning)."""
    for lang, tab in tables.items():
        for k, v in tab.items():
            if k == "banner":
                continue
            assert not re.search(r"accuracy|bearing|azimuth", v, re.I), (lang, k, v)
    assert tables["en"]["banner"] == "Prototype. GPS accuracy not yet field-tested."
    assert "Prototype" in tables["fil"]["banner"] and "GPS" in tables["fil"]["banner"]
    assert "not sure" in tables["en"]["notSure"] and "Hindi sigurado" in tables["fil"]["notSure"]
    assert tables["en"]["dir_SW"] == "south-west" and tables["fil"]["dir_SW"] == "south-west"     # the compass words stay English in the Filipino text (a phone compass shows N E S W): the review file asks about it


def test_the_honest_gps_lines_and_the_prototype_notice_are_in_both_languages(tables):
    for lang, nums in (("en", ("3 to 10 m", "3 to 20 m")), ("fil", ("3 hanggang 10 m", "3 hanggang 20 m"))):
        t = tables[lang]
        assert nums[0] in t["mapHonest"] and nums[1] in t["mapHonest"]
        assert t["gpsHonest"] and t["gpsPromise"] and t["approxMap"] and t["approxShort"] and t["notSure"]
        assert "{m}" in t["notSure"] and "tape measure" in t["notSure"]                 # the one honest line names how sure the phone is and points to the tape measure
        assert "tape measure" in t["approxShort"] or "Tape measure" in t["approxShort"]
    assert "Chrome" in tables["en"]["before1"] and "Chrome" in tables["fil"]["before1"] and "Messenger" in tables["fil"]["before1"]


def test_every_trouble_topic_exists_in_both_languages(tables):
    for lang, t in tables.items():
        for k in ("tLocTitle", "tLocAndroid", "tLocIphone", "tNoSigTitle", "tNoSig", "tArrowTitle", "tArrow", "tDieTitle", "tDie"):
            assert t[k]
        assert "figure 8" in tables["en"]["tArrow"] and "8" in tables["fil"]["tArrow"]
        assert "same link" in tables["en"]["tDie"] and "parehong link" in tables["fil"]["tDie"]
        assert "[RE-CHECK" not in " ".join(t.values())                                                  # the markers belong in the review file, not on the planters' screen


def test_filipino_is_the_default_and_the_choice_is_remembered():
    app = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
    assert "prefs.lang === 'en' || prefs.lang === 'fil' ? prefs.lang : 'fil'" in app                   # Filipino unless the person chose English
    assert "prefs.lang = l" in app and "savePrefs()" in app and "document.documentElement.lang" in app
    landing = app.split("function landingScreen")[1].split("function homeScreen")[0]
    assert "langSwitch()" in landing                                                                   # the switch is on the first screen
    assert "toolbox()" in landing and "toolbox()" in app.split("function blockScreen")[1].split("function leaveBlock")[0]        # Aa - / Aa + / Help on every screen
    assert "helpButton()" in app.split("const toolbox")[1].split("\n")[0]


def test_the_review_file_lists_every_filipino_text_and_the_unsure_words_first(tables):
    import export_field_pack_strings as ex
    review = (ROOT / "docs" / "FIELD_PACK_FILIPINO_REVIEW.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert review == ex.render(tables), "run: python scripts/export_field_pack_strings.py"
    for k, v in tables["fil"].items():
        assert f"`{k}`" in review and v.replace("|", "\\|") in review, k
    assert "[RE-CHECK]" in review and "native reader" in review
    assert review.index("Words and lines to look at first") < review.index("| key | English | Filipino |")      # the words we are unsure about are at the top
    for w in ("Naitanim na", "hakbang", "Malayo", "Nailagay na ang stake", "Hindi sigurado"):
        assert w in review.split("| key | English | Filipino |")[0], w
