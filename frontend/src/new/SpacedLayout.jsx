import { shapeColor } from './planShapes.js'
import { fmtM } from './blockGeometry.js'

const PAD = 16
const S = 100

// The layout of one planting block of SPACED points (design v2), drawn to scale like the printed page of the kit: the 100 m grid square, the plantable ground (dashed), the walking route
// (a thin line from START through the trees in number order), the numbered trees and START. The numbers come from the service (the same call as the kit), nothing is computed here.
export default function SpacedLayout({ item, kind = 0 }) {
  const pts = item.points_m || []
  const n = pts.length
  const x = (m) => PAD + m
  const y = (m) => PAD + S - m // y grows downward, north is up
  const fill = shapeColor(kind)
  const d = item.min_distance_m || 5
  const r = Math.max(0.9, Math.min(3, d * 0.22))
  const fs = Math.max(1.4, Math.min(3.2, d * 0.28))
  const label = (k) => n <= 120 || k === 1 || k % 10 === 0 || k === n
  const start = item.start_m || (pts[0] ?? [0, 0])
  const route = [start, ...pts].map((p) => `${x(p[0])},${y(p[1])}`).join(' ')
  return (
    <figure className="nw-blocklayout" data-role="spaced-layout">
      <svg viewBox={`0 0 ${S + PAD * 2} ${S + PAD * 2 + 12}`} role="img" aria-label={`Block layout: ${n} trees numbered 1 to ${n} along a walking route, at least ${fmtM(d)} metres apart`}>
        <rect x={PAD} y={PAD} width={S} height={S} className="nw-bl-square" />
        {(item.region_m || []).map((ring, i) => (
          <polygon key={i} points={ring.map((p) => `${x(p[0])},${y(p[1])}`).join(' ')} className="nw-bl-usable" />
        ))}
        {n > 0 && <polyline points={route} className="nw-bl-dim" fill="none" />}
        {pts.map((p, i) => (
          <g key={i}>
            <circle cx={x(p[0])} cy={y(p[1])} r={r} className="nw-bl-tree" style={{ fill }} />
            {label(i + 1) && <text x={x(p[0])} y={y(p[1]) + fs * 0.35} className="nw-bl-num" style={{ fontSize: `${fs}px` }} textAnchor="middle">{i + 1}</text>}
          </g>
        ))}
        <rect x={x(start[0]) - 2.4} y={y(start[1]) - 2.4} width="4.8" height="4.8" className="nw-bl-start" />
        <text x={x(start[0]) - 4} y={y(start[1]) + 7} className="nw-bl-text nw-bl-strong" textAnchor="end">START</text>
        <g transform={`translate(${PAD + S - 4} ${PAD + 12})`}>
          <path d="M0 8V-8M-4 -3 0 -9 4 -3" className="nw-bl-north" />
          <text x="0" y="17" className="nw-bl-text" textAnchor="middle">N</text>
        </g>
      </svg>
      <figcaption>
        <strong>{n}</strong> trees · at least {fmtM(d)} m apart · numbered along a walking route from START
        {item.fits === false ? ` · ${item.fit_note}` : ''}
        {item.layout_note ? ` · ${item.layout_note}` : ''}
      </figcaption>
    </figure>
  )
}
