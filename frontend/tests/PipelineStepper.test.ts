import { describe, it, expect } from 'vitest'
import { deriveStages } from '../src/components/dashboard/PipelineStepper'
import type { WorkflowTaskState } from '../src/types/workflow'

function makeTask(overrides: Partial<WorkflowTaskState> = {}): WorkflowTaskState {
  return {
    request_id: 'test-001',
    current_stage: '',
    status: '',
    message: '',
    field: {},
    detections: [],
    weather: {},
    spray_summary: {},
    decision: {},
    drone: {},
    drone_timeline: [],
    recent_events: [],
    ...overrides,
  }
}

describe('deriveStages', () => {
  it('returns all pending when task is null', () => {
    const stages = deriveStages(null)
    expect(stages).toHaveLength(5)
    expect(stages.every((s) => s.status === 'pending')).toBe(true)
  })

  it('marks upload as done when queue completed', () => {
    const task = makeTask({
      recent_events: [
        { timestamp: '', stage: 'queue', status: 'completed', message: '入队完成' },
      ],
    })
    const stages = deriveStages(task)
    expect(stages[0].status).toBe('done')
    expect(stages[0].message).toBe('图片已入队')
  })

  it('marks upload as active when queue running', () => {
    const task = makeTask({
      recent_events: [
        { timestamp: '', stage: 'queue', status: 'running', message: '' },
      ],
    })
    const stages = deriveStages(task)
    expect(stages[0].status).toBe('active')
  })

  it('marks detection as done when yolo completed', () => {
    const task = makeTask({
      recent_events: [
        { timestamp: '', stage: 'queue', status: 'completed', message: '' },
        { timestamp: '', stage: 'yolo', status: 'completed', message: '发现 3 个目标' },
      ],
    })
    const stages = deriveStages(task)
    expect(stages[1].status).toBe('done')
    expect(stages[1].message).toBe('发现 3 个目标')
  })

  it('marks detection as active when yolo running', () => {
    const task = makeTask({
      recent_events: [
        { timestamp: '', stage: 'yolo', status: 'running', message: '' },
      ],
    })
    const stages = deriveStages(task)
    expect(stages[1].status).toBe('active')
  })

  it('marks weather as done when weather data exists and yolo completed', () => {
    const task = makeTask({
      weather: { summary: '晴天 25℃' },
      recent_events: [
        { timestamp: '', stage: 'yolo', status: 'completed', message: '' },
      ],
    })
    const stages = deriveStages(task)
    expect(stages[2].status).toBe('done')
  })

  it('marks decision as done when decision data exists', () => {
    const task = makeTask({
      decision: { '用药': { '农药名称': '吡虫啉' } },
    })
    const stages = deriveStages(task)
    expect(stages[3].status).toBe('done')
    expect(stages[3].message).toContain('吡虫啉')
  })

  it('marks decision as active when yolo done but no decision', () => {
    const task = makeTask({
      recent_events: [
        { timestamp: '', stage: 'yolo', status: 'completed', message: '' },
      ],
    })
    const stages = deriveStages(task)
    expect(stages[3].status).toBe('active')
  })

  it('marks drone as done when task completed', () => {
    const task = makeTask({
      status: 'completed',
      decision: { '用药': {} },
    })
    const stages = deriveStages(task)
    expect(stages[4].status).toBe('done')
    expect(stages[4].message).toBe('作业完成')
  })

  it('marks drone as active with pending_confirmation', () => {
    const task = makeTask({
      drone: { status: 'pending_confirmation' },
      decision: { '用药': {} },
    })
    const stages = deriveStages(task)
    expect(stages[4].status).toBe('active')
    expect(stages[4].message).toBe('等待起飞确认')
  })

  it('handles full pipeline progression', () => {
    const task = makeTask({
      weather: { summary: '晴' },
      decision: { '用药': { '农药名称': '噻虫嗪' } },
      drone: { status: 'spraying', progress: 50 },
      recent_events: [
        { timestamp: '', stage: 'queue', status: 'completed', message: '' },
        { timestamp: '', stage: 'yolo', status: 'completed', message: '' },
      ],
    })
    const stages = deriveStages(task)
    expect(stages[0].status).toBe('done')
    expect(stages[1].status).toBe('done')
    expect(stages[2].status).toBe('done')
    expect(stages[3].status).toBe('done')
    expect(stages[4].status).toBe('active')
  })
})
