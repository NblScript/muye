import { useEffect, useRef, useState } from 'react'

const INITIAL_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 30000

function toErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

export function useWebSocket<T>(url: string, fallback: () => Promise<T>, interval = 2000) {
  const [data, setData] = useState<T | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reconnectCount, setReconnectCount] = useState(0)

  const wsRef = useRef<WebSocket | null>(null)
  const fallbackRef = useRef(fallback)
  const mountedRef = useRef(true)
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY_MS)
  const reconnectTimerRef = useRef<number | null>(null)
  const pollTimerRef = useRef<number | null>(null)
  const seenSuccessfulConnectionRef = useRef(false)
  const disconnectedSinceLastOpenRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true

    return () => {
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    fallbackRef.current = fallback
  }, [fallback])

  useEffect(() => {
    let cancelled = false
    const resetStateTimer = window.setTimeout(() => {
      if (!cancelled) {
        setConnected(false)
        setError(null)
      }
    }, 0)

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
    }

    const stopPolling = () => {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }

    const runFallback = async () => {
      try {
        const result = await fallbackRef.current()
        if (cancelled) {
          return
        }
        setData(result)
        setError(null)
      } catch (nextError) {
        if (cancelled) {
          return
        }
        setError(toErrorMessage(nextError, '实时数据加载失败'))
      }
    }

    const startPolling = () => {
      if (pollTimerRef.current !== null) {
        return
      }

      void runFallback()
      pollTimerRef.current = window.setInterval(() => {
        void runFallback()
      }, interval)
    }

    const scheduleReconnect = () => {
      if (cancelled || reconnectTimerRef.current !== null) {
        return
      }

      const delay = reconnectDelayRef.current
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null
        connect()
      }, delay)
      reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY_MS)
    }

    const connect = () => {
      if (cancelled) {
        return
      }

      try {
        const ws = new WebSocket(url)
        wsRef.current = ws

        ws.onopen = () => {
          if (cancelled || wsRef.current !== ws) {
            return
          }

          clearReconnectTimer()
          stopPolling()
          setConnected(true)
          setError(null)
          reconnectDelayRef.current = INITIAL_RECONNECT_DELAY_MS

          if (seenSuccessfulConnectionRef.current && disconnectedSinceLastOpenRef.current) {
            setReconnectCount((count) => count + 1)
            disconnectedSinceLastOpenRef.current = false
          }

          seenSuccessfulConnectionRef.current = true
        }

        ws.onmessage = (event) => {
          if (cancelled || wsRef.current !== ws) {
            return
          }

          try {
            setData(JSON.parse(event.data) as T)
            setError(null)
          } catch {
            setError('实时数据解析失败')
          }
        }

        ws.onerror = () => {
          if (cancelled || wsRef.current !== ws) {
            return
          }
          setConnected(false)
        }

        ws.onclose = () => {
          if (cancelled || wsRef.current !== ws) {
            return
          }

          wsRef.current = null
          setConnected(false)

          if (seenSuccessfulConnectionRef.current) {
            disconnectedSinceLastOpenRef.current = true
          }

          startPolling()
          scheduleReconnect()
        }
      } catch (nextError) {
        if (cancelled) {
          return
        }

        setConnected(false)
        setError(toErrorMessage(nextError, 'WebSocket 初始化失败'))
        startPolling()
        scheduleReconnect()
      }
    }

    reconnectDelayRef.current = INITIAL_RECONNECT_DELAY_MS
    seenSuccessfulConnectionRef.current = false
    disconnectedSinceLastOpenRef.current = false
    clearReconnectTimer()
    stopPolling()
    void runFallback()
    connect()

    return () => {
      cancelled = true
      window.clearTimeout(resetStateTimer)
      clearReconnectTimer()
      stopPolling()

      if (wsRef.current !== null) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [interval, url])

  const refresh = async () => {
    try {
      const result = await fallbackRef.current()
      if (mountedRef.current) {
        setData(result)
        setError(null)
      }
    } catch (nextError) {
      if (mountedRef.current) {
        setError(toErrorMessage(nextError, '实时数据加载失败'))
      }
      throw nextError
    }
  }

  return { data, connected, error, reconnectCount, refresh }
}
