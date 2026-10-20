// UX 12: "Isang species lang ba o marami?" Pure helpers (tested in companions.test.mjs). The companions come from the service (POST /companions): species suitable on the same squares as the main one.
export const ASK = 'Isang species lang ba o marami?'
export const COMPANION_NOTE = 'Batay lang ito sa parehong angkop na lugar. Hindi pa kasama ang laki ng canopy, ugat o lilim.'

// the species ids that go to the plan: the main species first, then the companions the person ticked (no repeats, never a companion without a main)
export function chosenIds(mainId, companionIds) {
  if (mainId == null) return []
  return [mainId, ...[...new Set(companionIds)].filter((i) => i !== mainId)]
}

// body of POST /companions: the area chosen in step 4 (barangay, zone or drawn shape) or none (the whole municipality)
export function companionBody(purpose, mainId, area) {
  if (mainId == null) return null
  const base = { species_id: mainId, purpose }
  if (!area) return base
  if (area.kind === 'barangay') return { ...base, barangay: area.name }
  if (area.kind === 'zone') return { ...base, zone: area.name }
  if (area.kind === 'polygon') return { ...base, polygon: area.geometry }
  return base
}

// a short sentence for the list: how much of the main species' land the companion also suits
export function overlapText(share) {
  return `angkop din sa ${Math.round(share * 100)}% ng lugar na angkop sa pangunahing species`
}
