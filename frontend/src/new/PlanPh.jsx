import { useApi } from '../v2/useApi.js'
import { planPhLine, planPhSummary } from './phEvidence.js'

function Two({ t }) {
  return (
    <>
      {t.en}
      <span className="nw-fil">{t.fil}</span>
    </>
  )
}

// A small card of the plan result: the pH reference of each species of the plan (from the evidence file) and how many have none. Reference only: it does not change the ranking, the plan CSV or the PDF.
export default function PlanPh({ species }) {
  const api = useApi('/species-ph-reference')
  const all = api.status === 'ok' && api.data?.available ? api.data.species : null
  if (!all || !species.length) return null
  const summary = planPhSummary(species.map((s) => s.id), all)
  return (
    <section className="nw-pcard" aria-label="Soil pH of the species" data-section="plan-ph">
      <div className="nw-pcard-head">
        <h3>pH ng lupa</h3>
      </div>
      {summary && (
        <p className="nw-plain nw-ph-summary" role="status" data-role="plan-ph-summary">
          <Two t={summary.text} />
        </p>
      )}
      <ul className="plain-list nw-ph-plan">
        {species.map((s) => {
          const line = planPhLine(all[String(s.id)])
          return (
            <li key={s.id} data-ph-species={s.id} data-ph-code={line.code}>
              <strong>{s.name}</strong> · <Two t={line.text} />
            </li>
          )
        })}
      </ul>
      <p className="muted">
        Mula sa sanggunian; hindi pa pirmado ng agriculturist. Gumamit ng pH test kit o meter sa mismong lugar.
      </p>
    </section>
  )
}
