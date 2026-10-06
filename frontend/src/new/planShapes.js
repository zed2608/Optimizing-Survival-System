// One distinct SHAPE (and a secondary colour) per species of a plan, so that species are never told apart by colour alone.
// Shapes are SVG path strings drawn around (0, 0) with radius about 1: the canvas layer fills them with Path2D, the legend draws the same paths in SVG.
const poly = (pts) => `M${pts.map(([x, y]) => `${x.toFixed(3)} ${y.toFixed(3)}`).join('L')}Z`
const regular = (n, r, rot = -Math.PI / 2) => Array.from({ length: n }, (_, k) => [r * Math.cos(rot + (2 * Math.PI * k) / n), r * Math.sin(rot + (2 * Math.PI * k) / n)])
const star = Array.from({ length: 10 }, (_, k) => {
  const r = k % 2 === 0 ? 1.25 : 0.52
  const a = -Math.PI / 2 + (Math.PI * k) / 5
  return [r * Math.cos(a), r * Math.sin(a)]
})
const plus = [[-0.32, -1], [0.32, -1], [0.32, -0.32], [1, -0.32], [1, 0.32], [0.32, 0.32], [0.32, 1], [-0.32, 1], [-0.32, 0.32], [-1, 0.32], [-1, -0.32], [-0.32, -0.32]]
const cross = plus.map(([x, y]) => [(x - y) * Math.SQRT1_2 * 1.1, (x + y) * Math.SQRT1_2 * 1.1])

export const SHAPE_NAMES = ['circle', 'square', 'triangle up', 'triangle down', 'diamond', 'pentagon', 'hexagon', 'star', 'plus', 'cross']
const PATHS = [
  'M1 0A1 1 0 1 1 -1 0A1 1 0 1 1 1 0Z',
  poly([[-0.85, -0.85], [0.85, -0.85], [0.85, 0.85], [-0.85, 0.85]]),
  poly([[0, -1.1], [1.05, 0.85], [-1.05, 0.85]]),
  poly([[0, 1.1], [1.05, -0.85], [-1.05, -0.85]]),
  poly([[0, -1.15], [1.15, 0], [0, 1.15], [-1.15, 0]]),
  poly(regular(5, 1.1)),
  poly(regular(6, 1.05, 0)),
  poly(star),
  poly(plus),
  poly(cross),
]
export const PLAN_COLORS = ['#e69f00', '#56b4e9', '#00c389', '#f0e442', '#3b82f6', '#ff6b35', '#e879c6', '#ffffff', '#a3e635', '#c084fc']

export const shapePath = (kind) => PATHS[kind % PATHS.length]
export const shapeColor = (kind) => PLAN_COLORS[kind % PLAN_COLORS.length]
