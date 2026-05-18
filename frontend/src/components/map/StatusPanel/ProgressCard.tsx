import { Progress } from '../../ui'

import type { MissionState, TrajectoryState } from '../../../types/simMap'

type ProgressCardProps = {
  mission: MissionState
  trajectory: TrajectoryState
}

function clampProgress(value: number) {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
}

export default function ProgressCard({ mission, trajectory }: ProgressCardProps) {
  const progress = clampProgress(mission.progress)

  return (
    <section className="status-panel-card">
      <div className="status-panel-card-header">
        <span>任务进度</span>
        <strong>{progress.toFixed(0)}%</strong>
      </div>
      <Progress percent={progress} size="small" strokeColor="var(--accent-green)" />
      <div className="status-panel-grid status-panel-grid-compact">
        <div>
          <span>航点</span>
          <strong>{mission.current_waypoint}/{mission.total_waypoints}</strong>
        </div>
        <div>
          <span>里程</span>
          <strong>{trajectory.total_distance.toFixed(1)} m</strong>
        </div>
      </div>
    </section>
  )
}
