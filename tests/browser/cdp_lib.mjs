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
  const b = { tileMode: 'ok', log: [] }
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data)
    if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); return }
    if (d.method === 'Page.javascriptDialogOpening') { dialogs.push(d.params.message); send('Page.handleJavaScriptDialog', { accept: true }) }
    else if (d.method === 'Fetch.requestPaused') {
      tiles.push({ url: d.params.request.url, referer: d.params.request.headers.Referer || d.params.request.headers.referer || null })
      if (b.tileMode === 'fail') send('Fetch.failRequest', { requestId: d.params.requestId, errorReason: 'InternetDisconnected' })
      else send('Fetch.fulfillRequest', { requestId: d.params.requestId, responseCode: 200, responseHeaders: [{ name: 'Content-Type', value: 'image/png' }], body: PNG })
    } else if (d.method === 'Runtime.exceptionThrown') events.push(d)
  }
  const ev = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })
    if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400))
    return r.result?.result?.value
  }
  await send('Page.enable'); await send('Runtime.enable')
  await send('Fetch.enable', { patterns: [{ urlPattern: '*tile.openstreetmap.org*' }, { urlPattern: '*server.arcgisonline.com*' }] })
  Object.assign(b, {
    send, ev, tiles, dialogs, events, out, sleep,
    shot: async (n) => writeFileSync(join(out, n + '.png'), Buffer.from((await send('Page.captureScreenshot', { format: 'png' })).result.data, 'base64')),
    text: () => ev('document.body.innerText'),
    // click by visible text or by aria-label
    click: (label) => ev(`(() => { const L = ${JSON.stringify(label)}; const els = [...document.querySelectorAll('button, summary, [role=button]')].filter((e) => !e.hidden && e.getBoundingClientRect().width > 0); const e = els.find((x) => (x.getAttribute('aria-label') || '') === L || x.textContent.trim() === L) || els.find((x) => (x.getAttribute('aria-label') || '').includes(L)) || els.find((x) => x.textContent.trim().includes(L)); if (!e) return false; e.click(); return true })()`),
    // a real touch tap at the middle of the element (so a cover-up or a too-small target would make it fail)
    tap: async (label) => {
      const r = await ev(`(() => { const L = ${JSON.stringify(label)}; const els = [...document.querySelectorAll('button, summary, [role=button]')].filter((e) => !e.hidden && e.getBoundingClientRect().width > 0); const e = els.find((x) => (x.getAttribute('aria-label') || '') === L || x.textContent.trim() === L) || els.find((x) => (x.getAttribute('aria-label') || '').includes(L)) || els.find((x) => x.textContent.trim().includes(L)); if (!e) return null; if (!e.closest('.stage')) e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect(); return JSON.stringify({ x: r.x + r.width / 2, y: r.y + r.height / 2 }) })()`)
      if (!r) return false
      const p = JSON.parse(r)
      await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: p.x, y: p.y }] })
      await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
      return true
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
