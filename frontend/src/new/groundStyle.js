// The ground-cover layer (satellite land cover 2021): six groups, each with a colour, a PATTERN and an icon, so that no class is told apart by colour alone.
// Used by the map (gridLayer.js draws the pattern tiles) and by the legend (GroundLegend.jsx draws the same patterns in SVG).
export const GROUND_GROUPS = ['tree', 'shrub_grass', 'crop', 'built', 'bare', 'water', 'other']

export const GROUND_STYLE = {
  tree: { label: 'Tree cover', color: '#2d6a4f', ink: 'rgba(255,255,255,0.55)', pattern: 'dots', icon: 'tree' },
  shrub_grass: { label: 'Shrub or grass', color: '#a3b13a', ink: 'rgba(40,50,0,0.55)', pattern: 'diag', icon: 'sprout' },
  crop: { label: 'Cropland', color: '#d9a21b', ink: 'rgba(70,40,0,0.55)', pattern: 'hlines', icon: 'wheat' },
  built: { label: 'Built-up', color: '#8c6a5a', ink: 'rgba(255,255,255,0.6)', pattern: 'cross', icon: 'building' },
  bare: { label: 'Bare or sparse', color: '#dccfae', ink: 'rgba(90,70,30,0.6)', pattern: 'stipple', icon: 'mountain' },
  water: { label: 'Water or wetland', color: '#2a7fb8', ink: 'rgba(255,255,255,0.6)', pattern: 'waves', icon: 'drop' },
  other: { label: 'Other', color: '#8a8f98', ink: 'rgba(255,255,255,0.5)', pattern: 'none', icon: 'dash' },
}
export const GROUND_MISSING = '#4b5563'
export const GROUND_FLAG_BITS = { ground_bare: 1, ground_built_up: 2, ground_water: 4 }

// the pattern strokes on an 8 x 8 tile (a list of drawing commands, shared by the canvas and the SVG legend)
export const PATTERN_SHAPES = {
  dots: [['c', 2, 2, 1.1], ['c', 6, 6, 1.1]],
  diag: [['l', 0, 8, 8, 0], ['l', -2, 2, 2, -2], ['l', 6, 10, 10, 6]],
  hlines: [['l', 0, 2, 8, 2], ['l', 0, 6, 8, 6]],
  cross: [['l', 0, 4, 8, 4], ['l', 4, 0, 4, 8]],
  stipple: [['c', 1.5, 1.5, 0.8], ['c', 5.5, 3, 0.8], ['c', 3, 6, 0.8], ['c', 7, 7, 0.8]],
  waves: [['l', 0, 3, 2, 1], ['l', 2, 1, 4, 3], ['l', 4, 3, 6, 1], ['l', 6, 1, 8, 3], ['l', 0, 7, 2, 5], ['l', 2, 5, 4, 7], ['l', 4, 7, 6, 5], ['l', 6, 5, 8, 7]],
  none: [],
}

export function patternTile(group, dpr = 1) {
  const st = GROUND_STYLE[group]
  const c = document.createElement('canvas')
  c.width = c.height = Math.round(8 * dpr)
  const g = c.getContext('2d')
  g.scale(dpr, dpr)
  g.fillStyle = st.color
  g.fillRect(0, 0, 8, 8)
  g.strokeStyle = st.ink
  g.fillStyle = st.ink
  g.lineWidth = 1
  for (const [k, ...a] of PATTERN_SHAPES[st.pattern]) {
    if (k === 'c') {
      g.beginPath()
      g.arc(a[0], a[1], a[2], 0, Math.PI * 2)
      g.fill()
    } else {
      g.beginPath()
      g.moveTo(a[0], a[1])
      g.lineTo(a[2], a[3])
      g.stroke()
    }
  }
  return c
}
