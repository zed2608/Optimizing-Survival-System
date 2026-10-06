import { useId, useState } from 'react'
import Icon from './Icon.jsx'
import DatasetNote from './DatasetNote.jsx'
import FieldSummary from './FieldSummary.jsx'

function Section({ title, open, onToggle, children }) {
  const id = useId()
  return (
    <div className="nw-more-sec">
      <button type="button" className="nw-more-item" aria-expanded={open} aria-controls={id} onClick={onToggle}>
        <span>{title}</span>
        <Icon name={open ? 'down' : 'right'} size={14} />
      </button>
      {open && (
        <div id={id} className="nw-more-content">
          {children}
        </div>
      )}
    </div>
  )
}

// The single "More" menu at the bottom of the sidebar: known limits, dataset version, field-check summary with download and import, other dashboards.
export default function MoreMenu({ health, fieldSummary, observer, onObserver, onChanged }) {
  const bodyId = useId()
  const [open, setOpen] = useState(false)
  const [sec, setSec] = useState('')
  const pick = (id) => setSec((s) => (s === id ? '' : id))
  return (
    <section className="nw-more" aria-label="More">
      <button type="button" className="nw-more-toggle" aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen((o) => !o)}>
        <span>More</span>
        <Icon name={open ? 'down' : 'right'} size={14} />
      </button>
      {open && (
        <div id={bodyId} className="nw-more-body">
          <Section title="Known limits" open={sec === 'limits'} onToggle={() => pick('limits')}>
            {health.status === 'ok' ? (
              <ul className="nw-limits-list">
                {health.data.limits.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            ) : (
              <p className="nw-hint">{health.status === 'loading' ? 'Loading…' : 'The limits could not be loaded (the planning service is not reachable).'}</p>
            )}
          </Section>
          <Section title="Dataset version" open={sec === 'dataset'} onToggle={() => pick('dataset')}>
            <DatasetNote health={health} />
          </Section>
          <Section title="Field checks" open={sec === 'field'} onToggle={() => pick('field')}>
            <FieldSummary summary={fieldSummary} observer={observer} onObserver={onObserver} onChanged={onChanged} />
          </Section>
          <p className="nw-links">
            <a href="#/legacy">Earlier dashboard</a> · <a href="#/v2">First v2 page</a>
          </p>
        </div>
      )}
    </section>
  )
}
