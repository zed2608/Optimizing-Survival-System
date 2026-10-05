import { useCallback, useEffect, useState } from 'react'
import { apiPost } from './apiPost.js'

// usePost(path, body): like useApi, but a POST with a JSON body. body === null means "do not ask" (status 'idle').
// A new body cancels the old request. State is only set after the request finishes.
export function usePost(path, body) {
  const [res, setRes] = useState({ id: null, data: null, error: null })
  const [tick, setTick] = useState(0)
  const bodyKey = body === null ? null : JSON.stringify(body)
  const id = bodyKey === null ? null : `${path}|${bodyKey}#${tick}`

  useEffect(() => {
    if (bodyKey === null) return undefined
    const controller = new AbortController()
    const myId = `${path}|${bodyKey}#${tick}`
    apiPost(path, JSON.parse(bodyKey), controller.signal).then(
      (data) => setRes({ id: myId, data, error: null }),
      (error) => {
        if (error?.name !== 'AbortError') setRes({ id: myId, data: null, error })
      },
    )
    return () => controller.abort()
  }, [path, bodyKey, tick])

  const retry = useCallback(() => setTick((t) => t + 1), [])
  if (id === null) return { status: 'idle', data: null, error: null, retry }
  if (res.id !== id) return { status: 'loading', data: null, error: null, retry }
  if (res.error) return { status: 'error', data: null, error: res.error, retry }
  return { status: 'ok', data: res.data, error: null, retry }
}
