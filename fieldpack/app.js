/* Field pack, Stage A1: the page. Plain JavaScript, no framework, no network calls. Every word the person reads comes from STRINGS (strings.js) through t(), so another language can be added later.
 * The plan (blocks, per-tree coordinates) is the JSON element with the id pack-data. Results are kept on this phone only (localStorage, in try/catch). */
(function () {
  'use strict'
  const Core = FieldPackCore
  const pack = JSON.parse(document.getElementById('pack-data').textContent)
  const t = (id, vars) => {
    let s = STRINGS[id]
    if (s === undefined) return '[' + id + ']'
    if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m))
    return s
  }
  const store = Core.makeStore(() => window.localStorage, `fieldpack:${pack.plan_id}:${pack.check_code}`)
  let state = store.load()
  const view = { screen: 'home', ref: null, tree: null, skipOpen: false, keepScroll: false }
  const gps = { id: null, fix: null, status: 'off', error: '' }
  const compass = { heading: null, at: 0, moveHeading: null, moveAt: 0, status: 'off' }
  const root = document.getElementById('app')
  let targetBox = null

  // ------------------------------------------------------------------ small helpers (the DOM is built with textContent only: nothing from the plan is ever read as HTML)
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag)
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue
      if (k === 'class') e.className = v
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v)
      else e.setAttribute(k, v === true ? '' : v)
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)))
    return e
  }
  const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
  const save = () => store.save(state)
  const blockOf = (ref) => pack.blocks.find((b) => b.ref === ref)
  const fmt = (x) => x.toFixed(6)

  // ------------------------------------------------------------------ GPS and compass
  function gpsProblem() {
    if (!('geolocation' in navigator)) return t('gpsNone')
    if (window.isSecureContext === false) return t('gpsInsecure')
    return ''
  }
  function startGps() {
    const p = gpsProblem()
    if (p) {
      gps.status = 'error'
      gps.error = p
      renderTarget()
      return
    }
    if (gps.id !== null) return
    gps.status = 'waiting'
    renderTarget()
    gps.id = navigator.geolocation.watchPosition(
      (pos) => {
        const c = pos.coords
        gps.fix = { lat: c.latitude, lon: c.longitude, acc: Number.isFinite(c.accuracy) ? c.accuracy : null, at: Date.now() }
        gps.status = 'ok'
        if (Number.isFinite(c.heading) && Number.isFinite(c.speed) && c.speed >= 1) {
          compass.moveHeading = c.heading
          compass.moveAt = Date.now()
        }
        renderTarget()
      },
      (err) => {
        gps.status = 'error'
        gps.error = (err && err.code === 1 ? t('gpsDenied') : err && err.code === 3 ? t('gpsTimeout') : t('gpsUnavailable')) + (location.protocol === 'file:' ? ' ' + t('gpsFile') : '')
        renderTarget()
      },
      { enableHighAccuracy: true, maximumAge: 1000, timeout: 20000 },
    )
  }
  function stopGps() {
    if (gps.id !== null) navigator.geolocation.clearWatch(gps.id)
    gps.id = null
    gps.status = 'off'
    gps.fix = null
    renderTarget()
  }
  async function startCompass() {
    try {
      if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
        const r = await DeviceOrientationEvent.requestPermission()
        if (r !== 'granted') {
          compass.status = 'denied'
          return renderTarget()
        }
      }
    } catch (e) {
      compass.status = 'none'
      return renderTarget()
    }
    const onOrient = (e) => {
      let hd = null
      if (typeof e.webkitCompassHeading === 'number') hd = e.webkitCompassHeading
      else if (e.absolute === true && typeof e.alpha === 'number') hd = (360 - e.alpha) % 360
      if (hd === null) return
      const angle = window.screen && window.screen.orientation ? window.screen.orientation.angle || 0 : 0
      compass.heading = (hd + angle) % 360
      compass.at = Date.now()
      compass.status = 'ok'
    }
    window.addEventListener('deviceorientationabsolute', onOrient, true)
    window.addEventListener('deviceorientation', onOrient, true)
    compass.status = 'waiting'
    renderTarget()
    setTimeout(() => {
      if (compass.status === 'waiting') {
        compass.status = 'none'
        renderTarget()
      }
    }, 3000)
  }
  function heading() {
    const n = Date.now()
    if (compass.heading !== null && n - compass.at < 3000) return { deg: compass.heading, source: 'compass' }
    if (compass.moveHeading !== null && n - compass.moveAt < 5000) return { deg: compass.moveHeading, source: 'movement' }
    return null
  }

  // ------------------------------------------------------------------ recording
  function activeTree(block) {
    return view.tree !== null && Core.treeOf(block, view.tree) ? view.tree : Core.nextTarget(block, state)
  }
  function record(block, k, rec) {
    state.trees[Core.key(block, k)] = Object.assign({ t: nowIso() }, rec)
    view.tree = null
    view.skipOpen = false
    if (!save()) alert(t('storageFail'))
    render(true)
  }
  function freshFix() {
    return gps.fix && Date.now() - gps.fix.at < 60000 ? gps.fix : null
  }
  function markPlanted(block, k) {
    const tr = Core.treeOf(block, k)
    const fix = freshFix()
    if (!fix) {
      if (!confirm(t('confirmNoFix'))) return
    } else {
      const d = Core.distanceM(fix.lat, fix.lon, tr[1], tr[2])
      const a = Core.arrival(d, fix.acc, block.spacing_m)
      if (!a.arrived && !confirm(t('confirmFar', { d: Core.distanceLabel(d, fix.acc).text }))) return
    }
    record(block, k, fix ? { s: 'planted', lat: fix.lat, lon: fix.lon, acc: fix.acc } : { s: 'planted' })
  }
  function markSkipped(block, k, reason) {
    record(block, k, { s: 'skipped', reason })
  }
  function undo(block, k) {
    delete state.trees[Core.key(block, k)]
    save()
    render()
  }

  // ------------------------------------------------------------------ the target card (re-drawn on every GPS reading)
  function renderTarget() {
    if (!targetBox || view.screen !== 'block') return
    const block = blockOf(view.ref)
    const k = activeTree(block)
    const kids = []
    if (gps.status === 'off') kids.push(h('button', { class: 'btn big', onclick: startGps }, t('gpsStart')), location.protocol === 'file:' ? h('p', { class: 'note' }, t('gpsFileMaybe')) : null)
    if (gps.status === 'waiting') kids.push(h('p', { class: 'note' }, t('gpsWaiting')))
    if (gps.status === 'error') kids.push(h('p', { class: 'warn', role: 'alert' }, gps.error), h('button', { class: 'btn', onclick: () => { if (gps.id !== null) navigator.geolocation.clearWatch(gps.id); gps.id = null; gps.status = 'off'; gps.error = ''; renderTarget() } }, t('gpsRetry')))
    if (k === null) {
      kids.push(h('p', { class: 'ok' }, t('blockDone')))
    } else {
      const tr = Core.treeOf(block, k)
      const rec = state.trees[Core.key(block, k)]
      kids.push(h('h3', null, t('targetTitle', { k, n: block.n })))
      if (rec) kids.push(h('p', { class: rec.s === 'planted' ? 'ok' : 'warn' }, rec.s === 'planted' ? t('recPlanted') : t('recSkipped', { reason: t('reason_' + rec.reason) })))
      kids.push(h('p', { class: 'note' }, t('targetCoords', { lat: fmt(tr[1]), lon: fmt(tr[2]) })))
      const fix = freshFix()
      if (fix) {
        const d = Core.distanceM(fix.lat, fix.lon, tr[1], tr[2])
        const b = Core.bearingDeg(fix.lat, fix.lon, tr[1], tr[2])
        const a = Core.arrival(d, fix.acc, block.spacing_m)
        const dl = Core.distanceLabel(d, fix.acc)
        const hd = heading()
        const turn = hd ? Core.turnDeg(b, hd.deg) : null
        kids.push(h('p', { class: 'dist' }, t('distance', { d: dl.text })))
        kids.push(h('p', { class: 'bearing' }, t('bearing', { deg: Math.round(b), dir: Core.compassPoint(b) })))
        if (turn !== null) {
          kids.push(h('div', { class: 'arrow', 'aria-hidden': 'true', style: `transform: rotate(${Math.round(turn)}deg)` }, '↑'), h('p', { class: 'note' }, t(hd.source === 'compass' ? 'arrowCompass' : 'arrowMovement')))
        } else {
          kids.push(h('p', { class: 'note' }, t('noArrow')))
        }
        kids.push(h('p', { class: 'acc' }, a.accuracyKnown ? t('accuracy', { m: Math.round(fix.acc) }) : t('accuracyUnknown')))
        if (a.arrived) kids.push(h('p', { class: 'ok big' }, t('arrived')))
        if (a.approximate) kids.push(h('p', { class: 'warn' }, a.accuracyKnown ? t('approxSpacing', { acc: Math.round(fix.acc), sp: block.spacing_m }) : t('approxUnknown')))
      } else if (gps.status === 'ok') {
        kids.push(h('p', { class: 'warn' }, t('fixOld')))
      }
      if (compass.status === 'off' || compass.status === 'none' || compass.status === 'denied') {
        kids.push(h('button', { class: 'btn', onclick: startCompass }, t('compassStart')))
        if (compass.status === 'none') kids.push(h('p', { class: 'note' }, t('compassNone')))
        if (compass.status === 'denied') kids.push(h('p', { class: 'note' }, t('compassDenied')))
      }
      kids.push(h('div', { class: 'actions' },
        h('button', { class: 'btn good', onclick: () => markPlanted(block, k) }, t('btnPlanted')),
        h('button', { class: 'btn bad', onclick: () => { view.skipOpen = !view.skipOpen; renderTarget() } }, t('btnSkip')),
        rec ? h('button', { class: 'btn', onclick: () => undo(block, k) }, t('btnUndo')) : null))
      if (view.skipOpen) {
        kids.push(h('p', { class: 'note' }, t('skipWhy')), h('div', { class: 'reasons' }, Core.REASONS.map((r) => h('button', { class: 'btn', onclick: () => markSkipped(block, k, r) }, t('reason_' + r)))))
      }
      if (gps.status === 'ok') kids.push(h('button', { class: 'btn link', onclick: stopGps }, t('gpsStop')))
    }
    targetBox.replaceChildren(...kids)
    if (map) updateMap(block, k)
    else {
      const sk = document.getElementById('sketch')
      if (sk) sk.replaceWith(sketch(block, k))
    }
  }

  // ------------------------------------------------------------------ a small drawing of the block (display only: a flat approximation around START, good to centimetres over 100 m)
  function sketch(block, active) {
    const NS = 'http://www.w3.org/2000/svg'
    const mk = (n, a) => {
      const e = document.createElementNS(NS, n)
      for (const [k, v] of Object.entries(a)) e.setAttribute(k, v)
      return e
    }
    const svg = mk('svg', { id: 'sketch', viewBox: '-4 -4 108 108', role: 'img', 'aria-label': t('sketchLabel'), class: 'sketch' })
    svg.append(mk('rect', { x: 0, y: 100 - 100, width: 100, height: 100, fill: '#fff', stroke: '#000', 'stroke-width': 0.6 }))
    const m = block.margin_m, side = block.side_m
    svg.append(mk('rect', { x: m, y: 100 - m - side, width: side, height: side, fill: '#eee', stroke: '#000', 'stroke-width': 0.4, 'stroke-dasharray': '2 1' }))
    const rad = Math.max(1.2, Math.min(4, block.spacing_m * 0.28))
    for (const tr of block.trees) {
      const r = state.trees[Core.key(block, tr[0])]
      const fill = r ? (r.s === 'planted' ? '#006400' : '#8b0000') : '#fff'
      svg.append(mk('circle', { cx: tr[3], cy: 100 - tr[4], r: rad, fill, stroke: tr[0] === active ? '#000' : '#444', 'stroke-width': tr[0] === active ? 1.4 : 0.4 }))
    }
    const fix = freshFix()
    if (fix) {
      const s0 = block.start
      const x = m + (fix.lon - s0[1]) * 111320 * Math.cos((s0[0] * Math.PI) / 180)
      const y = m + (fix.lat - s0[0]) * 110574
      if (x > -30 && x < 130 && y > -30 && y < 130) {
        svg.append(mk('circle', { cx: Math.max(-3, Math.min(103, x)), cy: 100 - Math.max(-3, Math.min(103, y)), r: 2.2, fill: '#0033cc', stroke: '#fff', 'stroke-width': 0.6 }))
        if (Number.isFinite(fix.acc) && fix.acc < 60) svg.append(mk('circle', { cx: x, cy: 100 - y, r: fix.acc, fill: 'none', stroke: '#0033cc', 'stroke-width': 0.4, 'stroke-dasharray': '1.5 1' }))
      }
    }
    return svg
  }

  // ------------------------------------------------------------------ the real map (Leaflet, inlined in this page). The map tiles are the ONLY thing this page ever fetches from the network.
  // Layers: the 100 m grid square, the planted rectangle, every tree as a numbered dot, the target, your position with the phone's accuracy circle, and a line to the target.
  // Everything is drawn from the coordinates in the plan: if the tiles fail or there is no signal the map still shows all of it on a plain background and says so.
  const mapState = { follow: false, base: 'osm', view: null, ref: null, ok: 0, bad: 0, btn: {} }
  const ml = { user: null, acc: null, line: null, label: null, nobase: null, base: null, area: null }
  let map = null
  let mapHandlers = []

  function treeIcon(block, tr, active) {
    const r = state.trees[Core.key(block, tr[0])]
    const cls = 'treeicon ' + (r ? (r.s === 'planted' ? 'st-planted' : 'st-skipped') : 'st-todo') + (active ? ' st-active' : '')
    const size = active ? 36 : 26
    const el = h('div', { class: cls, 'data-k': tr[0], 'data-lat': tr[1], 'data-lon': tr[2] }, String(tr[0]))
    return L.divIcon({ className: '', html: el, iconSize: [size, size], iconAnchor: [size / 2, size / 2] })
  }
  function updateNoBase() {
    if (!ml.nobase) return
    const none = navigator.onLine === false || (mapState.bad >= 3 && mapState.ok === 0)
    ml.nobase.hidden = !none
  }
  function setBase(id) {
    const def = (pack.basemaps || []).find((b) => b.id === id)
    if (!def || !map) return
    if (ml.base) map.removeLayer(ml.base)
    mapState.base = id
    mapState.ok = 0
    mapState.bad = 0
    ml.base = L.tileLayer(def.url, { maxNativeZoom: def.maxNativeZoom, maxZoom: 22, attribution: def.attribution, referrerPolicy: 'strict-origin-when-cross-origin', keepBuffer: 1 })
    ml.base.on('tileload', () => { mapState.ok++; updateNoBase() })
    ml.base.on('tileerror', () => { mapState.bad++; updateNoBase() })
    ml.base.addTo(map)
    ml.base.bringToBack()
    if (mapState.btn.base) mapState.btn.base.textContent = t(id === 'sat' ? 'mapBaseSat' : 'mapBaseOsm')
    updateNoBase()
  }
  function setFollow(on) {
    mapState.follow = on
    if (mapState.btn.follow) mapState.btn.follow.textContent = t(on ? 'mapFollowOn' : 'mapFollowOff')
    const fix = freshFix()
    if (on && fix && map) map.panTo([fix.lat, fix.lon])
  }
  function mapSection(block, k) {
    if (typeof L === 'undefined') return sketch(block, k)
    const note = h('p', { class: 'note', id: 'mapnote', 'aria-live': 'polite' })
    const btn = (label, fn) => h('button', { class: 'btn', onclick: fn }, label)
    mapState.btn.follow = btn(t(mapState.follow ? 'mapFollowOn' : 'mapFollowOff'), () => setFollow(!mapState.follow))
    mapState.btn.base = btn(t(mapState.base === 'sat' ? 'mapBaseSat' : 'mapBaseOsm'), () => {
      const defs = pack.basemaps || []
      if (defs.length > 1) setBase(defs[(defs.findIndex((d) => d.id === mapState.base) + 1) % defs.length].id)
    })
    const tools = h('div', { class: 'maptools' },
      btn(t('mapMe'), () => {
        const fix = freshFix()
        note.textContent = fix ? '' : t('mapNoFix')
        if (fix && map) map.setView([fix.lat, fix.lon], Math.max(map.getZoom(), 19))
      }),
      mapState.btn.follow,
      (pack.basemaps || []).length > 1 ? mapState.btn.base : null,
      btn(t('mapZoomIn'), () => map && map.zoomIn()),
      btn(t('mapZoomOut'), () => map && map.zoomOut()))
    return h('div', { id: 'mapbox' }, h('div', { id: 'map', class: 'map', role: 'application', 'aria-label': t('mapLabel') }), tools, note)
  }
  function destroyMap() {
    for (const [type, fn] of mapHandlers) window.removeEventListener(type, fn)
    mapHandlers = []
    if (map) map.remove()
    map = null
    Object.keys(ml).forEach((key) => (ml[key] = null))
  }
  function initMap(block, k) {
    const el = document.getElementById('map')
    if (!el || typeof L === 'undefined') return
    try {
      map = L.map(el, { zoomControl: false, maxZoom: 22, zoomSnap: 0.5, attributionControl: false })
      L.control.attribution({ prefix: '<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>' }).addTo(map)
      const style = { color: '#000', weight: 2, fill: false }
      L.polygon(block.square, Object.assign({ dashArray: '2 6' }, style)).addTo(map)
      ml.area = L.polygon(block.area, { color: '#000', weight: 3, fillColor: '#000', fillOpacity: 0.08 }).addTo(map)
      for (const tr of block.trees) {
        const m = L.marker([tr[1], tr[2]], { icon: treeIcon(block, tr, tr[0] === k), keyboard: false, zIndexOffset: tr[0] === k ? 1000 : 0 })
        m.on('click', () => { view.tree = tr[0]; view.skipOpen = false; render(true) })
        m.addTo(map)
      }
      ml.nobase = h('div', { class: 'nobase', role: 'status', hidden: true }, t('mapNoBase'))
      el.append(ml.nobase)
      setBase((pack.basemaps || []).some((b) => b.id === mapState.base) ? mapState.base : 'osm')
      if (mapState.view && mapState.ref === block.ref) map.setView(mapState.view.center, mapState.view.zoom)
      else map.fitBounds(ml.area.getBounds(), { padding: [24, 24], maxZoom: 20 })
      map.on('moveend', () => { mapState.view = { center: map.getCenter(), zoom: map.getZoom() }; mapState.ref = block.ref })
      map.on('dragstart', () => { if (mapState.follow) setFollow(false) })
      for (const type of ['online', 'offline']) {
        mapHandlers.push([type, updateNoBase])
        window.addEventListener(type, updateNoBase)
      }
      updateMap(block, k)
    } catch (e) {
      destroyMap()
      const box = document.getElementById('mapbox')
      if (box) box.replaceWith(sketch(block, k))
    }
  }
  function updateMap(block, k) {
    if (!map) return
    const fix = freshFix()
    for (const key of ['user', 'acc', 'line', 'label']) {
      if (ml[key]) { map.removeLayer(ml[key]); ml[key] = null }
    }
    if (!fix) return
    const here = [fix.lat, fix.lon]
    if (Number.isFinite(fix.acc)) ml.acc = L.circle(here, { radius: fix.acc, color: '#0033cc', weight: 2, dashArray: '4 4', fillColor: '#0033cc', fillOpacity: 0.12, interactive: false }).addTo(map)
    ml.user = L.circleMarker(here, { radius: 9, color: '#fff', weight: 3, fillColor: '#0033cc', fillOpacity: 1, interactive: false }).addTo(map)
    const tr = k === null ? null : Core.treeOf(block, k)
    if (tr) {
      const d = Core.distanceM(fix.lat, fix.lon, tr[1], tr[2])
      const b = Core.bearingDeg(fix.lat, fix.lon, tr[1], tr[2])
      const dl = Core.distanceLabel(d, fix.acc)
      ml.line = L.polyline([here, [tr[1], tr[2]]], { color: '#0033cc', weight: 4, dashArray: '8 8', interactive: false }).addTo(map)
      const mid = [(fix.lat + tr[1]) / 2, (fix.lon + tr[2]) / 2]
      ml.label = L.marker(mid, { icon: L.divIcon({ className: '', html: h('div', { class: 'linelabel' }, t('mapLine', { d: dl.text, dir: Core.compassPoint(b), deg: Math.round(b) })), iconSize: [150, 30], iconAnchor: [75, 15] }), interactive: false, keyboard: false }).addTo(map)
    }
    if (mapState.follow) map.panTo(here, { animate: true })
  }

  // ------------------------------------------------------------------ screens
  function treeButton(block, tr, active) {
    const r = state.trees[Core.key(block, tr[0])]
    const sym = r ? (r.s === 'planted' ? '✓' : '✗') : ''
    return h('button', { class: `tree ${r ? r.s : 'todo'}${tr[0] === active ? ' active' : ''}`, onclick: () => { view.tree = tr[0]; view.skipOpen = false; render() }, 'aria-label': t('treeAria', { k: tr[0], state: r ? t(r.s === 'planted' ? 'recPlanted' : 'recSkipped', { reason: t('reason_' + r.reason) }) : t('stateTodo') }) }, h('span', null, tr[0]), h('small', null, sym))
  }
  function blockScreen(block) {
    const k = activeTree(block)
    targetBox = h('section', { class: 'card', 'aria-live': 'polite' })
    const p = Core.progress(block, state)
    const node = h('div', null,
      h('button', { class: 'btn', onclick: () => { view.screen = 'home'; view.ref = null; view.tree = null; render() } }, t('back')),
      h('h2', null, `${block.ref} · ${block.name}`),
      h('p', { class: 'dist' }, t('progressLine', { done: p.planted, skipped: p.skipped, n: p.n })),
      mapSection(block, k),
      targetBox,
      typeof L === 'undefined' ? null : h('p', { class: 'note' }, t('mapLegend')),
      h('p', { class: 'note' }, t('mapHonest')),
      h('p', null, t('blockLine', { n: block.n, sp: block.spacing_m, rows: block.rows, per: block.per_row })),
      h('p', { class: 'note' }, t('startLine', { lat: fmt(block.start[0]), lon: fmt(block.start[1]) })),
      h('details', { class: 'more' }, h('summary', null, t('layoutHelp')), h('p', { class: 'note' }, t('orderLine')), block.note ? h('p', { class: 'note' }, block.note) : null),
      h('h3', null, t('treesTitle')),
      h('div', { class: 'trees' }, block.trees.map((tr) => treeButton(block, tr, k))))
    return node
  }
  function exportFile() {
    if (!(state.observer || '').trim()) return alert(t('needName'))
    const text = '﻿' + Core.exportCsv(pack, state, nowIso())
    const name = `results_${pack.plan_id}_${pack.check_code}.csv`
    const blob = new Blob([text], { type: 'text/csv;charset=utf-8' })
    return { blob, name }
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
    } catch (e) {
      /* the person closed the share sheet */
    }
  }
  function homeScreen() {
    const totals = pack.blocks.reduce((s, b) => {
      const p = Core.progress(b, state)
      return { n: s.n + p.n, planted: s.planted + p.planted, skipped: s.skipped + p.skipped }
    }, { n: 0, planted: 0, skipped: 0 })
    return h('div', null,
      h('h1', null, t('title')),
      h('p', { class: 'note' }, t('planLine', { plan: pack.plan_id, code: pack.check_code, pack: pack.pack_id })),
      h('p', { class: 'note' }, t('builtLine', { date: pack.built_on, tag: pack.dataset.tag, hash: pack.dataset.hash })),
      store.ok ? null : h('p', { class: 'warn', role: 'alert' }, t('storageWarn')),
      h('label', { for: 'observer' }, t('nameLabel')),
      h('input', { id: 'observer', type: 'text', maxlength: '80', autocomplete: 'name', value: state.observer || '', oninput: (e) => { state.observer = e.target.value; save() } }),
      h('h2', null, t('blocksTitle')),
      h('p', { class: 'dist' }, t('totalsLine', totals)),
      h('div', { class: 'blocks' }, pack.blocks.map((b) => {
        const p = Core.progress(b, state)
        return h('button', { class: 'btn block', onclick: () => { view.screen = 'block'; view.ref = b.ref; view.tree = null; view.skipOpen = false; render() } },
          h('strong', null, `${b.ref}`), h('span', null, `${b.name}`), h('small', null, t('blockButton', { n: b.n, done: p.planted, skipped: p.skipped })))
      })),
      h('h2', null, t('resultsTitle')),
      h('p', { class: 'note' }, t('resultsHelp')),
      h('div', { class: 'actions' }, h('button', { class: 'btn good', onclick: download }, t('btnDownload')), typeof navigator.canShare === 'function' ? h('button', { class: 'btn', onclick: share }, t('btnShare')) : null),
      h('p', { class: 'note' }, t('gpsHonest')),
      h('button', { class: 'btn link', onclick: () => { if (confirm(t('confirmErase'))) { state = Core.emptyState(); save(); render() } } }, t('btnErase')))
  }
  function render(keepScroll) {
    targetBox = null
    destroyMap()
    const b = view.screen === 'block' ? blockOf(view.ref) : null
    root.replaceChildren(b ? blockScreen(b) : homeScreen())
    if (b) {
      renderTarget()
      initMap(b, activeTree(b))
    }
    if (!keepScroll) window.scrollTo(0, 0)
  }

  document.getElementById('banner').textContent = t('banner')
  document.title = t('title') + ' ' + pack.plan_id
  render()
})()
