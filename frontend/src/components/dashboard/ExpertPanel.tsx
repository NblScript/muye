import type { ConsultationDetail, RagContext } from '../../types/workflow'

interface ExpertPanelProps {
  ragContext?: RagContext
}

const EXPERT_META: Record<string, { label: string; provider: string; avatar: string; colorClass: string; focus: string }> = {
  entomologist: {
    label: '昆虫学家',
    provider: 'Qwen',
    avatar: '虫',
    colorClass: 'qwen',
    focus: '昆虫分类与危害评估',
  },
  agronomist: {
    label: '农学家',
    provider: 'DeepSeek',
    avatar: '农',
    colorClass: 'deepseek',
    focus: '作物阶段与农艺约束',
  },
  plant_protection: {
    label: '植保专家',
    provider: 'Xiaomi MiMo',
    avatar: '植',
    colorClass: 'xiaomi',
    focus: '药剂安全与合规复核',
  },
  pesticide_specialist: {
    label: '植保专家',
    provider: 'Xiaomi MiMo',
    avatar: '植',
    colorClass: 'xiaomi',
    focus: '药剂安全与合规复核',
  },
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

const PATH_TEXT: Record<string, string> = {
  expert: '专家快速路径',
  escalated: '专家异常升级',
  multi_agent: '多智能体会诊',
}

function pct(value: number | undefined) {
  return `${Math.round((value ?? 0) * 100)}%`
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
  const failedCount = failedRoles.length

  const expertEntries = Object.entries(experts)
  if (expertEntries.length === 0) return null

  const decisionPath = ragContext?.decision_path ?? 'multi_agent'
  const pathLabel: Record<string, { text: string; cls: string }> = {
    expert: { text: '专家快速路径', cls: 'expert' },
    escalated: { text: '专家异常 → 多智能体升级', cls: 'escalated' },
    multi_agent: { text: `${activeCount} 位专家参与`, cls: 'multi_agent' },
  }
  const pathInfo = pathLabel[decisionPath] ?? pathLabel.multi_agent
  const winner = Object.entries(voteDist).sort(([, a], [, b]) => b - a)[0]
  const winningPesticide = winner?.[0] ?? ''
  const winningExpert = expertEntries.find(
    ([role, info]) => info['农药名称'] === winningPesticide && !failedRoles.includes(role),
  ) ?? expertEntries.find(([role]) => !failedRoles.includes(role))

  return (
    <div className="expert-panel-wrapper">
      <div className="panel-header">
        <span className="panel-title">多智能体专家会诊</span>
        <span className={`path-badge ${pathInfo.cls}`}>{pathInfo.text}</span>
      </div>
      <div className="panel-body">
        <div className="consultation-metrics">
          <div className="consultation-metric">
            <span>决策路径</span>
            <strong>{PATH_TEXT[decisionPath] ?? decisionPath}</strong>
          </div>
          <div className="consultation-metric">
            <span>参与专家</span>
            <strong>{activeCount} 位</strong>
          </div>
          <div className="consultation-metric">
            <span>会诊置信度</span>
            <strong>{pct(confidence)}</strong>
          </div>
          <div className="consultation-metric">
            <span>一致性</span>
            <strong>{AGREEMENT_LABEL[agreement] ?? agreement}</strong>
          </div>
          <div className={`consultation-metric ${failedCount > 0 ? 'is-warning' : ''}`}>
            <span>失败专家</span>
            <strong>{failedCount} 位</strong>
          </div>
        </div>

        {/* Expert Cards */}
        <div className="expert-panel-grid">
          {expertEntries.map(([role, info]) => {
            const meta = EXPERT_META[role] ?? {
              label: role,
              provider: '未知',
              avatar: '?',
              colorClass: 'qwen',
              focus: '专家推理',
            }
            const isFailed = failedRoles.includes(role)
            const pesticideName = info['农药名称'] || ''
            const voteWeight = voteDist[pesticideName] ?? 0
            const isAdopted = Boolean(winningPesticide && pesticideName === winningPesticide && !isFailed)

            return (
              <div key={role} className={`expert-card ${isFailed ? 'is-failed' : ''} ${isAdopted ? 'is-adopted' : ''}`}>
                <div className="expert-card-header">
                  <div className={`expert-avatar ${meta.colorClass}`}>{meta.avatar}</div>
                  <div className="expert-card-title">
                    <div className="expert-name">{info.name || meta.label}</div>
                    <div className="expert-provider">模型 {meta.provider}</div>
                  </div>
                  {isAdopted && <span className="expert-adopted-badge">采用</span>}
                </div>
                <div className="expert-focus">{meta.focus}</div>
                <div className="expert-detail-grid">
                  <div>
                    <span>权重</span>
                    <strong>权重 {pct(info.weight)}</strong>
                  </div>
                  <div>
                    <span>推荐</span>
                    <strong>{isFailed ? '--' : pesticideName || '推理中'}</strong>
                  </div>
                  <div>
                    <span>用量</span>
                    <strong>{isFailed ? '--' : info['总量'] ? `总量 ${info['总量']}` : '--'}</strong>
                  </div>
                </div>
                <div className="expert-opinion">
                  {isFailed
                    ? '调用失败，已降级处理'
                    : `${info.name || meta.label}建议使用${pesticideName || '待定药剂'}，本方案投票占比 ${pct(voteWeight)}。`}
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
                  <span className="vote-dist-name">{name}</span>
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
        {winningExpert && (
          <div className="consultation-final">
            <span className="consultation-label">最终采用</span>
            <div className="consultation-final-result">
              <div>
                <span className="final-result-name">{winningExpert[1]['农药名称']}</span>
                {winningExpert[1]['总量'] && (
                  <span className="final-result-detail">
                    {winningExpert[1]['总量']}
                  </span>
                )}
              </div>
              <span className="final-result-source">
                由{winningExpert[1].name || EXPERT_META[winningExpert[0]]?.label || '专家'}方案进入执行
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
