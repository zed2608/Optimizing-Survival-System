# Interview findings and what the system does with them

Everything on this page comes from the signed forms of 7 Oct 2026 (MPDC) and the MAO interview transcript of Oct 2026.
It is **provisional** until the licensed agriculturist and the LGU sign off. The dashboard shows a small "Provisional" label wherever one of these items is used.

People: **MENRO / MPDC** = Elaine R. De Jesus. **MAO** = Alexis P. Santos, OIC-MAO.

| Who | Date | What was said or ticked | What the system now does | Status |
|---|---|---|---|---|
| MPDC (Elaine R. De Jesus) | 7 Oct 2026 (form) | Zoning form: which zones can be planted, which need permission, which may be converted | `ZONE_RULES` and `ZONE_CONDITIONS` in `pipeline/rebuild_site_grid.py`; 6,731 confirmed, 1,279 unconfirmed (outside the zoning map), 78 excluded squares; the point panel shows the zone condition with a "Needs permission" badge; optional Zoning layer on the map | applied |
| MPDC | 7 Oct 2026 (form) | Cemetery, Quarry and Sanitary Landfill zones are not planting zones | Squares stay grey and are never scored | applied |
| MAO (Alexis P. Santos) | Oct 2026 (transcript) | Food-bearing trees on landfill or mining land can carry heavy metals | Warning in "Good to know" and in the kit; nobody is left out; testing advised before eating or selling | applied |
| MAO | Oct 2026 (transcript) | Habagat (heavy rain, flooding) in Jul-Sep hurts seedlings in Maly, Dulong Bayan I, Dulong Bayan II and Santa Ana | Ranking score W is multiplied by 0.8 for those squares when the planting window touches Jul-Sep. S and the S >= 0.50 rule do not change. The multiplier is shown in the score detail | applied |
| MAO | Oct 2026 (transcript) | Kape is in the nursery list, variety unknown | Robusta is NOT marked "in nursery"; note "Kape is in the nursery list, variety unknown" | applied |
| MAO | Oct 2026 (transcript) | Nursery list of 14 species (quantities not given) | `nursery_stock.csv`, "Available in LGU nursery" filter and badge; "Stock quantities unknown" | applied |
| MAO | Oct 2026 (transcript) | Short advice per species (5 notes) | Species card section "From the agriculturist (provisional)", source "MAO interview, transcript, Oct 2026" | applied |
| MAO | Oct 2026 (transcript) | Species by purpose (fruit, timber, ornamental, vegetable, and so on) | Eight purpose tags and a Purpose filter (rule based, provisional) | applied |
| MAO | Oct 2026 (transcript) | Which trees grow well together | Partner chips: "named in the sources" and, in a different style, "Named in sources, check conditions" | applied |
| MAO | 7 Oct 2026 (sample sheet) | Marked printed sample pairs (verdicts) | `data/validation/agri_sample_marks_20261007.csv`; results in `docs/SAMPLE_VALIDATION_RESULT.md` | applied; printed-sheet comparison waits for `data/validation/sample_printed_verdicts.csv` |
| MPDC | 7 Oct 2026 (form) | Waterways form (21 creeks, 50 m wetness rule) | **Signed blank.** Nothing is used. The creeks and the 50 m rule are NOT validated | deferred |

## Deferred list (not built; no data or rule was invented)

- Crop calendar view.
- El Nino, La Nina and typhoon hazard notes (source to be MDRRMO with PAG-ASA).
- A farmer questions tab.
- A propagation (grafted) field in the species data.
- Intercropping distance rules.
- Aquatic crops.
- Who may record field checks: MENRO staff and named volunteers (there is still no login).
- A nursery stock tracker (quantities are unknown today).
- Waterways: the 21 creeks and the 50 m wetness rule stay unvalidated because the form was signed blank.

## Plain statement about scores and months

Because of the Habagat rule, the **ranking score W of squares in Maly, Dulong Bayan I, Dulong Bayan II and Santa Ana now depends on the planting window**: a window that touches July, August or September lowers W by 20%. Site suitability S and eligibility do not depend on dates. For other barangays or other months nothing changes.
