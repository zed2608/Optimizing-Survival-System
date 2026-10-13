"""Field pack, stage A1d: two languages (Filipino is the default), plain words, and the review file for a native reader.
Run from the repo root: python -m pytest tests/test_field_pack_languages.py"""
import json, re, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


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
    same = [k for k, v in tables["en"].items() if v == tables["fil"][k]]
    allowed = {"langFil", "langEn", "startLabel", "exactM"}                                              # names and a number with its unit
    assert set(same) <= allowed | {k for k in same if re.fullmatch(r"[\W\d{}a-z]*", tables["en"][k])}, same
    assert len(same) <= 8, same
    assert "pagtatanim" in tables["fil"]["title"] and "Hakbang" in tables["fil"]["s1Title"] and "Naitanim na" == tables["fil"]["btnPlanted"]


def test_plain_words_instead_of_jargon(tables):
    """"accuracy" becomes "how sure the phone is", "bearing" becomes a direction in words; only the prototype notice keeps the words "GPS accuracy" (it is the agreed warning)."""
    for lang, tab in tables.items():
        for k, v in tab.items():
            if k == "banner":
                continue
            assert not re.search(r"accuracy|bearing|azimuth", v, re.I), (lang, k, v)
    assert tables["en"]["banner"] == "Prototype. GPS accuracy not yet field-tested."
    assert "Prototype" in tables["fil"]["banner"] and "GPS" in tables["fil"]["banner"]
    assert "sure" in tables["en"]["sureLine"] and "Sigurado" in tables["fil"]["sureLine"]
    assert tables["en"]["dir_SW"] == "south-west" and "timog-kanluran" in tables["fil"]["dir_SW"]


def test_the_honest_gps_line_and_the_prototype_notice_are_in_both_languages(tables):
    for lang, nums in (("en", ("3 to 10 m", "3 to 20 m")), ("fil", ("3 hanggang 10 m", "3 hanggang 20 m"))):
        t = tables[lang]
        assert nums[0] in t["mapHonest"] and nums[0] in t["intro2"] and nums[1] in t["intro2"]
        assert "mapHonest" in t and t["gpsHonest"] and t["gpsPromise"] and t["approxMap"] and t["s2More"]
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
    assert "langSwitch()" in app.split("function landingScreen")[1].split("function homeScreen")[0]       # the switch is on the first screen
    assert "helpButton()" in app.split("function landingScreen")[1].split("function homeScreen")[0] and "helpButton()" in app.split("function blockScreen")[1].split("function leaveBlock")[0]


def test_the_review_file_lists_every_filipino_text_and_is_up_to_date(tables):
    import export_field_pack_strings as ex
    review = (ROOT / "docs" / "FIELD_PACK_FILIPINO_REVIEW.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert review == ex.render(tables), "run: python scripts/export_field_pack_strings.py"
    for k, v in tables["fil"].items():
        assert f"`{k}`" in review and v.replace("|", "\\|") in review, k
    assert "[RE-CHECK]" in review and "native reader" in review
