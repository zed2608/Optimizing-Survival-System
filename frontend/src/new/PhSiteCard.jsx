import { useId, useState } from 'react'
import { useApi } from '../v2/useApi.js'
import { phFitCounts, phFitText, parsePhInput, sitePhText, PH_TEXT } from './phEvidence.js'

// The pH of the place on screen (UX round 2, B4): the SoilGrids estimate of the clicked square or of the area, said as an estimate, and a small "Sukat sa lugar" box: type the pH you measured and see how
// many of the listed species have it inside their range. Display only: no score, no order and nothing saved. scope = 'square' | 'area'; speciesIds = the species of the list on screen.
export default function PhSiteCard({ ph, scope = 'square', speciesIds = [] }) {
  const id = useId()
  const [text, setText] = useState('')
  const evidence = useApi('/species-ph-reference')
  const value = parsePhInput(text)
  const all = evidence.status === 'ok' && evidence.data?.available ? evidence.data.species : null
  return (
    <section className="nw-pcard nw-phsite" aria-label="pH ng lupa" data-role="ph-site" data-scope={scope}>
      <div className="nw-pcard-head">
        <h3>pH ng lupa</h3>
      </div>
      <p className="nw-plain" data-role="ph-site-text">
        {sitePhText(ph, scope)}
      </p>
      <p className="muted">Hindi ito kasama sa score o sa pagkakasunod-sunod.</p>
      <div className="nw-ph-tool" data-role="ph-site-tool">
        <label htmlFor={id}>
          <strong>{PH_TEXT.toolTitle.fil}</strong>
        </label>
        <div className="nw-ph-tool-row">
          <input id={id} type="text" inputMode="decimal" autoComplete="off" value={text} onChange={(e) => setText(e.target.value)} placeholder="6.5" aria-label={PH_TEXT.toolLabel.fil} />
          <button type="button" className="btn btn-small" onClick={() => setText('')} disabled={text.trim() === ''}>
            {PH_TEXT.toolReset.fil}
          </button>
        </div>
        <div className="muted">{PH_TEXT.toolNote.fil}</div>
        {text.trim() !== '' && value === null && (
          <div className="nw-ph-tool-bad" role="alert">
            {PH_TEXT.toolBad.fil}
          </div>
        )}
        {value !== null && ph && (
          <div className="nw-plain" data-role="ph-site-vs-model">
            {value >= ph.q05 && value <= ph.q95
              ? 'Ang sukat mo ay nasa loob ng tantiya ng modelo.'
              : 'Ang sukat mo ay labas sa tantiya ng modelo. Ang sukat sa mismong lugar ang gamitin; tantiya lang ang modelo.'}
          </div>
        )}
        {value !== null && all && speciesIds.length > 0 && (
          <div className="nw-plain" data-role="ph-site-fit">
            {phFitText(phFitCounts(value, speciesIds, all))}
          </div>
        )}
      </div>
    </section>
  )
}
