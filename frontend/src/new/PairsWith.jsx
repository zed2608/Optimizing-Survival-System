import { useApi } from '../v2/useApi.js'

// Step 4, "I have species": after a species is chosen, the species that pair well with it (starting rules of the species data) with a one-tap "Add".
// Only partners that are not chosen yet are offered; nothing is shown while loading, when there is none, or when the table is not built.
export default function PairsWith({ speciesId, chosen, onAdd, query = '' }) {
  const api = useApi(speciesId ? `/species/${speciesId}/partners?${query}` : null)
  if (api.status !== 'ok') return null
  const open = api.data.partners.filter((p) => !chosen.includes(p.species_id)).slice(0, 2)
  if (open.length === 0) return null
  const names = open.map((p) => p.common_name).join(', ')
  return (
    <div className="nw-pairs" role="status">
      <span className="nw-pairs-text">
        Pairs well with {names}. Add?
      </span>
      <button type="button" className="nw-btn nw-btn-small" aria-label={`Add ${names}`} onClick={() => onAdd(open.map((p) => p.species_id))}>
        Add
      </button>
    </div>
  )
}
