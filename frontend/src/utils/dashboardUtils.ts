import type { WorkflowDetectionEntry } from '../types/workflow'
import type { TaskRecord, TaskStatus, PestSummary } from '../types/dashboard.types'
import type { DashboardTaskEntry } from '../types/workflow'

/** Convert backend status string to frontend TaskStatus */
export function toTaskStatus(status: string): TaskStatus {
  if (status === 'spraying' || status === '作业中') {
    return '执行中'
  }
  if (status === 'returning' || status === '返航') {
    return '返航中'
  }
  return '待起飞'
}

/** Safely cast unknown to Record<string, unknown> */
export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

/** Format datetime string for display (zh-CN locale) */
export function formatDateTime(value?: string | null): string {
  if (!value) {
    return '--'
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

/** Format current time for display (zh-CN locale with year) */
export function formatNow(value: Date): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(value)
}

/** Map DashboardTaskEntry to TaskRecord */
export function mapTaskEntry(item: DashboardTaskEntry): TaskRecord {
  return {
    id: item.request_id,
    droneName: item.drone_label,
    fieldName: item.field_name,
    status: toTaskStatus(item.status),
    progress: Number(item.progress ?? 0),
    pesticideName: item.pesticide_name ?? '--',
    sprayAreaText: item.spray_area_mu !== null && item.spray_area_mu !== undefined ? `${item.spray_area_mu} 亩` : '--',
    updatedAt: formatDateTime(item.updated_at),
    isCurrent: item.is_current,
  }
}

/** Get color for task status tag */
export function statusColor(status: TaskStatus): string {
  if (status === '执行中') {
    return 'green'
  }
  if (status === '返航中') {
    return 'gold'
  }
  return 'blue'
}

/** Get color for mode tag */
export function modeColor(value?: string): string {
  if (value === 'mock') {
    return 'gold'
  }
  if (value === 'px4') {
    return 'cyan'
  }
  if (value === 'virtual_api') {
    return 'geekblue'
  }
  if (value === 'simulated') {
    return 'purple'
  }
  return 'green'
}

/** Summarize pest detections into labels and summary text */
export function summarizePests(detections: WorkflowDetectionEntry[]): PestSummary {
  if (detections.length === 0) {
    return {
      labels: [],
      summary: '未识别到害虫目标',
    }
  }

  const counts = new Map<string, number>()
  for (const detection of detections) {
    const pestType = String(detection.pest_type ?? 'unknown')
    counts.set(pestType, (counts.get(pestType) ?? 0) + 1)
  }

  const ordered = [...counts.entries()].sort((left, right) => {
    if (right[1] !== left[1]) {
      return right[1] - left[1]
    }
    return left[0].localeCompare(right[0], 'zh-CN')
  })

  const labels = ordered.map(([name, count]) => `${name} × ${count}`)
  return {
    labels,
    summary: labels.join('，'),
  }
}

/** Safely format metric value with optional suffix */
export function safeMetric(value: unknown, suffix = ''): string {
  if (value === null || value === undefined || value === '') {
    return '--'
  }
  return `${String(value)}${suffix}`
}
