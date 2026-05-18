import { Card, Tag } from '../ui'
import type { TagColor } from '../ui/Tag'
import { statusColor } from '../../utils/dashboardUtils'
import type { TaskRecord } from '../../types/dashboard.types'

interface TaskListProps {
  title?: string
  tasks: TaskRecord[]
  emptyText?: string
}

export default function TaskList({ title = '当前任务 / 最近任务', tasks, emptyText = '当前没有可展示的任务队列' }: TaskListProps) {
  return (
    <Card className="dashboard-card task-card" title={title}>
      {tasks.length === 0 ? (
        <div className="task-empty">{emptyText}</div>
      ) : (
        tasks.map((item) => (
          <div key={item.id} className="task-item">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
              <div className="task-topline">
                <span className="task-id">{item.id}</span>
                <div className="task-tag-group">
                  {item.isCurrent ? <Tag color="cyan">当前</Tag> : null}
                  <Tag color={statusColor(item.status) as TagColor}>{item.status}</Tag>
                </div>
              </div>

              <div className="task-name">{item.droneName}</div>
              <div className="task-field">{item.fieldName}</div>

              <div className="task-meta">
                <span className="task-meta-text">农药：{item.pesticideName}</span>
                <span className="task-meta-text">进度：{item.progress}%</span>
              </div>

              <div className="task-meta">
                <span className="task-meta-text">面积：{item.sprayAreaText}</span>
                <span className="task-meta-text">更新：{item.updatedAt}</span>
              </div>

              <div className="task-progress-track">
                <div className="task-progress-bar" style={{ width: `${item.progress}%` }} />
              </div>
            </div>
          </div>
        ))
      )}
    </Card>
  )
}
