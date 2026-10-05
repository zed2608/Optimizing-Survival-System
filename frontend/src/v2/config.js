// The ONE place for the API address and the page settings of the new dashboard (#/v2).
// Change the address with the VITE_API_BASE environment variable (for example in frontend/.env.local); default below.
export const API_BASE = (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8001').replace(/\/+$/, '')

// How to start the backend (shown in the "API is off" message). Run it from the project folder.
export const START_COMMAND = 'python -m uvicorn api_v2:app --port 8001'

// Map: same centre and zoom as the earlier dashboard. Bounds cover the mapped grid with a margin (lat/lon).
export const MAP_CENTER = [14.6983, 121.1185]
export const MAP_ZOOM = 13
export const MAP_MIN_ZOOM = 11
export const MAP_BOUNDS = [[14.6, 121.06], [14.78, 121.3]]

// A real legal spot (Forest Zone) for the "use an example spot" button.
export const EXAMPLE_SPOT = { lat: 14.726783, lon: 121.187781 }

// How many species the ranking panels ask for (the API allows more).
export const RANK_LIMIT = 10
export const MUNICIPAL_LIMIT = 10

// Colour scale for the overall score W (provisional, for reading only; the number is always shown too).
export const W_GOOD = 0.55
export const W_MODERATE = 0.35
