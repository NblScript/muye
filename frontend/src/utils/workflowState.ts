import type { WorkflowTaskState } from '../types/workflow'

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function isWorkflowTaskState(value: unknown): value is WorkflowTaskState {
  if (!isRecord(value)) return false

  return typeof value.request_id === 'string'
    && typeof value.current_stage === 'string'
    && typeof value.status === 'string'
    && typeof value.message === 'string'
    && isRecord(value.field)
    && Array.isArray(value.detections)
    && isRecord(value.weather)
    && isRecord(value.spray_summary)
    && isRecord(value.decision)
    && isRecord(value.drone)
    && Array.isArray(value.drone_timeline)
    && Array.isArray(value.recent_events)
}

/**
 * Return a task only when it came from the real event stream and has the
 * minimum shape required by the command-screen view model.
 */
export function extractEventBusTask(value: unknown): WorkflowTaskState | null {
  if (!isRecord(value) || value.source !== 'event_bus') return null
  return isWorkflowTaskState(value.latest_task) ? value.latest_task : null
}

/**
 * WebSocket pushes deliberately use workflow_state=null when one snapshot
 * fails to build. Keep the last valid task so a transient backend error does
 * not clear and redraw the heatmap.
 */
export function retainLatestEventBusTask(
  current: WorkflowTaskState | null,
  incomingWorkflowState: unknown,
): WorkflowTaskState | null {
  return extractEventBusTask(incomingWorkflowState) ?? current
}
