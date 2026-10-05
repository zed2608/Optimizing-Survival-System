import { API_BASE } from '../v2/config.js'
import { ApiError } from '../v2/api.js'

// POST a JSON body. Errors come back as the same ApiError as GET requests (the API's own message for 400/422).
export async function apiPost(path, body, signal) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (e) {
    if (e?.name === 'AbortError') throw e
    throw new ApiError(`The planning service could not be reached at ${API_BASE}.`, { network: true })
  }
  let payload
  try {
    payload = await res.json()
  } catch {
    payload = null
  }
  if (!res.ok) {
    const d = payload?.detail
    const message = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join('; ') : `The service answered with an error (HTTP ${res.status}).`
    throw new ApiError(message, { status: res.status })
  }
  return payload
}

// POST raw text (the CSV of a field kit) and read the JSON answer. Same error handling as apiPost.
export async function apiPostText(path, text, signal) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, { method: 'POST', signal, headers: { Accept: 'application/json', 'Content-Type': 'text/csv' }, body: text })
  } catch (e) {
    if (e?.name === 'AbortError') throw e
    throw new ApiError(`The planning service could not be reached at ${API_BASE}.`, { network: true })
  }
  let payload
  try {
    payload = await res.json()
  } catch {
    payload = null
  }
  if (!res.ok) {
    const d = payload?.detail
    throw new ApiError(typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join('; ') : `The service answered with an error (HTTP ${res.status}).`, { status: res.status })
  }
  return payload
}
