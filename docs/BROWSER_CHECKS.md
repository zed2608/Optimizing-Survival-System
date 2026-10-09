# Browser checks (headless Edge scripts)

These scripts drive the real dashboard in a headless browser. They live in the working folder of the project team (not in the repository) and are run
with the API on and with the API off. Each prints PASS or FAIL per check.

## Current scripts

default page, soil, blocks, ground cover, look (map), zoning and weather, modes, search, season, part 2, round 3, round 4a, plan 1, plan 2, and (round 16)
the tutorial script (`cdp_16.mjs`: every tour step, the Help page, the printed guide).

## OBSOLETE scripts: do not read their failures as problems

- **`cdp_field.mjs`** is OBSOLETE. It was written for the point panel of round 2 (selectors such as the old field-check buttons). The field checks are now covered by
  the round 3 script, the blocks script and `tests/test_field_verify.py`. Its failures mean only that the screen it describes no longer exists.
- **`cdp_routes.mjs`** is OBSOLETE. It expects the OLD dashboard at an empty address. Since round 9 the new dashboard is the default; `cdp_default.mjs`
  covers the routes now. Its "earlier dashboard is shown" failures are expected.
- `cdp_ba.mjs` only takes before/after screenshots; it has no checks (0 passed, 0 failed).
