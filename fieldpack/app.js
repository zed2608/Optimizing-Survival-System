/* Field pack, stage A1d: the page. Plain JavaScript, no framework. Every word the person reads comes from STRINGS (strings.js, one table per language) through t().
 * The plan (blocks, per-tree coordinates) is the JSON element with the id pack-data. Results and settings are kept on this phone only (localStorage, in try/catch).
 * The page's own code never sends anything anywhere; the map tiles are the only network requests (they come from the tile layers in the plan data).
 * Honest by design: phone GPS is 3 to 10 m off and trees are 3 to 20 m apart, so GPS guides the planter to the block's START corner and the tape or paces set each tree.
 * Screens: landing (how to use) -> home (the blocks) -> block (four steps with a map and a bottom sheet). Help and the first-visit intro are overlays. */
(function () {
  'use strict'
  const Core = FieldPackCore
  const pack = JSON.parse(document.getElementById('pack-data').textContent)
  const store = Core.makeStore(() => window.localStorage, `fieldpack:${pack.plan_id}:${pack.check_code}`)
  let state = store.load()
  // settings of the person on this phone (language, intro seen, checklist, step of each block): kept apart from the marks
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
  const view = { screen: 'landing', ref: null, tree: null, skipOpen: false, detailsOpen: false, step: 1 }
  const gps = { id: null, fix: null, status: 'off', error: '' }
  // heading: where the phone / the person faces. Sources in order: the phone's compass, then the GPS heading while walking, else none.
  const hdg = { compass: { deg: null, at: 0, status: 'off', listening: false }, gps: { deg: null, speed: 0, at: 0 }, smooth: null, source: 'none', raw: [], paintQueued: false }
  const mapState = { follow: false, rotate: false, base: 'osm', view: null, ref: null, ok: 0, bad: 0 }
  const ui = {} // the elements of the block screen (made again with the screen)
  const ml = { markers: {} } // the map layers
  let map = null
  let handlers = [] // window listeners to remove when the block screen is left
  let timer = null
  let overlay = null
  const wake = { want: false, sentinel: null }
  const root = document.getElementById('app')

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
    plus: () => [svgEl('path', { d: 'M12 5v14M5 12h14' })],
    minus: () => [svgEl('path', { d: 'M5 12h14' })],
    layers: () => [svgEl('path', { d: 'M12 3l9 5-9 5-9-5zM3 13l9 5 9-5' })],
  }
  const icon = (name) => svgEl('svg', { viewBox: '0 0 24 24', 'aria-hidden': 'true', focusable: 'false' }, ...ICONS[name]())
  const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
  const save = () => store.save(state)
  const blockOf = (ref) => pack.blocks.find((b) => b.ref === ref)
  const fmt = (x) => x.toFixed(6)
  const num = (x) => String(Math.round(x * 100) / 100) // 7 -> "7", 12.5 -> "12.5"
  const freshFix = () => (gps.fix && Date.now() - gps.fix.at < 60000 ? gps.fix : null)
  const activeTree = (block) => (view.tree !== null && Core.treeOf(block, view.tree) ? view.tree : Core.nextTarget(block, state))
  const dirWord = (deg) => t('dir_' + Core.compassPoint(deg))
  // a distance with its unit, never more exact than how sure the phone is: "about 45 m" / "mga 45 m"
  function distText(d, acc) {
    const dl = Core.distanceLabel(d, acc)
    return dl.step > 1 ? (dl.value === 0 ? t('lessThanM', { d: dl.step }) : t('aboutM', { d: dl.value })) : t('exactM', { d: dl.value })
  }

  // ------------------------------------------------------------------ the prototype notice: a thin strip, can be hidden for the session, always written into the results file
  const bannerEl = document.getElementById('banner')
  let bannerOff = false
  try { bannerOff = window.sessionStorage.getItem('fieldpack_banner_off') === '1' } catch (e) { /* storage refused: the notice just shows */ }
  const closeBtn = document.getElementById('bannerclose')
  bannerEl.hidden = bannerOff
  closeBtn.addEventListener('click', () => {
    bannerEl.hidden = true
    bannerOff = true
    try { window.sessionStorage.setItem('fieldpack_banner_off', '1') } catch (e) { /* ignore */ }
  })
  function paintStatic() { // the words of the strip and the page title, in the language in use
    document.documentElement.lang = lang === 'fil' ? 'fil' : 'en'
    document.getElementById('bannertext').textContent = t('banner')
    closeBtn.setAttribute('aria-label', t('bannerClose'))
    closeBtn.setAttribute('title', t('bannerClose'))
    document.title = t('title') + ' ' + pack.plan_id
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
  function gpsProblem() {
    if (!('geolocation' in navigator)) return t('gpsNone')
    if (window.isSecureContext === false) return t('gpsInsecure')
    return ''
  }
  function startGps() {
    startCompass() // first: iOS only asks for the compass inside a tap
    requestWake()
    const p = gpsProblem()
    if (p) {
      gps.status = 'error'
      gps.error = p
      updateAll()
      return
    }
    if (gps.id !== null) return
    gps.status = 'waiting'
    updateAll()
    gps.id = navigator.geolocation.watchPosition(
      (pos) => {
        const c = pos.coords
        gps.fix = { lat: c.latitude, lon: c.longitude, acc: Number.isFinite(c.accuracy) ? c.accuracy : null, at: Date.now() }
        gps.status = 'ok'
        if (Number.isFinite(c.heading) && Number.isFinite(c.speed) && c.speed >= 1) {
          hdg.gps = { deg: c.heading, speed: c.speed, at: Date.now() }
          onHeadingSample('gps', c.heading)
        }
        updateAll()
      },
      (err) => {
        gps.status = 'error'
        gps.error = (err && err.code === 1 ? t('gpsDenied') : err && err.code === 3 ? t('gpsTimeout') : t('gpsUnavailable')) + (location.protocol === 'file:' ? ' ' + t('gpsFile') : '')
        updateAll()
      },
      { enableHighAccuracy: true, maximumAge: 1000, timeout: 20000 },
    )
  }
  function stopGps() {
    if (gps.id !== null && navigator.geolocation) navigator.geolocation.clearWatch(gps.id)
    gps.id = null
    gps.status = 'off'
    gps.error = ''
    gps.fix = null
    updateAll()
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
    if (view.step <= 2 && map) { const b = blockOf(view.ref); ensureStartVisible(b) }
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
    const size = active ? 38 : 28
    const el = h('div', { class: cls, 'data-k': tr[0], 'data-lat': tr[1], 'data-lon': tr[2] }, String(tr[0]))
    return L.divIcon({ className: '', html: el, iconSize: [size, size], iconAnchor: [size / 2, size / 2] })
  }
  function startIcon() {
    return L.divIcon({ className: '', html: h('div', { class: 'starticon' }, t('startLabel')), iconSize: [60, 26], iconAnchor: [62, 28] })
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
  const ensureStartVisible = (block) => ensureVisible(block.start)
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
      m.setIcon(treeIcon(block, tr, view.step >= 3 && tr[0] === k))
      m.setZIndexOffset(tr[0] === k ? 1000 : 0)
    }
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
      ml.area = L.polygon(block.area, { color: '#000', weight: 3, fillColor: '#000', fillOpacity: 0.08 }).addTo(map)
      L.marker(block.start, { icon: startIcon(), keyboard: false, interactive: false, zIndexOffset: 800 }).addTo(map)
      const k = activeTree(block)
      for (const tr of block.trees) {
        const m = L.marker([tr[1], tr[2]], { icon: treeIcon(block, tr, view.step >= 3 && tr[0] === k), keyboard: false, zIndexOffset: tr[0] === k ? 1000 : 0 })
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
    const dStart = Core.distanceM(fix.lat, fix.lon, block.start[0], block.start[1])
    if (view.step <= 2 && Core.startStatus(dStart, fix.acc) !== 'here') { // the line goes to the START corner (until you are there): GPS is only trusted to bring you that close
      const d = dStart
      ml.line = L.polyline([here, block.start], { color: '#0033cc', weight: 4, dashArray: '8 8', interactive: false }).addTo(map)
      const mid = [(fix.lat + block.start[0]) / 2, (fix.lon + block.start[1]) / 2]
      ml.label = L.marker(mid, { icon: L.divIcon({ className: '', html: h('div', { class: 'linelabel' }, t('mapLine', { d: distText(d, fix.acc) })), iconSize: [130, 30], iconAnchor: [65, 15] }), interactive: false, keyboard: false }).addTo(map)
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
    updateCue()
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
    const w = block.per_row * block.spacing_m, hh = block.rows * block.spacing_m
    const svg = svgEl('svg', { viewBox: '-4 -10 108 112', role: 'img', 'aria-label': t('miniLabel') })
    svg.append(svgEl('rect', { x: 0, y: 0, width: 100, height: 100, fill: '#fff', stroke: '#000', 'stroke-width': 1 }))
    svg.append(svgEl('rect', { x: sx, y: 100 - sy - hh, width: w, height: hh, fill: '#eee', stroke: '#000', 'stroke-width': 1.2, 'stroke-dasharray': '3 2' }))
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

  // ------------------------------------------------------------------ the bottom sheet
  function updateCue() {
    if (!ui.cue) return
    const block = blockOf(view.ref)
    const fix = freshFix()
    const hs = headingNow()
    if (view.step !== 1 || !fix || !hs) { ui.cue.hidden = true; ui.cue.textContent = ''; return }
    const c = Core.relativeCue(Core.bearingDeg(fix.lat, fix.lon, block.start[0], block.start[1]), hs.deg)
    ui.cue.hidden = false
    ui.cue.textContent = c.kind === 'ahead' ? t('cueAhead') : c.kind === 'around' ? t('cueAround') : t(c.kind === 'left' ? 'cueLeft' : 'cueRight', { deg: c.deg })
    ui.cue.dataset.kind = c.kind
    ui.cue.dataset.turn = String(Math.round(c.turn))
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
    ui.stepLabel.textContent = t('stepOf', { n: step })
    ui.btnPrev.disabled = step === 1
    ui.btnNext.disabled = step === 4
    ui.title.textContent = t('s' + step + 'Title')
    // the words of the step, with the real numbers of this block
    let text = '', more = ''
    if (step === 1) text = gps.status === 'off' || gps.status === 'error' ? '' : t('s1Text') // before GPS runs the Start GPS button comes first, with room above the main button
    if (step === 2) { text = t('s2Text', { a: num(off[0]), b: num(off[1]), p: Core.paces(off[0]), q: Core.paces(off[1]) }); more = t('s2More') }
    if (step === 3) { text = t('s3Text', { s: num(sp), p: Core.paces(sp), n: block.per_row }); more = t('approxMap') }
    if (step === 4) { const p = Core.progress(block, state); text = t('s4Text', { p: p.planted, s: p.skipped, l: p.todo }); more = t('s4Blocked') }
    ui.text.textContent = text
    ui.text.hidden = text === ''
    ui.more.textContent = more
    ui.more.hidden = more === ''
    // the next tree (step 3)
    const finished = k === null
    ui.nextLine.hidden = step !== 3 || finished
    if (!finished) {
      const rp = Core.rowPlace(k, block.per_row)
      ui.nextLine.textContent = t('s3Next', { k, n: block.n }) + ' · ' + t('s3Row', { r: rp.row, c: rp.place })
    }
    // distance to the START corner, in words (steps 1 to 3): far / close / here
    let msg = '', cls = ''
    ui.startBox.hidden = step === 4
    let distLine = '', dirLine = '', sureLine = ''
    if (fix) {
      const d = Core.distanceM(fix.lat, fix.lon, block.start[0], block.start[1])
      const b = Core.bearingDeg(fix.lat, fix.lon, block.start[0], block.start[1])
      const st = Core.startStatus(d, fix.acc)
      distLine = st === 'here' ? t('s1Here') : t(st === 'close' ? 's1Close' : 's1Far', { d: distText(d, fix.acc) })
      ui.distLine.dataset.status = st
      dirLine = st === 'here' ? '' : t('dirLine', { dir: dirWord(b) })
      const a = Core.arrival(d, fix.acc, sp)
      sureLine = a.accuracyKnown ? t('sureLine', { m: Math.round(fix.acc) }) : t('sureUnknown')
      ui.longAcc.textContent = a.approximate ? (a.accuracyKnown ? t('approxSpacing', { acc: Math.round(fix.acc), sp: num(sp) }) : t('approxUnknown')) : ''
    } else {
      delete ui.distLine.dataset.status
      distLine = gps.status === 'waiting' ? t('s1Wait') : gps.status === 'ok' ? t('fixOld') : step === 1 ? t('s1NoGps') : ''
      ui.longAcc.textContent = gps.status === 'ok' ? t('fixOld') : ''
    }
    ui.distLine.textContent = distLine
    ui.dirLine.textContent = dirLine
    ui.sureLine.textContent = sureLine
    ui.sureLine.hidden = step !== 1
    ui.dirLine.hidden = step !== 1
    ui.distLine.className = 'startline' + (step === 1 && fix ? ' big' : '')
    if (gps.status === 'error') { msg = gps.error; cls = 'warn' }
    if (ui.note) { msg = ui.note; cls = 'warn' }
    ui.status.textContent = msg
    ui.status.className = 'msg ' + cls
    ui.status.hidden = msg === ''
    ui.btnGps.hidden = !((gps.status === 'off' || gps.status === 'error') && step === 1)
    ui.btnGps.textContent = t(gps.status === 'error' ? 'gpsRetry' : 'gpsStart')
    ui.fileNote.hidden = !(location.protocol === 'file:' && gps.status === 'off' && step === 1)
    // the buttons
    const marking = step >= 3
    ui.btnPrimary.textContent = step === 1 ? t('s1Go') : step === 2 ? t('s2Next') : t('btnPlanted')
    ui.btnPrimary.hidden = marking && finished
    ui.btnrow.hidden = marking && !finished && view.skipOpen // while the reasons are open they are the only thing to press
    ui.btnSkip.hidden = !marking || finished
    ui.btnUndo.hidden = !(marking && rec)
    ui.reasons.hidden = !(marking && !finished && view.skipOpen)
    ui.chips.hidden = step !== 4
    ui.blockDone.hidden = !(marking && finished)
    // details
    if (!finished) {
      const tr = Core.treeOf(block, k)
      ui.coords.textContent = t('targetCoords', { lat: fmt(tr[1]), lon: fmt(tr[2]) })
    } else ui.coords.textContent = ''
    ui.hdgLine.textContent = hs ? t(hs.source === 'compass' ? 'headingCompass' : 'headingGps') : t('headingNone')
    ui.hdgNote.textContent = hs ? (hs.source === 'gps' ? t('headingGpsNote') : '') : t('headingGpsNote')
    ui.hint.hidden = !(hs && hs.source === 'compass')
    ui.btnCompass.hidden = hdg.compass.status === 'ok'
    ui.compassMsg.textContent = hdg.compass.status === 'none' ? t('compassNone') : hdg.compass.status === 'denied' ? t('compassDenied') : ''
    ui.btnStop.hidden = gps.status === 'off'
    ui.btnDetails.setAttribute('aria-expanded', String(view.detailsOpen))
    ui.details.hidden = !view.detailsOpen
    ui.stage.classList.toggle('has-mini', step >= 3)
    updateCue()
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

  function blockScreen(block) {
    for (const key of Object.keys(ui)) delete ui[key]
    ui.note = ''
    ui.attrib = h('div', { class: 'attrib' })
    ui.stepLabel = h('span', { class: 'steplabel', 'aria-live': 'polite' })
    ui.btnPrev = h('button', { type: 'button', class: 'btn arrow', 'aria-label': t('stepPrev'), title: t('stepPrev'), onclick: () => setStep(view.step - 1) }, '‹')
    ui.btnNext = h('button', { type: 'button', class: 'btn arrow', 'aria-label': t('stepNextBtn'), title: t('stepNextBtn'), onclick: () => setStep(view.step + 1) }, '›')
    ui.btnDetails = h('button', { type: 'button', class: 'btn detailsbtn', 'aria-expanded': 'false', onclick: () => { view.detailsOpen = !view.detailsOpen; updateSheet() } }, t('detailsTitle'))
    ui.stepnav = h('div', { class: 'stepnav' }, ui.btnPrev, ui.stepLabel, ui.btnNext, ui.btnDetails)
    ui.title = h('h2', { class: 'steptitle' })
    ui.text = h('p', { class: 'steptext' })
    ui.more = h('p', { class: 'note' })
    ui.nextLine = h('p', { class: 'nextline' })
    ui.distLine = h('p', { class: 'startline', 'aria-live': 'polite' })
    ui.dirLine = h('p', { class: 'dirline' })
    ui.cue = h('p', { class: 'cue', hidden: true, 'aria-live': 'polite' })
    ui.sureLine = h('p', { class: 'note' })
    ui.btnGps = h('button', { type: 'button', class: 'btn good wide', onclick: () => { if (gps.status === 'error') stopGps(); startGps() } }, t('gpsStart'))
    ui.startBox = h('div', { class: 'startbox' }, ui.distLine, ui.btnGps, ui.dirLine, ui.cue, ui.sureLine)
    ui.status = h('p', { class: 'msg', 'aria-live': 'polite' })
    ui.fileNote = h('p', { class: 'note', hidden: true }, t('gpsFileMaybe'))
    ui.chips = h('div', { class: 'chips', role: 'group', 'aria-label': t('chipsLabel'), hidden: true })
    ui.blockDone = h('p', { class: 'ok', hidden: true }, t('blockDone'))
    ui.btnPrimary = h('button', { type: 'button', class: 'btn good primary', onclick: () => {
      if (view.step === 1) return setStep(2)
      if (view.step === 2) return setStep(3)
      const k = activeTree(block)
      if (k !== null) markPlanted(block, k)
    } }, t('btnPlanted'))
    ui.btnSkip = h('button', { type: 'button', class: 'btn bad secondary', hidden: true, onclick: () => { view.skipOpen = !view.skipOpen; updateSheet() } }, t('btnSkip'))
    ui.btnUndo = h('button', { type: 'button', class: 'btn secondary', hidden: true, onclick: () => { const k = activeTree(block); if (k !== null) undo(block, k) } }, t('btnUndo'))
    ui.btnrow = h('div', { class: 'btnrow' }, ui.btnPrimary, ui.btnSkip, ui.btnUndo)
    ui.reasons = h('div', { hidden: true }, h('p', { class: 'note' }, t('skipWhy')),
      h('div', { class: 'reasons' }, Core.REASONS.map((r) => h('button', { type: 'button', class: 'btn', onclick: () => { const k = activeTree(block); if (k !== null) markSkipped(block, k, r) } }, t('reason_' + r)))),
      h('p', { class: 'note' }, t('s4Blocked')),
      h('button', { type: 'button', class: 'btn link', onclick: () => { view.skipOpen = false; updateSheet() } }, t('skipCancel')))
    // the collapsed Details: tree position, how sure the phone is, heading source, compass button, legend, the honest line, the notice, how the block is laid out
    ui.coords = h('p', { class: 'note' })
    ui.longAcc = h('p', { class: 'note warn' })
    ui.hdgLine = h('p', { class: 'note', style: 'font-weight:700' })
    ui.hdgNote = h('p', { class: 'note' })
    ui.hint = h('p', { class: 'note', hidden: true }, t('headingHint'))
    ui.btnCompass = h('button', { type: 'button', class: 'btn', onclick: () => startCompass() }, t('compassStart'))
    ui.compassMsg = h('p', { class: 'note' })
    ui.btnStop = h('button', { type: 'button', class: 'btn link', hidden: true, onclick: () => stopGps() }, t('gpsStop'))
    ui.details = h('div', { class: 'inner', hidden: true }, ui.coords, ui.longAcc, ui.hdgLine, ui.hdgNote, ui.hint, ui.btnCompass, ui.compassMsg,
      h('p', { class: 'note' }, t('mapLegend')), h('p', { class: 'note' }, t('mapHonest')), h('p', { class: 'note' }, t('banner') + ' ' + t('bannerAgain')),
      h('h3', null, t('layoutTitle')), h('p', { class: 'note' }, t('blockLine', { n: block.n, sp: num(block.spacing_m), rows: block.rows, per: block.per_row })),
      h('p', { class: 'note' }, t('orderLine')), h('p', { class: 'note' }, t('startLine', { lat: fmt(block.start[0]), lon: fmt(block.start[1]) })), block.note ? h('p', { class: 'note' }, block.note) : null, ui.btnStop)
    ui.sheet = h('section', { class: 'sheet', 'aria-label': t('sheetLabel') },
      ui.stepnav, ui.title, ui.nextLine, ui.text, ui.more, ui.startBox, ui.status, ui.fileNote, ui.chips, ui.blockDone, ui.reasons, ui.btnrow, ui.details)
    // the round buttons on the map
    const rbtn = (name, label, fn, pressed) => h('button', { type: 'button', class: 'rbtn', 'aria-label': label, title: label, 'aria-pressed': pressed, onclick: fn }, icon(name))
    ui.btnMe = rbtn('locate', t('mapMe'), () => {
      ui.userMoved = true
      const fix = freshFix()
      ui.note = fix ? '' : t('mapNoFix')
      if (fix && map) centreOn([fix.lat, fix.lon], Math.max(map.getZoom(), 19))
      updateSheet()
    })
    ui.btnFollow = rbtn('follow', t('mapFollowOff'), () => setFollow(!mapState.follow), 'false')
    ui.btnRotate = rbtn('rotate', t('mapNorthUp'), () => setRotate(!mapState.rotate), 'false')
    ui.btnBase = (pack.basemaps || []).length > 1 ? rbtn('layers', t('mapBaseOsm'), () => { const defs = pack.basemaps; setBase(defs[(defs.findIndex((d) => d.id === mapState.base) + 1) % defs.length].id); syncButtons() }) : null
    ui.mapEl = h('div', { id: 'map', class: 'map', role: 'application', 'aria-label': t('mapLabel') })
    ui.maprot = h('div', { id: 'maprot' }, ui.mapEl)
    ui.nobase = h('div', { class: 'nobase', role: 'status', hidden: true }, t('mapNoBase'))
    ui.miniSvg = h('div', { class: 'minisvg' })
    ui.mini = h('div', { class: 'mini', hidden: true }, ui.miniSvg)
    ui.stage = h('div', { class: 'stage' + (ui.btnBase ? ' has-layers' : '') }, ui.maprot, ui.nobase, ui.attrib, ui.mini,
      h('div', { class: 'mapbtns' }, ui.btnMe, ui.btnFollow, ui.btnRotate, ui.btnBase,
        h('div', { class: 'pair' }, rbtn('plus', t('mapZoomIn'), () => { ui.userMoved = true; if (map) map.zoomIn() }), rbtn('minus', t('mapZoomOut'), () => { ui.userMoved = true; if (map) map.zoomOut() }))), ui.sheet)
    ui.done = h('span', { class: 'done' })
    return h('div', { style: 'display:flex;flex-direction:column;flex:1;min-height:0' },
      h('div', { class: 'topbar' }, h('button', { type: 'button', class: 'btn', 'aria-label': t('backLabel'), onclick: leaveBlock }, t('back')), h('div', { class: 'ttl' }, h('span', { class: 'ttl1' }, `${block.ref} · ${block.name}`), ui.done), helpButton()),
      ui.stage)
  }

  function leaveBlock() {
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

  // ------------------------------------------------------------------ language, help and the first-visit intro
  function setLang(l) {
    lang = l
    prefs.lang = l
    savePrefs()
    paintStatic()
    const wasHelp = overlay && overlay.dataset.kind === 'help'
    const wasIntro = overlay && overlay.dataset.kind === 'intro'
    const introAt = wasIntro ? Number(overlay.dataset.at) : 0
    closeOverlay()
    render()
    if (wasHelp) showHelp()
    if (wasIntro) showIntro(introAt)
  }
  const langSwitch = () => h('div', { class: 'lang', role: 'group', 'aria-label': t('langLabel') },
    ['fil', 'en'].map((l) => h('button', { type: 'button', class: 'btn langbtn', 'data-lang': l, 'aria-pressed': String(lang === l), onclick: () => { if (lang !== l) setLang(l) } }, t(l === 'fil' ? 'langFil' : 'langEn'))))
  const helpButton = () => h('button', { type: 'button', class: 'btn helpbtn', 'aria-label': t('helpTitle'), onclick: () => showHelp() }, t('helpBtn'))
  function closeOverlay() {
    if (overlay) overlay.remove()
    overlay = null
    document.body.classList.remove('has-overlay')
  }
  function openOverlay(kind, children) {
    closeOverlay()
    overlay = h('div', { class: 'overlay', role: 'dialog', 'aria-modal': 'true', 'aria-label': t(kind === 'help' ? 'helpTitle' : 'introTitle'), 'data-kind': kind }, h('div', { class: 'overlaybox' }, children))
    document.body.append(overlay)
    document.body.classList.add('has-overlay')
    const first = overlay.querySelector('button')
    if (first) first.focus({ preventScroll: true })
  }
  function trouble(titleKey, textKey, extraKey) {
    return h('div', { class: 'trouble' }, h('h3', null, t(titleKey)), h('p', null, t(textKey)), extraKey ? h('p', null, t(extraKey)) : null)
  }
  function showHelp() {
    openOverlay('help', [
      h('div', { class: 'overlayhead' }, h('h2', null, t('helpTitle')), h('button', { type: 'button', class: 'btn', onclick: closeOverlay }, t('helpClose'))),
      langSwitch(),
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
  }
  function showIntro(at) {
    const i = Math.max(0, Math.min(2, at || 0))
    const last = i === 2
    openOverlay('intro', [
      h('div', { class: 'card', 'data-card': i + 1 }, h('p', { class: 'cardn' }, t('introCard', { n: i + 1 })), h('h2', null, t('intro' + (i + 1) + 'Title')), h('p', { class: 'cardtext' }, t('intro' + (i + 1)))),
      h('div', { class: 'btnrow' },
        h('button', { type: 'button', class: 'btn good primary', onclick: () => { if (last) { prefs.introDone = true; savePrefs(); closeOverlay() } else showIntro(i + 1) } }, t(last ? 'introDone' : 'introNext')),
        last ? null : h('button', { type: 'button', class: 'btn secondary', onclick: () => { prefs.introDone = true; savePrefs(); closeOverlay() } }, t('introSkip'))),
    ])
    overlay.dataset.at = String(i)
  }

  // ------------------------------------------------------------------ landing and home
  function landingScreen() {
    const checks = prefs.checks || {}
    return h('div', null,
      h('div', { class: 'hdr' }, h('h1', null, t('title')), helpButton()),
      langSwitch(),
      h('h2', null, t('howTitle')),
      h('ol', { class: 'steps' }, [1, 2, 3, 4].map((i) => h('li', null, t('how' + i)))),
      h('p', { class: 'honest' }, t('gpsPromise')),
      h('h2', null, t('beforeTitle')),
      h('ul', { class: 'checklist' }, [1, 2, 3, 4, 5].map((i) => h('li', null, h('label', { class: 'check' },
        h('input', { type: 'checkbox', checked: checks[i] ? true : null, onchange: (e) => { prefs.checks = Object.assign({}, prefs.checks, { [i]: e.target.checked }); savePrefs() } }), h('span', null, t('before' + i)))))),
      h('button', { type: 'button', class: 'btn good wide big', onclick: () => { view.screen = 'home'; render() } }, t('start')),
      h('p', { class: 'note' }, t('planLine', { plan: pack.plan_id, code: pack.check_code, pack: pack.pack_id })),
      h('p', { class: 'note' }, t('builtLine', { date: pack.built_on, tag: pack.dataset.tag, hash: pack.dataset.hash })))
  }
  function homeScreen() {
    const totals = pack.blocks.reduce((s, b) => {
      const p = Core.progress(b, state)
      return { n: s.n + p.n, planted: s.planted + p.planted, skipped: s.skipped + p.skipped }
    }, { n: 0, planted: 0, skipped: 0 })
    return h('div', null,
      h('div', { class: 'hdr' }, h('button', { type: 'button', class: 'btn', 'aria-label': t('backToIntro'), onclick: () => { view.screen = 'landing'; render() } }, t('back')), h('h1', null, t('blocksTitle')), helpButton()),
      store.ok ? null : h('p', { class: 'warn', role: 'alert' }, t('storageWarn')),
      h('label', { for: 'observer' }, t('nameLabel')),
      h('input', { id: 'observer', type: 'text', maxlength: '80', autocomplete: 'name', value: state.observer || '', oninput: (e) => { state.observer = e.target.value; save() } }),
      h('p', { class: 'note' }, t('totalsLine', totals)),
      h('div', { class: 'blocks' }, pack.blocks.map((b) => {
        const p = Core.progress(b, state)
        return h('button', { type: 'button', class: 'bcard', onclick: () => { view.screen = 'block'; view.ref = b.ref; view.tree = null; view.skipOpen = false; view.step = stepOf(b); render() } },
          h('strong', null, b.ref), h('span', null, b.name), h('small', null, t('blockCard', { n: b.n, done: p.planted + p.skipped })),
          h('div', { class: 'bar', role: 'img', 'aria-label': t('blockCard', { n: b.n, done: p.planted + p.skipped }) }, h('span', { class: 'p', style: `width:${(100 * p.planted) / p.n}%` }), h('span', { class: 's', style: `width:${(100 * p.skipped) / p.n}%` })))
      })),
      h('h2', null, t('resultsTitle')),
      h('p', { class: 'note' }, t('resultsHelp')),
      h('div', { class: 'actions' }, h('button', { type: 'button', class: 'btn good', onclick: download }, t('btnDownload')), typeof navigator.canShare === 'function' ? h('button', { type: 'button', class: 'btn', onclick: share }, t('btnShare')) : null),
      h('p', { class: 'note' }, t('gpsHonest')),
      h('p', { class: 'note' }, t('banner')),
      langSwitch(),
      h('button', { type: 'button', class: 'btn link', onclick: () => { if (confirm(t('confirmErase'))) { state = Core.emptyState(); save(); render() } } }, t('btnErase')))
  }

  function render() {
    destroyMap()
    const b = view.screen === 'block' ? blockOf(view.ref) : null
    document.body.classList.toggle('in-block', !!b)
    root.replaceChildren(...clean([b ? blockScreen(b) : view.screen === 'home' ? homeScreen() : landingScreen()]))
    if (b) {
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
    root.scrollTop = 0
    window.scrollTo(0, 0)
  }

  paintStatic()
  render()
  if (!prefs.introDone) showIntro(0)
})()
