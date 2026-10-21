import { useId, useState } from 'react'
import Icon from './Icon.jsx'
import { areaPhText, phExplain } from './phEvidence.js'
import { useLang } from './i18n.js'

// The pH verdict of one species as a small chip (display only). Tap, click, Enter or hover explains it with the numbers: the estimate and its uncertainty against the species range.
// site = {mean, q05, q95} | null, ranges = GET /species-ph-reference .species (or null while it loads).
export default function PhChip({ verdict, speciesId, site, ranges, icon = false }) {
  const lang = useLang()
  const id = useId()
  const [open, setOpen] = useState(false)
  const label = areaPhText(verdict, lang)
  if (!label) return null
  const ref = ranges?.[String(speciesId)]
  const range = ref && ref.verdict_min != null && ref.verdict_max != null ? { min: ref.verdict_min, max: ref.verdict_max } : null
  const why = phExplain(verdict, site, range, lang)
  return (
    <div className="nw-phchip-wrap" data-role="row-ph" data-verdict={verdict}>
      {icon ? (
        <button type="button" className={`cy-rowicon is-ph-${verdict}`} aria-expanded={open} aria-controls={id} aria-label={label} title={`${label}. ${why}`} onClick={() => setOpen((v) => !v)} data-role="ph-icon">
          <Icon name="drop" size={16} />
        </button>
      ) : (
        <button type="button" className={`nw-phchip is-${verdict}`} aria-expanded={open} aria-controls={id} title={why} onClick={() => setOpen((v) => !v)}>
          {label}
        </button>
      )}
      {open && (
        <p className="nw-phchip-why muted" id={id} role="note" data-role="ph-why">
          {why}
        </p>
      )}
    </div>
  )
}
