import SourceLink from '../v2/components/SourceLink.jsx'
import { getLang, tr } from './i18n.js'

// A list of sources from a sources map (id -> source). Several fields often cite the same page: each page (and rank) is shown once.
// Nothing found for the ids -> Data Unavailable.
export default function SourceGroup({ title, ids, map }) {
  const found = (ids ?? []).map((id) => map?.[String(id)]).filter((s) => s && s.url)
  const unique = [...new Map(found.map((s) => [`${s.url}|${s.rank}`, s])).values()]
  return (
    <div>
      <h4>{title}</h4>
      {unique.length === 0 ? (
        <span className="unavailable">{tr('x.noSourceDs', {}, getLang())}</span>
      ) : (
        <ul className="plain-list">
          {unique.map((s) => (
            <li key={`${s.url}|${s.rank}`}>
              <SourceLink source={s} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
