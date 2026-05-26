import { Card, Tag } from '../ui'
import type { WorkflowTaskState } from '../../types/workflow'

function hazardLevel(confidence: number): { label: string; color: string } {
  if (confidence >= 0.8) return { label: '高', color: 'var(--accent-red)' }
  if (confidence >= 0.5) return { label: '中', color: 'var(--accent-amber)' }
  return { label: '低', color: 'var(--accent-green)' }
}

function weatherSuitability(weather: Record<string, unknown>): { text: string; ok: boolean } {
  const windSpeed = Number(weather.wind_speed ?? weather.windSpeed ?? 0)
  const humidity = Number(weather.humidity ?? 0)

  if (windSpeed > 5) return { text: `风速 ${windSpeed}m/s 过高，建议暂缓施药`, ok: false }
  if (windSpeed > 3) return { text: `风速 ${windSpeed}m/s 偏高，注意漂移`, ok: true }
  if (humidity < 40) return { text: `湿度 ${humidity}% 偏低，注意药液蒸发`, ok: true }
  return { text: '天气条件适宜施药', ok: true }
}

function complianceStatus(status?: string): { label: string; color: 'green' | 'amber' | 'red' | 'default' } {
  if (status === 'passed') return { label: '已通过', color: 'green' }
  if (status === 'blocked') return { label: '已拦截', color: 'red' }
  if (status === 'warning') return { label: '风险提示', color: 'amber' }
  return { label: '待审核', color: 'default' }
}

interface Props {
  task: WorkflowTaskState | null
}

export default function DecisionExplainPanel({ task }: Props) {
  if (!task) return null

  const detections = task.detections ?? []
  const weather = (task.weather ?? {}) as Record<string, unknown>
  const decision = (task.decision ?? {}) as Record<string, unknown>
  const medication = (decision['用药'] ?? {}) as Record<string, unknown>
  const rag = task.rag_context
  const compliance = task.compliance
  const hasData = detections.length > 0 || Object.keys(weather).length > 0 || Object.keys(medication).length > 0

  if (!hasData) return null

  const suit = weatherSuitability(weather)
  const safetyTips = Array.isArray(medication['安全提示']) ? (medication['安全提示'] as string[]) : []
  const complianceDisplay = complianceStatus(compliance?.status)
  const complianceMessages = compliance?.blocking_reasons.length
    ? compliance.blocking_reasons
    : compliance?.warnings ?? []

  return (
    <Card className="dashboard-card">
      <span className="label-uppercase">决策依据</span>
      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>

        {/* 虫害检测 */}
        {detections.length > 0 && (
          <div style={{ padding: '8px 10px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>虫害检测</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {detections.map((d, i) => {
                const conf = d.confidence ?? 0
                const haz = hazardLevel(conf)
                return (
                  <span key={i} style={{
                    fontSize: 12, padding: '3px 8px',
                    background: 'var(--bg-surface)', borderRadius: 4,
                    borderLeft: `3px solid ${haz.color}`,
                  }}>
                    <span style={{ fontWeight: 600 }}>{d.pest_type ?? '未知'}</span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>
                      {(conf * 100).toFixed(0)}% · 危害{haz.label}
                    </span>
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* 天气因素 */}
        {Object.keys(weather).length > 0 && (
          <div style={{ padding: '8px 10px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>天气因素</div>
            <div style={{ fontSize: 12, display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 4 }}>
              {weather.temperature != null && <span>温度 {String(weather.temperature)}°C</span>}
              {weather.humidity != null && <span>湿度 {String(weather.humidity)}%</span>}
              {(weather.wind_speed ?? weather.windSpeed) != null && <span>风速 {String(weather.wind_speed ?? weather.windSpeed)}m/s</span>}
            </div>
            <div style={{ fontSize: 11, color: suit.ok ? 'var(--accent-green)' : 'var(--accent-terracotta)' }}>
              {suit.text}
            </div>
          </div>
        )}

        {/* 合规审核 */}
        {compliance && (
          <div style={{ padding: '8px 10px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>合规审核</div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <Tag color={complianceDisplay.color}>{complianceDisplay.label}</Tag>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                  {compliance.score}分
                </span>
              </div>
            </div>
            {complianceMessages.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {complianceMessages.slice(0, 3).map((message, i) => (
                  <div key={i} style={{ fontSize: 12, color: 'var(--text-primary)', paddingLeft: 8, borderLeft: '2px solid var(--accent-amber)' }}>
                    {message}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--accent-green)' }}>
                作物、防治对象、毒性与天气规则均通过
              </div>
            )}
          </div>
        )}

        {/* RAG 引用 */}
        {rag && ((rag.pesticides?.length ?? 0) + (rag.historical_cases?.length ?? 0) + (rag.knowledge?.length ?? 0) > 0) && (
          <div style={{ padding: '8px 10px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>RAG 知识引用</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {rag.pesticides && rag.pesticides.length > 0 && (
                <Tag color="green">{rag.pesticides.length} 条农药</Tag>
              )}
              {rag.historical_cases && rag.historical_cases.length > 0 && (
                <Tag color="amber">{rag.historical_cases.length} 条案例</Tag>
              )}
              {rag.knowledge && rag.knowledge.length > 0 && (
                <Tag color="default">{rag.knowledge.length} 条知识</Tag>
              )}
            </div>
          </div>
        )}

        {/* 安全提示 */}
        {safetyTips.length > 0 && (
          <div style={{ padding: '8px 10px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>安全提示</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {safetyTips.slice(0, 3).map((tip, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--text-primary)', paddingLeft: 8, borderLeft: '2px solid var(--accent-terracotta)' }}>
                  {tip}
                </div>
              ))}
              {safetyTips.length > 3 && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>+{safetyTips.length - 3} 条</div>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
