import { useRef, useEffect, useState } from 'react'
import type { WorkflowEventEntry, WorkflowTaskState } from '../../types/workflow'

export type StageStatus = 'done' | 'active' | 'pending'

export interface PipelineStage {
  key: string
  label: string
  icon: React.ReactNode
  status: StageStatus
  message?: string
}

const UploadIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
)

const ScanIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 7V2h5M17 2h5v5M22 17v5h-5M7 22H2v-5" />
  </svg>
)

const CloudIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z" />
  </svg>
)

const BulbIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 18h6M10 22h4M12 2a7 7 0 017 7c0 2.38-1.19 4.47-3 5.74V17a1 1 0 01-1 1h-6a1 1 0 01-1-1v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 017-7z" />
  </svg>
)

const RocketIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z" />
    <path d="M12 15l-3-3a22 22 0 012-3.95A12.88 12.88 0 0122 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 01-4 2z" />
    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
  </svg>
)

const LoopIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="17 1 21 5 17 9" />
    <path d="M3 11V9a4 4 0 014-4h14" />
    <polyline points="7 23 3 19 7 15" />
    <path d="M21 13v2a4 4 0 01-4 4H3" />
  </svg>
)

const CheckIcon = () => (
  <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

const STAGE_DEFS: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: 'upload', label: '图片上传', icon: <UploadIcon /> },
  { key: 'detection', label: 'YOLO 检测', icon: <ScanIcon /> },
  { key: 'weather', label: '气象采集', icon: <CloudIcon /> },
  { key: 'decision', label: 'AI 决策', icon: <BulbIcon /> },
  { key: 'drone', label: '无人机执行', icon: <RocketIcon /> },
  { key: 'evaluation', label: '效果评估', icon: <LoopIcon /> },
]

export function deriveStages(task: WorkflowTaskState | null): PipelineStage[] {
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

      case 'evaluation': {
        const ev = task.evaluation
        if (!ev || !ev.status || ev.status === 'scheduled') {
          if (task.status === 'completed') {
            status = 'active'
            message = ev ? '等待药效发挥...' : '待评估'
          }
        } else if (ev.status === 'inspecting') {
          status = 'active'
          message = '复检巡飞中...'
        } else if (ev.status === 'passed') {
          status = 'done'
          const rate = ev.kill_rate != null ? `${Math.round(ev.kill_rate * 100)}%` : ''
          message = rate ? `杀灭率 ${rate}` : '评估通过'
        } else if (ev.status === 'retry_scheduled') {
          status = 'done'
          message = '效果不佳，待二次处理'
        } else if (ev.status === 'evaluated') {
          status = 'done'
          message = '评估完成'
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
  const prevStatusRef = useRef<Map<string, StageStatus>>(new Map())
  const [justCompleted, setJustCompleted] = useState<Set<string>>(new Set())

  useEffect(() => {
    const prev = prevStatusRef.current
    const newlyCompleted = new Set<string>()
    for (const stage of stages) {
      if (stage.status === 'done' && prev.get(stage.key) !== 'done') {
        newlyCompleted.add(stage.key)
      }
    }
    prevStatusRef.current = new Map(stages.map((s) => [s.key, s.status]))

    if (newlyCompleted.size > 0) {
      setJustCompleted(newlyCompleted)
      const timer = setTimeout(() => setJustCompleted(new Set()), 1400)
      return () => clearTimeout(timer)
    }
  }, [stages])

  return (
    <div className="pipeline-stepper">
      {stages.map((stage, index) => (
        <div key={stage.key} className="pipeline-step-group">
          <div className={`pipeline-step is-${stage.status}`}>
            <div className={`pipeline-step-icon ${justCompleted.has(stage.key) ? 'stage-just-completed' : ''}`}>
              {stage.status === 'done' ? (
                <span className="stage-complete-icon"><CheckIcon /></span>
              ) : stage.status === 'active' ? (
                <span className="spinner" />
              ) : (
                stage.icon
              )}
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
