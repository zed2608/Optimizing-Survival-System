// Plain-language wording for the new dashboard. Anything not listed falls back to a readable version of its code name.

export const PURPOSES = [
  { value: 'urban', label: 'Urban greening', help: 'Streets, parks and public spaces: shade, safe roots, low maintenance.' },
  { value: 'planting', label: 'Tree planting and restoration', help: 'Planting events: conservation, livelihood value, easy establishment.' },
  { value: 'watershed', label: 'Watershed and landscape protection', help: 'Slopes and waterways: soil holding, slope and riparian tolerance.' },
]

export function purposeLabel(value) {
  return PURPOSES.find((p) => p.value === value)?.label ?? value
}

export function humanize(code) {
  const s = String(code ?? '').replace(/[_-]+/g, ' ').trim()
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''
}

export const TERM_LABEL = {
  elevation: 'Elevation',
  slope: 'Slope',
  soil: 'Soil texture',
  wetness: 'Wetness (waterlogging near creeks and rivers)',
}

export const CRITERION_LABEL = {
  intended_use_fit: 'Fits the intended use',
  shade_provision: 'Shade',
  infrastructure_safety: 'Safe near buildings and pavements',
  storm_safety: 'Storm (typhoon) safety',
  low_maintenance: 'Low maintenance',
  native_biodiversity_value: 'Native biodiversity value',
  conservation_value: 'Conservation value',
  livelihood_value: 'Livelihood value',
  establishment_ease: 'Easy to establish',
  growth_speed: 'Growth speed',
  soil_improvement_nurse: 'Soil improvement (nitrogen fixing)',
  soil_binding: 'Holds the soil',
  steep_slope_tolerance: 'Tolerates steep slopes',
  riparian_tolerance: 'Tolerates wet ground by waterways',
  cover_interception: 'Canopy cover',
  soil_improvement: 'Soil improvement (nitrogen fixing)',
  slope_failure_resistance: 'Resists storm damage on slopes',
}

export const PART_LABEL = {
  urban_tags: 'Matches the planting purpose',
  canopy_spread_m: 'Canopy spread',
  growth_rate: 'Growth rate',
  foliage: 'Leaf cover through the year',
  root_urban_safety_prov: 'Root safety near buildings (provisional)',
  root_soil_binding_prov: 'Root soil holding (provisional)',
  planting_difficulty: 'Infrastructure risk noted',
  mature_height_m: 'Mature height (shorter is safer)',
  typhoon_res: 'Typhoon resistance',
  timber_density: 'Wood density',
  drought_tol: 'Drought tolerance',
  problem_tags: 'Pest and disease problems',
  care_tags: 'Extra care needed',
  origin: 'Native species',
  endangered: 'Conservation status',
  common_uses: 'Useful products',
  is_high_value_crop: 'High-value crop',
  propagation_method: 'Easy propagation',
  germination_days: 'Germination time (shorter is easier)',
  dry_season_months: 'Dry season tolerated',
  n_fixing: 'Fixes nitrogen',
  max_slope_pct: 'Steepest slope tolerated',
  waterlog_tol: 'Waterlogging tolerance',
  native_habitat: 'Grows by rivers or streams',
}

// Flags in words for non-specialists. `help` is the longer explanation.
export const FLAG_TEXT = {
  soil_unverified_mismatch: {
    label: 'Soil match not yet verified',
    help: 'The soil texture here does not match the species list, but the soil map is still unverified, so the score is lowered instead of ruling the species out.',
  },
  species_data_unverified: {
    label: 'Species data not fully verified',
    help: 'Some values for this species cite a source file that was not provided.',
  },
  low_confidence: {
    label: 'Some inputs missing',
    help: 'Some inputs for this place or species were missing, so the score is less certain.',
  },
  needs_both_sexes: {
    label: 'Plant male and female trees',
    help: 'Separate male and female trees are needed for fruit or seed.',
  },
}

export function flagInfo(flag) {
  if (FLAG_TEXT[flag]) return FLAG_TEXT[flag]
  if (flag.startsWith('gate_failed:')) {
    const term = flag.slice('gate_failed:'.length)
    return { label: `Outside the species' limit: ${(TERM_LABEL[term] ?? humanize(term)).toLowerCase()}`, help: 'A hard limit of the species is exceeded here, so the score is 0.' }
  }
  return { label: humanize(flag), help: '' }
}

export const RANK_MEANING = {
  1: 'Rank 1: government agency (DENR, DA, DOST-PCAARRD)',
  2: 'Rank 2: local academic or botanical source',
  3: 'Rank 3: international reference',
  4: 'Rank 4: unranked source or mirror site',
}

export const DIRECTION = { N: 'north', NE: 'north-east', E: 'east', SE: 'south-east', S: 'south', SW: 'south-west', W: 'west', NW: 'north-west' }

// Words for the API's 404 answers (outside a legal zone / too far from the grid), with the numbers taken from its message.
export function friendlyNotRankable(message) {
  const far = /is (\d+) m away \(limit (\d+) m\)/.exec(message)
  if (far) {
    return {
      title: 'This spot is outside the mapped area',
      text: `The nearest grid point is ${far[1]} m away, and rankings are only given within ${far[2]} m of a grid point. Click closer to San Mateo's mapped land.`,
    }
  }
  const zone = /not in a legal planting zone \((.*?)\)/.exec(message)
  if (zone) {
    const outside = /outside the zoning map/i.test(zone[1])
    return {
      title: 'This spot is not in a planting zone',
      text: outside
        ? 'The nearest grid point lies outside the zoning map, so it is not in one of the legal planting zones and no ranking is given.'
        : `The nearest grid point is in “${zone[1]}”, which is not one of the legal planting zones, so no ranking is given.`,
    }
  }
  return { title: 'No ranking for this spot', text: message }
}
