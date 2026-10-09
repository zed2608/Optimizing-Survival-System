import { useMemo, useState } from 'react'
import AskHelp from './tutorial/AskHelp.jsx'
import Icon from './Icon.jsx'
import { fmt, pct } from '../v2/scale.js'
import HelpTip from './HelpTip.jsx'
import KitControls from './KitControls.jsx'
import MatchChip from './MatchChip.jsx'
import PlanProgress from './PlanProgress.jsx'
import PlanWeather from './PlanWeather.jsx'
import ProvisionalTag from './ProvisionalTag.jsx'
import { shapeColor, shapePath } from './planShapes.js'
import { GROUND_FLAGS, planSentence, plainWarning, whyWarning } from './plainWords.js'
import { formatDay, monthsText } from './season.js'
import ViewSwitch from './ViewSwitch.jsx'

const TABS = [
  { id: 'plan', label: 'Plan', icon: 'clipboard' },
  { id: 'kit', label: 'Field kit', icon: 'printer' },
  { id: 'progress', label: 'Progress', icon: 'bars' },
]
const MAX_NOTES = 3 // "Good to know": at most this many bullets in the Simple view

// The result card of a created plan: a header (name, one sentence, three big numbers), a "Check first" box only when something needs attention, then three tabs:
// Plan (the mix, notes, planned blocks, weather), Field kit (two big buttons) and Progress. The Detailed view keeps the technical lines and numbers of before.
export default function PlanResult({ result, speciesInfo, view, onView, onOpenPoint, onAnother, onOpenWeather, includeUnzoned = true, fieldVersion = 0, onTopUp, onOpenPlan, onShowOnMap }) {
  const [q, setQ] = useState('')
  const [only, setOnly] = useState('')
  const [shown, setShown] = useState(25)
  const [tab, setTab] = useState('plan')
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
  const zn = s.zoning ?? null
  const gc = s.ground_cover ?? null
  const sel = s.species_selection
  const counts = s.species_counts ?? null
  const asked = new Map((counts?.per_species ?? []).map((r) => [r.species_id, r]))
  const partner = result.partners ?? null

  // "Check first": only what needs attention (a line with a zero count is never shown)
  const nGround = gc?.flagged_trees ?? 0
  const nZoning = zn?.unconfirmed_trees ?? 0
  const shortfall = counts ? counts.per_species.filter((r) => r.unplaced > 0) : []
  const flaggedItems = items.filter((it) => nGround > 0 && it.flags.some((f) => GROUND_FLAGS.includes(f)) || nZoning > 0 && it.flags.includes('zoning_unconfirmed'))
  const checkFirst = nGround > 0 || nZoning > 0 || shortfall.length > 0

  // "Good to know": plain notes, each with an icon and a "Why?" tip
  const notes = []
  if (s.rehab?.flagged_trees > 0) {                                       // food-bearing species on a landfill or mining site (MAO, provisional): a warning, nobody is left out
    const t = `${s.rehab.flagged_trees} trees of food-bearing species are on landfill or mining land. ${s.rehab.warning}`
    notes.push({ key: 'rehab', icon: 'warn', text: t, why: whyWarning(t), raw: t, prov: true })
  }
  if (s.habagat?.affected_trees > 0) {                                    // the Habagat multiplier (MAO, provisional)
    const t = `Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep. The overall match of ${s.habagat.affected_trees} trees is lowered by 20%.`
    notes.push({ key: 'habagat', icon: 'rain', text: t, why: whyWarning(t), raw: t, prov: true })
  }
  ;(s.palette_warnings ?? []).filter((w) => !/^Heavy rain and flooding \(Habagat\)/.test(w)).forEach((w) => notes.push({ key: w, icon: 'warn', text: plainWarning(w), why: whyWarning(w), raw: w }))
  if (both.length > 0) {
    const t = `Plant both male and female trees of: ${both.join(', ')}.`
    notes.push({ key: 'sexes', icon: 'tree', text: t, why: whyWarning(t), raw: t })
  }
  const seasonWarn = (s.palette_warnings ?? []).some((w) => /^season:/i.test(w))
  const shownNotes = full ? notes : notes.slice(0, MAX_NOTES)

  return (
    <div className="nw-ppanel" aria-label="Planting plan">
      <ViewSwitch value={view} onChange={onView} />
      <section className="nw-pcard nw-planhead" aria-label="Plan">
        <h2 className="nw-loc-title">{c.name ?? 'Planting plan'}</h2>
        <p className="nw-plan-sentence">{planSentence(result)}</p>
        <div className="nw-bignums" role="group" aria-label="The plan in three numbers">
          <div className="nw-bignum">
            <strong>{s.saplings_placed}</strong>
            <span>Trees{s.saplings_placed < s.n_saplings_requested ? ` (of ${s.n_saplings_requested})` : ''}</span>
          </div>
          {blocks && lay ? (
            <>
              <div className="nw-bignum">
                <strong>{lay.blocks}</strong>
                <span>Blocks</span>
              </div>
              <div className="nw-bignum">
                <strong>{lay.hectares_used}</strong>
                <span>Hectares</span>
              </div>
            </>
          ) : (
            <div className="nw-bignum">
              <strong>{items.length}</strong>
              <span>Squares</span>
            </div>
          )}
        </div>
        {result.parent_plan_id && (
          <div className="nw-loc-line">
            Top-up of{' '}
            <button type="button" className="fc-link" onClick={() => onOpenPlan?.(result.parent_plan_id)}>
              {result.parent_plan_id}
            </button>
          </div>
        )}
        {full && (
          <div className="nw-planfacts">
            <div className="nw-loc-line">{c.unit ? `Unit: ${c.unit}` : 'No unit given'}</div>
            <div className="nw-loc-line">
              {c.start && c.end ? `${formatDay(c.start)} - ${formatDay(c.end, true)}` : 'No dates given'} · {s.purpose}
            </div>
            <div className="nw-pcard-head nw-plan-kpis">
              <span className="nw-chip fc-verified_plantable">{blocks ? `Trees ${s.saplings_placed} of ${s.n_saplings_requested}` : `Placed ${s.saplings_placed} of ${s.n_saplings_requested}`}</span>
              {blocks && lay && <span className="nw-chip">{lay.blocks} blocks</span>}
              {blocks && lay && <span className="nw-chip">{lay.hectares_used} ha</span>}
              <span className="nw-chip">Mean score W {fmt(s.mean_W)}</span>
            </div>
            <div className="nw-loc-line">Area: {s.area_choice?.display_name ?? 'whole municipality'}</div>
            {(s.field_checks?.excluded_points ?? 0) > 0 && <div className="nw-loc-line">{s.field_checks.excluded_points} squares excluded by field checks</div>}
          </div>
        )}
        {!full && (
          <div className="nw-loc-line">
            Overall match <MatchChip w={s.mean_W} />
          </div>
        )}
      </section>

      {checkFirst && (
        <section className="nw-pcard nw-checkfirst" aria-label="Check first">
          <div className="nw-pcard-head">
            <h3>
              <Icon name="warn" /> Check first <AskHelp id="check-first" />
            </h3>
          </div>
          <ul className="nw-notelist">
            {nGround > 0 && (
              <li>
                <Icon name="mountain" size={14} /> {nGround} of {gc.placed_trees} trees are on squares that look bare, built-up or watery in satellite land cover. Check them first.
              </li>
            )}
            {nZoning > 0 && (
              <li>
                <Icon name="dotring" size={14} /> {nZoning} of {zn.placed_trees} trees are on land outside our zoning map (CLUP: Forest Reserve, Watershed). Coordinate with MENRO and DENR before planting.
              </li>
            )}
            {shortfall.map((r) => (
              <li key={r.species_id}>
                <Icon name="close" size={14} /> {r.species}: {r.placed} of {r.requested} trees placed. {r.reason}
              </li>
            ))}
          </ul>
          {flaggedItems.length > 0 && onShowOnMap && (
            <button type="button" className="nw-btn" onClick={() => onShowOnMap(flaggedItems)}>
              <Icon name="map" /> Show these on the map
            </button>
          )}
        </section>
      )}

      <div className="nw-ptabs" role="tablist" aria-label="Plan sections">
        {TABS.filter((t) => blocks || t.id !== 'progress').map((t) => (
          <button key={t.id} type="button" role="tab" id={`nw-ptab-${t.id}`} aria-selected={tab === t.id} aria-controls={`nw-ppanel-${t.id}`} className={`nw-ptab ${tab === t.id ? 'is-active' : ''}`} onClick={() => setTab(t.id)}>
            <Icon name={t.icon} size={16} /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'plan' && (
        <div role="tabpanel" id="nw-ppanel-plan" aria-labelledby="nw-ptab-plan">
          {shownNotes.length > 0 && (
            <section className="nw-pcard" aria-label="Good to know">
              <h3>Good to know</h3>
              <ul className="nw-notelist">
                {shownNotes.map((n) => (
                  <li key={n.key}>
                    <Icon name={n.icon} size={14} />
                    <span className="nw-note-text">
                      {full ? n.raw : n.text} {n.prov && <ProvisionalTag />}
                      {!full && <HelpTip label={`Why: ${n.text}`}>{n.why}</HelpTip>}
                    </span>
                  </li>
                ))}
              </ul>
              {full && shownNotes.some((n) => n.text !== n.raw) && <p className="muted">Plain words: {shownNotes.map((n) => n.text).join(' ')}</p>}
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
                  const ask = asked.get(p.species_id)
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
                      <td>{ask ? `${p.placed} of ${ask.requested}` : p.placed}</td>
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
            {partner && (
              <p className="nw-plain nw-partnerline" role="status">
                <Icon name={partner.pairs.length ? 'check' : 'dash'} size={14} /> {partner.text}
                <HelpTip label="About partner rules">{partner.note}</HelpTip>
              </p>
            )}
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
                {seasonWarn && <div>Season note: {(s.palette_warnings ?? []).find((w) => /^season:/i.test(w))}</div>}
              </div>
            )}
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
                  {it.species} · {blocks ? `${it.trees_planned} trees · ` : ''}
                  {full ? `W ${fmt(it.W)}` : `match ${Math.round(it.W * 100)}%`} · {it.barangay_display || 'outside barangays'}
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
        </div>
      )}

      {tab === 'kit' && (
        <div role="tabpanel" id="nw-ppanel-kit" aria-labelledby="nw-ptab-kit">
          <section className="nw-pcard" aria-label="Field kit">
            <div className="nw-pcard-head">
              <h3>Field kit</h3>
            </div>
            <KitControls planId={result.plan_id} simple={!full} />
          </section>
        </div>
      )}

      {tab === 'progress' && blocks && (
        <div role="tabpanel" id="nw-ppanel-progress" aria-labelledby="nw-ptab-progress">
          <section className="nw-pcard" aria-label="Progress">
            <div className="nw-pcard-head">
              <h3>Progress</h3>
              <HelpTip label="About progress">Counted from the saved field checks of this plan: mark each block Planted (with the number of trees), Can't plant here or Needs recheck in its point panel, or import the filled blocks.csv.</HelpTip>
            </div>
            <PlanProgress planId={result.plan_id} version={fieldVersion} full={full} onTopUp={onTopUp} onOpenPlan={onOpenPlan} />
          </section>
        </div>
      )}

      <section className="nw-pcard">
        <button type="button" className="btn" onClick={onAnother}>
          Make another plan
        </button>
        <p className="nw-planid">{full ? `The plan is saved as ${result.plan_id}.` : `Plan id ${result.plan_id}`}</p>
        {full && <p className="nw-planid">Plan id {result.plan_id}</p>}
      </section>
    </div>
  )
}
