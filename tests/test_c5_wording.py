"""C5 (overnight 2026-10-15): the word "Purpose" meant two different things. Step 2 (and the Weather tab control that drives the same state) is the SCORED planting purpose; the Step 4 species filter and the Species card tags are
TRAIT tags (fruit-bearing, timber, ...: a filter, never a score). Wording only: the state, the tags and the API are unchanged."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "frontend" / "src" / "new"


def src(name):
    return (NEW / name).read_text(encoding="utf-8")


def test_step_2_and_the_weather_control_say_planting_purpose():
    assert 'title="Layunin ng pagtatanim (Planting purpose)"' in src("AppNew.jsx")
    assert "Layunin ng pagtatanim (Planting purpose)" in src("WeatherTab.jsx")
    assert '<legend className="sr-only">Planting purpose</legend>' in src("PurposePicker.jsx")      # the radio group keeps its English name for screen readers


def test_step_4_filter_is_now_a_trait_filter():
    t = src("SpeciesMultiPicker.jsx")
    assert "Salain ayon sa katangian (Filter by trait)" in t and "Lahat ng katangian (All traits)" in t
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
