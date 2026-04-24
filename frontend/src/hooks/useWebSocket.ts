import { useEffect, useRef, useState } from 'react'

export function useWebSocket<T>(url: string, fallback: () => Promise<T>, interval = 2000) {
  const [data, setData] = useState<T | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // 尝试 WebSocket
    try {
      const ws = new WebSocket(url)
      ws.onopen = () => setConnected(true)
      ws.onmessage = (e) => setData(JSON.parse(e.data))
      ws.onclose = () => setConnected(false)
      wsRef.current = ws
      return () => ws.close()
    } catch {
      // 降级到轮询
    }
  }, [url])

  // 如果 WebSocket 未连接，使用轮询
  useEffect(() => {
    if (connected) return
    const timer = setInterval(async () => {
      const result = await fallback()
      setData(result)
    }, interval)
    return () => clearInterval(timer)
  }, [connected, fallback, interval])

  return { data, connected }
}
