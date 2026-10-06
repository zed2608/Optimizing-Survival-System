import HelpTip from './HelpTip.jsx'

// Step 4: "Include land outside the zoning map" (default ON). On: squares that no zoning polygon covers are scored like the others but flagged, and planned trees there get a dotted ring.
export default function UnzonedToggle({ value, onChange }) {
  return (
    <div className="nw-opt-head nw-opt-gap">
      <label className="nw-togglerow" htmlFor="nw-include-unzoned">
        <input id="nw-include-unzoned" type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} />
        <span>Include land outside the zoning map</span>
      </label>
      <HelpTip label="Include land outside the zoning map">Zoning not confirmed: check with the LGU before planting.</HelpTip>
    </div>
  )
}
