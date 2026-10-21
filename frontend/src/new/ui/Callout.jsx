import Icon from '../Icon.jsx'

// THE one coloured box of the dashboard (R1 W2): info, warning, error, success and empty. Colours come only from the semantic pairs (--c-<tone>-surface, --c-on-<tone>, --c-<tone>-border),
// so it reads the same in the light and the dark theme. Tone and words decide the meaning (an icon and the title carry it too, never only the colour).
//   <Callout tone="warning" title="..." actions={<button/>}>text</Callout>
const ICON = { info: 'info', warning: 'warn', error: 'warn', success: 'check', empty: 'dot' }

export default function Callout({ tone = 'info', title, children, actions, icon, role, className = '', ...rest }) {
  const t = ICON[tone] ? tone : 'info'
  const aria = role ?? (t === 'error' ? 'alert' : 'status')
  return (
    <div className={`cy-callout is-${t} ${className}`.trim()} role={aria} {...rest}>
      <span className="cy-callout-icon" aria-hidden="true">
        <Icon name={icon ?? ICON[t]} size={16} />
      </span>
      <div className="cy-callout-body">
        {title && <strong className="cy-callout-title">{title}</strong>}
        {children && <div className="cy-callout-text">{children}</div>}
        {actions && <div className="cy-callout-actions">{actions}</div>}
      </div>
    </div>
  )
}
