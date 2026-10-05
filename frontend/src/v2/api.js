import { API_BASE } from './config.js'

// An error from the API call, already worded for people. `network` is true when the API could not be reached at all.
export class ApiError extends Error {
  constructor(message, { status = null, network = false } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.network = network
  }
}

function detailText(body, fallback) {
  if (typeof body?.detail === 'string') return body.detail
  if (Array.isArray(body?.detail)) return body.detail.map((d) => d.msg).join('; ')
  return fallback
}

// GET a path like "/rank?purpose=urban&lat=14.7&lon=121.1". Aborting (signal) throws the browser's AbortError, which callers ignore.
export async function apiGet(pathAndQuery, signal) {
  let res
  try {
    res = await fetch(`${API_BASE}${pathAndQuery}`, { signal, headers: { Accept: 'application/json' } })
  } catch (e) {
    if (e?.name === 'AbortError') throw e
    throw new ApiError(`The planning service could not be reached at ${API_BASE}.`, { network: true })
  }
  let body
  try {
    body = await res.json()
  } catch {
    body = null
  }
  if (!res.ok) throw new ApiError(detailText(body, `The service answered with an error (HTTP ${res.status}).`), { status: res.status })
  return body
}
