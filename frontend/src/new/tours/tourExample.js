// The example data of the tours (R1 W3). The tours never depend on what the person selected: they use ONE fixed example point and ONE fixed example area.
// The point was chosen BY CODE (scripts/pick_tour_example.py): among confirmed-zone squares it has the most species with a Good match for urban greening in the default window (20 of 45).
export const EXAMPLE_POINT = { id: 12176, lat: 14.672713, lon: 121.207722, barangay: 'Pintong Bukawe', label: { en: 'Example point', tl: 'Halimbawang punto' } }

// About 240 m x 220 m around the example point: [lat, lon] corners of the area that the area-tool tour "draws".
const D_LAT = 0.0010
const D_LON = 0.0011
export const EXAMPLE_VERTICES = [
  [EXAMPLE_POINT.lat - D_LAT, EXAMPLE_POINT.lon - D_LON],
  [EXAMPLE_POINT.lat - D_LAT, EXAMPLE_POINT.lon + D_LON],
  [EXAMPLE_POINT.lat + D_LAT, EXAMPLE_POINT.lon + D_LON],
  [EXAMPLE_POINT.lat + D_LAT, EXAMPLE_POINT.lon - D_LON],
]
// the species of the example species card: chosen because it has advice (4 items) and partners (3), so every section of the card is on screen
export const EXAMPLE_SPECIES_ID = 17
