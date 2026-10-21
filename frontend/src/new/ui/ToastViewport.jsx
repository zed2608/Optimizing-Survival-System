import { AnimatePresence, motion } from 'motion/react'
import Icon from '../Icon.jsx'
import { dismissToast, useToasts } from './toast.js'
import { motionAllowed } from '../motionPref.js'
import { tr, useLang } from '../i18n.js'

const ICON = { success: 'check', info: 'info', warning: 'warn', error: 'close' }

// Toasts slide in and out, and can be swiped sideways to dismiss. With motion off they simply appear and disappear.
export default function ToastViewport() {
  const items = useToasts()
  const lang = useLang()
  const ok = motionAllowed()
  return (
    <div className="cy-toasts" aria-live="polite" aria-atomic="false" data-role="toasts">
      <AnimatePresence initial={false}>
        {items.map((t) => (
          <motion.div
            key={t.id}
            layout={ok}
            className={`cy-toast is-${t.kind}`}
            role={t.kind === 'error' ? 'alert' : 'status'}
            initial={ok ? { opacity: 0, x: 60 } : false}
            animate={{ opacity: 1, x: 0 }}
            exit={ok ? { opacity: 0, x: 80 } : { opacity: 0 }}
            transition={ok ? { type: 'spring', stiffness: 320, damping: 28 } : { duration: 0 }}
            drag={ok ? 'x' : false}
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.5}
            onDragEnd={(_, info) => Math.abs(info.offset.x) > 80 && dismissToast(t.id)}
          >
            <Icon name={ICON[t.kind]} size={18} />
            <div className="cy-toast-text">{t.text}</div>
            <button type="button" className="cy-toast-x" aria-label={tr('toast.close', {}, lang)} onClick={() => dismissToast(t.id)}>
              <Icon name="close" size={16} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
