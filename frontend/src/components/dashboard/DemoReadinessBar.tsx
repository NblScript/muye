import { Tag } from '../ui'
import type { TagColor } from '../ui/Tag'
import type { DemoReadinessResponse, WorkflowTaskState } from '../../types/workflow'

type Props = {
  connected: boolean
  workflowLoading: boolean
  workflowError?: string | null
  latestTask?: WorkflowTaskState | null
  qwenMode?: string
  px4Running: boolean
  readiness?: DemoReadinessResponse | null
}

type ReadinessItem = {
  key: string
  label: string
  value: string
  color: TagColor
}

const STATUS_COLOR: Record<string, TagColor> = {
  ok: 'green',
  warning: 'amber',
  error: 'red',
}

const CHECK_ORDER = [
  'backend',
  'websocket',
  'latest_task',
  'rag',
  'qwen',
  'multi_agent',
  'px4',
  'drone',
]

function taskHasDecision(task?: WorkflowTaskState | null): boolean {
  const medication = task?.decision?.['用药']
  return Boolean(medication && typeof medication === 'object' && Object.keys(medication).length > 0)
}

function droneStatusLabel(status?: string): string {
  const normalized = String(status ?? '').toLowerCase()
  if (!normalized) return '待命'
  if (normalized === 'completed') return '完成'
  if (normalized === 'pending_confirmation') return '待确认'
  if (normalized === 'spraying' || normalized === 'running') return '执行中'
  if (normalized === 'error' || normalized === 'failed') return '异常'
  return String(status)
}

export default function DemoReadinessBar({
  connected,
  workflowLoading,
  workflowError,
  latestTask,
  qwenMode,
  px4Running,
  readiness,
}: Props) {
  const hasTask = Boolean(latestTask?.request_id)
  const hasRag = Boolean(latestTask?.rag_context)
  const hasDecision = taskHasDecision(latestTask)
  const activeExperts = latestTask?.rag_context?.consultation_detail?.active_count ?? 0
  const droneStatus = String(latestTask?.drone?.status ?? '')
  const droneError = ['error', 'failed'].includes(droneStatus.toLowerCase())

  const fallbackItems: ReadinessItem[] = [
    {
      key: 'backend',
      label: '后端',
      value: workflowError ? '异常' : workflowLoading ? '加载中' : '在线',
      color: workflowError ? 'red' : workflowLoading ? 'amber' : 'green',
    },
    {
      key: 'websocket',
      label: 'WebSocket',
      value: connected ? '实时' : '轮询',
      color: connected ? 'green' : 'amber',
    },
    {
      key: 'latest_task',
      label: '最新任务',
      value: hasTask ? latestTask!.request_id.slice(0, 8) : '等待',
      color: hasTask ? 'green' : 'amber',
    },
    {
      key: 'rag',
      label: 'RAG',
      value: hasRag ? '已检索' : '等待',
      color: hasRag ? 'green' : 'amber',
    },
    {
      key: 'qwen',
      label: 'LLM',
      value: hasDecision ? qwenMode ?? '已决策' : '等待',
      color: hasDecision ? 'green' : 'amber',
    },
    {
      key: 'multi_agent',
      label: '多智能体',
      value: activeExperts > 0 ? `${activeExperts} 位专家` : '未触发',
      color: activeExperts > 0 ? 'green' : 'amber',
    },
    {
      key: 'px4',
      label: '无人机',
      value: px4Running ? '运行中' : '待命',
      color: px4Running ? 'green' : 'amber',
    },
    {
      key: 'drone',
      label: '无人机',
      value: droneStatusLabel(droneStatus),
      color: droneError ? 'red' : droneStatus ? 'green' : 'amber',
    },
  ]
  const readinessItems: ReadinessItem[] | null = readiness
    ? CHECK_ORDER
      .map((key) => {
        const item = readiness.checks[key]
        if (item) {
          return {
            key,
            label: item.label,
            value: item.detail,
            color: STATUS_COLOR[item.status] ?? 'default',
          }
        }
        return fallbackItems.find((fallback) => fallback.key === key)
      })
      .filter((item): item is ReadinessItem => Boolean(item))
    : null
  const items = readinessItems && readinessItems.length > 0 ? readinessItems : fallbackItems
  const statusLabel = readiness?.status === 'ready'
    ? '链路就绪'
    : readiness?.status === 'blocked'
      ? '演示阻断'
      : readiness?.status === 'degraded'
        ? '降级可演示'
        : workflowError
          ? '需要排查'
          : '链路可观测'
  const issues = readiness?.issues ?? []

  return (
    <section className="demo-readiness-strip" aria-label="演示链路状态">
      <div className="demo-readiness-header">
        <span className="panel-label">演示链路状态</span>
        <strong>{statusLabel}</strong>
        {readiness && (
          <span className="demo-readiness-summary">
            正常 {readiness.summary.ok} / 风险 {readiness.summary.warning} / 异常 {readiness.summary.error}
          </span>
        )}
      </div>
      <div className="demo-readiness-list">
        {items.map((item) => (
          <div key={item.label} className="demo-readiness-item">
            <span>{item.label}</span>
            <Tag color={item.color}>{item.value}</Tag>
          </div>
        ))}
      </div>
      {issues.length > 0 && (
        <div className="demo-readiness-issues">
          {issues.slice(0, 3).map((issue) => (
            <div key={issue.key} className={`demo-readiness-issue is-${issue.status}`}>
              <div className="demo-readiness-issue-head">
                <strong>{issue.label}</strong>
                <Tag color={STATUS_COLOR[issue.status] ?? 'default'}>{issue.detail}</Tag>
              </div>
              {issue.reason && (
                <div className="demo-readiness-issue-row">
                  <span>原因</span>
                  <p>{issue.reason}</p>
                </div>
              )}
              {issue.impact && (
                <div className="demo-readiness-issue-row">
                  <span>影响</span>
                  <p>{issue.impact}</p>
                </div>
              )}
              {issue.system_action && (
                <div className="demo-readiness-issue-row">
                  <span>系统处理</span>
                  <p>{issue.system_action}</p>
                </div>
              )}
              {issue.human_action && (
                <div className="demo-readiness-issue-row">
                  <span>人工动作</span>
                  <p>{issue.human_action}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
