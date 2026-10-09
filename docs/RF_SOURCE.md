# Random Forest as an optional source of S (round 19)

**Status: built, NOT switched on.** The default is `S_SOURCE = "rules"`: the app behaves exactly as before. Switching to `"rf"` needs the team's approval.

## The hybrid, in order
1. **Expert rules** (`pipeline/score_sites.py`): every square x species pair gets `s_rule` (0 to 1) from fixed rules (elevation, slope, soil, wetness, zone). Hard gates make S = 0.
2. **Random Forest** (`pipeline/train_rf.py`): learns from the pair table (`make_pair_table.py`: raw site values and raw species traits) to predict the rule label S >= 0.50 (no label noise). Its probability is stored as `s_prob` in `scores/site_scores`.
3. **Hungarian matching** (`pipeline/matching.py`): unchanged. It uses whichever S the setting names.

## How the probabilities are made
- **Spatial out-of-fold.** The squares are cut into blocks of 10 x 10 grid cells (about 1 km). A block is never split between training and test (GroupKFold, 5 folds, the same blocks and seed as the model comparison). Every pair gets its probability from the model of the fold where its block was the test part, so no pair is scored by a model that trained on its neighbourhood (`tests/test_rf_source.py` checks this).
- **Hard gates kept.** Where the rule S is 0 (outside the zone, outside the elevation range, beyond the slope hard stop) `s_prob` is set to 0 and the pair stays rejected. The zone is a gate, not a feature.
- **Model file.** `data/processed/models/rf_site_suitability.joblib` (trained on all pairs; git-ignored) and `rf_site_suitability_meta.json` (training date, dataset hash `34964a09fe44`, features, settings, out-of-fold accuracy). Random Forest settings: 200 trees, no depth limit, at least 5 pairs per leaf, seed 42.
- **Order of the pipeline:** `score_sites.py` -> `make_pair_table.py` -> `train_rf.py`. Running `score_sites.py` again empties `s_prob`; run `make_pair_table.py` and `train_rf.py` again afterwards.

## The setting
`S_SOURCE` in `pipeline/matching.py` ("rules" | "rf", default "rules"); the environment variable `OS_S_SOURCE` or `API_CFG["s_source"]` in `api_v2.py` override it without editing code. With "rf" the probability replaces S everywhere S is used: `mt.weights` (W and the 0.50 eligibility test), `/rank`, `/grid`, `/areas/rank`, `/rank/area`, `/nearest-viable`, palettes, plans and the matching. `GET /health` shows `s_source` and the model's training date and hash. With "rf", "Why this score?" has the line "Suitability from the Random Forest: 0.83. Rules check: passed." (and a note); with "rules" it is not shown.

## What the numbers say (graded slope mode; `data/processed/rf_vs_rules_report.txt`)
- **Eligibility:** rules 257,869 pairs, forest 257,961. 152 pairs change (0.04%): 30 eligible only by the rules, 122 only by the forest.
- **Out-of-fold accuracy (spatial folds, no noise):** Random Forest 0.9996, Decision Tree 0.9995. They are equal within the spread between folds (0.0003 to 0.0004). The forest is not clearly better than a single tree.
- **Top-20 squares per species:** the two lists share 10.4 of 20 squares on average. The rules tie on the top S for a median of about 2,300 squares per species, so which 20 are "the top" is mostly the tie-break.
- **Matching (Hungarian and greedy tie in both modes):** the plans differ a lot (for example 14 of 300 squares shared for planting, no square shared in blocks mode). Each plan is best by its own score; judged by the other score each loses a little: the plan made with the forest, judged by the rules, loses 5 to 10% of total W (urban points 190.3 against 201.9, planting 171.0 against 180.2, watershed 166.6 against 184.5); the rules' plan judged by the forest loses under 1%.

## Why the forest does not rank better than the rules (read this)
The label the forest learns is yes/no (S >= 0.50). It learns where the rules say yes. It does **not** learn how good a yes is (S = 0.55 or S = 1.0 look alike to it), so many squares end with a probability close to 1 and the matching then picks among them almost arbitrarily. The rules keep the gradation. This is the main reason not to prefer `"rf"` on accuracy alone.

## What it is and is not
The forest is trained on **expert-rule labels**, so it generalises the rules: it smooths their sharp edges and can score a square the rules would barely accept slightly differently. It is **not an independent measurement of survival** and has no field data behind it. Its very high accuracy only shows that the rules are easy to learn. Nothing here validates the rules against real planting results.
