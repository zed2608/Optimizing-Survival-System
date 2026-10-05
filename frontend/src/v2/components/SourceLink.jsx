import { RANK_MEANING } from '../labels.js'

function hostName(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}

// One source: its name (the website), a small rank badge and a link that opens in a new tab.
// No source (or no URL) -> "Data Unavailable". File citations (not a web address) are shown as text.
export default function SourceLink({ source }) {
  if (!source || !source.url) return <span className="unavailable">Data Unavailable</span>
  const rank = Number(source.rank)
  const hasRank = Number.isFinite(rank) && rank >= 1
  const isWeb = /^https?:\/\//i.test(source.url)
  const name = isWeb ? hostName(source.url) ?? source.url : source.url
  const fileMissing = String(source.flags ?? '').includes('file_source_not_provided')
  return (
    <span className="source">
      {isWeb ? (
        <a href={source.url} target="_blank" rel="noopener noreferrer" title={source.url}>
          {name}
          <span className="sr-only"> (opens in a new tab)</span>
        </a>
      ) : (
        <span title="A file, not a web page">{name} (file{fileMissing ? ' not provided' : ''})</span>
      )}{' '}
      <span className={`rank-badge ${hasRank ? '' : 'rank-none'}`} title={hasRank ? RANK_MEANING[rank] ?? `Rank ${rank}` : 'This source has no rank'}>
        {hasRank ? `Rank ${rank}` : 'Not ranked'}
      </span>
      {source.rank_basis === 'assigned_confirm' && <span className="note"> rank still to be confirmed</span>}
      {source.off_list === true && <span className="note"> not on the project source list</span>}
    </span>
  )
}
