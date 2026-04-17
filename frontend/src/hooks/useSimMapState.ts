import { useEffect, useRef, useState } from 'react'

import { buildSimMapWebSocketUrl, fetchSimMapState } from '../api/simMap'
import type { SimMapStateResponse } from '../types/simMap'

type UseSimMapStateResult = {
  data: SimMapStateResponse | null
  loading: boolean
  error: string | null
  transport: 'websocket' | 'polling'
}

export function useSimMapState(): UseSimMapStateResult {
  const [data, setData] = useState<SimMapStateResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [transport, setTransport] = useState<'websocket' | 'polling'>('polling')
  const pollingTimerRef = useRef<number | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)

  useEffect(() => {
    let active = true

    const loadState = async () => {
      try {
        const next = await fetchSimMapState()
        if (!active) {
          return
        }
        setData(next)
        setError(null)
        setTransport('polling')
      } catch (loadError) {
        if (!active) {
          return
        }
        setError(loadError instanceof Error ? loadError.message : '加载仿真地图失败')
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    const stopPolling = () => {
      if (pollingTimerRef.current !== null) {
        window.clearInterval(pollingTimerRef.current)
        pollingTimerRef.current = null
      }
    }

    const stopReconnect = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
    }

    const startPolling = () => {
      if (!active || pollingTimerRef.current !== null) {
        return
      }

      void loadState()
      pollingTimerRef.current = window.setInterval(() => {
        void loadState()
      }, 1000)
    }

    const scheduleReconnect = () => {
      if (!active || reconnectTimerRef.current !== null) {
        return
      }

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null
        connectWebSocket()
      }, 5000)
    }

    const connectWebSocket = () => {
      if (!active || socketRef.current !== null) {
        return
      }

      try {
        const socket = new WebSocket(buildSimMapWebSocketUrl())
        socketRef.current = socket

        socket.onopen = () => {
          if (!active) {
            socket.close()
            return
          }
          stopReconnect()
          setTransport('websocket')
          setError(null)
          stopPolling()
        }

        socket.onmessage = (event) => {
          if (!active) {
            return
          }

          try {
            const payload = JSON.parse(event.data) as SimMapStateResponse
            setData(payload)
            setLoading(false)
          } catch (parseError) {
            setError(parseError instanceof Error ? parseError.message : '解析地图数据失败')
          }
        }

        socket.onerror = () => {
          socket.close()
        }

        socket.onclose = () => {
          socketRef.current = null
          if (active) {
            setTransport('polling')
            startPolling()
            scheduleReconnect()
          }
        }
      } catch (connectError) {
        if (!active) {
          return
        }
        setError(connectError instanceof Error ? connectError.message : '连接地图通道失败')
        setTransport('polling')
        startPolling()
        scheduleReconnect()
      }
    }

    connectWebSocket()

    return () => {
      active = false
      stopPolling()
      stopReconnect()
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [])

  return {
    data,
    loading,
    error,
    transport,
  }
}
