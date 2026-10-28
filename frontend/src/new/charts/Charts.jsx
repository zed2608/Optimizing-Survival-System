import { useId, useState } from 'react'
import { motion } from 'motion/react'
import { motionAllowed } from '../motionPref.js'
import { downloadCsv, toCsv } from './csv.js'
import { PALETTE } from './palette.js'
import { tr, useLang } from '../i18n.js'
import Icon from '../Icon.jsx'

// Hand-rolled SVG charts for System Analytics (no library). Colour-blind-safe palette (Okabe-Ito blue, orange, bluish green); every chart has a title, labelled axes, a text summary for screen readers,
// a "View as table" and a client-side CSV download. No 3D, nothing decorative that hides a number.
const fmtN = (v) => (typeof v === 'number' ? v.toLocaleString('en-US') : String(v))

// The frame of one chart: a one-line summary row, closed by default (panel round: "keep Analytics to one screen, not endlessly
// scrollable; click an item to reveal its details"); clicking the row opens the chart, its note, the "View as table" toggle and
// the CSV button underneath. All ten cards closed add up to one short, scannable list instead of ten full-size charts stacked
// and scrolling past the fold; opening one never moves the others.
export function ChartCard({ title, note, children, rows, columns, filename, summary, tourId, defaultOpen = false }) {
  const lang = useLang()
  const [open, setOpen] = useState(defaultOpen)
  const [table, setTable] = useState(false)
  const id = useId()
  return (
    <motion.section
      className="cy-card an-chart"
      aria-label={title}
      data-tour={tourId}
      data-open={open}
      initial={motionAllowed() ? { opacity: 0, y: 26 } : false}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -40px 0px' }}
      transition={motionAllowed() ? { duration: 0.5, ease: [0.2, 0.7, 0.2, 1] } : { duration: 0 }}
    >
      <button type="button" className="an-chart-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
        <span className="an-chart-toggle-text">
          <h3>{title}</h3>
          {!open && summary && <span className="an-chart-summary muted">{summary}</span>}
        </span>
        <Icon name={open ? 'up' : 'down'} size={16} />
      </button>
      {open && (
        <div className="an-chart-body" id={id}>
          <div className="an-chart-tools">
            <button type="button" className="cy-btn cy-btn-quiet" data-tour={tourId ? `${tourId}-table` : undefined} aria-expanded={table} onClick={() => setTable((v) => !v)}>
              {tr(table ? 'an.hideTable' : 'an.viewTable', {}, lang)}
            </button>
            <button type="button" className="cy-btn" disabled={!rows?.length} onClick={() => downloadCsv(filename, toCsv(rows, columns))} data-role="csv" data-tour={tourId ? `${tourId}-csv` : undefined}>
              {tr('an.csv', {}, lang)}
            </button>
          </div>
          {note && <p className="muted an-note">{note}</p>}
          <div role="img" aria-label={summary ?? title}>
            {children}
          </div>
          {table && (
            <div className="an-table-wrap">
              <table className="an-table">
                <thead>
                  <tr>
                    {columns.map((c) => (
                      <th key={c.label} scope="col">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      {columns.map((c) => (
                        <td key={c.label}>{fmtN(typeof c.get === 'function' ? c.get(r) : r[c.key])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </motion.section>
  )
}

// Vertical bars (a histogram or a short series). data = [{label, value}]; xLabel / yLabel name the axes.
export function VBars({ data, xLabel, yLabel, color = PALETTE.blue, height = 190 }) {
  const W = 420
  const pad = { l: 58, r: 8, t: 10, b: 46 }
  const max = Math.max(1, ...data.map((d) => d.value))
  const bw = (W - pad.l - pad.r) / Math.max(1, data.length)
  const y = (v) => pad.t + (height - pad.t - pad.b) * (1 - v / max)
  return (
    <svg viewBox={`0 0 ${W} ${height}`} className="an-svg an-vert" preserveAspectRatio="xMidYMid meet">
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={pad.l} x2={W - pad.r} y1={y(max * f)} y2={y(max * f)} className="an-grid" />
          <text x={pad.l - 6} y={y(max * f) + 4} textAnchor="end" className="an-tick">
            {fmtN(Math.round(max * f))}
          </text>
        </g>
      ))}
      {data.map((d, i) => (
        <g key={d.label}>
          <rect x={pad.l + i * bw + 2} y={y(d.value)} width={Math.max(1, bw - 4)} height={Math.max(0, height - pad.b - y(d.value))} fill={color} rx="2">
            <title>{`${d.label}: ${fmtN(d.value)}`}</title>
          </rect>
          <text x={pad.l + i * bw + bw / 2} y={height - pad.b + 14} textAnchor="middle" className="an-tick">
            {d.label}
          </text>
        </g>
      ))}
      <text x={(W + pad.l) / 2} y={height - 6} textAnchor="middle" className="an-axis">
        {xLabel}
      </text>
      <text transform={`translate(11 ${(height - pad.b) / 2}) rotate(-90)`} textAnchor="middle" className="an-axis">
        {yLabel}
      </text>
    </svg>
  )
}

// Horizontal bars, one or two values per row (for example planned and planted). rows = [{label, a, b?}]; series = [{label, color}].
export function HBars({ rows, series, xLabel, limit = 12 }) {
  const lang = useLang()
  const [all, setAll] = useState(false)
  const shown = all ? rows : rows.slice(0, limit)
  const max = Math.max(1, ...shown.map((r) => Math.max(r.a ?? 0, r.b ?? 0)))
  const rowH = series.length === 2 ? 30 : 20
  const W = 420
  const labW = 128
  const H = shown.length * rowH + 40
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="an-svg" preserveAspectRatio="xMidYMid meet">
        {shown.map((r, i) => {
          const y0 = 4 + i * rowH
          return (
            <g key={r.label}>
              <text x={labW - 6} y={y0 + 13} textAnchor="end" className="an-tick">
                {r.label.length > 20 ? `${r.label.slice(0, 19)}…` : r.label}
              </text>
              <rect x={labW} y={y0 + 2} width={Math.max(0, ((W - labW - 44) * (r.a ?? 0)) / max)} height="12" fill={series[0].color} rx="2">
                <title>{`${r.label} · ${series[0].label}: ${fmtN(r.a ?? 0)}`}</title>
              </rect>
              <text x={labW + ((W - labW - 44) * (r.a ?? 0)) / max + 4} y={y0 + 12} className="an-val">
                {fmtN(r.a ?? 0)}
              </text>
              {series.length === 2 && (
                <>
                  <rect x={labW} y={y0 + 16} width={Math.max(0, ((W - labW - 44) * (r.b ?? 0)) / max)} height="10" fill={series[1].color} rx="2">
                    <title>{`${r.label} · ${series[1].label}: ${fmtN(r.b ?? 0)}`}</title>
                  </rect>
                  <text x={labW + ((W - labW - 44) * (r.b ?? 0)) / max + 4} y={y0 + 25} className="an-val">
                    {fmtN(r.b ?? 0)}
                  </text>
                </>
              )}
            </g>
          )
        })}
        <text x={(W + labW) / 2} y={H - 6} textAnchor="middle" className="an-axis">
          {xLabel}
        </text>
      </svg>
      {series.length === 2 && <Legend series={series} />}
      {rows.length > limit && (
        <button type="button" className="cy-btn cy-btn-quiet" onClick={() => setAll((v) => !v)}>
          {tr(all ? 'an.showFewer' : 'an.showAll', { n: rows.length }, lang)}
        </button>
      )}
    </div>
  )
}

// Grouped vertical bars for a time series (for example plans and field checks by week). data = [{label, ...keys}], series = [{key, label, color}].
export function GroupBars({ data, series, xLabel, yLabel, height = 200 }) {
  const W = 420
  const pad = { l: 58, r: 8, t: 10, b: 50 }
  const max = Math.max(1, ...data.flatMap((d) => series.map((s) => d[s.key] ?? 0)))
  const gw = (W - pad.l - pad.r) / Math.max(1, data.length)
  const bw = Math.max(2, (gw - 6) / series.length)
  const y = (v) => pad.t + (height - pad.t - pad.b) * (1 - v / max)
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${height}`} className="an-svg an-vert" preserveAspectRatio="xMidYMid meet">
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={pad.l} x2={W - pad.r} y1={y(max * f)} y2={y(max * f)} className="an-grid" />
            <text x={pad.l - 6} y={y(max * f) + 4} textAnchor="end" className="an-tick">
              {fmtN(Math.round(max * f))}
            </text>
          </g>
        ))}
        {data.map((d, i) => (
          <g key={d.label}>
            {series.map((s, k) => (
              <rect key={s.key} x={pad.l + i * gw + 3 + k * bw} y={y(d[s.key] ?? 0)} width={bw - 1} height={Math.max(0, height - pad.b - y(d[s.key] ?? 0))} fill={s.color} rx="2">
                <title>{`${d.label} · ${s.label}: ${fmtN(d[s.key] ?? 0)}`}</title>
              </rect>
            ))}
            <text x={pad.l + i * gw + gw / 2} y={height - pad.b + 14} textAnchor="middle" className="an-tick" transform={`rotate(35 ${pad.l + i * gw + gw / 2} ${height - pad.b + 14})`}>
              {d.label}
            </text>
          </g>
        ))}
        <text x={(W + pad.l) / 2} y={height - 4} textAnchor="middle" className="an-axis">
          {xLabel}
        </text>
        <text transform={`translate(11 ${(height - pad.b) / 2}) rotate(-90)`} textAnchor="middle" className="an-axis">
          {yLabel}
        </text>
      </svg>
      <Legend series={series} />
    </div>
  )
}

export function Legend({ series }) {
  return (
    <ul className="an-legend">
      {series.map((s) => (
        <li key={s.label}>
          <span className="an-swatch" style={{ background: s.color }} aria-hidden="true" /> {s.label}
        </li>
      ))}
    </ul>
  )
}
