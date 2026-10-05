import { useId, useState } from 'react'

// A small "?" button that opens a short explanation under it. Keyboard: Tab to it, Enter or Space opens it, Escape closes it. The explanation is a
// role="note" paragraph, so it is read out when opened. Returns two siblings (button + note): put it in a flex row that can wrap.
export default function HelpTip({ label, children }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        className="nw-tip-btn"
        aria-label={`Help: ${label}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setOpen(false)
        }}
        onBlur={() => setOpen(false)}
      >
        ?
      </button>
      {open && (
        <div id={id} role="note" className="nw-tip-body">
          {children}
        </div>
      )}
    </>
  )
}
