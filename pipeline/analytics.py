"""Small pure helpers of the System Analytics endpoint (api_v2.py GET /analytics/summary). They only count what already exists (scores, pH estimates, saved plans, saved field checks);
nothing here changes or reads back into a score, and nothing is forecast."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np

S_EDGES = [round(0.1 * i, 1) for i in range(11)]           # 0.0 ... 1.0
PH_EDGES = [3.0 + 0.5 * i for i in range(14)]               # 3.0 ... 9.5


def histogram(values, edges, zero_separate=False):
    """Counts of `values` in [edge_i, edge_i+1) (the last bin includes its upper edge). With zero_separate the exact zeros (a rejected pair has S = 0) are counted apart."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    zero = int((v == 0).sum()) if zero_separate else 0
    if zero_separate:
        v = v[v != 0]
    counts, _ = np.histogram(v, bins=edges)
    return {"zero": zero, "bins": [{"lo": float(edges[i]), "hi": float(edges[i + 1]), "count": int(c)} for i, c in enumerate(counts)], "n": int(len(v)) + zero}


def verdict_counts(q05, q95, lo, hi):
    """Counts of the pH verdict codes for one species range against many squares (the rule of soilgrids_ph.compare_interval, vectorised). q05 / q95 may hold NaN (no estimate)."""
    q05, q95 = np.asarray(q05, dtype=float), np.asarray(q95, dtype=float)
    none = np.isnan(q05) | np.isnan(q95)
    if lo is None or hi is None:
        return {"no_range": int(len(q05))}
    inside = ~none & (q05 >= lo) & (q95 <= hi)
    outside = ~none & ((q95 < lo) | (q05 > hi))
    uncertain = ~none & ~inside & ~outside
    return {"inside": int(inside.sum()), "outside": int(outside.sum()), "uncertain": int(uncertain.sum()), "no_value": int(none.sum())}


def week_start(iso):
    """Monday of the ISO week of a timestamp (YYYY-MM-DD[...]) as YYYY-MM-DD, or None when it cannot be read."""
    try:
        d = datetime.fromisoformat(str(iso)[:19]).date()
    except ValueError:
        try:
            d = date.fromisoformat(str(iso)[:10])
        except ValueError:
            return None
    return (d - timedelta(days=d.weekday())).isoformat()


def parse_day(text):
    """None for no text, a date, or False when the text is not YYYY-MM-DD."""
    if not text:
        return None
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return False
