import { describe, expect, it } from 'vitest'

import type { WorkflowTaskState } from '../src/types/workflow'
import {
  extractEventBusTask,
  retainLatestEventBusTask,
} from '../src/utils/workflowState'

function makeTask(requestId: string): WorkflowTaskState {
  return {
    request_id: requestId,
    current_stage: 'drone',
    status: 'running',
    message: '变量喷洒中',
    field: { field_name: '虚拟试验田' },
    detections: [{ pest_type: 'aphid', confidence: 0.91 }],
    weather: { wind_speed: 2.8, humidity: 63 },
    spray_summary: {},
    decision: {},
    drone: { status: 'spraying' },
    drone_timeline: [],
    recent_events: [],
  }
}

function eventBusState(task: WorkflowTaskState) {
  return {
    source: 'event_bus',
    event_count: 1,
    latest_task: task,
    recent_tasks: [],
  }
}

describe('workflow state stabilization', () => {
  it('extracts a structurally valid real workflow task', () => {
    const task = makeTask('req-live')

    expect(extractEventBusTask(eventBusState(task))).toBe(task)
  })

  it('rejects legacy fallback and malformed workflow snapshots', () => {
    const task = makeTask('req-fallback')

    expect(extractEventBusTask({ ...eventBusState(task), source: 'fallback' })).toBeNull()
    expect(extractEventBusTask({
      ...eventBusState(task),
      latest_task: { ...task, detections: 'invalid' },
    })).toBeNull()
    expect(extractEventBusTask(null)).toBeNull()
  })

  it('retains the last real task across null, fallback, and malformed pushes', () => {
    const current = makeTask('req-stable')

    expect(retainLatestEventBusTask(current, null)).toBe(current)
    expect(retainLatestEventBusTask(current, {
      ...eventBusState(makeTask('req-demo')),
      source: 'fallback',
    })).toBe(current)
    expect(retainLatestEventBusTask(current, { source: 'event_bus', latest_task: {} })).toBe(current)
  })

  it('replaces the retained task when a new valid event-bus snapshot arrives', () => {
    const current = makeTask('req-old')
    const next = makeTask('req-next')

    expect(retainLatestEventBusTask(current, eventBusState(next))).toBe(next)
  })
})
