import { shapeColor } from './planShapes.js'

const S = 100 // the grid square is 100 m: one unit of the drawing is one metre
const PAD = 14

// The layout of one planting block, drawn to scale: the 100 m grid square, the planted part (dashed), the rows from the south-west corner, every planned tree
// (filled; unplanned places of a partly filled block are hollow), the start corner, the spacing and a north arrow. A plain-words summary is printed under it.
export default function BlockLayout({ item, kind = 0 }) {
  const { trees_planned: n, spacing_m: sp, rows, trees_per_row: tpr, usable_side_m: us, capacity } = item
  const off = (S - us) / 2
  const r = Math.max(0.7, Math.min(2.6, sp * 0.2))
  const usedRows = Math.ceil(n / tpr)
  const x0 = PAD + off
  const y0 = PAD + S - off // the south-west planting corner (y grows downward, north is up)
  const trees = []
  for (let k = 0; k < capacity; k++) {
    trees.push({ x: x0 + (k % tpr) * sp, y: y0 - Math.floor(k / tpr) * sp, on: k < n })
  }
  const fill = shapeColor(kind)
  return (
    <figure className="nw-blocklayout">
      <svg viewBox={`0 0 ${S + PAD * 2} ${S + PAD * 2 + 10}`} role="img" aria-label={`Block layout: ${n} trees, ${usedRows} of ${rows} rows used, ${tpr} trees per row, ${sp} metres apart, start at the south-west corner, rows run east to west.`}>
        <rect x={PAD} y={PAD} width={S} height={S} className="nw-bl-square" />
        <rect x={PAD + off} y={PAD + off} width={us} height={us} className="nw-bl-usable" />
        {trees.map((t, i) => (
          <circle key={i} cx={t.x} cy={t.y} r={r} className={t.on ? 'nw-bl-tree' : 'nw-bl-empty'} style={t.on ? { fill } : undefined} />
        ))}
        <rect x={x0 - 2.6} y={y0 - 2.6} width="5.2" height="5.2" className="nw-bl-start" />
        <text x={x0 + 4} y={y0 + 11} className="nw-bl-text">start (south-west)</text>
        {tpr > 1 && (
          <g>
            <line x1={x0} y1={y0 - 6} x2={x0 + sp} y2={y0 - 6} className="nw-bl-dim" />
            <text x={x0 + sp / 2} y={y0 - 8} className="nw-bl-text" textAnchor="middle">{sp} m</text>
          </g>
        )}
        <text x={PAD + S / 2} y={PAD - 3} className="nw-bl-text" textAnchor="middle">{Math.round(us)} m planted part of the 100 m square</text>
        <g transform={`translate(${PAD + S - 4} ${PAD + 12})`}>
          <path d="M0 8V-8M-4 -3 0 -9 4 -3" className="nw-bl-north" />
          <text x="0" y="17" className="nw-bl-text" textAnchor="middle">N</text>
        </g>
      </svg>
      <figcaption>
        <strong>{n}</strong> trees · {sp} m apart · {usedRows < rows ? `${usedRows} of ${rows} rows used` : `${rows} rows`} of {tpr} trees · rows run {item.row_direction}, counted from the {item.start_corner} corner
        {item.layout_note ? ` · ${item.layout_note}` : ''}
      </figcaption>
    </figure>
  )
}
