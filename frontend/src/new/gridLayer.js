import L from 'leaflet'
import { wLevel } from '../v2/scale.js'
import { shapeColor, shapePath } from './planShapes.js'
import { GROUND_GROUPS, GROUND_MISSING, GROUND_STYLE, patternTile } from './groundStyle.js'
import { FIELD_CLASSES } from './fieldStatus.js'

// The grid of scored points, drawn in ONE canvas pass (no per-point React components, no per-point Leaflet objects).
// A custom Leaflet layer: a single <canvas> in the overlay pane, redrawn after every move/zoom. Hover and click are found with
// one pass over the point positions of the current view.

// colour per level: 0 none (grey), 1 poor (red), 2 moderate (orange), 3 good (green). Same colours as the legend swatches.
export const LEVEL_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#2e7d32']
const LEVEL_INDEX = { none: 0, poor: 1, moderate: 2, good: 3 }
const SELECT_COLOR = '#38bdf8'
const TWO_PI = Math.PI * 2
const CELL_M = 100 // the grid spacing, in metres
const HIT_EXTRA = 3 // extra pixels around a square that still count as hovering it
const SQUARE_ALPHA = 0.8 // the colour of the grid squares is a little soft
const GAP_FROM_PX = 8 // a 1 px gap between squares only when a square is at least this wide on screen (zoomed in)
const CONTEXT_FILL = 'rgba(148,163,184,0.15)' // the squares that are not planting zones: one flat, very faint tone
const BUBBLE_BELOW_ZOOM = 15 // planned trees are grouped into numbered bubbles below this zoom
const BUBBLE_BARANGAY_BELOW_ZOOM = 14 // ... one bubble per barangay below this zoom, one per 500 m cell between the two
const BUBBLE_CELL_M = 500 // one bubble per 500 m cell
const CODES_FROM_ZOOM = 17 // the 3-letter codes appear from this zoom (in the Detailed view)
const PAD = 0.5 // the canvas is this much larger than the screen on every side, so panning does not show blank edges

const GridCanvasLayer = L.Layer.extend({
  initialize(options) {
    L.setOptions(this, options)
    this._n = 0
    this._selected = -1
    this._spot = null
    this._labeler = null
    this._field = null
    this._hover = -1
    this._radius = 3
    this._half = 1
    this._detailed = false
    this._groundOn = false // the optional ground-cover layer: squares coloured (and patterned) by their dominant satellite land-cover class
    this._gcls = null
    this._gflags = null
    this._corners = false
    this._clusters = []
    this._cn = 0 // the second, fainter layer: grid squares that are not planting zones (GET /grid/context)
    this._cvisible = true
    this._chover = -1
    this._clabeler = null
    this._safe = { left: 8, right: 8, top: 8, bottom: 8 }
    this._pn = 0 // the planned trees (one shape per species) drawn on top of the grid
    this._pvisible = true
    this._phover = -1
    this._plabeler = null
  },

  onAdd(map) {
    this._map = map
    this._canvas = L.DomUtil.create('canvas', 'nw-grid-canvas')
    this._canvas.setAttribute('aria-hidden', 'true')
    this._canvas.style.pointerEvents = 'none'
    map.getPane('overlayPane').appendChild(this._canvas)
    this._tip = L.tooltip({ direction: 'top', offset: [0, -6], opacity: 0.97, className: 'nw-point-tip' })
    map.on('moveend zoomend resize', this._update, this)
    map.on('mousemove', this._onMove, this)
    map.on('mouseout', this._onOut, this)
    map.on('click', this._onClick, this)
    this._update()
  },

  onRemove(map) {
    map.off('moveend zoomend resize', this._update, this)
    map.off('mousemove', this._onMove, this)
    map.off('mouseout', this._onOut, this)
    map.off('click', this._onClick, this)
    this._closeTip()
    L.DomUtil.remove(this._canvas)
    this._canvas = null
    this._map = null
  },

  // cols = the `columns` object of GET /grid (point_id, lon, lat, W, best_species_id, n_eligible_species, barangay)
  setData(cols) {
    if (!cols) {
      this._n = 0
      this._cols = null
    } else {
      const n = cols.lon.length
      this._n = n
      this._cols = cols
      this._mx = new Float64Array(n)
      this._my = new Float64Array(n)
      this._level = new Uint8Array(n)
      for (let i = 0; i < n; i++) {
        this._mx[i] = (cols.lon[i] + 180) / 360 // Web Mercator, 0..1
        this._my[i] = 0.5 - Math.log(Math.tan(Math.PI / 4 + (cols.lat[i] * Math.PI) / 360)) / TWO_PI
        const w = cols.W[i]
        this._level[i] = LEVEL_INDEX[wLevel(w, w > 0)]
      }
      this._px = new Float32Array(n)
      this._py = new Float32Array(n)
    }
    this._hover = -1
    this._closeTip()
    this._draw()
  },

  // cols = the `columns` object of GET /grid/context (point_id, lon, lat, ...). Drawn UNDER the scored points as small grey dots with low opacity.
  setContext(cols) {
    if (!cols) {
      this._cn = 0
      this._ccols = null
    } else {
      const n = cols.lon.length
      this._cn = n
      this._ccols = cols
      this._cmx = new Float64Array(n)
      this._cmy = new Float64Array(n)
      for (let i = 0; i < n; i++) {
        this._cmx[i] = (cols.lon[i] + 180) / 360
        this._cmy[i] = 0.5 - Math.log(Math.tan(Math.PI / 4 + (cols.lat[i] * Math.PI) / 360)) / TWO_PI
      }
      this._cpx = new Float32Array(n)
      this._cpy = new Float32Array(n)
    }
    this._chover = -1
    this._closeTip()
    this._draw()
  },

  // items = [{lon, lat, kind, code, unconfirmed}] of the planned trees; kind picks the shape and the colour; unconfirmed = land outside the zoning map (a dotted ring)
  setPlan(items) {
    const list = items ?? []
    this._pn = list.length
    this._punconf = list.filter((it) => it.unconfirmed).length
    this._pitems = list
    this._pblocks = list.some((it) => it.trees != null) // blocks: a 100 m square with the species shape and the number of trees
    this._pside = 0
    this._pmx = new Float64Array(this._pn)
    this._pmy = new Float64Array(this._pn)
    this._ppx = new Float32Array(this._pn)
    this._ppy = new Float32Array(this._pn)
    this._ppaths = new Map()
    list.forEach((it, i) => {
      this._pmx[i] = (it.lon + 180) / 360
      this._pmy[i] = 0.5 - Math.log(Math.tan(Math.PI / 4 + (it.lat * Math.PI) / 360)) / TWO_PI
      if (!this._ppaths.has(it.kind)) this._ppaths.set(it.kind, new Path2D(shapePath(it.kind)))
    })
    this._phover = -1
    this._closeTip()
    this._draw()
  },

  setPlanVisible(on) {
    this._pvisible = !!on
    this._phover = -1
    this._closeTip()
    this._draw()
  },

  setPlanLabeler(fn) {
    this._plabeler = fn
  },

  // g = { cls: Uint8Array (index into GROUND_GROUPS, 255 = missing) per grid column, flags: Uint8Array (bits 1 bare, 2 built-up, 4 water) } or null
  setGround(g) {
    this._gcls = g ? g.cls : null
    this._gflags = g ? g.flags : null
    this._gctxcls = g ? g.ctxCls : null
    this._draw()
  },

  setGroundMode(on) {
    this._groundOn = !!on
    this._draw()
  },

  // a small corner marker on squares with a ground-cover flag (Detailed view)
  setCorners(on) {
    this._corners = !!on
    this._draw()
  },

  _groundPatterns() {
    const dpr = this._dpr || 1
    if (!this._gpat || this._gpatDpr !== dpr) {
      const ctx = this._canvas.getContext('2d')
      this._gpat = {}
      this._gpatDpr = dpr
      for (const g of GROUND_GROUPS) this._gpat[g] = ctx.createPattern(patternTile(g, dpr), 'repeat')
    }
    return this._gpat
  },

  // the Simple view hides the codes; Detailed shows them (from CODES_FROM_ZOOM)
  setDetailed(on) {
    this._detailed = !!on
    this._draw()
  },

  _planR() {
    const z = this._map.getZoom()
    return z >= 17 ? 9 : z >= 16 ? 7.5 : 6.5
  },

  // planned trees as numbered bubbles ("Maly 12") per 500 m cell at overview zoom; single trees stay shapes
  _bubbles() {
    const z = this._map.getZoom()
    if (z >= BUBBLE_BELOW_ZOOM || this._pn < 2) return null
    const scale = 256 * Math.pow(2, z)
    const mPerPx = (156543.03392 * Math.cos((14.69 * Math.PI) / 180)) / Math.pow(2, z)
    const cs = BUBBLE_CELL_M / mPerPx
    const cells = new Map()
    for (let i = 0; i < this._pn; i++) {
      const bn = this._pitems[i].barangay
      const key = z < BUBBLE_BARANGAY_BELOW_ZOOM && bn ? `b:${bn}` : `${Math.floor((this._pmx[i] * scale) / cs)},${Math.floor((this._pmy[i] * scale) / cs)}`
      let c = cells.get(key)
      if (!c) cells.set(key, (c = []))
      c.push(i)
    }
    return [...cells.values()]
  },

  _drawPlan(ctx) {
    this._pdrawn = 0
    this._pshapes = 0
    this._pbubbles = 0
    this._clusters = []
    this._phidden = new Uint8Array(this._pn)
    if (!this._pn || !this._pvisible) return
    const map = this._map
    const scale = 256 * Math.pow(2, map.getZoom())
    const o = map.getPixelOrigin()
    const ox = o.x + this._topLeft.x
    const oy = o.y + this._topLeft.y
    const R = this._planR()
    const { _ppx: px, _ppy: py, _pmx: mx, _pmy: my } = this
    for (let i = 0; i < this._pn; i++) {
      px[i] = mx[i] * scale - ox
      py[i] = my[i] * scale - oy
    }
    ctx.lineJoin = 'round'
    const groups = this._bubbles()
    const single = []
    if (groups) {
      for (const g of groups) {
        if (g.length < 2) {
          single.push(g[0])
          continue
        }
        let sx = 0
        let sy = 0
        const names = new Map()
        let unconf = false
        for (const i of g) {
          sx += px[i]
          sy += py[i]
          const nm = this._pitems[i].barangay || ''
          names.set(nm, (names.get(nm) ?? 0) + 1)
          if (this._pitems[i].unconfirmed) unconf = true
          this._phidden[i] = 1
        }
        const x = sx / g.length
        const y = sy / g.length
        const top = [...names.entries()].sort((a, b) => b[1] - a[1])[0][0]
        const label = top ? `${top} ${g.length}` : String(g.length)
        this._clusters.push({ x, y, n: g.length, label, name: top, members: g, unconf })
      }
    } else {
      for (let i = 0; i < this._pn; i++) single.push(i)
    }
    // bubbles: one pill with the barangay and the number
    ctx.font = '600 11px system-ui, sans-serif'
    for (const c of this._clusters) {
      if (c.x < -80 || c.y < -30 || c.x > this._w + 80 || c.y > this._h + 30) continue
      this._pbubbles++
      this._pdrawn += c.n
      const w = Math.max(26, ctx.measureText(c.label).width + 16)
      const h = 20
      c.w = w
      c.h = h
      ctx.fillStyle = 'rgba(15,23,42,0.88)'
      ctx.strokeStyle = 'rgba(248,250,252,0.9)'
      ctx.lineWidth = 1.2
      ctx.beginPath()
      ctx.roundRect(c.x - w / 2, c.y - h / 2, w, h, 10)
      ctx.fill()
      ctx.stroke()
      if (c.unconf) {
        ctx.save()
        ctx.setLineDash([2, 3])
        ctx.strokeStyle = '#f8fafc'
        ctx.beginPath()
        ctx.roundRect(c.x - w / 2 - 3, c.y - h / 2 - 3, w + 6, h + 6, 13)
        ctx.stroke()
        ctx.restore()
      }
      ctx.fillStyle = '#f8fafc'
      ctx.textBaseline = 'middle'
      ctx.textAlign = 'center'
      ctx.fillText(c.label, c.x, c.y + 0.5)
    }
    ctx.textAlign = 'start'
    ctx.textBaseline = 'alphabetic'
    // blocks: the 100 m square of every block (the species colour, a dark edge so that it shows on every map), under the shapes
    const mPerPx = (156543.03392 * Math.cos((14.69 * Math.PI) / 180)) / Math.pow(2, map.getZoom())
    this._pside = this._pblocks ? 100 / mPerPx : 0
    const half = this._pside / 2
    if (this._pblocks) {
      for (const i of single) {
        const x = px[i]
        const y = py[i]
        if (x < -half - 4 || y < -half - 4 || x > this._w + half + 4 || y > this._h + half + 4) continue
        const it = this._pitems[i]
        ctx.save()
        ctx.globalAlpha = 0.2
        ctx.fillStyle = shapeColor(it.kind)
        ctx.fillRect(x - half, y - half, this._pside, this._pside)
        ctx.globalAlpha = 1
        ctx.lineWidth = 3
        ctx.strokeStyle = 'rgba(15,23,42,0.9)'
        ctx.strokeRect(x - half, y - half, this._pside, this._pside)
        ctx.lineWidth = 1.5
        ctx.strokeStyle = shapeColor(it.kind)
        ctx.strokeRect(x - half, y - half, this._pside, this._pside)
        ctx.restore()
      }
    }
    // shapes: a thin dark outline only
    const showCodes = this._detailed && map.getZoom() >= CODES_FROM_ZOOM
    this._codesShown = showCodes
    for (const i of single) {
      const x = px[i]
      const y = py[i]
      if (x < -R - 12 - half || y < -R - 12 - half || x > this._w + R + 12 + half || y > this._h + R + 12 + half) continue
      const it = this._pitems[i]
      this._pdrawn++
      this._pshapes++
      ctx.save()
      ctx.translate(x, y)
      ctx.scale(R, R)
      const path = this._ppaths.get(it.kind)
      ctx.lineWidth = 1.2 / R
      ctx.strokeStyle = 'rgba(15,23,42,0.95)'
      ctx.fillStyle = shapeColor(it.kind)
      ctx.fill(path)
      ctx.stroke(path)
      ctx.restore()
      if (it.unconfirmed) {                                            // land outside the zoning map: a thin dotted ring
        ctx.save()
        ctx.beginPath()
        ctx.arc(x, y, R + 4, 0, TWO_PI)
        ctx.setLineDash([2, 3])
        ctx.lineWidth = 1.6
        ctx.strokeStyle = '#f8fafc'
        ctx.stroke()
        ctx.restore()
      }
      if (it.focus) {                                                  // "Show these on the map": a solid amber ring
        ctx.save()
        ctx.beginPath()
        ctx.arc(x, y, R + 7, 0, TWO_PI)
        ctx.lineWidth = 3
        ctx.strokeStyle = '#f59e0b'
        ctx.stroke()
        ctx.restore()
      }
      if (it.trees != null) {                                         // the number of trees of the block, in a small pill beside the shape
        const label = String(it.trees)
        ctx.font = '700 11px system-ui, sans-serif'
        const w = ctx.measureText(label).width + 8
        ctx.fillStyle = 'rgba(15,23,42,0.9)'
        ctx.beginPath()
        ctx.roundRect(x + R + 2, y - R - 3, w, 14, 7)
        ctx.fill()
        ctx.fillStyle = '#f8fafc'
        ctx.textBaseline = 'middle'
        ctx.textAlign = 'center'
        ctx.fillText(label, x + R + 2 + w / 2, y - R + 4)
        ctx.textAlign = 'start'
        ctx.textBaseline = 'alphabetic'
      }
      if (showCodes) {
        ctx.font = '600 10px system-ui, sans-serif'
        ctx.lineWidth = 3
        ctx.strokeStyle = 'rgba(15,23,42,0.9)'
        ctx.fillStyle = '#ffffff'
        ctx.strokeText(it.code, x - 9, y + R + 11)
        ctx.fillText(it.code, x - 9, y + R + 11)
      }
    }
  },

  // the bubble under a layer point, or null
  _hitBubble(layerPoint) {
    if (!this._clusters.length || !this._pvisible || !this._topLeft) return null
    const x = layerPoint.x - this._topLeft.x
    const y = layerPoint.y - this._topLeft.y
    return this._clusters.find((c) => Math.abs(c.x - x) <= (c.w ?? 26) / 2 + 2 && Math.abs(c.y - y) <= (c.h ?? 20) / 2 + 2) ?? null
  },

  _hitPlan(layerPoint) {
    if (!this._pn || !this._pvisible || !this._topLeft) return -1
    const x = layerPoint.x - this._topLeft.x
    const y = layerPoint.y - this._topLeft.y
    const reach = this._pblocks ? Math.max(this._planR() + 3, (this._pside || 0) / 2) : this._planR() + 3 // a block answers anywhere inside its 100 m square
    const lim = reach ** 2
    let best = -1
    let bestD = lim
    const { _ppx: px, _ppy: py } = this
    for (let i = 0; i < this._pn; i++) {
      if (this._phidden && this._phidden[i]) continue
      const dx = px[i] - x
      if (dx > reach + 25 || dx < -reach - 25) continue
      const d = this._pblocks ? Math.max(dx * dx, (py[i] - y) ** 2) : dx * dx + (py[i] - y) ** 2
      if (d <= bestD) {
        bestD = d
        best = i
      }
    }
    return best
  },

  setContextVisible(on) {
    this._cvisible = !!on
    this._chover = -1
    this._closeTip()
    this._draw()
  },

  // The part of the map that is free (not under the sidebar, the results panel or the top bar), in container pixels from each edge: hover cards flip to stay inside it.
  setSafeArea(a) {
    this._safe = { left: a.left, right: a.right, top: a.top, bottom: a.bottom }
  },

  // Show the hover card at a place and put it on the side where it stays fully visible (above, below, left or right of the dot).
  _showTip(latlng, lines) {
    const el = document.createElement('div')
    lines.forEach((t, k) => {
      const row = document.createElement(k === 0 ? 'strong' : 'div')
      row.textContent = t
      el.appendChild(row)
    })
    this._tip.options.direction = 'top'
    this._tip.options.offset = L.point(0, -6)
    this._tip.setLatLng(latlng)
    this._tip.setContent(el)
    if (!this._map.hasLayer(this._tip)) this._map.openTooltip(this._tip)
    this._placeTip(latlng)
  },

  _placeTip(latlng) {
    const node = this._tip.getElement()
    if (!node) return
    const map = this._map
    const size = map.getSize()
    const p = map.latLngToContainerPoint(latlng)
    const w = node.offsetWidth
    const h = node.offsetHeight
    const gap = 28
    const s = this._safe
    const roomAbove = p.y - h - gap >= s.top
    const roomBelow = p.y + h + gap <= size.y - s.bottom
    const midOk = p.y - h / 2 >= s.top && p.y + h / 2 <= size.y - s.bottom
    const lo = p.x - w / 2
    const hi = p.x + w / 2
    const dx = lo < s.left ? s.left - lo : hi > size.x - s.right ? size.x - s.right - hi : 0
    // preferred: above or below the dot, then beside it, and only then above or below shifted sideways so that it stays inside the free part of the map
    const order = []
    if (dx === 0 && roomAbove) order.push(['top', 0])
    if (dx === 0 && roomBelow) order.push(['bottom', 0])
    if (midOk && p.x - w - gap >= s.left) order.push(['left', 0])
    if (midOk && p.x + w + gap <= size.x - s.right) order.push(['right', 0])
    if (roomAbove) order.push(['top', dx])
    if (roomBelow) order.push(['bottom', dx])
    const [dir, shift] = order[0] ?? ['top', dx]
    this._tip.options.direction = dir
    this._tip.options.offset = L.point(Math.round(shift), dir === 'bottom' ? 14 : dir === 'top' ? -6 : 0)
    this._tip.update()
  },

  // fn(index) -> array of text lines for the hover tooltip of a grey square
  setContextLabeler(fn) {
    this._clabeler = fn
  },

  // field = { index: [...], status: [...] } of GET /grid (the field-checked points and their codes), or null to hide the symbols.
  // Symbols: 1 verified = ring, 2 not plantable = cross, 3 needs recheck = triangle; +4 (disputed) adds an exclamation mark. Shapes, never colour alone.
  setField(field) {
    this._field = field && field.index.length ? { index: Int32Array.from(field.index), code: Uint8Array.from(field.status), cls: field.class ? field.class.slice() : null } : null
    this._draw()
  },

  setSelected(index) {
    this._selected = index
    this._draw()
  },

  setSpot(lat, lon) {
    this._spot = lat === null || lat === undefined ? null : { lat, lon }
    this._draw()
  },

  // fn(index) -> array of text lines for the hover tooltip
  setLabeler(fn) {
    this._labeler = fn
  },

  setHandlers({ onPick }) {
    this.options.onPick = onPick
  },

  // for the page: how many points exist / are drawn right now (written on the canvas as data-* attributes)
  setMeta(meta) {
    this._meta = meta
    this._writeMeta()
  },

  _writeMeta() {
    if (!this._canvas) return
    const d = this._canvas.dataset
    d.points = String(this._n)
    d.drawn = String(this._drawn ?? 0)
    d.purpose = this._meta?.purpose ?? ''
    d.species = this._meta?.species ?? ''
    d.context = String(this._cn)
    d.plan = String(this._pn)
    d.planUnconfirmed = String(this._punconf ?? 0)
    d.planDrawn = String(this._pvisible ? (this._pdrawn ?? 0) : 0)
    d.planShapes = String(this._pvisible ? (this._pshapes ?? 0) : 0)
    d.planBubbles = String(this._pvisible ? (this._pbubbles ?? 0) : 0)
    d.planBlocks = String(this._pblocks ? 1 : 0)
    d.planSide = String(Math.round(this._pblocks ? (this._pside ?? 0) : 0))
    d.drawMs = (this._drawMs ?? 0).toFixed(1)
    d.squarePx = (this._half * 2).toFixed(2)
    d.bubbleLabels = (this._clusters ?? []).map((c) => c.label).join('|')
    d.codesShown = String(!!this._codesShown)
    d.groundMode = String(!!(this._groundOn && this._gcls))
    d.groundDrawn = String(this._gdrawn ?? 0)
    d.cornerDrawn = String(this._cornerDrawn ?? 0)
    d.fieldDrawn = String(this._fdrawn ?? 0)
    d.zoom = String(this._map ? this._map.getZoom() : 0)
    d.contextDrawn = String(this._cvisible || (this._groundOn && this._gctxcls) ? (this._cdrawn ?? 0) : 0)
  },

  _update() {
    const map = this._map
    if (!map || !this._canvas) return
    const size = map.getSize()
    const pad = size.multiplyBy(PAD)
    this._topLeft = map.containerPointToLayerPoint(pad.multiplyBy(-1)).round()
    this._w = Math.round(size.x * (1 + 2 * PAD))
    this._h = Math.round(size.y * (1 + 2 * PAD))
    const dpr = window.devicePixelRatio || 1
    this._dpr = dpr
    this._canvas.width = Math.round(this._w * dpr)
    this._canvas.height = Math.round(this._h * dpr)
    this._canvas.style.width = `${this._w}px`
    this._canvas.style.height = `${this._h}px`
    L.DomUtil.setPosition(this._canvas, this._topLeft)
    this._draw()
  },

  _project(mx, my) {
    const map = this._map
    const scale = 256 * Math.pow(2, map.getZoom())
    const o = map.getPixelOrigin()
    return [mx * scale - (o.x + this._topLeft.x), my * scale - (o.y + this._topLeft.y)]
  },

  _draw() {
    const map = this._map
    if (!map || !this._canvas || !this._topLeft) return
    const t0 = performance.now()
    const ctx = this._canvas.getContext('2d')
    ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0)
    ctx.clearRect(0, 0, this._w, this._h)
    this._drawn = 0
    this._fdrawn = 0
    const mPerPx = (156543.03392 * Math.cos((14.69 * Math.PI) / 180)) / Math.pow(2, map.getZoom())
    const cellPx = CELL_M / mPerPx
    const half = cellPx / 2
    this._half = half
    this._radius = Math.max(half, 3)
    this._drawContext(ctx, half, cellPx)
    if (this._n > 0) {
      const scale = 256 * Math.pow(2, map.getZoom())
      const o = map.getPixelOrigin()
      const ox = o.x + this._topLeft.x
      const oy = o.y + this._topLeft.y
      const { _px: px, _py: py, _level: level, _mx: mx, _my: my } = this
      const inView = new Uint8Array(this._n)
      const m = half + 2
      for (let i = 0; i < this._n; i++) {
        const x = mx[i] * scale - ox
        const y = my[i] * scale - oy
        px[i] = x
        py[i] = y
        if (x > -m && y > -m && x < this._w + m && y < this._h + m) {
          inView[i] = 1
          this._drawn++
        }
      }
      // one filled square per grid cell (100 m, scaled with the zoom), no outline; a 1 px gap only when zoomed in
      const gap = cellPx >= GAP_FROM_PX ? 1 : 0
      const gmode = this._groundOn && this._gcls && this._gcls.length === this._n
      this._gdrawn = 0
      ctx.globalAlpha = SQUARE_ALPHA
      const rects = (test) => {
        ctx.beginPath()
        let k = 0
        for (let i = 0; i < this._n; i++) {
          if (inView[i] && test(i)) {
            const x0 = Math.round(px[i] - half)
            const y0 = Math.round(py[i] - half)
            ctx.rect(x0, y0, Math.max(1, Math.round(px[i] + half) - x0 - gap), Math.max(1, Math.round(py[i] + half) - y0 - gap))
            k++
          }
        }
        ctx.fill()
        return k
      }
      if (gmode) {                                                    // ground cover: one fill per class; a pattern too once the squares are big enough to show it
        const pats = cellPx >= 10 ? this._groundPatterns() : null
        GROUND_GROUPS.forEach((g, gi) => {
          ctx.fillStyle = pats ? pats[g] : GROUND_STYLE[g].color
          this._gdrawn += rects((i) => this._gcls[i] === gi)
        })
        ctx.fillStyle = GROUND_MISSING
        this._gdrawn += rects((i) => this._gcls[i] === 255)
      } else {
        for (let lv = 0; lv < LEVEL_COLORS.length; lv++) {
          ctx.fillStyle = LEVEL_COLORS[lv]
          rects((i) => level[i] === lv)
        }
      }
      ctx.globalAlpha = 1
      this._cornerDrawn = 0
      if (this._corners && this._gflags && this._gflags.length === this._n && cellPx >= 10) {
        const sz = Math.min(12, cellPx * 0.3)
        ctx.fillStyle = '#f59e0b'
        ctx.strokeStyle = '#0f172a'
        ctx.lineWidth = 1
        for (let i = 0; i < this._n; i++) {
          if (!inView[i] || !this._gflags[i]) continue
          const rx = px[i] + half - (gap ? 1 : 0)
          const ty = py[i] - half
          ctx.beginPath()
          ctx.moveTo(rx - sz, ty)
          ctx.lineTo(rx, ty)
          ctx.lineTo(rx, ty + sz)
          ctx.closePath()
          ctx.fill()
          ctx.stroke()
          this._cornerDrawn++
        }
      }
      if (this._field) this._drawField(ctx, px, py, Math.min(9, Math.max(3, half * 0.4)))   // symbols stay small however big the squares are
      const sel = this._selected
      if (sel >= 0 && sel < this._n) {
        const h = Math.max(half, 4) + 3
        ctx.lineWidth = 3
        ctx.strokeStyle = '#0f172a'
        ctx.strokeRect(px[sel] - h, py[sel] - h, 2 * h, 2 * h)
        ctx.lineWidth = 1.8
        ctx.strokeStyle = SELECT_COLOR
        ctx.strokeRect(px[sel] - h, py[sel] - h, 2 * h, 2 * h)
      }
    }
    this._drawPlan(ctx)
    if (this._spot) {
      const sx = (this._spot.lon + 180) / 360
      const sy = 0.5 - Math.log(Math.tan(Math.PI / 4 + (this._spot.lat * Math.PI) / 360)) / TWO_PI
      const [x, y] = this._project(sx, sy)
      ctx.fillStyle = '#0b4f9c'
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(x, y, 5, 0, TWO_PI)
      ctx.fill()
      ctx.stroke()
    }
    this._drawMs = performance.now() - t0
    this._writeMeta()
  },

  _drawContext(ctx, half, cellPx) {
    this._cdrawn = 0
    const gmode = this._groundOn && this._gctxcls && this._gctxcls.length === this._cn
    if (!this._cn || !(this._cvisible || gmode)) return
    const map = this._map
    const scale = 256 * Math.pow(2, map.getZoom())
    const o = map.getPixelOrigin()
    const ox = o.x + this._topLeft.x
    const oy = o.y + this._topLeft.y
    this._crc = Math.max(half, 3)
    const { _cpx: px, _cpy: py, _cmx: mx, _cmy: my } = this
    const gap = cellPx >= GAP_FROM_PX ? 1 : 0
    const inView = new Uint8Array(this._cn)
    for (let i = 0; i < this._cn; i++) {
      const x = mx[i] * scale - ox
      const y = my[i] * scale - oy
      px[i] = x
      py[i] = y
      if (x > -half - 2 && y > -half - 2 && x < this._w + half + 2 && y < this._h + half + 2) inView[i] = 1
    }
    const rects = (test) => {
      ctx.beginPath()
      let k = 0
      for (let i = 0; i < this._cn; i++) {
        if (inView[i] && test(i)) {
          const x0 = Math.round(px[i] - half)
          const y0 = Math.round(py[i] - half)
          ctx.rect(x0, y0, Math.max(1, Math.round(px[i] + half) - x0 - gap), Math.max(1, Math.round(py[i] + half) - y0 - gap))
          k++
        }
      }
      ctx.fill()
      return k
    }
    if (gmode) {                                                      // ground-cover layer: the squares that are not planting zones (a quarry, for example) show their class too
      const pats = cellPx >= 10 ? this._groundPatterns() : null
      ctx.globalAlpha = 0.6
      GROUND_GROUPS.forEach((g, gi) => {
        ctx.fillStyle = pats ? pats[g] : GROUND_STYLE[g].color
        this._cdrawn += rects((i) => this._gctxcls[i] === gi)
      })
      ctx.fillStyle = GROUND_MISSING
      this._cdrawn += rects((i) => this._gctxcls[i] === 255)
      ctx.globalAlpha = 1
      return
    }
    ctx.fillStyle = CONTEXT_FILL
    this._cdrawn = rects(() => true)
  },

  _drawField(ctx, px, py, r) {
    const R = Math.max(r + 5, 9)
    const { index, code } = this._field
    const halo = (width, color, draw) => {
      ctx.lineWidth = width
      ctx.strokeStyle = color
      ctx.beginPath()
      draw()
      ctx.stroke()
    }
    this._fdrawn = 0
    for (let k = 0; k < index.length; k++) {
      const i = index[k]
      if (i >= this._n) continue
      const x = px[i]
      const y = py[i]
      if (x < -R || y < -R || x > this._w + R || y > this._h + R) continue
      this._fdrawn++
      const status = code[k] % 4
      const cname = (this._field.cls && this._field.cls[k]) || ({ 1: 'verified', 2: 'not_plantable', 3: 'recheck' })[status]
      const spec = FIELD_CLASSES[cname] ?? FIELD_CLASSES.not_plantable
      const col = spec.color
      if (spec.shape === 'ring') {                                   // plantable (verified): a green ring
        const ring = () => ctx.arc(x, y, R, 0, TWO_PI)
        halo(5, '#ffffff', ring)
        halo(2.5, col, ring)
      } else if (spec.shape === 'check') {                           // planted: a green disc with a white check
        ctx.beginPath()
        ctx.arc(x, y, R, 0, TWO_PI)
        ctx.fillStyle = col
        ctx.fill()
        halo(2, '#ffffff', () => ctx.arc(x, y, R, 0, TWO_PI))
        halo(2.6, '#ffffff', () => {
          ctx.moveTo(x - R * 0.5, y)
          ctx.lineTo(x - R * 0.1, y + R * 0.4)
          ctx.lineTo(x + R * 0.55, y - R * 0.4)
        })
      } else if (spec.shape === 'question') {                        // needs recheck: an amber disc with a white question mark
        ctx.beginPath()
        ctx.arc(x, y, R, 0, TWO_PI)
        ctx.fillStyle = col
        ctx.fill()
        halo(2, '#ffffff', () => ctx.arc(x, y, R, 0, TWO_PI))
        ctx.font = `bold ${Math.round(R * 1.45)}px sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillStyle = '#ffffff'
        ctx.fillText('?', x, y + 1)
        ctx.textAlign = 'start'
        ctx.textBaseline = 'alphabetic'
      } else {                                                       // not plantable: a cross (red; blue for water; gray for paved, building or rock)
        const cross = () => {
          ctx.moveTo(x - R, y - R)
          ctx.lineTo(x + R, y + R)
          ctx.moveTo(x + R, y - R)
          ctx.lineTo(x - R, y + R)
        }
        halo(6, '#ffffff', cross)
        halo(3, col, cross)
      }
      if (code[k] >= 4) {
        ctx.font = 'bold 13px sans-serif'
        ctx.lineWidth = 3
        ctx.strokeStyle = '#ffffff'
        ctx.fillStyle = '#b45309'
        ctx.strokeText('!', x + R, y - R)
        ctx.fillText('!', x + R, y - R)
      }
    }
  },

  // index of the square under a layer point (the nearest centre among the squares that contain it), or -1
  _hit(layerPoint) {
    if (!this._n || !this._topLeft) return -1
    return this._hitSquares(this._px, this._py, this._n, this._radius, layerPoint)
  },

  _hitSquares(px, py, n, half, layerPoint) {
    const x = layerPoint.x - this._topLeft.x
    const y = layerPoint.y - this._topLeft.y
    const lim = half + HIT_EXTRA
    let best = -1
    let bestD = Infinity
    for (let i = 0; i < n; i++) {
      const dx = px[i] - x
      if (dx > lim || dx < -lim) continue
      const dy = py[i] - y
      if (dy > lim || dy < -lim) continue
      const d = dx * dx + dy * dy
      if (d < bestD) {
        bestD = d
        best = i
      }
    }
    return best
  },

  // index of the grey square under a layer point, or -1 (only while that layer is shown)
  _hitContext(layerPoint) {
    if (!this._cn || !(this._cvisible || (this._groundOn && this._gctxcls)) || !this._topLeft) return -1
    return this._hitSquares(this._cpx, this._cpy, this._cn, this._crc, layerPoint)
  },

  _onMove(e) {
    const bub = this._hitBubble(e.layerPoint)
    if (bub) {
      this._map.getContainer().style.cursor = 'pointer'
      if (this._bhover !== bub) {
        this._bhover = bub
        this._hover = -2
        this._chover = -1
        this._phover = -1
        this._showTip(this._map.layerPointToLatLng(L.point(bub.x + this._topLeft.x, bub.y + this._topLeft.y)), [bub.name ? `${bub.name}: ${bub.n} planned ${this._pblocks ? 'blocks' : 'trees'}` : `${bub.n} planned ${this._pblocks ? 'blocks' : 'trees'}`, `Zoom in to see each ${this._pblocks ? 'block' : 'tree'}`])
      }
      return
    }
    this._bhover = null
    const pi = this._hitPlan(e.layerPoint)
    if (pi >= 0) {
      this._map.getContainer().style.cursor = 'pointer'
      if (pi !== this._phover) {
        this._phover = pi
        this._hover = -2
        this._chover = -1
        this._showTip(L.latLng(this._pitems[pi].lat, this._pitems[pi].lon), this._plabeler ? this._plabeler(pi) : [])
      }
      return
    }
    if (this._phover >= 0) this._phover = -1
    const i = this._hit(e.layerPoint)
    const ci = i < 0 ? this._hitContext(e.layerPoint) : -1
    this._map.getContainer().style.cursor = i >= 0 || ci >= 0 ? 'pointer' : ''
    if (i < 0 && ci >= 0) {
      if (ci === this._chover) return
      this._hover = -1
      this._chover = ci
      this._showTip(L.latLng(this._ccols.lat[ci], this._ccols.lon[ci]), this._clabeler ? this._clabeler(ci) : [])
      return
    }
    this._chover = -1
    if (i === this._hover) return
    this._hover = i
    if (i < 0) {
      this._closeTip()
      return
    }
    this._showTip(L.latLng(this._cols.lat[i], this._cols.lon[i]), this._labeler ? this._labeler(i) : [])
  },

  _onOut() {
    this._hover = -1
    this._map.getContainer().style.cursor = ''
    this._closeTip()
  },

  _closeTip() {
    if (this._map && this._tip && this._map.hasLayer(this._tip)) this._map.closeTooltip(this._tip)
  },

  _onClick(e) {
    const bub = this._hitBubble(e.layerPoint)
    if (bub) {                                                          // a bubble: zoom in to its trees
      const pts = bub.members.map((i) => L.latLng(this._pitems[i].lat, this._pitems[i].lon))
      this._closeTip()
      this._map.fitBounds(L.latLngBounds(pts).pad(0.4), { maxZoom: 17, animate: false })
      this._map.setZoom(Math.max(this._map.getZoom(), BUBBLE_BELOW_ZOOM + 0.25), { animate: false })
      return
    }
    const pi = this._hitPlan(e.layerPoint)
    if (pi >= 0) {
      if (this.options.onPick) this.options.onPick({ index: -1, context: -1, plan: pi, lat: e.latlng.lat, lon: e.latlng.lng })
      return
    }
    const i = this._hit(e.layerPoint)
    const ci = i < 0 ? this._hitContext(e.layerPoint) : -1
    if (this.options.onPick) this.options.onPick({ index: i, context: ci, lat: e.latlng.lat, lon: e.latlng.lng })
  },
})

export function createGridLayer() {
  return new GridCanvasLayer({})
}
