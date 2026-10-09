#!/usr/bin/env python3
"""Which saved plans would come out different with the graded slope rule? (round 18b)

For every saved plan (data/processed/plans) the same request is made again against two COPIES of the processed data, one scored with SLOPE_MODE hard and one with graded
(the real plans folder is only read; nothing is deleted or written there). The two results are compared square by square and species by species.
For the oldest plans, which have no request saved (made on the command line before round 10a), the request is rebuilt from the summary
(purpose, number of trees, seed, points mode); this is an approximation and the report says so.

    python scripts/slope_plans_compare.py --hard <processed copy scored hard> --graded <processed copy scored graded> --plans data/processed/plans --out data/processed

Writes <out>/slope_plans_report.txt.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def requests_from(plans_dir):
    out = []
    for sj in sorted(Path(plans_dir).glob("plan_*_summary.json")):
        s = json.loads(sj.read_text(encoding="utf-8"))
        pid = sj.name[: -len("_summary.json")]
        if "request" in s:
            r = s["request"]
            q = {k: r[k] for k in ("start", "end", "season_filter") if r.get(k)}
            body = {k: r[k] for k in ("purpose", "n_saplings", "layout_mode", "zone", "barangay", "polygon", "seed", "species_ids", "species_counts") if r.get(k) is not None}
            if body.get("species_counts"):
                body["species_counts"] = {int(k): int(v) for k, v in body["species_counts"].items()}
                body.pop("n_saplings", None)
            approx = False
        else:
            body = {"purpose": s["purpose"], "n_saplings": int(s["n_saplings_requested"]), "layout_mode": "points", "seed": s.get("seed", 42)}
            q = {"include_unzoned": "false"}
            approx = True
        out.append({"plan_id": pid, "body": body, "query": q, "approx": approx, "saved_csv": str(sj.with_name(pid + ".csv"))})
    return out


def worker(processed, reqs_json, out_json):
    """Runs inside a process whose OS_DATA_DIR points at one processed copy."""
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "pipeline"))
    import api_v2
    from fastapi.testclient import TestClient
    reqs = json.loads(Path(reqs_json).read_text(encoding="utf-8"))
    res = {}
    with TestClient(api_v2.app) as c:
        for r in reqs:
            body = dict(r["body"])
            body["campaign"] = {"name": "compare " + r["plan_id"], "unit": ""}
            resp = c.post("/plan-event", params=r["query"], json=body)
            if resp.status_code != 200:
                res[r["plan_id"]] = {"error": resp.text[:200]}
                continue
            j = resp.json()
            res[r["plan_id"]] = {"items": sorted([[int(i["point_id"]), int(i["species_id"]), int(i.get("trees_planned", 1))] for i in j["plan"]]),
                                 "placed": j["n_placed"], "flags": sorted({f for i in j["plan"] for f in i["flags"] if f == "slope_graded"})}
    Path(out_json).write_text(json.dumps(res), encoding="utf-8")


def run_mode(processed, reqs_json, out_json):
    env = dict(os.environ, OS_DATA_DIR=str(processed))
    subprocess.run([sys.executable, __file__, "--worker", str(processed), reqs_json, out_json], check=True, env=env, cwd=ROOT)
    return json.loads(Path(out_json).read_text(encoding="utf-8"))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        return worker(*sys.argv[2:5])
    ap = argparse.ArgumentParser()
    ap.add_argument("--hard", required=True)
    ap.add_argument("--graded", required=True)
    ap.add_argument("--plans", default="data/processed/plans")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--tmp", default=None)
    a = ap.parse_args()
    tmp = Path(a.tmp or Path(a.out) / "cache")
    tmp.mkdir(parents=True, exist_ok=True)
    reqs = requests_from(a.plans)
    rj = tmp / "slope_plans_requests.json"
    rj.write_text(json.dumps(reqs), encoding="utf-8")
    hard = run_mode(a.hard, str(rj), str(tmp / "slope_plans_hard.json"))
    gr = run_mode(a.graded, str(rj), str(tmp / "slope_plans_graded.json"))
    import pandas as pd
    L = []
    P = L.append
    P("Saved plans: would they come out different with the graded slope rule? (round 18b)")
    P("Method: each saved request is made again on two copies of the current data, scored hard and graded. Nothing in the plans folder is changed or deleted.")
    P("'rule effect' = the graded result differs from the hard result of today (squares or species). 'since saved' = the hard result of today differs from the saved plan (other changes since it was made, for example the zone rules).")
    P("")
    P(f"{'plan':<32} {'trees':>5} {'rebuilt from':<14} {'rule effect':<12} {'squares changed':>15} {'species changed':>15} {'since saved':<12}")
    n_diff = 0
    for r in reqs:
        h, g = hard[r["plan_id"]], gr[r["plan_id"]]
        if "error" in h or "error" in g:
            P(f"{r['plan_id']:<32} could not be repeated: {h.get('error') or g.get('error')}")
            continue
        hs, gs = {(p, s) for p, s, _ in h["items"]}, {(p, s) for p, s, _ in g["items"]}
        sq_h, sq_g = {p for p, _, _ in h["items"]}, {p for p, _, _ in g["items"]}
        sp_h, sp_g = {s for _, s, _ in h["items"]}, {s for _, s, _ in g["items"]}
        saved = pd.read_csv(r["saved_csv"])
        ss_ = {(int(x.point_id), int(x.species_id)) for x in saved.itertuples()}
        diff = hs != gs
        n_diff += diff
        P(f"{r['plan_id']:<32} {h['placed']:>5} {'summary (approx)' if r['approx'] else 'saved request':<14} {'DIFFERS' if diff else 'same':<12} {len(sq_h ^ sq_g):>15} {len(sp_h ^ sp_g):>15} {'differs' if hs != ss_ else 'same':<12}"
          + (f"  slope caution on {len(g['flags'])} flag" if g["flags"] else ""))
    P("")
    P(f"{n_diff} of {len(reqs)} saved plans would come out different with the graded rule on today's data.")
    (Path(a.out) / "slope_plans_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
