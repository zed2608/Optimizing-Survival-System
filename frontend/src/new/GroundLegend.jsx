import Icon from './Icon.jsx'
import { GROUND_GROUPS, GROUND_STYLE, PATTERN_SHAPES } from './groundStyle.js'

function Swatch({ group }) {
  const st = GROUND_STYLE[group]
  const id = `nw-gpat-${group}`
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" className="nw-gswatch">
      <defs>
        <pattern id={id} width="8" height="8" patternUnits="userSpaceOnUse">
          <rect width="8" height="8" fill={st.color} />
          {PATTERN_SHAPES[st.pattern].map(([k, ...a], i) =>
            k === 'c' ? <circle key={i} cx={a[0]} cy={a[1]} r={a[2]} fill={st.ink} /> : <line key={i} x1={a[0]} y1={a[1]} x2={a[2]} y2={a[3]} stroke={st.ink} strokeWidth="1" />,
          )}
        </pattern>
      </defs>
      <rect x="1" y="1" width="20" height="20" rx="3" fill={`url(#${id})`} stroke="rgba(15,23,42,0.6)" strokeWidth="1" />
    </svg>
  )
}

// The legend of the ground-cover layer: colour AND pattern AND icon AND words for each group, the corner marker, the attribution and the accuracy.
export default function GroundLegend({ data, onHide }) {
  return (
    <div className="nw-ground-legend v2 v2-embedded" role="group" aria-label="Ground cover legend">
      <div className="nw-legend-head">
        <strong>Ground cover (satellite 2021)</strong>
        <button type="button" className="btn btn-small" onClick={onHide}>
          Hide layer
        </button>
      </div>
      <ul className="nw-glist">
        {GROUND_GROUPS.filter((g) => g !== 'other').map((g) => (
          <li key={g}>
            <Swatch group={g} /> <Icon name={GROUND_STYLE[g].icon} size={14} /> {GROUND_STYLE[g].label}
          </li>
        ))}
      </ul>
      <div className="nw-gcorner">
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <rect x="1" y="1" width="16" height="16" fill="none" stroke="rgba(15,23,42,0.5)" />
          <path d="M9 1h8v8z" fill="#f59e0b" stroke="#0f172a" strokeWidth="1" />
        </svg>{' '}
        Corner mark = flagged as bare, built-up or water (Detailed view)
      </div>
      <div className="nw-legend-note">
        Dominant class of each 100 m square. Satellite land cover, about {data?.accuracy?.match(/\d+\.\d%/)?.[0] ?? '77%'} accurate worldwide: check on the ground.
      </div>
      <div className="nw-legend-note">{data?.attribution ?? '(c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium'}</div>
    </div>
  )
}
