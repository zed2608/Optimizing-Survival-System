import FlagList from './FlagList.jsx'
import HelpTip from './HelpTip.jsx'
import AskHelp from './tutorial/AskHelp.jsx'
import Icon from './Icon.jsx'
import ProvisionalTag from './ProvisionalTag.jsx'
import { conditionText, needsPermission } from './zoneColors.js'
import { tr, useLang } from './i18n.js'

// The header of the point panel (and of the grey-square panel). Simple: the barangay name only (UX revamp, Phase 0 A). Detailed: the same name and a collapsed "Land details" section with the land constraints
// (zone condition, "Needs permission", zoning, soil, ground cover, coordinates) and the soil pH line. The zone name, grid number, planting window, view date and distance are in the right-click menu (pointMenu.js).
export default function LocationCard({ full = true, zoneCondition = '', barangay, zone, lat, lon, elev, slope, searched, zoning = null, ground = null, soil = null, phLine = null, children }) {
  const lang = useLang()
  const coords = [`${Number(lat).toFixed(5)}, ${Number(lon).toFixed(5)}`]
  if (elev !== null && elev !== undefined) coords.push(`${elev} m elevation`)
  if (slope !== null && slope !== undefined) coords.push(`slope ${Number(slope).toFixed(0)} %`)
  const hasNotes = !!zoneCondition || zoning === 'unconfirmed' || (ground?.available && (ground.flags?.length > 0 || ground.info))
  return (
    <section className="nw-pcard nw-loc" aria-label="Where this is" data-tour="r-header">
      {searched && <div className="nw-loc-searched">Searched: {searched}</div>}
      <h2 className="nw-loc-title">{barangay || 'Outside the barangay outlines'}</h2>
      {!full && hasNotes && (
        <p className="nw-loc-line muted" data-role="land-hint">
          <Icon name="info" size={14} /> {tr('land.hint', {}, lang)}
        </p>
      )}
      {full && (
        <details className="nw-landdetails" data-role="land-details" data-tour="r-land">
          <summary data-tour="r-land-summary">{tr('land.title', {}, lang)}</summary>
          {zoneCondition && (
            <div className="nw-loc-line nw-zonecond" role="note">
              <Icon name="info" size={14} /> Zone condition: {conditionText(zoneCondition)}. <ProvisionalTag /> <AskHelp id="needs-permission" />
              {needsPermission(zoneCondition) && <span className="nw-chip nw-chip-permit">Needs permission</span>}
            </div>
          )}
          <div className="nw-loc-line">{coords.join(' · ')}</div>
          {zoning === 'confirmed' && <div className="nw-loc-line nw-zoning"><Icon name="check" size={14} /> Zoning: confirmed ({zone})</div>}
          {zoning === 'unconfirmed' && (
            <div className="nw-loc-line nw-zoning is-unconfirmed" role="note">
              <Icon name="dotring" size={14} /> {zone ? `Zoning: ${zone} (not confirmed)` : 'Zoning: outside our zoning map (CLUP: Forest Reserve, Watershed)'}
              <div className="nw-zoning-warn">
                {zone ? `${zone}: confirm with the LGU before planting.` : 'Land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting.'}
              </div>
            </div>
          )}
          {soil && (
            <div className="nw-opt-head nw-soilline">
              <span className="nw-loc-line nw-grow">
                <Icon name="layers" size={14} /> {soil.series ? `Soil: ${soil.series} (${String(soil.texture ?? '').toLowerCase()}), LGU soil map, provisional` : 'Soil: Data Unavailable (outside the LGU soil map)'}
              </span>
              <HelpTip label="Soil">
                {soil.note}
                {soil.series && soil.purity != null ? ` About ${Math.round(soil.purity * 100)}% of the map pixels of this square show this series.` : ''}
              </HelpTip>
            </div>
          )}
          {phLine}
          {ground && (
            <div className="nw-ground">
              <div className="nw-opt-head">
                <span className="nw-loc-line nw-grow">
                  <Icon name="tree" size={14} /> {ground.available ? ground.line : 'Ground cover (satellite 2021): Data Unavailable'}
                </span>
                <HelpTip label="Ground cover">{ground.accuracy_note}</HelpTip>
              </div>
              {ground.available && <FlagList flags={ground.flags} />}
              {ground.available && ground.info && <div className="muted nw-ground-info">{ground.info}.</div>}
            </div>
          )}
        </details>
      )}
      {children}
    </section>
  )
}
