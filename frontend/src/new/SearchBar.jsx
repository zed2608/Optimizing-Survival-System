import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { apiGet } from '../v2/api.js'
import { useApi } from '../v2/useApi.js'
import { parseCoordinates } from './coords.js'

const MIN_CHARS = 2 // suggestions start after this many characters
const DELAY_MS = 250 // wait for a pause in typing
const GROUP_LIMIT = 5
const RECENT_KEY = 'nw-recent-searches'
const RECENT_MAX = 8
const ATTRIBUTION_FALLBACK = 'Search data (c) OpenStreetMap contributors'

const GROUP_TITLE = { coords: 'Coordinates', barangay: 'Barangays', species: 'Species', point: 'Planting points', place: 'Places' }

function readRecent() {
  try {
    const v = JSON.parse(window.localStorage.getItem(RECENT_KEY) ?? '[]')
    return Array.isArray(v) ? v.filter((x) => x && x.item && x.item.type).slice(0, RECENT_MAX) : []
  } catch {
    return []
  }
}
function writeRecent(list) {
  try {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(list))
  } catch {
    /* storage may be blocked: recent searches are only a convenience */
  }
}

// How one result is shown: icon, main line, second line, and which group it belongs to.
function describe(it) {
  switch (it.type) {
    case 'coords':
      return { group: 'coords', icon: '⌖', label: `Go to ${it.lat.toFixed(5)}, ${it.lon.toFixed(5)}`, sub: it.note || 'Mark this spot and rank species for it' }
    case 'barangay':
      return { group: 'barangay', icon: '▦', label: it.display_name ?? it.name, sub: `Barangay · ${it.legal_points ?? 0} planting points` }
    case 'species':
      return { group: 'species', icon: '❦', label: it.common_name, sub: it.scientific_name ? `Species · ${it.scientific_name}` : 'Species' }
    case 'grid_point':
      return { group: 'point', icon: '●', label: `Grid point ${it.point_id}`, sub: `${it.barangay_display || 'Outside the barangay outlines'} · ${it.legal_zone ? 'planting zone' : 'not a planting zone'}` }
    case 'plan_point':
      return { group: 'point', icon: '◉', label: `${it.point_ref} · ${it.species}`, sub: `Plan ${it.plan_id} · ${it.barangay_display || 'barangay unknown'}` }
    case 'place':
      return { group: 'place', icon: '⚑', label: it.name || it.display_name, sub: it.display_name }
    default:
      return { group: 'point', icon: '•', label: String(it.type), sub: '' }
  }
}

function looksLikeCoordinates(t) {
  return /^[\d\s.,;°+\-NSEWnsew]+$/.test(t) && (t.match(/\d+(?:\.\d+)?/g) ?? []).length >= 2
}

// The search box at the top of the map. Suggestions come from GET /search/all after 2 characters and a short pause; coordinates are read in the
// browser (coords.js); streets and landmarks (GET /search/geocode) are asked only when Enter is pressed on that row and only if the API says
// the optional place search is on. Calls onChoose(item); the page decides what to do.
export default function SearchBar({ onChoose, note, onDismissNote }) {
  const uid = useId()
  const listId = `${uid}-list`
  const [text, setText] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [recent, setRecent] = useState(readRecent)
  const [places, setPlaces] = useState(null) // {q, status: 'loading'|'ok'|'error', results, error, attribution}
  const placeCtl = useRef(null)
  const inputRef = useRef(null)

  const trimmed = text.trim()
  useEffect(() => {
    const t = setTimeout(() => setDebounced(trimmed), DELAY_MS)
    return () => clearTimeout(t)
  }, [trimmed])

  const coords = useMemo(() => (trimmed ? parseCoordinates(trimmed) : { ok: false }), [trimmed])
  const wantCall = debounced.length >= MIN_CHARS && debounced === trimmed && !coords.ok
  const all = useApi(wantCall ? `/search/all?q=${encodeURIComponent(debounced)}&limit=${GROUP_LIMIT}` : null)
  const geocoderOn = all.status === 'ok' && all.data.geocoder_enabled === true

  // the flat list of choices, in the order shown
  const rows = useMemo(() => {
    const out = []
    if (coords.ok) out.push({ ...coords, type: 'coords' })
    if (all.status === 'ok') {
      const d = all.data
      out.push(...d.barangays, ...d.species, ...d.points, ...d.plan_points)
    }
    if (places && places.q === trimmed && places.status === 'ok') out.push(...places.results.map((r) => ({ ...r, type: 'place', attribution: places.attribution })))
    return out.map((it) => ({ it, ...describe(it) }))
  }, [coords, all.status, all.data, places, trimmed])
  const showHint = geocoderOn && trimmed.length >= 3 && !(places && places.q === trimmed)
  const showRecent = open && trimmed.length < MIN_CHARS && recent.length > 0

  function remember(it) {
    const key = JSON.stringify([it.type, it.name, it.species_id, it.point_id, it.point_ref, it.plan_id, it.lat, it.lon])
    const next = [{ key, item: it }, ...recent.filter((r) => r.key !== key)].slice(0, RECENT_MAX)
    setRecent(next)
    writeRecent(next)
  }

  function choose(it) {
    remember(it)
    setText(describe(it).label.replace(/^Go to /, ''))
    setOpen(false)
    setActive(-1)
    onChoose(it)
  }

  function runPlaceSearch() {
    if (trimmed.length < 3) return
    placeCtl.current?.abort()
    const ctl = new AbortController()
    placeCtl.current = ctl
    const q = trimmed
    setPlaces({ q, status: 'loading', results: [], error: '' })
    apiGet(`/search/geocode?q=${encodeURIComponent(q)}`, ctl.signal).then(
      (r) => setPlaces({ q, status: 'ok', results: r.results, attribution: r.attribution ?? ATTRIBUTION_FALLBACK, stale: r.stale, error: '' }),
      (e) => {
        if (e?.name !== 'AbortError') setPlaces({ q, status: 'error', results: [], error: e.message })
      },
    )
  }

  function clear() {
    placeCtl.current?.abort()
    setText('')
    setDebounced('')
    setPlaces(null)
    setActive(-1)
    setOpen(true)
    inputRef.current?.focus()
  }

  const slots = showRecent ? recent.length : rows.length + (showHint ? 1 : 0)
  function onKeyDown(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      if (slots === 0) return
      setActive((a) => (e.key === 'ArrowDown' ? (a + 1) % slots : (a - 1 + slots) % slots))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (showRecent) {
        if (active >= 0) choose(recent[active].item)
      } else if (active >= 0 && active < rows.length) choose(rows[active].it)
      else if ((active === rows.length || rows.length === 0) && showHint) runPlaceSearch()
      else if (active < 0 && rows.length > 0) choose(rows[0].it)
    } else if (e.key === 'Escape') {
      if (open) setOpen(false)
      else if (text) clear()
    }
  }

  const noResults = open && !showRecent && wantCall && all.status === 'ok' && rows.length === 0 && !(places && places.q === trimmed)
  const loading = open && !showRecent && wantCall && all.status === 'loading'
  const failed = open && !showRecent && all.status === 'error'
  const coordProblem = open && trimmed.length >= MIN_CHARS && !coords.ok && looksLikeCoordinates(trimmed) && coords.reason
  const placeBusy = places?.q === trimmed && places.status === 'loading'
  const placeFail = places?.q === trimmed && places.status === 'error'
  const placeEmpty = places?.q === trimmed && places.status === 'ok' && places.results.length === 0
  const attribution = places?.q === trimmed && places.status === 'ok' && places.results.length > 0 ? places.attribution : ''

  // group the visible rows (they are already in group order) for headings
  const headings = new Map()
  rows.forEach((r, i) => {
    if (!headings.has(r.group)) headings.set(r.group, i)
  })
  const firstOfGroup = new Map([...headings].map(([g, i]) => [i, g]))
  const activeId = active >= 0 ? `${uid}-opt-${active}` : undefined
  const panelOpen = open && (showRecent || trimmed.length >= MIN_CHARS)

  return (
    <div className="nw-search" role="search">
      <div className="nw-search-box">
        <span className="nw-search-icon" aria-hidden="true">
          ⌕
        </span>
        <input
          ref={inputRef}
          className="nw-search-input"
          type="text"
          role="combobox"
          aria-label="Search the map"
          aria-expanded={panelOpen}
          aria-controls={listId}
          aria-activedescendant={activeId}
          aria-autocomplete="list"
          autoComplete="off"
          spellCheck="false"
          placeholder="Search barangay, species, point, coordinates…"
          value={text}
          maxLength={100}
          onChange={(e) => {
            setText(e.target.value)
            setOpen(true)
            setActive(-1)
            setPlaces(null)
          }}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {text && (
          <button type="button" className="nw-search-clear" aria-label="Clear search" onMouseDown={(e) => e.preventDefault()} onClick={clear}>
            ✕
          </button>
        )}
      </div>

      {panelOpen && (
        <div className="nw-search-list" id={listId} role="listbox" aria-label="Search suggestions" onMouseDown={(e) => e.preventDefault()}>
          {showRecent && (
            <>
              <div className="nw-search-head">
                <span>Recent searches</span>
                <button
                  type="button"
                  className="nw-search-link"
                  onClick={() => {
                    setRecent([])
                    writeRecent([])
                  }}
                >
                  Clear
                </button>
              </div>
              {recent.map((r, i) => {
                const d = describe(r.item)
                return (
                  <div key={r.key} id={`${uid}-opt-${i}`} role="option" aria-selected={active === i} className={`nw-search-opt ${active === i ? 'is-active' : ''}`} onClick={() => choose(r.item)}>
                    <span className="nw-search-ico" aria-hidden="true">
                      ↺
                    </span>
                    <span>
                      <span className="nw-search-main">{d.label}</span>
                      <span className="nw-search-sub">{d.sub}</span>
                    </span>
                  </div>
                )
              })}
            </>
          )}

          {!showRecent &&
            rows.map((r, i) => (
              <div key={`${r.group}-${i}`}>
                {firstOfGroup.has(i) && (
                  <div className="nw-search-head" role="presentation">
                    {GROUP_TITLE[r.group]}
                  </div>
                )}
                <div id={`${uid}-opt-${i}`} role="option" aria-selected={active === i} className={`nw-search-opt ${active === i ? 'is-active' : ''}`} onClick={() => choose(r.it)}>
                  <span className="nw-search-ico" aria-hidden="true">
                    {r.icon}
                  </span>
                  <span>
                    <span className="nw-search-main">{r.label}</span>
                    <span className="nw-search-sub">{r.sub}</span>
                  </span>
                </div>
              </div>
            ))}

          {!showRecent && showHint && (
            <>
              <div className="nw-search-head" role="presentation">
                {GROUP_TITLE.place}
              </div>
              <div id={`${uid}-opt-${rows.length}`} role="option" aria-selected={active === rows.length} className={`nw-search-opt ${active === rows.length ? 'is-active' : ''}`} onClick={runPlaceSearch}>
                <span className="nw-search-ico" aria-hidden="true">
                  ⚑
                </span>
                <span>
                  <span className="nw-search-main">Search streets and landmarks for “{trimmed}”</span>
                  <span className="nw-search-sub">Press Enter on this row. Uses OpenStreetMap, once per search.</span>
                </span>
              </div>
            </>
          )}
          {placeBusy && <div className="nw-search-msg">Searching places…</div>}
          {placeFail && <div className="nw-search-msg nw-search-bad">{places.error}</div>}
          {placeEmpty && <div className="nw-search-msg">No streets or landmarks found for “{trimmed}” inside San Mateo.</div>}
          {attribution && <div className="nw-search-attr">{attribution}</div>}

          {loading && <div className="nw-search-msg">Searching…</div>}
          {failed && <div className="nw-search-msg nw-search-bad">Search is not available: {all.error.message}</div>}
          {coordProblem && <div className="nw-search-msg nw-search-bad">{coords.reason}</div>}
          {noResults && !coordProblem && (
            <div className="nw-search-msg">
              <strong>No results for “{trimmed}”.</strong>
              <br />
              Try a barangay (Santa Ana, Sto Niño), a species (Narra), coordinates (14.69, 121.12 or 296799 1625091), a grid point number (832) or a plan point (DUH-012).
            </div>
          )}
        </div>
      )}

      {note && (
        <div className="nw-search-note" role="status">
          <div>
            <strong>{note.title}</strong>
            {note.lines.map((l) => (
              <div key={l}>{l}</div>
            ))}
            {note.attribution && <div className="nw-search-attr">{note.attribution}</div>}
          </div>
          <button type="button" className="nw-search-clear" aria-label="Dismiss this note" onClick={onDismissNote}>
            ✕
          </button>
        </div>
      )}
    </div>
  )
}
