import { useState } from 'react'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import SeasonBadge from './SeasonBadge.jsx'

// Step 4 (goal "I have species"): search, pick species. Each species shows its season for the chosen dates. With the season filter on, species that
// are out of season are hidden (a species that is already chosen stays visible so that nothing disappears from under the user).
export default function SpeciesMultiPicker({ species, selected, onChange, onlySeason, onInfo }) {
  const [query, setQuery] = useState('')
  if (species.status === 'loading') return <div className="v2 v2-embedded"><Loading what="Loading the species list" /></div>
  if (species.status === 'error') return <div className="v2 v2-embedded"><ErrorBox error={species.error} onRetry={species.retry} title="Could not load the species list" brief /></div>
  if (species.status !== 'ok') return null

  const chosen = new Set(selected)
  const all = [...species.data.species].sort((a, b) => a.common_name.localeCompare(b.common_name))
  const visible = onlySeason ? all.filter((s) => s.season?.status !== 'out_of_season' || chosen.has(s.species_id)) : all
  const q = query.trim().toLowerCase()
  const shown = q ? visible.filter((s) => s.common_name.toLowerCase().includes(q) || String(s.scientific_name ?? '').toLowerCase().includes(q)) : visible
  const toggle = (id) => onChange(chosen.has(id) ? selected.filter((x) => x !== id) : [...selected, id])

  return (
    <div>
      <label className="sr-only" htmlFor="nw-species-search">
        Search species
      </label>
      <input id="nw-species-search" type="search" className="nw-input" placeholder="Search species" value={query} onChange={(e) => setQuery(e.target.value)} />
      <div className="nw-row">
        <button type="button" className="nw-btn nw-btn-small" onClick={() => onChange([...new Set([...selected, ...shown.map((s) => s.species_id)])])}>
          Select all{q ? ' shown' : ''}
        </button>
        <button type="button" className="nw-btn nw-btn-small" onClick={() => onChange([])} disabled={selected.length === 0}>
          Clear
        </button>
        <span className="nw-count" role="status">
          {selected.length} chosen
        </span>
      </div>
      <div className="nw-checklist" role="group" aria-label="Species list">
        {shown.length === 0 && <p className="nw-hint">{q ? `No species match “${query}”.` : 'No species to show.'}</p>}
        {shown.map((s) => (
          <label key={s.species_id} className="nw-check nw-check-sp">
            <input type="checkbox" checked={chosen.has(s.species_id)} onChange={() => toggle(s.species_id)} />
            <span className="nw-check-main">
              <span className="nw-check-line">
                <span>{s.common_name}</span>
                <button type="button" className="nw-infobtn" aria-label={`About ${s.common_name}`} onClick={(e) => { e.preventDefault(); onInfo(s.species_id) }}>
                  i
                </button>
              </span>
              <SeasonBadge season={s.season} />
            </span>
          </label>
        ))}
      </div>
    </div>
  )
}
