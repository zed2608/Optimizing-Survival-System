import { tr, useLang } from './i18n.js'
const TOOLS = [
  { id: 'point', label: 'Click a point', help: 'Click a dot on the map to see its species.' },
  { id: 'barangay', label: 'Click a barangay', help: 'Click inside a barangay outline.' },
  { id: 'draw', label: 'Draw an area', help: 'Click corners on the map, then Finish.' },
]

// Mode 2: the ways to choose an area: click a point, click a barangay, pick one from a list, or draw a polygon.
export default function AreaChooser({ tool, onTool, barangays, zones, area, onArea, draftCount, onFinish, onUndo, onClearDraft, summary = [], blocked = '' }) {
  const lang = useLang()
  const locked = area?.kind === 'polygon' && tool === 'draw' // UX round 2 (A2): a finished drawn area is locked until "Clear area" or "Start again"
  const barangayValue = area?.kind === 'barangay' ? area.name : ''
  const zoneValue = area?.kind === 'zone' ? area.name : ''
  return (
    <div>
      <fieldset className="nw-fieldset">
        <legend className="nw-label">How to choose the area</legend>
        <div className="nw-tools">
          {TOOLS.map((t) => (
            <label key={t.id} className={`nw-tool ${tool === t.id ? 'is-selected' : ''}`}>
              <input type="radio" name="nw-tool" checked={tool === t.id} onChange={() => onTool(t.id)} />
              <span>{t.label}</span>
            </label>
          ))}
        </div>
        <p className="nw-hint">{TOOLS.find((t) => t.id === tool).help}</p>
      </fieldset>

      {tool === 'draw' && (
        <div className="nw-drawbox">
          <p className="nw-hint" role="status">
            {locked
              ? tr('area.drawLocked', {}, lang)
              : draftCount === 0
              ? tr('area.draw0', {}, lang)
              : tr('area.drawN', { n: draftCount, need: draftCount < 3 ? tr('area.drawNeed', {}, lang) : '' }, lang)}
          </p>
          <div className="nw-row">
            <button type="button" className="nw-btn nw-btn-small nw-btn-go" onClick={onFinish} disabled={locked || draftCount < 3}>
              Finish area
            </button>
            <button type="button" className="nw-btn nw-btn-small" onClick={onUndo} disabled={locked || draftCount === 0}>
              Undo last corner
            </button>
            <button type="button" className="nw-btn nw-btn-small" onClick={() => { if (locked) onArea(null); onClearDraft() }} disabled={!locked && draftCount === 0}>
              Start again
            </button>
          </div>
        </div>
      )}

      {tool === 'barangay' && (
        <>
          <label className="nw-label" htmlFor="nw-barangay">
            Or pick a barangay
          </label>
          <select id="nw-barangay" className="nw-select" value={barangayValue} onChange={(e) => e.target.value && onArea({ kind: 'barangay', name: e.target.value })}>
            <option value="">Choose a barangay…</option>
            {barangays.map((b) => (
              <option key={b.properties.name} value={b.properties.name}>
                {b.properties.display_name}
              </option>
            ))}
          </select>
          <label className="nw-label nw-label-gap" htmlFor="nw-zone">
            Or pick a zone
          </label>
          <select id="nw-zone" className="nw-select" value={zoneValue} onChange={(e) => e.target.value && onArea({ kind: 'zone', name: e.target.value })}>
            <option value="">Choose a zone…</option>
            {zones.map((z) => (
              <option key={z.properties.name} value={z.properties.name}>
                {z.properties.name}
              </option>
            ))}
          </select>
          {(barangays.length === 0 || zones.length === 0) && <p className="nw-hint">{tr('area.svcNote', {}, lang)}</p>}
          </>
      )}

      {summary.length > 0 && (
        <div className="nw-current nw-areasummary" data-role="area-summary">
          <dl className="nw-summary-list">
            {summary.map((r) => (
              <div key={r.label}>
                <dt>{r.label}</dt>
                <dd>{r.value}</dd>
              </div>
            ))}
          </dl>
          {area && (
            <button type="button" className="nw-btn nw-btn-small" onClick={() => onArea(null)}>
              Clear area
            </button>
          )}
        </div>
      )}
      {blocked && (
        <p className="nw-hint nw-warn" role="alert" data-role="area-blocked">
          {blocked}
        </p>
      )}
    </div>
  )
}
