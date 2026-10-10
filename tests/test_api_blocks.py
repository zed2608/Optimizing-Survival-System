"""Round 10a through the API: plans in blocks (default), the preview estimate, the status planted with a tree count, progress, top-up plans, the kit's blocks.csv import.
Every test gets its own empty field database and a temp folder for plans and kits. Run from the repo root: python -m pytest tests/test_api_blocks.py"""
import csv, io, json, math, sys, zipfile
from pathlib import Path
import pandas as pd
import pytest

BLOCKS_DEFAULT = True          # tests/conftest.py: keep the real defaults (blocks) in this module
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import field_verify as fv  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def fresh(data, tmp_path, monkeypatch):
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(data, "work", tmp_path)
    monkeypatch.setitem(data.cfg, "field_exclude_not_plantable", True)
    fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


BASE = {"purpose": "urban", "n_saplings": 300, "seed": 4, "campaign": {"name": "Tree Day", "unit": "Team A"}}
WINDOW = {"start": "2027-05-01", "end": "2027-06-29"}


def make(client, body=None, **q):
    r = client.post("/plan-event", params={**WINDOW, **q}, json={**BASE, **(body or {})})
    assert r.status_code == 200, r.text
    return r.json()


def mark(client, plan, k, status="planted", trees=None, **kw):
    it = plan["plan"][k]
    body = {"point_id": it["point_id"], "status": status, "observer": "Ana", "plan_id": plan["plan_id"], **kw}
    if status == "planted":
        body["trees_planted"] = it["trees_planned"] if trees is None else trees
    if status == "not_plantable":
        body.setdefault("reason", "rock_or_ledge")
    return client.post("/field-checks", json=body)


# ---- plans in blocks ----------------------------------------------------------------------------------------------------------------------
def test_blocks_is_the_default_and_the_items_carry_the_layout(client):
    j = make(client)
    assert j["layout_mode"] == "blocks" and j["summary"]["layout_mode"] == "blocks"
    assert sum(i["trees_planned"] for i in j["plan"]) == 300 == j["n_placed"] == j["blocks"]["trees"] and j["blocks"]["blocks"] == len(j["plan"])
    for i in j["plan"]:
        assert i["block_ref"] == i["point_ref"] and "-B" in i["block_ref"] and i["block_ref"].split("-")[0] == i["species_code"]
        assert i["rows"] == i["trees_per_row"] and i["capacity"] == i["rows"] ** 2 and 1 <= i["trees_planned"] <= i["capacity"]
        assert i["row_direction"] == "east-west" and i["start_corner"] == "south-west" and i["usable_side_m"] == pytest.approx(77.46, abs=0.01) and i["spacing_m"] > 0
    lay = j["summary"]["layout"]
    assert lay["trees_placed"] == 300 and lay["blocks"] == len(j["plan"]) and lay["hectares_used"] == pytest.approx(len(j["plan"]))
    assert {p["species_id"] for p in lay["per_species"]} == {p["species_id"] for p in j["palette"]}
    assert j["summary"]["request"]["n_saplings"] == 300 and j["summary"]["request"]["campaign"]["name"] == "Tree Day"


def test_points_mode_still_works_and_old_plans_load_as_points(client, data):
    j = make(client, {"layout_mode": "points", "n_saplings": 40})
    assert j["layout_mode"] == "points" and len(j["plan"]) == 40 and "trees_planned" not in j["plan"][0] and "blocks" not in j and "request" not in j["summary"]
    g = client.get(f"/plans/{j['plan_id']}").json()
    assert g["layout_mode"] == "points" and len(g["plan"]) == 40
    assert client.get(f"/plans/{j['plan_id']}/progress").status_code == 400
    assert client.post(f"/plans/{j['plan_id']}/top-up").status_code == 400
    lst = {p["plan_id"]: p for p in client.get("/plans").json()["plans"]}
    assert lst[j["plan_id"]]["layout_mode"] == "points" and lst[j["plan_id"]]["parent_plan_id"] is None


def test_the_default_can_be_switched_by_the_config(client, data, monkeypatch):
    monkeypatch.setitem(data.cfg, "layout_mode", "points")
    r = client.post("/plan-event", json={**BASE, "n_saplings": 20})
    assert r.json()["layout_mode"] == "points"


def test_invalid_layout_mode_is_rejected(client):
    assert client.post("/plan-event", json={**BASE, "layout_mode": "grid"}).status_code == 422


def test_preview_says_about_how_many_blocks(client):
    r = client.post("/plan-event/preview", params=WINDOW, json={**BASE}).json()
    e = r["blocks_estimate"]
    assert r["layout_mode"] == "blocks" and r["can_create"] and e["trees"] == 300
    assert e["blocks_low"] <= e["blocks_about"] <= e["blocks_high"] and e.get("exact") is True       # round 21: the estimate is the real plan rule
    assert e["hectares_about"] == pytest.approx(e["blocks_about"]) and "Create plan" in e["basis"]
    assert r["capacity"]["unit"] == "trees" and r["capacity"]["max_placeable_blocks"] == r["area"]["suitable_squares"]
    p = client.post("/plan-event/preview", params=WINDOW, json={**BASE, "layout_mode": "points"}).json()
    assert p["blocks_estimate"] is None and p["capacity"]["unit"] == "squares"


def test_preview_capacity_message_when_there_are_too_few_squares(client):
    poly = {"type": "Polygon", "coordinates": [[[121.1380, 14.7080], [121.1400, 14.7080], [121.1400, 14.7100], [121.1380, 14.7100], [121.1380, 14.7080]]]}
    r = client.post("/plan-event/preview", params=WINDOW, json={**BASE, "n_saplings": 2000, "polygon": poly}).json()
    if r["can_create"]:
        assert r["capacity"]["short"] and "blocks" in r["capacity"]["message"]


def test_blocks_plan_loads_again_with_its_block_fields(client):
    j = make(client)
    g = client.get(f"/plans/{j['plan_id']}").json()
    assert g["layout_mode"] == "blocks" and [i["block_ref"] for i in g["plan"]] == [i["block_ref"] for i in j["plan"]] and g["child_plan_ids"] == []
    lst = {p["plan_id"]: p for p in client.get("/plans").json()["plans"]}
    assert lst[j["plan_id"]]["layout_mode"] == "blocks" and lst[j["plan_id"]]["blocks"] == len(j["plan"]) and lst[j["plan_id"]]["n_placed"] == 300


def test_block_model_endpoint_lists_every_species(client):
    j = client.get("/block-model").json()
    assert len(j["species"]) == 45 and j["config"]["block_side_m"] == 100 and j["config"]["usable_share"] == 0.6 and "provisional" in j["config"]["status"]
    for s in j["species"]:
        assert s["capacity"] is None or s["capacity"] == s["rows"] * s["trees_per_row"]


# ---- planted ---------------------------------------------------------------------------------------------------------------------------
def test_planted_needs_a_plan_a_block_and_a_sensible_count(client):
    j = make(client)
    it = j["plan"][0]
    ok = {"point_id": it["point_id"], "status": "planted", "observer": "Ana", "plan_id": j["plan_id"], "trees_planted": it["trees_planned"]}
    assert client.post("/field-checks", json={**ok, "plan_id": None}).status_code == 422
    assert client.post("/field-checks", json={**ok, "trees_planted": None}).status_code == 422
    assert client.post("/field-checks", json={**ok, "trees_planted": it["trees_planned"] + 1}).status_code == 422
    assert client.post("/field-checks", json={**ok, "trees_planted": -1}).status_code == 422
    assert client.post("/field-checks", json={**ok, "plan_id": "plan_nope_1"}).status_code == 404
    assert client.post("/field-checks", json={**ok, "plan_id": "../x"}).status_code == 400
    used = {x["point_id"] for x in j["plan"]}
    other = next(int(p) for p in client.app.state.data.ctx.sites.point_id if int(p) not in used)
    assert client.post("/field-checks", json={**ok, "point_id": other}).status_code == 422
    assert client.post("/field-checks", json={**ok, "reason": "paved"}).status_code == 422
    assert client.post("/field-checks", json={**ok, "status": "verified_plantable"}).status_code == 422     # a count only goes with planted
    assert fv.n_events(client.app.state.data.field_db) == 0
    r = client.post("/field-checks", json=ok)
    assert r.status_code == 201 and r.json()["saved"]["status"] == "planted" and r.json()["saved"]["trees_planted"] == it["trees_planned"]
    assert "trees planted" in r.json()["effect"]


def test_planted_on_a_points_plan_is_refused(client):
    j = make(client, {"layout_mode": "points", "n_saplings": 20})
    r = client.post("/field-checks", json={"point_id": j["plan"][0]["point_id"], "status": "planted", "observer": "Ana", "plan_id": j["plan_id"], "trees_planted": 1})
    assert r.status_code == 422 and "points mode" in r.json()["detail"]


def test_planted_shows_as_verified_on_the_grid_and_is_not_left_out(client, data):
    j = make(client)
    assert mark(client, j, 0).status_code == 201
    pid = j["plan"][0]["point_id"]
    assert pid not in data.field_ex_ids and data.field_current[pid]["status"] == "planted"
    assert fv.status_code(data.field_current[pid]) == 1
    assert client.get("/field-checks/summary").json()["trees_planted_total"] == j["plan"][0]["trees_planned"]


# ---- progress -----------------------------------------------------------------------------------------------------------------------------
def test_progress_before_any_field_work_everything_is_to_do(client):
    j = make(client)
    p = client.get(f"/plans/{j['plan_id']}/progress").json()
    assert p["trees"] == {"planned": 300, "planted": 0, "remaining": 300, "problem": 0, "percent_planted": 0.0}
    assert p["blocks"] == {"total": len(j["plan"]), "done": 0, "partly": 0, "problem": 0, "to_do": len(j["plan"])} and p["shortfall"]["trees"] == 0
    assert sum(e["planned"] for e in p["per_species"]) == 300 and p["campaign"]["name"] == "Tree Day"


def test_progress_totals_partial_and_problem_blocks(client):
    j = make(client)
    n = len(j["plan"])
    assert n >= 5
    full, part_n = j["plan"][0]["trees_planned"], 0
    assert mark(client, j, 0).status_code == 201                                             # all trees
    it1 = j["plan"][1]
    part_n = max(1, it1["trees_planned"] // 2)
    assert mark(client, j, 1, trees=part_n).status_code == 201                              # partly
    assert mark(client, j, 2, status="not_plantable").status_code == 201                    # problem
    assert mark(client, j, 3, status="needs_recheck").status_code == 201                    # still to do, flagged
    p = client.get(f"/plans/{j['plan_id']}/progress").json()
    t2 = j["plan"][2]["trees_planned"]
    done_state = [b["state"] for b in p["blocks_list"]]
    assert p["blocks"] == {"total": n, "done": 1 if full else 0, "partly": 1 if part_n < it1["trees_planned"] else 0, "problem": 1, "to_do": n - 3}
    assert p["trees"]["planted"] == full + part_n and p["trees"]["problem"] == t2 == p["shortfall"]["trees"]
    assert p["trees"]["remaining"] == 300 - (full + part_n) - t2
    assert p["trees"]["planned"] - p["trees"]["planted"] - p["trees"]["problem"] == p["trees"]["remaining"]
    assert [b["needs_recheck"] for b in p["blocks_list"]].count(True) == 1 and done_state.count("problem") == 1
    assert sum(e["planted"] for e in p["per_species"]) == p["trees"]["planted"] and sum(e["problem_trees"] for e in p["per_species"]) == t2
    assert p["blocks_list"][2]["reason"] == "rock_or_ledge" and p["blocks_list"][0]["observer"] == "Ana"


def test_a_later_event_replaces_the_earlier_one_for_progress(client):
    j = make(client)
    mark(client, j, 0, trees=1)
    mark(client, j, 0)                                                                       # now all trees
    mark(client, j, 1, status="not_plantable")
    mark(client, j, 1, status="verified_plantable", note="the owner cleared it")             # clearing a problem needs a note
    p = client.get(f"/plans/{j['plan_id']}/progress").json()
    assert p["blocks_list"][0]["state"] == "done" and p["blocks_list"][1]["state"] == "to_do" and p["shortfall"]["trees"] == 0


def test_planted_only_counts_for_the_plan_it_was_saved_for(client):
    a = make(client)
    b = make(client)                                                                         # same request and seed: the same squares
    assert [i["point_id"] for i in a["plan"]] == [i["point_id"] for i in b["plan"]] and a["plan_id"] != b["plan_id"]
    mark(client, a, 0)
    assert client.get(f"/plans/{a['plan_id']}/progress").json()["trees"]["planted"] == a["plan"][0]["trees_planned"]
    assert client.get(f"/plans/{b['plan_id']}/progress").json()["trees"]["planted"] == 0
    mark(client, a, 1, status="not_plantable")                                               # a fact about the square: counts for every plan
    assert client.get(f"/plans/{b['plan_id']}/progress").json()["blocks"]["problem"] == 1


def test_progress_rejects_bad_plan_ids(client):
    assert client.get("/plans/plan_nope_1/progress").status_code == 404
    assert client.get("/plans/bad.id/progress").status_code == 400
    assert client.post("/plans/bad.id/top-up").status_code == 400
    assert client.post("/plans/plan_nope_1/top-up").status_code == 404


# ---- top-up ---------------------------------------------------------------------------------------------------------------------------
def test_top_up_restores_the_trees_of_problem_blocks(client):
    j = make(client)
    mark(client, j, 0, status="not_plantable")
    mark(client, j, 1, status="not_plantable", reason="paved")
    lost = j["plan"][0]["trees_planned"] + j["plan"][1]["trees_planned"]
    r = client.post(f"/plans/{j['plan_id']}/top-up")
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["parent_plan_id"] == j["plan_id"] and t["layout_mode"] == "blocks" and t["summary"]["parent_plan_id"] == j["plan_id"]
    assert t["campaign"]["name"] == "Tree Day (top-up 1)" and t["campaign"]["unit"] == "Team A" and t["campaign"]["start"] == "2027-05-01" and t["campaign"]["end"] == "2027-06-29"
    assert sum(i["trees_planned"] for i in t["plan"]) == lost == t["topup"]["parent_shortfall_trees"] and t["summary"]["purpose"] == "urban"
    used = {i["point_id"] for i in j["plan"]}
    assert not ({i["point_id"] for i in t["plan"]} & used)                                   # never a square of the parent plan
    want = {}
    for k in (0, 1):
        want[j["plan"][k]["species_id"]] = want.get(j["plan"][k]["species_id"], 0) + j["plan"][k]["trees_planned"]
    got = {}
    for i in t["plan"]:
        got[i["species_id"]] = got.get(i["species_id"], 0) + i["trees_planned"]
    assert got == want
    g = client.get(f"/plans/{j['plan_id']}").json()
    assert g["child_plan_ids"] == [t["plan_id"]]
    lst = {p["plan_id"]: p for p in client.get("/plans").json()["plans"]}
    assert lst[t["plan_id"]]["parent_plan_id"] == j["plan_id"] and lst[t["plan_id"]]["campaign"]["name"] == "Tree Day (top-up 1)"
    assert client.get(f"/plans/{t['plan_id']}").json()["parent_plan_id"] == j["plan_id"]
    assert client.get(f"/plans/{j['plan_id']}/progress").json()["child_plan_ids"] == [t["plan_id"]]


def test_top_up_never_uses_squares_marked_not_plantable(client):
    j = make(client)
    mark(client, j, 0, status="not_plantable")
    first = client.post(f"/plans/{j['plan_id']}/top-up").json()
    bad = first["plan"][0]["point_id"]
    client.post("/field-checks", json={"point_id": bad, "status": "not_plantable", "reason": "paved", "observer": "Ben"})
    assert bad in client.app.state.data.field_ex_ids
    again = client.post(f"/plans/{j['plan_id']}/top-up")
    assert again.status_code == 400 and "already covered" in again.json()["detail"]          # the first top-up already plans the lost trees
    second = client.post(f"/plans/{first['plan_id']}/top-up")                                # the top-up itself lost a block
    assert second.status_code == 200
    s = second.json()
    squares = {i["point_id"] for i in j["plan"]} | {i["point_id"] for i in first["plan"]}
    assert not ({i["point_id"] for i in s["plan"]} & squares) and bad not in {i["point_id"] for i in s["plan"]}
    assert s["campaign"]["name"] == "Tree Day (top-up 2)" and s["parent_plan_id"] == first["plan_id"]


def test_top_up_with_nothing_lost_is_refused_in_plain_words(client):
    j = make(client)
    r = client.post(f"/plans/{j['plan_id']}/top-up")
    assert r.status_code == 400 and "Nothing to top up" in r.json()["detail"]
    assert len(client.get("/plans").json()["plans"]) == 1


def test_top_up_can_include_the_remaining_trees(client):
    j = make(client)
    mark(client, j, 0)
    mark(client, j, 1, status="not_plantable")
    r = client.post(f"/plans/{j['plan_id']}/top-up", json={"include_remaining": True})
    assert r.status_code == 200, r.text
    p = client.get(f"/plans/{j['plan_id']}/progress").json()
    assert sum(i["trees_planned"] for i in r.json()["plan"]) == p["trees"]["problem"] + p["trees"]["remaining"] and r.json()["topup"]["include_remaining"] is True


def test_the_top_up_keeps_the_settings_of_the_parent(client):
    j = make(client, {"purpose": "watershed", "n_saplings": 200, "barangay": "Santa Ana"})
    mark(client, j, 0, status="not_plantable")
    t = client.post(f"/plans/{j['plan_id']}/top-up").json()
    assert t["summary"]["purpose"] == "watershed" and t["summary"]["area_choice"]["name"] == j["summary"]["area_choice"]["name"]
    assert t["summary"]["request"]["barangay"] == "Santa Ana" and t["summary"]["request"]["seed"] == 4
    assert all(i["barangay"] == j["plan"][0]["barangay"] for i in t["plan"])


def test_a_long_campaign_name_is_cut_to_fit(client):
    j = make(client, {"campaign": {"name": "N" * 80, "unit": ""}})
    mark(client, j, 0, status="not_plantable")
    t = client.post(f"/plans/{j['plan_id']}/top-up").json()
    assert len(t["campaign"]["name"]) <= 80 and t["campaign"]["name"].endswith("(top-up 1)")


# ---- the kit and the import of blocks.csv --------------------------------------------------------------------------------------------------
def kit_rows(client, data, j):
    r = client.post(f"/plans/{j['plan_id']}/field-kit")
    assert r.status_code == 200, r.text
    with zipfile.ZipFile(api_v2.kit_zip_path(data, j["plan_id"])) as z:
        names = {n.rsplit("/", 1)[-1] for n in z.namelist()}
        text = z.read(next(n for n in z.namelist() if n.endswith("blocks.csv"))).decode("utf-8")
        pl = z.read(next(n for n in z.namelist() if n.endswith("point-list.csv"))).decode("utf-8")
        readme = z.read(next(n for n in z.namelist() if n.endswith("README.txt"))).decode("utf-8")
    return names, list(csv.DictReader(io.StringIO(text))), list(csv.DictReader(io.StringIO(pl))), readme, r.json()


def to_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def post_import(client, text, observer="Team Alpha", **q):
    return client.post("/field-checks/import", params={"observer": observer, **q}, content=text.encode("utf-8"), headers={"Content-Type": "text/csv"})


def test_kit_has_blocks_csv_with_the_agreed_columns_and_point_list_keeps_its_own(client, data):
    j = make(client)
    names, blocks, points, readme, info = kit_rows(client, data, j)
    assert {"blocks.csv", "point-list.csv", "points.gpx", "points.kml", "README.txt", "manifest.json"} <= names
    cols = list(blocks[0])
    assert cols[:22] == ["block_ref", "point_id", "lat", "lon", "utm_e", "utm_n", "species_code", "common_name", "trees_planned", "spacing_m", "rows", "trees_per_row", "row_direction",
                         "start_corner", "barangay", "zone", "flags", "notes", "status", "trees_planted", "moved_lat", "moved_lon"] and cols[22:24] == ["plan_id", "check_code"] and len(cols) == 32
    assert len(blocks) == len(j["plan"]) and sum(int(b["trees_planned"]) for b in blocks) == 300 and {b["block_ref"] for b in blocks} == {i["block_ref"] for i in j["plan"]}
    assert all(b["status"] == "" and b["trees_planted"] == "" for b in blocks)
    assert list(points[0]) == ["point_ref", "point_id", "lat", "lon", "utm_e", "utm_n", "species_code", "common_name", "flags", "notes", "status", "moved_lat", "moved_lon", "plan_id", "check_code"] \
        or "point_ref" in points[0]
    assert "Block of" in points[0]["notes"] and len(points) == len(blocks)
    for word in ("tape", "pace", "south-west", "east", "count", "blocks.csv"):
        assert word in readme.lower()
    assert info["manifest"]["counts"]["trees"] == 300 and info["manifest"]["counts"]["blocks"] == len(blocks)


def test_import_of_blocks_csv_counts_trees_and_is_idempotent(client, data):
    j = make(client)
    _, blocks, _, _, _ = kit_rows(client, data, j)
    blocks[0]["status"], blocks[0]["trees_planted"] = "planted", blocks[0]["trees_planned"]
    blocks[1]["status"], blocks[1]["trees_planted"] = "planted", "3"
    blocks[2]["status"] = "paved"
    blocks[3]["trees_planted"] = "2"                                                         # a count without a word means planted
    blocks[4]["status"], blocks[4]["trees_planted"] = "planted", str(int(blocks[4]["trees_planned"]) + 1)      # more than the block holds: rejected
    text = to_csv(blocks)
    rep = post_import(client, text).json()
    assert (rep["accepted"], rep["rejected"], rep["duplicates"]) == (4, 1, 0) and "more than" in next(x for x in rep["rows"] if x["outcome"] == "rejected")["reason"]
    p = client.get(f"/plans/{j['plan_id']}/progress").json()
    assert p["trees"]["planted"] == int(blocks[0]["trees_planned"]) + 3 + 2 and p["blocks"]["problem"] == 1
    again = post_import(client, text).json()
    assert (again["accepted"], again["duplicates"], again["rejected"]) == (0, 4, 1)
    assert fv.n_events(data.field_db) == 4
    assert client.get(f"/plans/{j['plan_id']}/progress").json()["trees"]["planted"] == p["trees"]["planted"]


def test_import_refuses_a_file_of_another_check_code(client, data):
    j = make(client)
    _, blocks, _, _, _ = kit_rows(client, data, j)
    blocks[0]["status"], blocks[0]["check_code"] = "planted", "deadbeef"
    rep = post_import(client, to_csv(blocks)).json()
    assert rep["accepted"] == 0 and rep["rejected"] == 1 and "check code" in rep["rows"][0]["reason"]


def test_point_list_import_keeps_the_old_words_and_planted_means_all_trees(client, data):
    j = make(client)
    _, _, points, _, _ = kit_rows(client, data, j)
    points[0]["status"] = "planted"
    points[1]["status"] = "x"
    rep = post_import(client, to_csv(points)).json()
    assert rep["accepted"] == 2
    p = client.get(f"/plans/{j['plan_id']}/progress").json()
    by = {b["point_id"]: b for b in p["blocks_list"]}
    b0, b1 = by[int(points[0]["point_id"])], by[int(points[1]["point_id"])]
    assert b0["state"] == "done" and b0["trees_planted"] == b0["trees_planned"]
    assert b1["field_status"] == "verified_plantable" and b1["state"] == "to_do"
