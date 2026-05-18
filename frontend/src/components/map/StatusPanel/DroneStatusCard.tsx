import { Tag } from '../../ui'
import type { TagColor } from '../../ui/Tag'

import type { DroneState } from '../../../types/simMap'

const STATUS_LABELS: Record<DroneState['status'], string> = {
  connecting: '连接中',
  ready: '待命',
  takeoff: '起飞',
  spraying: '作业中',
  returning: '返航',
  completed: '已完成',
  error: '异常',
}

const STATUS_COLORS: Record<DroneState['status'], TagColor> = {
  connecting: 'blue',
  ready: 'cyan',
  takeoff: 'amber',
  spraying: 'green',
  returning: 'orange',
  completed: 'green',
  error: 'red',
}

type DroneStatusCardProps = {
  drone: DroneState
}

export default function DroneStatusCard({ drone }: DroneStatusCardProps) {
  return (
    <section className="status-panel-card">
      <div className="status-panel-card-header">
        <span>无人机</span>
        <Tag color={STATUS_COLORS[drone.status]}>{STATUS_LABELS[drone.status]}</Tag>
      </div>
      <strong className="status-panel-primary">{drone.name}</strong>
      <span className="status-panel-muted">{drone.message || drone.id}</span>
    </section>
  )
}
