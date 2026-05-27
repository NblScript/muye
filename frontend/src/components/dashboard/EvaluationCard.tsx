import type { EvaluationResult } from '../../types/workflow'

interface EvaluationCardProps {
  evaluation: EvaluationResult | undefined
  onRequestCancel?: (requestId: string) => void
}

const STATUS_LABELS: Record<string, string> = {
  scheduled: '已安排复检',
  inspecting: '复检巡飞中',
  evaluated: '评估完成',
  retry_scheduled: '待二次打药',
  passed: '评估通过',
}

export default function EvaluationCard({ evaluation }: EvaluationCardProps) {
  if (!evaluation || !evaluation.status) return null

  const {
    status,
    kill_rate: killRate,
    pre_pest_count: preCount,
    post_pest_count: postCount,
    kill_rate_threshold: threshold = 0.7,
    action_time_hours: actionHours,
    notes,
    message,
  } = evaluation

  const ratePct = killRate != null ? Math.round(killRate * 100) : null
  const thresholdPct = Math.round(threshold * 100)
  const passed = killRate != null && killRate >= threshold
  const active = status === 'scheduled' || status === 'inspecting'

  return (
    <section className="drawer-section">
      <h4 className={`drawer-section-title is-${passed ? 'green' : 'red'}`}>
        药效评估
      </h4>

      <div className="evaluation-card">
        <div className="evaluation-status-row">
          <span className={`evaluation-status-dot is-${active ? 'active' : passed ? 'passed' : 'failed'}`} />
          <span className="evaluation-status-label">{STATUS_LABELS[status] ?? status}</span>
          {message && <span className="evaluation-message">{message}</span>}
        </div>

        {actionHours != null && (
          <div className="evaluation-meta">
            预计见效时间: {actionHours}h
          </div>
        )}

        {ratePct != null && (
          <div className="evaluation-rate-block">
            <div className="evaluation-rate-bar-track">
              <div
                className={`evaluation-rate-bar-fill is-${passed ? 'passed' : 'failed'}`}
                style={{ width: `${Math.min(ratePct, 100)}%` }}
              />
              <div
                className="evaluation-rate-threshold"
                style={{ left: `${thresholdPct}%` }}
              />
            </div>
            <div className="evaluation-rate-labels">
              <span className={`evaluation-rate-value is-${passed ? 'passed' : 'failed'}`}>
                杀灭率 {ratePct}%
              </span>
              <span className="evaluation-rate-threshold-label">
                阈值 {thresholdPct}%
              </span>
            </div>
          </div>
        )}

        {preCount != null && postCount != null && (
          <div className="evaluation-counts">
            <span>防治前: <strong>{preCount}</strong> 只</span>
            <span>防治后: <strong>{postCount}</strong> 只</span>
          </div>
        )}

        {notes && <div className="evaluation-notes">{notes}</div>}
      </div>
    </section>
  )
}
