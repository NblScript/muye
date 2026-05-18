import { useEffect, useState } from 'react'

import { fetchDashboardContext } from '../api/workflow'
import { Button, Card, Tag, useToast } from '../components/ui'
import type { DashboardContextResponse } from '../types/workflow'

const modeColor = (mode?: string): 'green' | 'red' | 'amber' | 'default' => {
  if (!mode) return 'default'
  const m = mode.toLowerCase()
  if (m === 'online' || m === 'running') return 'green'
  if (m === 'offline' || m === 'stopped') return 'red'
  if (m === 'sim' || m === 'simulation') return 'amber'
  return 'default'
}

export default function Settings() {
  const [context, setContext] = useState<DashboardContextResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  useEffect(() => {
    let active = true
    const loadContext = async () => {
      try {
        const result = await fetchDashboardContext()
        if (active) setContext(result)
      } catch { /* silently ignore */ }
      finally { if (active) setLoading(false) }
    }
    void loadContext()
    return () => { active = false }
  }, [])

  const handleSave = () => {
    toast.success('设置已保存（本地预览）')
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 24, fontWeight: 600 }}>系统设置</h2>

      <Card title="运行模式" style={{ marginBottom: 24 }}>
        {loading ? (
          <span className="spinner" />
        ) : context ? (
          <div className="settings-mode-grid">
            {Object.entries(context.modes).map(([key, value]) => (
              <div key={key} className="settings-mode-item">
                <span className="settings-mode-key">{key.toUpperCase()}</span>
                <Tag color={modeColor(value)}>{value}</Tag>
              </div>
            ))}
          </div>
        ) : (
          <span style={{ color: 'var(--text-secondary)' }}>无法获取运行模式</span>
        )}
      </Card>

      <Card title="应用配置">
        <form className="settings-form" onSubmit={(e) => { e.preventDefault(); handleSave() }}>
          <label className="settings-field">
            <span className="settings-label">后端 API 地址</span>
            <input className="input" defaultValue="/api" placeholder="例如: http://localhost:8000/api" />
          </label>

          <label className="settings-field">
            <span className="settings-label">刷新间隔(ms)</span>
            <input className="input" type="number" defaultValue="2000" />
          </label>

          <label className="settings-field settings-field-row">
            <span className="settings-label">启用 WebSocket</span>
            <input type="checkbox" defaultChecked className="settings-toggle" />
          </label>

          <label className="settings-field settings-field-row">
            <span className="settings-label">自动刷新</span>
            <input type="checkbox" defaultChecked className="settings-toggle" />
          </label>

          <Button variant="primary" type="submit" style={{ marginTop: 16 }}>保存设置</Button>
        </form>
      </Card>

      {toast.holder}
    </div>
  )
}
