import Icon from '../Icon.jsx'
import { dismissToast, useToasts } from './toast.js'
import { tr, useLang } from '../i18n.js'

const ICON = { success: 'check', info: 'info', warning: 'warn', error: 'close' }

export default function ToastViewport() {
  const items = useToasts()
  const lang = useLang()
  return (
    <div className="cy-toasts" aria-live="polite" aria-atomic="false" data-role="toasts">
      {items.map((t) => (
        <div key={t.id} className={`cy-toast is-${t.kind}`} role={t.kind === 'error' ? 'alert' : 'status'}>
          <Icon name={ICON[t.kind]} size={18} />
          <div className="cy-toast-text">{t.text}</div>
          <button type="button" className="cy-toast-x" aria-label={tr('toast.close', {}, lang)} onClick={() => dismissToast(t.id)}>
            <Icon name="close" size={16} />
          </button>
        </div>
      ))}
    </div>
  )
}
