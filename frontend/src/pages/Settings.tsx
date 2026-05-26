import { useEffect, useState } from 'react'

import { fetchHealth } from '../api/health'
import { fetchDashboardContext } from '../api/workflow'
import { Button, Card, Tag, useToast } from '../components/ui'
import type { HealthCheck, HealthResponse } from '../types/health'
import type { DashboardContextResponse } from '../types/workflow'

const modeColor = (mode?: string): 'green' | 'red' | 'amber' | 'default' => {
  if (!mode) return 'default'
  const m = mode.toLowerCase()
  if (m === 'online' || m === 'running') return 'green'
  if (m === 'offline' || m === 'stopped') return 'red'
  if (m === 'sim' || m === 'simulation') return 'amber'
  return 'default'
}

const healthLabels: Record<string, string> = {
  sqlite: 'SQLite 数据库',
  data_dir: '数据目录',
  embedded_yolo: '内嵌 YOLO 服务',
  yolo_model: 'YOLO 模型文件',
  ai_config: 'AI 决策配置',
  weather_config: '天气服务配置',
  event_bus: '事件流日志',
  rag_config: 'RAG 配置',
  px4_runtime: 'PX4 运行状态',
  runtime_config: '演示运行配置',
}

function healthColor(status?: string): 'green' | 'red' | 'amber' | 'default' {
  if (status === 'ok') return 'green'
  if (status === 'error') return 'red'
  if (status === 'skipped') return 'amber'
  return 'default'
}

function formatHealthDetail(check: HealthCheck): string {
  if (typeof check.detail === 'string' && check.detail) return check.detail
  const candidates = [
    check.path,
    check.model_path,
    check.detect_url,
    check.mode,
    check.qwen_mode,
    check.px4_execution_mode,
  ]
  const value = candidates.find((item) => typeof item === 'string' && item)
  if (value) return String(value)

  const flags = Object.entries(check)
    .filter(([key, value]) => key !== 'status' && typeof value !== 'object')
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value)}`)
  return flags.join(' · ') || '无附加信息'
}

export default function Settings() {
  const [context, setContext] = useState<DashboardContextResponse | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [healthLoading, setHealthLoading] = useState(true)
  const [healthError, setHealthError] = useState<string | null>(null)
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

  const loadHealth = async () => {
    setHealthLoading(true)
    try {
      const result = await fetchHealth()
      setHealth(result)
      setHealthError(null)
    } catch (error) {
      setHealthError(error instanceof Error ? error.message : '健康检查失败')
    } finally {
      setHealthLoading(false)
    }
  }

  useEffect(() => {
    void loadHealth()
    const timer = setInterval(() => void loadHealth(), 10000)
    return () => clearInterval(timer)
  }, [])

  const handleSave = () => {
    toast.success('设置已保存（本地预览）')
  }

  const healthChecks = health?.checks ? Object.entries(health.checks) : []

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 24, fontWeight: 600 }}>系统设置</h2>

      <Card
        title="系统预检"
        style={{ marginBottom: 24 }}
        extra={(
          <Button size="sm" loading={healthLoading} onClick={() => void loadHealth()}>
            刷新
          </Button>
        )}
      >
        {healthLoading && !health ? (
          <span className="spinner" />
        ) : healthError && !health ? (
          <span style={{ color: 'var(--accent-red)' }}>{healthError}</span>
        ) : (
          <div className="settings-health-list">
            <div className="settings-health-summary">
              <span>整体状态</span>
              <Tag color={healthColor(health?.status)}>{health?.status ?? '-'}</Tag>
            </div>
            {healthChecks.map(([key, check]) => (
              <div key={key} className="settings-health-row">
                <div className="settings-health-name">{healthLabels[key] ?? key}</div>
                <div className="settings-health-detail">{formatHealthDetail(check)}</div>
                <Tag color={healthColor(check.status)}>{check.status}</Tag>
              </div>
            ))}
          </div>
        )}
      </Card>

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
