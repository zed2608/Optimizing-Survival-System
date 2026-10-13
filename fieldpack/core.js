/* Field pack, Stage A1: the maths, the rules, the saving and the CSV. No page code here, so node can test it; the build script puts this same file into the page.
 * Layout of the trees is NOT worked out here: the build script gives every tree its latitude and longitude from pipeline/palettes.py block_geometry (the ONE layout formula).
 * Everything provisional: GPS accuracy has not been field-tested. */
const FieldPackCore = (function () {
  'use strict'

  const R = 6371000 // the same sphere as distance_m in pipeline/field_verify.py
  const rad = (d) => (d * Math.PI) / 180
  const POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
  const REASONS = ['paved', 'building', 'rock_or_ledge', 'creek_or_waterlogged', 'too_steep', 'existing_tree', 'owner_refused', 'other'] // the words of the kit README and of field_verify.REASONS
  const EXTRA_COLUMNS = ['reason', 'note', 'observer', 'observed_at', 'gps_lat', 'gps_lon', 'gps_accuracy_m', 'tree_log', 'pack_notice'] // appended after the 32 columns of blocks.csv; the dashboard import reads them by name (pack_notice: the prototype warning travels with the results)
  const MIN_ARRIVAL_M = 2

  function distanceM(lat1, lon1, lat2, lon2) {
    const p1 = rad(lat1), p2 = rad(lat2)
    const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(rad(lon2 - lon1) / 2) ** 2
    return 2 * R * Math.asin(Math.sqrt(a))
  }

  // initial bearing from point 1 to point 2, degrees clockwise from north (0 to 360)
  function bearingDeg(lat1, lon1, lat2, lon2) {
    const p1 = rad(lat1), p2 = rad(lat2), dl = rad(lon2 - lon1)
    const y = Math.sin(dl) * Math.cos(p2)
    const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl)
    return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360
  }

  function compassPoint(deg) {
    return POINTS[Math.round((((deg % 360) + 360) % 360) / 45) % 8]
  }

  // how far to turn from where the phone points (heading) to face the target; 0 = straight ahead. null when there is no heading: then only the bearing is shown.
  function turnDeg(bearing, heading) {
    if (heading === null || heading === undefined || !Number.isFinite(heading)) return null
    return (((bearing - heading) % 360) + 360) % 360
  }

  // "arrived" only when the distance is within the larger of 2 m and the accuracy the phone reports. Unknown accuracy: only the 2 m rule, and the point is called approximate.
  function arrival(distance, accuracy, spacing) {
    const known = Number.isFinite(accuracy) && accuracy >= 0
    const radius = Math.max(MIN_ARRIVAL_M, known ? accuracy : 0)
    return {
      arrived: Number.isFinite(distance) && distance <= radius,
      radius,
      accuracyKnown: known,
      approximate: !known || (Number.isFinite(spacing) && accuracy > spacing), // accuracy worse than the tree spacing: the point is only approximate
    }
  }

  // far / close / here, for the walk to the START corner (words, not colour alone). "here" = inside the larger of 2 m and how sure the phone says it is; "close" = within 30 m.
  const CLOSE_M = 30
  function startStatus(distance, accuracy) {
    if (!Number.isFinite(distance)) return null
    const known = Number.isFinite(accuracy) && accuracy >= 0
    if (distance <= Math.max(MIN_ARRIVAL_M, known ? accuracy : 0)) return 'here'
    return distance <= CLOSE_M ? 'close' : 'far'
  }

  // far / close / here for the walk to ONE TREE: "here" is inside half a spacing (never less than 2 m), "close" within 30 m. GPS is only 3 to 10 m good, so this is a hint, the tape decides.
  function treeStatus(distance, spacing) {
    if (!Number.isFinite(distance)) return null
    const half = Number.isFinite(spacing) ? spacing / 2 : 0
    if (distance <= Math.max(MIN_ARRIVAL_M, half)) return 'here'
    return distance <= CLOSE_M ? 'close' : 'far'
  }

  // one adult pace is about 0.75 m: a spacing of 7 m is about 9 paces
  const PACE_M = 0.75
  const paces = (metres) => Math.max(1, Math.round(metres / PACE_M))

  // row and place (both counted from 1) of tree k in a block with perRow trees in a row: tree 1 is row 1 place 1, the row is full after perRow trees
  function rowPlace(k, perRow) {
    return { row: Math.floor((k - 1) / perRow) + 1, place: ((k - 1) % perRow) + 1 }
  }

  // never show more digits than the phone's accuracy supports
  function distanceLabel(distance, accuracy) {
    const known = Number.isFinite(accuracy) && accuracy >= 0
    const step = !known ? 5 : accuracy >= 20 ? 10 : accuracy >= 8 ? 5 : accuracy >= 3 ? 2 : 1
    const v = Math.max(0, Math.round(distance / step) * step)
    return { value: v, step, text: step > 1 ? (v === 0 ? `less than ${step}` : `about ${v}`) : `${v}` }
  }


  // ------------------------------------------------------------------ heading (which way the phone or the person faces): smoothing, uncertainty and the turn cue
  const normDeg = (d) => ((d % 360) + 360) % 360
  // signed shortest turn from angle a to angle b, in degrees, from -180 up to 180 (positive = clockwise = to the right)
  const angleDiff = (a, b) => ((((b - a) % 360) + 540) % 360) - 180

  // low-pass filter on a circle: 359 followed by 1 moves by 2 degrees, never by 358
  function smoothAngle(prev, next, alpha) {
    if (!Number.isFinite(next)) return Number.isFinite(prev) ? prev : null
    if (!Number.isFinite(prev)) return normDeg(next)
    const a = Math.min(1, Math.max(0, alpha))
    return normDeg(prev + a * angleDiff(prev, next))
  }

  // spread of a list of angles in degrees (circular standard deviation): 0 = all the same, large = unstable
  function circularStd(angles) {
    const a = angles.filter(Number.isFinite)
    if (a.length < 2) return 0
    let sx = 0, sy = 0
    for (const d of a) { sx += Math.cos(rad(d)); sy += Math.sin(rad(d)) }
    const r = Math.hypot(sx, sy) / a.length
    if (r < 1e-9) return 180
    return Math.min(180, (Math.sqrt(-2 * Math.log(Math.min(1, r))) * 180) / Math.PI)
  }

  // half-width of the direction cone, degrees: wide for the compass (and wider when it is unstable), narrower for the GPS heading while walking
  function coneHalfAngle(source, std, speed) {
    if (source === 'gps') return Number.isFinite(speed) && speed >= 1.5 ? 12 : 18
    if (source === 'compass') return Number.isFinite(std) && std > 15 ? 50 : 28
    return null
  }

  // what to say to turn from the way you face (heading) to the target (bearing)
  function relativeCue(bearing, heading) {
    if (!Number.isFinite(bearing) || !Number.isFinite(heading)) return null
    const turn = angleDiff(heading, bearing)
    const n = Math.round(Math.abs(turn))
    if (n <= 15) return { kind: 'ahead', deg: n, turn }
    if (n >= 150) return { kind: 'around', deg: n, turn }
    return { kind: turn > 0 ? 'right' : 'left', deg: n, turn }
  }

  // Compass heading in degrees from the three angles of a deviceorientation event (alpha, beta, gamma; absolute = relative to north).
  // Phone held flat (screen up): the way its TOP points (plus the screen rotation). Phone held upright: the way its BACK (camera side) faces. Both come from the W3C rotation matrix.
  function compassHeading(alpha, beta, gamma, screenAngle) {
    if (![alpha, beta, gamma].every(Number.isFinite)) return null
    const a = rad(alpha), b = rad(beta), g = rad(gamma)
    const cA = Math.cos(a), sA = Math.sin(a), cB = Math.cos(b), sB = Math.sin(b), cG = Math.cos(g), sG = Math.sin(g)
    const m12 = -cB * sA, m22 = cA * cB, m32 = sB // device y axis (the top) in east, north, up
    const m13 = cG * sA * sB + cA * sG, m23 = sA * sG - cA * cG * sB // device z axis (out of the screen) east and north parts
    const m33 = cB * cG
    let deg
    if (m33 > 0.5) deg = (Math.atan2(m12, m22) * 180) / Math.PI + (Number.isFinite(screenAngle) ? screenAngle : 0)
    else deg = (Math.atan2(-m13, -m23) * 180) / Math.PI
    return Number.isFinite(deg) ? normDeg(deg) : null
  }

  // heading from one orientation event: iOS gives webkitCompassHeading; Android's absolute event gives alpha / beta / gamma; a relative event (no north) gives nothing
  function headingFromEvent(e, screenAngle) {
    if (!e) return null
    if (typeof e.webkitCompassHeading === 'number' && Number.isFinite(e.webkitCompassHeading)) return normDeg(e.webkitCompassHeading + (Number.isFinite(screenAngle) ? screenAngle : 0))
    if (e.absolute === true || e.type === 'deviceorientationabsolute') return compassHeading(e.alpha, e.beta, e.gamma, screenAngle)
    return null
  }

  // the SVG path of the cone: a pie slice that points up, centre (cx, cy), radius r, half-width in degrees
  function conePath(cx, cy, r, half) {
    const h = rad(Math.min(89, Math.max(1, half)))
    const x1 = cx - r * Math.sin(h), y1 = cy - r * Math.cos(h), x2 = cx + r * Math.sin(h)
    return `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y1.toFixed(2)} Z`
  }

  // ------------------------------------------------------------------ the trees of a block and what has been recorded
  const key = (block, k) => `${block.ref}:${k}`
  const emptyState = () => ({ v: 1, observer: '', trees: {} })

  function progress(block, state) {
    let planted = 0, skipped = 0
    for (const t of block.trees) {
      const r = state.trees[key(block, t[0])]
      if (r && r.s === 'planted') planted++
      else if (r && r.s === 'skipped') skipped++
    }
    return { n: block.n, planted, skipped, todo: block.n - planted - skipped }
  }

  // the next tree without a record, in the order of the README (1..N, row by row, east first); null when every tree has one
  function nextTarget(block, state) {
    for (const t of block.trees) if (!state.trees[key(block, t[0])]) return t[0]
    return null
  }

  function treeOf(block, k) {
    return block.trees.find((t) => t[0] === k) || null
  }

  const clip = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

  // what a block becomes in the results file (the rules of the kit README)
  function decide(block, state) {
    const rec = block.trees.map((t) => ({ k: t[0], r: state.trees[key(block, t[0])] || null }))
    const planted = rec.filter((x) => x.r && x.r.s === 'planted')
    const skipped = rec.filter((x) => x.r && x.r.s === 'skipped')
    const out = { status: '', trees_planted: '', reason: '', note: '' }
    if (planted.length) {
      out.status = 'planted'
      out.trees_planted = String(planted.length)
      if (skipped.length) out.note = clip(`Trees ${skipped.map((x) => x.k).join(', ')} not planted (${[...new Set(skipped.map((x) => x.r.reason))].join(', ')}).`, 480)
    } else if (skipped.length && skipped.length === block.n) {
      const reasons = [...new Set(skipped.map((x) => x.r.reason))]
      const one = reasons.length === 1 ? reasons[0] : 'other'
      out.status = one
      out.reason = one
      out.note = clip(reasons.length === 1 ? `All ${block.n} trees skipped: ${one}.` : `All ${block.n} trees skipped for different reasons: ${reasons.join(', ')}.`, 480)
    }
    return out
  }

  // ------------------------------------------------------------------ the results file
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const fix6 = (x) => (Number.isFinite(x) ? x.toFixed(6) : '')

  // Same 32 columns as blocks.csv in the same order, one row per block, then EXTRA_COLUMNS. A block with no decision keeps status and trees_planted empty (the import skips it).
  // moved_lat and moved_lon stay empty: they mean "where the BLOCK's centre really is" and one tree's position does not tell that.
  function exportCsv(pack, state, nowIso, notice) {
    const header = pack.columns.concat(EXTRA_COLUMNS)
    const lines = [header.map(esc).join(',')]
    for (const b of pack.blocks) {
      const row = Object.assign({}, b.row)
      const d = decide(b, state)
      row.status = d.status
      row.trees_planted = d.trees_planted
      const recs = b.trees.map((t) => ({ k: t[0], r: state.trees[key(b, t[0])] })).filter((x) => x.r)
      const last = recs.length ? recs.reduce((a, c) => (String(c.r.t) > String(a.r.t) ? c : a)) : null
      const withFix = recs.filter((x) => x.r.s === 'planted' && Number.isFinite(x.r.lat))
      const lastPlanted = withFix.length ? withFix.reduce((a, c) => (String(c.r.t) > String(a.r.t) ? c : a)) : null
      row.reason = d.reason
      row.note = d.note
      row.observer = d.status ? state.observer || '' : ''
      row.observed_at = d.status && last ? last.r.t : ''
      row.gps_lat = lastPlanted ? fix6(lastPlanted.r.lat) : ''
      row.gps_lon = lastPlanted ? fix6(lastPlanted.r.lon) : ''
      row.gps_accuracy_m = lastPlanted && Number.isFinite(lastPlanted.r.acc) ? String(Math.round(lastPlanted.r.acc * 10) / 10) : ''
      row.pack_notice = notice || ''
      row.tree_log = recs
        .map((x) => [x.k, x.r.s, x.r.reason || '', fix6(x.r.lat), fix6(x.r.lon), Number.isFinite(x.r.acc) ? Math.round(x.r.acc * 10) / 10 : '', x.r.t || ''].join(':'))
        .join('|')
      lines.push(header.map((c) => esc(row[c])).join(','))
    }
    return lines.join('\r\n') + '\r\n'
  }

  // ------------------------------------------------------------------ saving on the phone only (never throws; a phone that refuses storage still works until the page is closed)
  function makeStore(getStorage, storageKey) {
    let memory = null
    let ok = true
    const st = () => {
      try {
        return getStorage()
      } catch (e) {
        return null
      }
    }
    return {
      load() {
        try {
          const s = st()
          const raw = s ? s.getItem(storageKey) : null
          if (!raw) return memory || emptyState()
          const v = JSON.parse(raw)
          return v && v.v === 1 && v.trees ? v : emptyState()
        } catch (e) {
          ok = false
          return memory || emptyState()
        }
      },
      save(state) {
        memory = state
        try {
          const s = st()
          if (!s) throw new Error('no storage')
          s.setItem(storageKey, JSON.stringify(state))
          ok = true
        } catch (e) {
          ok = false
        }
        return ok
      },
      get ok() {
        return ok
      },
    }
  }

  return { R, REASONS, EXTRA_COLUMNS, POINTS, CLOSE_M, PACE_M, distanceM, bearingDeg, compassPoint, turnDeg, arrival, startStatus, treeStatus, paces, rowPlace, distanceLabel, normDeg, angleDiff, smoothAngle, circularStd, coneHalfAngle, relativeCue, compassHeading, headingFromEvent, conePath,
    progress, nextTarget, treeOf, decide, exportCsv, makeStore, emptyState, key, esc }
})()

if (typeof module !== 'undefined' && module.exports) module.exports = FieldPackCore
