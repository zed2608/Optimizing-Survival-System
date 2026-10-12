import sys, numpy as np, pandas as pd
R = "."  # run from the repo root: python scripts/scarcity_benchmark_draft.py
sys.path.insert(0, R + "/pipeline")
import score_sites as ss, matching as mt
sp = pd.read_csv(R + "/data/processed/species_clean.csv")
si = pd.read_csv(R + "/data/processed/site_points_clean.csv")
si = si[si.zoning_status.isin(["confirmed", "unconfirmed"])].reset_index(drop=True)
si["water_dist_m"] = np.nan  # wetness not evaluated here (no geopandas); small effect
sc = ss.score_pairs(sp, si)
S = sc.pivot(index="point_id", columns="species_id", values="s_rule").loc[si.point_id, sp.species_id].to_numpy()
ps = pd.read_csv(R + "/data/processed/purpose_scores.csv")
pcol = [c for c in ps.columns if c in ("p_score", "P", "score")][0]
rng = np.random.default_rng(1)
rows = []
for purpose in ["urban", "planting", "watershed"]:
    P = ps[ps.purpose == purpose].set_index("species_id")[pcol].reindex(sp.species_id).to_numpy()
    for trial in range(300):
        size = rng.choice([5, 8, 12])                    # window of size x size cells (~0.5-1.2 km)
        r0 = rng.integers(0, si.cell_row.max() - size); c0 = rng.integers(0, si.cell_col.max() - size)
        m = si.cell_row.between(r0, r0 + size - 1) & si.cell_col.between(c0, c0 + size - 1)
        idx = np.where(m)[0]
        if len(idx) < 6: continue
        k = rng.integers(2, 6)                           # user picks 2-5 species
        cand = np.where((S[idx] >= 0.5).sum(0) > 0)[0]
        if len(cand) < k: continue
        chosen = rng.choice(cand, k, replace=False)
        Ssub = S[np.ix_(idx, chosen)]; W = np.where(Ssub >= 0.5, Ssub * P[chosen], 0.0); F = Ssub >= 0.5
        n_ok = F.any(1).sum()
        frac = rng.choice([0.3, 0.6, 0.9])               # trees asked vs suitable squares
        total = max(k, int(frac * n_ok))
        q = np.full(k, total // k); q[: total - q.sum()] += 1
        h = mt.assign_hungarian(W, F, q); g = mt.assign_greedy(W, F, q)
        def tot(res):
            pi, sj = (res["point_idx"], res["species_idx"]) if isinstance(res, dict) else res[:2]
            return float(W[np.asarray(pi, int), np.asarray(sj, int)].sum()), len(pi)
        th, nh = tot(h); tg, ng = tot(g)
        rows.append(dict(purpose=purpose, size=size, k=k, frac=frac, n_ok=n_ok, total=total, hung=th, greedy=tg, placed_h=nh, placed_g=ng))
d = pd.DataFrame(rows); d["gap_pct"] = 100 * (d.hung - d.greedy) / d.hung.where(d.hung > 0)
print("cases:", len(d)); print("greedy worse in:", (d.gap_pct > 1e-6).sum(), f"({(d.gap_pct>1e-6).mean():.0%})")
print("placed fewer trees (greedy):", (d.placed_g < d.placed_h).sum())
print(d.groupby("frac").gap_pct.describe()[["count", "mean", "50%", "max"]].round(2))
print(d.groupby("k").gap_pct.agg(["mean", "max"]).round(2))
print(d.sort_values("gap_pct").tail(5)[["purpose","size","k","frac","n_ok","total","hung","greedy","placed_h","placed_g","gap_pct"]].round(2))
d.to_csv("data/processed/scarcity_draft_results.csv", index=False)
