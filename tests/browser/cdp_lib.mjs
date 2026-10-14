// Shared helper of the field pack browser checks: headless Edge through the Chrome DevTools protocol (no packages), fake GPS, intercepted map tiles, real touch taps.
// The tile requests are ALWAYS caught here and answered with a small picture (or made to fail), so no check ever contacts openstreetmap.org or arcgisonline.com.
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const EDGE = process.env.EDGE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export async function launch({ out = tmpdir() } = {}) {
  const port = 9400 + Math.floor(Math.random() * 400)
  const edge = spawn(EDGE, [`--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'edge_fp_'))}`, '--headless=new', '--disable-gpu', '--no-first-run', 'about:blank'], { stdio: 'ignore' })
  let tgt
  for (let i = 0; i < 60; i++) { try { tgt = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === 'page'); if (tgt) break } catch {} await sleep(300) }
  const ws = new WebSocket(tgt.webSocketDebuggerUrl)
  await new Promise((r) => (ws.onopen = r))
  let id = 0
  const pending = new Map()
  const events = []
  const tiles = []
  const dialogs = []
  const consoleErrors = []
  const b = { tileMode: 'ok', log: [] }
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data)
    if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); return }
    if (d.method === 'Page.javascriptDialogOpening') { dialogs.push(d.params.message); send('Page.handleJavaScriptDialog', { accept: true }) }
    else if (d.method === 'Fetch.requestPaused') {
      if (b.onPaused && b.onPaused(d.params, send)) return // a check may take over some requests (a failing service call)
      tiles.push({ url: d.params.request.url, referer: d.params.request.headers.Referer || d.params.request.headers.referer || null })
      if (b.tileMode === 'fail') send('Fetch.failRequest', { requestId: d.params.requestId, errorReason: 'InternetDisconnected' })
      else send('Fetch.fulfillRequest', { requestId: d.params.requestId, responseCode: 200, responseHeaders: [{ name: 'Content-Type', value: 'image/png' }], body: PNG })
    } else if (d.method === 'Runtime.exceptionThrown') events.push(d)
    else if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') consoleErrors.push(d.params.args.map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 200))
    else if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error') consoleErrors.push((d.params.entry.text + ' ' + (d.params.entry.url || '')).slice(0, 200))
  }
  const ev = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })
    if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400))
    return r.result?.result?.value
  }
  await send('Page.enable'); await send('Runtime.enable'); await send('Log.enable')
  await send('Fetch.enable', { patterns: [{ urlPattern: '*tile.openstreetmap.org*' }, { urlPattern: '*server.arcgisonline.com*' }] })
  Object.assign(b, {
    send, ev, tiles, dialogs, events, consoleErrors, out, sleep,
    shot: async (n) => writeFileSync(join(out, n + '.png'), Buffer.from((await send('Page.captureScreenshot', { format: 'png' })).result.data, 'base64')),
    text: () => ev('document.body.innerText'),
    // click by visible text or by aria-label
    click: (label) => ev(`(() => { const L = ${JSON.stringify(label)}; const els = [...document.querySelectorAll('button, summary, [role=button]')].filter((e) => !e.hidden && e.getBoundingClientRect().width > 0); const e = els.find((x) => (x.getAttribute('aria-label') || '') === L || x.textContent.trim() === L) || els.find((x) => (x.getAttribute('aria-label') || '').includes(L)) || els.find((x) => x.textContent.trim().includes(L)); if (!e) return false; e.click(); return true })()`),
    // a real touch tap at the middle of the element (so a cover-up or a too-small target would make it fail)
    tap: async (label) => {
      const find = `(() => { const L = ${JSON.stringify(label)}; const els = [...document.querySelectorAll('button, summary, [role=button]')].filter((e) => !e.hidden && e.getBoundingClientRect().width > 0); return els.find((x) => (x.getAttribute('aria-label') || '') === L || x.textContent.trim() === L) || els.find((x) => (x.getAttribute('aria-label') || '').includes(L)) || els.find((x) => x.textContent.trim().includes(L)) || null })()`
      // make sure nothing covers the middle of the button (a real finger would hit the cover): scroll the page or the bottom sheet a little until the button itself is under that point
      const r = await ev(`(() => { const e = ${find}; if (!e) return null; if (!e.closest('.stage') && !e.closest('.overlay')) e.scrollIntoView({ block: 'center' }); const sheet = e.closest('.sheetbody') || e.closest('.sheet'); const over = e.closest('.overlay .overlaybox'); for (let i = 0; i < 12; i++) { const r = e.getBoundingClientRect(); const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); if (top === e || e.contains(top)) break; if (sheet) sheet.scrollTop += 60; else if (over) over.scrollTop += 60; else break } const r = e.getBoundingClientRect(); const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return JSON.stringify({ x: r.x + r.width / 2, y: r.y + r.height / 2, covered: !(top === e || e.contains(top)), cover: top ? top.tagName + '.' + String(top.className && top.className.baseVal !== undefined ? top.className.baseVal : top.className) : 'nothing' }) })()`)
      if (!r) return false
      const p = JSON.parse(r)
      if (p.covered) b.check('a button was NOT covered when tapped: ' + label, false, 'covered by ' + p.cover)
      await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: p.x, y: p.y }] })
      await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
      return true
    },
    // the same real touch tap, for an element found by a CSS selector (a drag handle, a tour button, a chip ...)
    tapSel: async (sel) => {
      const r = await ev(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e || e.closest('[hidden]')) return null; const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return null; const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return JSON.stringify({ x: r.x + r.width / 2, y: r.y + r.height / 2, covered: !(top === e || e.contains(top)), cover: top ? top.tagName + '.' + String(top.className && top.className.baseVal !== undefined ? top.className.baseVal : top.className) : 'nothing' }) })()`)
      if (!r) return false
      const p = JSON.parse(r)
      if (p.covered) b.check('an element was NOT covered when tapped: ' + sel, false, 'covered by ' + p.cover)
      await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: p.x, y: p.y }] })
      await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
      return true
    },
    // a touch at a point, and a drag from one point to another (steps of 10 ms)
    touch: async (x, y) => { await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] }); await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }) },
    swipe: async (x, y0, y1, steps = 8) => {
      await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y: y0 }] })
      for (let i = 1; i <= steps; i++) { await send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: y0 + ((y1 - y0) * i) / steps }] }); await sleep(10) }
      await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    },
    // a fresh page with the given settings of the person (language, text size level 0..4, tours seen)
    fresh: async (url, { lang = 'en', size, tours = true, extra = {}, session = {} } = {}) => {
      await b.open(url)
      const prefs = Object.assign({ lang }, size === undefined ? {} : { size }, tours ? { tour: { landing: true, home: true, block: true } } : {}, extra)
      await ev(`sessionStorage.clear(); localStorage.clear(); localStorage.setItem('fieldpack:prefs', ${JSON.stringify(JSON.stringify({ v: 1, observer: '', trees: {}, prefs }))}); for (const [k, v] of Object.entries(${JSON.stringify(session)})) sessionStorage.setItem(k, v)`)
      await b.open(url)
    },
    gps: (lat, lon, accuracy, extra = {}) => send('Emulation.setGeolocationOverride', { latitude: lat, longitude: lon, accuracy, ...extra }),
    viewport: async (w, h) => {
      await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 2, mobile: true })
      await send('Emulation.setTouchEmulationEnabled', { enabled: true })
    },
    open: async (url) => {
      await send('Browser.grantPermissions', { permissions: ['geolocation'], origin: url.startsWith('file:') ? 'file://' : new URL(url).origin }).catch(() => {})
      await send('Page.navigate', { url })
      await sleep(1400)
    },
    waitFor: async (re, ms = 6000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (re.test(await b.text())) return true; await sleep(150) } return false },
    waitExpr: async (expr, ms = 6000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await ev(expr)) return true } catch {} await sleep(150) } return false },
    check: (name, ok, extra = '') => { b.log.push({ name, ok: !!ok, extra }); console.log((ok ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : '')) },
    // orientation events like a phone would send (Android: absolute alpha / beta / gamma; iOS: webkitCompassHeading)
    androidHeading: (alpha, beta = 0, gamma = 0) => ev(`window.dispatchEvent(new DeviceOrientationEvent('deviceorientationabsolute', { alpha: ${alpha}, beta: ${beta}, gamma: ${gamma}, absolute: true }))`),
    iosHeading: (deg) => ev(`(() => { const e = new Event('deviceorientation'); Object.defineProperty(e, 'webkitCompassHeading', { value: ${deg} }); window.dispatchEvent(e) })()`),
    addScript: (source) => send('Page.addScriptToEvaluateOnNewDocument', { source }),
    // the words that must never be visible
    badText: async () => JSON.parse(await ev(`(() => {
      const out = []
      const word = /\\b(null|undefined|NaN)\\b/
      const hole = /\\{[A-Za-z]+\\}|\\[[A-Za-z]+(_[A-Za-z]+)*\\]/
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      let n
      while ((n = w.nextNode())) {
        const p = n.parentElement
        if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(p.tagName)) continue
        if (word.test(n.textContent) || hole.test(n.textContent)) out.push(n.textContent.trim().slice(0, 50))
      }
      for (const e of document.querySelectorAll('[aria-label], [title]')) {
        const v = (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '')
        if (word.test(v) || hole.test(v)) out.push('attribute: ' + v.trim().slice(0, 50))
      }
      return JSON.stringify(out)
    })()`)),
    noBadText: async (where) => { const bad = await b.badText(); b.check(`no "null", "undefined", "NaN" or missing text on ${where}`, bad.length === 0, bad.join(' | ')) },
    done: async (name) => {
      writeFileSync(join(out, name + '.json'), JSON.stringify(b.log, null, 1))
      const failed = b.log.filter((l) => !l.ok).length
      console.log(`\n${b.log.length - failed} passed, ${failed} failed`)
      ws.close(); spawn('taskkill', ['/PID', String(edge.pid), '/T', '/F'], { stdio: 'ignore' })
      await sleep(500)
      process.exit(failed ? 1 : 0)
    },
  })
  return b
}
