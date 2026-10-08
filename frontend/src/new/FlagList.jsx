import { flagInfo } from '../v2/labels.js'
import Icon from './Icon.jsx'

// Words for the flags that were added after the first dashboard (the earlier word list in v2/labels.js is left as it was).
const EXTRA = {
  zoning_unconfirmed: { label: 'Land outside our zoning map', help: 'Outside our zoning map. The CLUP 2021-2031 shows this land as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting.', icon: 'dotring' },
  soil_provisional: { label: 'Soil: LGU map, provisional', help: 'Soil from the LGU soil map, digitized by us: provisional, not yet verified by the agriculturist.', icon: 'layers' },
  ground_bare: { label: 'Looks bare in satellite land cover', help: 'Satellite land cover (2021) looks bare: check on the ground before planting.', icon: 'mountain' },
  ground_built_up: { label: 'Looks built-up in satellite land cover', help: 'Satellite land cover (2021) looks built-up: check on the ground before planting.', icon: 'building' },
  rehab_site_food_warning: { label: 'Produce may hold heavy metals', help: 'Fruit or produce from a landfill or mining site may hold heavy metals; do not plan to eat or sell it without testing.', icon: 'warn' },
  habagat_washout: { label: 'Habagat washout risk (Jul-Sep)', help: 'Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep. The site match is multiplied by 0.8 (MAO, 7 Oct 2026, provisional).', icon: 'rain' },
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
