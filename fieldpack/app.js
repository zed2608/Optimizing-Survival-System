/* Field pack, stage A1e: the page. Plain JavaScript, no framework. Every word the person reads comes from STRINGS (strings.js, one table per language) through t().
 * The plan (blocks, per-tree coordinates) is the JSON element with the id pack-data. Results and settings are kept on this phone only (localStorage, in try/catch).
 * The page's own code never sends anything anywhere; the map tiles are the only network requests (they come from the tile layers in the plan data).
 * Honest by design: phone GPS is 3 to 10 m off and trees are 3 to 20 m apart. The arrow and the distance point to the target (the START corner in step 1, the chosen tree after that),
 * but they only bring the planter close: the tape measure or the paces set each tree, and the page says so.
 * Screens: landing (how to use) -> home (the blocks) -> block (four steps, a map and a bottom panel that can be collapsed). Help and the guided tour are overlays.
 * The whole interface scales with the Aa - / Aa + buttons (five levels, 85% to 150%, through the CSS variable --ui and rem units). */
(function () {
  'use strict'
  const Core = FieldPackCore
  const pack = JSON.parse(document.getElementById('pack-data').textContent)
  const store = Core.makeStore(() => window.localStorage, `fieldpack:${pack.plan_id}:${pack.check_code}`)
  let state = store.load()
  // settings of the person on this phone (language, text size, tours seen, checklist, step of each block): kept apart from the marks
  const prefsStore = Core.makeStore(() => window.localStorage, 'fieldpack:prefs')
  const prefsState = prefsStore.load()
  prefsState.prefs = prefsState.prefs || {}
  const prefs = prefsState.prefs
  const savePrefs = () => prefsStore.save(prefsState)
  let lang = prefs.lang === 'en' || prefs.lang === 'fil' ? prefs.lang : 'fil' // Filipino unless the person chose English
  const t = (id, vars) => {
    const table = STRINGS[lang] || STRINGS.fil
    let s = table[id]
    if (s === undefined) return '[' + id + ']'
    if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m))
    return s
  }
  const view = { screen: 'landing', ref: null, tree: null, skipOpen: false, gpsOpen: false, step: 1 }
  // status: off (not asked yet) | waiting | ok | error (reason: denied | timeout | unavailable | none | insecure) | nogps (the person chose to go on without GPS: kept in memory only, never saved)
  const gps = { id: null, fix: null, status: 'off', error: '', reason: '' }
  // heading: where the phone / the person faces. Sources in order: the phone's compass, then the GPS heading while walking, else none.
  const hdg = { compass: { deg: null, at: 0, status: 'off', listening: false }, gps: { deg: null, speed: 0, at: 0 }, smooth: null, source: 'none', raw: [], paintQueued: false }
  const mapState = { follow: false, rotate: false, base: 'osm', view: null, ref: null, ok: 0, bad: 0 }
  const ui = {} // the elements of the block screen (made again with the screen)
  const ml = { markers: {} } // the map layers
  let map = null
  let handlers = [] // window listeners to remove when the block screen is left
  let timer = null
  let overlay = null
  let tour = null
  const wake = { want: false, sentinel: null }
  const root = document.getElementById('app')
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

  // ------------------------------------------------------------------ small helpers. The DOM is built with textContent only: nothing from the plan is ever read as HTML.
  // Nothing that is null, undefined or true/false may ever become text on the page: `h` skips them, and every other way of putting a list of nodes on the page goes through `clean`.
  const clean = (list) => list.filter((x) => x !== null && x !== undefined && typeof x !== 'boolean')
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag)
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue
      if (k === 'class') e.className = v
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v)
      else e.setAttribute(k, v === true ? '' : v)
    }
    for (const kid of clean(kids.flat())) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)))
    return e
  }
  const SVG_NS = 'http://www.w3.org/2000/svg'
  function svgEl(tag, attrs, ...kids) {
    const e = document.createElementNS(SVG_NS, tag)
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v)
    for (const kid of clean(kids)) e.append(kid)
    return e
  }
  const ICONS = {
    locate: () => [svgEl('circle', { cx: 12, cy: 12, r: 4 }), svgEl('path', { d: 'M12 2v4M12 18v4M2 12h4M18 12h4' })],
    follow: () => [svgEl('path', { d: 'M12 3l7 18-7-4-7 4z' })],
    rotate: () => [svgEl('circle', { cx: 12, cy: 12, r: 9 }), svgEl('path', { d: 'M15.5 8.5l-2 5-5 2 2-5z' })],
    zoomin: () => [svgEl('circle', { cx: 10.5, cy: 10.5, r: 6.5 }), svgEl('path', { d: 'M15.5 15.5L21 21M7.5 10.5h6M10.5 7.5v6' })], // a magnifier: this is the MAP zoom, not the text size
    zoomout: () => [svgEl('circle', { cx: 10.5, cy: 10.5, r: 6.5 }), svgEl('path', { d: 'M15.5 15.5L21 21M7.5 10.5h6' })],
    layers: () => [svgEl('path', { d: 'M12 3l9 5-9 5-9-5zM3 13l9 5 9-5' })],
    chevUp: () => [svgEl('path', { d: 'M5 15l7-7 7 7' })],
    chevDown: () => [svgEl('path', { d: 'M5 9l7 7 7-7' })],
  }
  const icon = (name) => svgEl('svg', { viewBox: '0 0 24 24', 'aria-hidden': 'true', focusable: 'false' }, ...ICONS[name]())
  const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
  const save = () => store.save(state)
  const blockOf = (ref) => pack.blocks.find((b) => b.ref === ref)
  const fmt = (x) => x.toFixed(6)
  const num = (x) => String(Math.round(x * 100) / 100) // 7 -> "7", 12.5 -> "12.5"
  // spaced blocks: how far and which way tree k is from tree k-1 (from START for tree 1), from the plan's own coordinates (Core.distanceM / bearingDeg)
  const legFrom = (block, k) => {
    const cur = block.trees.find((q) => q[0] === k)
    const prev = k > 1 ? block.trees.find((q) => q[0] === k - 1) : null
    const a = prev ? [prev[1], prev[2]] : block.start
    return { k: k - 1, d: Core.distanceM(a[0], a[1], cur[1], cur[2]), deg: Core.bearingDeg(a[0], a[1], cur[1], cur[2]) }
  }
  const freshFix = () => (gps.fix && Date.now() - gps.fix.at < 60000 ? gps.fix : null)
  const activeTree = (block) => (view.tree !== null && Core.treeOf(block, view.tree) ? view.tree : Core.nextTarget(block, state))
  const dirWord = (deg) => t('dir_' + Core.compassPoint(deg))
  // a distance with its unit, never more exact than how sure the phone is: "about 45 m" / "mga 45 m"
  function distText(d, acc) {
    const dl = Core.distanceLabel(d, acc)
    return dl.step > 1 ? (dl.value === 0 ? t('lessThanM', { d: dl.step }) : t('aboutM', { d: dl.value })) : t('exactM', { d: dl.value })
  }

  // ------------------------------------------------------------------ text size: five levels, the whole interface follows (rem units and the variable --ui); the phone's own font size is respected (the base is 100%)
  const UI_LEVELS = [0.85, 1, 1.15, 1.3, 1.5]
  const sizeIndex = () => (Number.isInteger(prefs.size) && prefs.size >= 0 && prefs.size < UI_LEVELS.length ? prefs.size : 1)
  const uiScale = () => UI_LEVELS[sizeIndex()]
  const markScale = () => Math.min(uiScale(), 1.3) // the numbered trees on the map grow a little less than the text
  function applySize() {
    document.documentElement.style.setProperty('--ui', String(uiScale()))
    document.documentElement.dataset.ui = String(Math.round(uiScale() * 100))
    for (const b of document.querySelectorAll('[data-size]')) b.disabled = (b.dataset.size === '-1' && sizeIndex() === 0) || (b.dataset.size === '1' && sizeIndex() === UI_LEVELS.length - 1)
    for (const e of document.querySelectorAll('[data-size-now]')) e.textContent = t('sizeNow', { p: Math.round(uiScale() * 100) })
  }
  function setSize(delta) {
    const i = Math.max(0, Math.min(UI_LEVELS.length - 1, sizeIndex() + delta))
    if (i === sizeIndex()) return
    prefs.size = i
    savePrefs()
    applySize()
    if (map) { refreshMarkers(); layoutMap(); applyRotation() }
    measureTour()
  }
  const sizeBtn = (delta) => h('button', { type: 'button', class: 'btn sizebtn', 'data-size': String(delta), 'aria-label': t(delta < 0 ? 'sizeSmallerLabel' : 'sizeBiggerLabel'), title: t(delta < 0 ? 'sizeSmallerLabel' : 'sizeBiggerLabel'), onclick: () => setSize(delta) }, t(delta < 0 ? 'sizeSmaller' : 'sizeBigger'))
  const helpButton = () => h('button', { type: 'button', class: 'btn helpbtn', 'aria-label': t('helpTitle'), onclick: () => showHelp() }, t('helpBtn'))
  const toolbox = () => h('div', { class: 'toolbox', 'data-tour': 'toolbox' }, sizeBtn(-1), sizeBtn(1), helpButton())

  // ------------------------------------------------------------------ the prototype notice: a strip that can be made small (a "Prototype" chip that opens it again); always written into the results file
  const bannerEl = document.getElementById('banner')
  const bannerText = document.getElementById('bannertext')
  const closeBtn = document.getElementById('bannerclose')
  const chipBtn = document.getElementById('bannerchip')
  let bannerOff = false
  try { bannerOff = window.sessionStorage.getItem('fieldpack_banner_off') === '1' } catch (e) { /* storage refused: the notice just shows */ }
  function setBanner(off) {
    bannerOff = off
    try { window.sessionStorage.setItem('fieldpack_banner_off', off ? '1' : '0') } catch (e) { /* ignore */ }
    paintBanner()
  }
  function paintBanner() { // expanded strip, or a small chip (on the block screen the chip sits on the map)
    const inBlock = document.body.classList.contains('in-block')
    bannerEl.classList.toggle('is-chip', bannerOff)
    bannerEl.hidden = bannerOff && inBlock
    if (ui.protoChip) ui.protoChip.hidden = !(bannerOff && inBlock)
    if (ui.stage) ui.stage.classList.toggle('chip-on', bannerOff && inBlock)
  }
  closeBtn.addEventListener('click', () => setBanner(true))
  chipBtn.addEventListener('click', () => setBanner(false))
  function paintStatic() { // the words of the strip and the page title, in the language in use
    document.documentElement.lang = lang === 'fil' ? 'fil' : 'en'
    bannerText.textContent = t('banner')
    closeBtn.setAttribute('aria-label', t('bannerHide'))
    closeBtn.setAttribute('title', t('bannerHide'))
    chipBtn.setAttribute('aria-label', t('bannerShow'))
    chipBtn.setAttribute('title', t('bannerShow'))
    chipBtn.querySelector('.pill').textContent = t('bannerChip')
    document.title = t('title') + ' ' + pack.plan_id
    paintBanner()
  }

  // ------------------------------------------------------------------ keep the screen awake while a block is open (fails silently when the phone cannot)
  async function requestWake() {
    wake.want = true
    try {
      if (!navigator.wakeLock || wake.sentinel) return
      const s = await navigator.wakeLock.request('screen')
      wake.sentinel = s
      if (s && s.addEventListener) s.addEventListener('release', () => { if (wake.sentinel === s) wake.sentinel = null })
    } catch (e) { /* not allowed, not supported, battery saver: carry on without */ }
  }
  function releaseWake() {
    wake.want = false
    const s = wake.sentinel
    wake.sentinel = null
    try { if (s && s.release) Promise.resolve(s.release()).catch(() => {}) } catch (e) { /* ignore */ }
  }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && wake.want && !wake.sentinel) requestWake() })

  // ------------------------------------------------------------------ GPS
  const GPS_TEXT = { none: 'gpsNone', insecure: 'gpsInsecure', denied: 'gpsDenied', timeout: 'gpsTimeout', unavailable: 'gpsUnavailable' }
  function gpsProblem() { // '' when the phone and the page can use GPS, else why not
    if (!('geolocation' in navigator)) return 'none'
    if (window.isSecureContext === false) return 'insecure'
    return ''
  }
  function gpsFail(reason) {
    gps.status = 'error'
    gps.reason = reason
    gps.error = t(GPS_TEXT[reason] || 'gpsUnavailable')
    updateAll()
  }
  function startGps() {
    startCompass() // first: iOS only asks for the compass inside a tap
    requestWake()
    const p = gpsProblem()
    if (p) return gpsFail(p)
    if (gps.id !== null) return
    gps.status = 'waiting'
    gps.reason = ''
    updateAll()
    gps.id = navigator.geolocation.watchPosition(
      (pos) => {
        const c = pos.coords
        gps.fix = { lat: c.latitude, lon: c.longitude, acc: Number.isFinite(c.accuracy) ? c.accuracy : null, at: Date.now() }
        gps.status = 'ok'
        gps.reason = ''
        if (Number.isFinite(c.heading) && Number.isFinite(c.speed) && c.speed >= 1) {
          hdg.gps = { deg: c.heading, speed: c.speed, at: Date.now() }
          onHeadingSample('gps', c.heading)
        }
        updateAll()
      },
      (err) => gpsFail(err && err.code === 1 ? 'denied' : err && err.code === 3 ? 'timeout' : 'unavailable'),
      { enableHighAccuracy: true, maximumAge: 1000, timeout: 20000 },
    )
  }
  function stopGps() {
    if (gps.id !== null && navigator.geolocation) navigator.geolocation.clearWatch(gps.id)
    gps.id = null
    gps.status = 'off'
    gps.error = ''
    gps.reason = ''
    gps.fix = null
    updateAll()
  }
  // "Continue without GPS": the page keeps working with the tape measure and the steps (row and spot from the plan). Not saved: the GPS bar brings GPS back at any time, and a reload starts fresh.
  function setNoGps() {
    stopGps()
    gps.status = 'nogps'
    view.gpsOpen = false
    updateAll()
  }
  function retryGps() {
    stopGps()
    view.gpsOpen = false
    startGps()
  }

  // ------------------------------------------------------------------ heading: compass, GPS heading, smoothing
  const screenAngle = () => {
    try { return (window.screen && window.screen.orientation && window.screen.orientation.angle) || window.orientation || 0 } catch (e) { return 0 }
  }
  function onOrient(e) {
    const deg = Core.headingFromEvent(e, screenAngle())
    if (deg === null) return
    hdg.compass.deg = deg
    hdg.compass.at = Date.now()
    hdg.compass.status = 'ok'
    onHeadingSample('compass', deg)
  }
  async function startCompass() {
    if (hdg.compass.listening) return
    hdg.compass.listening = true
    let refused = false
    // The listeners are attached at once (Android needs no permission, and asking can never switch the sensor off). Only iOS asks, and only inside a tap.
    window.addEventListener('deviceorientationabsolute', onOrient, true)
    window.addEventListener('deviceorientation', onOrient, true)
    hdg.compass.status = 'waiting'
    try {
      if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
        refused = (await DeviceOrientationEvent.requestPermission()) !== 'granted'
      }
    } catch (e) {
      refused = true
    }
    if (hdg.compass.status !== 'ok') hdg.compass.status = refused ? 'denied' : 'waiting'
    if (!refused) setTimeout(() => { if (hdg.compass.status === 'waiting') { hdg.compass.status = 'none'; updateAll() } }, 3500)
    updateAll()
  }
  function stopCompass() {
    window.removeEventListener('deviceorientationabsolute', onOrient, true)
    window.removeEventListener('deviceorientation', onOrient, true)
    hdg.compass = { deg: null, at: 0, status: 'off', listening: false }
    hdg.gps = { deg: null, speed: 0, at: 0 }
    hdg.smooth = null
    hdg.source = 'none'
    hdg.raw = []
  }
  function chooseHeading() {
    const n = Date.now()
    if (hdg.compass.deg !== null && n - hdg.compass.at < 2500) return 'compass'
    if (hdg.gps.deg !== null && n - hdg.gps.at < 6000 && hdg.gps.speed >= 1) return 'gps'
    return 'none'
  }
  function onHeadingSample(source, raw) {
    const chosen = chooseHeading()
    if (chosen !== hdg.source) { hdg.source = chosen; hdg.smooth = null; hdg.raw = []; updateSheet() }
    if (chosen !== source) return // a lower-priority source while a better one is live
    hdg.raw.push(raw)
    if (hdg.raw.length > 12) hdg.raw.shift()
    hdg.smooth = Core.smoothAngle(hdg.smooth, raw, source === 'compass' ? 0.25 : 0.5)
    if (!hdg.paintQueued) {
      hdg.paintQueued = true
      requestAnimationFrame(() => { hdg.paintQueued = false; paintHeading() })
    }
  }
  // a source that went quiet is dropped at once (not at the next tick): the arrow never shows a stale heading
  const headingNow = () => { const c = chooseHeading(); return c !== 'none' && c === hdg.source && hdg.smooth !== null ? { deg: hdg.smooth, source: c } : null }
  function headingTick() { // twice a second: sources that went quiet are dropped
    const chosen = chooseHeading()
    if (chosen !== hdg.source) { hdg.source = chosen; hdg.smooth = null; hdg.raw = [] }
    if (chosen === 'none' && mapState.rotate) setRotate(false)
    updateSheet()
    paintHeading()
  }

  // ------------------------------------------------------------------ the target: the START corner in step 1, the chosen tree (the next one, or the one tapped) from step 2 on
  function curTarget(block) {
    if (view.step === 1) return { kind: 'start', name: t('startLabel'), lat: block.start[0], lon: block.start[1] }
    const k = activeTree(block)
    if (k === null) return null
    const tr = Core.treeOf(block, k)
    return { kind: 'tree', k, name: t('treeName', { k }), lat: tr[1], lon: tr[2] }
  }
  const targetStatus = (block, tg, d, acc) => (tg.kind === 'start' ? Core.startStatus(d, acc) : Core.treeStatus(d, block.spacing_m))
  const statusWord = (st) => t(st === 'here' ? 'tgtHere' : st === 'close' ? 'tgtClose' : 'tgtFar')

  // ------------------------------------------------------------------ steps of a block
  const stepOf = (block) => {
    const s = prefs.steps && prefs.steps[block.ref]
    if (s >= 1 && s <= 4) return s
    const p = Core.progress(block, state)
    return p.planted + p.skipped > 0 ? 3 : 1
  }
  function setStep(n) {
    view.step = Math.max(1, Math.min(4, n))
    view.skipOpen = false
    if (view.ref) { prefs.steps = prefs.steps || {}; prefs.steps[view.ref] = view.step; savePrefs() }
    if (view.step === 4) view.tree = null
    updateAll()
    refreshChips()
    refreshMarkers()
    drawMini()
    if (map) ensureTargetShown()
  }

  // ------------------------------------------------------------------ recording
  function selectTree(k) {
    view.tree = k
    view.skipOpen = false
    refreshAll()
    ensureTargetVisible(k)
  }
  function record(block, k, rec) {
    state.trees[Core.key(block, k)] = Object.assign({ t: nowIso() }, rec)
    view.tree = null
    view.skipOpen = false
    if (!save()) alert(t('storageFail'))
    if (view.step === 3 && Core.nextTarget(block, state) === null) setStep(4)
    refreshAll()
    ensureTargetVisible(activeTree(block))
  }
  function markPlanted(block, k) {
    const fix = freshFix() // the position of the phone is kept as a note; the tape sets the real spot, so nothing here blocks the tap
    record(block, k, fix ? { s: 'planted', lat: fix.lat, lon: fix.lon, acc: fix.acc } : { s: 'planted' })
  }
  const markSkipped = (block, k, reason) => record(block, k, { s: 'skipped', reason })
  function undo(block, k) {
    delete state.trees[Core.key(block, k)]
    save()
    view.tree = k
    refreshAll()
  }

  // ------------------------------------------------------------------ the map (Leaflet, inlined). The map tiles are the ONLY thing this page fetches from the network.
  function treeIcon(block, tr, active) {
    const r = state.trees[Core.key(block, tr[0])]
    const cls = 'treeicon ' + (r ? (r.s === 'planted' ? 'st-planted' : 'st-skipped') : 'st-todo') + (active ? ' st-active' : '')
    const size = Math.round((active ? 38 : 28) * markScale())
    const el = h('div', { class: cls, 'data-k': tr[0], 'data-lat': tr[1], 'data-lon': tr[2], style: `font-size:${Math.round((active ? 15 : 13) * markScale())}px` }, String(tr[0]))
    return L.divIcon({ className: '', html: el, iconSize: [size, size], iconAnchor: [size / 2, size / 2] })
  }
  function startIcon() {
    const s = markScale()
    return L.divIcon({ className: '', html: h('div', { class: 'starticon', style: `font-size:${Math.round(13 * s)}px;line-height:${Math.round(24 * s)}px` }, t('startLabel')), iconSize: [Math.round(60 * s), Math.round(26 * s)], iconAnchor: [Math.round(62 * s), Math.round(28 * s)] })
  }
  function userIcon() {
    const path = svgEl('path', { d: Core.conePath(40, 40, 38, 28), fill: 'rgba(0,51,204,0.38)', stroke: '#0033cc', 'stroke-width': 1.5 })
    const cone = svgEl('g', { class: 'cone' }, path)
    cone.style.display = 'none'
    const dot = svgEl('circle', { cx: 40, cy: 40, r: 9, fill: '#0033cc', stroke: '#fff', 'stroke-width': 3, class: 'dot' })
    ui.cone = cone
    ui.conePath = path
    ui.coneHalf = 28
    return L.divIcon({ className: '', html: h('div', { class: 'me' }, svgEl('svg', { viewBox: '0 0 80 80', 'aria-hidden': 'true' }, cone, dot)), iconSize: [80, 80], iconAnchor: [40, 40] })
  }
  function setAttribution(def) {
    if (!ui.attrib) return
    const doc = new DOMParser().parseFromString(def.attribution || '', 'text/html')
    for (const a of doc.querySelectorAll('a')) { a.setAttribute('target', '_blank'); a.setAttribute('rel', 'noopener') }
    ui.attrib.replaceChildren(h('a', { href: 'https://leafletjs.com', target: '_blank', rel: 'noopener' }, 'Leaflet'), ' | ', ...doc.body.childNodes)
  }
  function updateNoBase() {
    if (!ui.nobase) return
    ui.nobase.hidden = !(navigator.onLine === false || (mapState.bad >= 3 && mapState.ok === 0))
  }
  function setBase(id) {
    const def = (pack.basemaps || []).find((b) => b.id === id)
    if (!def || !map) return
    if (ml.base) map.removeLayer(ml.base)
    mapState.base = id
    mapState.ok = 0
    mapState.bad = 0
    ml.base = L.tileLayer(def.url, { maxNativeZoom: def.maxNativeZoom, maxZoom: 22, referrerPolicy: 'strict-origin-when-cross-origin', keepBuffer: 1 })
    ml.base.on('tileload', () => { mapState.ok++; updateNoBase() })
    ml.base.on('tileerror', () => { mapState.bad++; updateNoBase() })
    ml.base.addTo(map)
    ml.base.bringToBack()
    setAttribution(def)
    updateNoBase()
  }
  // The map container is the stage, or - in heading-up mode - a bigger square turned by the heading about the point that stays put on the screen (the middle of the part the sheet does not cover).
  function layoutMap() {
    if (!map || !ui.maprot || !ui.stage) return
    const W = ui.stage.clientWidth, H = ui.stage.clientHeight
    const sheetH = ui.sheet ? ui.sheet.offsetHeight : 0
    if (ui.attrib) ui.attrib.style.bottom = sheetH + 'px' // the credit sits right on top of the sheet, never under it
    const el = ui.maprot
    if (mapState.rotate) {
      const px = W / 2, py = Math.max(60, (H - sheetH) / 2)
      const far = Math.max(Math.hypot(px, py), Math.hypot(W - px, py), Math.hypot(px, H - py), Math.hypot(W - px, H - py))
      const D = Math.ceil(far) * 2 + 8
      Object.assign(el.style, { width: D + 'px', height: D + 'px', left: px - D / 2 + 'px', top: py - D / 2 + 'px' })
    } else {
      Object.assign(el.style, { width: '100%', height: '100%', left: '0px', top: '0px', transform: 'none' })
      el.style.setProperty('--maprot', '0deg')
    }
    map.invalidateSize({ animate: false })
  }
  function applyRotation() {
    if (!ui.maprot) return
    const hs = headingNow()
    if (mapState.rotate && hs) {
      const theta = -hs.deg
      ui.maprot.style.transform = `rotate(${theta.toFixed(2)}deg)`
      ui.maprot.style.setProperty('--maprot', `${theta.toFixed(2)}deg`)
      ui.maprot.dataset.rot = theta.toFixed(1)
    } else delete ui.maprot.dataset.rot
  }
  // put a place at the middle of the part of the stage the sheet does not cover
  function centreOn(ll, zoom) {
    if (!map) return
    const z = zoom === undefined ? map.getZoom() : zoom
    if (mapState.rotate) return map.setView(ll, z, { animate: false })
    const sheetH = ui.sheet ? ui.sheet.offsetHeight : 0
    map.setView(map.unproject(map.project(ll, z).add([0, sheetH / 2]), z), z, { animate: false })
  }
  function setFollow(on) {
    ui.userMoved = true
    mapState.follow = on
    if (!on && mapState.rotate) setRotate(false)
    syncButtons()
    const fix = freshFix()
    if (on && fix) centreOn([fix.lat, fix.lon])
  }
  function setRotate(on) {
    if (on && !headingNow()) { ui.note = t('rotateNeedsHeading'); updateSheet(); return }
    ui.note = ''
    mapState.rotate = on
    if (map) {
      map.dragging[on ? 'disable' : 'enable']()
      map.options.touchZoom = on ? 'center' : true
    }
    if (on) mapState.follow = true
    layoutMap()
    applyRotation()
    const fix = freshFix()
    if (fix && (on || mapState.follow)) centreOn([fix.lat, fix.lon])
    syncButtons()
    updateSheet()
  }
  function syncButtons() {
    if (!ui.btnFollow) return
    ui.btnFollow.setAttribute('aria-pressed', String(mapState.follow))
    ui.btnFollow.setAttribute('aria-label', t(mapState.follow ? 'mapFollowOn' : 'mapFollowOff'))
    ui.btnFollow.title = ui.btnFollow.getAttribute('aria-label')
    ui.btnRotate.setAttribute('aria-pressed', String(mapState.rotate))
    ui.btnRotate.setAttribute('aria-label', t(mapState.rotate ? 'mapHeadingUp' : 'mapNorthUp'))
    ui.btnRotate.title = ui.btnRotate.getAttribute('aria-label')
    if (ui.btnBase) {
      ui.btnBase.setAttribute('aria-label', t(mapState.base === 'sat' ? 'mapBaseSat' : 'mapBaseOsm'))
      ui.btnBase.title = ui.btnBase.getAttribute('aria-label')
    }
  }
  // keep a place inside the part of the map that the sheet, the round buttons and the little drawing do not cover
  function ensureVisible(ll) {
    if (!map || mapState.rotate) return
    const pt = map.latLngToContainerPoint(ll)
    const size = map.getSize()
    const sheetH = ui.sheet ? ui.sheet.offsetHeight : 0
    const minX = 28, maxX = size.x - 84, minY = 28, maxY = size.y - sheetH - 32
    const dx = pt.x < minX ? pt.x - minX : pt.x > maxX ? pt.x - maxX : 0
    const dy = pt.y < minY ? pt.y - minY : pt.y > maxY ? pt.y - maxY : 0
    if (dx || dy) map.panBy([dx, dy], { animate: true })
  }
  function ensureTargetVisible(k) {
    if (k === null || k === undefined) return
    const tr = Core.treeOf(blockOf(view.ref), k)
    if (tr) ensureVisible([tr[1], tr[2]])
  }
  function ensureTargetShown() {
    const tg = curTarget(blockOf(view.ref))
    if (tg) ensureVisible([tg.lat, tg.lon])
  }
  function fitBlock(block) {
    const sheetH = ui.sheet ? ui.sheet.offsetHeight : 0
    map.fitBounds(ml.area.getBounds(), { paddingTopLeft: [24, 24], paddingBottomRight: [84, sheetH + 24], maxZoom: 20, animate: false })
  }
  function refreshMarkers() {
    if (!map) return
    const block = blockOf(view.ref)
    const k = activeTree(block)
    for (const tr of block.trees) {
      const m = ml.markers[tr[0]]
      if (!m) continue
      m.setIcon(treeIcon(block, tr, view.step >= 2 && tr[0] === k))
      m.setZIndexOffset(tr[0] === k ? 1000 : 0)
    }
    if (ml.start) ml.start.setIcon(startIcon())
  }
  function destroyMap() {
    for (const [type, fn] of handlers) window.removeEventListener(type, fn)
    handlers = []
    if (ui.observer) ui.observer.disconnect()
    if (map) map.remove()
    map = null
    for (const key of Object.keys(ml)) delete ml[key]
    ml.markers = {}
  }
  function initMap(block) {
    if (!ui.mapEl || typeof L === 'undefined') return
    try {
      map = L.map(ui.mapEl, { zoomControl: false, attributionControl: false, maxZoom: 22, zoomSnap: 0.5, doubleClickZoom: false })
      L.polygon(block.square, { color: '#000', weight: 2, fill: false, dashArray: '2 6' }).addTo(map)
      if (block.layout === 'spaced') { // the shape the user selected in the dashboard (dashed) and the plantable ground of this block, not a square
        if (pack.area && pack.area.selected) for (const ring of pack.area.selected) L.polygon(ring, { color: '#1f6fb2', weight: 2, fill: false, dashArray: '6 6', interactive: false, className: 'tour-shape' }).addTo(map)
        const rings = block.areas && block.areas.length ? block.areas : [block.square]
        ml.area = L.featureGroup(rings.map((ring) => L.polygon(ring, { color: '#1f2a24', weight: 2, fillColor: '#1d5f2c', fillOpacity: 0.14, interactive: false, className: 'tour-ground' }))).addTo(map)
      } else ml.area = L.polygon(block.area, { color: '#000', weight: 3, fillColor: '#000', fillOpacity: 0.08, className: 'tour-ground' }).addTo(map)
      ml.start = L.marker(block.start, { icon: startIcon(), keyboard: false, interactive: false, zIndexOffset: 800 }).addTo(map)
      const k = activeTree(block)
      for (const tr of block.trees) {
        const m = L.marker([tr[1], tr[2]], { icon: treeIcon(block, tr, view.step >= 2 && tr[0] === k), keyboard: false, zIndexOffset: tr[0] === k ? 1000 : 0 })
        m.on('click', () => { if (view.step < 3) setStep(3); selectTree(tr[0]) })
        m.addTo(map)
        ml.markers[tr[0]] = m
      }
      setBase((pack.basemaps || []).some((b) => b.id === mapState.base) ? mapState.base : 'osm')
      layoutMap()
      if (mapState.view && mapState.ref === block.ref) map.setView(mapState.view.center, mapState.view.zoom, { animate: false })
      else fitBlock(block)
      map.on('moveend', () => { mapState.view = { center: map.getCenter(), zoom: map.getZoom() }; mapState.ref = block.ref })
      map.on('dragstart', () => { ui.userMoved = true; if (mapState.follow) setFollow(false) })
      for (const type of ['online', 'offline']) { handlers.push([type, updateNoBase]); window.addEventListener(type, updateNoBase) }
      if (typeof ResizeObserver !== 'undefined') {
        ui.observer = new ResizeObserver(() => { if (map) { layoutMap(); applyRotation() } })
        ui.observer.observe(ui.stage)
        ui.observer.observe(ui.sheet)
      }
      syncButtons()
      updateMap()
    } catch (e) {
      destroyMap()
    }
  }
  function updateMap() {
    if (!map) return
    const block = blockOf(view.ref)
    const fix = freshFix()
    for (const key of ['acc', 'line', 'label']) {
      if (ml[key]) { map.removeLayer(ml[key]); ml[key] = null }
    }
    if (!fix) {
      if (ml.user) { map.removeLayer(ml.user); ml.user = null }
      return
    }
    const here = [fix.lat, fix.lon]
    if (Number.isFinite(fix.acc)) ml.acc = L.circle(here, { radius: fix.acc, color: '#0033cc', weight: 2, dashArray: '4 4', fillColor: '#0033cc', fillOpacity: 0.12, interactive: false }).addTo(map)
    if (!ml.user) ml.user = L.marker(here, { icon: userIcon(), interactive: false, keyboard: false, zIndexOffset: 900 }).addTo(map)
    else ml.user.setLatLng(here)
    const tg = curTarget(block)
    if (tg) { // the dashed line goes to the target: START in step 1, the chosen tree after that (until the phone says it is there)
      const d = Core.distanceM(fix.lat, fix.lon, tg.lat, tg.lon)
      if (targetStatus(block, tg, d, fix.acc) !== 'here') {
        ml.line = L.polyline([here, [tg.lat, tg.lon]], { color: '#0033cc', weight: 4, dashArray: '8 8', interactive: false }).addTo(map)
        const mid = [(fix.lat + tg.lat) / 2, (fix.lon + tg.lon) / 2]
        ml.label = L.marker(mid, { icon: L.divIcon({ className: '', html: h('div', { class: 'linelabel' }, t('mapLine', { d: distText(d, fix.acc), name: tg.name })), iconSize: [0, 0], iconAnchor: [0, 0] }), interactive: false, keyboard: false }).addTo(map)
      }
    }
    paintHeading()
    if (mapState.follow) centreOn(here)
  }

  // the cone, the cue and the map turn follow the heading (also called many times a second by the compass)
  function paintHeading() {
    const hs = headingNow()
    if (ui.cone) {
      if (hs) {
        const half = Core.coneHalfAngle(hs.source, Core.circularStd(hdg.raw), hdg.gps.speed)
        ui.cone.style.display = ''
        ui.cone.style.transform = `rotate(${hs.deg.toFixed(1)}deg)`
        ui.cone.dataset.hdg = hs.deg.toFixed(1)
        ui.cone.dataset.source = hs.source
        if (half !== null && Math.abs(half - ui.coneHalf) > 1) { ui.coneHalf = half; ui.conePath.setAttribute('d', Core.conePath(40, 40, 38, half)) }
        ui.cone.dataset.half = String(ui.coneHalf)
      } else ui.cone.style.display = 'none'
    }
    applyRotation()
    updateTarget()
  }

  // ------------------------------------------------------------------ the little drawing of the block (steps 3 and 4): trees done and the next one. Only the trees' own places from the plan are used.
  function drawMini() {
    if (!ui.mini) return
    const block = blockOf(view.ref)
    ui.mini.hidden = view.step < 3
    if (view.step < 3) return
    const k = activeTree(block)
    const f = block.first_offset_m
    const sx = block.trees[0][3] - f[0], sy = block.trees[0][4] - f[1] // the START corner in metres from the south-west corner of the 100 m square
    const spaced = block.layout === 'spaced'
    const w = block.per_row * block.spacing_m, hh = block.rows * block.spacing_m
    const svg = svgEl('svg', { viewBox: '-4 -10 108 112', role: 'img', 'aria-label': t('miniLabel') })
    svg.append(svgEl('rect', { x: 0, y: 0, width: 100, height: 100, fill: '#fff', stroke: '#000', 'stroke-width': 1 }))
    if (spaced) for (const ring of block.region_m || []) svg.append(svgEl('polygon', { points: ring.map((q) => q[0] + ',' + (100 - q[1])).join(' '), fill: '#eee', stroke: '#000', 'stroke-width': 1.2, 'stroke-dasharray': '3 2' }))
    else svg.append(svgEl('rect', { x: sx, y: 100 - sy - hh, width: w, height: hh, fill: '#eee', stroke: '#000', 'stroke-width': 1.2, 'stroke-dasharray': '3 2' }))
    const rad = Math.max(2.2, Math.min(5, block.spacing_m * 0.3))
    for (const tr of block.trees) {
      const r = state.trees[Core.key(block, tr[0])]
      const next = tr[0] === k && !r
      svg.append(svgEl('circle', { cx: tr[3], cy: 100 - tr[4], r: next ? rad + 1.8 : rad, fill: r ? (r.s === 'planted' ? '#006400' : '#8b0000') : next ? '#ffe14d' : '#fff', stroke: next ? '#0033cc' : '#000', 'stroke-width': next ? 2.4 : 0.9 }))
    }
    svg.append(svgEl('rect', { x: sx - 2.5, y: 100 - sy - 2.5, width: 5, height: 5, fill: '#000' }))
    const label = svgEl('text', { x: sx + 5, y: 100 - sy + 9, 'font-size': 8, 'font-weight': 700, fill: '#000' })
    label.textContent = t('startLabel')
    svg.append(label)
    ui.miniSvg.replaceChildren(svg)
    ui.mini.setAttribute('title', k === null ? t('miniDone') : t('miniNext', { k }))
  }

  // ------------------------------------------------------------------ the bottom panel: collapsed (one thin bar), normal (one step) or expanded (Details). The state is remembered while the page is open.
  let sheetState = 'normal'
  try { const s = window.sessionStorage.getItem('fieldpack_sheet'); if (s === 'collapsed' || s === 'normal' || s === 'expanded') sheetState = s } catch (e) { /* storage refused: the panel starts normal */ }
  function setSheet(next, remember) {
    sheetState = next
    if (remember !== false) { try { window.sessionStorage.setItem('fieldpack_sheet', next) } catch (e) { /* ignore */ } }
    applySheet()
    if (map) requestAnimationFrame(() => { layoutMap(); applyRotation(); ensureTargetShown() })
  }
  function applySheet() {
    if (!ui.sheet) return
    const col = sheetState === 'collapsed', exp = sheetState === 'expanded'
    ui.sheet.dataset.state = sheetState
    ui.sheet.dataset.gps = view.gpsOpen ? 'open' : ''
    ui.body.hidden = col
    ui.sum.hidden = !col
    ui.grabText.hidden = col
    ui.btnDetails.hidden = col
    ui.btnDetails.textContent = t(exp ? 'detailsHide' : 'detailsTitle')
    ui.btnDetails.setAttribute('aria-expanded', String(exp))
    ui.details.hidden = !exp
    ui.btnChev.replaceChildren(icon(sheetState === 'normal' ? 'chevDown' : col ? 'chevUp' : 'chevDown'))
    const label = t(col ? 'sheetOpen' : exp ? 'sheetCloseDetails' : 'sheetClose')
    ui.btnChev.setAttribute('aria-label', label)
    ui.btnChev.setAttribute('title', label)
    ui.btnChev.setAttribute('aria-expanded', String(!col))
    updateSheet()
  }
  const toggleSheet = () => setSheet(sheetState === 'normal' ? 'collapsed' : 'normal')
  function grabDown(e) {
    if (e.target.closest('button')) return
    ui.drag = { y: e.clientY }
    try { ui.grab.setPointerCapture(e.pointerId) } catch (er) { /* not every browser lets us */ }
  }
  function grabUp(e) { // a tap (little movement) toggles the panel; a drag up opens one more state, a drag down closes one
    const d = ui.drag
    ui.drag = null
    if (!d) return
    const dy = e.clientY - d.y
    if (Math.abs(dy) < 12) return toggleSheet()
    if (dy < 0) setSheet(sheetState === 'collapsed' ? 'normal' : 'expanded')
    else setSheet(sheetState === 'expanded' ? 'normal' : 'collapsed')
  }

  // the arrow, the distance and the word for the target; the turn cue; the one line about how sure the phone is
  function updateTarget() {
    if (!ui.arrow) return
    const block = blockOf(view.ref)
    const tg = curTarget(block)
    const fix = freshFix()
    const hs = headingNow()
    ui.target.hidden = !tg || (view.step >= 3 && view.skipOpen) || view.gpsOpen
    ui.cue.hidden = true
    ui.cue.textContent = ''
    ui.dirline.hidden = true
    ui.sureline.hidden = true
    ui.approx.hidden = !(view.step >= 2 && tg)
    ui.sum.textContent = tg ? tg.name : ''
    if (!tg) return
    ui.tgtline.textContent = t('tgtNone', { name: tg.name })
    ui.arrow.toggleAttribute('hidden', !fix)
    if (!fix) { // no GPS reading: no arrow and no distance; the row and the spot of the tree (from the plan) and the tape measure take over
      if (tg.kind === 'tree') {
        if (block.layout === 'spaced') { const leg = legFrom(block, tg.k); ui.tgtline.textContent = t('tgtNoGpsSp', { name: tg.name, d: num(leg.d), dir: dirWord(leg.deg), from: leg.k === 0 ? t('startLabel') : t('treeWord') + ' ' + leg.k }) }
        else { const rp = Core.rowPlace(tg.k, block.per_row); ui.tgtline.textContent = t('tgtNoGps', { name: tg.name, r: rp.row, c: rp.place }) }
        if (gps.status === 'nogps') { ui.sureline.textContent = t('noGpsTip'); ui.sureline.hidden = false; ui.approx.hidden = true }
      }
      return
    }
    const d = Core.distanceM(fix.lat, fix.lon, tg.lat, tg.lon)
    const b = Core.bearingDeg(fix.lat, fix.lon, tg.lat, tg.lon)
    const st = targetStatus(block, tg, d, fix.acc)
    const dist = distText(d, fix.acc)
    ui.tgtline.textContent = t('tgtLine', { name: tg.name, d: dist, word: statusWord(st) })
    ui.target.dataset.status = st
    ui.sum.textContent = tg.name + ' · ' + dist
    // the arrow: up = the way you face when the phone knows it, otherwise it points the way the map points (north up)
    const c = hs ? Core.relativeCue(b, hs.deg) : null
    const rot = hs ? c.turn : b
    ui.arrowG.setAttribute('transform', `rotate(${rot.toFixed(1)} 12 12)`)
    ui.arrow.dataset.mode = hs ? 'heading' : 'north'
    ui.arrow.dataset.deg = String(Math.round(rot))
    ui.arrow.dataset.target = tg.kind === 'start' ? 'start' : String(tg.k)
    ui.arrow.setAttribute('aria-label', t('tgtAria', { name: tg.name }))
    if (st !== 'here') {
      if (c) {
        ui.cue.hidden = false
        ui.cue.textContent = c.kind === 'ahead' ? t('cueAhead') : c.kind === 'around' ? t('cueAround') : t(c.kind === 'left' ? 'cueLeft' : 'cueRight', { deg: c.deg })
        ui.cue.dataset.kind = c.kind
        ui.cue.dataset.turn = String(Math.round(c.turn))
      } else {
        ui.dirline.hidden = false
        ui.dirline.textContent = t('dirLine', { dir: dirWord(b) })
      }
    }
    // honest and short: when the phone is less sure than the distances that matter, say so once, and point to the tape measure (the arrow stays)
    const known = Number.isFinite(fix.acc)
    const limit = tg.kind === 'tree' ? block.spacing_m : 10
    const sure = !known ? t('sureUnknown') : fix.acc > limit ? t('notSure', { m: Math.round(fix.acc) }) : ''
    ui.sureline.textContent = sure
    ui.sureline.hidden = sure === ''
    if (sure !== '') ui.approx.hidden = true
  }
  function refreshChips() {
    if (!ui.chips) return
    const block = blockOf(view.ref)
    const k = activeTree(block)
    ui.chips.hidden = view.step !== 4
    ui.chips.replaceChildren(...clean(block.trees.map((tr) => {
      const r = state.trees[Core.key(block, tr[0])]
      return h('button', { type: 'button', class: `chip ${r ? r.s : 'todo'}${tr[0] === k ? ' active' : ''}`, 'data-k': tr[0], 'aria-pressed': String(tr[0] === k), onclick: () => selectTree(tr[0]),
        'aria-label': t('treeAria', { k: tr[0], state: !r ? t('stateTodo') : r.s === 'planted' ? t('recPlanted') : t('recSkipped', { reason: t('reason_' + r.reason) }) }) }, String(tr[0]))
    })))
    const a = ui.chips.querySelector('.chip.active')
    if (a) ui.chips.scrollLeft = Math.max(0, a.offsetLeft - (ui.chips.clientWidth - a.offsetWidth) / 2)
  }
  function updateTopbar() {
    if (!ui.done) return
    const p = Core.progress(blockOf(view.ref), state)
    ui.done.textContent = t('topDone', { n: p.planted + p.skipped, total: p.n })
  }
  function updateSheet() {
    if (!ui.sheet) return
    const block = blockOf(view.ref)
    const step = view.step
    const k = activeTree(block)
    const fix = freshFix()
    const rec = k === null ? null : state.trees[Core.key(block, k)]
    const hs = headingNow()
    const off = block.first_offset_m
    const sp = block.spacing_m
    const gpsOn = gps.status === 'ok' || gps.status === 'waiting'
    const col = sheetState === 'collapsed'
    ui.stepLabel.textContent = t('stepOf', { n: step })
    ui.btnPrev.disabled = step === 1
    ui.btnNext.disabled = step === 4
    ui.title.textContent = t('s' + step + 'Title')
    ui.dots.setAttribute('aria-label', t('stepOf', { n: step }))
    ui.dots.setAttribute('title', t('stepOf', { n: step }))
    for (const [i, d] of ui.dotEls.entries()) d.classList.toggle('on', i + 1 === step)
    // the ONE instruction of the step, with the real numbers of this block (the paces and the rest are under Details)
    const finished = k === null
    let text = ''
    if (step === 1) text = gps.status === 'nogps' ? t('s1NoGps') : gpsOn ? t('s1Text') : t('s1Off')
    const spaced = block.layout === 'spaced'
    const first = spaced && block.trees.length ? legFrom(block, 1) : null
    if (step === 2) text = spaced ? t('s2TextSp', { d: num(first ? first.d : 0), dir: first ? dirWord(first.deg) : '' }) : t('s2Text', { a: num(off[0]), b: num(off[1]) })
    if (step === 3 && !finished) {
      const leg = spaced ? legFrom(block, k) : null
      const rp = spaced ? { row: 0, place: 0 } : Core.rowPlace(k, block.per_row)
      if (spaced) text = t('s3Sp', { k, d: num(leg.d), dir: dirWord(leg.deg), from: leg.k === 0 ? t('startLabel') : t('treeWord') + ' ' + leg.k, m: num(block.spacing_m) })
      else text = rp.row === 1 && rp.place === 1 ? t('s3First', { a: num(off[0]), b: num(off[1]) }) : rp.place > 1 ? t('s3Walk', { s: num(sp), p: Core.paces(sp), k }) : t('s3Row', { r: rp.row, s: num(sp), j: k - block.per_row, k })
    }
    if (step === 4) { const p = Core.progress(block, state); text = t('s4Text', { p: p.planted, s: p.skipped, l: p.todo }) }
    ui.text.textContent = text
    ui.text.hidden = text === '' || (step >= 3 && (finished || view.skipOpen)) || view.gpsOpen
    // messages: a GPS problem, the compass note, a short wait
    let msg = '', cls = ''
    if (gps.status === 'error') { msg = gps.error; cls = 'warn' }
    else if (gps.status === 'waiting' && !fix) msg = t('s1Wait')
    else if (gps.status === 'ok' && !fix) { msg = t('fixOld'); cls = 'warn' }
    if (ui.note) { msg = ui.note; cls = 'warn' }
    ui.status.textContent = msg
    ui.status.className = 'msg ' + cls
    ui.status.hidden = msg === '' || view.gpsOpen
    ui.errRow.hidden = !(gps.status === 'error' && step >= 2 && !view.gpsOpen)
    updateGpsBar()
    // the buttons: ONE big primary button for the step
    const marking = step >= 3
    const noGps = gps.status === 'off' || gps.status === 'error'
    ui.btnPrimary.textContent = step === 1 ? t(noGps ? (gps.status === 'error' ? 'gpsRetry' : 'gpsStart') : 's1Go') : step === 2 ? t('s2Next') : t('btnPlanted')
    ui.btnPrimary.dataset.act = step === 1 ? (noGps ? 'gps' : 'next') : step === 2 ? 'next' : 'planted'
    ui.btnPrimary.hidden = marking && finished
    ui.btnSkip.textContent = t(marking ? (rec ? 'btnUndo' : 'btnSkip') : 'skipGps')
    ui.btnSkip.dataset.act = marking ? (rec ? 'undo' : 'skip') : 'nogps'
    ui.btnSkip.hidden = marking ? finished : !(step === 1 && noGps)
    ui.btnrow.hidden = col || (marking && !finished && view.skipOpen) || view.gpsOpen || (ui.btnPrimary.hidden && ui.btnSkip.hidden)
    ui.reasons.hidden = !(marking && !finished && view.skipOpen) || view.gpsOpen
    ui.chips.hidden = step !== 4 || view.gpsOpen
    ui.blockDone.hidden = !(marking && finished) || view.gpsOpen
    // the target (arrow, distance, word)
    updateTarget()
    // Details (expanded panel)
    ui.paces.textContent = spaced ? t('detPacesSp', { s: num(sp), sp: Core.paces(sp) }) : t('detPaces', { p: Core.paces(off[0]), q: Core.paces(off[1]), s: num(sp), sp: Core.paces(sp), n: block.per_row })
    const tg = curTarget(block)
    ui.coords.textContent = tg ? t('targetCoords', { lat: fmt(tg.lat), lon: fmt(tg.lon) }) : ''
    ui.hdgLine.textContent = hs ? t(hs.source === 'compass' ? 'headingCompass' : 'headingGps') : t('headingNone')
    ui.hdgNote.textContent = hs ? (hs.source === 'gps' ? t('headingGpsNote') : '') : t('headingGpsNote')
    ui.hint.hidden = !(hs && hs.source === 'compass')
    ui.btnCompass.hidden = hdg.compass.status === 'ok'
    ui.compassMsg.textContent = hdg.compass.status === 'none' ? t('compassNone') : hdg.compass.status === 'denied' ? t('compassDenied') : ''
    ui.btnStop.hidden = !(gps.status === 'ok' || gps.status === 'waiting')
    ui.fileNote.hidden = location.protocol !== 'file:'
    ui.stage.classList.toggle('has-mini', step >= 3)
  }
  // the GPS bar: one small line that says how the GPS is and opens the way to fix it or to go on without it
  function gpsBarKey() {
    const st = gps.status
    if (st === 'ok') return freshFix() ? 'gpsBarOk' : 'gpsBarWait'
    if (st === 'waiting') return 'gpsBarWait'
    if (st === 'nogps') return 'gpsBarNone'
    if (st === 'error') return gps.reason === 'denied' ? 'gpsBarBlocked' : 'gpsBarProblem'
    return 'gpsBarOff'
  }
  function updateGpsBar() {
    if (!ui.gpsbar) return
    ui.gpsbar.textContent = t(gpsBarKey()) + ' \u203a'
    ui.gpsbar.dataset.state = gps.status === 'ok' && !freshFix() ? 'waiting' : gps.status
    ui.gpsbar.setAttribute('aria-expanded', String(view.gpsOpen))
    ui.gpsbar.setAttribute('aria-label', t(gpsBarKey()) + '. ' + t('gpsBarLabel'))
    ui.gpsPanel.hidden = !view.gpsOpen
    ui.sheet.dataset.gps = view.gpsOpen ? 'open' : ''
    if (!view.gpsOpen) return
    const st = gps.status
    const msgKey = st === 'ok' ? 'gpsMsgOk' : st === 'waiting' ? 'gpsMsgWait' : st === 'nogps' ? 'gpsMsgNoGps' : st === 'error' ? (gps.reason === 'denied' ? 'gpsMsgDenied' : gps.reason === 'timeout' ? 'gpsMsgTimeout' : gps.reason === 'none' ? 'gpsMsgNone' : 'gpsMsgProblem') : 'gpsMsgOff'
    ui.gpsMsg.textContent = t(msgKey)
    ui.gpsAllow.hidden = !(st === 'error' && gps.reason === 'denied')
    ui.btnGpsTry.textContent = t(st === 'off' ? 'gpsStart' : st === 'nogps' ? 'gpsUse' : 'gpsAgain')
    ui.btnGpsTry.hidden = st === 'ok'
    ui.btnGpsNone.hidden = st === 'nogps'
  }
  function updateAll() {
    if (view.screen !== 'block') return
    updateTopbar()
    updateSheet()
    updateMap()
  }
  function refreshAll() {
    refreshChips()
    refreshMarkers()
    drawMini()
    updateAll()
  }

  function primaryAction(block) {
    if (view.step === 1) {
      if (gps.status === 'off' || gps.status === 'error') return retryGps()
      return setStep(2)
    }
    if (view.step === 2) return setStep(3)
    const k = activeTree(block)
    if (k !== null) markPlanted(block, k)
  }

  function blockScreen(block) {
    for (const key of Object.keys(ui)) delete ui[key]
    ui.note = ''
    ui.attrib = h('div', { class: 'attrib' })
    // the handle: a drag handle, the step dots, the collapsed summary, Details and the chevron
    ui.dotEls = [1, 2, 3, 4].map(() => h('span', { class: 'dot' }))
    ui.dots = h('span', { class: 'dots', role: 'img' }, ui.dotEls)
    ui.title = h('h2', { class: 'steptitle' })
    ui.grabText = h('div', { class: 'grabtext' }, ui.title, ui.dots)
    ui.sum = h('span', { class: 'sum' })
    ui.btnDetails = h('button', { type: 'button', class: 'btn detailsbtn', 'aria-expanded': 'false', onclick: () => setSheet(sheetState === 'expanded' ? 'normal' : 'expanded') }, t('detailsTitle'))
    ui.btnChev = h('button', { type: 'button', class: 'btn chevbtn', 'aria-expanded': 'true', onclick: () => { if (sheetState === 'expanded') setSheet('normal'); else toggleSheet() } })
    ui.grab = h('div', { class: 'grab', 'aria-label': t('grabLabel'), title: t('grabLabel'), onpointerdown: grabDown, onpointerup: grabUp, onpointercancel: () => { ui.drag = null } },
      h('span', { class: 'pill', 'aria-hidden': 'true' }), h('div', { class: 'grabrow' }, ui.grabText, ui.sum, ui.btnDetails, ui.btnChev))
    ui.stepLabel = h('span', { class: 'steplabel', 'aria-live': 'polite' })
    ui.btnPrev = h('button', { type: 'button', class: 'btn arrow', 'aria-label': t('stepPrev'), title: t('stepPrev'), onclick: () => setStep(view.step - 1) }, '‹')
    ui.btnNext = h('button', { type: 'button', class: 'btn arrow', 'aria-label': t('stepNextBtn'), title: t('stepNextBtn'), onclick: () => setStep(view.step + 1) }, '›')
    ui.stepnav = h('div', { class: 'stepnav' }, ui.btnPrev, ui.stepLabel, ui.btnNext)
    ui.text = h('p', { class: 'steptext' })
    // the target: an arrow, then "Tree 3 · about 12 m · Close", then the turn cue (or the direction in words) and one line about how sure the phone is
    ui.arrowG = svgEl('g', null, svgEl('path', { d: 'M12 2.5 L19.5 14 H14.5 V21.5 H9.5 V14 H4.5 Z', fill: 'currentColor', stroke: '#fff', 'stroke-width': 1, 'stroke-linejoin': 'round' }))
    ui.arrow = svgEl('svg', { class: 'tgtarrow', viewBox: '0 0 24 24', role: 'img' }, ui.arrowG)
    ui.arrow.setAttribute('hidden', '')
    ui.tgtline = h('p', { class: 'tgtline', 'aria-live': 'polite' })
    ui.cue = h('p', { class: 'cue', hidden: true, 'aria-live': 'polite' })
    ui.dirline = h('p', { class: 'dirline', hidden: true })
    ui.sureline = h('p', { class: 'sureline', hidden: true })
    ui.approx = h('p', { class: 'note approx', hidden: true }, t('approxShort'))
    ui.target = h('div', { class: 'target', hidden: true }, h('div', { class: 'tgtrow' }, ui.arrow, h('div', { class: 'tgttext' }, ui.tgtline, ui.cue, ui.dirline)), ui.sureline, ui.approx)
    ui.status = h('p', { class: 'msg', 'aria-live': 'polite' })
    ui.errRow = h('div', { class: 'errrow', hidden: true }, h('button', { type: 'button', class: 'btn good', onclick: () => retryGps() }, t('gpsAgain')), h('button', { type: 'button', class: 'btn', onclick: () => setNoGps() }, t('gpsContinue')))
    ui.gpsbar = h('button', { type: 'button', class: 'btn gpsbar', 'data-tour': 'gps', 'aria-expanded': 'false', onclick: () => { view.gpsOpen = !view.gpsOpen; updateSheet(); ui.body.scrollTop = 0 } })
    ui.gpsMsg = h('p', { class: 'gpsmsg' })
    ui.gpsAllow = h('div', { hidden: true }, h('p', { class: 'note', style: 'font-weight:700' }, t('gpsAllowTitle')), h('p', { class: 'note' }, t('gpsAllowAndroid')), h('p', { class: 'note' }, t('gpsAllowIphone')))
    ui.btnGpsTry = h('button', { type: 'button', class: 'btn good wide', onclick: () => retryGps() }, t('gpsAgain'))
    ui.btnGpsNone = h('button', { type: 'button', class: 'btn wide', onclick: () => setNoGps() }, t('gpsContinue'))
    ui.gpsPanel = h('div', { class: 'gpspanel', hidden: true }, ui.gpsMsg, ui.btnGpsTry, ui.btnGpsNone, ui.gpsAllow, h('button', { type: 'button', class: 'btn link', onclick: () => { view.gpsOpen = false; updateSheet() } }, t('helpClose')))
    ui.chips = h('div', { class: 'chips', role: 'group', 'aria-label': t('chipsLabel'), hidden: true })
    ui.blockDone = h('p', { class: 'ok', hidden: true }, t('blockDone'))
    ui.btnPrimary = h('button', { type: 'button', class: 'btn good primary', onclick: () => primaryAction(block) }, t('btnPlanted'))
    ui.btnSkip = h('button', { type: 'button', class: 'btn bad secondary', hidden: true, onclick: () => {
      const k = activeTree(block)
      if (ui.btnSkip.dataset.act === 'nogps') return setNoGps()
      if (ui.btnSkip.dataset.act === 'undo') { if (k !== null) undo(block, k); return }
      view.skipOpen = !view.skipOpen
      updateSheet()
    } }, t('btnSkip'))
    ui.btnrow = h('div', { class: 'btnrow', 'data-tour': 'buttons' }, ui.btnPrimary, ui.btnSkip)
    ui.reasons = h('div', { hidden: true }, h('p', { class: 'steptext' }, t('skipWhy')),
      h('div', { class: 'reasons' }, Core.REASONS.map((r) => h('button', { type: 'button', class: 'btn', onclick: () => { const k = activeTree(block); if (k !== null) markSkipped(block, k, r) } }, t('reason_' + r)))),
      h('p', { class: 'note' }, t('s4Blocked')),
      h('button', { type: 'button', class: 'btn link', onclick: () => { view.skipOpen = false; updateSheet() } }, t('skipCancel')))
    // Details: the step arrows, the paces, the place of the tree, how sure the phone is, the heading, the compass button, the legend, the honest lines, how the block is laid out
    ui.paces = h('p', { class: 'note' })
    ui.coords = h('p', { class: 'note' })
    ui.hdgLine = h('p', { class: 'note', style: 'font-weight:700' })
    ui.hdgNote = h('p', { class: 'note' })
    ui.hint = h('p', { class: 'note', hidden: true }, t('headingHint'))
    ui.btnCompass = h('button', { type: 'button', class: 'btn', onclick: () => startCompass() }, t('compassStart'))
    ui.compassMsg = h('p', { class: 'note' })
    ui.fileNote = h('p', { class: 'note', hidden: true }, t('gpsFile'))
    ui.btnStop = h('button', { type: 'button', class: 'btn link', hidden: true, onclick: () => setNoGps() }, t('gpsStop'))
    ui.details = h('div', { class: 'inner', hidden: true }, ui.stepnav, ui.paces, ui.coords, h('p', { class: 'note' }, t('approxMap')), ui.hdgLine, ui.hdgNote, ui.hint, ui.btnCompass, ui.compassMsg, ui.fileNote,
      h('p', { class: 'note' }, t('mapLegend')), h('p', { class: 'note' }, t('mapHonest')), h('p', { class: 'note' }, t('s4Blocked')), h('p', { class: 'note' }, t('banner')),
      h('h3', null, t('layoutTitle')), h('p', { class: 'note', style: 'font-weight:700' }, `${block.ref} · ${block.name}`), h('p', { class: 'note' }, block.layout === 'spaced' ? t('blockLineSp', { n: block.n, sp: num(block.spacing_m) }) : t('blockLine', { n: block.n, sp: num(block.spacing_m), rows: block.rows, per: block.per_row })),
      block.layout === 'spaced' && block.fits === false ? h('p', { class: 'warn', role: 'status' }, t('fitShort', { p: block.n, n: block.requested })) : null,
      h('p', { class: 'note' }, block.layout === 'spaced' ? t('orderLineSp') : t('orderLine')), h('p', { class: 'note' }, t('startLine', { lat: fmt(block.start[0]), lon: fmt(block.start[1]) })), block.note ? h('p', { class: 'note' }, block.note) : null, ui.btnStop)
    ui.body = h('div', { class: 'sheetbody' }, ui.gpsbar, ui.gpsPanel, ui.text, ui.target, ui.status, ui.errRow, ui.chips, ui.blockDone, ui.reasons, ui.details)
    ui.sheet = h('section', { class: 'sheet', 'data-tour': 'sheet', 'aria-label': t('sheetLabel') }, ui.grab, ui.body, ui.btnrow)
    // the round buttons on the map
    const rbtn = (name, label, fn, pressed, tourId) => h('button', { type: 'button', class: 'rbtn', 'data-tour': tourId, 'aria-label': label, title: label, 'aria-pressed': pressed, onclick: fn }, icon(name))
    ui.btnMe = rbtn('locate', t('mapMe'), () => {
      ui.userMoved = true
      const fix = freshFix()
      ui.note = fix ? '' : t('mapNoFix')
      if (fix && map) centreOn([fix.lat, fix.lon], Math.max(map.getZoom(), 19))
      updateSheet()
    }, null, 'me')
    ui.btnFollow = rbtn('follow', t('mapFollowOff'), () => setFollow(!mapState.follow), 'false')
    ui.btnRotate = rbtn('rotate', t('mapNorthUp'), () => setRotate(!mapState.rotate), 'false', 'rotate')
    ui.btnBase = (pack.basemaps || []).length > 1 ? rbtn('layers', t('mapBaseOsm'), () => { const defs = pack.basemaps; setBase(defs[(defs.findIndex((d) => d.id === mapState.base) + 1) % defs.length].id); syncButtons() }) : null
    ui.mapEl = h('div', { id: 'map', class: 'map', role: 'application', 'aria-label': t('mapLabel') })
    ui.maprot = h('div', { id: 'maprot' }, ui.mapEl)
    ui.nobase = h('div', { class: 'nobase', role: 'status', hidden: true }, t('mapNoBase'))
    ui.miniSvg = h('div', { class: 'minisvg' })
    ui.mini = h('div', { class: 'mini', hidden: true }, ui.miniSvg)
    ui.protoChip = h('button', { type: 'button', class: 'protochip', hidden: true, 'aria-label': t('bannerShow'), title: t('bannerShow'), onclick: () => setBanner(false) }, h('span', { class: 'pill' }, t('bannerChip')))
    ui.stage = h('div', { class: 'stage' + (ui.btnBase ? ' has-layers' : '') }, ui.maprot, ui.nobase, ui.attrib, ui.protoChip, ui.mini,
      h('div', { class: 'mapbtns' }, h('div', { class: 'mcol' }, ui.btnMe, ui.btnFollow, ui.btnRotate, ui.btnBase),
        h('div', { class: 'mcol' }, rbtn('zoomin', t('mapZoomIn'), () => { ui.userMoved = true; if (map) map.zoomIn() }), rbtn('zoomout', t('mapZoomOut'), () => { ui.userMoved = true; if (map) map.zoomOut() }))), ui.sheet)
    ui.done = h('span', { class: 'done' })
    return h('div', { style: 'display:flex;flex-direction:column;flex:1;min-height:0' },
      h('div', { class: 'topbar' }, h('button', { type: 'button', class: 'btn', 'aria-label': t('backLabel'), onclick: leaveBlock }, t('back')), h('div', { class: 'ttl' }, h('span', { class: 'ttl1', title: block.name }, block.ref), ui.done), toolbox()),
      ui.stage)
  }

  function leaveBlock() {
    closeTour(false)
    stopGps()
    stopCompass()
    releaseWake()
    if (timer) clearInterval(timer)
    timer = null
    destroyMap()
    view.screen = 'home'
    view.ref = null
    view.tree = null
    view.skipOpen = false
    view.gpsOpen = false
    render()
  }

  // ------------------------------------------------------------------ results
  function exportFile() {
    if (!(state.observer || '').trim()) return alert(t('needName'))
    const text = '﻿' + Core.exportCsv(pack, state, nowIso(), STRINGS.en.banner + ' (pack ' + pack.pack_id + ')')
    return { blob: new Blob([text], { type: 'text/csv;charset=utf-8' }), name: `results_${pack.plan_id}_${pack.check_code}.csv` }
  }
  function download() {
    const f = exportFile()
    if (!f) return
    const a = h('a', { href: URL.createObjectURL(f.blob), download: f.name })
    document.body.append(a)
    a.click()
    a.remove()
  }
  async function share() {
    const f = exportFile()
    if (!f) return
    const file = new File([f.blob], f.name, { type: 'text/csv' })
    try {
      if (navigator.canShare && navigator.canShare({ files: [file] })) await navigator.share({ files: [file], title: f.name })
      else alert(t('shareNone'))
    } catch (e) { /* the person closed the share sheet */ }
  }

  // ------------------------------------------------------------------ the guided tour: a spotlight on the real element, a short card (title, text, step dots, Back / Next / Skip). Same look and flow as the tour of the main dashboard,
  // written again here in plain JavaScript (this page stays one self-contained file). A step whose element is not on the screen is skipped. It runs by itself the first time for each screen.
  const TOURS = {
    landing: [
      { id: 'l1', title: 'tl1Title', text: 'tl1', targets: ['[data-tour="l-title"]'] },
      { id: 'l2', title: 'tl2Title', text: 'tl2', targets: ['[data-tour="l-how"]'] },
      { id: 'l3', title: 'tl3Title', text: 'tl3', targets: ['[data-tour="l-start"]'] },
      { id: 'l4', title: 'tl4Title', text: 'tl4', targets: ['[data-tour="toolbox"]'] },
    ],
    home: [
      { id: 'h1', title: 'th1Title', text: 'th1', targets: ['[data-tour="h-blocks"]'] },
      { id: 'h2', title: 'th2Title', text: 'th2', targets: ['#observer'] },
      { id: 'h3', title: 'th3Title', text: 'th3', targets: ['[data-tour="h-results"]'] },
    ],
    block: [
      { id: 'b1', title: 'tb1Title', text: 'tb1', targets: ['#map'], before: () => tourSheet('collapsed', true) },
      { id: 'b11', title: 'tb11Title', text: 'tb11', targets: ['.tour-shape', '.tour-ground'], before: () => tourSheet('collapsed', true) },
      { id: 'b2', title: 'tb2Title', text: 'tb2', targets: ['.me .dot', '[data-tour="me"]'], before: () => tourSheet('collapsed') },
      { id: 'b3', title: 'tb3Title', text: 'tb3', targets: ['.me .cone', '[data-tour="rotate"]'], before: () => tourSheet('collapsed') },
      { id: 'b4', title: 'tb4Title', text: 'tb4', targets: ['.starticon'], before: () => tourSheet('collapsed', true) },
      { id: 'b5', title: 'tb5Title', text: 'tb5', targets: ['.treeicon.st-active', '.treeicon'], before: () => tourSheet('collapsed') },
      { id: 'b12', title: 'tb12Title', text: 'tb12', targets: ['[data-tour="sheet"]'], before: () => tourSheet('normal') },
      { id: 'b6', title: 'tb6Title', text: 'tb6', targets: ['[data-tour="sheet"]'], before: () => tourSheet('normal') },
      { id: 'b7', title: 'tb7Title', text: 'tb7', targets: ['[data-tour="buttons"]'], before: () => tourSheet('normal') },
      { id: 'b9', title: 'tb9Title', text: 'tb9', targets: ['[data-tour="gps"]'], before: () => tourSheet('normal') },
      { id: 'b10', title: 'tb10Title', text: 'tb10', targets: ['.detailsbtn'], before: () => tourSheet('normal') },
      { id: 'b8', title: 'tb8Title', text: 'tb8', targets: ['.topbar [data-tour="toolbox"]'] },
    ],
  }
  function tourSheet(state2, refit) { // the panel is opened or closed for a step (and put back when the tour ends)
    if (view.screen !== 'block' || !ui.sheet) return
    if (sheetState !== state2) setSheet(state2, false)
    if (refit && map && ml.area) requestAnimationFrame(() => { if (map && ml.area) { layoutMap(); fitBlock(blockOf(view.ref)) } })
  }
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x))
  // an element counts as shown when it is on the screen, not hidden, and not under the panel, the round buttons or the top bar (map markers cannot be hit-tested, so those are tested by their position)
  function isShown(el) {
    if (!el || !el.isConnected || el.closest('[hidden]')) return false
    const cs = window.getComputedStyle(el)
    if (cs.display === 'none' || cs.visibility === 'hidden') return false
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) return false
    const vw = window.innerWidth, vh = window.innerHeight
    if (r.right <= 0 || r.bottom <= 0 || r.left >= vw || r.top >= vh) return false
    const x = clamp(r.left + r.width / 2, 1, vw - 1), y = clamp(r.top + r.height / 2, 1, vh - 1)
    const inMap = !!el.closest('.leaflet-container')
    if (inMap) {
      if (el.id === 'map' || el.classList.contains('map')) return true
      for (const sel of ['.sheet', '.topbar', '.mapbtns .rbtn', '.mini', '.protochip', '#banner']) {
        for (const o of document.querySelectorAll(sel)) {
          if (o.closest('[hidden]') || !o.getClientRects().length) continue
          const b = o.getBoundingClientRect()
          if (x >= b.left && x <= b.right && y >= b.top && y <= b.bottom) return false
        }
      }
      return true
    }
    const top = document.elementsFromPoint(x, y).find((e) => !e.closest('.tour'))
    return !!top && (top === el || el.contains(top) || top.contains(el))
  }
  function findShown(targets) {
    for (const sel of targets) for (const el of document.querySelectorAll(sel)) if (isShown(el)) return el
    return null
  }
  function startTour(screen) {
    closeOverlay()
    closeTour(false)
    const steps = TOURS[screen]
    if (!steps) return
    // the "seen" flag is set the moment the tour starts (not only when it finishes or Skip is pressed), so a visitor who starts it and then navigates away, presses Back, or
    // switches language mid-tour never has it auto-offered again on this screen; manually re-opening it from Help still works regardless of the flag.
    if (!(prefs.tour && prefs.tour[screen])) { prefs.tour = Object.assign({}, prefs.tour, { [screen]: true }); savePrefs() }
    const tr = { screen, steps, idx: 0, token: 0, el: null, prevSheet: sheetState }
    tr.hole = h('div', { class: 'tour-hole', 'aria-hidden': 'true' })
    tr.count = h('div', { class: 'tour-count' })
    tr.titleEl = h('h3', { class: 'tour-title' })
    tr.textEl = h('p', { class: 'tour-text' })
    tr.dots = h('div', { class: 'tour-dots', 'aria-hidden': 'true' }, steps.map(() => h('span', { class: 'tdot' })))
    tr.btnBack = h('button', { type: 'button', class: 'btn tourbtn', onclick: () => tourGo(-1) }, t('tourBack'))
    tr.btnNext = h('button', { type: 'button', class: 'btn good tourbtn', onclick: () => tourGo(1) }, t('tourNext'))
    tr.btnSkip = h('button', { type: 'button', class: 'btn tourbtn ghost', onclick: () => closeTour(true) }, t('tourSkip'))
    tr.card = h('div', { class: 'tour-card', tabindex: '-1', 'aria-live': 'polite' }, tr.count, tr.titleEl, tr.textEl, tr.dots, h('div', { class: 'tour-btns' }, tr.btnBack, tr.btnNext, tr.btnSkip))
    tr.root = h('div', { class: 'tour', role: 'dialog', 'aria-modal': 'true', 'aria-label': t('tourLabel'), 'data-screen': screen }, tr.hole, tr.card)
    document.body.append(tr.root)
    document.body.classList.add('has-tour')
    tr.timer = setInterval(measureTour, 400)
    tr.onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); closeTour(true) } else if (e.key === 'ArrowRight') tourGo(1)
      else if (e.key === 'ArrowLeft') tourGo(-1)
    }
    window.addEventListener('keydown', tr.onKey)
    window.addEventListener('resize', measureTour)
    tour = tr
    openTourStep(0, 1)
  }
  function tourGo(dir) {
    if (!tour) return
    const next = tour.idx + dir
    if (next < 0) return
    if (next >= tour.steps.length) return closeTour(true)
    openTourStep(next, dir)
  }
  async function openTourStep(i, dir) {
    const tr = tour
    if (!tr) return
    const token = ++tr.token
    const step = tr.steps[i]
    tr.idx = i
    tr.shown = false
    try { if (step.before) step.before() } catch (e) { /* a step that cannot get ready is skipped below */ }
    let el = null
    for (let n = 0; n < 8 && !el; n++) {
      await sleep(n === 0 ? 160 : 110)
      if (tour !== tr || token !== tr.token) return
      for (const sel of step.targets) { // something below the fold is brought into view first
        const first = document.querySelector(sel)
        if (first && !first.closest('.leaflet-container') && !first.closest('[hidden]')) { try { first.scrollIntoView({ block: 'center', inline: 'nearest' }) } catch (e) { /* old browser */ } break }
      }
      el = findShown(step.targets)
    }
    if (tour !== tr || token !== tr.token) return
    if (!el) { // not on the screen: skip this step (forwards, or backwards when going back)
      const nx = i + dir
      if (nx >= tr.steps.length) return closeTour(true)
      if (nx < 0) return openTourStep(i + 1, 1)
      return openTourStep(nx, dir)
    }
    tr.el = el
    tr.shown = true
    tr.count.textContent = t('tourStep', { n: i + 1, total: tr.steps.length })
    tr.titleEl.textContent = t(step.title)
    tr.textEl.textContent = t(step.text)
    for (const [k, d] of [...tr.dots.children].entries()) d.classList.toggle('on', k === i)
    tr.btnBack.disabled = i === 0
    tr.btnNext.textContent = i === tr.steps.length - 1 ? t('tourDone') : t('tourNext')
    tr.card.dataset.stepId = step.id
    tr.card.dataset.target = el.id || el.className && String(el.className.baseVal !== undefined ? el.className.baseVal : el.className).split(' ')[0] || el.tagName
    tr.side = null
    measureTour()
    fitTourTarget(tr)
    measureTour()
    tr.card.focus({ preventScroll: true })
  }
  // the landing page and the block list scroll: put the highlighted thing in the part of the screen the card does not cover
  function fitTourTarget(tr) {
    const sc = document.getElementById('app')
    if (!tr.el || document.body.classList.contains('in-block') || !sc || !sc.contains(tr.el)) return
    const vh = window.innerHeight
    const r = tr.el.getBoundingClientRect()
    const ch = tr.card.getBoundingClientRect().height
    const want = (side) => {
      const band = side === 'at-bottom' ? [8, vh - ch - 12] : [ch + 12, vh - 8]
      const delta = r.height <= band[1] - band[0] ? (band[0] + band[1]) / 2 - (r.top + r.height / 2) : band[0] - r.top
      const room = delta > 0 ? sc.scrollTop : sc.scrollHeight - sc.clientHeight - sc.scrollTop // how far the page can still move that way
      return { side, delta, got: Math.sign(delta) * Math.min(Math.abs(delta), Math.max(0, room)) }
    }
    const a = want('at-bottom'), c = want('at-top')
    const best = Math.abs(a.delta - a.got) <= Math.abs(c.delta - c.got) ? a : c
    sc.scrollTop -= best.got
    tr.side = best.side
  }
  function measureTour() {
    const tr = tour
    if (!tr || !tr.shown || !tr.el || !tr.el.isConnected) return
    const r = tr.el.getBoundingClientRect()
    const vw = window.innerWidth, vh = window.innerHeight
    const big = r.width * r.height > vw * vh * 0.4 // a huge target (the whole map): outline only, no dimming
    const pad = 4
    Object.assign(tr.hole.style, { top: r.top - pad + 'px', left: r.left - pad + 'px', width: r.width + pad * 2 + 'px', height: r.height + pad * 2 + 'px' })
    tr.hole.classList.toggle('is-big', big)
    const overlap = (c) => Math.max(0, Math.min(c.bottom, r.bottom) - Math.max(c.top, r.top)) * Math.max(0, Math.min(c.right, r.right) - Math.max(c.left, r.left))
    const put = (side) => { tr.card.classList.remove('at-top', 'at-bottom'); tr.card.classList.add(side); return big ? 0 : overlap(tr.card.getBoundingClientRect()) }
    const first = tr.side || (r.top + r.height / 2 > vh * 0.45 ? 'at-top' : 'at-bottom')
    const other = first === 'at-top' ? 'at-bottom' : 'at-top'
    let side = first
    const o1 = put(first)
    if (o1 > 0) { // the card would cover the highlighted thing: try the other side and keep the better one
      if (put(other) < o1) side = other
      else put(first)
    }
    tr.side = side
    tr.root.dataset.covers = String(Math.round(big ? 0 : overlap(tr.card.getBoundingClientRect())))
  }
  function closeTour(markDone) {
    const tr = tour
    if (!tr) return
    tour = null
    tr.token++
    clearInterval(tr.timer)
    window.removeEventListener('keydown', tr.onKey)
    window.removeEventListener('resize', measureTour)
    tr.root.remove()
    document.body.classList.remove('has-tour')
    if (markDone) { prefs.tour = Object.assign({}, prefs.tour, { [tr.screen]: true }); savePrefs() }
    if (tr.screen === 'block' && view.screen === 'block' && ui.sheet && sheetState !== tr.prevSheet) setSheet(tr.prevSheet, false)
  }
  function autoTour(screen) { // the first time for each screen
    setTimeout(() => { if (!tour && !overlay && view.screen === screen && !(prefs.tour && prefs.tour[screen])) startTour(screen) }, 350)
  }

  // ------------------------------------------------------------------ language and Help
  function setLang(l) {
    lang = l
    prefs.lang = l
    savePrefs()
    closeTour(false)
    paintStatic()
    const wasHelp = overlay && overlay.dataset.kind === 'help'
    closeOverlay()
    render()
    if (wasHelp) showHelp()
  }
  const langSwitch = () => h('div', { class: 'lang', role: 'group', 'aria-label': t('langLabel') },
    ['fil', 'en'].map((l) => h('button', { type: 'button', class: 'btn langbtn', 'data-lang': l, 'aria-pressed': String(lang === l), onclick: () => { if (lang !== l) setLang(l) } }, t(l === 'fil' ? 'langFil' : 'langEn'))))
  function closeOverlay() {
    if (overlay) overlay.remove()
    overlay = null
    document.body.classList.remove('has-overlay')
  }
  function openOverlay(kind, children) {
    closeTour(false)
    closeOverlay()
    overlay = h('div', { class: 'overlay', role: 'dialog', 'aria-modal': 'true', 'aria-label': t('helpTitle'), 'data-kind': kind }, h('div', { class: 'overlaybox' }, children))
    document.body.append(overlay)
    document.body.classList.add('has-overlay')
    const first = overlay.querySelector('button')
    if (first) first.focus({ preventScroll: true })
  }
  function trouble(titleKey, textKey, extraKey) {
    return h('div', { class: 'trouble' }, h('h3', null, t(titleKey)), h('p', null, t(textKey)), extraKey ? h('p', null, t(extraKey)) : null)
  }
  function showHelp() {
    const screen = view.screen
    openOverlay('help', [
      h('div', { class: 'overlayhead' }, h('h2', null, t('helpTitle')), h('button', { type: 'button', class: 'btn', onclick: closeOverlay }, t('helpClose'))),
      h('button', { type: 'button', class: 'btn good wide', 'data-act': 'tour', onclick: () => { closeOverlay(); startTour(screen) } }, t('helpTour')),
      h('p', { class: 'note' }, t('helpTourText')),
      langSwitch(),
      h('h3', null, t('sizeTitle')), h('div', { class: 'sizerow' }, sizeBtn(-1), sizeBtn(1), h('span', { class: 'sizenow', 'data-size-now': '1' }, t('sizeNow', { p: Math.round(uiScale() * 100) }))),
      h('h3', null, t('howTitle')), h('ol', { class: 'steps' }, [1, 2, 3, 4].map((i) => h('li', null, t('how' + i)))),
      h('h3', null, t('troubleTitle')),
      trouble('tLocTitle', 'tLocAndroid', 'tLocIphone'),
      trouble('tNoSigTitle', 'tNoSig'),
      trouble('tArrowTitle', 'tArrow'),
      trouble('tDieTitle', 'tDie'),
      h('h3', null, t('gpsTruthTitle')), h('p', null, t('gpsPromise')), h('p', null, t('mapHonest')), h('p', null, t('gpsHonest')),
      h('p', { class: 'note' }, t('banner')),
      h('button', { type: 'button', class: 'btn good wide', onclick: closeOverlay }, t('helpClose')),
    ])
    applySize()
  }

  // ------------------------------------------------------------------ landing and home
  function landingScreen() {
    const checks = prefs.checks || {}
    return h('div', null,
      h('div', { class: 'toolrow' }, toolbox()),
      h('h1', { 'data-tour': 'l-title' }, t('title')),
      h('p', { class: 'note', 'data-role': 'who' }, t('landWho')),
      langSwitch(),
      h('h2', null, t('howTitle')),
      h('ol', { class: 'steps', 'data-tour': 'l-how' }, [1, 2, 3, 4].map((i) => h('li', null, t('how' + i)))),
      h('p', { class: 'honest' }, t('gpsPromise')),
      h('h2', null, t('beforeTitle')),
      h('ul', { class: 'checklist' }, [1, 2, 3, 4, 5].map((i) => h('li', null, h('label', { class: 'check' },
        h('input', { type: 'checkbox', checked: checks[i] ? true : null, onchange: (e) => { prefs.checks = Object.assign({}, prefs.checks, { [i]: e.target.checked }); savePrefs() } }), h('span', null, t('before' + i)))))),
      h('button', { type: 'button', class: 'btn good wide big', 'data-tour': 'l-start', onclick: () => { view.screen = 'home'; render() } }, t('start')),
      h('p', { class: 'note' }, t('planLine', { plan: pack.plan_id, code: pack.check_code, pack: pack.pack_id })),
      h('p', { class: 'note' }, t('builtLine', { date: pack.built_on, tag: pack.dataset.tag, hash: pack.dataset.hash })))
  }
  // Texts of the soil pH section (kept here, not in strings.js: they are new and not yet part of the Filipino review file). Same two languages.
  const PH_T = {
    fil: {
      phTitle: 'Bago magtanim: sukatin ang pH',
      phIntro: 'Ang mga pH range sa ibaba ay mula sa sanggunian at hindi pa pirmado ng agriculturist. Sukatin sa mismong lugar.',
      phNone: 'Walang nakumpirmang pH range',
      phNoneList: '{n} species ang walang nakumpirmang pH range: {names}. Itanong sa agriculturist/MAO bago magtanim kung kaduda-duda ang pH.',
      phTol: 'Matitiis',
      phOpt: 'Pinakamainam',
      phListed: 'Nakalista',
      phConflict: 'May magkaibang sanggunian; itanong sa agriculturist',
      phPickLabel: 'Piliin ang species',
      phInputLabel: 'pH na nasukat mo (3.0 hanggang 10.0)',
      phReset: 'I-reset',
      phBad: 'Maglagay ng numero mula 3.0 hanggang 10.0.',
      phCmpOptimal: 'Nasa pinakamainam na saklaw',
      phCmpTolerated: 'Nasa saklaw na matitiis, hindi pinakamainam',
      phCmpListed: 'Nasa saklaw na nakalista',
      phCmpOutside: 'Labas sa saklaw',
      phCmpOutsideOptimal: 'Labas sa pinakamainam na saklaw',
      phCmpNone: 'Walang nakumpirmang pH range',
      phNote: 'Gumamit ng pH test kit o meter sa mismong lugar. Hindi ito sine-save.',
    },
    en: {
      phTitle: 'Before planting: measure the soil pH',
      phIntro: 'Soil pH ranges below come from sources and are not yet signed by the agriculturist. Measure on site.',
      phNone: 'No confirmed pH range',
      phNoneList: '{n} species have no confirmed pH range: {names}. Ask the agriculturist or MAO before planting where the pH is doubtful.',
      phTol: 'Tolerated',
      phOpt: 'Best',
      phListed: 'Listed',
      phConflict: 'Sources disagree; ask the agriculturist',
      phPickLabel: 'Choose species',
      phInputLabel: 'pH you measured (3.0 to 10.0)',
      phReset: 'Clear',
      phBad: 'Enter a number from 3.0 to 10.0.',
      phCmpOptimal: 'Inside the best range',
      phCmpTolerated: 'Inside the tolerated range, not the best',
      phCmpListed: 'Inside the listed range',
      phCmpOutside: 'Outside the range',
      phCmpOutsideOptimal: 'Outside the best range',
      phCmpNone: 'No confirmed pH range',
      phNote: 'Use a pH test kit or meter on the spot. This is not saved.',
    },
  }
  const tp = (id, vars) => {
    let x = (PH_T[lang] || PH_T.fil)[id]
    for (const k in vars || {}) x = x.split('{' + k + '}').join(String(vars[k]))
    return x
  }
  // "Bago magtanim: sukatin ang pH": the soil pH reference of the species in this plan (text from the plan, no network) and the "Sukat sa lugar" check. Nothing is saved.
  const phRange = (a, b) => (a != null && b != null ? a + '–' + b : null)
  function phLine(r) {
    if (r.status !== 'sourced') return tp('phNone')
    const bits = [['phTol', phRange(r.tol_min, r.tol_max)], ['phOpt', phRange(r.opt_min, r.opt_max)], ['phListed', phRange(r.listed_min, r.listed_max)]].filter((x) => x[1]).map((x) => tp(x[0]) + ' ' + x[1])
    return bits.join(' · ') + (r.conflict ? ' · ' + tp('phConflict') : '')
  }
  function phSection() {
    const list = pack.ph || []
    if (!list.length) return null
    const none = list.filter((r) => r.status !== 'sourced')
    const result = h('p', { class: 'note', role: 'status', 'data-role': 'ph-result' })
    const input = h('input', { id: 'ph-input', type: 'text', inputmode: 'decimal', autocomplete: 'off', placeholder: '6.5', 'aria-label': tp('phInputLabel') })
    const pick = h('select', { id: 'ph-species', 'aria-label': tp('phPickLabel') }, list.map((r, i) => h('option', { value: String(i) }, r.name)))
    const update = () => {
      const typed = input.value.trim() !== ''
      const v = Core.parsePh(input.value)
      result.textContent = !typed ? '' : v === null ? tp('phBad') : ({ optimal: tp('phCmpOptimal'), tolerated: tp('phCmpTolerated'), listed: tp('phCmpListed'), outside: tp('phCmpOutside'), outside_optimal: tp('phCmpOutsideOptimal'), none: tp('phCmpNone') })[Core.phCompare(v, list[Number(pick.value)])]
    }
    input.addEventListener('input', update)
    pick.addEventListener('change', update)
    return h('div', { class: 'phbox', 'data-role': 'ph-section' },
      h('h2', null, tp('phTitle')),
      h('p', { class: 'note' }, tp('phIntro')),
      none.length ? h('p', { class: 'warn', 'data-role': 'ph-none-list' }, tp('phNoneList', { n: none.length, names: none.map((r) => r.name).join(', ') })) : null,
      h('ul', { class: 'plain' }, list.map((r) => h('li', null, h('strong', null, r.name), ': ', phLine(r)))),
      h('label', { for: 'ph-species' }, tp('phPickLabel')), pick,
      h('label', { for: 'ph-input' }, tp('phInputLabel')), input,
      h('button', { type: 'button', class: 'btn', onclick: () => { input.value = ''; update() } }, tp('phReset')),
      result,
      h('p', { class: 'note' }, tp('phNote')))
  }
  // "Suriin sa lugar": ten questions the PLANTER answers (Oo / Hindi / Hindi sigurado) with a tip for each answer, its source and quotation. The system checks nothing; the answers stay in this page's memory only
  // (not saved, not in any field check, plan or CSV). The questions, tips and quotations are in pack.checklist (data/reference/site_checklist.csv); only the frame texts are here (like the pH texts, not in strings.js).
  const CL_T = {
    fil: { title: 'Suriin sa lugar', intro: 'Hindi ito sinusuri ng system at hindi bahagi ng score. Para ito sa pagpapasya sa mismong lugar.', source: 'Sanggunian', quote: 'Sipi', scope: 'saklaw', noQuote: 'Walang naberipikang sipi',
      species: 'Mga species sa plano (shade tolerance at light preference mula sa species table, draft)', cond: 'Kondisyon ng zone sa planong ito (mula sa app)', noCond: 'Walang nakalistang kondisyon ng zone sa planong ito.',
      counts: '{oo} Oo, {hindi} Hindi, {hs} hindi sigurado', other: ', {n} iba pang sagot', left: ', {n} hindi pa sinasagot', saved: 'Ang mga sagot ay hindi sine-save.', open: 'buksan ang sanggunian' },
    en: { title: 'Check on site', intro: 'The system does not check this and it is not part of the score. It is for deciding on the spot.', source: 'Source', quote: 'Quotation', scope: 'scope', noQuote: 'No verified quotation',
      species: 'Species in the plan (shade tolerance and light preference from the species table, draft)', cond: 'Zone conditions in this plan (from the app)', noCond: 'No zone condition is listed for this plan.',
      counts: '{oo} Yes, {hindi} No, {hs} not sure', other: ', {n} other answers', left: ', {n} not answered', saved: 'The answers are not saved.', open: 'open the source' },
  }
  const tc = (id, vars) => {
    let x = (CL_T[lang] || CL_T.fil)[id]
    for (const k in vars || {}) x = x.split('{' + k + '}').join(String(vars[k]))
    return x
  }
  const siteAnswers = {}
  function checklistSection() {
    const cl = pack.checklist
    if (!cl || !(cl.items || []).length) return null
    const summary = h('p', { class: 'note', role: 'status', 'data-role': 'cl-counts' })
    const refreshCounts = () => {
      const c = Core.checklistCounts(cl.items, siteAnswers)
      summary.textContent = tc('counts', { oo: c.oo, hindi: c.hindi, hs: c.hindi_sigurado }) + (c.other ? tc('other', { n: c.other }) : '') + (c.unanswered ? tc('left', { n: c.unanswered }) : '')
    }
    const extras = (it) => {
      const out = []
      if (it.id === 'C4' && cl.species.length) out.push(h('div', { class: 'note', 'data-role': 'cl-species' }, h('strong', null, tc('species')),
        h('ul', { class: 'plain' }, cl.species.map((sp) => h('li', null, sp.name + ': ' + [sp.shade_tol ? 'shade ' + sp.shade_tol : '', sp.light_preference].filter(Boolean).join('; '))))))
      if (it.id === 'C8') out.push(h('div', { class: 'note', 'data-role': 'cl-zone' }, h('strong', null, tc('cond')), cl.zone_conditions.length ? h('ul', { class: 'plain' }, cl.zone_conditions.map((z) => h('li', null, z))) : h('p', null, tc('noCond'))))
      return out
    }
    const build = (it) => {
      const chosen = siteAnswers[it.id]
      const t = chosen ? Core.checklistTips(it, chosen, cl.genera) : null
      const src = it.source || {}
      const box = h('fieldset', { class: 'clitem', 'data-item': it.id },
        h('legend', null, it.question),
        h('p', { class: 'note' }, it.why),
        h('div', { class: 'actions' }, it.options.map((o) => h('button', { type: 'button', class: 'btn' + (chosen === o.id ? ' good' : ''), 'aria-pressed': String(chosen === o.id), 'data-option': o.id,
          onclick: () => { siteAnswers[it.id] = o.id; box.replaceWith(build(it)); refreshCounts() } }, o.label))),
        t ? h('p', { class: 'note', role: 'status', 'data-role': 'cl-tip' }, t.tip) : null,
        t && t.genusTip ? h('p', { class: 'warn', 'data-role': 'cl-genus-tip' }, t.genusTip) : null,
        ...extras(it),
        h('p', { class: 'note', 'data-role': 'cl-source' }, tc('source') + ': ' + src.name + ' (' + tc('scope') + ': ' + src.scope + ')', src.url ? [' ', h('a', { href: src.url, target: '_blank', rel: 'noopener noreferrer' }, tc('open'))] : null),
        (src.quotes || []).length ? h('blockquote', { class: 'note', 'data-role': 'cl-quote' }, src.quotes.map((q) => h('p', null, q))) : (src.url ? h('p', { class: 'note', 'data-role': 'cl-noquote' }, tc('noQuote')) : null),
        it.note ? h('p', { class: 'note' }, it.note) : null)
      return box
    }
    refreshCounts()
    return h('div', { class: 'checklist', 'data-role': 'cl-section' },
      h('h2', null, tc('title')),
      h('p', { class: 'note', 'data-role': 'cl-intro' }, tc('intro')),
      cl.items.map(build),
      summary,
      h('p', { class: 'note' }, tc('saved')))
  }
  function homeScreen() {
    const totals = pack.blocks.reduce((s, b) => {
      const p = Core.progress(b, state)
      return { n: s.n + p.n, planted: s.planted + p.planted, skipped: s.skipped + p.skipped }
    }, { n: 0, planted: 0, skipped: 0 })
    return h('div', null,
      h('div', { class: 'toolrow' }, h('button', { type: 'button', class: 'btn', 'aria-label': t('backToIntro'), onclick: () => { view.screen = 'landing'; render() } }, t('back')), toolbox()),
      h('h1', null, t('blocksTitle')),
      store.ok ? null : h('p', { class: 'warn', role: 'alert' }, t('storageWarn')),
      h('label', { for: 'observer' }, t('nameLabel')),
      h('input', { id: 'observer', type: 'text', maxlength: '80', autocomplete: 'name', value: state.observer || '', oninput: (e) => { state.observer = e.target.value; save() } }),
      h('p', { class: 'note' }, t('totalsLine', totals)),
      h('div', { class: 'blocks', 'data-tour': 'h-blocks' }, pack.blocks.map((b) => {
        const p = Core.progress(b, state)
        return h('button', { type: 'button', class: 'bcard', onclick: () => { view.screen = 'block'; view.ref = b.ref; view.tree = null; view.skipOpen = false; view.step = stepOf(b); render() } },
          h('strong', null, b.ref), h('span', null, b.name), h('small', null, t('blockCard', { n: b.n, done: p.planted + p.skipped }) + (b.layout === 'spaced' && b.fits === false ? ' · ' + t('fitShort', { p: b.n, n: b.requested }) : '')),
          h('div', { class: 'bar', role: 'img', 'aria-label': t('blockCard', { n: b.n, done: p.planted + p.skipped }) }, h('span', { class: 'p', style: `width:${(100 * p.planted) / p.n}%` }), h('span', { class: 's', style: `width:${(100 * p.skipped) / p.n}%` })))
      })),
      phSection(),
      checklistSection(),
      h('h2', null, t('resultsTitle')),
      h('p', { class: 'note' }, t('resultsHelp')),
      h('div', { class: 'actions', 'data-tour': 'h-results' }, h('button', { type: 'button', class: 'btn good', onclick: download }, t('btnDownload')), typeof navigator.canShare === 'function' ? h('button', { type: 'button', class: 'btn', onclick: share }, t('btnShare')) : null),
      h('p', { class: 'note' }, t('gpsHonest')),
      h('p', { class: 'note' }, t('banner')),
      langSwitch(),
      h('button', { type: 'button', class: 'btn link', onclick: () => { if (confirm(t('confirmErase'))) { state = Core.emptyState(); save(); render() } } }, t('btnErase')))
  }

  function render() {
    closeTour(false)
    destroyMap()
    const b = view.screen === 'block' ? blockOf(view.ref) : null
    document.body.classList.toggle('in-block', !!b)
    root.replaceChildren(...clean([b ? blockScreen(b) : view.screen === 'home' ? homeScreen() : landingScreen()]))
    applySize()
    if (b) {
      applySheet()
      refreshChips()
      updateTopbar()
      updateSheet()
      drawMini()
      ui.restoring = !!(mapState.view && mapState.ref === b.ref)
      initMap(b)
      if (timer) clearInterval(timer)
      timer = setInterval(headingTick, 500)
      requestAnimationFrame(() => { if (map) { layoutMap(); if (!ui.restoring && !ui.userMoved) fitBlock(b) } })
    }
    paintBanner()
    root.scrollTop = 0
    window.scrollTo(0, 0)
    autoTour(view.screen)
  }

  applySize()
  paintStatic()
  render()
})()
