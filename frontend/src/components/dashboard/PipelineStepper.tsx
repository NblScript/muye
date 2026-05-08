import {
  BulbOutlined,
  CheckCircleFilled,
  CloudOutlined,
  LoadingOutlined,
  RocketOutlined,
  ScanOutlined,
  UploadOutlined,
} from '@ant-design/icons'

import type { WorkflowEventEntry, WorkflowTaskState } from '../../types/workflow'

export type StageStatus = 'done' | 'active' | 'pending'

interface PipelineStage {
  key: string
  label: string
  icon: React.ReactNode
  status: StageStatus
  message?: string
}

const STAGE_DEFS: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: 'upload', label: '图片上传', icon: <UploadOutlined /> },
  { key: 'detection', label: 'YOLO 检测', icon: <ScanOutlined /> },
  { key: 'weather', label: '气象采集', icon: <CloudOutlined /> },
  { key: 'decision', label: 'AI 决策', icon: <BulbOutlined /> },
  { key: 'drone', label: '无人机执行', icon: <RocketOutlined /> },
]

function deriveStages(task: WorkflowTaskState | null): PipelineStage[] {
  if (!task) {
    return STAGE_DEFS.map((def) => ({ ...def, status: 'pending' as StageStatus }))
  }

  const events = task.recent_events ?? []
  const byStage = new Map<string, WorkflowEventEntry[]>()
  for (const ev of events) {
    const list = byStage.get(ev.stage) ?? []
    list.push(ev)
    byStage.set(ev.stage, list)
  }

  const hasCompleted = (stage: string) =>
    (byStage.get(stage) ?? []).some((e) => e.status === 'completed')
  const hasRunning = (stage: string) =>
    (byStage.get(stage) ?? []).some((e) => e.status === 'running')

  const weatherReady = Object.keys(task.weather ?? {}).length > 0
  const decisionReady = Object.keys(task.decision ?? {}).length > 0
  const currentStage = task.current_stage ?? ''

  return STAGE_DEFS.map((def) => {
    let status: StageStatus = 'pending'
    let message: string | undefined

    switch (def.key) {
      case 'upload':
        if (hasCompleted('queue') || currentStage !== '') {
          status = 'done'
          message = '图片已入队'
        } else if (hasRunning('queue')) {
          status = 'active'
          message = '上传中...'
        }
        break

      case 'detection':
        if (hasCompleted('yolo')) {
          status = 'done'
          const last = byStage.get('yolo')?.find((e) => e.status === 'completed')
          message = last?.message ?? '检测完成'
        } else if (hasRunning('yolo') || currentStage === 'yolo') {
          status = 'active'
          message = '识别中...'
        }
        break

      case 'weather':
        if (weatherReady && (hasCompleted('yolo') || decisionReady)) {
          status = 'done'
          message = (task.weather as Record<string, unknown>).summary as string ?? '气象数据已采集'
        } else if (hasRunning('yolo') && !hasCompleted('yolo')) {
          // weather runs in parallel with yolo
          status = 'active'
          message = '采集中...'
        }
        break

      case 'decision':
        if (decisionReady) {
          status = 'done'
          const med = (task.decision as Record<string, unknown>)['用药'] as Record<string, unknown> | undefined
          message = med ? `推荐 ${String(med['农药名称'] ?? '')}` : '决策完成'
        } else if (hasCompleted('yolo') && !decisionReady) {
          status = 'active'
          message = '推理中...'
        }
        break

      case 'drone': {
        const droneStatus = String(task.drone?.status ?? '').toLowerCase()
        if (task.status === 'completed' || droneStatus === 'completed') {
          status = 'done'
          message = '作业完成'
        } else if (droneStatus && droneStatus !== 'pending_confirmation') {
          status = 'active'
          message = task.drone?.message ?? '执行中...'
        } else if (droneStatus === 'pending_confirmation' || decisionReady) {
          status = 'active'
          message = '等待起飞确认'
        }
        break
      }
    }

    return { ...def, status, message }
  })
}

interface PipelineStepperProps {
  task: WorkflowTaskState | null
}

export default function PipelineStepper({ task }: PipelineStepperProps) {
  const stages = deriveStages(task)

  return (
    <div className="pipeline-stepper">
      {stages.map((stage, index) => (
        <div key={stage.key} className="pipeline-step-group">
          <div className={`pipeline-step is-${stage.status}`}>
            <div className="pipeline-step-icon">
              {stage.status === 'done' ? <CheckCircleFilled /> : stage.status === 'active' ? <LoadingOutlined /> : stage.icon}
            </div>
            <div className="pipeline-step-label">{stage.label}</div>
            {stage.message && <div className="pipeline-step-message">{stage.message}</div>}
          </div>
          {index < stages.length - 1 && (
            <div className={`pipeline-connector is-${stages[index + 1].status === 'done' || stages[index + 1].status === 'active' ? 'filled' : 'empty'}`} />
          )}
        </div>
      ))}
    </div>
  )
}
