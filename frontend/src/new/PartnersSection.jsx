import { useApi } from '../v2/useApi.js'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import HelpTip from './HelpTip.jsx'
import Icon from './Icon.jsx'
import SeasonBadge from './SeasonBadge.jsx'

// The species card section "Works well with": up to 3 partners with one line of reason each, the badge "named in the sources", the verbatim dataset text ("Sources say: ...")
// and a "None found" state. These are starting rules from the species data (provisional): the tip says so.
export default function PartnersSection({ speciesId, query = '' }) {
  const api = useApi(`/species/${speciesId}/partners?${query}`)
  const d = api.status === 'ok' ? api.data : null
  return (
    <section className="nw-card-sec" aria-label="Works well with">
      <div className="nw-pcard-head">
        <h3>Works well with</h3>
        <HelpTip label="About partner species">These are starting rules from the species data. The agriculturist will check them.</HelpTip>
      </div>
      {api.status === 'loading' && <Loading what="Looking for partner species" />}
      {api.status === 'error' && (api.error.status === 503 ? <p className="nw-plain">The partner rules are not built yet.</p> : <ErrorBox error={api.error} onRetry={api.retry} title="Could not load the partner species" brief />)}
      {d && d.partners.length === 0 && (
        <p className="nw-plain" role="status">
          <Icon name="dash" size={14} /> None found. {d.message}.
        </p>
      )}
      {d && (
        <ul className="nw-partners">
          {d.partners.slice(0, 3).map((p) => (
            <li key={p.species_id}>
              <div className="nw-partner-name">
                <strong>{p.common_name}</strong>
                {p.source_named && (
                  <span className="nw-chip nw-chip-named">
                    <Icon name="check" size={12} /> named in the sources
                  </span>
                )}
                <SeasonBadge season={p.season} strip={false} best={false} />
              </div>
              <div className="nw-partner-why">{p.reasons[0]}</div>
            </li>
          ))}
        </ul>
      )}
      {d && d.sources_say && <p className="nw-plain nw-sourcesay">Sources say: {d.sources_say}</p>}
    </section>
  )
}
