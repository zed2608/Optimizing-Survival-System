# The 30 hardest panel questions, with honest short answers

Every answer cites repository evidence (files, functions, numbers in `NUMBERS.md`). Where the repository does not know, the answer says UNKNOWN. Figures are of 10 Oct 2026.

## Algorithms

**1. Where is the Random Forest in your system?**
It makes the site match S the app shows. `pipeline/train_rf.py` trains a regressor on the rule score S with 20 raw features, out of fold on 1 km spatial blocks, and writes `s_prob` into the saved scores; `matching.S_SOURCE = "rf"` makes every ranking, map colour, area table and plan use it (hard limits first: where the rules say 0 the forest says 0). "Why this score?" shows "Suitability from the Random Forest: 0.83. Rules check: passed." If `s_prob` is missing the app falls back to the rules and `/health` warns.

**2. Why not just use the rules?**
We could: `S_SOURCE = "rules"` does exactly that and gives almost the same answer (257,869 against 257,929 eligible pairs; 168 pairs, 0.047%, differ; Spearman 0.994). The forest smooths the sharp edges of the thresholds a little and is the "machine learning" layer of the thesis, but it adds no information. We say so everywhere (`docs/RF_SOURCE.md`, README, Help).

**3. Why does the Random Forest equal the Decision Tree?**
Because the labels are threshold rules and a tree represents thresholds exactly. Clean labels: 0.9976 against 0.9979 (random folds), 0.9972 against 0.9971 (spatial); regressor R-squared 0.9998 against 0.9997 (`model_comparison.csv`, `rf_vs_dt_regression_oof.csv`). Only with 5% deliberately flipped labels is the forest ahead (0.946 against 0.936).

**4. Why Hungarian, if greedy gives the same result?**
It is exact and is the right tool if squares become scarce; in our benchmark it gives the same total W as greedy in all 6 cases (gap 0.000000, `matching_benchmark.csv`). We do not claim it beat greedy. What the benchmark does show: both beat random placement by 5.6 to 9.0% of total W, and blind random placement breaks the rules (45, 32, 22 per 300 trees).

**5. How is S computed, exactly?**
`pipeline/score_sites.py`: hard gates (zone, elevation range, slope limit) then the mean of four factors with equal weight 0.25 (elevation, slope, soil, wetness); graded slope rule above the limit; eligible when S >= 0.50. See `ALGORITHMS.md` section 1. All weights are provisional.

**6. What does the graded slope rule change, and who approved it?**
A square up to 25% steeper than a tree's limit now passes with a lowered S and a caution (8,480 more eligible pairs, 72 on squares steeper than 57.7%: Molave 59, Clumping Bamboo 13). It is a team decision awaiting the adviser (`docs/SLOPE_RULE.md`); `SLOPE_MODE = "hard"` reproduces the old 249,389 pairs exactly.

**7. How are the species chosen for a plan?**
`palettes.build_palette`: 6 to 10 species by W, at most 20% per species and 30% per genus (no source for the caps), both sexes for dioecious species, common planting months. Or the user types exact counts per species. A single-species plan gets the warning "higher pest and disease risk".

## Validation and circularity

**8. What did the agriculturist validate?**
One agriculturist marked 40 sample pairs on 7 Oct 2026 (7 of 8 pages signed): 25 Suitable, 11 Marginal, 4 Cannot judge, **no Not suitable**. Agreement with the system 69.4% / 66.7% (printed verdicts), 75.0% / 66.7% (today's rules and the forest), kappa 0.00 and 0.21. He did **not** validate the weights, the soil map, the waterways, or the survival of any tree (`docs/SAMPLE_VALIDATION_RESULT.md`).

**8b. Is that enough to say the model is valid?**
No. One reviewer, 36 judged pairs, no negatives: it cannot show that the model rejects bad pairs, and one or two pairs move the percentage. It is a first look, stated as such.

**9. Isn't your machine learning circular?**
Yes, and we say so: the target is the rule score from the same raw inputs, so a model can only learn the rules back (R-squared 0.9998). Its accuracy proves learnability, not survival. There is no survival data to test against (`README.md` Known limits).

**10. How would you know the model is right in the field?**
We would not today. The saved field checks (planted, not plantable, needs recheck, with counts) and the progress/top-up cards are built so that results can be collected; nothing uses them to calibrate scores yet. Survival monitoring is future work.

**11. Why should we trust the numbers?**
Every value shown carries its source link and rank (`species_sources`); missing values stay "Data Unavailable"; the scores rebuild bit for bit (round 20 Part A: same s_prob and model bytes after a rebuild from scratch, 278 s); the data release is frozen (hash 34964a09fe44). That shows traceability and reproducibility, not correctness.

**12. Did you test the model on a different place or time?**
No. One municipality, one release. Spatial folds (1 km blocks) test within San Mateo; unseen-species folds give about 0.97 with a spread of 0.02. Transfer to another municipality is UNKNOWN.

## Data

**13. What happens if a species is not in your table?**
It cannot be scored: the API answers 404 "species_id ... not found (valid ids: 1-45)" and the app only lists the 45 species. Adding one means adding a row with cited sources to a new release of the raw species file (a new tag), re-running `ingest_species.py`, `scripts/rebuild_scores.py` (about 5 minutes), `score_purposes.py`, `partners.py` and `species_extras.py`, and the agriculturist reviewing it. A species with a missing trait is still scored, but that term is not evaluated or scores a neutral 0.5 and the confidence drops; nothing is guessed.

**14. How good is the soil layer?**
Provisional. We digitized the LGU soil map from a scan (13 m per pixel); the map outline differs from our barangay outline by about 164 m. 3,393 of 8,088 squares (42.0%) have no soil, and for them the soil term is simply not evaluated. The agriculturist has not verified the texture mapping.

**15. Why are 1,279 squares outside your zoning map included?**
The CLUP shows that land as Forest Reserve (Watershed), co-managed with DENR; planting there may be the point of a watershed project. They are scored but flagged ("coordinate with MENRO and DENR") and the user can switch them off. 78 squares (cemetery, quarry) are never scored.

**16. What about the waterways form that was signed blank?**
Nothing from that form is used, and the waterways map has not been validated by MENRO. Creek and river distance is nevertheless used as a soft wetness factor in S (weight 0.25, 50 m from the creek and river polygons; only trees that do not fully tolerate wet ground (Low or Medium tolerance) are lowered; it lowers S for 2,960 of 360,450 pairs). It is a provisional rule of ours, not a validated one. (The Help text said it was "not used" until round 21; the round 20 audit found and fixed that.)

**17. How accurate is the satellite ground cover?**
ESA WorldCover 2021 states 76.7% overall accuracy worldwide; it is not measured for San Mateo. It only adds flags (bare, built-up, water) and never changes a score. The project team reports that MENRO checked the ground cover on only 10 squares (the repository holds no record of which squares or what they found: UNKNOWN), so we have no local accuracy figure.

**17b. Your plan put blocks on land that looks built up. How can that happen?**
Because the site scores read elevation, slope, soil, distance to water and zoning, and the only inputs that could show buildings are the zoning map (a legal zone, not what stands there) and the ESA land cover, which is information only and changes no score. In the Guinayang demo run several blocks lay on what looks like housing and roads. The mitigation is the field check before planting: the kit tells the team to check every square, move a block when a house, road or creek is in the way, never plant on paved or built land, and mark a square "Not plantable" with a reason, which drops it from rankings and plans (and "Plan top-up" replaces its trees). The system proposes; the field team decides.

**18. Planting months are May to September for every species; is that real?**
It is what the sources give (36 species list May, 41 July). It is unverified and probably too uniform; in October to April the app finds no species in season and says so ("Jump to the next planting season").

**19. Which data is unverified?**
34 Batikuling cells cite a PDF we do not have; 30 cells cite sources outside the supplied list; 20 are non-standard; 6 species have no Type I climate preference. All are listed in `data/processed/dataset_release.txt` for the agriculturist.

## Ethics, people and deployment

**20. Who is responsible if a plan fails?**
The system is a decision aid, not a replacement for the agriculturist, MENRO or a DENR permit (the app says so in Help and Known limits). Every plan carries a check code, the release hash and "provisional" labels; the final decision stays with the people.

**21. Are field checks trustworthy? Anyone can type a name.**
No login exists yet (observer is a typed name). Events are append-only (database triggers refuse update and delete), a "not plantable" mark needs a reason, disagreeing observers mark the point DISPUTED. It is an audit trail, not authentication.

**22. Is there personal data?**
Only observer names typed into field checks, GPS positions the observer chooses to save, and the plan campaign names. No accounts, no tracking. The field database is local and git-ignored; backing it up is the user's job.

**23. Could the system harm a community or ecosystem?**
Risks we address: monocultures (caps, warnings), planting where permission is needed (zone conditions, Forest Reserve flags), contaminated land (rehabilitation food warning), flooding in Habagat months (W multiplied by 0.8, advice). Risks we do not address: invasive or unsuitable species outside the 45, land tenure and consent, long-term maintenance. UNKNOWN: how a real planting season would go.

**24. Can it be deployed by the LGU as it is?**
As a research prototype on one computer: yes (README, `scripts/start_dev.ps1`). Not as a production service: no login, no server hardening, no backup automation, scores and the model are not in git (a fresh clone must run `scripts/rebuild_scores.py`), the field kit was never tested on a phone, GPS or paper.

**25. What does it need to run, and how fast is it?**
Python 3.14, Node 22; the API starts in about 4 seconds and uses about 190 MB at start; typical endpoints answer in under 0.2 s warm (the 300-tree plan: 0.3 to 0.7 s); the dashboard plan click-to-result: 0.45 to 0.52 s. The weather and map tiles need the internet; everything else works offline.

## Limitations the panel will find anyway

**26. Does the form's block estimate match the plan?**
Yes, since round 21. The round 20 audit found that the form said "About 5 blocks" (median block size, 64 trees) while real plans had 12 to 15, because species differ a lot in trees per block (Weeping Fig 9 trees per block at 20 m spacing, Chesa/Tiesa 121). `/plan-event/preview` now runs the same plan rule as Create plan and reports its blocks (`tests/test_round21.py` compares estimate and real plan for three purposes and four tree counts). If suitable squares run short the plan places fewer trees and the capacity message says so.

**27. What if the Random Forest file is missing at the demo?**
The app falls back to the rules automatically and `/health` shows a warning; ranking and plans keep working with almost the same results. Since round 21 the dashboard also shows a notice at the top ("Random Forest scores are not loaded. The app is using the rule scores. Run scripts/rebuild_scores.py.") and Help says the rules are being used (round 20 had found that this fallback was silent on screen).

**28. Why are the weights equal (0.25) and who chose the purpose weights?**
The team; no source. They are labelled provisional, and `purpose_sensitivity.csv` (76 scenarios) shows how species ranks move. The agriculturist has not signed them off.

**29. What is the single biggest weakness?**
No independent evidence of survival. Every score is expert rules from species descriptions, copied by a model. The honest claim of the thesis: a transparent, reproducible decision-support pipeline with sources, flags and a field-feedback loop, not a validated prediction of survival.

**30. What would you do next?**
Get the agriculturist to sign (or change) the species data, weights, soil mapping and slope rule; collect field survival with the existing field-check flow and test S against it; verify the waterways with the MPDC; add a login; test the field kit on a phone and on paper.
