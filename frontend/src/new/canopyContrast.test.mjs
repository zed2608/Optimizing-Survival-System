import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// WCAG AA (4.5:1 for text) for the colour pairs the Canopy design system uses, in BOTH themes, read from canopy.css itself.
const css = readFileSync(new URL('./canopy.css', import.meta.url), 'utf8')
const block = (re) => {
  const m = css.match(re)
  assert.ok(m, `block ${re}`)
  return Object.fromEntries([...m[1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\b/g)].map((x) => [x[1], x[2]]))
}
const light = block(/:root\s*\{([\s\S]*?)\n\}/)
const dark = { ...light, ...block(/:root\[data-theme='dark'\]\s*\{([\s\S]*?)\n\}/) }
const rgb = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16))
const lum = (c) => {
  const [r, g, b] = rgb(c).map((v) => {
    const x = v / 255
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
// [foreground token, background token]
const PAIRS = [
  ['c-text', 'c-bg'], ['c-text', 'c-surface'], ['c-text', 'c-surface-2'], ['c-text', 'c-surface-3'],
  ['c-muted', 'c-bg'], ['c-muted', 'c-surface'], ['c-muted', 'c-surface-2'],
  ['c-on-primary', 'c-primary'], ['c-on-primary', 'c-primary-hover'],
  ['c-accent-text', 'c-surface'], ['c-accent-text', 'c-bg'],
  ['c-link', 'c-surface'], ['c-link', 'c-bg'],
  ['c-warn', 'c-warn-bg'], ['c-danger', 'c-danger-bg'], ['c-ok', 'c-ok-bg'], ['c-info', 'c-info-bg'],
]
for (const [name, t] of [['light', light], ['dark', dark]]) {
  test(`AA contrast of the Canopy colour pairs in the ${name} theme`, () => {
    for (const [f, b] of PAIRS) {
      assert.ok(t[f] && t[b], `${f} / ${b} exist`)
      const r = ratio(t[f], t[b])
      assert.ok(r >= 4.5, `${name}: ${f} ${t[f]} on ${b} ${t[b]} is ${r.toFixed(2)}:1, below 4.5`)
    }
  })
}

test('the reserved colours stay distinct from the theme colours', () => {
  const violet = '#8b5cf6'
  const dist = (a, b) => Math.hypot(...rgb(a).map((v, i) => v - rgb(b)[i]))
  for (const t of [light, dark]) for (const k of ['c-primary', 'c-accent', 'c-link', 'c-warn', 'c-danger']) assert.ok(dist(violet, t[k]) > 60, `violet vs ${k}`)
})
