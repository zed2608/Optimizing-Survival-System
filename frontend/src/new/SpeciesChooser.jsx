import { tr, useLang } from './i18n.js'
import { useState } from 'react'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import SpeciesMultiPicker from './SpeciesMultiPicker.jsx'
import { chosenIds, companionBody, overlapText } from './companions.js'
import { usePost } from './usePost.js'

// UX 12: first ask "Isang species lang ba o marami?". One species: the usual list, one choice. Many: choose the MAIN species, then tick "Puwedeng samahan" (species that are suitable on the same
// squares of the chosen area, or of the whole municipality when no area is chosen). The note says plainly that this is about the land only.
export default function SpeciesChooser({ species, selected, onChange, onlySeason, onInfo, purpose, area, query, how, onHow, mainId, onMain }) {
  const [more, setMore] = useState(false)
  const lang = useLang()
  const t = (k, p) => tr(k, p, lang)
  const body = how === 'many' ? companionBody(purpose, mainId, area) : null
  const comp = usePost(`/companions?${query}`, body)
  const companionIds = selected.filter((i) => i !== mainId)

  if (!how) {
    return (
      <div className="nw-ask" role="group" aria-label={t('sc.ask')}>
        <p className="nw-label">{t('sc.ask')}</p>
        <div className="nw-row">
          <button type="button" className="nw-btn nw-btn-go" onClick={() => onHow('one')}>
            {t('sc.one')}
          </button>
          <button type="button" className="nw-btn nw-btn-go" onClick={() => onHow('many')}>
            {t('sc.many')}
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
      {t('sc.change')}
    </button>
  )
  if (how === 'one') {
    return (
      <div>
        <p className="nw-hint">{t('sc.oneNote')} {back}</p>
        <SpeciesMultiPicker species={species} selected={selected} onChange={(ids) => onChange(ids.slice(-1))} onlySeason={onlySeason} onInfo={onInfo} single />
      </div>
    )
  }
  return (
    <div>
      <p className="nw-hint">{t('sc.manyNote')} {back}</p>
      <p className="nw-label">{t('sc.main')}</p>
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
        <section className="nw-companions" aria-label={t('sc.comp')} data-role="companions">
          <p className="nw-label">{t('sc.comp')}</p>
          <p className="nw-hint" data-role="companion-note">
            {t('sc.note')}
          </p>
          {comp.status === 'loading' && <Loading what={t('sc.load')} />}
          {comp.status === 'error' && <ErrorBox error={comp.error} onRetry={comp.retry} title={t('sc.err')} brief />}
          {comp.status === 'ok' && comp.data.companions.length === 0 && (
            <p className="nw-hint">{t('sc.nocomp')}</p>
          )}
          {comp.status === 'ok' && comp.data.companions.length > 0 && (
            <>
              <p className="nw-hint">
                {t('sc.count', { name: comp.data.area.display_name, n: comp.data.n_companions, m: comp.data.companions.length })}
              </p>
              <div className="nw-checklist" role="group" aria-label={t('sc.comp')}>
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
                      <span className="nw-hint">{overlapText(c.share_of_main_squares, lang)}</span>
                    </span>
                  </label>
                ))}
              </div>
            </>
          )}
          <button type="button" className="nw-linkbtn" onClick={() => setMore((m) => !m)} aria-expanded={more}>
            {more ? t('sc.less') : t('sc.more')}
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
