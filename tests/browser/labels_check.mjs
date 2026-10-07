// Round 14: every label of the old Full view is still in the Detailed view. Needs the dashboard on http://localhost:5173 and the API on 8001 (a temporary data folder is best). Usage: node tests/browser/labels_check.mjs after
import { spawn } from 'node:child_process'
import { writeFileSync, mkdirSync } from 'node:fs'

const PART = process.argv[2] || 'on'
const OUT = process.env.TEMP || '/tmp'
const PROFILE = (process.env.TEMP || '/tmp') + '/os_labels_profile'
mkdirSync(OUT, { recursive: true })
const EDGE = process.env.EDGE_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const PORT = 9811
const BASE = 'http://localhost:5173/'
const API = 'http://127.0.0.1:8001'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const proc = spawn(EDGE, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}/p14l_${PART}_${Date.now()}`, '--window-size=1366,768', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' })
let targets
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); if (targets.find((t) => t.type === 'page')) break } catch { /* wait */ }
  await sleep(300)
}
const page = targets.find((t) => t.type === 'page')
const ws = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((r) => (ws.onopen = r))
let id = 0
const pending = new Map()
const problems = []
ws.onmessage = (m) => {
  const d = JSON.parse(m.data)
  if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) }
  if (d.method === 'Runtime.exceptionThrown') problems.push('EXCEPTION ' + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text).slice(0, 200))
  if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') problems.push('CONSOLE.error ' + d.params.args.map((a) => a.value || a.description).join(' ').slice(0, 200))
}
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expression) => { const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }); return r.result?.result?.value }
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(`${OUT}/${PART}_${name}.png`, Buffer.from(r.result.data, 'base64')) }
const waitFor = async (expr, label, ms = 15000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await ev('!!(' + expr + ')')) return true; await sleep(200) } console.log('   (timeout waiting for', label + ')'); return false }
const text = (sel) => ev(`(document.querySelector(${JSON.stringify(sel)})||{}).innerText||''`)
const click = (sel, contains = '') => ev(`(() => { const el=[...document.querySelectorAll(${JSON.stringify(sel)})].find(e=>e.textContent.includes(${JSON.stringify(contains)})); if(!el) return false; el.click(); return true })()`)
let failures = 0
const check = (name, ok, extra = '') => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? '  -> ' + String(extra).replace(/\n/g, ' | ').slice(0, 260) : ''}`); if (!ok) failures++ }
const setVal = (sel, value) => ev(`(() => { const s=document.querySelector(${JSON.stringify(sel)}); const proto=s.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto,'value').set.call(s,${JSON.stringify(value)}); s.dispatchEvent(new Event('input',{bubbles:true})); return true })()`)
const setSelect = (idv, value) => ev(`(() => { const s=document.getElementById(${JSON.stringify(idv)}); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,${JSON.stringify(value)}); s.dispatchEvent(new Event('change',{bubbles:true})); return true })()`)
const key = async (k, code, vk, txt) => { await send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code, windowsVirtualKeyCode: vk, text: txt }); await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk }) }
const stepOpen = (name) => ev(`(() => { const sec=document.querySelector('.nw-step[data-step=${name}]'); if(!sec) return false; if(!sec.classList.contains('is-open')) sec.querySelector('.nw-step-toggle').click(); return true })()`)
const mouse = (type, x, y) => send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1 })
const mapClick = async (x, y) => { await mouse('mouseMoved', x, y); await sleep(60); await mouse('mousePressed', x, y); await mouse('mouseReleased', x, y); await sleep(400) }
const OVERLAYS = '.nw-sidebar,.nw-topbar,.nw-right,.nw-legend,.nw-legend-btn,.nw-plan-legend,.leaflet-control,.nw-toasts,.nw-toggle,.nw-search,.nw-mapview,.nw-card'
const PLAN_RGB = [[230, 159, 0], [86, 180, 233], [0, 195, 137], [240, 228, 66], [59, 130, 246], [255, 107, 53], [232, 121, 198], [163, 230, 53], [192, 132, 252]]
const findPlanTree = (skip = 0) => ev(`(() => { const cols=${JSON.stringify(PLAN_RGB)}; const c=document.querySelector('canvas.nw-grid-canvas'); const ctx=c.getContext('2d'); const w=c.width,h=c.height; const img=ctx.getImageData(0,0,w,h).data; const r=c.getBoundingClientRect(); const dpr=window.devicePixelRatio||1; let n=0;
  for (let y=0; y<h; y+=1) for (let x=0; x<w; x+=1) { const i=(y*w+x)*4; if (img[i+3]<250) continue; if (!cols.some(([R,G,B])=>Math.abs(img[i]-R)<3&&Math.abs(img[i+1]-G)<3&&Math.abs(img[i+2]-B)<3)) continue; const px=r.left+x/dpr, py=r.top+y/dpr; if (px<380||px>1330||py<150||py>720) continue; const el=document.elementFromPoint(px,py); if (el && !el.closest(${JSON.stringify(OVERLAYS)})) { if (n++>=${skip}) return {x:px,y:py} } } return null })()`)
const meta = () => ev(`(() => { const d=document.querySelector('canvas.nw-grid-canvas')?.dataset||{}; return {points:d.points, plan:d.plan, planDrawn:d.planDrawn} })()`)
const uzPath = (path) => (process.env.UZ === 'off' && /^\/(grid|rank|areas|nearest-viable|plan-event|health|search)/.test(path) && !path.includes('include_unzoned')) ? path + (path.includes('?') ? '&' : '?') + 'include_unzoned=false' : path
const api = async (path, opts) => (await fetch(API + uzPath(path), opts)).json()
const openMapView = async () => { if (!(await ev(`!!document.querySelector('.nw-mapview-menu')`))) { await click('.nw-mapview-btn', 'Map view'); await sleep(250) } }

const dmNow = (n) => ev(`(() => { const d=new Date(); d.setDate(d.getDate()+${n}); return d.getDate()+' '+['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()] })()`)

import { readFileSync, writeFileSync as wf } from 'node:fs'
const BASE_FILE = process.argv[3] || new URL('../fixtures/full_view_labels_before_round14.json', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const dmNow2 = dmNow
await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable')
await send('Page.addScriptToEvaluateOnNewDocument', { source: "try{localStorage.setItem('nw_view_mode','full')}catch(e){}" + "try{localStorage.setItem('nw_map_detail','simple')}catch(e){}" + "try{localStorage.setItem('nw_legend_open','false')}catch(e){}" + "try{localStorage.setItem('nw_tour_done','1')}catch(e){}" + "try{localStorage.setItem('nw_help_banner_off','1')}catch(e){}" })
await send('Emulation.setDeviceMetricsOverride', { width: 1366, height: 768, deviceScaleFactor: 1, mobile: false })
await send('Page.navigate', { url: BASE + '#/new' }); await sleep(2500)
await waitFor(`document.querySelector('canvas.nw-grid-canvas')?.dataset.points`, 'grid', 30000)
await sleep(1500)

const captured = {}
const grab = async (name, sel) => {
  const t = await ev(`(() => { const e=document.querySelector(${JSON.stringify(sel)}); return e ? e.innerText : '' })()`)
  captured[name] = t
}
const norm = (line) => line.replace(/\s+/g, ' ').trim().replace(/\d+(\.\d+)?/g, '#')
const labelsOf = (t) => [...new Set(t.split('\n').map(norm).filter((l) => l.length >= 3 && l.length <= 140))]

// 1. area mode, Santa Ana, season filter off so species show
await stepOpen('goal'); await click('.nw-mode', 'I have an area'); await sleep(500)
await stepOpen('window'); await sleep(300)
await ev(`(() => { const c=document.getElementById('nw-only-season'); if (c && c.checked) c.click() })()`); await sleep(800)
await stepOpen('pick'); await sleep(300)
await setSelect('nw-barangay', 'STA ANA'); await sleep(2500)
await grab('area_panel', '.nw-right')
// 2. species card
await ev(`(() => { const b=document.querySelector('.nw-right .nw-namebtn'); if (b) b.click() })()`); await sleep(1800)
await grab('species_card', '.nw-card')
await ev(`(() => { const b=[...document.querySelectorAll('.nw-card button')].find(x=>x.textContent.includes('Close')); if (b) b.click() })()`); await sleep(400)
// 3. a point panel (grid point 5048 by the search box)
await ev(`(() => { const i=document.querySelector('.nw-search-input'); i.focus() })()`)
await setVal('.nw-search-input', '5048'); await sleep(1200)
await key('Enter', 'Enter', 13, '\r'); await sleep(2800)
await grab('point_panel', '.nw-right')
// 4. a plan (area mode, Santa Ana, 100 trees)
await stepOpen('plan'); await sleep(300)
await setVal('#nw-campaign-name', 'Label check'); await setVal('#nw-campaign-unit', 'Team'); await setVal('#nw-saplings', '100'); await sleep(1800)
await grab('plan_form', '.nw-step[data-step=plan]')
await click('.nw-step[data-step=plan] .nw-btn-wide', 'Create plan'); await waitFor(`document.querySelector('.nw-created')`, 'created', 60000); await sleep(2500)
await grab('plan_result', '.nw-right')
// 5. open the field-kit / progress parts if they are behind tabs (the label test wants every label reachable)
for (const tabName of ['Field kit', 'Progress', 'Plan']) {
  await ev(`(() => { const b=[...document.querySelectorAll('.nw-right [role=tab]')].find(x=>x.textContent.trim()===${JSON.stringify(tabName)}); if (b) b.click() })()`); await sleep(900)
  await grab('plan_result_tab_' + tabName, '.nw-right')
}
// 6. species mode with two chosen species: the areas panel
await stepOpen('goal'); await click('.nw-mode', 'I have species'); await sleep(500)
await stepOpen('pick'); await sleep(300)
await ev(`(() => { const want=['Duhat','Kamagong']; [...document.querySelectorAll('.nw-check-sp')].filter(l=>want.some(w=>l.textContent.includes(w))).forEach(l=>l.querySelector('input').click()) })()`); await sleep(2500)
await grab('areas_panel', '.nw-right')
await stepOpen('plan'); await sleep(500)
await grab('plan_form_species', '.nw-step[data-step=plan]')

const all = {}
for (const [k, t] of Object.entries(captured)) all[k] = labelsOf(t)
if (PART === 'baseline') {
  wf(BASE_FILE, JSON.stringify({ captured: all, raw: captured }, null, 1))
  console.log('baseline saved:', Object.entries(all).map(([k, v]) => `${k}=${v.length}`).join(' '))
} else {
  const base = JSON.parse(readFileSync(BASE_FILE, 'utf-8')).captured
  const everywhere = new Set(Object.values(all).flat())
  let missing = 0
  for (const [k, labels] of Object.entries(base)) {
    // a line that holds only a zero value is deliberately hidden (round 14: "never show lines whose value is zero")
    const RENAMED = new Set(['Compact', 'Full details', 'Please note']) // round 14: Compact | Full details -> Simple | Detailed; Please note -> Good to know
    const lost = labels.filter((l) => !everywhere.has(l) && !RENAMED.has(l) && !l.startsWith('# of # trees are on') && !l.startsWith('# squares excluded')) // zero lines are hidden on purpose
    missing += lost.length
    console.log(`${lost.length === 0 ? 'PASS' : 'FAIL'}  every label of the old Full view "${k}" is still in the Detailed view (${labels.length} labels)`, lost.length ? '-> missing: ' + lost.slice(0, 12).join(' || ') : '')
    if (lost.length) failures++
  }
  const renamedOk = everywhere.has('Simple') && everywhere.has('Detailed')
  console.log(`${renamedOk ? 'PASS' : 'FAIL'}  the switch now reads Simple | Detailed`)
  if (!renamedOk) failures++
  console.log(failures === 0 ? 'ALL PASS' : failures + ' FAILED')
}
ws.close(); proc.kill(); process.exit(0)

