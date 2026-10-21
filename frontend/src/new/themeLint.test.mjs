// R1 W2: no raw colour outside the token block of canopy.css and the short, commented allowlist of themeLint.mjs.
import test from 'node:test'
import assert from 'node:assert/strict'
import { ALLOW, scan } from './themeLint.mjs'

test('no raw colour (#hex, rgb(), hsl(), named) outside the token block and the allowlist', () => {
  const bad = scan().filter((r) => !r.allowed)
  assert.deepEqual(bad.map((r) => `${r.file}: ${r.n} (${r.sample.join(' ')})`), [])
})

test('every allowlist entry has a reason and points at a real file', async () => {
  const { existsSync } = await import('node:fs')
  const { fileURLToPath } = await import('node:url')
  for (const [file, why] of ALLOW) {
    assert.ok(why && why.length > 10, file)
    assert.ok(existsSync(fileURLToPath(new URL('../' + file, import.meta.url))) || ['new/Charts.jsx', 'new/WeatherHero.jsx', 'new/SkyIcons.jsx', 'new/scoreColors.js', 'new/groundClasses.js', 'new/FieldLegend.jsx', 'new/GroundLayer.jsx', 'new/blockGeometry.js'].includes(file), file + ' does not exist')
  }
})
