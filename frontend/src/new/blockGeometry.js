// The planted rectangle of one block, the same rule as pipeline/palettes.py block_geometry (tests compare the two).
// Metres from the south-west corner of the 100 m grid square. The rectangle is trees_per_row x spacing wide and rows x spacing high, CENTRED in the square.
// Tree k (1-based) runs row by row from the south-west, east first, then one spacing north, at the CENTRE of its cell. A partly filled block plants trees 1..N.
export const SQUARE_M = 100

export function blockGeometry(spacing, treesPerRow, rows, treesPlanned, side = SQUARE_M) {
  const cap = treesPerRow * rows
  const n = treesPlanned == null ? cap : Math.max(0, Math.min(treesPlanned, cap))
  const w = treesPerRow * spacing
  const h = rows * spacing
  const mx = (side - w) / 2
  const my = (side - h) / 2
  const trees = []
  for (let k = 0; k < cap; k++) {
    const i = k % treesPerRow
    const j = Math.floor(k / treesPerRow)
    trees.push({ k: k + 1, x: mx + spacing * (i + 0.5), y: my + spacing * (j + 0.5), planted: k < n })
  }
  return { side, rectW: w, rectH: h, rectSide: w, margin: mx, marginY: my, capacity: cap, planted: n, trees, firstTree: trees[0], lastTree: n ? trees[n - 1] : null }
}

export function fmtM(v) {
  const r = Math.round(v * 100) / 100
  return Number.isInteger(r) ? String(r) : String(r)
}
