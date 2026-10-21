"""Spaced planting points (pipeline/point_layout.py): spacing per pair of species, inside the selected area and the planned squares, quotas, determinism, odd shapes, route."""
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import point_layout as pl  # noqa: E402

SPECIES = pl.species_rules([
    {"species_id": 1, "common_name": "Narra", "spacing_min_m": 10, "canopy_spread_m": 20, "root_type": "Taproot"},
    {"species_id": 2, "common_name": "Molave", "spacing_min_m": 5, "canopy_spread_m": 15, "root_type": "Taproot"},
    {"species_id": 3, "common_name": "Banyan-like", "spacing_min_m": 6, "canopy_spread_m": 12, "root_type": "Extensive aggressive surface roots"},
    {"species_id": 4, "common_name": "Wide crown", "spacing_min_m": 2, "canopy_spread_m": 30, "root_type": "Fibrous"},
    {"species_id": 5, "common_name": "No spacing", "spacing_min_m": None, "canopy_spread_m": 8, "root_type": "Taproot"},
])
E0, N0 = 296_000.0, 1_625_000.0


def blk(ref, sid, n, i=0, j=0):
    return {"ref": ref, "species_id": sid, "n": n, "e": E0 + 100 * i + 50, "n_utm": N0 + 100 * j + 50}


def all_points(res, blocks):
    out = []
    for b in blocks:
        info = res["blocks"][b["ref"]]
        sw = (b["e"] - 50, b["n_utm"] - 50)
        out += [(sw[0] + x, sw[1] + y, int(b["species_id"]), b["ref"]) for x, y in info["points"]]
    return out


def test_pair_distance_is_the_one_formula():
    d = lambda a, b: pl.pair_distance(SPECIES[a], SPECIES[b])
    assert d(1, 1) == 10 and d(2, 2) == 5 and d(1, 2) == 10 and d(2, 1) == 10               # the larger spacing_min of the pair
    assert d(4, 4) == pytest.approx(9.0)                                                      # canopy floor: 0.30 x 30 m beats spacing_min 2 m
    assert d(3, 3) == pytest.approx(6 * 1.2) and d(3, 2) == pytest.approx(6 * 1.2)          # spreading roots: +20 % for any pair that has one
    assert pl.spreading_root("Extensive Taproot") and pl.spreading_root("Shallow spreading") and not pl.spreading_root("Taproot") and not pl.spreading_root(None)


def test_minimum_distance_holds_for_every_pair_across_blocks():
    blocks = [blk("A", 1, 40, 0, 0), blk("B", 2, 150, 1, 0), blk("C", 3, 80, 0, 1)]
    res = pl.layout_plan(blocks, SPECIES)
    pts = all_points(res, blocks)
    assert len(pts) >= 100
    for i, (x1, y1, s1, _) in enumerate(pts):
        for (x2, y2, s2, _) in pts[i + 1:]:
            need = pl.pair_distance(SPECIES[s1], SPECIES[s2])
            assert math.hypot(x1 - x2, y1 - y2) >= need - 1e-6


def test_all_points_are_inside_the_selected_shape_the_edge_margin_and_the_planned_squares():
    shape = Polygon([(E0 + 10, N0 + 10), (E0 + 160, N0 + 30), (E0 + 140, N0 + 90), (E0 + 30, N0 + 80)])       # covers parts of two squares
    blocks = [blk("A", 2, 60, 0, 0), blk("B", 2, 60, 1, 0)]
    res = pl.layout_plan(blocks, SPECIES, shape)
    inner = shape.buffer(-pl.LAYOUT_CFG["edge_margin_m"])
    pts = all_points(res, blocks)
    assert pts
    from shapely.geometry import Point
    for x, y, _, ref in pts:
        assert inner.buffer(1e-6).contains(Point(x, y)), (x, y)
        b = next(b for b in blocks if b["ref"] == ref)
        assert box(b["e"] - 50, b["n_utm"] - 50, b["e"] + 50, b["n_utm"] + 50).buffer(1e-6).contains(Point(x, y))
    # a square that is not planned gets nothing: the shape reaches into i = 2 but only A and B were planned
    wide = box(E0, N0, E0 + 300, N0 + 100)
    res2 = pl.layout_plan([blk("A", 2, 20, 0, 0)], SPECIES, wide)
    assert all(0 <= x <= 100 and 0 <= y <= 100 for x, y in res2["blocks"]["A"]["points"])


def test_count_is_exact_when_it_fits_and_reported_when_it_does_not():
    res = pl.layout_plan([blk("A", 2, 30)], SPECIES)
    a = res["blocks"]["A"]
    assert a["placed"] == 30 and a["fits"] is True and a["reason"] == "" and a["min_distance_m"] == 5
    big = pl.layout_plan([blk("A", 1, 400)], SPECIES)["blocks"]["A"]                            # 400 trees at 10 m in one 100 m square cannot fit
    assert big["fits"] is False and 20 < big["placed"] < 120
    assert big["reason"].startswith(f"{big['placed']} of 400 fit at the required spacing") and "Reduce the number of trees or enlarge the area" in big["reason"]
    none = pl.layout_plan([blk("A", 5, 10)], SPECIES)["blocks"]["A"]
    assert none["placed"] == 0 and none["fits"] is False and "no planting distance" in none["reason"]


def test_deterministic_for_a_seed_and_different_for_another():
    blocks = [blk("A", 2, 40), blk("B", 1, 15, 1, 0)]
    a = pl.layout_plan(blocks, SPECIES, seed=7)["blocks"]
    b = pl.layout_plan(blocks, SPECIES, seed=7)["blocks"]
    c = pl.layout_plan(blocks, SPECIES, seed=8)["blocks"]
    assert a["A"]["points"] == b["A"]["points"] and a["B"]["points"] == b["B"]["points"]
    assert a["A"]["points"] != c["A"]["points"]


def test_several_species_each_get_their_quota():
    blocks = [blk("N", 1, 20, 0, 0), blk("M", 2, 60, 1, 0), blk("B", 3, 40, 0, 1), blk("W", 4, 8, 1, 1)]
    res = pl.layout_plan(blocks, SPECIES)
    for b in blocks:
        info = res["blocks"][b["ref"]]
        assert info["placed"] == b["n"] and info["fits"], (b["ref"], info["reason"])


def test_tiny_and_irregular_shapes():
    tiny = box(E0 + 40, N0 + 40, E0 + 52, N0 + 52)                                              # 12 m x 12 m
    r = pl.layout_plan([blk("A", 2, 10)], SPECIES, tiny)["blocks"]["A"]
    assert 0 <= r["placed"] <= 4 and (r["placed"] == 10 or r["reason"].startswith(f"{r['placed']} of 10 fit"))
    gone = box(E0 + 40, N0 + 40, E0 + 44, N0 + 44)                                              # 4 m: nothing is left after the 3 m margin
    r = pl.layout_plan([blk("A", 2, 3)], SPECIES, gone)["blocks"]["A"]
    assert r["placed"] == 0 and r["fits"] is False and "no plantable ground" in r["reason"]
    ell = Polygon([(E0 + 5, N0 + 5), (E0 + 95, N0 + 5), (E0 + 95, N0 + 35), (E0 + 35, N0 + 35), (E0 + 35, N0 + 95), (E0 + 5, N0 + 95)])    # concave L
    res = pl.layout_plan([blk("A", 2, 45)], SPECIES, ell)
    from shapely.geometry import Point
    inner = ell.buffer(-3)
    pts = [(E0 + x, N0 + y) for x, y in res["blocks"]["A"]["points"]]
    assert len(pts) >= 30 and all(inner.buffer(1e-6).contains(Point(p)) for p in pts)
    assert not any(55 < x - E0 < 95 and 40 < y - N0 < 95 for x, y in pts)                       # the notch of the L stays empty


def test_route_visits_every_point_once_starts_near_start_and_beats_a_random_order():
    blocks = [blk("A", 2, 80)]
    res = pl.layout_plan(blocks, SPECIES)
    a = res["blocks"]["A"]
    pts = a["points"]
    assert len(pts) == len(set(pts)) == 80
    assert math.dist(pts[0], a["start"]) <= min(math.dist(p, a["start"]) for p in pts) + 3.0
    length = lambda seq: sum(math.dist(seq[i], seq[i + 1]) for i in range(len(seq) - 1))
    shuffled = sorted(pts, key=lambda p: (p[0] * 7919 + p[1] * 104729) % 1.0)
    assert length(pts) < 0.5 * length(shuffled)
    order = pl.route_order([(0, 0), (10, 0), (5, 0)], (0, 0))
    assert sorted(order) == [0, 1, 2] and order[0] == 0 and order[1] == 2
