import { COUNT_DEFAULT, COUNT_MAX, COUNT_PRESETS, countText, countsSummary } from './counts.js'
import Icon from './Icon.jsx'

// Step 5, "I have species": one row per chosen species with a number box, minus and plus buttons and the presets 10, 20, 50; the total line; the blocks estimate.
export default function CountsForm({ rows, counts, onChange, est }) {
  const { total, valid, nums } = countsSummary(rows.map((r) => r.id), counts)
  const set = (id, v) => onChange(id, String(Math.max(1, Math.min(COUNT_MAX, v))))
  return (
    <div className="nw-countsform" role="group" aria-label="Trees for each species">
      <ul className="nw-counts-list">
        {rows.map((r, k) => {
          const n = nums[k]
          return (
            <li key={r.id} className="nw-counts-row">
              <span className="nw-counts-name">{r.name}</span>
              <span className="nw-stepper">
                <button type="button" className="nw-btn nw-btn-small" aria-label={`Fewer ${r.name} trees`} onClick={() => set(r.id, (Number.isFinite(n) ? n : COUNT_DEFAULT) - 1)}>
                  <Icon name="dash" size={14} />
                </button>
                <input
                  id={`nw-count-${r.id}`}
                  className="nw-input nw-counts-input"
                  type="number"
                  min="1"
                  max={COUNT_MAX}
                  value={countText(counts, r.id)}
                  aria-label={`Number of ${r.name} trees`}
                  aria-invalid={!Number.isFinite(n) || n < 1}
                  onChange={(e) => onChange(r.id, e.target.value)}
                />
                <button type="button" className="nw-btn nw-btn-small" aria-label={`More ${r.name} trees`} onClick={() => set(r.id, (Number.isFinite(n) ? n : COUNT_DEFAULT) + 1)}>
                  <Icon name="plus" size={14} />
                </button>
              </span>
              <span className="nw-counts-presets" role="group" aria-label={`Presets for ${r.name}`}>
                {COUNT_PRESETS.map((v) => (
                  <button key={v} type="button" className={`nw-btn nw-btn-small ${n === v ? 'nw-btn-go' : ''}`} onClick={() => set(r.id, v)}>
                    {v}
                  </button>
                ))}
              </span>
            </li>
          )
        })}
      </ul>
      <p className="nw-counts-total" role="status" id="nw-counts-total">
        Total {total} trees
      </p>
      {!valid && rows.length > 0 && (
        <p className="nw-error" role="alert">
          Trees: 1 to 2000.
        </p>
      )}
      {est && valid && (
        <p className="nw-estimate" role="status">
          About {est.blocks_about} block{est.blocks_about === 1 ? '' : 's'} (about {est.hectares_about} ha)
        </p>
      )}
    </div>
  )
}
