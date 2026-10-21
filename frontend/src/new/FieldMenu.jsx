import { useEffect, useRef } from 'react'
import Icon from './Icon.jsx'
import VerifyBar from './VerifyBar.jsx'
import { tr, useLang } from './i18n.js'

// The field-check menu of the map (UX 13): opens where the person right-clicked (or long-pressed on a phone) a planting square, or from the "Open field check" button of the point panel.
// It holds the same VerifyBar as before (same buttons, same saving, same words); only its place changed. On a narrow screen it is a sheet at the bottom.
const WIDTH = 340

export default function FieldMenu({ x, y, pointId, title, lines = [], api, observer, onObserver, onSaved, block, onSeeSpecies, onClose }) {
  const lang = useLang()
  const openedAt = useRef(0) // the click that a long press leaves behind must not close the menu that it just opened
  useEffect(() => {
    openedAt.current = Date.now()
  }, [])
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  const vw = typeof window === 'undefined' ? 1280 : window.innerWidth
  const vh = typeof window === 'undefined' ? 800 : window.innerHeight
  const narrow = vw < 600 || x == null
  const style = narrow
    ? undefined
    : { left: Math.max(8, Math.min(x + 8, vw - WIDTH - 8)), top: Math.max(8, Math.min(y + 8, vh - 420)), width: WIDTH }
  return (
    <>
      <div className="nw-fmenu-backdrop" onClick={() => Date.now() - openedAt.current > 700 && onClose()} aria-hidden="true" />
      <div className={`nw-fmenu ${narrow ? 'is-sheet' : ''}`} style={style} role="dialog" aria-label={`Field check: ${title}`}>
        <div className="nw-fmenu-head">
          <strong>{title}</strong>
          <button type="button" className="nw-btn nw-btn-small" onClick={onClose}>
            <Icon name="close" /> Close<span className="sr-only"> (Escape)</span>
          </button>
        </div>
        <div className="nw-fmenu-where" data-role="menu-where">
          {lines.map((l) => (
            <div key={l}>{l}</div>
          ))}
        </div>
        <div className="nw-fmenu-actions">
          <button type="button" className="nw-btn nw-btn-small nw-btn-go" onClick={onSeeSpecies} data-role="see-species">
            <Icon name="tree" size={14} /> {tr('menu.seeSpecies', {}, lang)}
          </button>
        </div>
        <VerifyBar key={`${pointId}|${block?.planId ?? ''}`} pointId={pointId} api={api} observer={observer} onObserver={onObserver} onSaved={onSaved} block={block} />
      </div>
    </>
  )
}
