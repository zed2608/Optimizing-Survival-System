"""Field pack, stage A1e: simpler, clearer, adjustable, with a guided tour. Source-level checks (the browser checks are in tests/browser/fieldpack_ui_check.mjs):
the arrow and distance to each tree, one step at a time, the three panel states, the text size levels, the tour content, the Filipino review file.
Run from the repo root: python -m pytest tests/test_field_pack_a1e.py"""
import json, re, shutil, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
APP = (ROOT / "fieldpack" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "fieldpack" / "app.css").read_text(encoding="utf-8")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


@pytest.fixture(scope="module")
def tables():
    r = subprocess.run([NODE, "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])))", str(ROOT / "fieldpack" / "strings.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_each_tree_has_its_own_arrow_distance_and_word_and_start_stays_the_target_of_step_1():
    cur = APP.split("function curTarget")[1].split("const targetStatus")[0]
    assert "view.step === 1" in cur and "kind: 'start'" in cur and "kind: 'tree'" in cur and "activeTree(block)" in cur       # START in step 1, the chosen tree after that
    assert "Core.treeStatus(d, block.spacing_m)" in APP and "Core.startStatus(d, acc)" in APP                               # far / close / here for a tree and for START
    upd = APP.split("function updateTarget")[1].split("function refreshChips")[0]
    assert "Core.distanceM(fix.lat, fix.lon, tg.lat, tg.lon)" in upd and "Core.bearingDeg(fix.lat, fix.lon, tg.lat, tg.lon)" in upd and "Core.relativeCue(b, hs.deg)" in upd      # the target's own distance, bearing and cue
    assert "toggleAttribute('hidden', !fix)" in upd                                                                         # the arrow is hidden only when there is no GPS reading, never because of the accuracy
    assert re.search(r"fix\.acc > limit \? t\('notSure'", upd) and "block.spacing_m" in upd                                  # one honest line when the phone is less sure than the spacing
    mp = APP.split("function updateMap")[1].split("function paintHeading")[0]
    assert "const tg = curTarget(block)" in mp and "ml.line = L.polyline([here, [tg.lat, tg.lon]]" in mp                     # the dashed line goes to the target
    assert "view.step >= 2 && tr[0] === k" in APP                                                                           # the chosen tree is the big yellow one from step 2 on
    assert "m.on('click', () => { if (view.step < 3) setStep(3); selectTree(tr[0]) })" in APP                                # tapping a tree on the map makes it the target


def test_one_instruction_one_target_one_big_button_and_the_rest_under_details():
    body = APP.split("ui.body = h('div', { class: 'sheetbody' }")[1].split("\n")[0]
    assert body.index("ui.text") < body.index("ui.target") < body.index("ui.status") < body.index("ui.chips") < body.index("ui.details")
    assert body.count("ui.details") == 1 and "ui.btnrow" in APP.split("ui.sheet = h('section'")[1].split("\n")[0]             # the details live in ONE collapsed block; the buttons sit outside the scrolling body
    det = APP.split("ui.details = h('div'")[1].split("ui.body = ")[0]
    for must in ("ui.stepnav", "ui.paces", "ui.coords", "t('mapLegend')", "t('mapHonest')", "t('banner')", "t('layoutTitle')", "ui.btnCompass", "ui.btnStop", "ui.hdgLine"):
        assert must in det, must                                                                                               # coordinates, accuracy notes, legend, other steps, layout text, the long GPS explanation
    assert APP.count("class: 'btn good primary'") == 1                                                                       # exactly ONE primary button


def test_the_panel_has_three_states_a_drag_handle_a_chevron_and_remembers_its_state():
    for must in ("'collapsed'", "'normal'", "'expanded'", "function setSheet", "function applySheet", "function grabDown", "function grabUp", "onpointerdown: grabDown", "onpointerup: grabUp", "class: 'pill'", "chevbtn", "'sheetOpen'", "'sheetClose'"):
        assert must in APP, must
    assert "window.sessionStorage.setItem('fieldpack_sheet'" in APP and "window.sessionStorage.getItem('fieldpack_sheet')" in APP     # remembered during the session, in try / catch
    assert "catch (e)" in APP.split("let sheetState")[1].split("function setSheet")[0]
    assert "touch-action: none" in CSS.split(".grab {")[1].split("}")[0]                                                     # a drag on the handle is not taken by the browser
    assert re.search(r"\.sheet\[data-state=\"expanded\"\] \{ max-height: calc\(100% - 8px\); \}", CSS)
    col = APP.split("function applySheet")[1].split("const toggleSheet")[0]
    assert "ui.body.hidden = col" in col and "ui.sum.hidden = !col" in col                                                   # collapsed = the handle row only, with "Tree 3 · 12 m"


def test_the_prototype_notice_collapses_to_a_chip_and_stays_in_the_results_file():
    assert "setBanner(true)" in APP and "chipBtn.addEventListener('click', () => setBanner(false))" in APP and "class: 'protochip'" in APP
    tpl = (ROOT / "fieldpack" / "template.html").read_text(encoding="utf-8")
    assert 'id="bannerchip"' in tpl and 'id="bannertext"' in tpl                                                              # the strip is in the page from the first load
    assert "STRINGS.en.banner" in APP.split("function exportFile")[1].split("function download")[0]                          # and in every row of the results file, always in English


def test_text_size_five_levels_everything_in_rem_and_the_phone_font_setting_is_respected():
    assert "const UI_LEVELS = [0.85, 1, 1.15, 1.3, 1.5]" in APP
    assert "prefs.size = i" in APP and "savePrefs()" in APP.split("function setSize")[1].split("const sizeBtn")[0]            # remembered (through the guarded wrapper)
    assert "document.documentElement.style.setProperty('--ui'" in APP
    assert re.search(r"html \{[^}]*font-size: calc\(100% \* var\(--ui\)\)", CSS)                                              # 100% = the phone's own setting
    for rule in (r"\.steptext \{ font-size: 1\.125rem", r"\.tgtline \{ font-size: 1\.4rem", r"\.btnrow \.primary \{[^}]*font-size: calc\(1\.35rem \* var\(--cap\)\)", r"\.sheet \{[^}]*max-height: max\(", r"\.tour-card \{[^}]*font-size: calc\(1rem \* var\(--cap\)\)"):
        assert re.search(rule, CSS), rule                                                                                     # text, buttons, the panel and the tour all follow the size
    assert "sizeBtn(-1), sizeBtn(1), helpButton()" in APP                                                                     # Aa - and Aa + next to Help, on every screen (the toolbox)
    assert APP.count("toolbox()") >= 3                                                                                        # landing, home and block (plus its definition)


def test_the_tour_has_the_steps_that_were_asked_for_and_every_text_exists_in_both_languages(tables):
    tours = APP.split("const TOURS = {")[1].split("function tourSheet")[0]
    for name, count in (("landing", 4), ("home", 3), ("block", 10)):
        part = tours.split(f"{name}: [")[1].split("\n    ],")[0]
        assert len(re.findall(r"\{ id: '", part)) == count, name
    for k in re.findall(r"(?:title|text): '(\w+)'", tours):
        assert k in tables["en"] and k in tables["fil"], k
    block = tours.split("block: [")[1]
    for target in (".me .dot", ".me .cone", ".starticon", ".treeicon", "data-tour=\"sheet\"", "data-tour=\"buttons\"", "topbar [data-tour=\"toolbox\"]", "#map"):
        assert target in block, target                                                                                       # the map, the blue dot, the cone, START, the trees, the panel, Planted and Skip, text size and Help
    for sel in set(re.findall(r"\[data-tour=\"([\w-]+)\"\]", tours)):
        assert f"'data-tour': '{sel}'" in APP or f", '{sel}')" in APP, sel                                                                           # every spotlight has an element to point to
    assert "react" not in APP.lower() and "import " not in APP                                                                # the page stays one self-contained file: the React tour is copied in style, not imported
    for must in ("function isShown", "function findShown", "if (!el) { // not on the screen: skip this step", "e.key === 'Escape'", "ArrowRight", "ArrowLeft", "tour-dots", "tourSkip", "tourBack", "tourNext", "tourDone", "function autoTour", "prefs.tour"):
        assert must in APP, must
    assert "!e.closest('.tour')" in APP                                                                                      # the tour itself is never counted as covering the thing it points to
    assert ".tour { position: fixed; inset: 0;" in CSS                                                                        # the tour blocks taps on the page behind it
    help_ = APP.split("function showHelp")[1].split("function landingScreen")[0]
    assert "data-act': 'tour'" in help_ and "startTour(screen)" in help_                                                      # Help > Take the tour restarts it for the screen you are on


def test_a_tour_step_is_skipped_when_its_element_is_not_there_and_the_sheet_is_put_back():
    one = APP.split("async function openTourStep")[1].split("function measureTour")[0]
    assert "step.before()" in one and "findShown(step.targets)" in one and "openTourStep(nx, dir)" in one and "closeTour(true)" in one
    close = APP.split("function closeTour")[1].split("function autoTour")[0]
    assert "setSheet(tr.prevSheet, false)" in close and "prefs.tour = Object.assign({}, prefs.tour, { [tr.screen]: true })" in close   # finishing or skipping is remembered; the panel goes back to the state it had
    assert "tourSheet('collapsed'" in APP and "tourSheet('normal')" in APP                                                    # it opens or closes the panel as a step needs
