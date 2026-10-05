import { useState } from 'react'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'

// Mode 1: choose one or more species (search box, Select all, Clear) and how they must combine.
export default function SpeciesMultiPicker({ species, selected, onChange, combine, onCombine }) {
  const [query, setQuery] = useState('')
  if (species.status === 'loading') return <div className="v2 v2-embedded"><Loading what="Loading the species list" /></div>
  if (species.status === 'error') return <div className="v2 v2-embedded"><ErrorBox error={species.error} onRetry={species.retry} title="Could not load the species list" brief /></div>
  if (species.status !== 'ok') return null

  const all = [...species.data.species].sort((a, b) => a.common_name.localeCompare(b.common_name))
  const q = query.trim().toLowerCase()
  const shown = q ? all.filter((s) => s.common_name.toLowerCase().includes(q) || String(s.scientific_name ?? '').toLowerCase().includes(q)) : all
  const chosen = new Set(selected)
  const toggle = (id) => onChange(chosen.has(id) ? selected.filter((x) => x !== id) : [...selected, id])

  return (
    <div>
      <label className="nw-label" htmlFor="nw-species-search">
        Species ({selected.length} of {all.length} selected)
      </label>
      <input id="nw-species-search" type="search" className="nw-input" placeholder="Search by common or scientific name" value={query} onChange={(e) => setQuery(e.target.value)} />
      <div className="nw-row">
        <button type="button" className="nw-btn nw-btn-small" onClick={() => onChange([...new Set([...selected, ...shown.map((s) => s.species_id)])])}>
          Select all{q ? ' shown' : ''}
        </button>
        <button type="button" className="nw-btn nw-btn-small" onClick={() => onChange([])} disabled={selected.length === 0}>
          Clear
        </button>
      </div>
      <div className="nw-checklist" role="group" aria-label="Species list">
        {shown.length === 0 && <p className="nw-hint">No species match “{query}”.</p>}
        {shown.map((s) => (
          <label key={s.species_id} className="nw-check">
            <input type="checkbox" checked={chosen.has(s.species_id)} onChange={() => toggle(s.species_id)} />
            <span>{s.common_name}</span>
          </label>
        ))}
      </div>

      <fieldset className="nw-fieldset nw-combine">
        <legend className="nw-label">A place counts when…</legend>
        <label className={`nw-choice ${combine === 'all' ? 'is-selected' : ''}`}>
          <input type="radio" name="nw-combine" checked={combine === 'all'} onChange={() => onCombine('all')} />
          <span>
            <strong>Must suit all selected</strong>
            <span className="nw-choice-help">Every selected species can grow there. Score = the lowest of their scores.</span>
          </span>
        </label>
        <label className={`nw-choice ${combine === 'any' ? 'is-selected' : ''}`}>
          <input type="radio" name="nw-combine" checked={combine === 'any'} onChange={() => onCombine('any')} />
          <span>
            <strong>Suits at least one</strong>
            <span className="nw-choice-help">At least one selected species can grow there. Score = the highest of their scores.</span>
          </span>
        </label>
      </fieldset>
    </div>
  )
}
