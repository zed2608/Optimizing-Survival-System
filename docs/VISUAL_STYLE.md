# Visual style of `#/new` (round 7b)

The look is calm, dark glass, one accent. Nothing was removed to get there: every piece of information is still reachable, only quieter.
The values below are the ones in `frontend/src/new/new.css` (block "round 7b" at the end, variables on `.nw-root`) and in `Icon.jsx`.

## Principles
1. Tints and spacing instead of outlines. A card is a white (or dark-tint) block on a slightly different background; borders only where they carry meaning (the coloured edge of a ranked species, the dashed ring of unconfirmed land).
2. One accent colour (emerald) for primary actions, the active tab, the open step and the active switch. Status colours (green, orange, red) mean suitability or a field status and always come with a word or an icon.
3. Two font weights only: 400 (text) and 600 (headings, names, buttons, numbers that matter). The browser check lists the weights actually used.
4. One corner radius (8 px; pills 999 px; round badges 50%), one spacing step (8 px and its multiples).
5. Icon plus word wherever the meaning is not obvious. An icon alone is only used inside a button that has a text or an `aria-label`. Icons are `aria-hidden`.
6. At most three chips in a row; the rest are plain lines. No heading is written twice (the panel title is the heading; a duplicate inside is hidden from sight but kept for screen readers).
7. The map is quiet by default ("Simple"); detail is one switch away ("Detailed") and the user's own work is always visible.

## Colours
| Use | Value |
|---|---|
| Page / map background | `#090d16` |
| Glass panels (top bar, sidebar, menus) | `rgba(15, 23, 42, 0.55 – 0.9)` with blur |
| Tint (step, chip on dark) | `rgba(255,255,255,0.05)`; hover / open `0.08` |
| Text on dark | `#f8fafc`; muted `#94a3b8` |
| Cards (result panels, weather, logs) | `#ffffff` on `#eef1f5`; ink `#1b1f23`; muted ink `#5a626b` |
| Accent (primary action, active) | `#10b981`; strong `#059669` |
| Link / focus ring | `#38bdf8` (3 px focus outline) |
| Suitability scale on the map (same as the legend) | good `#2e7d32`, moderate `#e65100`, poor `#c62828`, none `#9e9e9e`; squares drawn at 0.8 opacity |
| Grey squares (not planting zones) | `rgba(148,163,184,0.15)`, one flat tone |
| Boundaries | municipality `#fde68a` (1.8 px) over a dark 4 px line at 0.3; barangays `#f1f5f9`, 1 px, 0.5 opacity, dashed |
| Selected square | `#38bdf8` outline over a dark one |
| Planted trees | one shape per species, fill from `planShapes.js`, thin dark outline `#0f172a` (1.2 px) |

## Spacing, size, type
- Spacing: 8 px grid (4 px only inside compact controls). Cards: 16 px padding, 8 px gap. Panel header: 8 px 16 px. Top bar: 56 px high.
- Corner radius: 8 px.
- Type: system / Plus Jakarta Sans. Sizes: 11 px (labels, notes), 12 px (small text), 13 px (buttons, tabs), 14 px (body, headings of cards), 22 px (verdict heading in the Weather tab). Weights 400 and 600.
- Top-bar title: "Tree Planting Decision Support", subtitle "MENRO · San Mateo, Rizal" (the full name stays in the tooltip of the title).

## Map
- Grid squares: one filled square per 100 m cell, scaled with the zoom, no outline, 1 px gap only when a square is at least 8 px wide.
- Grey squares: faint flat tone, same hover reason and click panel; drawn only in the Detailed view.
- Planted trees: below zoom 14 one bubble per barangay ("Maly 12"), from 14 to 15 one bubble per 500 m cell, from 15 on single shapes; the 3-letter codes appear from zoom 17 in the Detailed view. A dotted ring marks unconfirmed zoning (on bubbles too).
- Barangay labels: 10.5 px with a dark halo; a label that would overlap a larger barangay's label is hidden.
- Simple (default, remembered as `nw_map_detail`): squares, outlines, labels, and the user's own work (the plan and the points marked in this session). Detailed adds every saved field-check symbol, the tree codes and the grey squares.

## Icons (`Icon.jsx`, 24 × 24 grid, stroke 1.5, round ends, `currentColor`; 16 px, 18 px in tabs, 22 px in the verdict)
`map` (Active Studio) · `cloud` (Weather) · `clipboard` (Campaign Logs, Plan step) · `bars` (System Analytics) · `tree` (brand, Purpose step, species) · `target` (Goal step, coordinates) · `calendar` (Planting window step) · `pin` (Area step, places, planned points) · `grid` (barangay in search) · `layers` (Map view) · `legend` (Legend) · `search` · `close` (close, not plantable) · `check` (ok, verified, good) · `ring` (verified plantable) · `triangle` (needs recheck) · `warn` (warnings, disputed) · `flag` (flags) · `dotring` (unconfirmed zoning) · `sun` (dry) · `rain` (heavy rain) · `cloud` (rain) · `wave` (El Nino) · `clock` (upcoming, outside planting window) · `dot` (active) · `half` (partly in season) · `dash` (no dates) · `down` `up` `left` `right` (chevrons) · `undo` (recent searches) · `download` · `info` · `question` (unknown) · `panel` · `sprout` (shrub or grass) · `wheat` (cropland) · `building` (built-up) · `mountain` (bare or sparse ground) · `drop` (water or wetland).
Field-check status always pairs shape with a word: ring = Verified plantable, cross = Not plantable, triangle = Needs recheck.

## What is not restyled
`frontend/src/v2/` (the first v2 page) and the legacy dashboard are untouched, so a few shared v2 components (error boxes, the colour legend) keep their older look inside `#/new`.
