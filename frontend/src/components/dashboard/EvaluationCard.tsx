import type { EvaluationResult, MissionDetail } from '../../types/workflow'

interface EvaluationCardProps {
  evaluation: EvaluationResult | undefined
  mission?: MissionDetail | undefined
  onRequestCancel?: (requestId: string) => void
}

const STATUS_LABELS: Record<string, string> = {
  scheduled: '已安排复检',
  inspecting: '复检巡飞中',
  evaluated: '评估完成',
  retry_scheduled: '待二次打药',
  passed: '评估通过',
}

const MISSION_STATUS_LABELS: Record<string, string> = {
  active: '进行中',
  completed: '已完成',
  failed: '未达标',
  cancelled: '已取消',
}

const ITER_STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  spraying: '喷洒中',
  sprayed: '喷洒完成',
  inspecting: '巡检中',
  evaluated: '已评估',
  passed: '达标',
  failed: '未达标',
}

export default function EvaluationCard({ evaluation, mission }: EvaluationCardProps) {
  if (mission && mission.status) {
    return <MissionTimeline mission={mission} />
  }
  if (!evaluation || !evaluation.status) return null
  return <SingleEvaluation evaluation={evaluation} />
}

function MissionTimeline({ mission }: { mission: MissionDetail }) {
  const threshold = mission.kill_rate_threshold ?? 0.9
  const thresholdPct = Math.round(threshold * 100)
  const finalRate = mission.final_kill_rate
  const finalPct = finalRate != null ? Math.round(finalRate * 100) : null
  const passed = finalRate != null && finalRate >= threshold
  const isActive = mission.status === 'active'

  return (
    <section className="drawer-section">
      <h4 className={`drawer-section-title is-${passed ? 'green' : 'red'}`}>
        任务闭环
      </h4>

      <div className="evaluation-card">
        <div className="evaluation-status-row">
          <span className={`evaluation-status-dot is-${isActive ? 'active' : passed ? 'passed' : 'failed'}`} />
          <span className="evaluation-status-label">
            {MISSION_STATUS_LABELS[mission.status] ?? mission.status}
          </span>
          {mission.pest_types?.length > 0 && (
            <span className="evaluation-message">
              {mission.pest_types.join('、')}
            </span>
          )}
        </div>

        <div className="evaluation-meta">
          目标杀灭率: {thresholdPct}% | 最大轮次: {mission.max_iterations}
          {mission.pesticide_name && ` | 用药: ${mission.pesticide_name}`}
        </div>

        {finalPct != null && (
          <div className="evaluation-rate-block">
            <div className="evaluation-rate-bar-track">
              <div
                className={`evaluation-rate-bar-fill is-${passed ? 'passed' : 'failed'}`}
                style={{ width: `${Math.min(finalPct, 100)}%` }}
              />
              <div
                className="evaluation-rate-threshold"
                style={{ left: `${thresholdPct}%` }}
              />
            </div>
            <div className="evaluation-rate-labels">
              <span className={`evaluation-rate-value is-${passed ? 'passed' : 'failed'}`}>
                最终杀灭率 {finalPct}%
              </span>
              <span className="evaluation-rate-threshold-label">
                阈值 {thresholdPct}%
              </span>
            </div>
          </div>
        )}

        {mission.iterations?.length > 0 && (
          <div className="mission-timeline">
            {mission.iterations.map((iter) => (
              <MissionIterationRow key={iter.iteration_id} iteration={iter} threshold={threshold} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function MissionIterationRow({
  iteration,
  threshold,
}: {
  iteration: MissionDetail['iterations'][number]
  threshold: number
}) {
  const ratePct = iteration.kill_rate != null ? Math.round(iteration.kill_rate * 100) : null
  const passed = iteration.kill_rate != null && iteration.kill_rate >= threshold
  const isActive = ['spraying', 'inspecting'].includes(iteration.status)

  return (
    <div className="mission-iteration-row">
      <div className="mission-iteration-header">
        <span className={`evaluation-status-dot is-${isActive ? 'active' : passed ? 'passed' : iteration.status === 'failed' ? 'failed' : 'neutral'}`} />
        <span className="mission-iteration-title">
          第 {iteration.iteration_number} 轮
        </span>
        <span className="mission-iteration-status">
          {ITER_STATUS_LABELS[iteration.status] ?? iteration.status}
        </span>
        {ratePct != null && (
          <span className={`mission-iteration-rate is-${passed ? 'passed' : 'failed'}`}>
            {ratePct}%
          </span>
        )}
      </div>
      {iteration.pre_pest_count != null && iteration.post_pest_count != null && (
        <div className="mission-iteration-counts">
          防治前 {iteration.pre_pest_count} 只 → 防治后 {iteration.post_pest_count} 只
        </div>
      )}
    </div>
  )
}

function SingleEvaluation({ evaluation }: { evaluation: EvaluationResult }) {
  const {
    status,
    kill_rate: killRate,
    pre_pest_count: preCount,
    post_pest_count: postCount,
    kill_rate_threshold: threshold = 0.9,
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
