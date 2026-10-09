import { ZONE_TABLE as table } from './zoneColorsTable.js'

// The colours of the optional Zoning overlay (MPDC standard colours). One module: the map layer, the legend and the tests all read it.
export const ZONE_FILL_OPACITY = table.fill_opacity
export const ZONE_LINE_WEIGHT = table.line_weight
export const ZONE_COLORS = table.colors
export const OUTSIDE_MAP = table.outside_map

export function zoneColor(name) {
  return (ZONE_COLORS[name] ?? table.fallback).color
}
export function zoneColorName(name) {
  return (ZONE_COLORS[name] ?? table.fallback).name
}

// Legend order: the order of the colours table (greens, yellows, blues, violets, reds, grays); a zone that is not in the table goes last.
export function legendOrder(features) {
  const order = Object.keys(ZONE_COLORS)
  const rank = (n) => (order.includes(n) ? order.indexOf(n) : order.length)
  return [...features].sort((a, b) => rank(a.properties.name) - rank(b.properties.name) || a.properties.name.localeCompare(b.properties.name))
}

// "needs permission (private land)" -> "Needs permission (private land)"
export function conditionText(c) {
  return c ? c.charAt(0).toUpperCase() + c.slice(1) : ''
}
export function needsPermission(c) {
  return /permission|permit/i.test(c ?? '')
}
