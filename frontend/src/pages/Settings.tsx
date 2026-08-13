import { useEffect, useState } from 'react'

import { fetchHealth } from '../api/health'
import { fetchDashboardContext } from '../api/workflow'
import { Button, Card, Tag, useToast } from '../components/ui'
import { modeColor } from '../utils/dashboardUtils'
import type { HealthCheck, HealthResponse } from '../types/health'
import type { DashboardContextResponse } from '../types/workflow'

const healthLabels: Record<string, string> = {
  sqlite: 'SQLite 数据库',
  data_dir: '数据目录',
  embedded_yolo: '内嵌 YOLO 服务',
  yolo_model: 'YOLO 模型文件',
  ai_config: 'AI 决策配置',
  weather_config: '天气服务配置',
  event_bus: '事件流日志',
  rag_config: 'RAG 配置',
  px4_runtime: '无人机运行状态',
  runtime_config: '展示运行配置',
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

function formatConfigValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? '开启' : '关闭'
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
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

  const healthChecks = health?.checks ? Object.entries(health.checks) : []
  const runtimeConfig = health?.checks?.runtime_config
  const runtimeConfigItems: Array<[string, unknown]> = runtimeConfig
    ? [
        ['起飞确认', runtimeConfig.takeoff_mode],
        ['无人机后端', runtimeConfig.drone_backend],
        ['无人机执行', runtimeConfig.px4_execution_mode],
        ['天气模式', runtimeConfig.weather_mode],
        ['AI 模式', runtimeConfig.qwen_mode],
        ['RAG', runtimeConfig.rag_enabled],
        ['路由层', runtimeConfig.router_enabled],
        ['多智能体', runtimeConfig.multi_agent_enabled],
        ['YOLO 模型', runtimeConfig.yolo_active_model],
        ['YOLO 设备', runtimeConfig.yolo_device],
      ]
    : []

  return (
    <div className="page-container">
      <h2 className="page-title">系统设置</h2>

      <Card
        title="系统预检"
        className="settings-card"
        extra={(
          <Button size="sm" loading={healthLoading} onClick={() => void loadHealth()}>
            刷新
          </Button>
        )}
      >
        {healthLoading && !health ? (
          <span className="spinner" />
        ) : healthError && !health ? (
          <span className="color-error">{healthError}</span>
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

      <Card title="当前生效配置" className="settings-card">
        {runtimeConfigItems.length > 0 ? (
          <div className="settings-config-grid">
            {runtimeConfigItems.map(([label, value]) => (
              <div key={String(label)} className="settings-config-item">
                <span className="settings-config-key">{label}</span>
                <span className="settings-config-value">{formatConfigValue(value)}</span>
              </div>
            ))}
          </div>
        ) : (
          <span className="color-muted">无法获取当前生效配置</span>
        )}
      </Card>

      <Card title="运行模式" className="settings-card">
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
          <span className="color-muted">无法获取运行模式</span>
        )}
      </Card>

      <Card title="应用配置说明">
        <div className="settings-config-notes">
          <p>运行配置由启动脚本和环境文件统一管理，不在页面内修改：</p>
          <ul>
            <li>演示环境：<code>.env.demo</code>（模板 <code>.env.demo.example</code>）</li>
            <li>生产环境：<code>.env.production</code>（模板 <code>.env.production.example</code>）</li>
            <li>无人机参数：<code>config/drone_config.json</code></li>
            <li>检测模型：<code>config/yolo_config.yaml</code> · 决策模型：<code>config/model_config.yaml</code></li>
          </ul>
          <p className="color-muted">修改配置后请重启对应服务；上方「当前生效配置」实时展示后端实际读取到的值。</p>
        </div>
      </Card>

      {toast.holder}
    </div>
  )
}
