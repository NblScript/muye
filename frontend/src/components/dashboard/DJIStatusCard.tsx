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
      <div style={{ marginTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 15, fontWeight: 700 }}>{status.drone_model}</span>
          <span style={{
            fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
            background: connected ? 'rgba(90, 138, 106, 0.15)' : 'rgba(184, 112, 90, 0.15)',
            color: connected ? 'var(--accent-green)' : 'var(--accent-terracotta)',
          }}>
            {connected ? '已连接' : '未连接'}
          </span>
        </div>

        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
          {modeLabel} · {status.backend}
        </div>

        {telemetry && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
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
    <div style={{
      padding: '6px 8px',
      background: 'var(--bg-elevated)',
      borderRadius: 'var(--radius-sm)',
      fontSize: 11,
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}
