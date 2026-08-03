import { describe, expect, it } from 'vitest'
import { buildScreenViewModel } from '../src/assets/screen/model'
import type { WorkflowTaskState } from '../src/types/workflow'

function makeTask(overrides: Partial<WorkflowTaskState> = {}): WorkflowTaskState {
  return {
    request_id: 'req-screen-model',
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
      { pest_type: 'aphid', confidence: 0.88, position: { x1: 420, y1: 260, x2: 490, y2: 330, coordinate_space: 'image_pixel', image_width: 640, image_height: 480 } },
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
    rag_context: {
      confidence: 0.86,
      decision_path: 'multi_agent',
      consultation_detail: { active_count: 3 },
    },
    drone: {
      task_id: 'px4-001',
      status: 'spraying',
      message: '变量喷洒中',
      progress: 62,
      current_waypoint_index: 4,
      instruction: {
        飞行路径: [[113.6, 34.7], [113.7, 34.8]],
        覆盖区域: { coordinates: [[113.58, 34.68], [113.72, 34.68], [113.72, 34.82], [113.58, 34.82]] },
        高度: 8,
        速度: 5,
        喷洒速率: '0.8 L/min',
        density_grid: [
          { row: 0, col: 0, density: 0.82, bounds: [[113.59, 34.69], [113.64, 34.74]] },
        ],
        density_metadata: {
          source: 'yolo_bbox',
          density_kind: 'relative_detection_weight',
          accepted_detection_count: 2,
          is_simulated: false,
        },
      },
      position: { latitude_deg: 34.76, longitude_deg: 113.65 },
    },
    drone_timeline: [],
    recent_events: [
      { timestamp: '2026-08-03T08:00:00Z', stage: 'detection', status: 'completed', message: '识别完成' },
      { timestamp: '2026-08-03T08:01:00Z', stage: 'evaluation', status: 'evaluated', message: '复检完成', payload: {
        kill_rate: 0.94,
        threshold: 0.9,
        before_count: 50,
        after_count: 3,
        rounds: 1,
      } },
    ],
    ...overrides,
  }
}

describe('buildScreenViewModel', () => {
  it('maps live Muye workflow data into the command-screen panels', () => {
    const model = buildScreenViewModel(makeTask(), undefined, 55, true)

    expect(model.connected).toBe(true)
    expect(model.field).toMatchObject({
      name: '郑州高标准农田 01',
      city: '郑州市',
      crop: '小麦',
      area: '12.6',
      pestCount: 2,
      riskLabel: '高风险',
    })
    expect(model.pests).toEqual([{ name: '蚜虫', count: 2, confidence: 0.9 }])
    expect(model.weatherSuitable).toBe(true)
    expect(model.weatherReady).toBe(true)
    expect(model.decision).toMatchObject({
      pesticide: '吡虫啉',
      complianceStatus: 'passed',
      complianceScore: 92,
      decisionPath: '多智能体会诊',
      expertCount: 3,
    })
    expect(model.drone).toMatchObject({
      taskId: 'px4-001',
      statusLabel: '变量喷洒',
      progress: 62,
      waypoint: 4,
      waypointTotal: 2,
      latitude: 34.76,
      longitude: 113.65,
    })
    expect(model.evaluation).toMatchObject({
      status: 'evaluated',
      statusLabel: '评估完成',
      killRate: 0.94,
      threshold: 0.9,
      beforeCount: 50,
      afterCount: 3,
      currentIteration: 1,
    })
    expect(model.evaluation.verdict).toContain('达到闭环目标')
    expect(model.fieldTwin.boundarySource).toBe('virtual')
    expect(model.fieldTwin.boundary).toHaveLength(4)
    expect(model.fieldTwin.route).toHaveLength(2)
    expect(model.fieldTwin.hasRoute).toBe(true)
    expect(model.fieldTwin.pestPoints).toHaveLength(2)
    expect(model.fieldTwin.pestPoints[0]).toMatchObject({
      x: 0.319375,
      y: 0.31125,
    })
    expect(model.fieldTwin.heatCells[0].density).toBe(0.82)
    expect(model.fieldTwin.densitySourceLabel).toBe('YOLO 相对检测热值')
    expect(model.fieldTwin.densitySimulated).toBe(false)
    expect(model.fieldTwin.densityAcceptedCount).toBe(2)
    expect(model.fieldTwin.dronePosition).not.toBeNull()
  })

  it('provides a safe waiting state before the first task arrives', () => {
    const model = buildScreenViewModel(null, undefined, 0, false)

    expect(model.statusLabel).toBe('系统待命')
    expect(model.field.name).toBe('未绑定地块')
    expect(model.field.crop).toBe('--')
    expect(model.pests).toEqual([])
    expect(model.pipeline).toHaveLength(7)
    expect(model.pipeline.every((stage) => stage.status === 'pending')).toBe(true)
    expect(model.decision.pesticide).toBe('等待 AI 推荐')
    expect(model.drone.statusLabel).toBe('待命')
    expect(model.weatherReady).toBe(false)
    expect(model.fieldTwin.boundarySource).toBe('virtual')
    expect(model.fieldTwin.hasRoute).toBe(false)
    expect(model.fieldTwin.route).toEqual([])
    expect(model.fieldTwin.pestPoints).toEqual([])
    expect(model.fieldTwin.densitySourceLabel).toBe('等待虫情数据')
  })
})
