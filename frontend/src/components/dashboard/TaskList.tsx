import { Card, List, Space, Tag, Typography } from 'antd'
import { statusColor } from '../../utils/dashboardUtils'
import type { TaskRecord } from '../../types/dashboard.types'

interface TaskListProps {
  title?: string
  tasks: TaskRecord[]
  emptyText?: string
}

export default function TaskList({ title = '当前任务 / 最近任务', tasks, emptyText = '当前没有可展示的任务队列' }: TaskListProps) {
  return (
    <Card bordered={false} className="dashboard-card task-card" title={title}>
      <List
        itemLayout="vertical"
        locale={{ emptyText }}
        dataSource={tasks}
        renderItem={(item) => (
          <List.Item className="task-item">
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <div className="task-topline">
                <Typography.Text className="task-id">{item.id}</Typography.Text>
                <div className="task-tag-group">
                  {item.isCurrent ? <Tag color="cyan">当前</Tag> : null}
                  <Tag color={statusColor(item.status)}>{item.status}</Tag>
                </div>
              </div>

              <div className="task-name">{item.droneName}</div>
              <div className="task-field">{item.fieldName}</div>

              <div className="task-meta">
                <Typography.Text className="task-meta-text">农药：{item.pesticideName}</Typography.Text>
                <Typography.Text className="task-meta-text">进度：{item.progress}%</Typography.Text>
              </div>

              <div className="task-meta">
                <Typography.Text className="task-meta-text">面积：{item.sprayAreaText}</Typography.Text>
                <Typography.Text className="task-meta-text">更新：{item.updatedAt}</Typography.Text>
              </div>

              <div className="task-progress-track">
                <div className="task-progress-bar" style={{ width: `${item.progress}%` }} />
              </div>
            </Space>
          </List.Item>
        )}
      />
    </Card>
  )
}
