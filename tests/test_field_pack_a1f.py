"""Field pack, stage A1f: "no GPS" is never a dead end. Source-level checks and the short texts (the browser checks are in tests/browser/fieldpack_nogps_check.mjs).
Run from the repo root: python -m pytest tests/test_field_pack_a1f.py"""
import json, re, shutil, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
APP = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "fieldpack" / "app.css").read_text(encoding="utf-8")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")
SAMPLE = {"name": "Tree 12", "r": "2", "c": "5"}


@pytest.fixture(scope="module")
def tables():
    r = subprocess.run([NODE, "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])))", str(ROOT / "fieldpack" / "strings.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def words(s):
    return len([w for w in s.split() if re.search(r"[A-Za-z0-9]", w)])


def test_every_gps_state_has_a_status_word_and_a_message_and_the_reason_is_kept():
    for st in ("'off'", "'waiting'", "'ok'", "'error'", "'nogps'"):
        assert f"gps.status === {st}" in APP or f"gps.status = {st}" in APP or f"st === {st}" in APP, st
    for reason in ("denied", "timeout", "unavailable", "none", "insecure"):
        assert f"{reason}:" in APP.split("const GPS_TEXT")[1].split("\n")[0], reason                      # one message per reason
    assert "gpsFail(err && err.code === 1 ? 'denied' : err && err.code === 3 ? 'timeout' : 'unavailable')" in APP
    bar = APP.split("function gpsBarKey")[1].split("function updateGpsBar")[0]
    for key in ("gpsBarOk", "gpsBarWait", "gpsBarNone", "gpsBarBlocked", "gpsBarProblem", "gpsBarOff"):
        assert key in bar, key


def test_the_gps_bar_is_always_there_and_both_ways_out_are_always_reachable():
    assert "ui.gpsbar" in APP.split("ui.body = h('div', { class: 'sheetbody' }")[1].split("\n")[0]                         # in the body of the panel
    assert "position: sticky" in CSS.split(".gpsbar {")[1].split("}")[0]                                                   # it never scrolls out of sight
    assert re.search(r"\.gpsbar \{[^}]*min-height: max\(48px", CSS)                                                          # 48 px or more
    panel = APP.split("function updateGpsBar")[1].split("function updateAll")[0]
    assert "ui.btnGpsTry.hidden = st === 'ok'" in panel and "ui.btnGpsNone.hidden = st === 'nogps'" in panel                  # try / use GPS unless it works; continue-without unless already without
    assert "ui.errRow.hidden = !(gps.status === 'error' && step >= 2 && !view.gpsOpen)" in APP                                # an error in step 2 to 4: the two buttons right under the message
    assert "if (gps.status === 'off' || gps.status === 'error') return retryGps()" in APP                                    # step 1: the main button tries again
    assert "if (ui.btnSkip.dataset.act === 'nogps') return setNoGps()" in APP                                                # ... and the second one continues without GPS (it used to jump to step 2 and leave no way back)
    assert "ui.sheet.dataset.gps" in APP and 'data-gps="open"' in CSS                                                       # the panel gets room


def test_without_gps_the_row_and_spot_come_from_the_plan_and_nothing_is_saved():
    upd = APP.split("function updateTarget")[1].split("function refreshChips")[0]
    assert "Core.rowPlace(tg.k, block.per_row)" in upd and "t('tgtNoGps'" in upd and "t('noGpsTip')" in upd                 # the data already in the pack: row and spot, no new algorithm
    assert "ui.arrow.toggleAttribute('hidden', !fix)" in upd                                                                 # the arrow comes back by itself when a GPS reading arrives
    block = APP.split("function setNoGps")[1].split("function retryGps")[0]
    assert "save" not in block.lower() and "localStorage" not in block and "prefs" not in block                              # kept in memory only
    assert "gps.status = 'nogps'" in block and "gps.status = 'off'" in APP.split("function stopGps")[1].split("function setNoGps")[0]


def test_the_new_texts_are_short_and_in_both_languages(tables):
    limits = {"gpsBarOk": 4, "gpsBarWait": 4, "gpsBarOff": 4, "gpsBarBlocked": 4, "gpsBarProblem": 4, "gpsBarNone": 4, "gpsAgain": 5, "gpsUse": 5, "gpsContinue": 5, "skipGps": 3,
              "gpsMsgOff": 12, "gpsMsgWait": 12, "gpsMsgOk": 12, "gpsMsgDenied": 12, "gpsMsgTimeout": 12, "gpsMsgProblem": 12, "gpsMsgNone": 12, "gpsMsgNoGps": 12,
              "s1NoGps": 12, "tgtNoGps": 8, "noGpsTip": 14, "gpsDenied": 12, "gpsTimeout": 12, "gpsInsecure": 12, "fixOld": 12, "mapNoFix": 12, "compassDenied": 12}
    for lang, tab in tables.items():
        for k, mx in limits.items():
            assert words(re.sub(r"\{(\w+)\}", lambda m: SAMPLE.get(m.group(1), "1"), tab[k])) <= mx, (lang, k, tab[k])
    for k in ("gpsAllowAndroid", "gpsAllowIphone"):
        assert all(re.search(r"Permissions|Website Settings|Location|Allow", tables[lang][k]) for lang in tables)         # the menu names stay as phones show them ([RE-CHECK] in the review file)
    assert tables["fil"]["gpsContinue"] == "Ituloy nang walang GPS" and tables["en"]["gpsContinue"] == "Continue without GPS"


def test_the_deep_words_are_gone_from_the_texts_the_planter_reads(tables):
    deep = re.compile(r"permission|coordinates|calibrat|satellite|accuracy|compass heading", re.I)
    for lang, tab in tables.items():
        for k, v in tab.items():
            if k in ("banner", "tLocAndroid", "gpsAllowAndroid"):         # the agreed prototype notice, and the Android menu name "Permissions" as the phone shows it
                continue
            assert not deep.search(v), (lang, k, v)
    assert "aerial photo" in tables["en"]["mapBaseSat"] and "litrato" in tables["fil"]["mapBaseSat"]


def test_the_review_file_lists_the_changed_words_and_the_questions():
    review = (ROOT / "docs" / "FIELD_PACK_FILIPINO_REVIEW.md").read_text(encoding="utf-8")
    assert "Stage A1f" in review and "Subukan ulit ang GPS" in review and "Ituloy nang walang GPS" in review and "[RE-CHECK]" in review
