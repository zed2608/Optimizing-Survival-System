import { useId, useState } from 'react'
import { useApi } from '../v2/useApi.js'
import { phFitCounts, phFitText, parsePhInput, sitePhText } from './phEvidence.js'
import { tr, useLang } from './i18n.js'

// The pH of the place on screen (UX round 2, B4): the SoilGrids estimate of the clicked square or of the area, said as an estimate, and a small "Sukat sa lugar" box: type the pH you measured and see how
// many of the listed species have it inside their range. Display only: no score, no order and nothing saved. scope = 'square' | 'area'; speciesIds = the species of the list on screen.
export default function PhSiteCard({ ph, scope = 'square', speciesIds = [] }) {
  const id = useId()
  const lang = useLang()
  const t = (k, p) => tr(k, p, lang)
  const [text, setText] = useState('')
  const evidence = useApi('/species-ph-reference')
  const value = parsePhInput(text)
  const all = evidence.status === 'ok' && evidence.data?.available ? evidence.data.species : null
  return (
    <section className="nw-pcard nw-phsite" aria-label={t('ph.title')} data-role="ph-site" data-scope={scope}>
      <div className="nw-pcard-head">
        <h3>{t('ph.title')}</h3>
      </div>
      <p className="nw-plain" data-role="ph-site-text">
        {sitePhText(ph, scope, lang)}
      </p>
      <p className="muted">{t('ph.notScored')}</p>
      <details className="nw-ph-tool" data-role="ph-site-tool">
        <summary data-role="ph-tool-link">{t('ph.tool')}</summary>
        <label htmlFor={id} className="sr-only">
          {t('ph.toolLabel')}
        </label>
        <div className="nw-ph-tool-row">
          <input id={id} type="text" inputMode="decimal" autoComplete="off" value={text} onChange={(e) => setText(e.target.value)} placeholder="6.5" aria-label={t('ph.toolLabel')} />
          <button type="button" className="btn btn-small" onClick={() => setText('')} disabled={text.trim() === ''}>
            {t('ph.toolReset')}
          </button>
        </div>
        <div className="muted">{t('ph.toolNote')}</div>
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
      </details>
    </section>
  )
}
