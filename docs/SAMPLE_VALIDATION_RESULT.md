# Sample validation result (agriculturist marks, 7 Oct 2026)

**This does not validate the model.** It compares one reviewer's marks on 40 sample pairs with the site score S that the current pipeline gives. It is a first look at where the rules and a farm expert disagree, nothing more.

## What was compared
- Marks: `data/validation/agri_sample_marks_20261007.csv`: Alexis P. Santos, OIC-MAO, signed 7 Oct 2026, sheet of dataset v0.1-draft (hash 3483e2b668e8), 7 of the 8 pages signed, no comments. S = Suitable, M = Marginal, N = Not suitable, X = Cannot judge.
- Model: S recomputed for each (grid point, species) pair with `pipeline/score_sites.py` (the current pipeline, release v1.0-review, LGU soil layer, the zone rules of round 15a). The model says "suitable" when S >= 0.50.
- **Slope rule: this comparison is scored with SLOPE_MODE = "hard"** (the slope gate as it was when the sheet was printed). The graded slope rule of round 18 (the production default since then, provisional, awaiting adviser confirmation) is NOT used here, so the numbers below are the ones of the printed sheet.
- Marks given: {'S': 25, 'M': 11, 'X': 4}. Four pairs (X) were left out of every figure below.

## Agreement
| Marginal counted as | Agreement | Cohen's kappa |
|---|---|---|
| Marginal counted as Suitable | 69.4% | 0.00 |
| Marginal counted as Not suitable | 66.7% | 0.21 |

Reading: about two thirds of the judged pairs agree either way. When Marginal counts as Suitable the reviewer says "suitable" for every judged pair, so there is nothing for kappa to measure (0.00 = no better than chance); when Marginal counts as Not suitable kappa is 0.21, a weak agreement.

Pairs the reviewer marked Suitable or Marginal but the model scores below 0.50:

| Sample | Species | Grid | Mark | S today | Gate failed |
|---|---|---|---|---|---|
| S04 | Robusta (Coffee) | 3258 | S | 0.00 | elevation |
| S05 | Lemon | 6977 | M | 0.00 | slope |
| S08 | Narra | 4847 | M | 0.00 | slope |
| S16 | Yakal | 5281 | M | 0.00 | slope |
| S17 | Robusta (Coffee) | 6638 | S | 0.00 | elevation |
| S20 | Robusta (Coffee) | 10365 | S | 0.00 | elevation |
| S22 | Guava | 5514 | S | 0.00 | slope |
| S29 | Lemon | 4603 | M | 0.00 | slope |
| S30 | Talisay | 6424 | S | 0.00 | slope |
| S31 | Kamias | 4954 | M | 0.00 | slope |
| S40 | Narra | 5045 | S | 0.00 | slope |

## Slope sensitivity (analysis only; production scoring is unchanged)
9 of the 40 sample pairs fail on slope today (8 judged, 1 marked Cannot judge); the request expected 7, so the list below has the two more that the script found.

Production rule: S = 0 where the slope is steeper than the species limit (a gate). Alternative: slope factor = max(0, 1 - (slope - max) / (0.5 x max)), so a slope slightly over the limit lowers S instead of zeroing it. Every other gate and factor stays the same.

| Sample | Species | Grid | Mark | Slope % | Limit % | Over | S today | S alternative | Crosses 0.50 |
|---|---|---|---|---|---|---|---|---|---|
| S05 | Lemon | 6977 | M | 41.9 | 20 | +21.9 | 0.00 | 0.562 | yes |
| S07 | Calamansi | 5941 | X | 28.3 | 25 | +3.3 | 0.00 | 0.747 | yes |
| S08 | Narra | 4847 | M | 31.6 | 30 | +1.6 | 0.00 | 0.785 | yes |
| S16 | Yakal | 5281 | M | 56.5 | 45 | +11.5 | 0.00 | 0.684 | yes |
| S22 | Guava | 5514 | S | 25.5 | 25 | +0.5 | 0.00 | 0.990 | yes |
| S29 | Lemon | 4603 | M | 22.1 | 20 | +2.1 | 0.00 | 0.759 | yes |
| S30 | Talisay | 6424 | S | 45.3 | 30 | +15.3 | 0.00 | 0.562 | yes |
| S31 | Kamias | 4954 | M | 20.2 | 20 | +0.2 | 0.00 | 0.806 | yes |
| S40 | Narra | 5045 | S | 32.3 | 30 | +2.3 | 0.00 | 0.774 | yes |

- On today's grid the alternative rule would add 105221 pairs with S >= 0.50 to the 249389 that have it now.
- On the grid before round 15a (7,530 squares, Cemetery scored, the base of the 228,919 pairs) it would add 104209 to 228919.

## Robusta and elevation
The data gives Robusta an elevation range of 300 to 800 m. The reviewer marked all three Robusta pairs Suitable, at much lower places:

| Sample | Grid | Elevation (m) | Range in the data (m) | S today | Gate failed |
|---|---|---|---|---|---|
| S04 | 3258 | 16 | 300-800 | 0.00 | elevation |
| S17 | 6638 | 199 | 300-800 | 0.00 | elevation |
| S20 | 10365 | 189 | 300-800 | 0.00 | elevation |

## Limits
- One reviewer, one afternoon, 40 pairs (36 judged, 4 "cannot judge"); 7 of the 8 pages of the sheet were signed.
- There are no "Not suitable" marks at all, so the sample cannot show whether the model correctly rejects bad pairs; agreement is mostly "model also says suitable".
- The 40 pairs were chosen for review, not drawn to represent all 360,450 pairs.
- "Marginal" has no fixed meaning in the model, so it is counted both ways.
- The printed sheet (dataset v0.1-draft) is not in the repository, so today's verdicts could not be compared with the verdicts printed on the sheet.
- The marks are a judgement, not a measurement of survival. Nothing here proves that trees survive where S is high.

## Full printout
```
S recomputed for 40 pairs; identical to the stored site_scores.db value for all but 6 (['S07', 'S08', 'S22', 'S29', 'S31', 'S40']).
These differ only because the stored site_scores.db is now made with the graded slope rule (round 18) and the sample is scored with the hard gate, as printed.
Marks: {'S': 25, 'M': 11, 'X': 4}; judged pairs 36, cannot judge 4 (S07, S12, S14, S19).
Model verdict today (S >= 0.5): suitable 25, not suitable 11 of 36 judged pairs.
Marginal counted as Suitable: agreement 69.4% (25 of 36), Cohen's kappa 0.00.
   by group: high-value crop: 14/21 agree, kappa 0.00; native timber: 6/10 agree, kappa 0.00; other (fruit, ornamental, grass): 5/5 agree, kappa undefined
   by mark: mark M: 6/11 agree; mark S: 19/25 agree
Marginal counted as Not suitable: agreement 66.7% (24 of 36), Cohen's kappa 0.21.
   by group: high-value crop: 15/21 agree, kappa 0.31; native timber: 6/10 agree, kappa 0.17; other (fruit, ornamental, grass): 3/5 agree, kappa 0.00
   by mark: mark M: 5/11 agree; mark S: 19/25 agree
Pairs the agriculturist marked Suitable but the model says not suitable (S below 0.5): 6: S04 Robusta (Coffee) grid 3258 S=0.00 gate elevation; S17 Robusta (Coffee) grid 6638 S=0.00 gate elevation; S20 Robusta (Coffee) grid 10365 S=0.00 gate elevation; S22 Guava grid 5514 S=0.00 gate slope; S30 Talisay grid 6424 S=0.00 gate slope; S40 Narra grid 5045 S=0.00 gate slope
Pairs marked Marginal where the model says suitable: 6 (S03, S06, S09, S15, S35, S36).
Printed-sheet verdicts read from sample_printed_verdicts.csv (40 of 40 pairs). Pairs whose verdict changed between the printed sheet and today (S now = suitable at S >= 0.50, N = not): 0 changed, 0 printed Marginal (listed too):
SLOPE SENSITIVITY (analysis only): 9 sample pairs fail on slope (the request expected 7).
   S05 Lemon grid 6977 (mark M): slope 41.9% against the limit 20% -> over by 21.9 points; S today 0.00, alternative S 0.562 (crosses 0.50)
   S07 Calamansi grid 5941 (mark X): slope 28.3% against the limit 25% -> over by 3.3 points; S today 0.00, alternative S 0.747 (crosses 0.50)
   S08 Narra grid 4847 (mark M): slope 31.6% against the limit 30% -> over by 1.6 points; S today 0.00, alternative S 0.785 (crosses 0.50)
   S16 Yakal grid 5281 (mark M): slope 56.5% against the limit 45% -> over by 11.5 points; S today 0.00, alternative S 0.684 (crosses 0.50)
   S22 Guava grid 5514 (mark S): slope 25.5% against the limit 25% -> over by 0.5 points; S today 0.00, alternative S 0.990 (crosses 0.50)
   S29 Lemon grid 4603 (mark M): slope 22.1% against the limit 20% -> over by 2.1 points; S today 0.00, alternative S 0.759 (crosses 0.50)
   S30 Talisay grid 6424 (mark S): slope 45.3% against the limit 30% -> over by 15.3 points; S today 0.00, alternative S 0.562 (crosses 0.50)
   S31 Kamias grid 4954 (mark M): slope 20.2% against the limit 20% -> over by 0.2 points; S today 0.00, alternative S 0.806 (crosses 0.50)
   S40 Narra grid 5045 (mark S): slope 32.3% against the limit 30% -> over by 2.3 points; S today 0.00, alternative S 0.774 (crosses 0.50)
Whole grid today (8010 scored squares, 360450 pairs): 249389 pairs have S >= 0.50; the alternative slope rule would ADD 105221 (to 354610).
On the grid before round 15a (7530 squares, the Cemetery zone still scored): 228919 pairs with S >= 0.50 (the 228,919 of before); the alternative rule would add 104209.
ROBUSTA elevation: the data gives 300-800 m; the three Robusta pairs the agriculturist marked Suitable lie at S04 16 m (model S 0.00, gate elevation), S17 199 m (model S 0.00, gate elevation), S20 189 m (model S 0.00, gate elevation).
```
