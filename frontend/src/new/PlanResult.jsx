import { useMemo, useState } from 'react'
import Icon from './Icon.jsx'
import { fmt, pct } from '../v2/scale.js'
import HelpTip from './HelpTip.jsx'
import KitControls from './KitControls.jsx'
import PlanProgress from './PlanProgress.jsx'
import PlanWeather from './PlanWeather.jsx'
import { shapeColor, shapePath } from './planShapes.js'
import { formatDay, monthsText } from './season.js'
import ViewSwitch from './ViewSwitch.jsx'

// The result card of a created plan: who/what/when, placed / requested, the mix, mean score, field-check exclusions, warnings, and a searchable list of the planned points.
export default function PlanResult({ result, speciesInfo, view, onView, onOpenPoint, onAnother, onOpenWeather, includeUnzoned = true, fieldVersion = 0, onTopUp, onOpenPlan }) {
  const [q, setQ] = useState('')
  const [only, setOnly] = useState('')
  const [shown, setShown] = useState(25)
  const full = view === 'full'
  const s = result.summary
  const blocks = result.layout_mode === 'blocks'
  const lay = s.layout
  const c = result.campaign
  const items = result.plan
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase()
    return items.filter((it) => (!only || String(it.species_id) === only) && (!t || it.point_ref.toLowerCase().includes(t) || (it.block_ref ?? '').toLowerCase().includes(t) || it.species_code.toLowerCase().includes(t) || it.species.toLowerCase().includes(t)))
  }, [items, q, only])
  const stats = useMemo(() => {
    const m = new Map()
    items.forEach((it) => {
      const e = m.get(it.species_id) ?? { n: 0, S: 0, P: 0, W: 0 }
      e.n += 1
      e.trees = (e.trees ?? 0) + (it.trees_planned ?? 1)
      e.S += it.S
      e.P += it.P
      e.W += it.W
      m.set(it.species_id, e)
    })
    return m
  }, [items])
  const planted = result.palette.filter((p) => p.placed > 0)
  const both = planted.filter((p) => p.needs_both_sexes).map((p) => p.species)
  const warnings = [...(s.palette_warnings ?? [])]
  const zn = s.zoning ?? null
  if (zn && zn.unconfirmed_trees > 0) warnings.push(`${zn.unconfirmed_trees} of ${zn.placed_trees} trees are on land outside our zoning map (the CLUP 2021-2031 shows it as Forest Reserve, Watershed): coordinate with MENRO and DENR before planting.`)
  const sel = s.species_selection

  return (
    <div className="nw-ppanel" aria-label="Planting plan">
      <ViewSwitch value={view} onChange={onView} />
      <section className="nw-pcard nw-planhead" aria-label="Plan">
        <h2 className="nw-loc-title">{c.name ?? 'Planting plan'}</h2>
        <div className="nw-loc-line">{c.unit ? `Unit: ${c.unit}` : 'No unit given'}</div>
        <div className="nw-loc-line">
          {c.start && c.end ? `${formatDay(c.start)} - ${formatDay(c.end, true)}` : 'No dates given'} · {s.purpose}
        </div>
        <div className="nw-loc-line">Plan id {result.plan_id}</div>
        <div className="nw-pcard-head nw-plan-kpis">
          <span className="nw-chip fc-verified_plantable">
            {blocks ? `Trees ${s.saplings_placed} of ${s.n_saplings_requested}` : `Placed ${s.saplings_placed} of ${s.n_saplings_requested}`}
          </span>
          {blocks && lay && <span className="nw-chip">{lay.blocks} blocks</span>}
          {blocks && lay && <span className="nw-chip">{lay.hectares_used} ha</span>}
          <span className="nw-chip">Mean score W {fmt(s.mean_W)}</span>
        </div>
        {result.parent_plan_id && (
          <div className="nw-loc-line">
            Top-up of{' '}
            <button type="button" className="fc-link" onClick={() => onOpenPlan?.(result.parent_plan_id)}>
              {result.parent_plan_id}
            </button>
          </div>
        )}
        <div className="nw-loc-line">Area: {s.area_choice?.display_name ?? 'whole municipality'}</div>
        <div className="nw-loc-line">{s.field_checks?.excluded_points ?? 0} squares excluded by field checks</div>
        {s.ground_cover && (
          <div className={`nw-loc-line ${s.ground_cover.flagged_trees > 0 ? 'nw-zoning is-unconfirmed' : ''}`}>
            <Icon name="mountain" size={14} /> {s.ground_cover.flagged_trees} of {s.ground_cover.placed_trees} trees are on squares that look bare, built-up or watery in satellite land cover.
            {s.ground_cover.flagged_trees > 0 ? ' Check them first.' : ''}
          </div>
        )}
        {zn && (
          <div className={`nw-loc-line ${zn.unconfirmed_trees > 0 ? 'nw-zoning is-unconfirmed' : ''}`}>
            <Icon name="dotring" size={14} /> {zn.unconfirmed_trees} of {zn.placed_trees} trees are on land outside our zoning map (CLUP: Forest Reserve, Watershed)
          </div>
        )}
      </section>

      {blocks && (
        <section className="nw-pcard" aria-label="Progress">
          <div className="nw-pcard-head">
            <h3>Progress</h3>
            <HelpTip label="About progress">Counted from the saved field checks of this plan: mark each block Planted (with the number of trees), Can't plant here or Needs recheck in its point panel, or import the filled blocks.csv.</HelpTip>
          </div>
          <PlanProgress planId={result.plan_id} version={fieldVersion} full={full} onTopUp={onTopUp} onOpenPlan={onOpenPlan} />
        </section>
      )}

      {(warnings.length > 0 || both.length > 0) && (
        <section className="nw-pcard" aria-label="Warnings">
          <h3>Please note</h3>
          <ul className="nw-warnlist">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
            {both.length > 0 && <li>Plant both male and female trees of: {both.join(', ')}.</li>}
          </ul>
        </section>
      )}

      <section className="nw-pcard" aria-label="The mix">
        <div className="nw-pcard-head">
          <h3>The mix</h3>
          <HelpTip label="About the mix">The 3-letter code is the one on the map and in the field kit. Share is the part of the trees; a block is one 100 m square planted at the species spacing, and its layout is rows of trees counted from the south-west corner.</HelpTip>
        </div>
        <table className="nw-table">
          <thead>
            <tr>
              <th scope="col">Code</th>
              <th scope="col">Species</th>
              <th scope="col">Share</th>
              <th scope="col">{blocks ? 'Trees' : 'Count'}</th>
              {blocks && <th scope="col">Blocks</th>}
              {blocks && <th scope="col">Spacing and layout</th>}
              {full && <th scope="col">Mean S / P / W</th>}
            </tr>
          </thead>
          <tbody>
            {planted.map((p) => {
              const sp = speciesInfo.get(p.species_id)
              const st = stats.get(p.species_id)
              return (
                <tr key={p.species_id}>
                  <th scope="row">
                    <svg viewBox="-1.5 -1.5 3 3" width="16" height="16" aria-hidden="true">
                      <path d={shapePath(sp?.kind ?? 0)} fill={shapeColor(sp?.kind ?? 0)} stroke="#0f172a" strokeWidth="0.22" />
                    </svg>{' '}
                    {sp?.code}
                  </th>
                  <td>{p.species}</td>
                  <td>{pct(p.placed / Math.max(s.saplings_placed, 1))}</td>
                  <td>{p.placed}</td>
                  {blocks && <td>{p.blocks_placed}</td>}
                  {blocks && (
                    <td>
                      {p.spacing_m} m · {p.rows} rows × {p.trees_per_row} ({p.capacity} per full block)
                    </td>
                  )}
                  {full && <td>{st ? `${fmt(st.S / st.n)} / ${fmt(st.P / st.n)} / ${fmt(st.W / st.n)}` : '-'}</td>}
                </tr>
              )
            })}
          </tbody>
        </table>
        {full && (
          <div className="nw-fullnote">
            <div>
              Caps: {sel ? `per species ${pct(sel.caps.max_species_share.used)}, per genus ${pct(sel.caps.max_genus_share.used)} (${sel.caps_note})` : 'default (per species 20%, per genus 30%)'}
            </div>
            <div>Shared planting months: {monthsText(s.palette_common_planting_months ?? [])}</div>
            {result.summary.season && <div>Months inside your dates: {monthsText(result.summary.season.palette_common_months_in_window)}</div>}
            <div>
              Squares: {s.area?.candidate_points_after_exclusion} candidates, {s.unused_candidate_points} unused. Unplaced {blocks ? 'trees' : 'saplings'}: {s.saplings_unmatched} unmatched, {s.saplings_unallocated} not shared out.
            </div>
          </div>
        )}
      </section>

      <section className="nw-pcard" aria-label="Field kit">
        <div className="nw-pcard-head">
          <h3>Field kit</h3>
        </div>
        <KitControls planId={result.plan_id} />
      </section>

      <section className="nw-pcard" aria-label="Weather for this plan">
        <div className="nw-pcard-head">
          <h3>Weather this week</h3>
        </div>
        <PlanWeather result={result} includeUnzoned={includeUnzoned} onOpenWeather={onOpenWeather} />
      </section>

      <section className="nw-pcard" aria-label={blocks ? 'Planned blocks' : 'Planned points'}>
        <div className="nw-pcard-head">
          <h3>
            {blocks ? 'Planned blocks' : 'Planned points'} ({rows.length})
          </h3>
        </div>
        <label className="sr-only" htmlFor="nw-plan-search">
          Search planned points
        </label>
        <input id="nw-plan-search" type="search" className="fc-input" placeholder={blocks ? 'Search by block ref or species code' : 'Search by point ref or species code'} value={q} onChange={(e) => { setQ(e.target.value); setShown(25) }} />
        <label className="sr-only" htmlFor="nw-plan-species">
          Filter by species
        </label>
        <select id="nw-plan-species" className="fc-input nw-plan-filter" value={only} onChange={(e) => { setOnly(e.target.value); setShown(25) }}>
          <option value="">All species</option>
          {planted.map((p) => (
            <option key={p.species_id} value={String(p.species_id)}>
              {speciesInfo.get(p.species_id)?.code} · {p.species}
            </option>
          ))}
        </select>
        <ul className="nw-planlist">
          {rows.slice(0, shown).map((it) => (
            <li key={it.point_id}>
              <button type="button" className="nw-rowbtn" onClick={() => onOpenPoint(it)}>
                {it.point_ref}
              </button>{' '}
              {it.species} · {blocks ? `${it.trees_planned} trees · ` : ''}W {fmt(it.W)} · {it.barangay_display || 'outside barangays'}
            </li>
          ))}
          {rows.length === 0 && <li className="muted">No planned point matches.</li>}
        </ul>
        {rows.length > shown && (
          <button type="button" className="btn btn-small" onClick={() => setShown((n) => n + 50)}>
            Show more
          </button>
        )}
      </section>

      <section className="nw-pcard">
        <button type="button" className="btn" onClick={onAnother}>
          Make another plan
        </button>
        <p className="nw-plain">The plan is saved as {result.plan_id}.</p>
      </section>
    </div>
  )
}
