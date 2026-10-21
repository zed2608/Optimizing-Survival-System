"""C5 (overnight 2026-10-15): the word "Purpose" meant two different things. Step 2 (and the Weather tab control that drives the same state) is the SCORED planting purpose; the Step 4 species filter and the Species card tags are
TRAIT tags (fruit-bearing, timber, ...: a filter, never a score). Wording only: the state, the tags and the API are unchanged."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "frontend" / "src" / "new"


def src(name):
    return (NEW / name).read_text(encoding="utf-8")


def test_step_2_and_the_weather_control_say_planting_purpose():
    # V2: the label moved into messages.js so that English mode shows no Filipino: English "Planting purpose", Taglish "Layunin ng pagtatanim (Planting purpose)"
    assert "title={tr('purpose.title', {}, lang)}" in src("AppNew.jsx")
    assert "tr('wx.purpose', {}, lang)" in src("WeatherTab.jsx")
    msgs = src("messages.js")
    assert "'purpose.title': 'Planting purpose'" in msgs and "'purpose.title': 'Layunin ng pagtatanim (Planting purpose)'" in msgs
    assert "'wx.purpose': 'Planting purpose'" in msgs and "'wx.purpose': 'Layunin ng pagtatanim (Planting purpose)'" in msgs
    assert '<legend className="sr-only">Planting purpose</legend>' in src("PurposePicker.jsx")      # the radio group keeps its English name for screen readers


def test_step_4_filter_is_now_a_trait_filter():
    t = src("SpeciesMultiPicker.jsx")
    m = src("messages.js")                                                                         # the words live in the message table (W6: English mode shows English only)
    assert "'sc.filterTrait': 'Salain ayon sa katangian (Filter by trait)'" in m and "'sc.allTraits': 'Lahat ng katangian (All traits)'" in m
    assert "sc.filterTrait" in t and "sc.allTraits" in t
    assert "All purposes" not in t and ">\n          Purpose " not in t
    assert 'id="nw-purpose-filter"' in t                                                           # the element id is unchanged (nothing else depends on the words)


def test_the_species_card_tags_use_the_same_word():
    c = src("SpeciesCard.jsx")
    assert "Katangian (Trait)" in c and 'aria-label="Trait tags and nursery"' in c and "Trait tags are filters" in c
    assert '<span className="nw-tagrow-label">Purpose</span>' not in c


def test_nothing_but_the_words_changed():
    # the scored purposes and the tag list are the same as before
    assert "export const PURPOSE_SHORT = { urban: 'Urban greening', planting: 'Tree planting', watershed: 'Watershed' }" in src("labelsNew.js")
    assert src("purposeTags.js").count("'") >= 16 and "'fruit-bearing'" in src("purposeTags.js")
