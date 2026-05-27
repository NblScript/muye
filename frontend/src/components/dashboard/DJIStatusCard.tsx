import { useEffect, useState } from 'react'
import { Card } from '../ui'
import type { DJIStatus, DJITelemetry } from '../../types/workflow'

async function fetchJSON<T>(url: string): Promise<T | null> {
  try {
    const resp = await fetch(url)
    if (!resp.ok) return null
    return resp.json()
  } catch {
    return null
  }
}

export default function DJIStatusCard() {
  const [status, setStatus] = useState<DJIStatus | null>(null)
  const [telemetry, setTelemetry] = useState<DJITelemetry | null>(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      const [s, t] = await Promise.all([
        fetchJSON<DJIStatus>('/api/drone/dji/status'),
        fetchJSON<DJITelemetry>('/api/drone/dji/telemetry'),
      ])
      if (active) {
        setStatus(s)
        setTelemetry(t)
      }
    }
    load()
    const timer = setInterval(load, 3000)
    return () => { active = false; clearInterval(timer) }
  }, [])

  if (!status) return null

  const connected = status.connected
  const modeLabel = status.execution_mode === 'osdk_sim' ? '仿真模式' : '实机模式'

  return (
    <Card className="dashboard-card">
      <span className="label-uppercase">DJI 无人机</span>
      <div className="dji-card">
        <div className="dji-header">
          <span className="dji-model-name">{status.drone_model}</span>
          <span className={`dji-badge ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '已连接' : '未连接'}
          </span>
        </div>

        <div className="dji-mode-label">
          {modeLabel} · {status.backend}
        </div>

        {telemetry && (
          <div className="dji-telemetry-grid">
            <MetricItem label="电量" value={`${telemetry.battery_percent.toFixed(0)}%`} />
            <MetricItem label="高度" value={`${telemetry.altitude.toFixed(1)} m`} />
            <MetricItem
              label="纬度"
              value={telemetry.latitude ? telemetry.latitude.toFixed(6) : '--'}
            />
            <MetricItem
              label="经度"
              value={telemetry.longitude ? telemetry.longitude.toFixed(6) : '--'}
            />
          </div>
        )}
      </div>
    </Card>
  )
}

function MetricItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="dji-metric">
      <div className="dji-metric-label">{label}</div>
      <div className="dji-metric-value">{value}</div>
    </div>
  )
}
