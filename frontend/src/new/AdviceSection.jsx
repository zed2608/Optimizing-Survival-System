import { useState } from 'react'
import Icon from './Icon.jsx'
import ProvisionalTag from './ProvisionalTag.jsx'
import AskHelp from './tutorial/AskHelp.jsx'

// "Ways to improve survival" (round 17): short advice for a species or a plan. ADVICE ONLY: it never changes a score. Every item is advice that the agriculturist
// still has to confirm. Collapsible: closed in Simple, open in Detailed (the parent gives it key={view}, so it starts again when the view changes).
// Simple shows at most `limit` items (4 per species, 5 per plan); Detailed shows all and the source of each item.
export default function AdviceSection({ items, note, view, limit }) {
  const full = view === 'full'
  const [open, setOpen] = useState(full)
  if (!items || items.length === 0) return null
  const shown = full ? items : items.slice(0, limit)
  const hidden = items.length - shown.length
  return (
    <section className="nw-advice" aria-label="Ways to improve survival" data-advice-open={open ? 'yes' : 'no'}>
      <div className="nw-advice-bar">
        <button type="button" className="nw-advice-head" aria-expanded={open} aria-controls="nw-advice-list" onClick={() => setOpen((o) => !o)}>
          <Icon name={open ? 'down' : 'right'} size={14} /> <span>Ways to improve survival</span> <ProvisionalTag />
        </button>
        <AskHelp id="advice-what" />
      </div>
      <p className="nw-advice-note muted">{note}</p>
      {open && (
        <>
          <ul className="nw-advice-list" id="nw-advice-list">
            {shown.map((it) => (
              <li key={`${it.rule_id}-${(it.species ?? []).join(',')}`}>
                <Icon name="sprout" size={14} />
                <span>
                  {it.text}
                  {it.species && it.species.length > 0 && <span className="muted"> For: {it.species.join(', ')}.</span>}
                  {full && <span className="nw-advice-src muted"> Source: {it.source}.</span>}
                </span>
              </li>
            ))}
          </ul>
          {hidden > 0 && <p className="muted nw-advice-more">{hidden} more in the Detailed view.</p>}
        </>
      )}
    </section>
  )
}
