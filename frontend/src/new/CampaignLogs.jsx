import { useMemo, useState } from 'react'
import Icon from './Icon.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { useApi } from '../v2/useApi.js'
import { purposeLabel } from '../v2/labels.js'
import KitControls from './KitControls.jsx'
import { campaignStatus, formatSpanYear } from './season.js'
import WeatherCard from './WeatherCard.jsx'

const STATUS = {
  active: { word: 'Active', symbol: 'dot' },
  upcoming: { word: 'Upcoming', symbol: 'clock' },
  concluded: { word: 'Concluded', symbol: 'check' },
  none: { word: 'No dates', symbol: 'dash' },
}
const FILTERS = ['all', 'active', 'upcoming', 'concluded', 'none']
const LIMIT = 100 // the most the planning service returns at once

// The "Campaign Logs" tab: every saved plan as a card with its campaign, dates, status, kit and weather advice. Nothing here deletes a plan.
export default function CampaignLogs({ today, onOpen, onStudio }) {
  const api = useApi(`/plans?limit=${LIMIT}`)
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')
  const [opening, setOpening] = useState('')
  const [openError, setOpenError] = useState('')
  const plans = useMemo(() => (api.status === 'ok' ? api.data.plans.map((p) => ({ ...p, status: campaignStatus(p.campaign.start, p.campaign.end, today) })) : []), [api.status, api.data, today])
  const counts = useMemo(() => Object.fromEntries(FILTERS.map((f) => [f, f === 'all' ? plans.length : plans.filter((p) => p.status === f).length])), [plans])
  const t = q.trim().toLowerCase()
  const shown = plans.filter((p) => (filter === 'all' || p.status === filter) && (!t || [p.campaign.name, p.campaign.unit, p.plan_id].some((v) => String(v ?? '').toLowerCase().includes(t))))

  async function open(id) {
    setOpening(id)
    setOpenError('')
    try {
      await onOpen(id)
    } catch (e) {
      setOpenError(e.message)
    } finally {
      setOpening('')
    }
  }

  if (api.status === 'loading') return <div className="v2 v2-embedded nw-logs"><Loading what="Loading the saved plans" /></div>
  if (api.status === 'error') return <div className="v2 v2-embedded nw-logs"><ErrorBox error={api.error} onRetry={api.retry} title="Could not load the saved plans" /></div>
  if (plans.length === 0) {
    return (
      <div className="v2 v2-embedded nw-logs nw-empty">
        <h3>No plans saved yet</h3>
        <p className="nw-plain">Make a plan in step 5 of Active Studio. It will appear here.</p>
        <button type="button" className="btn btn-primary" onClick={onStudio}>
          Go to Active Studio
        </button>
      </div>
    )
  }
  return (
    <div className="nw-logs">
      <div className="nw-logbar v2 v2-embedded">
        <div className="nw-chips" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button key={f} type="button" className={`nw-fchip ${filter === f ? 'is-active' : ''}`} aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {f === 'all' ? 'All' : STATUS[f].word} ({counts[f]})
            </button>
          ))}
        </div>
        <label className="sr-only" htmlFor="nw-log-search">
          Search campaigns
        </label>
        <input id="nw-log-search" type="search" className="fc-input" placeholder="Search name, unit or plan id" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {api.data.total_saved > LIMIT && <p className="nw-modal-text">Showing the newest {LIMIT} of {api.data.total_saved} saved plans.</p>}
      {openError && <p className="fc-bad" role="alert">{openError}</p>}
      {shown.length === 0 && <p className="nw-modal-text">No plan matches.</p>}
      <ul className="nw-loglist">
        {shown.map((p) => {
          const c = p.campaign
          const st = STATUS[p.status]
          return (
            <li key={p.plan_id} className="v2 v2-embedded nw-logcard" aria-label={`Plan ${p.plan_id}`}>
              <div className="nw-logcard-head">
                <h3>{c.name ?? 'Unnamed plan (made before campaigns)'}</h3>
                <span className={`nw-chip nw-st-${p.status}`}>
                  <Icon name={st.symbol} size={14} /> 
                  {st.word}
                </span>
              </div>
              <div className="nw-loc-line">{c.unit ? `Unit: ${c.unit}` : c.status === 'missing' ? 'Unit: missing (older plan)' : 'No unit given'}</div>
              <div className="nw-loc-line">{c.start && c.end ? `Planting window: ${formatSpanYear(c.start, c.end)}` : 'Planting window: missing (older plan)'}</div>
              <div className="nw-loc-line">
                {purposeLabel(p.purpose)} · {p.n_placed} of {p.n_saplings_requested} trees placed · {p.n_species} species
              </div>
              <div className="nw-loc-line">
                Plan id {p.plan_id} · {p.field_kit_built ? 'Kit built' : 'No kit yet'}
              </div>
              <div className="nw-row nw-logactions">
                <button type="button" className="btn" disabled={opening === p.plan_id} onClick={() => open(p.plan_id)}>
                  {opening === p.plan_id ? 'Opening…' : 'Open on map'}
                </button>
              </div>
              <KitControls planId={p.plan_id} />
              <WeatherCard url={`/plans/${p.plan_id}/advisory`} />
            </li>
          )
        })}
      </ul>
    </div>
  )
}
