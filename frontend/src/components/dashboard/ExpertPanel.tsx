import type { ConsultationDetail, RagContext } from '../../types/workflow'

interface ExpertPanelProps {
  ragContext?: RagContext
}

const EXPERT_META: Record<string, { label: string; provider: string; avatar: string; colorClass: string }> = {
  entomologist: { label: '昆虫学家', provider: 'Qwen', avatar: '虫', colorClass: 'qwen' },
  agronomist: { label: '农学家', provider: 'DeepSeek', avatar: '农', colorClass: 'deepseek' },
  plant_protection: { label: '植保专家', provider: 'Xiaomi MiMo', avatar: '植', colorClass: 'xiaomi' },
}

const AGREEMENT_LABEL: Record<string, string> = {
  unanimous: '一致通过',
  majority: '多数通过',
  divided: '意见分歧',
  single_expert: '单专家',
  all_failed: '全部失败',
}

const AGREEMENT_COLOR: Record<string, string> = {
  unanimous: 'var(--accent-green)',
  majority: 'var(--accent-amber)',
  divided: 'var(--accent-red)',
  single_expert: 'var(--text-muted)',
  all_failed: 'var(--accent-red)',
}

function ConfidenceRing({ value, color }: { value: number; color: string }) {
  const radius = 16
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - value)

  return (
    <div className="consultation-ring">
      <svg width="40" height="40" viewBox="0 0 40 40">
        <circle className="consultation-ring-bg" cx="20" cy="20" r={radius} />
        <circle
          className="consultation-ring-fill"
          cx="20"
          cy="20"
          r={radius}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="consultation-ring-text">{Math.round(value * 100)}%</span>
    </div>
  )
}

export default function ExpertPanel({ ragContext }: ExpertPanelProps) {
  const detail: ConsultationDetail | undefined = ragContext?.consultation_detail
  if (!detail) return null

  const experts = detail.experts ?? {}
  const failedRoles = detail.failed_roles ?? []
  const confidence = ragContext?.confidence ?? 0
  const agreement = ragContext?.agreement ?? ''
  const voteDist = detail.vote_distribution ?? {}
  const activeCount = detail.active_count ?? Object.keys(experts).length

  const expertEntries = Object.entries(experts)
  if (expertEntries.length === 0) return null

  const decisionPath = ragContext?.decision_path ?? 'multi_agent'
  const pathLabel: Record<string, { text: string; cls: string }> = {
    expert: { text: '专家快速路径', cls: 'expert' },
    escalated: { text: '专家异常 → 多智能体升级', cls: 'escalated' },
    multi_agent: { text: `${activeCount} 位专家参与`, cls: 'multi_agent' },
  }
  const pathInfo = pathLabel[decisionPath] ?? pathLabel.multi_agent

  return (
    <div className="expert-panel-wrapper">
      <div className="panel-header">
        <span className="panel-title">多智能体专家会诊</span>
        <span className={`path-badge ${pathInfo.cls}`}>{pathInfo.text}</span>
      </div>
      <div className="panel-body">
        {/* Expert Cards */}
        <div className="expert-panel-grid">
          {expertEntries.map(([role, info]) => {
            const meta = EXPERT_META[role] ?? { label: role, provider: '未知', avatar: '?', colorClass: 'qwen' }
            const isFailed = failedRoles.includes(role)
            const voteWeight = voteDist[info.name] ?? 0

            return (
              <div key={role} className={`expert-card ${isFailed ? 'is-failed' : ''}`}>
                <div className="expert-card-header">
                  <div className={`expert-avatar ${meta.colorClass}`}>{meta.avatar}</div>
                  <div>
                    <div className="expert-name">{info.name || meta.label}</div>
                    <div className="expert-provider">{meta.provider}</div>
                  </div>
                </div>
                <div className="expert-opinion">
                  {isFailed ? '调用失败，已降级处理' : info['农药名称'] || '推理中...'}
                </div>
                {!isFailed && (
                  <div className="expert-vote-bar">
                    <div className="expert-vote-track">
                      <div
                        className={`expert-vote-fill ${meta.colorClass}`}
                        style={{ width: `${Math.max(voteWeight * 100, 2)}%` }}
                      />
                    </div>
                    <span className="expert-vote-pct">{(voteWeight * 100).toFixed(0)}%</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Consultation Summary */}
        <div className="consultation-summary">
          <span className="consultation-label">会诊结论</span>
          <div className="consultation-agreement">
            <ConfidenceRing value={confidence} color={AGREEMENT_COLOR[agreement] ?? 'var(--accent-cyan)'} />
            <div>
              <div className="consultation-agreement-text">
                {AGREEMENT_LABEL[agreement] ?? agreement}
              </div>
              <div className="consultation-agreement-desc">
                {failedRoles.length > 0 && `${failedRoles.length} 位专家降级 · `}
                置信度 {(confidence * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        </div>

        {/* Vote Distribution Bar */}
        {Object.keys(voteDist).length > 1 && (
          <div className="vote-distribution">
            <span className="consultation-label">投票分布</span>
            {Object.entries(voteDist).map(([name, weight]) => {
              const colorClass = expertEntries.find(([, info]) => info.name === name)
                ? (EXPERT_META[expertEntries.find(([, info]) => info.name === name)![0]]?.colorClass ?? 'qwen')
                : 'qwen'
              return (
                <div key={name} className="expert-vote-bar">
                  <span style={{ fontSize: 12, minWidth: 80, color: 'var(--text-secondary)' }}>{name}</span>
                  <div className="expert-vote-track">
                    <div
                      className={`expert-vote-fill ${colorClass}`}
                      style={{ width: `${weight * 100}%` }}
                    />
                  </div>
                  <span className="expert-vote-pct">{(weight * 100).toFixed(0)}%</span>
                </div>
              )
            })}
          </div>
        )}

        {/* Final Recommendation */}
        {expertEntries.length > 0 && (() => {
          const winner = Object.entries(voteDist).sort(([, a], [, b]) => b - a)[0]
          const winnerExpert = expertEntries.find(([, info]) => info.name === winner?.[0])
          return winnerExpert ? (
            <div className="consultation-final">
              <span className="consultation-label">最终方案</span>
              <div className="consultation-final-result">
                <span style={{ fontWeight: 700, fontSize: 14 }}>{winnerExpert[1]['农药名称']}</span>
                {winnerExpert[1]['总量'] && (
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 8 }}>
                    {winnerExpert[1]['总量']}
                  </span>
                )}
              </div>
            </div>
          ) : null
        })()}
      </div>
    </div>
  )
}
