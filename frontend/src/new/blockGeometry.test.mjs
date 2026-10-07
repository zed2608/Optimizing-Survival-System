import test from 'node:test'
import assert from 'node:assert/strict'
import { blockGeometry } from './blockGeometry.js'

const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} vs ${b}`)

test('12.5 m spacing, 6 x 6: rectangle 12.5 to 87.5 m, trees at 18.75 ... 81.25', () => {
  const g = blockGeometry(12.5, 6, 6, 36)
  near(g.margin, 12.5); near(g.rectSide, 75)
  assert.deepEqual(g.trees.slice(0, 6).map((t) => t.x), [18.75, 31.25, 43.75, 56.25, 68.75, 81.25])
  near(g.firstTree.x, 18.75); near(g.firstTree.y, 18.75); near(g.lastTree.x, 81.25); near(g.lastTree.y, 81.25)
})

test('a partly filled block plants trees 1..N row by row; the rest are empty', () => {
  const g = blockGeometry(12.5, 6, 6, 14)
  assert.equal(g.trees.filter((t) => t.planted).length, 14)
  assert.ok(g.trees.slice(0, 14).every((t) => t.planted) && g.trees.slice(14).every((t) => !t.planted))
  near(g.lastTree.x, 31.25); near(g.lastTree.y, 43.75) // tree 14 = row 3, second tree
})

test('margins are symmetric and every tree lies inside its rectangle', () => {
  for (const [sp, n] of [[2.5, 30], [5, 15], [7.5, 10], [10, 7], [12.5, 6], [25, 3], [50, 1]]) {
    const g = blockGeometry(sp, n, n, n * n)
    near(g.margin, 100 - g.margin - g.rectSide)
    for (const t of g.trees) assert.ok(t.x > g.margin && t.x < g.margin + g.rectSide && t.y > g.margin && t.y < g.margin + g.rectSide)
    near(g.firstTree.x, g.margin + sp / 2)
  }
})
