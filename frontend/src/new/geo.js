// Small geometry helpers (no extra packages). Coordinates are GeoJSON order: [lon, lat].

function ringContains(ring, lon, lat) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

function polygonContains(rings, lon, lat) {
  if (!ringContains(rings[0], lon, lat)) return false
  for (let h = 1; h < rings.length; h++) if (ringContains(rings[h], lon, lat)) return false
  return true
}

export function geometryContains(geometry, lon, lat) {
  if (!geometry) return false
  if (geometry.type === 'Polygon') return polygonContains(geometry.coordinates, lon, lat)
  if (geometry.type === 'MultiPolygon') return geometry.coordinates.some((p) => polygonContains(p, lon, lat))
  return false
}

// the first feature whose polygon contains the point, or null
export function featureAt(features, lon, lat) {
  return features.find((f) => geometryContains(f.geometry, lon, lat)) ?? null
}

// vertices = [[lat, lon], ...] -> a closed GeoJSON Polygon geometry
export function polygonFromVertices(vertices) {
  const ring = vertices.map(([lat, lon]) => [lon, lat])
  ring.push([...ring[0]])
  return { type: 'Polygon', coordinates: [ring] }
}

// a GeoJSON geometry's bbox [minlon, minlat, maxlon, maxlat]
export function geometryBbox(geometry) {
  let x0 = Infinity
  let y0 = Infinity
  let x1 = -Infinity
  let y1 = -Infinity
  const visit = (c) => {
    if (typeof c[0] === 'number') {
      x0 = Math.min(x0, c[0])
      x1 = Math.max(x1, c[0])
      y0 = Math.min(y0, c[1])
      y1 = Math.max(y1, c[1])
    } else c.forEach(visit)
  }
  visit(geometry.coordinates)
  return [x0, y0, x1, y1]
}
