import { useMemo, useState } from 'react'
import Callout from './ui/Callout.jsx'
import { useApi } from '../v2/useApi.js'
import { ChartCard, GroupBars, HBars, VBars } from './charts/Charts.jsx'
import { PALETTE } from './charts/palette.js'
import CountUp from './ui/CountUp.jsx'
import { EmptyState, Skeleton } from './ui/ui.jsx'
import { tr, useLang } from './i18n.js'

const nf = (v) => (typeof v === 'number' ? v.toLocaleString('en-US') : '—')

function Kpi({ label, value, sub }) {
  return (
    <div className="an-kpi">
      <div className="an-kpi-n">{typeof value === 'number' ? <CountUp value={value} /> : value}</div>
      <div className="an-kpi-l">{label}</div>
      {sub && <div className="an-kpi-s">{sub}</div>}
    </div>
  )
}

// The "System Analytics" tab as a statistical tool (UX revamp, Phase 6): KPI tiles, suitability, soil pH, zones and missing data, activity by week, planned versus planted. Everything is counted from data that
// already exists (GET /analytics/summary); each chart has labelled axes, a table and a CSV download; no forecast is shown because there are no survival records.
export default function AnalyticsPanel() {
  const lang = useLang()
  const t = (k, p) => tr(k, p, lang)
  const [f, setF] = useState({ barangay: '', species: '', from: '', to: '' })
  const qs = useMemo(() => {
    const q = new URLSearchParams()
    if (f.barangay) q.set('barangay', f.barangay)
    if (f.species) q.set('species_id', f.species)
    if (f.from) q.set('from', f.from)
    if (f.to) q.set('to', f.to)
    return q.toString()
  }, [f])
  const api = useApi(`/analytics/summary${qs ? `?${qs}` : ''}`)
  const sp = useApi('/species')
  const species = sp.status === 'ok' ? sp.data.species : []
  const set = (k) => (e) => setF((o) => ({ ...o, [k]: e.target.value }))
  const dateBad = f.from && f.to && f.to < f.from

  const filters = (
    <section className="cy-card an-filters" aria-label={t('an.filters')}>
      <label>
        <span className="nw-label">{t('an.barangay')}</span>
        <select className="nw-select" value={f.barangay} onChange={set('barangay')} data-role="an-barangay">
          <option value="">{t('an.allBarangays')}</option>
          {(api.status === 'ok' ? api.data.suitability.per_barangay : []).map((b) => (
            <option key={b.barangay} value={b.barangay}>
              {b.display_name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="nw-label">{t('an.species')}</span>
        <select className="nw-select" value={f.species} onChange={set('species')} data-role="an-species">
          <option value="">{t('an.allSpecies')}</option>
          {species.map((s) => (
            <option key={s.species_id} value={s.species_id}>
              {s.common_name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="nw-label">{t('an.from')}</span>
        <input className="nw-input" type="date" value={f.from} onChange={set('from')} data-role="an-from" />
      </label>
      <label>
        <span className="nw-label">{t('an.to')}</span>
        <input className="nw-input" type="date" value={f.to} onChange={set('to')} data-role="an-to" />
      </label>
      <button type="button" className="cy-btn" onClick={() => setF({ barangay: '', species: '', from: '', to: '' })} disabled={!qs}>
        {t('an.reset')}
      </button>
      {dateBad && (
        <Callout tone="error" role="alert">
          {t('an.dateBad')}
        </Callout>
      )}
    </section>
  )

  if (api.status === 'loading' || api.status === 'idle') {
    return (
      <div className="an-root">
        {filters}
        <div className="an-kpis" aria-busy="true" aria-label={t('an.loading')}>
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="an-kpi">
              <Skeleton height={28} width="50%" />
              <Skeleton height={12} width="80%" style={{ marginTop: 8 }} />
            </div>
          ))}
        </div>
        <div className="an-grid">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} height={220} />
          ))}
        </div>
      </div>
    )
  }
  if (api.status === 'error') {
    return (
      <div className="an-root">
        {filters}
        <EmptyState
          tone="error"
          icon="warn"
          title={api.error?.network ? t('state.down.title') : t('an.error.title')}
          text={api.error?.network ? t('state.down.text') : api.error?.message}
          action={
            <button type="button" className="cy-btn cy-btn-primary" onClick={api.retry}>
              {t('state.retry')}
            </button>
          }
        />
      </div>
    )
  }
  const d = api.data
  const k = d.kpi
  const S = d.suitability.histogram
  const sRows = S.bins.map((b) => ({ label: b.lo.toFixed(1), value: b.count, range: `${b.lo.toFixed(1)}–${b.hi.toFixed(1)}` }))
  const brgy = d.suitability.per_barangay.filter((b) => b.squares > 0).sort((a, b) => b.suitable_squares - a.suitable_squares).map((b) => ({ label: b.display_name, a: b.suitable_squares, total: b.squares }))
  const spRows = d.suitability.per_species.map((s) => ({ label: s.name, a: s.suitable_squares }))
  const phRows = d.ph.histogram.bins.map((b) => ({ label: b.lo.toFixed(1), value: b.count, range: `${b.lo.toFixed(1)}–${b.hi.toFixed(1)}` }))
  const vOrder = ['inside', 'uncertain', 'outside', 'no_value']
  const vRows = vOrder.map((c) => ({ code: c, label: t(`an.v.${c}`), a: d.ph.verdicts[c] ?? 0 }))
  const zRows = d.land.zones.map((z) => ({ label: z.zone, a: z.squares }))
  const weeks = d.activity.by_week.map((w) => ({ ...w, label: w.week.slice(5) }))
  const pvB = d.planned_vs_planted.by_barangay.map((r) => ({ label: r.name, a: r.planned, b: r.planted }))
  const pvS = d.planned_vs_planted.by_species.map((r) => ({ label: r.name, a: r.planned, b: r.planted }))
  const pvSeries = [{ label: t('an.planned'), color: PALETTE.blue }, { label: t('an.planted'), color: PALETTE.orange }]
  const chk = k.field_checks_current ?? {}
  const checksTotal = Object.values(chk).reduce((a, b) => a + b, 0)
  const top = (rows) => (rows.length ? `${rows[0].label} (${nf(rows[0].a ?? rows[0].value)})` : '—')
  const colCsv = (extra = []) => [{ key: 'label', label: t('an.col.name') }, { key: 'a', label: t('an.col.value') }, ...extra]

  return (
    <div className="an-root" data-role="analytics">
      {filters}
      <div className="an-kpis" data-role="kpis">
        <Kpi label={t('an.kpi.squares')} value={k.squares_scored} />
        <Kpi label={t('an.kpi.species')} value={k.species} />
        <Kpi label={t('an.kpi.suitable')} value={k.suitable_squares} sub={t('an.kpi.suitableSub', { th: d.suitability.threshold })} />
        <Kpi label={t('an.kpi.plans')} value={k.plans} />
        <Kpi label={t('an.kpi.trees')} value={k.trees_planned} />
        <Kpi
          label={t('an.kpi.checks')}
          value={checksTotal}
          sub={Object.entries(chk).filter(([, n]) => n > 0).map(([s, n]) => `${t(`an.status.${s}`)} ${n}`).join(' · ') || t('an.none')}
        />
      </div>

      <div className="an-grid">
        <ChartCard
          title={t('an.c.s')}
          note={t('an.c.s.note', { zero: nf(S.zero), th: d.suitability.threshold })}
          rows={sRows}
          columns={[{ key: 'range', label: t('an.ax.s') }, { key: 'value', label: t('an.ax.pairs') }]}
          filename="suitability_histogram"
          summary={t('an.sum.hist', { n: nf(S.n), zero: nf(S.zero) })}
        >
          <VBars data={sRows} xLabel={t('an.ax.s')} yLabel={t('an.ax.pairs')} />
        </ChartCard>

        <ChartCard title={t('an.c.brgy')} rows={brgy} columns={[{ key: 'label', label: t('an.barangay') }, { key: 'a', label: t('an.col.suitable') }, { key: 'total', label: t('an.col.total') }]} filename="suitable_squares_by_barangay" summary={t('an.sum.top', { top: top(brgy) })}>
          <HBars rows={brgy} series={[{ label: t('an.col.suitable'), color: PALETTE.blue }]} xLabel={t('an.ax.squares')} />
        </ChartCard>

        <ChartCard title={t('an.c.species')} rows={spRows} columns={colCsv()} filename="suitable_squares_by_species" summary={t('an.sum.top', { top: top(spRows) })}>
          <HBars rows={spRows} series={[{ label: t('an.ax.squares'), color: PALETTE.green }]} xLabel={t('an.ax.squares')} limit={10} />
        </ChartCard>

        <ChartCard
          title={t('an.c.ph')}
          note={t('an.c.ph.note', { with: nf(d.ph.squares_with_estimate), without: nf(d.ph.squares_without_estimate) })}
          rows={phRows}
          columns={[{ key: 'range', label: t('an.ax.ph') }, { key: 'value', label: t('an.ax.squares') }]}
          filename="soil_ph_estimate_distribution"
          summary={t('an.sum.ph', { n: nf(d.ph.squares_with_estimate) })}
        >
          <VBars data={phRows} xLabel={t('an.ax.ph')} yLabel={t('an.ax.squares')} color={PALETTE.orange} />
        </ChartCard>

        <ChartCard title={t('an.c.verdict')} note={t('an.c.verdict.note')} rows={vRows} columns={[{ key: 'label', label: t('an.col.name') }, { key: 'a', label: t('an.ax.pairs') }]} filename="ph_verdict_counts" summary={t('an.sum.top', { top: top([...vRows].sort((a, b) => b.a - a.a)) })}>
          <HBars rows={vRows} series={[{ label: t('an.ax.pairs'), color: PALETTE.orange }]} xLabel={t('an.ax.pairs')} />
        </ChartCard>

        <ChartCard title={t('an.c.zone')} rows={zRows} columns={colCsv()} filename="squares_by_zone" summary={t('an.sum.top', { top: top(zRows) })}>
          <HBars rows={zRows} series={[{ label: t('an.ax.squares'), color: PALETTE.green }]} xLabel={t('an.ax.squares')} limit={8} />
          <ul className="an-callouts">
            <li data-role="outside-zoning">{t('an.land.outside', { n: nf(d.land.outside_zoning_map) })}</li>
            <li data-role="no-soil">{d.land.no_soil_data === null ? t('an.land.nosoilNA') : t('an.land.nosoil', { n: nf(d.land.no_soil_data) })}</li>
          </ul>
        </ChartCard>

        <ChartCard
          title={t('an.c.activity')}
          note={d.activity.by_week.length === 0 ? t('an.empty.text') : d.activity.note}
          rows={weeks}
          columns={[{ key: 'week', label: t('an.ax.week') }, { key: 'plans', label: t('an.plans') }, { key: 'field_checks', label: t('an.checks') }, { key: 'trees_planned', label: t('an.ax.trees') }]}
          filename="activity_by_week"
          summary={t('an.sum.weeks', { n: weeks.length })}
        >
          {weeks.length === 0 ? (
            <EmptyState icon="clipboard" title={t('an.empty.title')} text={t('an.empty.text')} />
          ) : (
            <GroupBars data={weeks} series={[{ key: 'plans', label: t('an.plans'), color: PALETTE.blue }, { key: 'field_checks', label: t('an.checks'), color: PALETTE.orange }]} xLabel={t('an.ax.week')} yLabel={t('an.ax.count')} />
          )}
        </ChartCard>

        <ChartCard
          title={t('an.c.trees')}
          rows={weeks}
          columns={[{ key: 'week', label: t('an.ax.week') }, { key: 'trees_planned', label: t('an.ax.trees') }]}
          filename="trees_planned_by_week"
          summary={t('an.sum.weeks', { n: weeks.length })}
        >
          {weeks.length === 0 ? <EmptyState icon="clipboard" title={t('an.empty.title')} text={t('an.empty.text')} /> : <VBars data={weeks.map((w) => ({ label: w.label, value: w.trees_planned }))} xLabel={t('an.ax.week')} yLabel={t('an.ax.trees')} color={PALETTE.green} />}
        </ChartCard>

        <ChartCard title={t('an.c.pvb')} note={d.planned_vs_planted.note} rows={pvB} columns={[{ key: 'label', label: t('an.barangay') }, { key: 'a', label: t('an.planned') }, { key: 'b', label: t('an.planted') }]} filename="planned_vs_planted_by_barangay" summary={t('an.sum.top', { top: top(pvB) })}>
          {pvB.length === 0 ? <EmptyState icon="clipboard" title={t('an.empty.title')} text={t('an.empty.text')} /> : <HBars rows={pvB} series={pvSeries} xLabel={t('an.ax.trees')} />}
        </ChartCard>

        <ChartCard title={t('an.c.pvs')} note={d.planned_vs_planted.note} rows={pvS} columns={[{ key: 'label', label: t('an.species') }, { key: 'a', label: t('an.planned') }, { key: 'b', label: t('an.planted') }]} filename="planned_vs_planted_by_species" summary={t('an.sum.top', { top: top(pvS) })}>
          {pvS.length === 0 ? <EmptyState icon="clipboard" title={t('an.empty.title')} text={t('an.empty.text')} /> : <HBars rows={pvS} series={pvSeries} xLabel={t('an.ax.trees')} />}
        </ChartCard>
      </div>
      <p className="muted an-forecast" data-role="no-forecast">
        {t('an.noforecast')}
      </p>
    </div>
  )
}
