// Text size and colour rules of the fix round (the browser audit scripts/contrast_audit.mjs measures the rendered page; this test keeps the style sheets from sliding back).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const SHEETS = ['new.css', 'canopy.css', '../v2/v2.css'].map((f) => [f, readFileSync(new URL(f, import.meta.url), 'utf8')])

test('no font-size under 12px in any style sheet of the dashboard', () => {
  const bad = []
  for (const [f, css0] of SHEETS) {
    const css = css0.split(String.fromCharCode(10)).filter((l) => !l.includes('fill:')).join(String.fromCharCode(10)) // text inside an SVG is sized in the drawing's own units, not in screen pixels
    for (const m of css.matchAll(/font-size:\s*([\d.]+)(px|rem|em)/g)) {
      const px = m[2] === 'px' ? +m[1] : +m[1] * 16
      if (px < 12) bad.push(`${f}: ${m[0]}`)
    }
  }
  assert.deepEqual(bad, [])
})

test('text colours of the dashboard come from tokens, not light-on-dark literals', () => {
  const bad = []
  for (const [f, css] of SHEETS) {
    for (const m of css.matchAll(/(?:^|[\s;{])color:\s*(#(?:94a3b8|cbd5e1|e2e8f0|f8fafc|334155|6ee7b7|fca5a5|fde68a))\b/gi)) bad.push(`${f}: color ${m[1]}`)
  }
  assert.deepEqual(bad, [])
})

test('the "locked" steps are not dimmed with opacity', () => {
  const canopy = SHEETS.find(([f]) => f === 'canopy.css')[1]
  assert.match(canopy, /\.nw-step\.is-open ~ \.nw-step[^{]*\{ opacity: 1; \}/)
})
