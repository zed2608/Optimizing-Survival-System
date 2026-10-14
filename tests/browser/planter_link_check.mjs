// Stage A2 in headless Edge, against a REAL service (uvicorn with the built dashboard, the public sandbox and the access code on):
//  1. the dashboard: Campaign Logs > "Make a link for the planter": making, the link, Copy, the QR code (decoded back from the page with jsQR), when it stops, the warning, replace, switch off with a question,
//     and an error with "Try again" (the service call is made to fail);
//  2. the planter: the link opened WITHOUT the access code loads the page, the map tiles come with the origin as Referer, no console errors, and the page works;
//  3. a bad token gets the plain 404.
//   node tests/browser/planter_link_check.mjs <base address> <access cookie value> <plan id> <folder for pictures>
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import { launch } from './cdp_lib.mjs'

const [BASE, COOKIE, PLAN, OUT] = process.argv.slice(2)
const require = createRequire(resolve('frontend/package.json'))
const jsQR = require('jsqr')
const b = await launch({ out: OUT })
const { ev, text, tap, tapSel, check, sleep, waitExpr, noBadText } = b
const host = new URL(BASE).hostname
const setCookie = () => b.send('Network.setCookie', { name: 'os_access', value: COOKIE, domain: host, path: '/' })
const tapV = async (q) => { await ev(`document.querySelector(${JSON.stringify(q)})?.scrollIntoView({ block: 'center' })`); await sleep(150); return tapSel(q) } // a button below the fold is scrolled to first, as a person would
const visible = (q) => ev(`(() => { const e = document.querySelector(${JSON.stringify(q)}); return !!e && !e.closest('[hidden]') && e.getBoundingClientRect().width > 0 })()`)
// the planter's requests are made by Node itself (no cookie at all): a fetch from inside the dashboard page would trigger the dashboard's own redirect to the login page
const fetchStatus = async (u) => { const r = await fetch(u, { redirect: 'manual' }); return { status: r.status, type: r.type, body: (await r.text()).slice(0, 40) } }

await b.send('Network.enable')
await setCookie()
await b.viewport(1100, 900)
await b.open(`${BASE}/#/new`)
await sleep(2500)
await tap('Campaign Logs')
await waitExpr(`document.querySelectorAll('.nw-plink').length > 0`, 12000)
const card = `.nw-plink`
// the card of our plan: the one whose input id names the plan; there may be several plans in the list, so find the box of OUR plan through its Make button inside the card that holds the plan id text
const found = await waitExpr(`[...document.querySelectorAll('li')].some((x) => x.textContent.includes(${JSON.stringify(PLAN)}) && x.querySelector('.nw-plink'))`, 20000)
if (!found) { await b.shot('plink_0_not_found'); console.log('PAGE TEXT: ' + (await text()).slice(0, 600)) }
const markJs = `window.__mark = () => { const li = [...document.querySelectorAll('li')].find((x) => x.textContent.includes(${JSON.stringify(PLAN)}) && x.querySelector('.nw-plink')); document.querySelectorAll('[data-ours]').forEach((e) => e !== li && e.removeAttribute('data-ours')); if (li) li.setAttribute('data-ours', '1') }; window.__markTimer && clearInterval(window.__markTimer); window.__markTimer = setInterval(window.__mark, 50); window.__mark()` // the dashboard may redraw the list: keep the mark on OUR plan's card
await ev(markJs)
const mine = (q) => `[data-ours="1"] ${q}`
check('Campaign Logs shows the plan with the planter-link box next to the kit buttons (the kit buttons are still there)', await visible(mine('.nw-plink')) && /Build field kit|Rebuild field kit/.test(await ev(`document.querySelector('[data-ours="1"]').innerText`)))
check('the button is in two languages and says "Make a link for the planter"', /Make a link for the planter/.test(await ev(`document.querySelector('${mine('[data-act="make"]')}').innerText`)) && /Gumawa ng link para sa planter/.test(await ev(`document.querySelector('${mine('[data-act="make"]')}').innerText`)))
await b.shot('plink_1_none')

// ---- make: the state "making", then the link
await tapV(mine('[data-act="make"]'))
await waitExpr(`document.querySelector('[data-ours="1"] .nw-plink').dataset.state === 'live'`, 30000)
const link = await ev(`document.querySelector('${mine('.nw-plink-url input')}').value`)
const token = link.split('/field/')[1].replace('/', '')
check('a live link: the service address, /field/ and a 22-character token', link.startsWith(BASE + '/field/') && /^[A-Za-z0-9_-]{22}$/.test(token), link.replace(token, token.slice(0, 4) + '…'))
const exp = await ev(`document.querySelector('${mine('[data-role="expiry"]')}').innerText`)
check('"This link will stop working at HH:MM (in … h)" and the same in Filipino', /This link will stop working at \d\d:\d\d.*\(in [\d.]+ (h|min)\)/.test(exp) && /Mawawala ang link na ito sa \d\d:\d\d/.test(exp), exp)
const warn = await ev(`document.querySelector('${mine('.nw-plink-warn')}').innerText`)
check('a clear warning: the link stops when the server restarts, and the planter must save the results file (both languages)', /restarts/.test(warn) && /save the results file/.test(warn) && /nag-restart/.test(warn) && /results file/.test(warn), warn)
check('Copy, a QR code and "Switch off this link" are shown', (await visible(mine('[data-act="copy"]'))) && (await visible(mine('svg.nw-plink-qr'))) && (await visible(mine('[data-act="off"]'))))
const qrPath = await ev(`document.querySelector('${mine('svg.nw-plink-qr path')}').getAttribute('d')`)
const qrSize = Number(await ev(`document.querySelector('${mine('svg.nw-plink-qr')}').dataset.qr`))
const scale = 8, w = qrSize * scale
const px = new Uint8ClampedArray(w * w * 4).fill(255)
for (const m of qrPath.matchAll(/M(\d+) (\d+)h1v1h-1z/g)) for (let y = Number(m[2]) * scale; y < (Number(m[2]) + 1) * scale; y++) for (let x = Number(m[1]) * scale; x < (Number(m[1]) + 1) * scale; x++) { const i = (y * w + x) * 4; px[i] = px[i + 1] = px[i + 2] = 0 }
const decoded = jsQR(px, w, w)
check('the QR code on the page, read back with a QR decoder (jsQR), is the link', !!decoded && decoded.data === link, decoded ? decoded.data.slice(0, 40) : 'not read')
check('the QR svg is drawn by the page (no image file, no CDN)', await ev(`!document.querySelector('${mine('svg.nw-plink-qr')}').querySelector('image') && !document.documentElement.outerHTML.includes('cdn.')`))
await b.shot('plink_2_live')
await noBadText('the planter link box')

// ---- copy
await b.send('Browser.grantPermissions', { permissions: ['clipboardReadWrite', 'clipboardSanitizedWrite'], origin: new URL(BASE).origin }).catch(() => {})
await tapV(mine('[data-act="copy"]')); await sleep(400)
check('Copy: the button says "Copied" and the clipboard holds the link', /Copied/.test(await ev(`document.querySelector('${mine('[data-act="copy"]')}').innerText`)) && (await ev(`navigator.clipboard.readText().catch(() => 'no clipboard')`)) === link)

// ---- the planter (no cookie) opens it
const planter = await fetchStatus(link)
check('without the access code the link answers 200 (not a redirect to the login page)', planter.status === 200 && planter.type !== 'opaqueredirect', JSON.stringify(planter))
check('without the code every other address still asks for it', (await fetchStatus(`${BASE}/health`)).status === 401 && (await fetchStatus(`${BASE}/plans`)).status === 401)
const bad = await fetchStatus(`${BASE}/field/${'a'.repeat(22)}/`)
check('a wrong token gets the plain 404 "Not found."', bad.status === 404 && bad.body === 'Not found.', JSON.stringify(bad))

// ---- replace: a new link, the old one dies
await tapV(mine('[data-act="make"]'))
const replaced = await waitExpr(`!!document.querySelector('[data-ours="1"] .nw-plink-url input') && document.querySelector('[data-ours="1"] .nw-plink-url input').value !== ${JSON.stringify(link)}`, 30000)
if (!replaced) { await b.shot('plink_0_replace'); console.log('STATE ' + (await ev(`document.querySelector('[data-ours="1"] .nw-plink')?.dataset.state + ' | ' + (document.querySelector('[data-ours="1"] .nw-plink')?.innerText || 'no box').slice(0, 300)`))) }
const link2 = await ev(`document.querySelector('${mine('.nw-plink-url input')}').value`)
check('"Make a new link" replaces the old link (the old address now says Not found)', link2 !== link && (await fetchStatus(link)).status === 404 && (await fetchStatus(link2)).status === 200)

// ---- an error with "Try again": the service call fails once
let failOnce = true
b.onPaused = (p, send) => {
  if (/field-pack/.test(p.request.url) && p.request.method === 'POST' && failOnce) { failOnce = false; send('Fetch.failRequest', { requestId: p.requestId, errorReason: 'Failed' }); return true }
  if (/field-pack/.test(p.request.url)) { send('Fetch.continueRequest', { requestId: p.requestId }); return true }
  return false
}
await b.send('Fetch.enable', { patterns: [{ urlPattern: '*tile.openstreetmap.org*' }, { urlPattern: '*server.arcgisonline.com*' }, { urlPattern: '*field-pack*' }] })
await tapV(mine('[data-act="make"]'))
await waitExpr(`document.querySelector('[data-ours="1"] .nw-plink').dataset.state === 'error'`, 15000)
check('an error shows a message and a "Try again" button', (await visible(mine('[role="alert"]'))) && (await visible(mine('[data-act="retry"]'))), await ev(`document.querySelector('${mine('[role="alert"]')}')?.innerText`))
await b.shot('plink_3_error')
await tapV(mine('[data-act="retry"]'))
await waitExpr(`document.querySelector('[data-ours="1"] .nw-plink').dataset.state === 'live'`, 30000)
const link3 = await ev(`document.querySelector('${mine('.nw-plink-url input')}').value`)
check('"Try again" makes the link', link3.startsWith(BASE + '/field/') && (await fetchStatus(link3)).status === 200)

// ---- switch off, with a question
await tapV(mine('[data-act="off"]'))
check('"Switch off" asks first (both languages), nothing is switched off yet', (await visible(mine('[role="alertdialog"]'))) && /Switch off this link\?/.test(await ev(`document.querySelector('${mine('[role="alertdialog"]')}').innerText`)) && (await fetchStatus(link3)).status === 200)
await tapV(mine('[data-act="off-no"]'))
check('"No, keep it" keeps the link', !(await visible(mine('[role="alertdialog"]'))) && (await fetchStatus(link3)).status === 200)
await tapV(mine('[data-act="off"]'))
await tapV(mine('[data-act="off-yes"]'))
await waitExpr(`document.querySelector('[data-ours="1"] .nw-plink').dataset.state === 'none'`, 15000)
check('"Yes, switch it off": the box goes back to "Make a link" and the link says Not found', (await fetchStatus(link3)).status === 404 && (await visible(mine('[data-act="make"]'))))
// a link that is live when the page is opened again (it is read from the service)
await tapV(mine('[data-act="make"]'))
await waitExpr(`document.querySelector('[data-ours="1"] .nw-plink').dataset.state === 'live'`, 30000)
const link4 = await ev(`document.querySelector('${mine('.nw-plink-url input')}').value`)
await b.send('Page.reload'); await sleep(3000)
await tap('Campaign Logs')
await ev(markJs)
await waitExpr(`document.querySelectorAll('.nw-plink[data-state="live"]').length > 0`, 15000)
check('after a reload of the dashboard the live link is shown again (read from the service)', (await ev(`[...document.querySelectorAll('.nw-plink-url input')].map((i) => i.value).includes(${JSON.stringify(link4)})`)))

// ---- the planter's phone: no cookie, the page of the link
b.onPaused = null
await b.send('Network.clearBrowserCookies')
await b.viewport(360, 640)
b.tiles.length = 0
b.consoleErrors.length = 0
b.events.length = 0
await b.open(link4)
await sleep(1500)
check('the planter page opens from the link without the access code (the first page of the pack)', (await ev(`document.title`)).includes(PLAN) && (await text()).length > 100)
const pk = JSON.parse(await ev("document.getElementById('pack-data').textContent"))
await ev(`localStorage.setItem('fieldpack:prefs', JSON.stringify({ v: 1, observer: '', trees: {}, prefs: { lang: 'en', tour: { landing: true, home: true, block: true } } }))`)
await b.open(link4)
await tap('Start'); await sleep(300)
await tap(pk.blocks[0].ref)
await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${pk.blocks[0].n}`, 10000)
await sleep(1500)
const osm = b.tiles.filter((x) => x.url.includes('tile.openstreetmap.org'))
check('the map tiles are asked for at openstreetmap.org, and ONLY there', osm.length > 0 && b.tiles.every((x) => x.url.includes('tile.openstreetmap.org')), `${osm.length} tile requests`)
check('every tile request carries a valid Referer: the origin only (not the secret path)', osm.every((x) => x.referer === new URL(BASE).origin + '/'), [...new Set(osm.map((x) => x.referer))].join(' , '))
check('no satellite layer is offered by the served page', !(await ev(`!!document.querySelector('.rbtn[aria-label="Map: aerial photo"], .rbtn[aria-label="Map: standard"]')`)) && !(await ev('document.documentElement.outerHTML')).includes('arcgisonline'))
check('no page errors and no console errors on the planter page', b.events.length === 0 && b.consoleErrors.length === 0, JSON.stringify(b.consoleErrors.slice(0, 3)))
await noBadText('the planter page served from the link')
await b.shot('plink_4_planter')
check('no uncaught page errors during the whole run', b.events.length === 0, b.events.length ? JSON.stringify(b.events[0].params.exceptionDetails).slice(0, 300) : '')
await b.done('planter_link_report')
