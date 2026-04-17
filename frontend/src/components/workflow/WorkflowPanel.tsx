import { Alert, Empty, Spin, Tag, Typography } from 'antd'

import type { WorkflowStateResponse, WorkflowTaskState, WorkflowTimelineEntry } from '../../types/workflow'

const { Text } = Typography

const DRONE_STAGE_LABELS: Record<string, string> = {
  submitted: '任务提交',
  queued: '任务接收',
  connecting: '链路连接',
  connected: '飞控连接',
  ready: '定位就绪',
  uploaded: '航线上传',
  armed: '解锁待飞',
  takeoff: '起飞',
  enroute: '前往作业区',
  spraying: '喷洒执行',
  returning: '返航',
  completed: '任务完成',
  error: '异常',
  failed: '失败',
}

const DRONE_STAGE_SEQUENCES: Record<string, string[]> = {
  px4: ['connecting', 'connected', 'ready', 'uploaded', 'armed', 'takeoff', 'spraying', 'completed'],
  virtual_api: ['submitted', 'queued', 'takeoff', 'enroute', 'spraying', 'returning', 'completed'],
  simulated: ['queued', 'takeoff', 'spraying', 'completed'],
  generic: ['submitted', 'queued', 'connecting', 'connected', 'ready', 'uploaded', 'armed', 'takeoff', 'enroute', 'spraying', 'returning', 'completed'],
}

function formatTimestamp(value?: string | null) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function inferDroneBackend(task: WorkflowTaskState) {
  const drone = task.drone ?? {}
  const timeline = task.drone_timeline ?? []
  const taskId = String(drone.task_id ?? '').toLowerCase()
  const statuses = new Set<string>()

  for (const item of timeline) {
    const status = String(item.status ?? '').toLowerCase()
    if (status) {
      statuses.add(status)
    }
  }

  const currentStatus = String(drone.status ?? '').toLowerCase()
  if (currentStatus) {
    statuses.add(currentStatus)
  }

  if (taskId.startsWith('px4-') || ['connecting', 'connected', 'ready', 'uploaded', 'armed'].some((item) => statuses.has(item))) {
    return { key: 'px4', label: 'PX4 SITL' }
  }

  if (taskId.startsWith('vd-') || ['submitted', 'enroute', 'returning'].some((item) => statuses.has(item))) {
    return { key: 'virtual_api', label: '虚拟无人机 API' }
  }

  if (taskId.startsWith('sim-')) {
    return { key: 'simulated', label: '内置模拟' }
  }

  return { key: 'generic', label: '无人机链路' }
}

function buildStageSequence(task: WorkflowTaskState, backendKey: string) {
  const sequence = [...(DRONE_STAGE_SEQUENCES[backendKey] ?? DRONE_STAGE_SEQUENCES.generic)]
  const currentStatus = String(task.drone?.status ?? '').toLowerCase()

  for (const item of task.drone_timeline ?? []) {
    const status = String(item.status ?? '').toLowerCase()
    if (status && !sequence.includes(status)) {
      sequence.push(status)
    }
  }

  if (currentStatus && !sequence.includes(currentStatus)) {
    sequence.push(currentStatus)
  }

  return sequence
}

function stageState(sequence: string[], timeline: Map<string, WorkflowTimelineEntry>, currentStatus: string, status: string) {
  if (status === currentStatus) {
    return 'current'
  }

  if (timeline.has(status)) {
    return 'done'
  }

  const currentIndex = sequence.indexOf(currentStatus)
  const statusIndex = sequence.indexOf(status)
  if (currentIndex >= 0 && statusIndex >= 0 && statusIndex < currentIndex) {
    return 'done'
  }

  return 'pending'
}

function statusTagColor(status: string) {
  if (status === 'completed') {
    return 'success'
  }
  if (status === 'error' || status === 'failed') {
    return 'error'
  }
  if (status === 'running' || status === 'spraying') {
    return 'processing'
  }
  return 'default'
}

type WorkflowPanelProps = {
  data: WorkflowStateResponse | null
  loading?: boolean
  error?: string | null
}

export default function WorkflowPanel({ data, loading = false, error = null }: WorkflowPanelProps) {
  if (loading && !data) {
    return (
      <div className="workflow-loading">
        <Spin />
      </div>
    )
  }

  if (error && !data) {
    return <Alert type="error" message="任务流程加载失败" description={error} showIcon />
  }

  if (!data) {
    return <Empty description="暂无任务流程数据" />
  }

  const task = data.latest_task
  const backend = inferDroneBackend(task)
  const currentStatus = String(task.drone?.status ?? '').toLowerCase()
  const timelineByStatus = new Map<string, WorkflowTimelineEntry>()
  for (const item of task.drone_timeline ?? []) {
    const status = String(item.status ?? '').toLowerCase()
    if (status) {
      timelineByStatus.set(status, item)
    }
  }

  const sequence = buildStageSequence(task, backend.key)
  const progressValue = Math.max(0, Math.min(100, Number(task.drone?.progress ?? 0)))
  const instruction = task.drone?.instruction ?? {}
  const routePoints = Array.isArray(instruction.飞行路径) ? instruction.飞行路径.length : 0
  const coveragePoints = Array.isArray(instruction.覆盖区域?.coordinates) ? instruction.覆盖区域?.coordinates.length : 0

  return (
    <div className="workflow-shell">
      <div className="workflow-topline">
        <div>
          <Text className="workflow-kicker">Mission Command</Text>
          <div className="workflow-title">{task.drone?.message || task.message || '等待无人机任务状态'}</div>
          <div className="workflow-subtitle">
            请求 {task.request_id.slice(0, 12)} · 最近更新 {formatTimestamp(task.updated_at)} · 当前阶段 {DRONE_STAGE_LABELS[currentStatus] || currentStatus || '-'}
          </div>
        </div>

        <div className="workflow-badge-group">
          <Tag color={statusTagColor(task.status)}>{task.status}</Tag>
          <Tag color="cyan">{backend.label}</Tag>
          <Tag color={data.source === 'event_bus' ? 'geekblue' : 'gold'}>{data.source === 'event_bus' ? '实时事件' : '仿真回退'}</Tag>
        </div>
      </div>

      <div className="workflow-stage-grid">
        {sequence.map((status) => {
          const item = timelineByStatus.get(status)
          const state = stageState(sequence, timelineByStatus, currentStatus, status)
          return (
            <div key={status} className={`workflow-stage-chip is-${state}`}>
              <div className="workflow-stage-status">
                {state === 'current' ? '当前' : state === 'done' ? '已达成' : '待执行'}
              </div>
              <div className="workflow-stage-name">{DRONE_STAGE_LABELS[status] || status}</div>
              <div className="workflow-stage-meta">
                {item?.message || '等待进入该阶段'}
                <br />
                {formatTimestamp(item?.timestamp)}
              </div>
            </div>
          )
        })}
      </div>

      <div className="workflow-progress-track">
        <div className="workflow-progress-fill" style={{ width: `${progressValue}%` }} />
      </div>

      <div className="workflow-meta-grid">
        <div className="workflow-meta-card">
          <div className="workflow-meta-label">飞控任务号</div>
          <div className="workflow-meta-value">{task.drone?.task_id || '-'}</div>
        </div>
        <div className="workflow-meta-card">
          <div className="workflow-meta-label">当前航点</div>
          <div className="workflow-meta-value">{task.drone?.current_waypoint_index ?? 0}</div>
        </div>
        <div className="workflow-meta-card">
          <div className="workflow-meta-label">航点数量</div>
          <div className="workflow-meta-value">{routePoints}</div>
        </div>
        <div className="workflow-meta-card">
          <div className="workflow-meta-label">覆盖顶点</div>
          <div className="workflow-meta-value">{coveragePoints}</div>
        </div>
        <div className="workflow-meta-card">
          <div className="workflow-meta-label">飞行高度</div>
          <div className="workflow-meta-value">{instruction.高度 ?? '-'}</div>
        </div>
        <div className="workflow-meta-card">
          <div className="workflow-meta-label">事件总数</div>
          <div className="workflow-meta-value">{data.event_count}</div>
        </div>
      </div>

      <div className="workflow-log-header">
        <Text className="panel-label">Recent Events</Text>
      </div>
      <div className="workflow-log-box">
        {task.recent_events.length === 0 ? (
          <div className="workflow-log-empty">暂无事件</div>
        ) : (
          task.recent_events.slice().reverse().map((event, index) => (
            <div key={`${event.timestamp}-${event.stage}-${index}`} className="workflow-log-line">
              <span className="workflow-log-time">{formatTimestamp(event.timestamp)}</span>
              <span className="workflow-log-stage">{event.stage}</span>
              <span className="workflow-log-status">{event.status}</span>
              <span className="workflow-log-message">{event.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
