import { formatDay } from './season.js'
import Icon from './Icon.jsx'

// The header of the point panel (and of the grey-square panel): where exactly this is, one short line each.
//   barangay (large) / "Forest Zone, grid 11809" / coordinates, elevation, slope / the planting window and today's date / how far from the click.
export default function LocationCard({ barangay, zone, pointId, lat, lon, elev, slope, win, today, distance, searched, zoning = null, children }) {
  const coords = [`${Number(lat).toFixed(5)}, ${Number(lon).toFixed(5)}`]
  if (elev !== null && elev !== undefined) coords.push(`${elev} m elevation`)
  if (slope !== null && slope !== undefined) coords.push(`slope ${Number(slope).toFixed(0)} %`)
  const away = Math.round(distance ?? 0)
  return (
    <section className="nw-pcard nw-loc" aria-label="Where this is">
      {searched && <div className="nw-loc-searched">Searched: {searched}</div>}
      <h2 className="nw-loc-title">{barangay || 'Outside the barangay outlines'}</h2>
      <div className="nw-loc-line">
        {zone || 'Outside the zoning map'}, grid {pointId}
      </div>
      <div className="nw-loc-line">{coords.join(' · ')}</div>
      <div className="nw-loc-line">
        Planting window {formatDay(win.start)} - {formatDay(win.end, true)}, viewed {formatDay(today, true)}
      </div>
      {away >= 1 && <div className="nw-loc-line">{away} m from where you clicked</div>}
      {zoning === 'confirmed' && <div className="nw-loc-line nw-zoning"><Icon name="check" size={14} /> Zoning: confirmed ({zone})</div>}
      {zoning === 'unconfirmed' && (
        <div className="nw-loc-line nw-zoning is-unconfirmed" role="note">
          <Icon name="dotring" size={14} /> {zone ? `Zoning: ${zone} (not confirmed)` : 'Zoning: not on the zoning map (not confirmed)'}
          <div className="nw-zoning-warn">{zone ? `${zone}: confirm with the LGU before planting.` : 'Land outside the zoning map: confirm with the LGU before planting.'}</div>
        </div>
      )}
      {children}
    </section>
  )
}
