import { useCallback, useEffect, useState } from 'react'
import { apiGet } from './api.js'

// useApi(url): GET `url` (a path with query string) and report { status, data, error, retry }.
// status is 'idle' (url is null), 'loading', 'ok' or 'error'. A new url cancels the old request, so a slow old answer never
// replaces a newer one. State is only set after the request finishes (never synchronously inside the effect).
// useApi(url, { ttlMs }): with ttlMs a good answer for the same url is kept in memory for that long, so switching tabs or re-rendering does not ask the service again (retry() always asks again).
const memo = new Map()
const isFresh = (hit, ttl) => !!hit && Date.now() - hit.t < ttl
export function useApi(url, { ttlMs = 0 } = {}) {
  const [res, setRes] = useState({ id: null, data: null, error: null })
  const [tick, setTick] = useState(0)
  const id = url === null ? null : `${url}#${tick}`
  const hit = ttlMs && url !== null && tick === 0 ? memo.get(url) : null
  const fresh = isFresh(hit, ttlMs) ? hit : null

  useEffect(() => {
    if (url === null || (ttlMs && tick === 0 && isFresh(memo.get(url), ttlMs))) return undefined
    const controller = new AbortController()
    const myId = `${url}#${tick}`
    apiGet(url, controller.signal).then(
      (data) => {
        if (ttlMs) memo.set(url, { t: Date.now(), data })
        setRes({ id: myId, data, error: null })
      },
      (error) => {
        if (error?.name !== 'AbortError') setRes({ id: myId, data: null, error })
      },
    )
    return () => controller.abort()
  }, [url, tick, ttlMs])

  const retry = useCallback(() => {
    memo.delete(url)
    setTick((t) => t + 1)
  }, [url])
  if (id === null) return { status: 'idle', data: null, error: null, retry }
  if (fresh) return { status: 'ok', data: fresh.data, error: null, retry }
  if (res.id !== id) return { status: 'loading', data: null, error: null, retry }
  if (res.error) return { status: 'error', data: null, error: res.error, retry }
  return { status: 'ok', data: res.data, error: null, retry }
}
