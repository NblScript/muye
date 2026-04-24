/** Task record status type */
export type TaskStatus = '执行中' | '待起飞' | '返航中'

/** Task record for displaying in task list */
export interface TaskRecord {
  id: string
  droneName: string
  fieldName: string
  status: TaskStatus
  progress: number
  pesticideName: string
  sprayAreaText: string
  updatedAt: string
  isCurrent: boolean
}

/** Pest summary for displaying detection results */
export interface PestSummary {
  labels: string[]
  summary: string
}

/** History filter parameters */
export interface HistoryFilterParams {
  limit: number
  status: string
  search: string
}
