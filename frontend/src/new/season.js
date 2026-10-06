// Planting window helpers for #/new: dates, the months a window covers, wording. Pure functions (no browser APIs), tested with node (season.test.mjs).
// Dates are plain "YYYY-MM-DD" strings; arithmetic is done in UTC so the time zone and daylight saving never shift a day.

export const MONTH_LETTERS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
export const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const MAX_DAYS = 366 // the longest window (the API refuses more)
export const DEFAULT_DAYS = 30 // the default window: today until 30 days later
export const FEW_SPECIES = 10 // with this many species or fewer left by the season filter, a notice offers "Show all species" / "Change dates"

const DAY_MS = 86400000

function parse(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso ?? ''))
  if (!m) return null
  const ms = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return toIso(ms) === iso ? ms : null // rejects 2026-02-30
}

function toIso(ms) {
  const d = new Date(ms)
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
}

// Today's calendar date in the computer's own time zone.
export function localToday(now = new Date()) {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export function addDays(iso, n) {
  const ms = parse(iso)
  return ms === null ? null : toIso(ms + n * DAY_MS)
}

// Length of the window in days, counting both the first and the last day.
export function windowDays(start, end) {
  const a = parse(start)
  const b = parse(end)
  return a === null || b === null ? null : Math.round((b - a) / DAY_MS) + 1
}

export function defaultWindow(today) {
  return { start: today, end: addDays(today, DEFAULT_DAYS) }
}

// { ok, error }: the plain-words rules of the dashboard (the start cannot be in the past, as in the earlier dashboard; the end not before the start; at most 366 days).
export function validateWindow(start, end, today) {
  if (parse(start) === null || parse(end) === null) return { ok: false, error: 'Pick a start date and an end date.' }
  if (start < today) return { ok: false, error: 'The start date cannot be in the past.' }
  if (end < start) return { ok: false, error: 'The end date must be on or after the start date.' }
  const days = windowDays(start, end)
  if (days > MAX_DAYS) return { ok: false, error: `That window is ${days} days; the longest is ${MAX_DAYS} days.` }
  return { ok: true, error: '' }
}

// Month numbers (1-12) the window touches, in calendar order from the start; a window may cross the year end (20 Nov to 20 Feb gives 11, 12, 1, 2).
export function windowMonths(start, end) {
  const a = parse(start)
  const b = parse(end)
  if (a === null || b === null || b < a) return []
  const s = new Date(a)
  const e = new Date(b)
  const out = []
  let y = s.getUTCFullYear()
  let m = s.getUTCMonth() + 1
  while (y < e.getUTCFullYear() || (y === e.getUTCFullYear() && m <= e.getUTCMonth() + 1)) {
    if (!out.includes(m)) out.push(m)
    if (m === 12) {
      y += 1
      m = 1
    } else {
      m += 1
    }
  }
  return out
}

export function formatDay(iso, withYear = false) {
  const ms = parse(iso)
  if (ms === null) return ''
  const d = new Date(ms)
  return `${d.getUTCDate()} ${MONTH_SHORT[d.getUTCMonth()]}${withYear ? ` ${d.getUTCFullYear()}` : ''}`
}

// "6 Oct to 5 Nov" (the year is added when the window crosses into another year).
export function formatRange(start, end) {
  const a = parse(start)
  const b = parse(end)
  if (a === null || b === null) return ''
  const cross = new Date(a).getUTCFullYear() !== new Date(b).getUTCFullYear()
  return `${formatDay(start, cross)} to ${formatDay(end, cross)}`
}

export function monthsText(months) {
  return months.length ? months.map((m) => MONTH_SHORT[m - 1]).join(', ') : 'none'
}

export const SEASON_WORDS = {
  in_season: { word: 'In season', glyph: 'check' },
  partly: { word: 'Partly in season', glyph: 'half' },
  out_of_season: { word: 'Outside best months', glyph: 'close' },
  unknown: { word: 'Season unknown', glyph: 'question' },
}

// The query string every species-listing call carries: the dates and whether out-of-season species are removed ("only") or just labelled ("mark").
export function seasonQuery(win, only) {
  return `start=${win.start}&end=${win.end}&season_filter=${only ? 'only' : 'mark'}`
}

// A window remembered in the browser is used only if it is still valid today (its start may have passed since); otherwise the default.
export function restoreWindow(saved, today) {
  if (saved && typeof saved.start === 'string' && typeof saved.end === 'string' && validateWindow(saved.start, saved.end, today).ok) return { start: saved.start, end: saved.end }
  return defaultWindow(today)
}

export const NEXT_SEASON_DAYS = 60 // the "Jump to the next planting season" button looks for the best window of this many days

// "5;6;7" -> [5, 6, 7]; missing -> null (never guessed).
export function parseMonths(value) {
  if (value === null || value === undefined || String(value).trim() === '') return null
  const out = String(value).replace(/,/g, ';').split(';').map((x) => Number(x.trim())).filter((n) => Number.isInteger(n) && n >= 1 && n <= 12)
  return out.length ? out : null
}

// The best window of `days` days that starts today or later (up to a year ahead): the one in which the most species are fully in season
// (every month of the window is one of the species' planting months). Ties go to the earliest start. Species without planting months never count.
// speciesMonths: one array of month numbers (or null) per species.
export function bestSeasonWindow(speciesMonths, today, days = NEXT_SEASON_DAYS, horizon = MAX_DAYS) {
  const sets = speciesMonths.map((m) => (m ? new Set(m) : null))
  let best = null
  for (let k = 0; k < horizon; k += 1) {
    const start = addDays(today, k)
    const end = addDays(start, days - 1)
    const months = windowMonths(start, end)
    const count = sets.filter((s) => s && months.every((m) => s.has(m))).length
    if (best === null || count > best.count) best = { start, end, count, total: speciesMonths.length }
  }
  return best
}

// "1 May - 29 Jun" (the year is added when the window crosses into another year).
export function formatSpan(start, end) {
  const cross = start.slice(0, 4) !== end.slice(0, 4)
  return `${formatDay(start, cross)} - ${formatDay(end, cross)}`
}

// Shown with every explanation of the season: the planting months are the best months from the species sources, not a ban.
export const BEST_MONTHS_NOTE = 'Best months come from the species sources. You can still plant outside them, but expect more watering and more losses.'

// "1 May - 29 Jun 2027" (both years when the span crosses a year end): the same wording as the planning service uses.
export function formatSpanYear(start, end) {
  if (start.slice(0, 4) !== end.slice(0, 4)) return `${formatDay(start, true)} - ${formatDay(end, true)}`
  return `${formatDay(start)} - ${formatDay(end, true)}`
}

// How the planting dates relate to a forecast that runs from firstDay to lastDay (ISO dates). Returns { covered, overlap, message } in plain words.
export function windowForecastMessage(start, end, firstDay, lastDay, n = 16) {
  const label = formatSpanYear(start, end)
  if (!firstDay || !lastDay) return { covered: false, overlap: null, message: 'The forecast has no days, so your planting dates cannot be compared with it.' }
  if (start > lastDay) return { covered: false, overlap: null, message: `Your planting dates (${label}) are beyond the ${n}-day forecast. The advice below is for the next ${n} days only.` }
  if (end < firstDay) return { covered: false, overlap: null, message: `Your planting dates (${label}) have already passed. The advice below is for the next ${n} days only.` }
  const lo = start > firstDay ? start : firstDay
  const hi = end < lastDay ? end : lastDay
  const overlap = { start: lo, end: hi }
  if (start >= firstDay && end <= lastDay) return { covered: true, overlap, message: `The ${n}-day forecast covers all of your planting dates (${label}).` }
  return { covered: true, overlap, message: `The ${n}-day forecast covers ${formatSpanYear(lo, hi)} of your planting dates (${label}). The rest is outside the forecast, so the advice below is for the next ${n} days only.` }
}

// The status of a campaign from its dates and today: active (today is between start and end, inclusive), upcoming, concluded, or none (no dates saved).
export function campaignStatus(start, end, today) {
  if (!start || !end) return 'none'
  if (start > today) return 'upcoming'
  if (end < today) return 'concluded'
  return 'active'
}

export function formatBytes(n) {
  if (typeof n !== 'number') return 'Data Unavailable'
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / (1024 * 1024)).toFixed(1)} MB`
}
