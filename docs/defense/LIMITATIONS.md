# Limitations: every known limit, with numbers and who validated what

Written 10 Oct 2026 from the code, the saved data and the documents of the repository. "UNKNOWN" means the repository does not say. Numbers are in `NUMBERS.md` with their source file.

## A. Who validated what (the evidence ladder)
| Item | Validated by | Evidence | What it does NOT show |
|---|---|---|---|
| Species data (45 species, 2,347 cited cells) | nobody yet; frozen as release `v1.0-review` (hash 34964a09fe44) for the licensed agriculturist | `data/processed/dataset_release.txt`; not signed off | that any value is right; 190 ingest issues are listed (34 high) |
| Site rule scores S (40 sample pairs) | one agriculturist (MAO), 7 Oct 2026, one afternoon | `data/validation/agri_sample_marks_20261007.csv`; `docs/SAMPLE_VALIDATION_RESULT.md` | see section B |
| Zoning rules | MPDC (signed form, 7 Oct 2026) | `docs/INTERVIEW_FINDINGS.md` | the waterways form was signed BLANK |
| Habagat factor 0.8, rehabilitation warning, nursery list, purpose tags | MAO interview, Oct 2026 (a single interviewee) | `docs/INTERVIEW_FINDINGS.md` | the 0.8 is "his example figure"; nothing measured |
| Purpose weights, caps, thresholds, soil compatibility, block share | nobody (team proposals) | marked provisional in code and screens | any of them; `purpose_sensitivity.csv` only shows how ranks move |
| Soil map | nobody (digitized by us from a scan) | `data/processed/soil_lgu_report.txt` | agreement with the real soil |
| Field results (survival) | nobody; no field survival data exists | none | **everything about survival** |

## B. The model measures the rules, not survival
1. **The labels are the rules.** The Random Forest, Decision Tree, logistic regression and KNN of `compare_models.py` and `train_rf.py` are trained on S produced by `score_sites.py` from the same raw inputs. High accuracy only shows the rules are learnable.
2. **The forest copies the rules:** out-of-fold R-squared 0.9998, MAE 0.00059 (spatial folds); 168 of 360,450 pairs (0.047%) change eligibility; the 20 features are the raw values the rules read. It adds no independent information and is **not a measurement of survival**.
3. **RF equals Decision Tree on clean labels:** accuracy 0.9976 / 0.9979 (random folds), 0.9972 / 0.9971 (spatial); regressor R-squared 0.9998 / 0.9997. The forest is ahead only under 5% flipped labels (0.946 against 0.936). Reason: the labels are thresholds, which a tree represents exactly.
4. **Hungarian equals greedy** in all 6 benchmark cases (gap 0.000000). The optimal solver gives no measured advantage on this problem; random feasible loses 5.6 to 9.0% of total W (urban 190.69 against 201.93 ... watershed 168.00 against 184.55); random blind breaks rules (45, 32, 22 per 300 trees in points mode).
5. **Spatial folds show little leakage** (0.9972) which (our reading, not separately tested) is because the rule is a simple function of elevation and slope that holds everywhere, not because the model understands ecology. Unseen-species folds (0.971 for RF) have a spread of about 0.02: with 45 species no model comparison there is reliable.

## C. Agriculturist sample (the only external check)
- **One reviewer, 40 pairs** (36 judged, 4 "Cannot judge": S07, S12, S14, S19), 7 of 8 pages signed.
- **There are no "Not suitable" marks at all** (25 Suitable, 11 Marginal, 4 X, 0 N). The sample cannot show whether the model rejects bad pairs correctly; agreement is mostly "the model also says suitable".
- Agreement of the printed system verdicts with the marks: 69.4% (Marginal as Suitable; kappa 0.00, no better than chance) or 66.7% (Marginal as Not suitable; kappa 0.21). Graded rules and the forest: 75.0% / 66.7%. 0 of 40 verdicts differ between graded rules and forest; 2 differ from the printed sheet because of the graded slope rule (S22 Guava, S31 Kamias). Differences of one or two pairs are noise at n = 36.
- It does not validate the model. It is a first look at where one expert and the rules disagree.

## D. Data limits
1. **Soil.** The LGU soil map (BSWM, Soil Map of Rizal Province) was digitized by us from a scan (about 13 m per pixel; map outline and our barangay outline differ by about 164 m on shared sides; red roads and red soil colour are confused). **3,393 of 8,088 squares (42.0%) have no soil texture** (the map is blank in the north-east watershed area): for them the soil term is not evaluated, never a mismatch. A mismatch only lowers S (factor 0.25); strict mode was measured in round 9 only on an older grid (about 98,000 of 229,000 pairs removed) and not re-run. Everything is PROVISIONAL.
2. **Wetness / waterways.** The MPDC waterways form (21 creeks, 50 m rule) was **signed blank**. The scoring has its own wetness term (`score_sites.py`: weight 0.25 of S; layer `data/SMR_WATERBODIES_POLY.shp`, classes CREEK and RIVER; within 50 m of water a species scores `tolerance + (1 - tolerance) x distance / 50`, tolerance Low / Medium / High = 0 / 0.5 / 1, so only trees that do not fully tolerate wet ground (Low or Medium) are lowered; it lowers S for 2,960 of 360,450 pairs). Creek and river distance is therefore **used as a soft wetness factor (50 m), and the waterways map has not been validated by MENRO**. (Found in the round 20 audit and corrected in round 21: until then the Help text and the user guide wrongly said the creeks and the 50 m rule "are not used"; they now say the above.)
3. **Ground cover.** ESA WorldCover 10 m 2021: stated global overall accuracy **76.7%**, not measured for San Mateo; bare, built-up and grass are often confused; information flags only (it never changes a score). **Planned blocks can lie on land that looks built up in the satellite picture** (round 20 demo run: several blocks in Guinayang lay on what looks like housing and roads). Reason: the site scores read elevation, slope, soil, distance to water and the zoning status; the only inputs that could show built land are the zoning map (a zone is a legal designation, not what stands on the ground) and the ESA land cover, and the land cover only adds information flags ("bare", "built-up", "water", the "Check first" box); it changes no score, rank or eligibility. The project team reports that the ground cover was checked by MENRO on only 10 squares (no file in the repository records which squares or the result: UNKNOWN), so its accuracy for San Mateo is not known either. **Mitigation: a field check before planting** (the field kit tells the team to check every square on the ground, to move a block when a house, road or creek is in the way, and never to plant on paved or built land; a square found built up is marked "Not plantable" with a reason and drops out of rankings and plans, and "Plan top-up" replaces its trees).
4. **Zoning.** 1,279 squares lie outside every zoning polygon (95% in the eastern upland, median slope about 30%). The CLUP 2021-2031 shows them as Forest Reserve (Watershed), co-managed with DENR: scored, flagged, "coordinate with MENRO and DENR before planting". 78 squares (cemetery, quarry) are never scored. Conditions (private land, DENR permission, may be converted) are shown but do not change scores.
5. **Species data.** 34 Batikuling cells cite a PDF that was not provided; 30 cells cite sources outside the supplied list; 20 citations are non-standard; **6 species have no Type I climate preference**; the Batikuling soil text "Top soil and manure 10:1" cannot be mapped. Planting months are May to September only for all 45 species (36 have May, 38 June, 41 July, 10 August, 1 September): in October to April no species is in season and the app says so.
6. **Grid.** 100 m squares: a square is an area, not a tree spot. Slope comes from finite differences; 22% of squares have only one axis ("partial") and may under-estimate; 5474 (93%) is an example of a square no species can use.
7. **Not scored at all:** soil pH (no real layer), rainfall, temperature, canopy, exposure, existing trees on the ground (a trees table is optional and not supplied).
8. **Weather.** Open-Meteo forecast covers 16 days, needs the internet; El Nino status is set by hand ("none, source not set").

## E. Rules and numbers with no source (all provisional)
- Term weights 0.25 each; elevation / slope margin 10%; wetness distance 50 m; soil mismatch factor 0.25; `SOIL_COMPAT`.
- **Graded slope rule** (margin 25% of the species limit): a team decision awaiting the adviser; 8,480 newly eligible pairs, 72 on squares steeper than 57.7%.
- **Habagat multiplier 0.8** on W in Maly, Dulong Bayan I and II, Santa Ana for July to September windows: from one interviewee's example; scores in those barangays depend on the planting month.
- **Caps of 20% per species and 30% per genus**, palette of 6 to 10 species: no source.
- **Block model:** 60% usable share, spacing = midpoint rounded to 0.5 m, rectangle centred, grid assumed aligned to UTM north (EPSG:32651).
- Purpose weights (6 / 6 / 7 criteria, each summing to 1.00), the 0.50 eligibility cut, partner thresholds (50% overlap, 60% height, 0.4 roots), ground-cover thresholds (50% / 50% / 30%).

## F. System and process limits
- **Saved scores and the model are not in git** (site_scores.csv 115 MB, .db 129 MB, model 50 MB). A fresh clone must run `python scripts/rebuild_scores.py` (278 s here; the result is byte identical). Until then the app runs on the rules with a `/health` warning, and (since round 21) a notice at the top of the dashboard: "Random Forest scores are not loaded. The app is using the rule scores. Run scripts/rebuild_scores.py."; Help then says the rules make the site match.
- Field checks have a typed name, no login (anyone can write any observer name); append-only by design; the field database is git-ignored and must be backed up.
- The field kit (GPX, KML, CSV, PDF) was **not tested on a phone, with a real GPS, or printed on paper**.
- The legacy dashboard `#/legacy` and root scripts (`api.py`, `optimization.py`, `train_model.py`, ...) are kept but not maintained; the legacy backend mixes slope units (degrees only when the value is above 90).
- Single municipality, one release; nothing was tested elsewhere (transferability UNKNOWN).
- Fixed in round 21: the estimate line of the plan form used the median block size ("About 5 blocks" for 300 trees, real 12 to 15) and now reports the blocks of the same plan rule as Create plan. It is exact for the automatic mix; fewer trees fit if suitable squares run short (the capacity message says so).
- Partner rules are starting rules; species with Low waterlogging tolerance cannot partner High ones (Duhat, Clumping Bamboo have none); name matching is word-based.
- Tests pin the data (counts, hashes); a data change fails them on purpose.
