import { shapeColor, shapePath } from './planShapes.js'

// The legend of the planned trees on the map: shape, 3-letter code, common name and count (shape + code, never colour alone).
export default function PlanLegend({ species, visible, nUnconfirmed = 0 }) {
  return (
    <div className="nw-plan-legend" role="group" aria-label="Planned trees legend">
      <strong>Planned trees{visible ? '' : ' (hidden)'}</strong>
      <ul>
        {species.map((s) => (
          <li key={s.species_id}>
            <svg viewBox="-1.5 -1.5 3 3" width="18" height="18" aria-hidden="true">
              <path d={shapePath(s.kind)} fill={shapeColor(s.kind)} stroke="#0f172a" strokeWidth="0.22" />
            </svg>
            <span className="nw-plan-code">{s.code}</span> {s.common_name} <span className="nw-plan-count">× {s.count}</span>
          </li>
        ))}
      </ul>
      {nUnconfirmed > 0 && (
        <div className="nw-plan-legend-unz">
          <svg viewBox="-2 -2 4 4" width="20" height="20" aria-hidden="true">
            <circle r="1.4" fill="none" stroke="#0f172a" strokeWidth="0.5" strokeDasharray="0.45 0.55" />
          </svg>{' '}
          Dotted ring = land outside the zoning map (not confirmed) <span className="nw-plan-count">× {nUnconfirmed}</span>
        </div>
      )}
    </div>
  )
}
