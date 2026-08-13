import { act, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Panel from '../src/assets/screen/panel'
import { buildScreenViewModel } from '../src/assets/screen/model'
import { useConfigStore } from '../src/assets/screen/store'
import type { FooterActions } from '../src/assets/screen/panel/footer'
import type { WorkflowTaskState } from '../src/types/workflow'

function makeTask(): WorkflowTaskState {
  return {
    request_id: 'req-panel-entrance',
    current_stage: 'drone',
    status: 'running',
    message: '正在执行变量喷洒',
    updated_at: '2026-08-03T08:00:00Z',
    field: {
      field_name: '郑州高标准农田 01',
      province: '河南省',
      city: '郑州市',
      crop_cycle: { crop_name: '小麦' },
      area_mu: 12.6,
    },
    detections: [
      { pest_type: 'aphid', confidence: 0.92, position: { x1: 120, y1: 80, x2: 180, y2: 140, coordinate_space: 'image_pixel', image_width: 640, image_height: 480 } },
    ],
    weather: { summary: '晴', temperature: 27.4, humidity: 61, wind_speed: 3.2 },
    spray_summary: { spray_area_mu: 12.6 },
    decision: {
      用药: { 农药名称: '吡虫啉', 浓度: '10%', 配比: '1:1500', 总量: '1.2 L' },
      农事建议: ['避开正午高温时段'],
    },
    compliance: {
      status: 'passed',
      score: 92,
      summary: '合规检查通过',
      checks: [],
      blocking_reasons: [],
      warnings: [],
      execution_policy: { takeoff_mode: 'auto', reason: '符合自动执行条件' },
      alternatives: [],
    },
    drone: { task_id: 'px4-001', status: 'spraying', message: '变量喷洒中', progress: 62 },
    drone_timeline: [],
    recent_events: [],
  }
}

const restartSpies: ReturnType<typeof vi.fn>[] = []
const reverseSpies: ReturnType<typeof vi.fn>[] = []

vi.mock('../src/assets/screen/hooks/useMoveTo', () => ({
  default: () => {
    const restart = vi.fn()
    const reverse = vi.fn()
    restartSpies.push(restart)
    reverseSpies.push(reverse)
    return { ref: { current: null }, restart, reverse }
  },
}))

const actions: FooterActions = {
  onUpload: vi.fn(),
  onRefresh: vi.fn(),
  onToggleCloud: vi.fn(),
  onToggleBar: vi.fn(),
  onToggleRotation: vi.fn(),
  onToggleHeat: vi.fn(),
  onToggleMode: vi.fn(),
  onConfirmTakeoff: vi.fn(),
}

describe('Panel entrance', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    restartSpies.length = 0
    reverseSpies.length = 0
    useConfigStore.getState().reset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts the entrance as soon as the 3D map completes', () => {
    const model = buildScreenViewModel(makeTask(), undefined, 55, true)
    render(<Panel model={model} actions={actions} />)

    expect(restartSpies.some((spy) => spy.mock.calls.length > 0)).toBe(false)

    act(() => {
      useConfigStore.setState({ mapPlayComplete: true })
    })

    expect(restartSpies.filter((spy) => spy.mock.calls.length > 0).length).toBeGreaterThanOrEqual(8)
  })

  it('forces the entrance after 4s even when the map never completes', () => {
    const model = buildScreenViewModel(makeTask(), undefined, 55, true)
    render(<Panel model={model} actions={actions} />)

    expect(restartSpies.some((spy) => spy.mock.calls.length > 0)).toBe(false)

    act(() => {
      vi.advanceTimersByTime(4000)
    })

    expect(restartSpies.filter((spy) => spy.mock.calls.length > 0).length).toBeGreaterThanOrEqual(8)

    // 幂等：地图稍后完成时不得重复触发入场动画
    const calledAfterFallback = restartSpies.map((spy) => spy.mock.calls.length)
    act(() => {
      useConfigStore.setState({ mapPlayComplete: true })
    })
    expect(restartSpies.map((spy) => spy.mock.calls.length)).toEqual(calledAfterFallback)
  })
})
