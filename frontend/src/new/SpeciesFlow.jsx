import Segmented from './Segmented.jsx'
import SpeciesChooser from './SpeciesChooser.jsx'
import UnzonedToggle from './UnzonedToggle.jsx'
import Icon from './Icon.jsx'
import { canGoNext, canJump, flowSteps } from './flowState.js'

// Goal "I have species", step 4 as a real stepper (UX round 4):
//   1 Piliin ang species   2 Saan hahanapin (filter: buong San Mateo, barangay, zone)   3 Markahan sa mapa (one point, or an area)   4 Gumawa ng plano
// The stepper shows the current step, a check and a short summary on finished steps, and a finished step can be clicked to go back. Next stays off until the step is complete, with the reason in words.
// The choices live in AppNew, so they persist when the person goes back and forth.

function Stepper({ steps, sub, setSub }) {
  return (
    <ol className="nw-stepper" aria-label={`Hakbang ${sub} ng 4`} data-role="flow-steps">
      {steps.map((st) => {
        const current = st.n === sub
        const reachable = canJump(steps, st.n)
        const cls = current ? 'is-current' : st.done && st.n < sub ? 'is-done' : ''
        return (
          <li key={st.n} className={cls} aria-current={current ? 'step' : undefined}>
            <button type="button" className="nw-stepbtn" disabled={!reachable || current} onClick={() => setSub(st.n)} data-step={st.n} aria-label={`Hakbang ${st.n}: ${st.title}${st.summary ? `. ${st.summary}` : ''}`}>
              <span className="nw-flowno">{st.done && !current ? <Icon name="check" /> : st.n}</span>
              <span className="nw-steptext">
                <span className="nw-steptitle">{st.title}</span>
                {st.done && !current && st.summary && <span className="nw-stepsum">{st.summary}</span>}
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}

function Nav({ steps, sub, setSub, nextLabel, onNext }) {
  const g = sub < 4 ? canGoNext(steps, sub) : { ok: true, reason: '' }
  return (
    <div className="nw-flownav" data-role="flow-nav">
      <div className="nw-row">
        {sub > 1 && (
          <button type="button" className="nw-btn nw-btn-small" onClick={() => setSub(sub - 1)} data-role="flow-back">
            Balik
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
  markCount = 0, markArea = null, markSummary = [], onFinishMark, onUndoMark, onClearMark, onShowPoint, onOpenMap, notice = '', selNames = [],
}) {
  const whereLabel = where.kind === 'barangay' ? (barangays.find((b) => b.properties.name === where.name)?.properties.display_name ?? where.name) : where.name
  const steps = flowSteps({ selNames, where, whereLabel, planAreaLabel, planCreated })
  return (
    <div data-role="species-flow" data-sub={sub}>
      <Stepper steps={steps} sub={sub} setSub={setSub} />
      {sub === 1 && (
        <div>
          <h4 className="nw-flowtitle">Hakbang 1: Piliin ang species</h4>
          {seasonNotice}
          <SpeciesChooser species={species} selected={selIds} onChange={setSelIds} onlySeason={onlySeason} onInfo={onInfo} purpose={purpose} area={null} query={query} how={how} onHow={setHow} mainId={mainId} onMain={setMain} />
          {how && <Nav steps={steps} sub={1} setSub={setSub} nextLabel={`Susunod: Saan hahanapin${selIds.length ? ` (${selIds.length} napili)` : ''}`} />}
        </div>
      )}
      {sub === 2 && (
        <div>
          <h4 className="nw-flowtitle">Hakbang 2: Saan hahanapin?</h4>
          <fieldset className="nw-fieldset">
            <legend className="nw-label">Saan hahanapin ang mga pinakaangkop na lugar?</legend>
            <div className="nw-tools">
              {[
                ['all', 'Buong San Mateo'],
                ['barangay', 'Isang barangay'],
                ['zone', 'Isang zone'],
              ].map(([k, label]) => (
                <label key={k} className={`nw-tool ${where.kind === k ? 'is-selected' : ''}`}>
                  <input type="radio" name="nw-where" checked={where.kind === k} onChange={() => onWhere({ kind: k, name: '' })} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          {where.kind === 'barangay' && (
            <>
              <label className="nw-label" htmlFor="nw-where-barangay">
                Piliin ang barangay
              </label>
              <select id="nw-where-barangay" className="nw-select" value={where.name} onChange={(e) => onWhere({ kind: 'barangay', name: e.target.value })}>
                <option value="">Pumili ng barangay…</option>
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
                Piliin ang zone
              </label>
              <select id="nw-where-zone" className="nw-select" value={where.name} onChange={(e) => onWhere({ kind: 'zone', name: e.target.value })}>
                <option value="">Pumili ng zone…</option>
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
          <Nav steps={steps} sub={2} setSub={setSub} nextLabel="Susunod: Markahan sa mapa" />
        </div>
      )}
      {sub === 3 && (
        <div data-role="mark-tool">
          <h4 className="nw-flowtitle">Hakbang 3: Markahan sa mapa</h4>
          <p className="nw-plain" data-role="flow-where">
            Species: <strong>{selIds.length}</strong> · Hahanapin sa: <strong>{where.kind === 'all' ? 'Buong San Mateo' : whereLabel}</strong>
            {selIds.length > 1 ? ` · ${combine === 'all' ? 'Suits all' : 'Suits at least one'}` : ''}
          </p>
          {!markArea ? (
            <>
              <p className="nw-hint" data-role="mark-help">
                Mag-click sa mapa. Isang click = isang puntos (lalabas ang species para roon). Tatlo o higit pang click, tapos “Tapusin ang area” = isang area na pagtatamnan.
              </p>
              <p className="nw-plain" data-role="mark-count">
                Mga puntos na minarkahan: <strong>{markCount}</strong>
                {markCount >= 3 ? ' · puwede mo nang tapusin ang area' : markCount === 2 ? ' · kailangan pa ng isa para maging area' : ''}
              </p>
              <button type="button" className="nw-btn nw-btn-small nw-openmap" onClick={onOpenMap} data-role="mark-open-map">
                Buksan ang mapa para magmarka
              </button>
              {markCount === 1 && (
                <button type="button" className="nw-btn nw-btn-small" onClick={onShowPoint} data-role="mark-show-point">
                  Tingnan ang species sa puntong ito
                </button>
              )}
              <div className="nw-row">
                <button type="button" className="nw-btn nw-btn-go" disabled={markCount < 3} onClick={onFinishMark} data-role="mark-finish" title={markCount < 3 ? 'Kailangan ng hindi bababa sa tatlong puntos' : undefined}>
                  Tapusin ang area
                </button>
                <button type="button" className="nw-btn nw-btn-small" disabled={markCount === 0} onClick={onUndoMark} data-role="mark-undo">
                  Alisin ang huling puntos
                </button>
                <button type="button" className="nw-btn nw-btn-small" disabled={markCount === 0} onClick={onClearMark} data-role="mark-clear">
                  Burahin lahat
                </button>
              </div>
            </>
          ) : (
            <div className="nw-areasum" data-role="area-summary">
              <p className="nw-plain">
                <strong>Naka-lock ang minarkahang area.</strong>
              </p>
              {markSummary.map((t) => (
                <p key={t} className="nw-plain">
                  {t}
                </p>
              ))}
              <button type="button" className="nw-btn nw-btn-small" onClick={onClearMark} data-role="mark-clear">
                Burahin lahat
              </button>
            </div>
          )}
          {notice && (
            <p className="nw-hint nw-warn" role="status">
              {notice}
            </p>
          )}
          <p className="nw-hint">Nasa kanang card ang mga barangay at zone na pinakaangkop; kulay ng mapa ang tugma ng bawat parisukat.</p>
          <Nav steps={steps} sub={3} setSub={setSub} nextLabel="Susunod: Gumawa ng plano" />
        </div>
      )}
      {sub === 4 && (
        <div data-role="flow-plan">
          <h4 className="nw-flowtitle">Hakbang 4: Gumawa ng plano</h4>
          <ul className="nw-plain nw-flowlist">
            {steps.slice(0, 3).map((st) => (
              <li key={st.n}>
                {st.title}: <strong>{st.summary || '—'}</strong>
              </li>
            ))}
          </ul>
          <Nav steps={steps} sub={4} setSub={setSub} nextLabel={planCreated ? 'Buksan ang Plano' : 'Gumawa ng plano'} onNext={onGoPlan} />
        </div>
      )}
    </div>
  )
}
