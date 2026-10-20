import Segmented from './Segmented.jsx'
import SpeciesChooser from './SpeciesChooser.jsx'
import UnzonedToggle from './UnzonedToggle.jsx'

// Goal "I have species", step 4 as a short walk (UX round 2, C): one question per screen, a step indicator, one list at a time.
//   1 Piliin ang species    2 Saan hahanapin (buong San Mateo, isang barangay o isang zone)    3 Mga pinakaangkop na lugar (the right card)    4 Gumawa ng plano (the Plan step)
// Everything that existed is kept: the same choices, the same API calls (GET /grid, /areas/rank), the same filters (now behind the "Salain" button of the list).
const FLOW_STEPS = ['Piliin ang species', 'Saan hahanapin', 'Mga pinakaangkop na lugar', 'Gumawa ng plano']

function StepIndicator({ sub }) {
  return (
    <ol className="nw-flowsteps" aria-label="Mga hakbang" data-role="flow-steps">
      {FLOW_STEPS.map((t, i) => (
        <li key={t} className={i + 1 === sub ? 'is-current' : i + 1 < sub ? 'is-done' : ''} aria-current={i + 1 === sub ? 'step' : undefined}>
          <span className="nw-flowno">{i + 1}</span> {t}
        </li>
      ))}
    </ol>
  )
}

export default function SpeciesFlow({
  sub, setSub, species, selIds, setSelIds, onlySeason, onInfo, purpose, query, how, setHow, mainId, setMain, combine, setCombine, includeUnzoned, setIncludeUnzoned,
  where, onWhere, barangays, zones, onGoPlan, seasonNotice = null,
}) {
  const nothing = selIds.length === 0
  return (
    <div data-role="species-flow" data-sub={sub}>
      <StepIndicator sub={sub} />
      {sub === 1 && (
        <div>
          <h4 className="nw-flowtitle">Hakbang 1: Piliin ang species</h4>
          {seasonNotice}
          <SpeciesChooser species={species} selected={selIds} onChange={setSelIds} onlySeason={onlySeason} onInfo={onInfo} purpose={purpose} area={null} query={query} how={how} onHow={setHow} mainId={mainId} onMain={setMain} />
          {how && (
            <button type="button" className="nw-btn nw-btn-go nw-btn-wide" disabled={nothing} onClick={() => setSub(2)} title={nothing ? 'Pumili muna ng species' : undefined}>
              {nothing ? 'Pumili muna ng species' : `Susunod: Saan hahanapin (${selIds.length} napili)`}
            </button>
          )}
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
          <div className="nw-row">
            <button type="button" className="nw-btn nw-btn-small" onClick={() => setSub(1)}>
              Balik
            </button>
            <button type="button" className="nw-btn nw-btn-go" onClick={() => setSub(3)} disabled={where.kind !== 'all' && !where.name} title={where.kind !== 'all' && !where.name ? 'Pumili muna ng lugar' : undefined}>
              Susunod: Tingnan ang mga lugar
            </button>
          </div>
        </div>
      )}
      {sub === 3 && (
        <div>
          <h4 className="nw-flowtitle">Hakbang 3: Mga pinakaangkop na lugar</h4>
          <p className="nw-plain" data-role="flow-where">
            Species: <strong>{selIds.length}</strong> · Lugar: <strong>{where.kind === 'all' ? 'Buong San Mateo' : where.name}</strong>
            {selIds.length > 1 ? ` · ${combine === 'all' ? 'Suits all' : 'Suits at least one'}` : ''}
          </p>
          <p className="nw-hint">Nasa kanang card ang mga barangay at zone na pinakaangkop, at kulay ng mapa ang tugma ng bawat parisukat.</p>
          <div className="nw-row">
            <button type="button" className="nw-btn nw-btn-small" onClick={() => setSub(2)}>
              Balik
            </button>
            <button type="button" className="nw-btn nw-btn-go" onClick={onGoPlan}>
              Susunod: Gumawa ng plano
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
