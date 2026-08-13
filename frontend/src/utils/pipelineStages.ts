import type { WorkflowEventEntry, WorkflowTaskState } from '../types/workflow'

export type StageStatus = 'done' | 'active' | 'pending'

export interface PipelineStage {
  key: string
  label: string
  status: StageStatus
  message?: string
}

const STAGE_DEFINITIONS = [
  { key: 'upload', label: '图片上传' },
  { key: 'detection', label: 'YOLO 检测' },
  { key: 'weather', label: '气象采集' },
  { key: 'decision', label: 'AI 决策' },
  { key: 'drone', label: '无人机执行' },
  { key: 'evaluation', label: '效果评估' },
] as const

export function deriveStages(task: WorkflowTaskState | null): PipelineStage[] {
  if (!task) {
    return STAGE_DEFINITIONS.map((definition) => ({ ...definition, status: 'pending' }))
  }

  const eventsByStage = new Map<string, WorkflowEventEntry[]>()
  for (const event of task.recent_events ?? []) {
    const events = eventsByStage.get(event.stage) ?? []
    events.push(event)
    eventsByStage.set(event.stage, events)
  }

  const hasStatus = (stage: string, status: string) =>
    (eventsByStage.get(stage) ?? []).some((event) => event.status === status)
  const weatherReady = Object.keys(task.weather ?? {}).length > 0
  const decisionReady = Object.keys(task.decision ?? {}).length > 0
  const currentStage = task.current_stage ?? ''

  return STAGE_DEFINITIONS.map((definition): PipelineStage => {
    let status: StageStatus = 'pending'
    let message: string | undefined

    switch (definition.key) {
      case 'upload':
        if (hasStatus('queue', 'completed') || currentStage !== '') {
          status = 'done'
          message = '图片已入队'
        } else if (hasStatus('queue', 'running')) {
          status = 'active'
          message = '上传中...'
        }
        break
      case 'detection':
        if (hasStatus('yolo', 'completed')) {
          status = 'done'
          message = eventsByStage.get('yolo')?.find((event) => event.status === 'completed')?.message
            ?? '检测完成'
        } else if (hasStatus('yolo', 'running') || currentStage === 'yolo') {
          status = 'active'
          message = '识别中...'
        }
        break
      case 'weather':
        if (weatherReady && (hasStatus('yolo', 'completed') || decisionReady)) {
          status = 'done'
          message = String((task.weather as Record<string, unknown>).summary ?? '气象数据已采集')
        } else if (hasStatus('yolo', 'running')) {
          status = 'active'
          message = '采集中...'
        }
        break
      case 'decision':
        if (decisionReady) {
          status = 'done'
          const medication = (task.decision as Record<string, unknown>)['用药'] as
            | Record<string, unknown>
            | undefined
          message = medication ? `推荐 ${String(medication['农药名称'] ?? '')}` : '决策完成'
        } else if (hasStatus('yolo', 'completed')) {
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
      case 'evaluation': {
        const evaluation = task.evaluation
        if (!evaluation?.status || evaluation.status === 'scheduled') {
          if (task.status === 'completed') {
            status = 'active'
            message = evaluation ? '等待药效发挥...' : '待评估'
          }
        } else if (evaluation.status === 'inspecting') {
          status = 'active'
          message = '复检巡飞中...'
        } else if (evaluation.status === 'passed') {
          status = 'done'
          const rate = evaluation.kill_rate == null ? '' : `${Math.round(evaluation.kill_rate * 100)}%`
          message = rate ? `杀灭率 ${rate}` : '评估通过'
        } else if (evaluation.status === 'retry_scheduled') {
          status = 'done'
          message = '效果不佳，待二次处理'
        } else if (evaluation.status === 'evaluated') {
          status = 'done'
          message = '评估完成'
        }
        break
      }
    }

    return { ...definition, status, message }
  })
}

export function derivePipelineProgress(task: WorkflowTaskState | null): number {
  if (!task) return 0
  if (task.status === 'completed') return 100

  const missionProgress = Number(task.drone?.progress ?? 0)
  const safeMissionProgress = Number.isFinite(missionProgress)
    ? Math.max(0, Math.min(100, Math.round(missionProgress)))
    : 0
  const stages = deriveStages(task)
  const completed = stages.filter((stage) => stage.status === 'done').length
  const stageProgress = Math.round((completed / Math.max(1, stages.length)) * 100)
  return Math.max(safeMissionProgress, stageProgress)
}
