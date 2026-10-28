import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Callout from './ui/Callout.jsx'
import '../v2/v2.css'
import './new.css'
import './canopy.css'
import SettingsMenu from './SettingsMenu.jsx'
import HintsSwitch from './HintsSwitch.jsx'
import { useHints } from './hints.js'
import { Tabs } from './ui/ui.jsx'
import ToastViewport from './ui/ToastViewport.jsx'
import { toast } from './ui/toast.js'
import { sparkBurst } from './ui/spark.js'
import { findPosition, geoMessageKey } from './myLocation.js'
import { AnimatePresence, motion } from 'motion/react'
import { motionAllowed } from './motionPref.js'
import Splash from './Splash.jsx'
import Landing from './Landing.jsx'
import { markVisit, shouldShowLanding } from './landing.js'
import AskHelp from './tutorial/AskHelp.jsx'
import Icon from './Icon.jsx'
import ColorLegend from '../v2/components/ColorLegend.jsx'
import GroundLegend from './GroundLegend.jsx'
import { GROUND_GROUPS, GROUND_STYLE } from './groundStyle.js'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { purposeLabel } from '../v2/labels.js'
import { LEVEL_WORD, pct, wLevel } from '../v2/scale.js'
import { useApi } from '../v2/useApi.js'
import AreaChooser from './AreaChooser.jsx'
import AreaResultPanel from './AreaResultPanel.jsx'
import AreasPanel from './AreasPanel.jsx'
import { decodeFieldCode, STATUS_LABEL } from './fieldLabels.js'
import { featureAt, geometryBbox, polygonFromVertices } from './geo.js'
import { continueState, describeArea, diagnosticText, geometryHectares, haText } from './areaInfo.js'
import { tr, useLang } from './i18n.js'
import { sitePhText } from './phEvidence.js'
import FieldMenu from './FieldMenu.jsx'
import { menuLines } from './pointMenu.js'
import { PURPOSE_SHORT } from './labelsNew.js'
import MoreMenu from './MoreMenu.jsx'
import MapViewMenu from './MapViewMenu.jsx'
import PlanLegend from './PlanLegend.jsx'
import PlanResult from './PlanResult.jsx'
import PlanStep from './PlanStep.jsx'
import { countText, countsSummary } from './counts.js'
import FieldLegend from './FieldLegend.jsx'
import ZoningLegend from './ZoningLegend.jsx'
import ToursMenu from './tours/ToursMenu.jsx'
import useTourBridge from './tours/useTourBridge.js'
import { getTour, PAGE_TOUR } from './tours/tourDefs.js'
import { startTour } from './tours/tourController.js'
import { EXAMPLE_POINT, EXAMPLE_VERTICES } from './tours/tourExample.js'
import HelpPage from './tutorial/HelpPage.jsx'
import ScoreSourceNotice from './ScoreSourceNotice.jsx'
import PublicNotice from './PublicNotice.jsx'
import { isSandbox, SANDBOX_NOTICE_HEIGHT, FALLBACK_NOTICE_HEIGHT } from './publicMode.js'
import { isFallback } from './scoreSource.js'
import { HelpContext } from './tutorial/helpContext.js'
import { useHelpState } from './help.js'
import { matchText } from './plainWords.js'
import { apiPost } from './apiPost.js'
import { apiGet } from '../v2/api.js'
import { MAP_CENTER } from '../v2/config.js'
import PlantingWindow from './PlantingWindow.jsx'
import PointPanel from './PointPanel.jsx'
import ContextPanel from './ContextPanel.jsx'
import SpeciesCard from './SpeciesCard.jsx'
import MapNew from './MapNew.jsx'
import ModeSwitch from './ModeSwitch.jsx'
import PurposePicker from './PurposePicker.jsx'
import RightPanel from './RightPanel.jsx'
import SearchBar from './SearchBar.jsx'
import { formatDay, formatRange, monthsText, seasonQuery, windowMonths } from './season.js'
import SeasonNotice from './SeasonNotice.jsx'
import SidebarStep from './SidebarStep.jsx'
import SpeciesChooser from './SpeciesChooser.jsx'
import SpeciesFlow from './SpeciesFlow.jsx'
import { useObserver } from './useObserver.js'
import { usePost } from './usePost.js'
import { useIncludeUnzoned, useLegendOpen, useMapDetail, useViewMode } from './useViewMode.js'
import UnzonedToggle from './UnzonedToggle.jsx'
// the three tab pages are loaded when first opened (the charts, the weather and the logs are not needed to plan): a smaller first download and less memory on a phone
const AnalyticsPanel = lazy(() => import('./AnalyticsPanel.jsx'))
const CampaignLogs = lazy(() => import('./CampaignLogs.jsx'))
const WeatherTab = lazy(() => import('./WeatherTab.jsx'))
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
  const lang = useLang()
  const hints = useHints()
  const pageTitle = useRef(null)
  // "My location": the position stays in memory (never logged, never sent). The button shows "Finding your location…" while it works and never stays stuck; any failure says what to do and offers
  // "Set my location on the map" (the next tap on the map sets it).
  const [myLoc, setMyLoc] = useState(null)
  const [locating, setLocating] = useState(false)
  const [pickingMe, setPickingMe] = useState(false)
  const [locFailed, setLocFailed] = useState(false)
  const placeMe = (pos, fromTap) => {
    setMyLoc({ lat: pos.lat, lon: pos.lon })
    setGoTarget({ lat: pos.lat, lon: pos.lon })
    setLocFailed(false)
    if (!locate(pos.lat, pos.lon)) toast('info', tr('geo.outside', {}, lang))
    else if (fromTap) toast('success', tr('geo.set', {}, lang))
  }
  const locateMe = async () => {
    if (locating) return
    setLocating(true)
    setPickingMe(false)
    try {
      placeMe(await findPosition())
    } catch (e) {
      setLocFailed(true)
      toast('warning', tr(geoMessageKey(e), {}, lang), 9000)
    } finally {
      setLocating(false)
    }
  }
  const [landing, setLanding] = useState(() => shouldShowLanding())
  const [firstVisit] = useState(() => shouldShowLanding())
  const closeLanding = () => {
    markVisit()
    setLanding(false)
  }
  const [tool, setTool] = useState('point') // mode 2: 'point' | 'barangay' | 'draw'
  const [area, setArea] = useState(null) // mode 2: {kind:'barangay'|'zone', name} | {kind:'polygon', geometry}
  const [draft, setDraft] = useState([]) // mode 2: corners of the shape being drawn, [lat, lon]
  const [markArea, setMarkArea] = useState(null) // goal "I have species", step 3 "Markahan sa mapa": the finished shape {kind:'polygon', geometry} (UX round 4)
  const [notice, setNotice] = useState('')
  const [spot, setSpot] = useState(null) // the clicked point {lat, lon}
  const [fieldMenu, setFieldMenu] = useState(null) // the menu of a square {x, y, pick, pointId, square: {lat, lon, pointId}, click: {lat, lon}} (x null = centred), or null
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
  const [speciesSub, setSpeciesSub] = useState(1) // goal "I have species", step 4: 1 species, 2 where to look, 3 the best areas (right card)
  const [where, setWhere] = useState({ kind: 'all', name: '' }) // "Saan hahanapin": the whole municipality, one barangay or one zone
  const [speciesHow, setSpeciesHow] = useState('') // UX 12: '' (not asked yet) | 'one' | 'many'
  const [mainSpecies, setMainSpecies] = useState(null) // UX 12: the main species when the person chose many
  const [ownSpecies, setOwnSpecies] = useState(false) // goal "I have an area": the user chose their own species and counts
  const [focusIds, setFocusIds] = useState(() => new Set()) // planned squares to circle on the map ("Show these on the map")
  const help = useHelpState()
  const [toursOpen, setToursOpen] = useState(false)
  const [hasPlan, setHasPlan] = useState(false)
  const [planResult, setPlanResult] = useState(null) // the last plan created (it is also saved on the server)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [showPlan, setShowPlan] = useState(true) // the "Planned trees" layer
  const win = usePlantingWindow()
  const [onlySeason] = useOnlySeason() // always false: the dates label species, they never remove one (W1)
  const [tab, setTab] = useState('studio')
  const [fieldVersion, setFieldVersion] = useState(0) // bumped after every saved field check: reloads what depends on them (and skips the browser cache)
  const [showField, setShowField] = useState(true)
  const [showGround, setShowGround] = useState(false) // the optional ground-cover layer (default off)
  const [showZoning, setShowZoning] = useState(false) // the optional Zoning overlay (MPDC colours, default off)
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
  const zoning = useApi(showZoning ? '/geo/zoning' : null) // every land-use zone with its rule, condition and number of squares
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
  const kept = sInfo ? sInfo.species_total : null
  const fewSpecies = !!sInfo && sInfo.in_season + sInfo.partly === 0 // no species is in its best months for these dates: say so, the species stay listed (W1)
  const selectedRemoved = selection ? (grid.data?.season?.selected_removed_ids ?? []) : []
  const allRemoved = selection && selectedRemoved.length === selIds.length
  const showAllSpecies = () => {
    setSidebarOpen(true)
    setOpenStep('pick')
  }
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

  const markActive = mode === 'species' && speciesSub === 3 && !markArea
  const highlight = useMemo(() => {
    const spec = mode === 'area' ? area : markArea || rowActive
    if (!spec) return null
    if (spec.kind === 'polygon') return spec.geometry
    return (spec.kind === 'barangay' ? barangayFeatures : zoneFeatures).find((f) => f.properties.name === spec.name)?.geometry ?? null
  }, [mode, area, markArea, rowActive, barangayFeatures, zoneFeatures])

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
        w > 0 ? (view === 'full' ? `Score W ${pct(w)} (${LEVEL_WORD[wLevel(w, true)]})` : `Overall match ${matchText(w)}`) : view === 'full' ? 'Not suitable here (score 0)' : 'Not suitable here',
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
    setFieldMenu(null)
    if (pickingMe) {
      placeMe({ lat, lon }, true)
      setPickingMe(false)
      return
    }
    if (mode === 'area' && tool === 'draw') {
      if (area?.kind === 'polygon') {
        setNotice(tr('area.lockNotice', {}, lang)) // UX round 2 (A2)
        return
      }
      setDraft((d) => [...d, [lat, lon]])
      return
    }
    if (mode === 'species' && speciesSub === 3) {
      // Markahan sa mapa: one click is a point (the point panel opens); three or more clicks and "Tapusin" make an area
      if (markArea) {
        setNotice(tr('mark.lockNotice', {}, lang))
        return
      }
      // the right card stays closed while marking, so that it never covers the map; the first click also keeps the spot, and "Tingnan ang species sa puntong ito" opens its panel
      if (draft.length === 0) setSpot(columns && index >= 0 ? { lat: columns.lat[index], lon: columns.lon[index], pointId: columns.point_id[index] } : { lat, lon })
      setDraft((d) => [...d, [lat, lon]])
      setNotice('')
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
  // Right-click (or long press) on the map: ONLY a menu opens (where this is, "Tingnan ang species dito", the field check). The right card does not open and nothing is selected: that is what a left click does.
  // Not while drawing an area, and only for planting squares and planned blocks.
  const onContext = (pick) => {
    if ((mode === 'area' && tool === 'draw') || (markActive && draft.length > 0)) return
    let sq = null
    if (pick.plan >= 0 && planResult) {
      const it = planResult.plan[pick.plan]
      sq = { lat: it.lat, lon: it.lon, pointId: it.point_id }
    } else if (pick.index >= 0 && columns) {
      sq = { lat: columns.lat[pick.index], lon: columns.lon[pick.index], pointId: columns.point_id[pick.index] }
    }
    if (!sq) {
      setFieldMenu(null)
      setNotice(pick.context >= 0 ? tr('notice.notPlanting', {}, lang) : tr('notice.noSquare', {}, lang))
      return
    }
    setFieldMenu({ x: pick.x, y: pick.y, pick, pointId: sq.pointId, square: sq, click: { lat: pick.lat, lon: pick.lon } })
  }
  const chooseWhere = (w) => {
    setWhere(w)
    if (w.kind === 'all' || !w.name) {
      setRowActive(null)
      return
    }
    const f = featureOf(w.kind, w.name)
    if (f) {
      setRowActive({ kind: w.kind, name: w.name })
      setFitTarget({ bbox: f.properties.bbox })
    }
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
      changeMode('species') // the map and the Areas panel show the best squares for this species
      setSelIds([it.species_id])
      setRowActive(null)
      setSearchNote({ title: it.common_name, lines: ['The species card is open and the map shows the best squares for it.'] })
      return
    }
    const rankable = it.type === 'grid_point' && (it.legal_zone || it.zoning_status === 'unconfirmed')
    const pointId = it.type === 'plan_point' || rankable ? it.point_id : undefined
    const searched =
      it.type === 'coords' ? `coordinates ${it.lat.toFixed(5)}, ${it.lon.toFixed(5)}` : it.type === 'grid_point' ? `${tr('search.point', {}, lang)} ${it.point_id}` : it.type === 'plan_point' ? `${it.point_ref} (${it.species})` : (it.name || it.display_name)
    const ci = it.type === 'grid_point' && !rankable && contextCols ? contextCols.point_id.indexOf(it.point_id) : -1
    setSpot({ lat: it.lat, lon: it.lon, searched, ...(it.type === 'plan_point' ? { planned: true } : {}), ...(ci >= 0 ? { context: ci } : pointId ? { pointId } : {}) })
    setGoTarget({ lat: it.lat, lon: it.lon })
    setPanelTab('point')
    setHidden(false)
    setNotice('')
    if (it.type === 'plan_point') {
      setSearchNote({ title: `${it.point_ref} · ${it.species}`, lines: [`Plan ${it.plan_id}`, `${tr('search.pointLabel', { id: it.point_id }, lang)}${it.barangay_display ? ' · ' + it.barangay_display : ''}`] })
    } else if (it.type === 'grid_point') {
      setSearchNote({ title: tr('search.pointLabel', { id: it.point_id }, lang), lines: [it.note ?? `${it.barangay_display || 'Outside the barangay outlines'} · ${it.zone}`] })
    } else if (it.type === 'place') {
      setSearchNote({ title: it.name || it.display_name, lines: [it.display_name], attribution: it.attribution })
    } else {
      setSearchNote({ title: `${it.lat.toFixed(5)}, ${it.lon.toFixed(5)}`, lines: [it.note || 'Marked on the map. If it is outside San Mateo or not a planting zone, the panel says so and offers the nearest suitable spot.'] })
    }
  }
  const finishDraw = () => {
    if (draft.length < 3) return
    if (mode === 'species') {
      setMarkArea({ kind: 'polygon', geometry: polygonFromVertices(draft) })
      setNotice('')
      setPanelTab('main')
      setHidden(false)
      setSidebarOpen(true) // the summary is in the sidebar: bring it back on a narrow screen
    } else chooseArea({ kind: 'polygon', geometry: polygonFromVertices(draft) })
    setFitTarget({ bbox: geometryBbox(polygonFromVertices(draft)) })
    setDraft([])
  }
  // one marked point = a plan on the one 100 m square it stands in (a 100 m box around the centre of the square, or around the click when no square was hit): the service then selects that one square
  const usePoint = () => {
    if (draft.length !== 1) return
    const [lat0, lon0] = spot && spot.pointId !== undefined ? [spot.lat, spot.lon] : draft[0]
    const dlat = 50 / 111320
    const dlon = 50 / (111320 * Math.cos((lat0 * Math.PI) / 180))
    const corners = [[lat0 - dlat, lon0 - dlon], [lat0 - dlat, lon0 + dlon], [lat0 + dlat, lon0 + dlon], [lat0 + dlat, lon0 - dlon]]
    const geometry = polygonFromVertices(corners)
    setMarkArea({ kind: 'polygon', single: true, geometry })
    setFitTarget({ bbox: geometryBbox(geometry) })
    setDraft([])
    setNotice('')
    setSidebarOpen(true)
  }
  const clearMark = () => {
    setDraft([])
    setMarkArea(null)
    setNotice('')
  }
  const goSub = (n) => {
    setSpeciesSub(n)
    if (n === 3) setHidden(true)
    if (n !== 3) setDraft([]) // a half-drawn shape is dropped when the person leaves the step; a finished one is kept
    setNotice('')
  }
  const changeMode = (m) => {
    setMode(m)
    setOwnSpecies(false)
    setPanelTab('main')
    setHidden(false)
    setTool('point')
    setDraft([])
    setMarkArea(null)
    setNotice('')
  }
  const toggleStep = (id) => setOpenStep((o) => (o === id ? '' : id))
  const changeTool = (t) => {
    setTool(t)
    if (t !== 'draw') setDraft([])
    setNotice('')
  }

  const hasMain = mode === 'species' ? selection : !!area
  // UX 2-5: what the Area step says about the choice, and whether Continue may be pressed (an area with no planting square blocks it)
  const cont = continueState({ mode, area, areaRank, lang })
  // UX 12: one species or many (a main species and the species that can go with it on the same land)
  const chooser = (forArea) => (
    <SpeciesChooser species={species} selected={selIds} onChange={setSelIds} onlySeason={onlySeason} onInfo={setCardId} purpose={purpose} area={forArea} query={sq} how={speciesHow} onHow={setSpeciesHow} mainId={mainSpecies} onMain={setMainSpecies} />
  )
  // goal "I have species": the area the plan will use = the shape marked on the map, else the area chosen with "Plan here", else the barangay or zone of "Saan hahanapin"
  const whereArea = where.kind !== 'all' && where.name ? { kind: where.kind, name: where.name } : null
  const speciesArea = markArea || (planPrefill ? { kind: planPrefill.area.kind, name: planPrefill.area.key } : whereArea)
  const diagArea = mode === 'area' ? area : speciesArea
  const diag = usePost(`/area/diagnostic?${uz}`, !diagArea ? null : diagArea.kind === 'barangay' ? { barangay: diagArea.name } : diagArea.kind === 'zone' ? { zone: diagArea.name } : { polygon: diagArea.geometry })
  const areaSplit = diag.status === 'ok' ? diagnosticText(diag.data, lang) : null
  const areaSummary = useMemo(
    () => (mode !== 'area' ? [] : describeArea({ tool, area, spot, barangayFeatures, zoneFeatures, squares: areaRank.status === 'ok' ? areaRank.data.area.legal_points : null, selection: areaRank.status === 'ok' ? areaRank.data.area.selection ?? null : null, split: areaSplit, ph: areaRank.status === 'ok' ? areaRank.data.area.ph ?? null : null, lang })),
    [mode, tool, area, spot, barangayFeatures, zoneFeatures, areaRank.status, areaRank.data, areaSplit, lang],
  )
  const hasPoint = !!spot
  const hasPlanTab = !!planResult
  const avail = { plan: hasPlanTab, main: hasMain, point: hasPoint }
  const activeTab = avail[panelTab] ? panelTab : (['plan', 'main', 'point'].find((k) => avail[k]) ?? 'point')
  const showPanel = (hasMain || hasPoint || hasPlanTab) && !hidden
  // UX 14: two different lists, two clear names, one sentence each (they are never merged)
  const tabs = [
    ...(hasPlanTab ? [{ id: 'plan', label: 'Plan', hint: tr('tab.plan.hint', {}, lang) }] : []),
    ...(hasMain
      ? [{ id: 'main', label: tr(mode === 'species' ? 'tab.main.species' : 'tab.main.area', {}, lang), hint: tr(mode === 'species' ? 'tab.main.hint.species' : 'tab.main.hint.area', {}, lang) }]
      : []),
    ...(hasPoint ? [{ id: 'point', label: tr('tab.point', {}, lang), hint: tr('tab.point.hint', {}, lang) }] : []),
  ]
  const areaLabel = !area ? '' : area.kind === 'polygon' ? 'the drawn area' : (featureOf(area.kind, area.name)?.properties.display_name ?? area.name)

  // ---- step 5 "Plan"
  const nNum = Number(nSaplings)
  const countsMode = mode === 'species' || ownSpecies // one number per chosen species, or one total for the automatic mix
  const countRows = useMemo(() => [...selIds].sort((a, b) => a - b).map((id) => ({ id, name: speciesNames.get(id) ?? `species ${id}` })), [selIds, speciesNames])
  const cs = countsSummary(countRows.map((r) => r.id), counts)
  const nValid = countsMode ? cs.valid : /^\d+$/.test(String(nSaplings).trim()) && nNum >= 1 && nNum <= 2000
  const planTotal = countsMode ? cs.total : nNum
  const planArea = mode === 'area' ? area : speciesArea
  const planAreaBody = !planArea ? null : planArea.kind === 'barangay' ? { barangay: planArea.name } : planArea.kind === 'zone' ? { zone: planArea.name } : { polygon: planArea.geometry }
  const planAreaLabel = !planArea ? '' : planArea.kind === 'polygon' ? (planArea.single ? 'One square' : 'The drawn area') : (featureOf(planArea.kind, planArea.name)?.properties.display_name ?? planArea.name)
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
    ? 'Lagyan ng pangalan ang plano'
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
      sparkBurst(document.querySelector('[data-role="create-plan"]'))
      toast('success', tr('toast.planCreated', { name: campaignName.trim() }, lang))
      // the Plan step's own fields go back to their defaults once the plan is safely created (the result itself, and the rest of the sidebar - goal, purpose, dates,
      // species, area - stay as they are: only this one step's form is "used up" by a successful create)
      setCampaignName('')
      setCampaignUnit('')
      setNSaplings('100')
      setCounts({})
    } catch (e) {
      setCreateError(e.message)
      toast('error', tr('toast.planFailed', { msg: e.message }, lang))
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
  // the field-check menu of a right-click: its own field-check data, its own lines and its own plan block (the point panel keeps its own)
  const menuField = useApi(fieldMenu ? `/field-checks/${fieldMenu.pointId}?${fc}` : null)
  const menuInfo = useMemo(
    () => (fieldMenu ? menuLines({ square: fieldMenu.square, click: fieldMenu.click, barangayFeatures, zoneFeatures, win: win.applied, today: win.today, me: myLoc, fromYou: (m) => tr('geo.fromYou', { m }, lang) }) : { title: '', lines: [] }),
    [fieldMenu, barangayFeatures, zoneFeatures, win.applied, win.today, myLoc, lang],
  )
  const menuBlock = useMemo(() => {
    if (!fieldMenu || !planResult || planResult.layout_mode !== 'blocks') return null
    const item = planResult.plan.find((x) => x.point_id === fieldMenu.pointId)
    return item ? { planId: planResult.plan_id, trees: item.trees_planned, ref: item.block_ref } : null
  }, [fieldMenu, planResult])
  const nPlanUnconfirmed = useMemo(() => (planItems ? planItems.filter((x) => x.unconfirmed).length : 0), [planItems])
  const planLabeler = useMemo(
    () =>
      planResult
        ? (i) => {
            const it = planResult.plan[i]
            return [`${it.point_ref} · ${it.species}`, ...(it.trees_planned != null ? [`${it.trees_planned} trees · ${it.rows} rows of ${it.trees_per_row} · ${it.spacing_m} m apart`] : []), view === 'full' ? `S ${pct(it.S)} · P ${pct(it.P)} · W ${pct(it.W)}` : `Overall match ${matchText(it.W)}`, `Barangay: ${it.barangay_display || 'outside the barangay outlines'}`, it.flags.includes('zoning_unconfirmed') ? 'Zoning: not on the zoning map (not confirmed)' : `Zone: ${it.zone}`]
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
    selectRow(kind, row) // UX 6: the outline is highlighted and the map zooms to the area, as when its name is clicked
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
    return keep.length ? { ...f, index: keep.map((k) => f.index[k]), status: keep.map((k) => f.status[k]), class: f.class ? keep.map((k) => f.class[k]) : undefined } : null
  }, [grid.data, detailed, showField, sessionMarks])
  const meta = useMemo(() => ({ purpose, species: selection ? idsParam : '' }), [purpose, selection, idsParam])
  const apiState = health.status === 'ok' ? 'ok' : health.status === 'loading' ? 'wait' : 'off'
  const healthData = health.status === 'ok' ? health.data : null
  const sandbox = isSandbox(healthData)                        // the public sandbox: a notice at the top (text from the service)
  const noticeH = (isFallback(healthData) ? FALLBACK_NOTICE_HEIGHT : 0) + (sandbox ? SANDBOX_NOTICE_HEIGHT : 0)
  const scoreFallback = isFallback(healthData)                 // the service fell back from the Random Forest to the rules: a notice at the top
  const usingRules = healthData?.s_source === 'rules'          // the rules make S (fallback or chosen): Help must not say the forest does
  const legendSub = allRemoved
    ? 'The chosen species are out of season for your dates'
    : selection
    ? `${selIds.length === 1 ? selNames[0] : `${selIds.length} species`} · ${selIds.length === 1 ? 'one species' : combine === 'all' ? 'must suit all' : 'suits at least one'}`
    : 'Best species at each point'

  // the tabs are full pages: Esc goes back to the studio, and the page title takes the focus when a tab opens
  useEffect(() => {
    if (tab === 'studio') return undefined
    // the page mounts after the old one has faded out: focus the title of the page that is really there
    const focusTimer = setTimeout(() => (document.querySelector('[data-role="tab-page"] h1') ?? pageTitle.current)?.focus({ preventScroll: true }), 220)
    const onKey = (e) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      if (document.querySelector('[role="dialog"], .set-menu, .nw-helppage, .ln-root')) return
      setTab('studio')
    }
    document.addEventListener('keydown', onKey)
    return () => {
      clearTimeout(focusTimer)
      document.removeEventListener('keydown', onKey)
    }
  }, [tab])
  // ---- the tour engine's handle on this page (R1 W3): navigation and selection only, never a write
  const runTour = (id, section) => {
    const t = getTour(id)
    if (!t) return
    setToursOpen(false)
    help.closeHelp()
    startTour(t, { section })
  }
  const startPageTour = () => runTour(PAGE_TOUR[tab] ?? 'global')
  // first visit: once the landing is closed, the short tour of the header and the global controls starts by itself. The "seen" flag is set the moment it STARTS (not only when it
  // finishes or is skipped with the checkbox), so it never auto-triggers again once a first-time visitor has been shown it, whatever they do with it (close the tab, press Escape,
  // Skip, or let it finish) - the manual "Tours" menu still opens any tour at any time, flag or no flag.
  useEffect(() => {
    if (landing || !firstVisit) return undefined
    let seen = null
    try {
      seen = window.localStorage.getItem('nw_tour_done')
    } catch {
      /* storage refused: the tour is simply offered again next time */
    }
    if (seen === '1') return undefined
    const id = setTimeout(() => {
      const t = getTour('global')
      if (!t) return
      try {
        window.localStorage.setItem('nw_tour_done', '1')
      } catch {
        /* storage refused: the choice is not remembered, the tour may be offered again */
      }
      startTour(t, { auto: true })
    }, 900)
    return () => clearTimeout(id)
  }, [landing, firstVisit])
  useTourBridge({
    page: help.helpPage ? 'help' : tab,
    snapshot: () => ({ planResult, tab, openStep, mode, purpose, selIds, combine, speciesSub, speciesHow, mainSpecies, where, tool, area, draft, markArea, spot, sidebarOpen, view, panelTab, hidden, cardId, legendOpen, detailed, start: win.raw.start, end: win.raw.end, helpPage: help.helpPage }),
    restore: (s) => {
      setPlanResult(s.planResult); setTab(s.tab); setOpenStep(s.openStep); setMode(s.mode); setPurpose(s.purpose); setSelIds(s.selIds); setCombine(s.combine); setSpeciesSub(s.speciesSub); setSpeciesHow(s.speciesHow)
      setMainSpecies(s.mainSpecies); setWhere(s.where); setTool(s.tool); setArea(s.area); setDraft(s.draft); setMarkArea(s.markArea); setSpot(s.spot); setSidebarOpen(s.sidebarOpen)
      setView(s.view); setPanelTab(s.panelTab); setHidden(s.hidden); setCardId(s.cardId); setLegendOpen(s.legendOpen); setDetailed(s.detailed); setFieldMenu(null)
      win.setRange(s.start, s.end)
      if (s.helpPage) help.openHelp(s.helpPage.faq)
      else help.closeHelp()
    },
    setPage: (p) => {
      if (p === 'help') help.openHelp()
      else {
        help.closeHelp()
        setTab(p)
      }
    },
    setSidebar: (v) => setSidebarOpen(v),
    setStep: (id) => setOpenStep(id),
    setMode: (m) => (m === mode ? undefined : changeMode(m)),
    setSpeciesSub: (n) => setSpeciesSub(n),
    setHow: (h) => setSpeciesHow(h),
    setTool: (t) => changeTool(t),
    setExampleArea: () => chooseArea({ kind: 'polygon', geometry: polygonFromVertices(EXAMPLE_VERTICES) }),
    openExamplePoint: () => {
      setSpot({ lat: EXAMPLE_POINT.lat, lon: EXAMPLE_POINT.lon, pointId: EXAMPLE_POINT.id })
      setPanelTab('point')
      setHidden(false)
    },
    closePoint: () => setSpot(null),
    setView: (v) => setView(v),
    openExampleMenu: () => setFieldMenu({ x: null, y: null, pick: { lat: EXAMPLE_POINT.lat, lon: EXAMPLE_POINT.lon, index: -1, plan: -1, context: -1 }, pointId: EXAMPLE_POINT.id, square: { lat: EXAMPLE_POINT.lat, lon: EXAMPLE_POINT.lon, pointId: EXAMPLE_POINT.id }, click: { lat: EXAMPLE_POINT.lat, lon: EXAMPLE_POINT.lon } }),
    closeMenu: () => setFieldMenu(null),
    openSpeciesCard: (id) => setCardId(id),
    closeSpeciesCard: () => setCardId(null),
    setLegend: (v) => setLegendOpen(v),
    openLatestPlan: async () => {
      const r = await apiGet('/plans?limit=1')
      const id = (r.plans ?? r)?.[0]?.plan_id
      if (id) await openSavedPlan(id)
    },
  })
  useEffect(() => {
    if (!toursOpen) return undefined
    let live = true
    apiGet('/plans?limit=1').then((r) => live && setHasPlan(((r.plans ?? r) ?? []).length > 0), () => live && setHasPlan(false))
    return () => {
      live = false
    }
  }, [toursOpen])

  return (
    <HelpContext.Provider value={{ openHelp: help.openHelp, startPageTour }}>
    <PublicNotice health={healthData} />
    <ScoreSourceNotice health={healthData} />
    <div style={noticeH ? { '--nw-notice-h': `${noticeH}px` } : undefined} className={`nw-root ${tab !== 'studio' ? 'tab-page' : ''} lang-${lang} ${hints ? '' : 'hints-off'} ${mode === 'species' && openStep === 'pick' && speciesSub === 1 ? 'pick-species' : ''} ${scoreFallback || sandbox ? 'has-notice' : ''} ${showPanel ? 'panel-open' : ''} ${sidebarOpen ? 'sidebar-open' : ''} ${showGround ? 'has-ground' : ''} ${showZoning ? 'has-zoning' : ''}`}>
      <div className="nw-map">
        {boundaries.status === 'loading' && (
          <div className="nw-map-loading" role="status" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            <span>Loading map…</span>
          </div>
        )}
        <MapNew
          bbox={boundaries.data?.bbox ?? null}
          boundaries={boundaries.data}
          grid={columns}
          clearGrid={grid.status === 'error'}
          labeler={labeler}
          selected={selected}
          spot={spot}
          onPick={onPick}
          onContext={onContext}
          areaSquares={(mode === 'area' ? area : markArea)?.kind === 'polygon' && diag.status === 'ok' ? diag.data.squares ?? null : null}
          meta={meta}
          goTarget={goTarget}
          fitTarget={fitTarget}
          highlight={highlight}
          myLoc={myLoc}
          draft={draft}
          drawing={(mode === 'area' && tool === 'draw') || markActive}
          field={fieldForMap}
          baseLayer={baseLayer}
          contextCols={contextCols}
          contextVisible={detailed && showOther}
          detailed={detailed}
          ground={groundInfo}
          groundOn={showGround}
          zoning={zoning.status === 'ok' ? zoning.data : null}
          zoningOn={showZoning}
          contextLabeler={contextLabeler}
          safeArea={safeArea}
          planItems={planItems}
          planVisible={showPlan}
          planLabeler={planLabeler}
        />
      </div>

      <MapViewMenu showGround={showGround} onShowGround={setShowGround} showZoning={showZoning} onShowZoning={setShowZoning} detailed={detailed} onDetailed={setDetailed} baseLayer={baseLayer} onBaseLayer={setBaseLayer} showField={showField} onShowField={setShowField} showOther={showOther} onShowOther={setShowOther} showPlan={showPlan} onShowPlan={setShowPlan} hasPlan={!!planResult} />
      <SearchBar locate={locate} onChoose={onSearchChoose} note={searchNote} onDismissNote={() => setSearchNote(null)} includeUnzoned={includeUnzoned} />

      {/* messages over the map */}
      <div className="nw-toasts v2 v2-embedded">
        {grid.status === 'loading' && <Loading what={tr('grid.loading', {}, lang)} />}
        {grid.status === 'error' && <ErrorBox error={grid.error} onRetry={grid.retry} title={tr('grid.error', {}, lang)} />}
        {boundaries.status === 'error' && !boundaries.error.network && <ErrorBox error={boundaries.error} onRetry={boundaries.retry} title="Could not load the outlines" brief />}
      </div>

      {/* the "not in best months" notice: hugs the top edge of the map as a slim banner (V1.1 fix 5), not a card sitting over the middle of the view. It shares the
          nw-toasts class so it inherits all its responsive rules (hidden on a phone once the panel covers the map, pushed behind the panel on a narrow screen -
          the panel shows the same notice itself, moved clear of the panel when there is room) - only its top offset and padding are overridden, right below. */}
      {fewSpecies && <div className="nw-toasts nw-season-banner v2 v2-embedded">{seasonNotice(true)}</div>}

      {/* legend of the colours (on the map) */}
      {legendOpen ? (
        <div className="nw-legend v2 v2-embedded" role="group" aria-label="Map legend" data-tour="m-legend">
          <div className="nw-legend-head">
            <strong>{view === 'full' ? 'Overall score W' : 'Overall match'} · {purposeLabel(purpose)}</strong>
            <AskHelp id="colours" />
            <button type="button" className="btn btn-small" aria-expanded="true" onClick={() => setLegendOpen(false)}>
              Hide legend
            </button>
          </div>
          <div className="nw-legend-sub">{legendSub}</div>
          <ColorLegend />
          {(mode === 'area' ? area : markArea)?.kind === 'polygon' && diag.status === 'ok' && diag.data.squares && (
            <div className="nw-legend-area" data-role="legend-area-squares" data-tour="m-legend-area">
              <span className="nw-legend-sq is-counted" aria-hidden="true" /> {tr('sq.counted', {}, lang)}
              <br />
              <span className="nw-legend-sq is-partial" aria-hidden="true" /> {tr('sq.partial', {}, lang)}
            </div>
          )}
          {noneSuitable && (
            <Callout tone="warning" className="nw-legend-warn">
              {allRemoved ? 'No chosen species can be planted in your dates.' : `No point is suitable for this selection${combine === 'all' && selIds.length > 1 ? ': try “Suits at least one”' : ''}.`}
            </Callout>
          )}
          {fieldForMap && (
            <FieldLegend />
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
          <div className="nw-legend-note">{tr('sq.note', {}, lang)}</div>
        </div>
      ) : (
        <button type="button" className="nw-legend-btn" aria-expanded="false" onClick={() => setLegendOpen(true)} data-tour="m-legend-btn">
          <Icon name="legend" /> Legend
        </button>
      )}
      <button type="button" className={`nw-locate ${locating ? 'is-busy' : ''}`} onClick={locateMe} data-role="locate" data-tour="m-locate" aria-busy={locating} aria-label={locating ? tr('geo.finding', {}, lang) : tr('map.locate', {}, lang)} title={tr('map.locate', {}, lang)}>
        <Icon name="target" size={18} />
        {locating && <span className="nw-locate-text">{tr('geo.finding', {}, lang)}</span>}
      </button>
      {(locFailed || pickingMe) && (
        <button type="button" className={`nw-locate-set ${pickingMe ? 'is-on' : ''}`} onClick={() => setPickingMe((v) => !v)} data-role="locate-set" data-tour="m-locate-set" aria-pressed={pickingMe}>
          <Icon name="pin" size={16} /> {pickingMe ? tr('geo.setHint', {}, lang) : tr('geo.setOnMap', {}, lang)}
        </button>
      )}

      {showZoning && <ZoningLegend api={zoning} onHide={() => setShowZoning(false)} onExpand={() => setLegendOpen(false)} />}

      {showGround && <GroundLegend data={landcover.status === 'ok' ? landcover.data : null} onHide={() => setShowGround(false)} />}

      {planResult && <PlanLegend species={[...planSpecies.values()]} visible={showPlan} nUnconfirmed={nPlanUnconfirmed} blocks={planResult.layout_mode === 'blocks'} />}

      {/* TOP GLASS NAVIGATION BAR (look copied from the earlier dashboard) */}
      <header className="nw-topbar">
        <div className="nw-brandrow">
          <div className="nw-brand" data-tour="h-brand">
            <Icon name="tree" size={18} /> LGU SAN MATEO
          </div>
          <div title="Urban Tree Planting Decision Support System. Municipal Environment and Natural Resources Office (MENRO)">
            <div className="nw-title">Tree Planting Decision Support</div>
            <div className="nw-subtitle">MENRO · San Mateo, Rizal</div>
          </div>
        </div>
        <Tabs tourId="h-tabs" className="nw-tabs-v2" label="Views" value={tab} onChange={setTab} items={TABS.map((x) => ({ id: x.id, label: x.label, icon: <Icon name={x.icon} size={18} /> }))} />
        <div className="nw-topright">
          <SettingsMenu onAbout={() => setLanding(true)} onHelp={() => help.openHelp()} onTour={() => setToursOpen(true)} />
          <div className="nw-pill" role="status" data-tour="h-api">
            <span className={`nw-dot nw-dot-${apiState}`} aria-hidden="true" />
            <span>{apiState === 'ok' ? 'API connected' : apiState === 'wait' ? 'Connecting…' : 'API offline'}</span>
          </div>
        </div>
      </header>
      <AnimatePresence mode="wait">
      {tab !== 'studio' && (
        <motion.section
          key={tab}
          className="nw-page nw-modal"
          data-role="tab-page"
          data-tab={tab}
          aria-label={TABS.find((x) => x.id === tab).label}
          initial={motionAllowed() ? { opacity: 0 } : false}
          animate={{ opacity: 1 }}
          exit={motionAllowed() ? { opacity: 0 } : { opacity: 0 }}
          transition={{ duration: motionAllowed() ? 0.15 : 0, ease: 'easeOut' }}
        >
          <div className="nw-page-in">
            <header className="nw-page-head" data-tour="p-head">
              <h1 ref={pageTitle} tabIndex={-1}>
                {tr(`page.${tab === 'history' ? 'history' : tab === 'weather' ? 'weather' : 'analytics'}.t`, {}, lang)}
              </h1>
              <AskHelp id={tab === 'weather' ? 'weather' : 'logs-analytics'} />
              <p>{tr(`page.${tab === 'history' ? 'history' : tab === 'weather' ? 'weather' : 'analytics'}.d`, {}, lang)}</p>
            </header>
          <Suspense fallback={<p className="nw-pageload" role="status">{tr('page.loading', {}, lang)}</p>}>
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
            <AnalyticsPanel />
          )}
          </Suspense>
          </div>
        </motion.section>
      )}
      </AnimatePresence>

      {/* SIDEBAR (look copied from the earlier dashboard) */}
      {markActive && !sidebarOpen && (
        <div className="nw-markbar" role="group" aria-label={tr('mark.bar.group', {}, lang)} data-role="mark-bar">
          <span data-role="mark-bar-count">{tr('mark.bar.count', { n: draft.length }, lang)}</span>
          <button type="button" className="nw-btn nw-btn-small" disabled={draft.length === 0} onClick={() => setDraft((d) => d.slice(0, -1))}>
            {tr('mark.bar.undo', {}, lang)}
          </button>
          <button type="button" className="nw-btn nw-btn-small" disabled={draft.length === 0} onClick={clearMark}>
            {tr('mark.bar.clear', {}, lang)}
          </button>
          <button type="button" className="nw-btn nw-btn-go nw-btn-small" disabled={draft.length < 3} onClick={finishDraw} data-role="mark-bar-finish">
            {tr('mark.finish', {}, lang)}
          </button>
        </div>
      )}
      <button type="button" className="nw-toggle" data-tour="m-collapse" onClick={() => setSidebarOpen((o) => !o)} aria-expanded={sidebarOpen} aria-controls="nw-sidebar">
        <Icon name={sidebarOpen ? 'left' : 'right'} /> {sidebarOpen ? 'Hide Control Panel' : 'Open Control Panel'}
      </button>
      <aside id="nw-sidebar" className="nw-sidebar" aria-label="Controls" data-tour="s-panel">
        <HintsSwitch />
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
          title={tr('purpose.title', {}, lang)}
          summary={PURPOSE_SHORT[purpose]}
          open={openStep === 'purpose'}
          onToggle={() => toggleStep('purpose')}
          help="Urban greening: shade, lower root-damage risk, low upkeep. Tree planting: conservation and livelihood. Watershed: holding soil on slopes and by waterways."
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
          <PlantingWindow win={win} species={species} />
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
              <SpeciesFlow
                sub={speciesSub}
                setSub={goSub}
                species={species}
                selIds={selIds}
                setSelIds={setSelIds}
                onlySeason={onlySeason}
                onInfo={setCardId}
                purpose={purpose}
                query={sq}
                how={speciesHow}
                setHow={setSpeciesHow}
                mainId={mainSpecies}
                setMain={setMainSpecies}
                combine={combine}
                setCombine={setCombine}
                includeUnzoned={includeUnzoned}
                setIncludeUnzoned={setIncludeUnzoned}
                where={where}
                onWhere={chooseWhere}
                barangays={barangayFeatures}
                zones={zoneFeatures}
                onGoPlan={() => setOpenStep('plan')}
                planAreaLabel={planArea ? (markArea ? tr(markArea.single ? 'flow.areaPoint' : 'flow.areaDrawn', {}, lang) : planAreaLabel) : ''}
                planCreated={!!planResult}
                markCount={draft.length}
                markArea={markArea}
                markSummary={markArea ? [tr('mark.size', { ha: haText(geometryHectares(markArea.geometry), lang) }, lang), areaSplit, diag.status === 'ok' ? sitePhText(diag.data.ph ?? null, 'area', lang) : null].filter(Boolean) : []}
                onFinishMark={finishDraw}
                onUsePoint={usePoint}
                onUndoMark={() => setDraft((d) => d.slice(0, -1))}
                onClearMark={clearMark}
                onShowPoint={() => { setPanelTab('point'); setHidden(false) }}
                onOpenMap={() => setSidebarOpen(false)}
                notice={notice}
                selNames={selNames}
                seasonNotice={fewSpecies ? <div className="nw-season-inline">{seasonNotice(false)}</div> : null}
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
                summary={areaSummary}
                blocked={cont.ok ? '' : cont.reason}
              />
              {notice && (
                <Callout tone="warning">
                  {notice}
                </Callout>
              )}
            </>
          )}
          {mode === 'area' && <UnzonedToggle value={includeUnzoned} onChange={setIncludeUnzoned} />}
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
          {(mode === 'area' || planPrefill) && (
          <button type="button" className="nw-btn nw-btn-go nw-btn-wide" onClick={() => setOpenStep('plan')} disabled={!cont.ok} aria-disabled={!cont.ok} title={cont.ok ? undefined : cont.reason}>
            Continue
          </button>
          )}
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
            areaSplit={areaSplit}
            modeLabel={countsMode ? `Your species (${selIds.length})` : 'Mix chosen automatically'}
            countsMode={countsMode}
            countRows={countRows}
            counts={counts}
            onCount={(id, v) => setCounts((c) => ({ ...c, [id]: v }))}
            areaMode={mode === 'area'}
            ownSpecies={ownSpecies && mode === 'area'}
            onOwnSpecies={() => setOwnSpecies(true)}
            onAutoMix={() => setOwnSpecies(false)}
            picker={chooser(area)}
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
      {fieldMenu && (
        <FieldMenu
          x={fieldMenu.x}
          y={fieldMenu.y}
          pointId={fieldMenu.pointId}
          title={menuInfo.title}
          lines={menuInfo.lines}
          api={menuField}
          observer={observer}
          onObserver={setObserver}
          onSaved={() => {
            bumpField()
            toast('success', tr('toast.fieldSaved', {}, lang))
            setSessionMarks((s) => new Set(s).add(fieldMenu.pointId))
          }}
          block={menuBlock}
          onSeeSpecies={() => {
            const pick = fieldMenu.pick
            setFieldMenu(null)
            onPick(pick)
          }}
          onClose={() => setFieldMenu(null)}
        />
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
                  onOpenFieldMenu={() => spot && pointId && setFieldMenu({ x: null, y: null, pick: { index: -1, context: -1, plan: -1, lat: spot.lat, lon: spot.lon, pointId }, pointId, square: { lat: spot.lat, lon: spot.lon, pointId }, click: { lat: spot.lat, lon: spot.lon } })}
                />
              )}
            </div>
          ) : mode === 'species' ? (
            <AreasPanel
              focus={speciesSub >= 3 ? where : null}
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
      {help.helpPage && (
        <HelpPage
          initialFaq={help.helpPage.faq}
          usingRules={usingRules}
          screen={tab}
          onClose={help.closeHelp}
          onTour={startPageTour}
          onQuickTour={() => {
            help.closeHelp()
            setToursOpen(true)
          }}
        />
      )}
      {toursOpen && <ToursMenu page={tab} onStart={runTour} onClose={() => setToursOpen(false)} hasPlan={hasPlan} />}
      {cardId !== null && (
        <SpeciesCard
          speciesId={cardId}
          window={win.applied}
          view={view}
          pointId={pointId}
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
      <ToastViewport />
      {!firstVisit && <Splash ready={apiState !== 'wait'} />}
      {landing && <Landing onClose={closeLanding} />}
    </div>
    </HelpContext.Provider>
  )
}
