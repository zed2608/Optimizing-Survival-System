import { useCallback, useMemo, useState } from 'react'
import '../v2/v2.css'
import './new.css'
import Icon from './Icon.jsx'
import ColorLegend from '../v2/components/ColorLegend.jsx'
import GroundLegend from './GroundLegend.jsx'
import { GROUND_GROUPS, GROUND_STYLE } from './groundStyle.js'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { purposeLabel } from '../v2/labels.js'
import { LEVEL_WORD, fmt, wLevel } from '../v2/scale.js'
import { useApi } from '../v2/useApi.js'
import AreaChooser from './AreaChooser.jsx'
import AreaResultPanel from './AreaResultPanel.jsx'
import AreasPanel from './AreasPanel.jsx'
import { decodeFieldCode, STATUS_LABEL } from './fieldLabels.js'
import { featureAt, geometryBbox, polygonFromVertices } from './geo.js'
import { PURPOSE_SHORT } from './labelsNew.js'
import MoreMenu from './MoreMenu.jsx'
import MapViewMenu from './MapViewMenu.jsx'
import PlanLegend from './PlanLegend.jsx'
import PlanResult from './PlanResult.jsx'
import PlanStep from './PlanStep.jsx'
import { countText, countsSummary } from './counts.js'
import PairsWith from './PairsWith.jsx'
import { HelpBanner, HelpButton, HowToUse, Tour } from './HelpCenter.jsx'
import { useHelpState } from './help.js'
import { matchText } from './plainWords.js'
import { apiPost } from './apiPost.js'
import { apiGet } from '../v2/api.js'
import { MAP_CENTER } from '../v2/config.js'
import AnalyticsPanel from './AnalyticsPanel.jsx'
import CampaignLogs from './CampaignLogs.jsx'
import PlantingWindow from './PlantingWindow.jsx'
import PointPanel from './PointPanel.jsx'
import ContextPanel from './ContextPanel.jsx'
import Segmented from './Segmented.jsx'
import SpeciesCard from './SpeciesCard.jsx'
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
import { useIncludeUnzoned, useLegendOpen, useMapDetail, useViewMode } from './useViewMode.js'
import UnzonedToggle from './UnzonedToggle.jsx'
import WeatherTab from './WeatherTab.jsx'
import { useOnlySeason, usePlantingWindow } from './useWindow.js'
import { RIGHT_PANEL_WIDTH, SIDEBAR_WIDTH } from './layout.js'

const POINT_LIMIT = 45 // species asked for in a point ranking and an area ranking (the panels show 5, 10 or all)

const TABS = [
  { id: 'studio', label: 'Active Studio', icon: 'map' },
  { id: 'weather', label: 'Weather', icon: 'cloud' },
  { id: 'history', label: 'Campaign Logs', icon: 'clipboard' },
  { id: 'analytics', label: 'System Analytics', icon: 'bars' },
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
  const [campaignName, setCampaignName] = useState('')
  const [campaignUnit, setCampaignUnit] = useState('')
  const [nSaplings, setNSaplings] = useState('100')
  const [counts, setCounts] = useState({}) // trees per chosen species (a species not edited yet has the default)
  const [ownSpecies, setOwnSpecies] = useState(false) // goal "I have an area": the user chose their own species and counts
  const [focusIds, setFocusIds] = useState(() => new Set()) // planned squares to circle on the map ("Show these on the map")
  const help = useHelpState()
  const [planResult, setPlanResult] = useState(null) // the last plan created (it is also saved on the server)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [showPlan, setShowPlan] = useState(true) // the "Planned trees" layer
  const win = usePlantingWindow()
  const [onlySeason, setOnlySeason] = useOnlySeason()
  const [tab, setTab] = useState('studio')
  const [fieldVersion, setFieldVersion] = useState(0) // bumped after every saved field check: reloads what depends on them (and skips the browser cache)
  const [showField, setShowField] = useState(true)
  const [showGround, setShowGround] = useState(false) // the optional ground-cover layer (default off)
  const [showOther, setShowOther] = useState(true) // the faint layer of grid squares that are not planting zones
  const [observer, setObserver] = useObserver()
  const [view, setView] = useViewMode() // Compact | Full details of the species lists
  const [legendOpen, setLegendOpen] = useLegendOpen()
  const [searchNote, setSearchNote] = useState(null) // what the last search result was (shown under the search box)
  const [detailed, setDetailed] = useMapDetail() // Simple (default) | Detailed map
  const [sessionMarks, setSessionMarks] = useState(() => new Set()) // grid points marked in this browser session: their symbols show even in Simple
  const [includeUnzoned, setIncludeUnzoned] = useIncludeUnzoned() // land outside the zoning map: scored and flagged (default) or left out
  const [weatherLoc, setWeatherLoc] = useState('centre') // the Weather tab's place: 'centre' | 'point' | 'plan' | 'b:<barangay>'
  const uz = `include_unzoned=${includeUnzoned}`

  const health = useApi(`/health?${uz}`)
  const boundaries = useApi('/geo/boundaries')
  const zones = useApi('/geo/zones')
  const contextData = useApi(`/grid/context?${uz}`)
  const landcover = useApi(showGround || detailed ? '/grid/landcover' : null) // dominant satellite land-cover class per square (for the layer and the Detailed corner marks)
  const sq = `${seasonQuery(win.applied, onlySeason)}&${uz}` // the dates (and 'only' or 'mark') and the zoning switch that every species-listing call carries
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
    const base = { purpose, limit: POINT_LIMIT, fc: fieldVersion }
    if (area.kind === 'barangay') return { ...base, barangay: area.name }
    if (area.kind === 'zone') return { ...base, zone: area.name }
    return { ...base, polygon: area.geometry }
  }, [mode, area, purpose, fieldVersion])
  const areaRank = usePost(`/rank/area?${sq}`, areaBody)
  const spotSq = spot?.planned ? sq.replace(/include_unzoned=(true|false)/, 'include_unzoned=true') : sq // a point of a saved plan is always ranked, even if its square is outside the zoning map and the switch is off
  const spotQuery = spot ? `purpose=${purpose}&lat=${spot.lat.toFixed(6)}&lon=${spot.lon.toFixed(6)}&${fc}&${spotSq}` : null
  // While the same spot is re-ranked (after a saved field check, for instance) the last answer stays on screen, so the confirmation and the open menus are not lost.
  const [keptRank, setKeptRank] = useState(null)
  const rankKey = spot ? `${purpose}|${spot.lat}|${spot.lon}|${sq}` : ''
  // the chosen species at the clicked spot ("I have species"): ranked with the season only marked, so a species the dates filter removes still shows its numbers
  const chosenQ = spot && spot.context === undefined && mode === 'species' && selIds.length > 0 ? `purpose=${purpose}&lat=${spot.lat.toFixed(6)}&lon=${spot.lon.toFixed(6)}&${fc}&${seasonQuery(win.applied, false)}&${spot.planned ? 'include_unzoned=true' : uz}` : null
  const chosenRank = useApi(chosenQ ? `/rank?${chosenQ}&limit=45&include_left_out=true` : null)
  const isContext = !!spot && spot.context !== undefined // a click on a grey square (not a planting zone)
  const rank = useApi(spotQuery && !isContext ? `/rank?${spotQuery}&limit=${POINT_LIMIT}&include_left_out=true&explain=${view === 'full'}` : null)
  const viable = useApi(spotQuery && viableFor === spotQuery ? `/nearest-viable?${spotQuery}` : null)
  if (rank.status === 'ok' && (keptRank === null || keptRank.data !== rank.data)) setKeptRank({ data: rank.data, key: rankKey })
  const shownRank = rank.status === 'loading' && keptRank && keptRank.key === rankKey ? { ...rank, status: 'ok', data: keptRank.data } : rank
  const pointId = spot && !isContext ? (spot.pointId ?? (rank.status === 'ok' ? rank.data.point.point_id : null)) : null
  const fieldPoint = useApi(pointId ? `/field-checks/${pointId}?${fc}` : null)
  const fieldSummary = useApi(`/field-checks/summary?${fc}`)
  const bumpField = () => setFieldVersion((v) => v + 1)

  const barangayFeatures = useMemo(() => (boundaries.data?.features ?? []).filter((f) => f.properties.kind === 'barangay'), [boundaries.data])
  const zoneFeatures = useMemo(() => zones.data?.features ?? [], [zones.data])
  const speciesNames = useMemo(() => new Map((species.data?.species ?? []).map((s) => [s.species_id, s.common_name])), [species.data])
  const selNames = useMemo(() => selIds.map((id) => speciesNames.get(id) ?? `species ${id}`), [selIds, speciesNames])
  const columns = grid.data?.columns ?? null
  const indexById = useMemo(() => new Map((columns?.point_id ?? []).map((id, i) => [id, i])), [columns])
  // ground cover per grid column: the group index and the flag bits of every scored square (aligned with the /grid columns)
  const groundInfo = useMemo(() => {
    if (landcover.status !== 'ok' || !columns) return null
    const cc = contextData.status === 'ok' ? contextData.data.columns : null
    const lc = landcover.data
    const groupOfClass = lc.classes.map((c) => Math.max(0, GROUND_GROUPS.indexOf(c.group)))
    const at = new Map(lc.columns.point_id.map((id, i) => [id, i]))
    const cls = new Uint8Array(columns.point_id.length)
    const flags = new Uint8Array(columns.point_id.length)
    columns.point_id.forEach((id, i) => {
      const k = at.get(id)
      const c = k === undefined ? -1 : lc.columns.class[k]
      cls[i] = c < 0 ? 255 : groupOfClass[c]
      flags[i] = k === undefined ? 0 : lc.columns.flags[k]
    })
    const ctxCls = cc ? new Uint8Array(cc.point_id.length) : null
    if (cc) {
      cc.point_id.forEach((id, i) => {
        const k = at.get(id)
        const c = k === undefined ? -1 : lc.columns.class[k]
        ctxCls[i] = c < 0 ? 255 : groupOfClass[c]
      })
    }
    return { cls, flags, ctxCls }
  }, [landcover.status, landcover.data, columns, contextData.status, contextData.data])
  const selected = rank.status === 'ok' ? (indexById.get(rank.data.point.point_id) ?? -1) : -1
  const locate = useCallback((lat, lon) => featureAt(barangayFeatures, lon, lat)?.properties.display_name ?? '', [barangayFeatures])
  const contextCols = contextData.status === 'ok' ? contextData.data.columns : null
  const contextLabeler = useMemo(() => {
    if (contextData.status !== 'ok') return null
    const d = contextData.data
    return (i) => [d.columns.zone[i] >= 0 ? `Not a planting zone: ${d.zones[d.columns.zone[i]]}` : 'Outside the zoning map', 'Not scored']
  }, [contextData.status, contextData.data])
  let pointBarangay = ''
  if (shownRank.status === 'ok') {
    const gi = indexById.get(shownRank.data.point.point_id)
    const b = gi !== undefined && columns ? columns.barangay[gi] : -1
    pointBarangay = b >= 0 && grid.data ? grid.data.barangays_display[b] : locate(shownRank.data.point.lat, shownRank.data.point.lon)
  }
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
    const unconfirmed = new Set(g.zoning?.unconfirmed_index ?? [])
    return (i) => {
      const c = g.columns
      const b = c.barangay[i]
      const w = c.W[i]
      const sid = c.best_species_id[i]
      const sname = sid >= 0 ? (speciesNames.get(sid) ?? `species ${sid}`) : null
      const label = { all: 'Limiting species', any: 'Best of the selected', single: 'Species', best: 'Best species' }[g.mode]
      const lines = [
        `Barangay: ${b >= 0 ? g.barangays_display[b] : 'Data Unavailable'}`,
        w > 0 ? (view === 'full' ? `Score W ${w.toFixed(2)} (${LEVEL_WORD[wLevel(w, true)]})` : `Overall match ${matchText(w)}`) : view === 'full' ? 'Not suitable here (score 0)' : 'Not suitable here',
        sname ? `${label}: ${sname}` : null,
      ]
      if (g.mode === 'all' || g.mode === 'any') lines.push(`${c.n_eligible_species[i]} of ${g.species_ids.length} selected species suit this point`)
      if (unconfirmed.has(i)) lines.push('Zoning: outside our zoning map (CLUP: Forest Reserve, Watershed)')
      if (showGround && groundInfo) lines.push(`Ground cover (satellite 2021): ${groundInfo.cls[i] === 255 ? 'Data Unavailable' : GROUND_STYLE[GROUND_GROUPS[groundInfo.cls[i]]].label.toLowerCase()}${groundInfo.flags[i] ? ' (flagged: check on the ground)' : ''}`)
      if (fieldAt.has(i)) {
        const f = decodeFieldCode(fieldAt.get(i))
        lines.push(`Field check: ${STATUS_LABEL[f.status]}${f.disputed ? ' (disputed)' : ''}${f.status === 'not_plantable' ? ' - left out' : ''}`)
      }
      return lines.filter(Boolean)
    }
  }, [grid.data, speciesNames, showGround, groundInfo, view])

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

  const onPick = ({ index, context = -1, plan = -1, lat, lon }) => {
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
    if (plan >= 0 && planResult) {
      openPlanPoint(planResult.plan[plan])
      setNotice('')
      return
    }
    if (index < 0 && context >= 0 && contextCols) {
      setSpot({ lat: contextCols.lat[context], lon: contextCols.lon[context], context })
      setPanelTab('point')
      setHidden(false)
      setNotice('')
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
    const rankable = it.type === 'grid_point' && (it.legal_zone || it.zoning_status === 'unconfirmed')
    const pointId = it.type === 'plan_point' || rankable ? it.point_id : undefined
    const searched =
      it.type === 'coords' ? `coordinates ${it.lat.toFixed(5)}, ${it.lon.toFixed(5)}` : it.type === 'grid_point' ? `grid point ${it.point_id}` : it.type === 'plan_point' ? `${it.point_ref} (${it.species})` : (it.name || it.display_name)
    const ci = it.type === 'grid_point' && !rankable && contextCols ? contextCols.point_id.indexOf(it.point_id) : -1
    setSpot({ lat: it.lat, lon: it.lon, searched, ...(it.type === 'plan_point' ? { planned: true } : {}), ...(ci >= 0 ? { context: ci } : pointId ? { pointId } : {}) })
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
    setOwnSpecies(false)
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
  const hasPlanTab = !!planResult
  const avail = { plan: hasPlanTab, main: hasMain, point: hasPoint }
  const activeTab = avail[panelTab] ? panelTab : (['plan', 'main', 'point'].find((k) => avail[k]) ?? 'point')
  const showPanel = (hasMain || hasPoint || hasPlanTab) && !hidden
  const tabs = [...(hasPlanTab ? [{ id: 'plan', label: 'Plan' }] : []), ...(hasMain ? [{ id: 'main', label: mode === 'species' ? 'Areas' : 'Area species' }] : []), ...(hasPoint ? [{ id: 'point', label: 'This point' }] : [])]
  const areaLabel = !area ? '' : area.kind === 'polygon' ? 'the drawn area' : (featureOf(area.kind, area.name)?.properties.display_name ?? area.name)

  // ---- step 5 "Plan"
  const nNum = Number(nSaplings)
  const countsMode = mode === 'species' || ownSpecies // one number per chosen species, or one total for the automatic mix
  const countRows = useMemo(() => [...selIds].sort((a, b) => a - b).map((id) => ({ id, name: speciesNames.get(id) ?? `species ${id}` })), [selIds, speciesNames])
  const cs = countsSummary(countRows.map((r) => r.id), counts)
  const nValid = countsMode ? cs.valid : /^\d+$/.test(String(nSaplings).trim()) && nNum >= 1 && nNum <= 2000
  const planTotal = countsMode ? cs.total : nNum
  const planArea = mode === 'area' ? area : planPrefill ? { kind: planPrefill.area.kind, name: planPrefill.area.key } : null
  const planAreaBody = !planArea ? null : planArea.kind === 'barangay' ? { barangay: planArea.name } : planArea.kind === 'zone' ? { zone: planArea.name } : { polygon: planArea.geometry }
  const planAreaLabel = !planArea ? '' : planArea.kind === 'polygon' ? 'The drawn area' : (featureOf(planArea.kind, planArea.name)?.properties.display_name ?? planArea.name)
  const planSpeciesOk = !countsMode || selIds.length > 0
  const planBody = !planAreaBody
    ? null
    : countsMode
    ? { purpose, species_counts: Object.fromEntries(countRows.map((r) => [r.id, Number(countText(counts, r.id))])), ...planAreaBody }
    : { purpose, n_saplings: nNum, ...planAreaBody }
  const preview = usePost(`/plan-event/preview?${sq}`, planBody && nValid && planSpeciesOk && !win.error ? planBody : null)
  const planReason = !planArea
    ? 'Choose an area first'
    : !planSpeciesOk
    ? 'Choose species first'
    : campaignName.trim() === ''
    ? 'Name the campaign'
    : win.error
    ? 'Fix the planting dates'
    : !nValid
    ? 'Trees: 1 to 2000'
    : preview.status === 'loading' || preview.status === 'idle'
    ? 'Checking the area…'
    : preview.status === 'error'
    ? 'The area could not be checked'
    : !preview.data.can_create
    ? preview.data.reason === 'no_suitable_squares'
      ? 'No suitable squares here'
      : 'No species can be planted in these dates'
    : ''
  // show a plan (just created, or opened from Campaign Logs): the result card, the planned trees on the map, and fit the map to them
  const showPlanResult = (r) => {
    setPlanResult(r)
    setFocusIds(new Set())
    setShowPlan(true)
    setPanelTab('plan')
    setHidden(false)
    setSpot(null)
    const lons = r.plan.map((x) => x.lon)
    const lats = r.plan.map((x) => x.lat)
    setFitTarget({ bbox: [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)] })
  }
  const openSavedPlan = async (planId) => {
    const r = await apiGet(`/plans/${planId}`)
    showPlanResult(r)
    setTab('studio')
  }
  const openTopUp = (r) => {
    showPlanResult(r)
    setTab('studio')
  }
  const createPlan = async () => {
    if (planReason || creating) return
    setCreating(true)
    setCreateError('')
    try {
      const r = await apiPost(`/plan-event?${sq}`, { ...planBody, campaign: { name: campaignName.trim(), unit: campaignUnit.trim() } })
      showPlanResult(r)
    } catch (e) {
      setCreateError(e.message)
    } finally {
      setCreating(false)
    }
  }
  const anotherPlan = () => {
    setPlanResult(null)
    setFocusIds(new Set())
    setCreateError('')
    setPanelTab('main')
    setOpenStep('plan')
  }
  const planSpecies = useMemo(() => {
    const m = new Map()
    if (planResult) {
      planResult.palette.filter((p) => p.placed > 0).forEach((p, k) => {
        const it = planResult.plan.find((x) => x.species_id === p.species_id)
        m.set(p.species_id, { kind: k, code: it?.species_code ?? '???', common_name: p.species, count: p.placed, blocks: p.blocks_placed ?? null, species_id: p.species_id })
      })
    }
    return m
  }, [planResult])
  const planItems = useMemo(() => (planResult ? planResult.plan.map((it) => ({ lon: it.lon, lat: it.lat, kind: planSpecies.get(it.species_id)?.kind ?? 0, code: it.species_code, barangay: it.barangay_display, unconfirmed: it.flags.includes('zoning_unconfirmed'), focus: focusIds.has(it.point_id), ...(it.trees_planned != null ? { trees: it.trees_planned } : {}) })) : null), [planResult, planSpecies, focusIds])
  const planBlock = useMemo(() => {
    if (!planResult || planResult.layout_mode !== 'blocks' || !pointId) return null
    const item = planResult.plan.find((x) => x.point_id === pointId)
    return item ? { item, kind: planSpecies.get(item.species_id)?.kind ?? 0, planId: planResult.plan_id } : null
  }, [planResult, pointId, planSpecies])
  const nPlanUnconfirmed = useMemo(() => (planItems ? planItems.filter((x) => x.unconfirmed).length : 0), [planItems])
  const planLabeler = useMemo(
    () =>
      planResult
        ? (i) => {
            const it = planResult.plan[i]
            return [`${it.point_ref} · ${it.species}`, ...(it.trees_planned != null ? [`${it.trees_planned} trees · ${it.rows} rows of ${it.trees_per_row} · ${it.spacing_m} m apart`] : []), view === 'full' ? `S ${fmt(it.S)} · P ${fmt(it.P)} · W ${fmt(it.W)}` : `Overall match ${matchText(it.W)}`, `Barangay: ${it.barangay_display || 'outside the barangay outlines'}`, it.flags.includes('zoning_unconfirmed') ? 'Zoning: not on the zoning map (not confirmed)' : `Zone: ${it.zone}`]
          }
        : null,
    [planResult, view],
  )
  const planWeatherLoc = useMemo(
    () => (planResult && planResult.plan.length ? { lat: planResult.plan.reduce((a, x) => a + x.lat, 0) / planResult.plan.length, lon: planResult.plan.reduce((a, x) => a + x.lon, 0) / planResult.plan.length, label: `The middle of the plan (${planResult.campaign?.name ?? planResult.plan_id})` } : null),
    [planResult],
  )
  const openWeatherForPlan = () => {
    setWeatherLoc('plan')
    setTab('weather')
  }
  const showOnMap = (list) => {
    if (!list.length) return
    setFocusIds(new Set(list.map((x) => x.point_id)))
    setShowPlan(true)
    const lons = list.map((x) => x.lon)
    const lats = list.map((x) => x.lat)
    const pad = 0.0015
    setFitTarget({ bbox: [Math.min(...lons) - pad, Math.min(...lats) - pad, Math.max(...lons) + pad, Math.max(...lats) + pad] })
  }
  const openPlanPoint = (it) => {
    setSpot({ lat: it.lat, lon: it.lon, pointId: it.point_id, planned: true, searched: `${it.point_ref} (planned ${it.species})` })
    setGoTarget({ lat: it.lat, lon: it.lon })
    setPanelTab('point')
    setHidden(false)
  }
  const planFromRow = (kind, row) => {
    planHere(kind, row)
    setSidebarOpen(true)
    setOpenStep('plan')
  }

  // the free part of the map, for hover cards: not under the sidebar, the results panel or the top bar
  const safeArea = useMemo(() => ({ left: sidebarOpen ? SIDEBAR_WIDTH + 40 : 16, right: showPanel || cardId !== null ? RIGHT_PANEL_WIDTH + 104 : 60, top: 142, bottom: 16 }), [sidebarOpen, showPanel, cardId])
  const fieldForMap = useMemo(() => {
    const f = grid.data?.field
    if (!f) return null
    if (detailed) return showField ? f : null // Detailed: every field-check symbol
    const ids = grid.data.columns.point_id
    const keep = f.index.map((idx, k) => (sessionMarks.has(ids[idx]) ? k : -1)).filter((k) => k >= 0) // Simple: only the points the user marked in this session
    return keep.length ? { ...f, index: keep.map((k) => f.index[k]), status: keep.map((k) => f.status[k]) } : null
  }, [grid.data, detailed, showField, sessionMarks])
  const meta = useMemo(() => ({ purpose, species: selection ? idsParam : '' }), [purpose, selection, idsParam])
  const apiState = health.status === 'ok' ? 'ok' : health.status === 'loading' ? 'wait' : 'off'
  const legendSub = allRemoved
    ? 'The chosen species are out of season for your dates'
    : selection
    ? `${selIds.length === 1 ? selNames[0] : `${selIds.length} species`} · ${selIds.length === 1 ? 'one species' : combine === 'all' ? 'must suit all' : 'suits at least one'}`
    : 'Best species at each point'

  return (
    <div className={`nw-root ${showPanel ? 'panel-open' : ''} ${sidebarOpen ? 'sidebar-open' : ''} ${showGround ? 'has-ground' : ''}`}>
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
          contextCols={contextCols}
          contextVisible={detailed && showOther}
          detailed={detailed}
          ground={groundInfo}
          groundOn={showGround}
          contextLabeler={contextLabeler}
          safeArea={safeArea}
          planItems={planItems}
          planVisible={showPlan}
          planLabeler={planLabeler}
        />
      </div>

      <MapViewMenu showGround={showGround} onShowGround={setShowGround} detailed={detailed} onDetailed={setDetailed} baseLayer={baseLayer} onBaseLayer={setBaseLayer} showField={showField} onShowField={setShowField} showOther={showOther} onShowOther={setShowOther} showPlan={showPlan} onShowPlan={setShowPlan} hasPlan={!!planResult} />
      <SearchBar locate={locate} onChoose={onSearchChoose} note={searchNote} onDismissNote={() => setSearchNote(null)} includeUnzoned={includeUnzoned} />

      {/* messages over the map */}
      <div className="nw-toasts v2 v2-embedded">
        {grid.status === 'loading' && <Loading what="Loading the grid points" />}
        {grid.status === 'error' && <ErrorBox error={grid.error} onRetry={grid.retry} title="Could not load the grid points" />}
        {fewSpecies && seasonNotice(true)}
        {boundaries.status === 'error' && !boundaries.error.network && <ErrorBox error={boundaries.error} onRetry={boundaries.retry} title="Could not load the outlines" brief />}
      </div>

      {/* legend of the colours (on the map) */}
      {legendOpen ? (
        <div className="nw-legend v2 v2-embedded" role="group" aria-label="Map legend">
          <div className="nw-legend-head">
            <strong>{view === 'full' ? 'Overall score W' : 'Overall match'} · {purposeLabel(purpose)}</strong>
            <button type="button" className="btn btn-small" aria-expanded="true" onClick={() => setLegendOpen(false)}>
              Hide legend
            </button>
          </div>
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
                <Icon name="ring" /> verified plantable
              </li>
              <li>
                <Icon name="close" /> not plantable (left out)
              </li>
              <li>
                <Icon name="triangle" /> needs recheck
              </li>
            </ul>
          )}
          {contextData.status === 'ok' && (
            <div className="nw-legend-other">
              <span className="nw-legend-dot" aria-hidden="true" /> Planting squares: <strong>{contextData.data.legal_points.toLocaleString('en-US')}</strong> · Other map squares (not planting zones): <strong>{contextData.data.n.toLocaleString('en-US')}</strong>
              {detailed && showOther ? '' : ' (hidden: Detailed view)'}
              {grid.data?.zoning && (
                <div>
                  <Icon name="dotring" size={14} /> 
                  {grid.data.zoning.n_unconfirmed.toLocaleString('en-US')} of the planting squares are outside our zoning map (CLUP: Forest Reserve, Watershed)
                </div>
              )}
            </div>
          )}
          <div className="nw-legend-note">Each dot is a 100 m grid cell in a planting zone. Blue-ringed dot = the chosen point.</div>
        </div>
      ) : (
        <button type="button" className="nw-legend-btn" aria-expanded="false" onClick={() => setLegendOpen(true)}>
          <Icon name="legend" /> Legend
        </button>
      )}

      {showGround && <GroundLegend data={landcover.status === 'ok' ? landcover.data : null} onHide={() => setShowGround(false)} />}

      {planResult && <PlanLegend species={[...planSpecies.values()]} visible={showPlan} nUnconfirmed={nPlanUnconfirmed} blocks={planResult.layout_mode === 'blocks'} />}

      {/* TOP GLASS NAVIGATION BAR (look copied from the earlier dashboard) */}
      <header className="nw-topbar">
        <div className="nw-brandrow">
          <div className="nw-brand">
            <Icon name="tree" size={18} /> LGU SAN MATEO
          </div>
          <div title="Urban Tree Planting Decision Support System. Municipal Environment and Natural Resources Office (MENRO)">
            <div className="nw-title">Tree Planting Decision Support</div>
            <div className="nw-subtitle">MENRO · San Mateo, Rizal</div>
          </div>
        </div>
        <div className="nw-tabs" role="tablist" aria-label="Views">
          {TABS.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={`nw-tab ${tab === t.id ? 'is-active' : ''}`} onClick={() => setTab(t.id)}>
              <Icon name={t.icon} size={18} /> {t.label}
            </button>
          ))}
        </div>
        <div className="nw-topright">
          <HelpButton onClick={() => help.setHowOpen(true)} />
          <div className="nw-pill" role="status">
            <span className={`nw-dot nw-dot-${apiState}`} aria-hidden="true" />
            <span>{apiState === 'ok' ? 'API connected' : apiState === 'wait' ? 'Connecting…' : 'API offline'}</span>
          </div>
        </div>
      </header>
      {tab !== 'studio' && (
        <section className="nw-modal" aria-label={TABS.find((t) => t.id === tab).label}>
          <div className="nw-modal-head">
            <h2>{tab === 'history' ? 'Campaign Event Logs & History' : tab === 'weather' ? 'Weather this week' : 'System Spatial Analytics'}</h2>
            <button type="button" className="nw-btn" onClick={() => setTab('studio')}>
              <Icon name="close" /> Close & Return to Map
            </button>
          </div>
          {tab === 'history' ? (
            <CampaignLogs today={win.today} onOpen={openSavedPlan} onStudio={() => setTab('studio')} fieldVersion={fieldVersion} onTopUp={openTopUp} />
          ) : tab === 'weather' ? (
            <WeatherTab
              purpose={purpose}
              onPurpose={setPurpose}
              view={view}
              onView={setView}
              loc={weatherLoc === 'point' && !spot ? 'centre' : weatherLoc === 'plan' && !planWeatherLoc ? 'centre' : weatherLoc}
              onLoc={setWeatherLoc}
              barangays={barangayFeatures}
              spot={spot}
              planLoc={planWeatherLoc}
              onInfo={setCardId}
              includeUnzoned={includeUnzoned}
            />
          ) : (
            <AnalyticsPanel includeUnzoned={includeUnzoned} />
          )}
        </section>
      )}

      {/* SIDEBAR (look copied from the earlier dashboard) */}
      <button type="button" className="nw-toggle" onClick={() => setSidebarOpen((o) => !o)} aria-expanded={sidebarOpen} aria-controls="nw-sidebar">
        <Icon name={sidebarOpen ? 'left' : 'right'} /> {sidebarOpen ? 'Hide Control Panel' : 'Open Control Panel'}
      </button>
      <aside id="nw-sidebar" className="nw-sidebar" aria-label="Controls">
        {!help.bannerOff && <HelpBanner onStart={() => help.setTourStep(0)} onDismiss={help.dismissBanner} />}
        <SidebarStep
          n={1}
          id="goal"
          icon="target"
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
          icon="tree"
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
          icon="calendar"
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
          icon={mode === 'species' ? 'tree' : 'pin'}
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
              {selIds.length > 0 && selIds.length <= 5 && (
                <PairsWith speciesId={selIds[selIds.length - 1]} chosen={selIds} query={seasonQuery(win.applied, false)} onAdd={(ids) => setSelIds((cur) => [...cur, ...ids.filter((i) => !cur.includes(i))])} />
              )}
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
          <UnzonedToggle value={includeUnzoned} onChange={setIncludeUnzoned} />
          {planPrefill && (
            <div className="nw-prefill">
              <span>
                Plan area: <strong>{planPrefill.area.name}</strong>
              </span>
              <button type="button" className="nw-btn nw-btn-small" onClick={() => setPlanPrefill(null)}>
                Clear
              </button>
            </div>
          )}
          <button type="button" className="nw-btn nw-btn-go nw-btn-wide" onClick={() => setOpenStep('plan')}>
            Continue
          </button>
        </SidebarStep>
        <SidebarStep
          n={5}
          id="plan"
          icon="clipboard"
          title="Plan"
          summary={`${campaignName.trim() || 'No name yet'} · ${planTotal} trees${planResult ? ' · created' : ''}`}
          open={openStep === 'plan'}
          onToggle={() => toggleStep('plan')}
          help="Creates a saved planting plan from the area, dates and species you chose in the steps above."
        >
          <PlanStep
            name={campaignName}
            onName={setCampaignName}
            unit={campaignUnit}
            onUnit={setCampaignUnit}
            n={nSaplings}
            onN={setNSaplings}
            nValid={nValid}
            areaLabel={planAreaLabel}
            modeLabel={countsMode ? `Your species (${selIds.length})` : 'Mix chosen automatically'}
            countsMode={countsMode}
            countRows={countRows}
            counts={counts}
            onCount={(id, v) => setCounts((c) => ({ ...c, [id]: v }))}
            areaMode={mode === 'area'}
            ownSpecies={ownSpecies && mode === 'area'}
            onOwnSpecies={() => setOwnSpecies(true)}
            onAutoMix={() => setOwnSpecies(false)}
            picker={<SpeciesMultiPicker species={species} selected={selIds} onChange={setSelIds} onlySeason={onlySeason} onInfo={setCardId} />}
            windowText={`${formatRange(win.applied.start, win.applied.end)} · ${onlySeason ? 'only species for your dates' : 'all species'}`}
            preview={preview}
            reason={planReason}
            onCreate={createPlan}
            creating={creating}
            createError={createError}
            result={planResult}
            onAnother={anotherPlan}
            seasonNoticeProps={sInfo ? { kept, total: sInfo.species_total, start: win.applied.start, end: win.applied.end, onShowAll: showAllSpecies, onChangeDates: changeDates } : null}
          />
        </SidebarStep>
        <MoreMenu health={health} fieldSummary={fieldSummary} observer={observer} onObserver={setObserver} onChanged={bumpField} />
      </aside>

      {(hasMain || hasPoint || hasPlanTab) && hidden && (
        <button type="button" className="nw-reopen" onClick={() => setHidden(false)}>
          Show results
        </button>
      )}
      {showPanel && (
        <RightPanel
          title={activeTab === 'plan' ? 'Planting plan' : activeTab === 'point' ? (isContext ? 'Not a planting zone' : 'Species for this point') : mode === 'species' ? 'Areas for the selected species' : `Species for ${areaLabel}`}
          subtitle={purposeLabel(purpose)}
          tabs={tabs}
          activeTab={activeTab}
          onTab={setPanelTab}
          onClose={() => setHidden(true)}
        >
          {activeTab === 'plan' && planResult ? (
            <div className="v2 v2-embedded">
              <PlanResult result={planResult} speciesInfo={planSpecies} view={view} onView={setView} onOpenPoint={openPlanPoint} onAnother={anotherPlan} onOpenWeather={openWeatherForPlan} includeUnzoned={includeUnzoned} fieldVersion={fieldVersion} onTopUp={openTopUp} onOpenPlan={(id) => openSavedPlan(id).catch((e) => setCreateError(e.message))} onShowOnMap={showOnMap} />
            </div>
          ) : activeTab === 'point' ? (
            <div className="v2 v2-embedded">
              {isContext && contextData.status === 'ok' ? (
                <ContextPanel
                  key={`ctx-${spot.context}`}
                  data={contextData.data}
                  index={spot.context}
                  win={win.applied}
                  today={win.today}
                  searched={spot.searched}
                  viable={viable}
                  onFindViable={() => setViableFor(spotQuery)}
                  onGo={goTo}
                  onIncludeUnzoned={() => setIncludeUnzoned(true)}
                />
              ) : (
                <PointPanel
                  key={`${purpose}|${spot.lat}|${spot.lon}`}
                  rank={shownRank}
                  purpose={purpose}
                  win={win.applied}
                  today={win.today}
                  barangay={pointBarangay}
                  searched={spot.searched}
                  pointId={pointId}
                  fieldApi={fieldPoint}
                  observer={observer}
                  onObserver={setObserver}
                  onSaved={() => {
                    bumpField()
                    if (pointId) setSessionMarks((s) => new Set(s).add(pointId))
                  }}
                  viable={viable}
                  onFindViable={() => setViableFor(spotQuery)}
                  onGo={goTo}
                  seasonNote={seasonNotice(true)}
                  onInfo={setCardId}
                  view={view}
                  onView={setView}
                  chosen={chosenQ ? chosenRank : null}
                  selIds={selIds}
                  combine={combine}
                  onlySeason={onlySeason}
                  planBlock={planBlock}
                />
              )}
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
              onPlan={planFromRow}
              view={view}
              onView={setView}
              allRemoved={allRemoved}
              seasonNote={selectedRemoved.length > 0 ? seasonNotice(true, `${selectedRemoved.map((id) => speciesNames.get(id) ?? `species ${id}`).join(', ')} ${selectedRemoved.length === 1 ? 'is' : 'are'} out of season between ${formatDay(win.applied.start)} and ${formatDay(win.applied.end)} and left out.`) : null}
            />
          ) : (
            <AreaResultPanel api={areaRank} areaLabel={areaLabel} onShowAll={showAllSpecies} onChangeDates={changeDates} onInfo={setCardId} view={view} onView={setView} />
          )}
        </RightPanel>
      )}
      {help.howOpen && (
        <HowToUse
          onClose={() => help.setHowOpen(false)}
          onTour={() => {
            help.setHowOpen(false)
            setSidebarOpen(true)
            help.setTourStep(0)
          }}
        />
      )}
      {help.tourStep !== null && <Tour step={help.tourStep} onStep={help.setTourStep} onFinish={help.finishTour} onOpenStep={(id) => { setSidebarOpen(true); setOpenStep(id) }} />}
      {cardId !== null && (
        <SpeciesCard
          speciesId={cardId}
          window={win.applied}
          onClose={() => setCardId(null)}
          point={spot ? { lat: spot.lat, lon: spot.lon, label: 'the point you clicked' } : { lat: MAP_CENTER[0], lon: MAP_CENTER[1], label: 'the middle of San Mateo' }}
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
