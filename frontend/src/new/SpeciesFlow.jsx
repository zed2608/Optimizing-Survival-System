import Segmented from './Segmented.jsx'
import Callout from './ui/Callout.jsx'
import SpeciesChooser from './SpeciesChooser.jsx'
import UnzonedToggle from './UnzonedToggle.jsx'
import Icon from './Icon.jsx'
import { canGoNext, canJump, flowSteps } from './flowState.js'
import { tr, useLang } from './i18n.js'

// Goal "I have species", step 4 as a real stepper (UX round 4):
//   1 Choose species   2 Where to look (filter: whole San Mateo, barangay, zone)   3 Mark on the map (one point, or an area)   4 Create plan
// The stepper shows the current step, a check and a short summary on finished steps, and a finished step can be clicked to go back. Next stays off until the step is complete, with the reason in words.
// The choices live in AppNew, so they persist when the person goes back and forth. The words come from messages.js (English by default, Taglish through the header switch).

function Stepper({ steps, sub, setSub, lang }) {
  const t = (k, p) => tr(k, p, lang)
  return (
    <ol className="nw-stepper" aria-label={t('flow.stepsAria', { n: sub })} data-role="flow-steps">
      {steps.map((st) => {
        const current = st.n === sub
        const reachable = canJump(steps, st.n)
        const cls = current ? 'is-current' : st.done && st.n < sub ? 'is-done' : ''
        return (
          <li key={st.n} className={cls} aria-current={current ? 'step' : undefined}>
            <button type="button" className="nw-stepbtn" disabled={!reachable || current} onClick={() => setSub(st.n)} data-step={st.n} aria-label={`${t('flow.stepLabel', { n: st.n, title: st.title })}${st.summary ? `. ${st.summary}` : ''}`}>
              <span className="nw-flowno">{st.done && !current ? <Icon name="check" /> : st.n}</span>
              <span className="nw-steptext">
                <span className="nw-steptitle">{t(`flow.short${st.n}`)}</span>
                {st.done && !current && st.summary && <span className="nw-stepsum">{st.summary}</span>}
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}

function Nav({ steps, sub, setSub, nextLabel, onNext, lang }) {
  const g = sub < 4 ? canGoNext(steps, sub) : { ok: true, reason: '' }
  return (
    <div className="nw-flownav" data-role="flow-nav">
      <div className="nw-row">
        {sub > 1 && (
          <button type="button" className="nw-btn nw-btn-small" onClick={() => setSub(sub - 1)} data-role="flow-back">
            {tr('flow.back', {}, lang)}
          </button>
        )}
        <button type="button" className="nw-btn nw-btn-go" disabled={!g.ok} aria-describedby={g.ok ? undefined : 'nw-flow-why'} onClick={onNext ?? (() => setSub(sub + 1))} data-role="flow-next">
          {nextLabel}
        </button>
      </div>
      {!g.ok && (
        <p className="nw-hint" id="nw-flow-why" data-role="flow-why">
          {g.reason}
        </p>
      )}
    </div>
  )
}

export default function SpeciesFlow({
  sub, setSub, species, selIds, setSelIds, onlySeason, onInfo, purpose, query, how, setHow, mainId, setMain, combine, setCombine, includeUnzoned, setIncludeUnzoned,
  where, onWhere, barangays, zones, onGoPlan, seasonNotice = null, planAreaLabel = '', planCreated = false,
  markCount = 0, markArea = null, markSummary = [], onFinishMark, onUsePoint, onUndoMark, onClearMark, onShowPoint, onOpenMap, notice = '', selNames = [],
}) {
  const lang = useLang()
  const t = (k, p) => tr(k, p, lang)
  const whereLabel = where.kind === 'barangay' ? (barangays.find((b) => b.properties.name === where.name)?.properties.display_name ?? where.name) : where.name
  const steps = flowSteps({ selNames, where, whereLabel, planAreaLabel, planCreated }, lang)
  const countKey = markCount >= 3 ? 'mark.count3' : markCount === 2 ? 'mark.count2' : 'mark.count'
  return (
    <div data-role="species-flow" data-sub={sub}>
      <Stepper steps={steps} sub={sub} setSub={setSub} lang={lang} />
      {sub === 1 && (
        <div>
          <h4 className="nw-flowtitle">{t('flow.title1')}</h4>
          {seasonNotice}
          <SpeciesChooser species={species} selected={selIds} onChange={setSelIds} onlySeason={onlySeason} onInfo={onInfo} purpose={purpose} area={null} query={query} how={how} onHow={setHow} mainId={mainId} onMain={setMain} />
          {how && <Nav steps={steps} sub={1} setSub={setSub} lang={lang} nextLabel={selIds.length ? t('flow.next1n', { n: selIds.length }) : t('flow.next1')} />}
        </div>
      )}
      {sub === 2 && (
        <div>
          <h4 className="nw-flowtitle">{t('flow.title2')}</h4>
          <fieldset className="nw-fieldset">
            <legend className="nw-label">{t('flow.where.legend')}</legend>
            <div className="nw-tools">
              {['all', 'barangay', 'zone'].map((k) => (
                <label key={k} className={`nw-tool ${where.kind === k ? 'is-selected' : ''}`}>
                  <input type="radio" name="nw-where" checked={where.kind === k} onChange={() => onWhere({ kind: k, name: '' })} />
                  <span>{t(`flow.where.${k}`)}</span>
                </label>
              ))}
            </div>
          </fieldset>
          {where.kind === 'barangay' && (
            <>
              <label className="nw-label" htmlFor="nw-where-barangay">
                {t('flow.where.pickBarangay')}
              </label>
              <select id="nw-where-barangay" className="nw-select" value={where.name} onChange={(e) => onWhere({ kind: 'barangay', name: e.target.value })}>
                <option value="">{t('flow.where.barangayPh')}</option>
                {barangays.map((b) => (
                  <option key={b.properties.name} value={b.properties.name}>
                    {b.properties.display_name}
                  </option>
                ))}
              </select>
            </>
          )}
          {where.kind === 'zone' && (
            <>
              <label className="nw-label" htmlFor="nw-where-zone">
                {t('flow.where.pickZone')}
              </label>
              <select id="nw-where-zone" className="nw-select" value={where.name} onChange={(e) => onWhere({ kind: 'zone', name: e.target.value })}>
                <option value="">{t('flow.where.zonePh')}</option>
                {zones.map((z) => (
                  <option key={z.properties.name} value={z.properties.name}>
                    {z.properties.name}
                  </option>
                ))}
              </select>
            </>
          )}
          {selIds.length > 1 && (
            <Segmented
              name="combine"
              label="Place counts when"
              help="“Suits all”: every chosen species can grow there, and the score is the lowest of theirs. “Suits at least one”: one is enough, and the score is the highest."
              value={combine}
              options={[
                { value: 'all', label: 'Suits all' },
                { value: 'any', label: 'Suits at least one' },
              ]}
              onChange={setCombine}
            />
          )}
          <UnzonedToggle value={includeUnzoned} onChange={setIncludeUnzoned} />
          <Nav steps={steps} sub={2} setSub={setSub} lang={lang} nextLabel={t('flow.next2')} />
        </div>
      )}
      {sub === 3 && (
        <div data-role="mark-tool">
          <h4 className="nw-flowtitle">{t('flow.title3')}</h4>
          <p className="nw-plain" data-role="flow-where">
            {t('flow.summary.species')}: <strong>{selIds.length}</strong> · {t('flow.summary.where')}: <strong>{where.kind === 'all' ? t('flow.sum.all') : whereLabel}</strong>
            {selIds.length > 1 ? ` · ${combine === 'all' ? t('flow.combine.all') : t('flow.combine.any')}` : ''}
          </p>
          {!markArea ? (
            <>
              <p className="nw-hint" data-role="mark-help">
                {t('mark.help')}
              </p>
              <p className="nw-plain" data-role="mark-count">
                {t(countKey, { n: markCount })}
              </p>
              <button type="button" className="nw-btn nw-btn-small nw-openmap" onClick={onOpenMap} data-role="mark-open-map">
                {t('mark.openMap')}
              </button>
              {markCount === 1 && (
                <div className="nw-row">
                  <button type="button" className="nw-btn nw-btn-small" onClick={onShowPoint} data-role="mark-show-point">
                    {t('mark.showPoint')}
                  </button>
                  <button type="button" className="nw-btn nw-btn-go nw-btn-small" onClick={onUsePoint} data-role="mark-use-point">
                    {t('mark.usePoint')}
                  </button>
                </div>
              )}
              <div className="nw-row">
                <button type="button" className="nw-btn nw-btn-go" disabled={markCount < 3} onClick={onFinishMark} data-role="mark-finish" title={markCount < 3 ? t('mark.finishNeed') : undefined}>
                  {t('mark.finish')}
                </button>
                <button type="button" className="nw-btn nw-btn-small" disabled={markCount === 0} onClick={onUndoMark} data-role="mark-undo">
                  {t('mark.undo')}
                </button>
                <button type="button" className="nw-btn nw-btn-small" disabled={markCount === 0} onClick={onClearMark} data-role="mark-clear">
                  {t('mark.clear')}
                </button>
              </div>
            </>
          ) : (
            <div className="nw-areasum" data-role="area-summary">
              <p className="nw-plain">
                <strong>{t('mark.locked')}</strong>
              </p>
              {markSummary.map((x) => (
                <p key={x} className="nw-plain">
                  {x}
                </p>
              ))}
              <button type="button" className="nw-btn nw-btn-small" onClick={onClearMark} data-role="mark-clear">
                {t('mark.clear')}
              </button>
            </div>
          )}
          {notice && (
            <Callout tone="warning">
              {notice}
            </Callout>
          )}
          <p className="nw-hint">{t('mark.rightCard')}</p>
          <Nav steps={steps} sub={3} setSub={setSub} lang={lang} nextLabel={t('flow.next3')} />
        </div>
      )}
      {sub === 4 && (
        <div data-role="flow-plan">
          <h4 className="nw-flowtitle">{t('flow.title4')}</h4>
          <ul className="nw-plain nw-flowlist">
            {steps.slice(0, 3).map((st) => (
              <li key={st.n}>
                {st.title}: <strong>{st.summary || '—'}</strong>
              </li>
            ))}
          </ul>
          <Nav steps={steps} sub={4} setSub={setSub} lang={lang} nextLabel={planCreated ? t('flow.next4done') : t('flow.next4')} onNext={onGoPlan} />
        </div>
      )}
    </div>
  )
}
