import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import Icon from '../Icon.jsx'

// The shared components of the Canopy design system (UX revamp, Phase 2). Plain, small, no dependency. Every interactive one has a 44 px target and a visible focus ring (canopy.css).
export function Button({ variant = 'secondary', className = '', type = 'button', ...rest }) {
  return <button type={type} className={`cy-btn ${variant === 'primary' ? 'cy-btn-primary' : variant === 'quiet' ? 'cy-btn-quiet' : ''} ${className}`} {...rest} />
}

export function Card({ as: Tag = 'section', className = '', ...rest }) {
  return <Tag className={`cy-card ${className}`} {...rest} />
}

// tone: neutral | ok | warn | danger | info (always with words, never colour alone)
export function Chip({ tone = 'neutral', icon = null, children, className = '' }) {
  return (
    <span className={`cy-chip ${tone === 'neutral' ? '' : `is-${tone}`} ${className}`}>
      {icon && <Icon name={icon} size={14} />}
      {children}
    </span>
  )
}

// items = [{id, label, icon?}], value = id. Arrow keys move, Home / End jump (the WAI-ARIA tabs pattern). The highlight is one element that slides under the active tab (CSS transition).
export function Tabs({ items, value, onChange, label, className = '', tourId }) {
  const refs = useRef({})
  const [hl, setHl] = useState({ left: 0, width: 0 })
  const measure = () => {
    const el = refs.current[value]
    if (el) setHl({ left: el.offsetLeft, width: el.offsetWidth })
  }
  useLayoutEffect(measure, [value, items.length])
  useEffect(() => {
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  })
  const move = (i) => {
    const n = items[(i + items.length) % items.length]
    onChange(n.id)
    refs.current[n.id]?.focus()
  }
  return (
    <div className={`cy-tabs-slide ${className}`} role="tablist" aria-label={label} data-tour={tourId}>
      <span className="cy-tab-hl" style={{ left: hl.left, width: hl.width }} aria-hidden="true" />
      {items.map((it, i) => (
        <button
          key={it.id}
          ref={(el) => (refs.current[it.id] = el)}
          type="button"
          role="tab"
          className="cy-tab"
          aria-selected={value === it.id}
          tabIndex={value === it.id ? 0 : -1}
          onClick={() => onChange(it.id)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') { e.preventDefault(); move(i + 1) }
            else if (e.key === 'ArrowLeft') { e.preventDefault(); move(i - 1) }
            else if (e.key === 'Home') { e.preventDefault(); move(0) }
            else if (e.key === 'End') { e.preventDefault(); move(items.length - 1) }
          }}
        >
          {it.icon}
          <span className="cy-tab-label">{it.label}</span>
        </button>
      ))}
    </div>
  )
}

export function IconButton({ label, className = '', type = 'button', children, ...rest }) {
  return (
    <button type={type} className={`cy-iconbtn ${className}`} aria-label={label} title={label} {...rest}>
      {children}
    </button>
  )
}

// A small label in tiny letter-spaced capitals; items are separated by dots.
export function Eyebrow({ items }) {
  return (
    <span className="cy-eyebrow">
      {items.flatMap((x, i) => (i === 0 ? [<span key={x}>{x}</span>] : [<i key={`d${i}`} aria-hidden="true" />, <span key={x}>{x}</span>]))}
    </span>
  )
}

export function Badge({ children }) {
  return <span className="cy-badge">{children}</span>
}

// A panel on the edge of the screen. side 'right' (a bottom sheet on a phone).
export function Drawer({ label, children, className = '' }) {
  return (
    <aside className={`cy-drawer is-right ${className}`} aria-label={label}>
      {children}
    </aside>
  )
}

export function Skeleton({ width = '100%', height = 14, className = '', style }) {
  return <span className={`cy-skeleton ${className}`} style={{ width, height, ...style }} aria-hidden="true" />
}

// A friendly empty or error state: an icon, a short title, one sentence, and an optional action (for example Retry).
export function EmptyState({ icon = 'info', title, text, action = null, tone = 'neutral', role }) {
  return (
    <div className={`cy-empty ${tone === 'error' ? 'is-error' : ''}`} role={role ?? (tone === 'error' ? 'alert' : undefined)}>
      <span className="cy-empty-icon">
        <Icon name={icon} size={22} />
      </span>
      <h3>{title}</h3>
      {text && <p>{text}</p>}
      {action}
    </div>
  )
}

// A hint shown on hover AND on keyboard focus of the child (the child must be focusable).
export function Tooltip({ text, children }) {
  return (
    <span className="cy-tip">
      {children}
      <span className="cy-tip-box" role="tooltip">
        {text}
      </span>
    </span>
  )
}

// On a phone, a panel that slides up from the bottom. Escape and the scrim close it.
export function BottomSheet({ open, onClose, label, children }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <>
      <div className="cy-sheet-scrim" onClick={onClose} aria-hidden="true" />
      <div className="cy-sheet" role="dialog" aria-modal="true" aria-label={label}>
        <div className="cy-sheet-grip" aria-hidden="true" />
        {children}
      </div>
    </>
  )
}
