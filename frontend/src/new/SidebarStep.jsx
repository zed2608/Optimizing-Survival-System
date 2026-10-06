import { useId } from 'react'
import Icon from './Icon.jsx'
import HelpTip from './HelpTip.jsx'

// One collapsible step of the sidebar. Collapsed it shows a one-line summary of the choice; the caller keeps only one step open at a time.
export default function SidebarStep({ n, title, summary, open, onToggle, help, id: stepId, icon = null, children }) {
  const uid = useId()
  const bodyId = `${uid}-body`
  return (
    <section className={`nw-step ${open ? 'is-open' : ''}`} data-step={stepId}>
      <div className="nw-step-head">
        <button type="button" className="nw-step-toggle" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
          <span className="nw-step-n" aria-hidden="true">
            {n}
          </span>
          <span className="nw-step-text">
            <span className="nw-step-title">
              {icon && <Icon name={icon} size={16} className="nw-step-icon" />}
              {title}
            </span>
            {!open && <span className="nw-step-sum">{summary}</span>}
          </span>
          <span className="nw-chev" aria-hidden="true">
            <Icon name={open ? 'down' : 'right'} size={14} />
          </span>
        </button>
        {help && <HelpTip label={title}>{help}</HelpTip>}
      </div>
      {open && (
        <div id={bodyId} className="nw-step-body">
          {children}
        </div>
      )}
    </section>
  )
}
