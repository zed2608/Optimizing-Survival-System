import { flagInfo } from '../v2/labels.js'
import Icon from './Icon.jsx'

// Words for the flags that were added after the first dashboard (the earlier word list in v2/labels.js is left as it was).
const EXTRA = {
  zoning_unconfirmed: { label: 'Land outside the zoning map', help: 'Zoning not confirmed: check with the LGU before planting.', icon: 'dotring' },
  ground_bare: { label: 'Looks bare in satellite land cover', help: 'Satellite land cover (2021) looks bare: check on the ground before planting.', icon: 'mountain' },
  ground_built_up: { label: 'Looks built-up in satellite land cover', help: 'Satellite land cover (2021) looks built-up: check on the ground before planting.', icon: 'building' },
  ground_water: { label: 'Looks like water in satellite land cover', help: 'Satellite land cover (2021) looks like water or wetland: check on the ground before planting.', icon: 'drop' },
}

// Flags as small badges with plain words (the longer explanation is in the tooltip).
export default function FlagList({ flags }) {
  if (!flags || flags.length === 0) return null
  return (
    <ul className="flags" aria-label="Notes about this result">
      {flags.map((f) => {
        const info = EXTRA[f] ?? flagInfo(f)
        return (
          <li key={f} className="flag" title={info.help}>
            <Icon name={info.icon ?? 'flag'} size={14} /> 
            {info.label}
          </li>
        )
      })}
    </ul>
  )
}
