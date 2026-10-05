import { useCallback, useEffect, useState } from 'react'
import { apiGet } from './api.js'

// useApi(url): GET `url` (a path with query string) and report { status, data, error, retry }.
// status is 'idle' (url is null), 'loading', 'ok' or 'error'. A new url cancels the old request, so a slow old answer never
// replaces a newer one. State is only set after the request finishes (never synchronously inside the effect).
export function useApi(url) {
  const [res, setRes] = useState({ id: null, data: null, error: null })
  const [tick, setTick] = useState(0)
  const id = url === null ? null : `${url}#${tick}`

  useEffect(() => {
    if (url === null) return undefined
    const controller = new AbortController()
    const myId = `${url}#${tick}`
    apiGet(url, controller.signal).then(
      (data) => setRes({ id: myId, data, error: null }),
      (error) => {
        if (error?.name !== 'AbortError') setRes({ id: myId, data: null, error })
      },
    )
    return () => controller.abort()
  }, [url, tick])

  const retry = useCallback(() => setTick((t) => t + 1), [])
  if (id === null) return { status: 'idle', data: null, error: null, retry }
  if (res.id !== id) return { status: 'loading', data: null, error: null, retry }
  if (res.error) return { status: 'error', data: null, error: res.error, retry }
  return { status: 'ok', data: res.data, error: null, retry }
}
