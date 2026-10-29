# Program flowchart (panel §6, revision defense 3 Nov 2026)

Source: `docs/defense/flowchart.mmd` (Mermaid). Rendered: `docs/defense/flowchart.png` (for slides), `docs/defense/flowchart.svg` (vector, for the printed paper).
To re-render after an edit: `mmdc -i docs/defense/flowchart.mmd -o docs/defense/flowchart.png -b white -w 1800` (also `.svg` the same way, without `-w`).

## What the panel asked for, and how this diagram meets each point

The panel's four requirements (from the reconciliation doc, §6 "Flowchart requirements"):

1. **Exactly one Start and one End symbol.** One green stadium "Start" at the top, one green stadium "End" at the bottom. Nothing else in the diagram is a terminator.
2. **The algorithm step shown as a predefined process, looping back into the main program after it executes.** The blue box "Run the suitability and matching algorithm" is drawn as a *subroutine* shape (the double-bordered rectangle — the standard ANSI flowchart symbol for "predefined process": a self-contained procedure defined elsewhere, not expanded inline). Its one outgoing arrow is labelled "loops back into the main program" and returns control to the next step of the main flow (showing the results), exactly as the panel described it ("nag-loop lang siya").
3. **Only one flowchart for the whole program, not fragmented per module.** This single diagram covers the whole user-facing program loop — input, the algorithm, showing results, the optional plan/field-kit/report step, and the "run another query" loop — not a separate diagram per pipeline stage or per dashboard screen. The algorithm's own internal stages (expert-rule MCA, the Random Forest, the Hungarian/spatial-diversity matching) are named inside the one predefined-process box rather than drawn as their own boxes, which is exactly what "predefined process" is for: it says the procedure exists and names it, without re-fragmenting the diagram to show its internals.
4. **Simplify, and consider walking through it in reverse.** The diagram is 10 shapes total (2 terminators, 1 predefined process, 4 processes, 3 decisions) — deliberately flat, no nested sub-flows. The panel's "present it in reverse" note was about delivery order when presenting, not the diagram's structure: at the defense, it can be walked backward from End (what did the user get and when do they stop) to Start (what did they begin with), which works cleanly here because every path is a simple top-to-bottom loop with no stray branches.

## What the flow actually shows

1. **Start.**
2. Show the San Mateo map and the search bar (barangay / species / point).
3. The user picks a goal (species-first or area-first), a purpose, a planting window, and the species or area.
4. **Decision:** is the input complete and valid? If not, a plain-words message explains what's missing and the user is sent back to the picking step (this is the dashboard's own validation, e.g. bad coordinates, an end date before a start date).
5. If valid, control passes into the **predefined process**: the suitability-and-matching algorithm (expert-rule multi-criteria evaluation produces the rule score S; the Random Forest regressor reproduces and generalises it as `s_prob`; the weighted bipartite Hungarian matching, with the round 25 spatial-diversity penalty, assigns species to sites). This is the one algorithm box the panel wanted to see as a single, named, loop-back unit.
6. The algorithm's result loops back into the main program, which shows the ranked species / suitability map / suggested mix, each with its "why this score" breakdown (answering panel point §3 at the same time).
7. **Decision:** does the user want to turn this into a saved plan, a field kit, or a survival report? If yes, the plan (with its field kit and survival-monitoring schedule) is generated and saved.
8. **Decision:** does the user want to run another query? If yes, control returns to the map/search step (step 2). If no, the program reaches **End**.

## Known limits of this diagram (say so if asked)

- It shows the **program's user-facing control flow**, not the full software architecture (it does not show the FastAPI/React split, the database writes, or the separate offline score-rebuild pipeline described in `scripts/rebuild_scores.py` — that pipeline runs independently of this loop, ahead of time, and is documented separately in `CLAUDE.md`'s round 19 section).
- The "predefined process" box intentionally does not expand the Hungarian/spatial-diversity re-solve loop (round 25's `assign_spatial`, which internally re-solves up to 3 times) — that is itself a predefined process's own internal detail, consistent with the point of using the symbol at all.
- Not yet pasted into the actual thesis document or slide deck — that step is still manual (PNG/SVG are ready to drop in).
