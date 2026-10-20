import { useState } from 'react'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import SpeciesMultiPicker from './SpeciesMultiPicker.jsx'
import { ASK, COMPANION_NOTE, chosenIds, companionBody, overlapText } from './companions.js'
import { usePost } from './usePost.js'

// UX 12: first ask "Isang species lang ba o marami?". One species: the usual list, one choice. Many: choose the MAIN species, then tick "Puwedeng samahan" (species that are suitable on the same
// squares of the chosen area, or of the whole municipality when no area is chosen). The note says plainly that this is about the land only.
export default function SpeciesChooser({ species, selected, onChange, onlySeason, onInfo, purpose, area, query, how, onHow, mainId, onMain }) {
  const [more, setMore] = useState(false)
  const body = how === 'many' ? companionBody(purpose, mainId, area) : null
  const comp = usePost(`/companions?${query}`, body)
  const companionIds = selected.filter((i) => i !== mainId)

  if (!how) {
    return (
      <div className="nw-ask" role="group" aria-label={ASK}>
        <p className="nw-label">{ASK}</p>
        <div className="nw-row">
          <button type="button" className="nw-btn nw-btn-go" onClick={() => onHow('one')}>
            Isang species lang
          </button>
          <button type="button" className="nw-btn nw-btn-go" onClick={() => onHow('many')}>
            Marami
          </button>
        </div>
      </div>
    )
  }
  const back = (
    <button
      type="button"
      className="nw-linkbtn"
      onClick={() => {
        onHow('')
        onMain(null)
        onChange([])
      }}
    >
      Palitan: isa o marami?
    </button>
  )
  if (how === 'one') {
    return (
      <div>
        <p className="nw-hint">Isang species lang. {back}</p>
        <SpeciesMultiPicker species={species} selected={selected} onChange={(ids) => onChange(ids.slice(-1))} onlySeason={onlySeason} onInfo={onInfo} single />
      </div>
    )
  }
  return (
    <div>
      <p className="nw-hint">Marami. {back}</p>
      <p className="nw-label">1. Pumili ng PANGUNAHING species</p>
      <SpeciesMultiPicker
        species={species}
        selected={mainId == null ? [] : [mainId]}
        onChange={(ids) => {
          const id = ids.slice(-1)[0] ?? null
          onMain(id)
          onChange(chosenIds(id, []))
        }}
        onlySeason={onlySeason}
        onInfo={onInfo}
        single
      />
      {mainId != null && (
        <section className="nw-companions" aria-label="Puwedeng samahan" data-role="companions">
          <p className="nw-label">2. Puwedeng samahan</p>
          <p className="nw-hint" data-role="companion-note">
            {COMPANION_NOTE}
          </p>
          {comp.status === 'loading' && <Loading what="Hinahanap ang mga species na angkop sa parehong lugar" />}
          {comp.status === 'error' && <ErrorBox error={comp.error} onRetry={comp.retry} title="Hindi makuha ang mga puwedeng samahan" brief />}
          {comp.status === 'ok' && comp.data.companions.length === 0 && (
            <p className="nw-hint">Walang ibang species na angkop sa kalahati o higit pa ng lugar na angkop sa pangunahing species.</p>
          )}
          {comp.status === 'ok' && comp.data.companions.length > 0 && (
            <>
              <p className="nw-hint">
                {comp.data.area.display_name}: {comp.data.n_companions} ang puwede (hanggang {comp.data.companions.length} ang ipinapakita).
              </p>
              <div className="nw-checklist" role="group" aria-label="Puwedeng samahan">
                {comp.data.companions.map((c) => (
                  <label key={c.species_id} className="nw-check nw-check-sp">
                    <input
                      type="checkbox"
                      checked={companionIds.includes(c.species_id)}
                      onChange={() => onChange(chosenIds(mainId, companionIds.includes(c.species_id) ? companionIds.filter((i) => i !== c.species_id) : [...companionIds, c.species_id]))}
                    />
                    <span className="nw-check-main">
                      <span className="nw-check-line">
                        <span>{c.common_name}</span>
                        <button
                          type="button"
                          className="nw-infobtn"
                          aria-label={`About ${c.common_name}`}
                          onClick={(e) => {
                            e.preventDefault()
                            onInfo(c.species_id)
                          }}
                        >
                          i
                        </button>
                      </span>
                      <span className="nw-hint">{overlapText(c.share_of_main_squares)}</span>
                    </span>
                  </label>
                ))}
              </div>
            </>
          )}
          <button type="button" className="nw-linkbtn" onClick={() => setMore((m) => !m)} aria-expanded={more}>
            {more ? 'Itago ang buong listahan' : 'Magdagdag ng iba pang species mula sa buong listahan'}
          </button>
          {more && (
            <SpeciesMultiPicker
              species={species}
              selected={selected}
              onChange={(ids) => onChange(chosenIds(mainId, ids.filter((i) => i !== mainId)))}
              onlySeason={onlySeason}
              onInfo={onInfo}
            />
          )}
        </section>
      )}
    </div>
  )
}
