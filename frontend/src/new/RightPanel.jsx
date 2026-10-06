import Icon from './Icon.jsx'
// The right-hand glass panel. It holds the result of the current mode and, when a point has been clicked, a second tab with the existing
// ranking and "Why this score?" accordion. The caller passes the content (children) of the active tab.
export default function RightPanel({ title, subtitle, tabs, activeTab, onTab, onClose, children }) {
  return (
    <aside className="nw-right" aria-label={title}>
      <div className="nw-right-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <div className="nw-right-sub">{subtitle}</div>}
        </div>
        <button type="button" className="nw-btn nw-btn-ghost" onClick={onClose}>
          <Icon name="close" /> Close
        </button>
      </div>
      {tabs.length > 1 && (
        <div className="nw-right-tabs" role="tablist" aria-label="Panel views">
          {tabs.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={activeTab === t.id} className={`nw-rtab ${activeTab === t.id ? 'is-active' : ''}`} onClick={() => onTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
      )}
      <div className="nw-right-body" aria-live="polite">
        {children}
      </div>
    </aside>
  )
}
