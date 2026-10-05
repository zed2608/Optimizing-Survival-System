import { useMemo, useState } from 'react'
import '../v2/v2.css'
import './new.css'
import ColorLegend from '../v2/components/ColorLegend.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { RANK_LIMIT } from '../v2/config.js'
import { purposeLabel } from '../v2/labels.js'
import { LEVEL_WORD, wLevel } from '../v2/scale.js'
import { useApi } from '../v2/useApi.js'
import AreaChooser from './AreaChooser.jsx'
import AreaResultPanel from './AreaResultPanel.jsx'
import AreasPanel from './AreasPanel.jsx'
import { decodeFieldCode, STATUS_LABEL, STATUS_SYMBOL } from './fieldLabels.js'
import { featureAt, geometryBbox, polygonFromVertices } from './geo.js'
import { PURPOSE_SHORT } from './labelsNew.js'
import MoreMenu from './MoreMenu.jsx'
import MapViewMenu from './MapViewMenu.jsx'
import PlantingWindow from './PlantingWindow.jsx'
import PointRanking from './PointRanking.jsx'
import Segmented from './Segmented.jsx'
import SpeciesCard from './SpeciesCard.jsx'
import VerifyBar from './VerifyBar.jsx'
import MapNew from './MapNew.jsx'
import ModeSwitch from './ModeSwitch.jsx'
import PurposePicker from './PurposePicker.jsx'
import RightPanel from './RightPanel.jsx'
import SearchBar from './SearchBar.jsx'
import { FEW_SPECIES, formatDay, formatRange, monthsText, seasonQuery, windowMonths } from './season.js'
import SeasonNotice from './SeasonNotice.jsx'
import SidebarStep from './SidebarStep.jsx'
import SpeciesMultiPicker from './SpeciesMultiPicker.jsx'
import { useObserver } from './useObserver.js'
import { usePost } from './usePost.js'
import { useOnlySeason, usePlantingWindow } from './useWindow.js'

const TABS = [
  { id: 'studio', label: '𖥠 Active Studio' },
  { id: 'history', label: '🕮 Campaign Logs' },
  { id: 'analytics', label: '🗠 System Analytics' },
]

// The revamped dashboard (open it with #/new). Two ways in:
//   "I have species - find areas": choose species -> the map shows where they suit, barangays and zones are ranked.
//   "I have an area - find species": choose an area (point, barangay, zone or a drawn shape) -> its species are ranked, with a suggested mix.
// The top bar, tabs and sidebar copy the look of the earlier dashboard (App.legacy.jsx).
export default function AppNew() {
  const [mode, setMode] = useState('species')
  const [purpose, setPurpose] = useState('urban')
  const [selIds, setSelIds] = useState([]) // mode 1: chosen species
  const [combine, setCombine] = useState('all') // mode 1: 'all' | 'any'
  const [rowActive, setRowActive] = useState(null) // mode 1: the clicked table row {kind, name}
  const [planPrefill, setPlanPrefill] = useState(null)
  const [tool, setTool] = useState('point') // mode 2: 'point' | 'barangay' | 'draw'
  const [area, setArea] = useState(null) // mode 2: {kind:'barangay'|'zone', name} | {kind:'polygon', geometry}
  const [draft, setDraft] = useState([]) // mode 2: corners of the shape being drawn, [lat, lon]
  const [notice, setNotice] = useState('')
  const [spot, setSpot] = useState(null) // the clicked point {lat, lon}
  const [viableFor, setViableFor] = useState(null)
  const [goTarget, setGoTarget] = useState(null)
  const [fitTarget, setFitTarget] = useState(null)
  const [panelTab, setPanelTab] = useState('main')
  const [hidden, setHidden] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [openStep, setOpenStep] = useState('goal') // the one open step of the sidebar
  const [baseLayer, setBaseLayer] = useState('satellite')
  const [cardId, setCardId] = useState(null) // the species whose information card is open
  const win = usePlantingWindow()
  const [onlySeason, setOnlySeason] = useOnlySeason()
  const [tab, setTab] = useState('studio')
  const [fieldVersion, setFieldVersion] = useState(0) // bumped after every saved field check: reloads what depends on them (and skips the browser cache)
  const [showField, setShowField] = useState(true)
  const [observer, setObserver] = useObserver()
  const [searchNote, setSearchNote] = useState(null) // what the last search result was (shown under the search box)

  const health = useApi('/health')
  const boundaries = useApi('/geo/boundaries')
  const zones = useApi('/geo/zones')
  const sq = seasonQuery(win.applied, onlySeason) // the dates (and 'only' or 'mark') that every species-listing call carries
  const species = useApi(`/species?${seasonQuery(win.applied, false)}`) // all species, each with its season (the toggle hides the out-of-season ones here)

  const idsParam = [...selIds].sort((a, b) => a - b).join(',')
  const selection = mode === 'species' && selIds.length > 0
  const fc = `fc=${fieldVersion}`
  const grid = useApi(selection ? `/grid?purpose=${purpose}&species_ids=${idsParam}&mode=${combine}&${fc}&${sq}` : `/grid?purpose=${purpose}&${fc}&${sq}`)
  const areasQuery = selection ? `purpose=${purpose}&species_ids=${idsParam}&mode=${combine}&${fc}&${sq}` : null
  const byBarangay = useApi(areasQuery ? `/areas/rank?${areasQuery}&by=barangay` : null)
  const byZone = useApi(areasQuery ? `/areas/rank?${areasQuery}&by=zone` : null)
  const areaBody = useMemo(() => {
    if (mode !== 'area' || !area) return null
    const base = { purpose, limit: RANK_LIMIT, fc: fieldVersion }
    if (area.kind === 'barangay') return { ...base, barangay: area.name }
    if (area.kind === 'zone') return { ...base, zone: area.name }
    return { ...base, polygon: area.geometry }
  }, [mode, area, purpose, fieldVersion])
  const areaRank = usePost(`/rank/area?${sq}`, areaBody)
  const spotQuery = spot ? `purpose=${purpose}&lat=${spot.lat.toFixed(6)}&lon=${spot.lon.toFixed(6)}&${fc}&${sq}` : null
  const rank = useApi(spotQuery ? `/rank?${spotQuery}&limit=${RANK_LIMIT}&include_left_out=true` : null)
  const viable = useApi(spotQuery && viableFor === spotQuery ? `/nearest-viable?${spotQuery}` : null)
  const pointId = spot ? (spot.pointId ?? (rank.status === 'ok' ? rank.data.point.point_id : null)) : null
  const fieldPoint = useApi(pointId ? `/field-checks/${pointId}?${fc}` : null)
  const fieldSummary = useApi(`/field-checks/summary?${fc}`)
  const bumpField = () => setFieldVersion((v) => v + 1)

  const barangayFeatures = useMemo(() => (boundaries.data?.features ?? []).filter((f) => f.properties.kind === 'barangay'), [boundaries.data])
  const zoneFeatures = useMemo(() => zones.data?.features ?? [], [zones.data])
  const speciesNames = useMemo(() => new Map((species.data?.species ?? []).map((s) => [s.species_id, s.common_name])), [species.data])
  const selNames = useMemo(() => selIds.map((id) => speciesNames.get(id) ?? `species ${id}`), [selIds, speciesNames])
  const columns = grid.data?.columns ?? null
  const indexById = useMemo(() => new Map((columns?.point_id ?? []).map((id, i) => [id, i])), [columns])
  const selected = rank.status === 'ok' ? (indexById.get(rank.data.point.point_id) ?? -1) : -1
  const sInfo = species.status === 'ok' ? species.data.season : null
  const kept = sInfo ? (onlySeason ? sInfo.species_total - sInfo.out_of_season : sInfo.species_total) : null
  const fewSpecies = onlySeason && kept !== null && kept <= FEW_SPECIES
  const selectedRemoved = selection ? (grid.data?.season?.selected_removed_ids ?? []) : []
  const allRemoved = selection && selectedRemoved.length === selIds.length
  const showAllSpecies = () => setOnlySeason(false)
  const changeDates = () => {
    setSidebarOpen(true)
    setOpenStep('window')
    setTimeout(() => document.getElementById('nw-start')?.focus(), 80)
  }
  const seasonNotice = (light, text = '') =>
    sInfo && (
      <SeasonNotice light={light} text={text} kept={kept} total={sInfo.species_total} start={win.applied.start} end={win.applied.end} onShowAll={showAllSpecies} onChangeDates={changeDates} />
    )
  const noneSuitable = useMemo(() => !!columns && selection && columns.W.every((w) => w === 0), [columns, selection])

  const highlight = useMemo(() => {
    const spec = mode === 'area' ? area : rowActive
    if (!spec) return null
    if (spec.kind === 'polygon') return spec.geometry
    return (spec.kind === 'barangay' ? barangayFeatures : zoneFeatures).find((f) => f.properties.name === spec.name)?.geometry ?? null
  }, [mode, area, rowActive, barangayFeatures, zoneFeatures])

  // hover text: barangay and score of the point under the mouse
  const labeler = useMemo(() => {
    if (!grid.data) return null
    const g = grid.data
    const fieldAt = new Map((g.field?.index ?? []).map((idx, k) => [idx, g.field.status[k]]))
    return (i) => {
      const c = g.columns
      const b = c.barangay[i]
      const w = c.W[i]
      const sid = c.best_species_id[i]
      const sname = sid >= 0 ? (speciesNames.get(sid) ?? `species ${sid}`) : null
      const label = { all: 'Limiting species', any: 'Best of the selected', single: 'Species', best: 'Best species' }[g.mode]
      const lines = [
        `Barangay: ${b >= 0 ? g.barangays_display[b] : 'Data Unavailable'}`,
        w > 0 ? `Score W ${w.toFixed(2)} (${LEVEL_WORD[wLevel(w, true)]})` : 'Not suitable here (score 0)',
        sname ? `${label}: ${sname}` : null,
      ]
      if (g.mode === 'all' || g.mode === 'any') lines.push(`${c.n_eligible_species[i]} of ${g.species_ids.length} selected species suit this point`)
      if (fieldAt.has(i)) {
        const f = decodeFieldCode(fieldAt.get(i))
        lines.push(`Field check: ${STATUS_SYMBOL[f.status]} ${STATUS_LABEL[f.status]}${f.disputed ? ' (disputed)' : ''}${f.status === 'not_plantable' ? ' - left out' : ''}`)
      }
      return lines.filter(Boolean)
    }
  }, [grid.data, speciesNames])

  const reveal = () => setHidden(false)
  const featureOf = (kind, name) => (kind === 'barangay' ? barangayFeatures : zoneFeatures).find((f) => f.properties.name === name)

  const chooseArea = (a) => {
    setArea(a)
    setNotice('')
    setHidden(false)
    setPanelTab('main')
    if (a && a.kind !== 'polygon') {
      const f = featureOf(a.kind, a.name)
      if (f) setFitTarget({ bbox: f.properties.bbox })
    }
  }
  const selectRow = (kind, row) => {
    setRowActive({ kind, name: row.name })
    setFitTarget({ bbox: row.bbox })
    setPanelTab('main')
    reveal()
  }
  const planHere = (kind, row) => setPlanPrefill({ purpose, speciesIds: selIds, speciesNames: selNames, combine, area: { kind, name: row.display_name, key: row.name } })

  const onPick = ({ index, lat, lon }) => {
    if (mode === 'area' && tool === 'draw') {
      setDraft((d) => [...d, [lat, lon]])
      return
    }
    if (mode === 'area' && tool === 'barangay') {
      const f = featureAt(barangayFeatures, lon, lat)
      if (f) chooseArea({ kind: 'barangay', name: f.properties.name })
      else setNotice('There is no barangay at that spot. Click inside an outline.')
      return
    }
    setSpot(columns && index >= 0 ? { lat: columns.lat[index], lon: columns.lon[index], pointId: columns.point_id[index] } : { lat, lon })
    setPanelTab('point')
    setHidden(false)
    setNotice('')
  }
  const goTo = (lat, lon) => {
    setSpot({ lat, lon })
    setGoTarget({ lat, lon })
  }
  // The search box chose something. Barangay -> mode 2 with that barangay; species -> mode 1 with that species; a coordinate, grid point, plan point
  // or place -> jump there, mark it and open its ranking.
  const onSearchChoose = (it) => {
    setSearchNote(null)
    if (it.type === 'barangay') {
      changeMode('area')
      setTool('barangay')
      chooseArea({ kind: 'barangay', name: it.name })
      if (it.bounds) setFitTarget({ bbox: it.bounds })
      setSearchNote({ title: it.display_name ?? it.name, lines: ['Barangay outline highlighted. The species ranked for it are in the panel on the right.'] })
      return
    }
    if (it.type === 'species') {
      setCardId(it.species_id)
      setSearchNote({ title: it.common_name, lines: ['The species card is open. “Find areas for this species” switches the map to it.'] })
      return
    }
    const pointId = it.type === 'plan_point' || (it.type === 'grid_point' && it.legal_zone) ? it.point_id : undefined
    setSpot({ lat: it.lat, lon: it.lon, ...(pointId ? { pointId } : {}) })
    setGoTarget({ lat: it.lat, lon: it.lon })
    setPanelTab('point')
    setHidden(false)
    setNotice('')
    if (it.type === 'plan_point') {
      setSearchNote({ title: `${it.point_ref} · ${it.species}`, lines: [`Plan ${it.plan_id}`, `Grid point ${it.point_id}${it.barangay_display ? ' · ' + it.barangay_display : ''}`] })
    } else if (it.type === 'grid_point') {
      setSearchNote({ title: `Grid point ${it.point_id}`, lines: [it.note ?? `${it.barangay_display || 'Outside the barangay outlines'} · ${it.zone}`] })
    } else if (it.type === 'place') {
      setSearchNote({ title: it.name || it.display_name, lines: [it.display_name], attribution: it.attribution })
    } else {
      setSearchNote({ title: `${it.lat.toFixed(5)}, ${it.lon.toFixed(5)}`, lines: [it.note || 'Marked on the map. If it is outside San Mateo or not a planting zone, the panel says so and offers the nearest suitable spot.'] })
    }
  }
  const finishDraw = () => {
    if (draft.length < 3) return
    chooseArea({ kind: 'polygon', geometry: polygonFromVertices(draft) })
    setFitTarget({ bbox: geometryBbox(polygonFromVertices(draft)) })
    setDraft([])
  }
  const changeMode = (m) => {
    setMode(m)
    setPanelTab('main')
    setHidden(false)
    setTool('point')
    setDraft([])
    setNotice('')
  }
  const toggleStep = (id) => setOpenStep((o) => (o === id ? '' : id))
  const changeTool = (t) => {
    setTool(t)
    if (t !== 'draw') setDraft([])
    setNotice('')
  }

  const hasMain = mode === 'species' ? selection : !!area
  const hasPoint = !!spot
  const activeTab = panelTab === 'main' && !hasMain ? 'point' : panelTab === 'point' && !hasPoint ? 'main' : panelTab
  const showPanel = (hasMain || hasPoint) && !hidden
  const tabs = [...(hasMain ? [{ id: 'main', label: mode === 'species' ? 'Areas' : 'Area species' }] : []), ...(hasPoint ? [{ id: 'point', label: 'This point' }] : [])]
  const areaLabel = !area ? '' : area.kind === 'polygon' ? 'the drawn area' : (featureOf(area.kind, area.name)?.properties.display_name ?? area.name)

  const fieldForMap = showField ? (grid.data?.field ?? null) : null
  const meta = useMemo(() => ({ purpose, species: selection ? idsParam : '' }), [purpose, selection, idsParam])
  const apiState = health.status === 'ok' ? 'ok' : health.status === 'loading' ? 'wait' : 'off'
  const legendSub = allRemoved
    ? 'The chosen species are out of season for your dates'
    : selection
    ? `${selIds.length === 1 ? selNames[0] : `${selIds.length} species`} · ${selIds.length === 1 ? 'one species' : combine === 'all' ? 'must suit all' : 'suits at least one'}`
    : 'Best species at each point'

  return (
    <div className={`nw-root ${showPanel ? 'panel-open' : ''} ${sidebarOpen ? 'sidebar-open' : ''}`}>
      <div className="nw-map">
        <MapNew
          bbox={boundaries.data?.bbox ?? null}
          boundaries={boundaries.data}
          grid={columns}
          clearGrid={grid.status === 'error'}
          labeler={labeler}
          selected={selected}
          spot={spot}
          onPick={onPick}
          meta={meta}
          goTarget={goTarget}
          fitTarget={fitTarget}
          highlight={highlight}
          draft={draft}
          drawing={mode === 'area' && tool === 'draw'}
          field={fieldForMap}
          baseLayer={baseLayer}
        />
      </div>

      <MapViewMenu baseLayer={baseLayer} onBaseLayer={setBaseLayer} showField={showField} onShowField={setShowField} />
      <SearchBar onChoose={onSearchChoose} note={searchNote} onDismissNote={() => setSearchNote(null)} />

      {/* messages over the map */}
      <div className="nw-toasts v2 v2-embedded">
        {grid.status === 'loading' && <Loading what="Loading the grid points" />}
        {grid.status === 'error' && <ErrorBox error={grid.error} onRetry={grid.retry} title="Could not load the grid points" />}
        {fewSpecies && seasonNotice(true)}
        {boundaries.status === 'error' && !boundaries.error.network && <ErrorBox error={boundaries.error} onRetry={boundaries.retry} title="Could not load the outlines" brief />}
      </div>

      {/* legend of the colours (on the map) */}
      <div className="nw-legend v2 v2-embedded" role="group" aria-label="Map legend">
        <strong>Overall score W · {purposeLabel(purpose)}</strong>
        <div className="nw-legend-sub">{legendSub}</div>
        <ColorLegend />
        {noneSuitable && (
          <div className="nw-legend-warn" role="status">
            {allRemoved ? 'No chosen species can be planted in your dates.' : `No point is suitable for this selection${combine === 'all' && selIds.length > 1 ? ': try “Suits at least one”' : ''}.`}
          </div>
        )}
        {fieldForMap && (
          <ul className="nw-fieldkey" aria-label="Field check symbols">
            <li>
              <span aria-hidden="true">◯</span> verified plantable
            </li>
            <li>
              <span aria-hidden="true">✕</span> not plantable (left out)
            </li>
            <li>
              <span aria-hidden="true">△</span> needs recheck
            </li>
          </ul>
        )}
        <div className="nw-legend-note">Each dot is a 100 m grid cell in a planting zone. Blue-ringed dot = the chosen point.</div>
      </div>

      {/* TOP GLASS NAVIGATION BAR (look copied from the earlier dashboard) */}
      <header className="nw-topbar">
        <div className="nw-brandrow">
          <div className="nw-brand">LGU SAN MATEO 𖣂︎</div>
          <div>
            <div className="nw-title">Urban Tree Planting Decision Support System</div>
            <div className="nw-subtitle">Municipal Environment and Natural Resources Office (MENRO)</div>
          </div>
        </div>
        <div className="nw-tabs" role="tablist" aria-label="Views">
          {TABS.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={`nw-tab ${tab === t.id ? 'is-active' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="nw-topright">
          <div className="nw-pill" role="status">
            <span className={`nw-dot nw-dot-${apiState}`} aria-hidden="true" />
            <span>{apiState === 'ok' ? 'API connected' : apiState === 'wait' ? 'Connecting…' : 'API offline'}</span>
          </div>
        </div>
      </header>
      {tab !== 'studio' && (
        <section className="nw-modal" aria-label={TABS.find((t) => t.id === tab).label}>
          <div className="nw-modal-head">
            <h2>{tab === 'history' ? 'Campaign Event Logs & History' : 'System Spatial Analytics'}</h2>
            <button type="button" className="nw-btn" onClick={() => setTab('studio')}>
              ✕ Close & Return to Map
            </button>
          </div>
          <p className="nw-modal-text">
            This view will be rebuilt in a later step of the revamp. The earlier dashboard still has it: open <a href="#/legacy">#/legacy</a>.
          </p>
        </section>
      )}

      {/* SIDEBAR (look copied from the earlier dashboard) */}
      <button type="button" className="nw-toggle" onClick={() => setSidebarOpen((o) => !o)} aria-expanded={sidebarOpen} aria-controls="nw-sidebar">
        {sidebarOpen ? '◀ Hide Control Panel' : '▶ Open Control Panel'}
      </button>
      <aside id="nw-sidebar" className="nw-sidebar" aria-label="Controls">
        <SidebarStep
          n={1}
          id="goal"
          title="Goal"
          summary={mode === 'species' ? 'I have species' : 'I have an area'}
          open={openStep === 'goal'}
          onToggle={() => toggleStep('goal')}
          help="“I have species” shows where the species you choose can grow. “I have an area” ranks the species for an area you choose."
        >
          <ModeSwitch
            value={mode}
            onChange={(m) => {
              changeMode(m)
              setOpenStep('purpose')
            }}
          />
        </SidebarStep>
        <SidebarStep
          n={2}
          id="purpose"
          title="Purpose"
          summary={PURPOSE_SHORT[purpose]}
          open={openStep === 'purpose'}
          onToggle={() => toggleStep('purpose')}
          help="Urban greening: shade, safe roots, low upkeep. Tree planting: conservation and livelihood. Watershed: holding soil on slopes and by waterways."
        >
          <PurposePicker value={purpose} onChange={setPurpose} />
          <button type="button" className="nw-btn nw-btn-go nw-btn-wide" onClick={() => setOpenStep('window')}>
            Continue
          </button>
        </SidebarStep>
        <SidebarStep
          n={3}
          id="window"
          title="Planting window"
          summary={`${formatRange(win.applied.start, win.applied.end)} · ${monthsText(windowMonths(win.applied.start, win.applied.end))}${onlySeason ? '' : ' · all species'}${win.error ? ' · fix dates' : ''}`}
          open={openStep === 'window'}
          onToggle={() => toggleStep('window')}
          help="The season decides which species can be planted. A month counts if any day of it is in your dates. Scores never change with the dates."
        >
          <PlantingWindow win={win} onlySeason={onlySeason} onOnlySeason={setOnlySeason} species={species} />
          <button type="button" className="nw-btn nw-btn-go nw-btn-wide" onClick={() => setOpenStep('pick')}>
            Continue
          </button>
        </SidebarStep>
        <SidebarStep
          n={4}
          id="pick"
          title={mode === 'species' ? 'Species' : 'Area'}
          summary={mode === 'species' ? `${selIds.length ? `${selIds.length} chosen` : 'None chosen'} · ${combine === 'all' ? 'Suits all' : 'Suits one or more'}` : area ? areaLabel : 'None chosen'}
          open={openStep === 'pick'}
          onToggle={() => toggleStep('pick')}
          help={
            mode === 'species'
              ? 'Until you choose species the map shows the best species at each point. Green is good, orange moderate, red poor, grey not suitable. Click a dot to see why.'
              : 'Click a point or a barangay outline on the map, draw a shape, or pick a barangay or zone from the lists.'
          }
        >
          {mode === 'species' ? (
            <>
              {fewSpecies && seasonNotice(false)}
              <SpeciesMultiPicker species={species} selected={selIds} onChange={setSelIds} onlySeason={onlySeason} onInfo={setCardId} />
              <Segmented
                name="combine"
                label="Place counts when"
                help="“Suits all”: every chosen species can grow there, and the score is the lowest of theirs. “Suits at least one”: one is enough, and the score is the highest."
                value={combine}
                options={[
                  { value: 'all', label: 'Suits all' },
                  { value: 'any', label: 'Suits at least one' },
                ]}
                onChange={setCombine}
              />
            </>
          ) : (
            <>
              <AreaChooser
                tool={tool}
                onTool={changeTool}
                barangays={barangayFeatures}
                zones={zoneFeatures}
                area={area}
                onArea={chooseArea}
                draftCount={draft.length}
                onFinish={finishDraw}
                onUndo={() => setDraft((d) => d.slice(0, -1))}
                onClearDraft={() => setDraft([])}
              />
              {notice && (
                <p className="nw-hint nw-warn" role="status">
                  {notice}
                </p>
              )}
            </>
          )}
          {planPrefill && (
            <div className="nw-prefill">
              <span>
                Plan tool: <strong>{planPrefill.area.name}</strong>
              </span>
              <button type="button" className="nw-btn nw-btn-small" onClick={() => setPlanPrefill(null)}>
                Clear
              </button>
            </div>
          )}
          <button type="button" className="nw-btn nw-btn-go nw-btn-wide" onClick={() => setOpenStep('')}>
            Done
          </button>
        </SidebarStep>
        <MoreMenu health={health} fieldSummary={fieldSummary} observer={observer} onObserver={setObserver} onChanged={bumpField} />
      </aside>

      {(hasMain || hasPoint) && hidden && (
        <button type="button" className="nw-reopen" onClick={() => setHidden(false)}>
          Show results
        </button>
      )}
      {showPanel && (
        <RightPanel
          title={activeTab === 'point' ? 'Species for this point' : mode === 'species' ? 'Areas for the selected species' : `Species for ${areaLabel}`}
          subtitle={purposeLabel(purpose)}
          tabs={tabs}
          activeTab={activeTab}
          onTab={setPanelTab}
          onClose={() => setHidden(true)}
        >
          {activeTab === 'point' ? (
            <div className="v2 v2-embedded">
              {pointId ? <VerifyBar key={pointId} pointId={pointId} api={fieldPoint} observer={observer} onObserver={setObserver} onSaved={bumpField} /> : null}
              <PointRanking
                key={`${purpose}|${spot.lat}|${spot.lon}`}
                rank={rank}
                purpose={purpose}
                viable={viable}
                onFindViable={() => setViableFor(spotQuery)}
                onGo={goTo}
                seasonNote={seasonNotice(true)}
                onInfo={setCardId}
              />
            </div>
          ) : mode === 'species' ? (
            <AreasPanel
              speciesNames={selNames}
              combine={combine}
              onCombine={setCombine}
              byBarangay={byBarangay}
              byZone={byZone}
              activeKey={rowActive ? `${rowActive.kind}|${rowActive.name}` : ''}
              onSelect={selectRow}
              onPlan={planHere}
              allRemoved={allRemoved}
              seasonNote={selectedRemoved.length > 0 ? seasonNotice(true, `${selectedRemoved.map((id) => speciesNames.get(id) ?? `species ${id}`).join(', ')} ${selectedRemoved.length === 1 ? 'is' : 'are'} out of season between ${formatDay(win.applied.start)} and ${formatDay(win.applied.end)} and left out.`) : null}
            />
          ) : (
            <AreaResultPanel api={areaRank} areaLabel={areaLabel} onShowAll={showAllSpecies} onChangeDates={changeDates} onInfo={setCardId} />
          )}
        </RightPanel>
      )}
      {cardId !== null && (
        <SpeciesCard
          speciesId={cardId}
          window={win.applied}
          onClose={() => setCardId(null)}
          onFindAreas={(id) => {
            changeMode('species')
            setSelIds([id])
            setRowActive(null)
            setCardId(null)
          }}
        />
      )}
    </div>
  )
}
