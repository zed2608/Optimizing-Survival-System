import { useId, useState } from 'react'
import { useApi } from '../v2/useApi.js'
import { phFitCounts, phFitText, parsePhInput, phLineText } from './phEvidence.js'
import { tr, useLang } from './i18n.js'

// The soil pH of the place on screen as ONE compact line (UX revamp, Phase 0 B): the SoilGrids estimate with its range, said as an estimate that was not measured in San Mateo, and a small
// "Measure on site" link that opens a box: type the pH you measured and see how many of the listed species have it inside their range. Display only: no score, no order and nothing saved.
// scope = 'square' | 'area'; speciesIds = the species of the list on screen.
export default function PhSiteCard({ ph, scope = 'square', speciesIds = [] }) {
  const id = useId()
  const lang = useLang()
  const t = (k, p) => tr(k, p, lang)
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const evidence = useApi('/species-ph-reference')
  const value = parsePhInput(text)
  const all = evidence.status === 'ok' && evidence.data?.available ? evidence.data.species : null
  return (
    <div className="nw-phline" data-role="ph-site" data-scope={scope} data-tour={scope === 'square' ? 'r-ph' : undefined}>
      <p className="nw-plain" data-role="ph-site-text">
        {phLineText(ph, scope, lang)}{' '}
        <button type="button" className="nw-linkquiet" data-role="ph-tool-link" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
          {t('ph.measure')}
        </button>
      </p>
      {open && (
        <div className="nw-ph-tool" id={id} data-role="ph-site-tool">
          <label htmlFor={`${id}-in`}>
            <strong>{t('ph.toolLabel')}</strong>
          </label>
          <div className="nw-ph-tool-row">
            <input id={`${id}-in`} type="text" inputMode="decimal" autoComplete="off" value={text} onChange={(e) => setText(e.target.value)} placeholder="6.5" />
            <button type="button" className="btn btn-small" onClick={() => setText('')} disabled={text.trim() === ''}>
              {t('ph.toolReset')}
            </button>
          </div>
          <div className="muted">{t('ph.toolNote')}</div>
          <div className="muted">{t('ph.notScored')}</div>
          {text.trim() !== '' && value === null && (
            <div className="nw-ph-tool-bad" role="alert">
              {t('ph.toolBad')}
            </div>
          )}
          {value !== null && ph && (
            <div className="nw-plain" data-role="ph-site-vs-model">
              {value >= ph.q05 && value <= ph.q95 ? t('ph.vsInside') : t('ph.vsOutside')}
            </div>
          )}
          {value !== null && all && speciesIds.length > 0 && (
            <div className="nw-plain" data-role="ph-site-fit">
              {phFitText(phFitCounts(value, speciesIds, all), lang)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
