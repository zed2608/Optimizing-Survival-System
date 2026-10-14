// node --test src/new/planterLink.test.mjs : the pure parts of the planter link box and its QR code (the QR is decoded back with jsQR, a test-only package).
import test from 'node:test'
import assert from 'node:assert/strict'
import jsQR from 'jsqr'
import { QUIET, qrMatrix, qrSvg } from './planterQr.js'
import { TEXT, boxState, expiryInfo, expiryLines, fullUrl, isLocalAddress } from './planterLink.js'

const URL1 = 'https://optimizing-survival.onrender.com/field/AbCdEfGhIjKlMnOpQrStUv/'

// draw the path of qrSvg() as pixels (8 px per module, black on white) exactly as an SVG viewer would, and let jsQR read it
function rasterise(svg, scale = 8) {
  const w = svg.size * scale
  const data = new Uint8ClampedArray(w * w * 4).fill(255)
  for (const m of svg.d.matchAll(/M(\d+) (\d+)h1v1h-1z/g)) {
    const x0 = Number(m[1]) * scale, y0 = Number(m[2]) * scale
    for (let y = y0; y < y0 + scale; y += 1) for (let x = x0; x < x0 + scale; x += 1) { const i = (y * w + x) * 4; data[i] = data[i + 1] = data[i + 2] = 0 }
  }
  return { data, width: w, height: w }
}

test('the QR code of a planter link is read back as the same address', () => {
  for (const url of [URL1, 'http://127.0.0.1:8001/field/zzzzzzzzzzzzzzzzzzzzzz/', 'https://a.example/field/' + 'x'.repeat(22) + '/']) {
    const svg = qrSvg(url)
    const img = rasterise(svg)
    const got = jsQR(img.data, img.width, img.height)
    assert.ok(got, 'jsQR could not read the code of ' + url)
    assert.equal(got.data, url)
  }
})

test('the QR data: a square matrix, the quiet zone of 4 modules, one path and no markup', () => {
  const rows = qrMatrix(URL1)
  const n = rows.length
  assert.ok(n >= 21 && n <= 41 && (n - 17) % 4 === 0 && rows.every((r) => r.length === n)) // versions 1 to 6 for a link of this length
  const svg = qrSvg(URL1)
  assert.equal(svg.size, n + 2 * QUIET)
  assert.equal(svg.viewBox, `0 0 ${svg.size} ${svg.size}`)
  assert.match(svg.d, /^(M\d+ \d+h1v1h-1z)+$/)
  assert.ok(![...svg.d.matchAll(/M(\d+) (\d+)h/g)].some((m) => Number(m[1]) < QUIET || Number(m[2]) < QUIET || Number(m[1]) >= n + QUIET || Number(m[2]) >= n + QUIET))
  assert.ok(rows[0][0] && rows[0][n - 1] && rows[n - 1][0]) // the three finder squares
  assert.deepEqual(qrSvg(URL1), qrSvg(URL1)) // the same text, the same picture
  assert.notEqual(qrSvg(URL1).d, qrSvg(URL1 + 'x').d)
})

test('the address a phone must open', () => {
  assert.equal(fullUrl('', 'https://app.onrender.com', '/field/abc/'), 'https://app.onrender.com/field/abc/') // the deployment build: API_BASE is empty
  assert.equal(fullUrl('http://127.0.0.1:8001/', 'http://localhost:5173', '/field/abc/'), 'http://127.0.0.1:8001/field/abc/') // development: the service, not the page
  assert.equal(isLocalAddress('http://127.0.0.1:8001/field/x/'), true)
  assert.equal(isLocalAddress('http://localhost:5173/field/x/'), true)
  assert.equal(isLocalAddress('https://app.onrender.com/field/x/'), false)
  assert.equal(isLocalAddress('not a url'), false)
})

test('when the link stops: the time, in plain words, in both languages', () => {
  const now = new Date(2026, 9, 14, 10, 0, 0)
  const in23h = new Date(2026, 9, 15, 9, 0, 0)
  const a = expiryInfo(in23h.toISOString(), now)
  assert.equal(a.minutes, 23 * 60) // 10:00 to 09:00 the next day
  assert.match(a.when, /^09:00 \(15 Oct\)$/)
  assert.equal(a.left, '23 h')
  const soon = expiryInfo(new Date(2026, 9, 14, 10, 25, 0).toISOString(), now)
  assert.deepEqual([soon.when, soon.left, soon.expired], ['10:25', '25 min', false])
  assert.equal(expiryInfo(new Date(2026, 9, 14, 9, 0, 0).toISOString(), now).expired, true)
  assert.equal(expiryInfo('nonsense'), null)
  const l = expiryLines(new Date(2026, 9, 14, 13, 30, 0).toISOString(), now)
  assert.equal(l.en, 'This link will stop working at 13:30 (in 3.5 h).')
  assert.equal(l.fil, 'Mawawala ang link na ito sa 13:30 (sa loob ng 3.5 h).')
})

test('the states of the box', () => {
  assert.equal(boxState({}), 'none')
  assert.equal(boxState({ info: { live: false } }), 'none')
  assert.equal(boxState({ info: { live: true, url: '/field/x/' } }), 'live')
  assert.equal(boxState({ making: true, info: { live: true, url: '/field/x/' } }), 'making') // a new link is being made: say so
  assert.equal(boxState({ error: 'The service said no', info: { live: true, url: '/field/x/' } }), 'error')
  assert.equal(boxState({ making: true, error: 'x' }), 'making')
})

test('the words: both languages for every text, short, with the warning and the revoke question', () => {
  for (const [k, v] of Object.entries(TEXT)) {
    assert.ok(v.en.length > 1 && v.fil.length > 1, k)
    assert.ok(!/undefined|null|\[object/.test(v.en + v.fil), k)
    assert.ok(v.en.split(/\s+/).length <= 20 && v.fil.split(/\s+/).length <= 22, k + ' is too long')
  }
  assert.equal(TEXT.make.fil, 'Gumawa ng link para sa planter')
  assert.equal(TEXT.copy.fil, 'Kopyahin')
  assert.equal(TEXT.off.fil, 'Patayin ang link')
  assert.match(TEXT.warn.en, /restarts/)
  assert.match(TEXT.warn.en, /save the results file/)
  assert.match(TEXT.warn.fil, /nag-restart/)
  assert.match(TEXT.warn.fil, /results file/)
  assert.doesNotMatch(Object.values(TEXT).map((v) => v.fil).join(' '), /istaka|panukat|punla|hanay|pwesto/i)
})
