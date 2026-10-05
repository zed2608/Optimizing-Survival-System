import { useMemo, useState } from 'react'
import '../v2/v2.css'
import './new.css'
import ColorLegend from '../v2/components/ColorLegend.jsx'
import LimitsBox from '../v2/components/LimitsBox.jsx'
import RankingPanel from '../v2/components/RankingPanel.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { RANK_LIMIT } from '../v2/config.js'
import { purposeLabel } from '../v2/labels.js'
import { LEVEL_WORD, wLevel } from '../v2/scale.js'
import { useApi } from '../v2/useApi.js'
import AreaChooser from './AreaChooser.jsx'
import AreaResultPanel from './AreaResultPanel.jsx'
import AreasPanel from './AreasPanel.jsx'
import DatasetNote from './DatasetNote.jsx'
import FieldCheckSection from './FieldCheckSection.jsx'
import FieldSummary from './FieldSummary.jsx'
import { decodeFieldCode, STATUS_LABEL, STATUS_SYMBOL } from './fieldLabels.js'
import { featureAt, geometryBbox, polygonFromVertices } from './geo.js'
import MapNew from './MapNew.jsx'
import ModeSwitch from './ModeSwitch.jsx'
import PurposePicker from './PurposePicker.jsx'
import RightPanel from './RightPanel.jsx'
import SpeciesMultiPicker from './SpeciesMultiPicker.jsx'
import { useObserver } from './useObserver.js'
import { usePost } from './usePost.js'

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
  const [limitsOpen, setLimitsOpen] = useState(false)
  const [tab, setTab] = useState('studio')
  const [fieldVersion, setFieldVersion] = useState(0) // bumped after every saved field check: reloads what depends on them (and skips the browser cache)
  const [showField, setShowField] = useState(true)
  const [observer, setObserver] = useObserver()

  const health = useApi('/health')
  const boundaries = useApi('/geo/boundaries')
  const zones = useApi('/geo/zones')
  const species = useApi('/species')

  const idsParam = [...selIds].sort((a, b) => a - b).join(',')
  const selection = mode === 'species' && selIds.length > 0
  const fc = `fc=${fieldVersion}`
  const grid = useApi(selection ? `/grid?purpose=${purpose}&species_ids=${idsParam}&mode=${combine}&${fc}` : `/grid?purpose=${purpose}&${fc}`)
  const areasQuery = selection ? `purpose=${purpose}&species_ids=${idsParam}&mode=${combine}&${fc}` : null
  const byBarangay = useApi(areasQuery ? `/areas/rank?${areasQuery}&by=barangay` : null)
  const byZone = useApi(areasQuery ? `/areas/rank?${areasQuery}&by=zone` : null)
  const areaBody = useMemo(() => {
    if (mode !== 'area' || !area) return null
    const base = { purpose, limit: RANK_LIMIT, fc: fieldVersion }
    if (area.kind === 'barangay') return { ...base, barangay: area.name }
    if (area.kind === 'zone') return { ...base, zone: area.name }
    return { ...base, polygon: area.geometry }
  }, [mode, area, purpose, fieldVersion])
  const areaRank = usePost('/rank/area', areaBody)
  const spotQuery = spot ? `purpose=${purpose}&lat=${spot.lat.toFixed(6)}&lon=${spot.lon.toFixed(6)}&${fc}` : null
  const rank = useApi(spotQuery ? `/rank?${spotQuery}&limit=${RANK_LIMIT}` : null)
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
  const legendSub = selection
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
        />
      </div>

      {/* messages over the map */}
      <div className="nw-toasts v2 v2-embedded">
        {grid.status === 'loading' && <Loading what="Loading the grid points" />}
        {grid.status === 'error' && <ErrorBox error={grid.error} onRetry={grid.retry} title="Could not load the grid points" />}
        {boundaries.status === 'error' && !boundaries.error.network && <ErrorBox error={boundaries.error} onRetry={boundaries.retry} title="Could not load the outlines" brief />}
      </div>

      {/* legend of the colours (on the map) */}
      <div className="nw-legend v2 v2-embedded" role="group" aria-label="Map legend">
        <strong>Overall score W · {purposeLabel(purpose)}</strong>
        <div className="nw-legend-sub">{legendSub}</div>
        <ColorLegend />
        {noneSuitable && (
          <div className="nw-legend-warn" role="status">
            No point is suitable for this selection{combine === 'all' && selIds.length > 1 ? ': try “Suits at least one”' : ''}.
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
          <button type="button" className="nw-pillbtn" aria-expanded={limitsOpen} aria-controls="limits-panel" onClick={() => setLimitsOpen((o) => !o)}>
            {limitsOpen ? 'Hide known limits' : 'Known limits'}
          </button>
          <div className="nw-pill" role="status">
            <span className={`nw-dot nw-dot-${apiState}`} aria-hidden="true" />
            <span>{apiState === 'ok' ? 'API connected' : apiState === 'wait' ? 'Connecting…' : 'API offline'}</span>
          </div>
        </div>
      </header>
      {limitsOpen && (
        <div className="nw-limits v2 v2-embedded">
          <LimitsBox health={health} open />
        </div>
      )}

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
        <ModeSwitch value={mode} onChange={changeMode} />
        <section className="nw-section">
          <h3>1. Purpose</h3>
          <PurposePicker value={purpose} onChange={setPurpose} />
        </section>
        {mode === 'species' ? (
          <section className="nw-section">
            <h3>2. Species</h3>
            <SpeciesMultiPicker species={species} selected={selIds} onChange={setSelIds} combine={combine} onCombine={setCombine} />
            <p className="nw-hint">
              {selIds.length === 0
                ? 'Pick one or more species to find the areas that suit them. Until then the map shows the best species at each point.'
                : 'Green = good, orange = moderate, red = poor, grey = not suitable. Point at a dot to see its number; click it to see why it scores that way.'}
            </p>
          </section>
        ) : (
          <section className="nw-section">
            <h3>2. Area</h3>
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
          </section>
        )}
        {planPrefill && (
          <section className="nw-section">
            <h3>Plan tool selection</h3>
            <p className="nw-hint">
              <strong>{planPrefill.area.name}</strong> · {purposeLabel(planPrefill.purpose)} ·{' '}
              {planPrefill.speciesNames.length === 1 ? planPrefill.speciesNames[0] : `${planPrefill.speciesNames.length} species (${planPrefill.combine === 'all' ? 'must suit all' : 'at least one'})`}
              <br />
              Saved for the plan tool, which comes in a later step.
            </p>
            <button type="button" className="nw-btn nw-btn-small" onClick={() => setPlanPrefill(null)}>
              Clear
            </button>
          </section>
        )}
        <FieldSummary summary={fieldSummary} observer={observer} onObserver={setObserver} showField={showField} onShowField={setShowField} onChanged={bumpField} />
        <section className="nw-section">
          <h3>Switch dashboard</h3>
          <p className="nw-hint">
            <a href="#/legacy">Earlier dashboard</a> · <a href="#/v2">First v2 page</a>
          </p>
          <DatasetNote health={health} />
        </section>
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
              <RankingPanel
                key={`${purpose}|${spot.lat}|${spot.lon}`}
                rank={rank}
                purpose={purpose}
                viable={viable}
                onFindViable={() => setViableFor(spotQuery)}
                onGo={goTo}
              />
              {pointId ? (
                <div className="panel-body fc-wrap">
                  <FieldCheckSection key={pointId} pointId={pointId} api={fieldPoint} observer={observer} onObserver={setObserver} onSaved={bumpField} />
                </div>
              ) : null}
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
            />
          ) : (
            <AreaResultPanel api={areaRank} areaLabel={areaLabel} />
          )}
        </RightPanel>
      )}
    </div>
  )
}
