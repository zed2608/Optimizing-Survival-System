import L from 'leaflet'
import { wLevel } from '../v2/scale.js'

// The grid of scored points, drawn in ONE canvas pass (no per-point React components, no per-point Leaflet objects).
// A custom Leaflet layer: a single <canvas> in the overlay pane, redrawn after every move/zoom. Hover and click are found with
// one pass over the point positions of the current view.

// colour per level: 0 none (grey), 1 poor (red), 2 moderate (orange), 3 good (green). Same colours as the legend swatches.
export const LEVEL_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#2e7d32']
const LEVEL_INDEX = { none: 0, poor: 1, moderate: 2, good: 3 }
const SELECT_COLOR = '#38bdf8'
const TWO_PI = Math.PI * 2
const CELL_M = 100 // the grid spacing, in metres
const MIN_RADIUS = 2.4
const MAX_RADIUS = 13
const RADIUS_PER_CELL = 0.38 // radius as a share of the cell width on screen
const HIT_EXTRA = 4 // extra pixels around a dot that still count as hovering it
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
    this._radius = MIN_RADIUS
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

  // field = { index: [...], status: [...] } of GET /grid (the field-checked points and their codes), or null to hide the symbols.
  // Symbols: 1 verified = ring, 2 not plantable = cross, 3 needs recheck = triangle; +4 (disputed) adds an exclamation mark. Shapes, never colour alone.
  setField(field) {
    this._field = field && field.index.length ? { index: Int32Array.from(field.index), code: Uint8Array.from(field.status) } : null
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
    const ctx = this._canvas.getContext('2d')
    ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0)
    ctx.clearRect(0, 0, this._w, this._h)
    this._drawn = 0
    if (this._n > 0) {
      const scale = 256 * Math.pow(2, map.getZoom())
      const o = map.getPixelOrigin()
      const ox = o.x + this._topLeft.x
      const oy = o.y + this._topLeft.y
      const mPerPx = (156543.03392 * Math.cos((14.69 * Math.PI) / 180)) / Math.pow(2, map.getZoom())
      const r = Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, (CELL_M / mPerPx) * RADIUS_PER_CELL))
      this._radius = r
      const { _px: px, _py: py, _level: level, _mx: mx, _my: my } = this
      const inView = new Uint8Array(this._n)
      for (let i = 0; i < this._n; i++) {
        const x = mx[i] * scale - ox
        const y = my[i] * scale - oy
        px[i] = x
        py[i] = y
        if (x > -r && y > -r && x < this._w + r && y < this._h + r) {
          inView[i] = 1
          this._drawn++
        }
      }
      ctx.lineWidth = 1
      ctx.strokeStyle = 'rgba(255,255,255,0.85)'
      for (let lv = 0; lv < LEVEL_COLORS.length; lv++) {
        ctx.fillStyle = LEVEL_COLORS[lv]
        ctx.beginPath()
        for (let i = 0; i < this._n; i++) {
          if (inView[i] && level[i] === lv) {
            ctx.moveTo(px[i] + r, py[i])
            ctx.arc(px[i], py[i], r, 0, TWO_PI)
          }
        }
        ctx.fill()
        ctx.stroke()
      }
      if (this._field) this._drawField(ctx, px, py, r)
      const sel = this._selected
      if (sel >= 0 && sel < this._n) {
        ctx.lineWidth = 3
        ctx.strokeStyle = '#0f172a'
        ctx.beginPath()
        ctx.arc(px[sel], py[sel], r + 5, 0, TWO_PI)
        ctx.stroke()
        ctx.lineWidth = 2
        ctx.strokeStyle = SELECT_COLOR
        ctx.beginPath()
        ctx.arc(px[sel], py[sel], r + 5, 0, TWO_PI)
        ctx.stroke()
      }
    }
    if (this._spot) {
      const sx = (this._spot.lon + 180) / 360
      const sy = 0.5 - Math.log(Math.tan(Math.PI / 4 + (this._spot.lat * Math.PI) / 360)) / TWO_PI
      const [x, y] = this._project(sx, sy)
      ctx.fillStyle = '#0b4f9c'
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(x, y, 6, 0, TWO_PI)
      ctx.fill()
      ctx.stroke()
    }
    this._writeMeta()
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
    for (let k = 0; k < index.length; k++) {
      const i = index[k]
      if (i >= this._n) continue
      const x = px[i]
      const y = py[i]
      if (x < -R || y < -R || x > this._w + R || y > this._h + R) continue
      const status = code[k] % 4
      if (status === 1) {
        const ring = () => ctx.arc(x, y, R, 0, TWO_PI)
        halo(5, '#ffffff', ring)
        halo(2.5, '#064e3b', ring)
      } else if (status === 2) {
        const cross = () => {
          ctx.moveTo(x - R, y - R)
          ctx.lineTo(x + R, y + R)
          ctx.moveTo(x + R, y - R)
          ctx.lineTo(x - R, y + R)
        }
        halo(6, '#ffffff', cross)
        halo(3, '#7f1d1d', cross)
      } else if (status === 3) {
        const tri = () => {
          ctx.moveTo(x, y - R - 1)
          ctx.lineTo(x + R + 1, y + R)
          ctx.lineTo(x - R - 1, y + R)
          ctx.closePath()
        }
        halo(5, '#ffffff', tri)
        halo(2.5, '#78350f', tri)
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

  // index of the point under a layer point (the nearest one within the dot radius), or -1
  _hit(layerPoint) {
    if (!this._n || !this._topLeft) return -1
    const x = layerPoint.x - this._topLeft.x
    const y = layerPoint.y - this._topLeft.y
    const lim = (this._radius + HIT_EXTRA) ** 2
    let best = -1
    let bestD = lim
    const { _px: px, _py: py } = this
    for (let i = 0; i < this._n; i++) {
      const dx = px[i] - x
      if (dx > 20 || dx < -20) continue
      const d = dx * dx + (py[i] - y) ** 2
      if (d <= bestD) {
        bestD = d
        best = i
      }
    }
    return best
  },

  _onMove(e) {
    const i = this._hit(e.layerPoint)
    this._map.getContainer().style.cursor = i >= 0 ? 'pointer' : ''
    if (i === this._hover) return
    this._hover = i
    if (i < 0) {
      this._closeTip()
      return
    }
    const lines = this._labeler ? this._labeler(i) : []
    const el = document.createElement('div')
    lines.forEach((t, k) => {
      const row = document.createElement(k === 0 ? 'strong' : 'div')
      row.textContent = t
      el.appendChild(row)
    })
    this._tip.setLatLng(L.latLng(this._cols.lat[i], this._cols.lon[i]))
    this._tip.setContent(el)
    if (!this._map.hasLayer(this._tip)) this._map.openTooltip(this._tip)
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
    const i = this._hit(e.layerPoint)
    if (this.options.onPick) this.options.onPick({ index: i, lat: e.latlng.lat, lon: e.latlng.lng })
  },
})

export function createGridLayer() {
  return new GridCanvasLayer({})
}
