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

  return (
    <Card className="dashboard-card decision-explain-card">
      <span className="label-uppercase">决策依据</span>
      <div className="explain-root">

        {/* 虫害检测 */}
        {detections.length > 0 && (
          <div className="explain-section">
            <div className="explain-section-title">虫害检测</div>
            <div className="explain-detection-tags">
              {detections.map((d, i) => {
                const conf = d.confidence ?? 0
                const haz = hazardLevel(conf)
                return (
                  <span key={i} className="explain-detection-tag" style={{ borderLeftColor: haz.color }}>
                    <span className="tag-label">{d.pest_type ?? '未知'}</span>
                    <span className="tag-meta">
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
          <div className="explain-section">
            <div className="explain-section-title">天气因素</div>
            <div className="explain-weather-row">
              {weather.temperature != null && <span>温度 {String(weather.temperature)}°C</span>}
              {weather.humidity != null && <span>湿度 {String(weather.humidity)}%</span>}
              {(weather.wind_speed ?? weather.windSpeed) != null && <span>风速 {String(weather.wind_speed ?? weather.windSpeed)}m/s</span>}
            </div>
            <div className={`explain-weather-suit ${suit.ok ? 'ok' : 'warn'}`}>
              {suit.text}
            </div>
          </div>
        )}

        {/* 合规推理链 */}
        {compliance && (
          <div className="explain-section">
            <div className="explain-compliance-header">
              <div className="explain-section-title">农药安全合规推理链</div>
              <div className="explain-compliance-score">
                <Tag color={complianceDisplay.color}>{complianceDisplay.label}</Tag>
                <span className="explain-compliance-score-value">
                  {compliance.score}/100
                </span>
              </div>
            </div>

            {/* Five-check chain */}
            <div className="explain-check-list">
              {(compliance.checks ?? []).map((check) => {
                const checkColor = check.status === 'passed' ? 'var(--accent-green)' : check.status === 'blocked' ? 'var(--accent-red)' : 'var(--accent-amber)'
                const dot = check.status === 'passed' ? '●' : check.status === 'blocked' ? '✕' : '▲'
                return (
                  <div key={check.rule} className="explain-check-row">
                    <span className="explain-check-dot" style={{ color: checkColor }}>{dot}</span>
                    <span className="explain-check-name">{check.name ?? check.rule}</span>
                    <span className="explain-check-msg">{check.message}</span>
                    {check.evidence && check.evidence.length > 0 && (
                      <span className="explain-check-evidence">
                        {check.evidence.map((e) => e.title).join(', ')}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Summary + Execution policy */}
            <div className="explain-footer">
              <span className="explain-footer-summary">{compliance.summary ?? ''}</span>
              {compliance.execution_policy && (
                <Tag color={compliance.execution_policy.takeoff_mode === 'auto' ? 'green' : compliance.execution_policy.takeoff_mode === 'blocked' ? 'red' : 'amber'}>
                  {compliance.execution_policy.takeoff_mode === 'auto' ? '自动执行' : compliance.execution_policy.takeoff_mode === 'blocked' ? '已拦截' : '需人工确认'}
                </Tag>
              )}
            </div>

            {/* Alternatives */}
            {compliance.alternatives && compliance.alternatives.length > 0 && (
              <div className="explain-alternatives">
                <div className="explain-alternatives-title">替代方案推荐</div>
                <div className="explain-alt-list">
                  {compliance.alternatives.map((alt, i) => (
                    <div key={i} className="explain-alt-row">
                      <span className="explain-alt-index">{i + 1}.</span>
                      <span className="explain-alt-name">{alt.pesticide}</span>
                      <span className="explain-alt-reason">{alt.reason}</span>
                      <span className="explain-alt-score">{alt.score}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* RAG 引用 */}
        {rag && ((rag.pesticides?.length ?? 0) + (rag.historical_cases?.length ?? 0) + (rag.knowledge?.length ?? 0) > 0) && (
          <div className="explain-section">
            <div className="explain-section-title">RAG 知识引用</div>
            <div className="explain-rag-tags">
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
          <div className="explain-section">
            <div className="explain-section-title">安全提示</div>
            <div className="explain-safety-tips">
              {safetyTips.slice(0, 3).map((tip, i) => (
                <div key={i} className="explain-safety-tip">{tip}</div>
              ))}
              {safetyTips.length > 3 && (
                <div className="explain-safety-more">+{safetyTips.length - 3} 条</div>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
