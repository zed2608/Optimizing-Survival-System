const TOOLS = [
  { id: 'point', label: 'Click a point', help: 'Click a dot on the map to see its species.' },
  { id: 'barangay', label: 'Click a barangay', help: 'Click inside a barangay outline.' },
  { id: 'draw', label: 'Draw an area', help: 'Click corners on the map, then Finish.' },
]

// Mode 2: the ways to choose an area: click a point, click a barangay, pick one from a list, or draw a polygon.
export default function AreaChooser({ tool, onTool, barangays, zones, area, onArea, draftCount, onFinish, onUndo, onClearDraft }) {
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
            {draftCount === 0 ? 'Click the map to place the first corner.' : `${draftCount} corner${draftCount === 1 ? '' : 's'} placed${draftCount < 3 ? ' (at least 3 are needed)' : ''}.`}
          </p>
          <div className="nw-row">
            <button type="button" className="nw-btn nw-btn-small nw-btn-go" onClick={onFinish} disabled={draftCount < 3}>
              Finish area
            </button>
            <button type="button" className="nw-btn nw-btn-small" onClick={onUndo} disabled={draftCount === 0}>
              Undo last corner
            </button>
            <button type="button" className="nw-btn nw-btn-small" onClick={onClearDraft} disabled={draftCount === 0}>
              Start again
            </button>
          </div>
        </div>
      )}

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
      {(barangays.length === 0 || zones.length === 0) && <p className="nw-hint">The barangay and zone lists load from the planning service.</p>}

      {area && (
        <div className="nw-current">
          <span>
            Area: <strong>{area.kind === 'polygon' ? 'Drawn area' : area.kind === 'zone' ? area.name : (barangays.find((b) => b.properties.name === area.name)?.properties.display_name ?? area.name)}</strong>
          </span>
          <button type="button" className="nw-btn nw-btn-small" onClick={() => onArea(null)}>
            Clear area
          </button>
        </div>
      )}
    </div>
  )
}
