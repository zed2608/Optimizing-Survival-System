import { shapeColor } from './planShapes.js'
import { blockGeometry, fmtM, SQUARE_M as S } from './blockGeometry.js'

const PAD = 16

// The layout of one planting block, drawn to scale with the same geometry as the field kit: the 100 m grid square, the planted rectangle centred in it (dashed),
// the numbered trees at the centres of its cells (filled; the empty places of a partly filled block are hollow), START beside the south-west corner, the spacing, the margin
// and a north arrow. The words under it say the same as the printed page of the kit.
export default function BlockLayout({ item, kind = 0 }) {
  const { trees_planned: n, spacing_m: sp, rows, trees_per_row: tpr, capacity } = item
  const g = blockGeometry(sp, tpr, rows, n)
  const r = Math.max(0.9, Math.min(3, sp * 0.22))
  const x = (m) => PAD + m
  const y = (m) => PAD + S - m // y grows downward, north is up
  const fill = shapeColor(kind)
  const label = (t) => capacity <= 100 || t.k === 1 || (t.k - 1) % tpr === 0 || t.k === n
  const fs = Math.max(1.4, Math.min(3.2, sp * 0.28))
  const usedRows = Math.ceil(n / tpr)
  return (
    <figure className="nw-blocklayout">
      <svg viewBox={`0 0 ${S + PAD * 2} ${S + PAD * 2 + 12}`} role="img" aria-label={`Block layout: ${n} trees numbered 1 to ${n}, ${tpr} trees per row, ${sp} metres apart, planted area ${fmtM(g.rectSide)} metres square in the middle of the 100 metre square, start at the south-west corner, rows run east.`}>
        <rect x={PAD} y={PAD} width={S} height={S} className="nw-bl-square" />
        <rect x={x(g.margin)} y={y(g.margin + g.rectH)} width={g.rectW} height={g.rectH} className="nw-bl-usable" />
        {g.trees.map((t) => (
          <g key={t.k}>
            <circle cx={x(t.x)} cy={y(t.y)} r={r} className={t.planted ? 'nw-bl-tree' : 'nw-bl-empty'} style={t.planted ? { fill } : undefined} />
            {label(t) && <text x={x(t.x)} y={y(t.y) + fs * 0.35} className={t.planted ? 'nw-bl-num' : 'nw-bl-num nw-bl-num-empty'} style={{ fontSize: `${fs}px` }} textAnchor="middle">{t.k}</text>}
          </g>
        ))}
        <rect x={x(g.margin) - 2.4} y={y(g.margin) - 2.4} width="4.8" height="4.8" className="nw-bl-start" />
        <text x={x(g.margin) - 4} y={y(g.margin) + 7} className="nw-bl-text nw-bl-strong" textAnchor="end">START</text>
        <line x1={x(g.margin)} y1={y(g.margin) + 3.8} x2={x(g.margin) + Math.min(g.rectW, 3 * sp)} y2={y(g.margin) + 3.8} className="nw-bl-dim" />
        <text x={x(g.margin) + Math.min(g.rectW, 3 * sp) + 2} y={y(g.margin) + 5.4} className="nw-bl-text">rows run east</text>
        <line x1={x(0)} y1={y(S / 2)} x2={x(g.margin)} y2={y(S / 2)} className="nw-bl-dim" />
        <text x={x(g.margin / 2)} y={y(S / 2) - 1.5} className="nw-bl-text" textAnchor="middle">{fmtM(g.margin)} m</text>
        {tpr > 1 && (
          <g>
            <line x1={x(g.trees[0].x)} y1={y(g.margin + g.rectH) - 3} x2={x(g.trees[1].x)} y2={y(g.margin + g.rectH) - 3} className="nw-bl-dim" />
            <text x={x((g.trees[0].x + g.trees[1].x) / 2)} y={y(g.margin + g.rectH) - 4.5} className="nw-bl-text" textAnchor="middle">{fmtM(sp)} m</text>
          </g>
        )}
        <text x={PAD + S / 2} y={PAD - 4} className="nw-bl-text" textAnchor="middle">Planted area {fmtM(g.rectSide)} m x {fmtM(g.rectSide)} m in the middle of the square</text>
        <g transform={`translate(${PAD + S - 4} ${PAD + 12})`}>
          <path d="M0 8V-8M-4 -3 0 -9 4 -3" className="nw-bl-north" />
          <text x="0" y="17" className="nw-bl-text" textAnchor="middle">N</text>
        </g>
      </svg>
      <figcaption>
        <strong>{n}</strong> trees · {fmtM(sp)} m apart · {usedRows < rows ? `${usedRows} of ${rows} rows used` : `${rows} rows`} of {tpr} trees · planted area {fmtM(g.rectSide)} m x {fmtM(g.rectSide)} m in the middle of the square, {fmtM(g.margin)} m from each edge · tree 1 is {fmtM(g.margin + sp / 2)} m from the south and west edges
        {n < capacity ? ` · plant trees 1 to ${n}; leave the rest empty` : ''}
        {item.layout_note ? ` · ${item.layout_note}` : ''}
      </figcaption>
    </figure>
  )
}
