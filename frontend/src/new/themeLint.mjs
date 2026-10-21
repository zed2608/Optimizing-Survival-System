// Theme lint (R1 W2): finds raw colours (#hex, rgb()/rgba(), hsl()/hsla(), named colours in colour properties) in the dashboard sources.
// Raw colours live ONLY in the token block of canopy.css (and in the short allowlist below, each entry with its reason). Everything else uses var(--c-...) tokens.
//   node frontend/src/new/themeLint.mjs            prints the count per file (the inventory)
// themeLint.test.mjs runs it and fails when anything outside the allowlist is left.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const ROOTS = ['new', 'v2']
const RAW = /#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)|\bhsla?\([^)]*\)/g
const NAMED = /(?:^|[\s;{(])(?:color|background(?:-color)?|border(?:-[a-z]+)*-color|border|fill|stroke|outline(?:-color)?|text-shadow|box-shadow):\s*['"]?(white|black|red|blue|green|gray|grey|orange|yellow|navy|teal|purple)\b/g

// Files (or file + marker) that may hold raw colours, each with the reason. Map layers and swatches are drawn on a map whose pictures are light/dark in both themes, so their colours are data, not theme.
export const ALLOW = [
  ['new/canopy.css', 'TOKENS block: the one place where colours are defined (light and dark); later blocks of the file may only use tokens'],
  ['new/gridLayer.js', 'canvas drawing of the map squares, planned shapes and field marks: score colours and the ONE violet of field checks are data colours'],
  ['new/planShapes.js', 'species shape colours on the map'],
  ['new/zoneColors.json', 'LGU style file colours of the zoning overlay (data)'],
  ['new/zoneColorsTable.js', 'mirror of zoneColors.json'],
  ['new/fieldStatus.json', 'field-status colours (data, shared with the PDF)'],
  ['new/fieldStatusTable.js', 'mirror of fieldStatus.json'],
  ['new/scoreColors.js', 'score colours (Good / Moderate / Poor) shared by map and legend swatches'],
  ['new/Charts.jsx', 'chart series colours (data)'],
  ['new/charts/Charts.jsx', 'chart series colours (data)'],
  ['new/WeatherHero.jsx', 'sun / cloud / rain drawing of the weather hero (illustration)'],
  ['new/SkyIcons.jsx', 'weather illustration'],
  ['new/BoundaryLayers.jsx', 'barangay outline colours on the map'],
  ['new/ZoningLayer.jsx', 'zoning overlay on the map'],
  ['new/MapNew.jsx', 'map layer styles and the blue "my location" marker'],
  ['new/GroundLayer.jsx', 'satellite ground-cover class colours (data)'],
  ['new/groundClasses.js', 'satellite ground-cover class colours (data)'],
  ['new/FieldLegend.jsx', 'legend swatches of the field-check marks (they must equal the map symbols)'],
  ['new/groundStyle.js', 'satellite ground-cover patterns: class colours drawn on the map (data)'],
  ['new/DrawLayer.jsx', 'the area being drawn on the map: amber vertices and line are drawn over map imagery'],
  ['v2/components/MapView.jsx', 'the first v2 page (#/v2) map layer colours'],
  ['new/charts/palette.js', 'colour-blind-safe chart palette (data colours, Okabe-Ito)'],
  ['new/GroundLegend.jsx', 'swatches of the ground-cover legend (must equal the map)'],
  ['new/AreaSquaresLayer.jsx', 'counted / partly touched squares on the map: cyan fill and dashed grey are reserved meanings'],
  ['new/HighlightLayer.jsx', 'cyan highlight of the chosen area on the map (reserved)'],
  ['new/FieldChip.jsx', 'a chip with its OWN white background and its own status text colour (an explicit pair tuned for AA on white in both themes)'],
]
const CANOPY_TOKENS_END = '/* TOKENS:END */'

function walk(dir, out = []) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f)
    if (statSync(p).isDirectory()) {
      if (f !== 'node_modules') walk(p, out)
    } else if (/\.(css|jsx?|mjs|json)$/.test(f) && !/\.test\./.test(f) && f !== 'themeLint.mjs') out.push(p)
  }
  return out
}

export function scan() {
  const rows = []
  for (const r of ROOTS) {
    for (const p of walk(join(SRC, r))) {
      const rel = relative(SRC, p).replace(/\\/g, '/')
      let s = readFileSync(p, 'utf8')
      if (rel === 'new/canopy.css') {
        const i = s.indexOf(CANOPY_TOKENS_END)
        s = i >= 0 ? s.slice(i + CANOPY_TOKENS_END.length) : s // the token block is allowed; the rest of the file is not
      }
      s = s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '') // comments do not count
      const hits = [...(s.match(RAW) || []), ...(s.match(NAMED) || [])]
      if (hits.length) rows.push({ file: rel, n: hits.length, sample: hits.slice(0, 3), allowed: ALLOW.some(([f]) => f === rel) })
    }
  }
  return rows.sort((a, b) => b.n - a.n)
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const rows = scan()
  let total = 0
  for (const r of rows) {
    total += r.n
    console.log(String(r.n).padStart(5), r.allowed ? 'allowed' : 'RAW    ', r.file)
  }
  console.log('total', total, 'outside the allowlist:', rows.filter((r) => !r.allowed).reduce((a, r) => a + r.n, 0))
}
