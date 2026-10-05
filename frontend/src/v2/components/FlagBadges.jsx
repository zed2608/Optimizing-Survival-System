import { flagInfo } from '../labels.js'

// Flags as small badges with plain words (the longer explanation is in the tooltip and in the explanation panel).
export default function FlagBadges({ flags }) {
  if (!flags || flags.length === 0) return null
  return (
    <ul className="flags" aria-label="Notes about this result">
      {flags.map((f) => {
        const info = flagInfo(f)
        return (
          <li key={f} className="flag" title={info.help}>
            <span aria-hidden="true">⚑ </span>
            {info.label}
          </li>
        )
      })}
    </ul>
  )
}
