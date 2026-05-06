import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../api'

/**
 * useSSE — connects to the live SSE stream from Part 1
 * Returns: { events, latestByCell, isConnected, error }
 */
export function useSSE(maxEvents = 200) {
  const [events, setEvents]         = useState([])
  const [latestByCell, setLatest]   = useState({})
  const [isConnected, setConnected] = useState(false)
  const [error, setError]           = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    let es
    const connect = () => {
      es = new EventSource(api.sseUrl)
      esRef.current = es

      es.onopen = () => { setConnected(true); setError(null) }

      es.onmessage = (e) => {
        try {
          const record = JSON.parse(e.data)
          if (record.type === 'connected') return

          setEvents(prev => {
            const next = [record, ...prev]
            return next.slice(0, maxEvents)
          })
          setLatest(prev => ({
            ...prev,
            [record.cell_id]: record,
          }))
        } catch {/* ignore parse errors */}
      }

      es.onerror = () => {
        setConnected(false)
        setError('Connexion SSE perdue — reconnexion...')
        es.close()
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => { if (esRef.current) esRef.current.close() }
  }, [maxEvents])

  return { events, latestByCell, isConnected, error }
}

/**
 * usePolling — polls an async fn every `interval` ms
 */
export function usePolling(fn, interval = 10000, deps = []) {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  const fetchData = useCallback(async () => {
    try {
      const result = await fn()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, deps)

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, interval)
    return () => clearInterval(id)
  }, [fetchData, interval])

  return { data, loading, error, refresh: fetchData }
}
