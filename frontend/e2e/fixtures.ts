import type { Page, Route } from '@playwright/test'

import type {
  HeatmapComparisonResponse,
  HeatmapSnapshotDetail,
  HeatmapSnapshotListResponse,
  MissionDetail,
  WorkflowDetectionEntry,
  WorkflowHistoryResponse,
  WorkflowStateResponse,
} from '../src/types/workflow'

function makeGrid(multiplier = 1) {
  return Array.from({ length: 80 }, (_, index) => {
    const row = Math.floor(index / 10)
    const col = index % 10
    const dx = (col - 5) / 5
    const dy = (row - 3.5) / 4
    const density = Math.max(0.05, Math.min(1, (1 - Math.sqrt(dx * dx + dy * dy)) * multiplier))
    const west = 113.58 + col * 0.007
    const south = 34.68 + row * 0.004375
    return {
      row,
      col,
      density: Number(density.toFixed(3)),
      bounds: [
        [west, south],
        [west + 0.007, south + 0.004375],
      ] as [number, number][],
    }
  })
}

function makeDetections(
  pestType: string,
  count: number,
  offset: number,
): WorkflowDetectionEntry[] {
  return Array.from({ length: count }, (_, index) => {
    const slot = index + offset
    const x1 = 0.08 + (slot % 8) * 0.105
    const y1 = 0.12 + (Math.floor(slot / 8) % 5) * 0.15
    return {
      pest_type: pestType,
      confidence: Number((0.78 + (index % 5) * 0.035).toFixed(3)),
      position: {
        x1,
        y1,
        x2: Math.min(0.98, x1 + 0.045),
        y2: Math.min(0.98, y1 + 0.065),
        coordinate_space: 'image_normalized',
      },
    }
  })
}

const preSprayDetections = [
  ...makeDetections('aphid', 18, 0),
  ...makeDetections('planthopper', 7, 21),
]

const reinspectionDetections = [
  ...makeDetections('aphid', 3, 6),
  ...makeDetections('planthopper', 1, 28),
]

const preSpray: HeatmapSnapshotDetail = {
  snapshot_id: 'heatmap:req-visual:pre_spray:1',
  batch_id: 'inspection:req-visual:pre_spray:1',
  request_id: 'req-visual',
  field_id: 'field-visual-01',
  mission_id: 'mission-visual-01',
  iteration_number: 1,
  inspection_kind: 'pre_spray',
  captured_at: '2026-08-04T08:00:00+08:00',
  algorithm_version: 'relative-bbox-grid-v1',
  pest_counts: { aphid: 18, planthopper: 7 },
  total_detection_count: 25,
  hotspot_cell_count: 11,
  peak_relative_heat: 1,
  source: 'yolo_bbox',
  is_simulated: false,
  legacy: false,
  density_grid: makeGrid(),
  density_metadata: {
    source: 'yolo_bbox',
    density_kind: 'relative_detection_weight',
    accepted_detection_count: 25,
    rejected_detection_count: 0,
    grid_rows: 8,
    grid_cols: 10,
    is_simulated: false,
  },
  image_paths: ['/app/data/images/visual-acceptance.jpg'],
  detections: preSprayDetections,
}

const reinspection: HeatmapSnapshotDetail = {
  ...preSpray,
  snapshot_id: 'heatmap:req-visual:reinspection:1',
  batch_id: 'inspection:req-visual:reinspection:1',
  inspection_kind: 'reinspection',
  captured_at: '2026-08-05T08:00:00+08:00',
  pest_counts: { aphid: 3, planthopper: 1 },
  total_detection_count: 4,
  hotspot_cell_count: 2,
  peak_relative_heat: 0.42,
  density_grid: makeGrid(0.42),
  density_metadata: {
    ...preSpray.density_metadata,
    accepted_detection_count: 4,
  },
  detections: reinspectionDetections,
}

export const workflowState: WorkflowStateResponse = {
  source: 'event_bus',
  event_count: 18,
  latest_task: {
    request_id: 'req-visual',
    current_stage: 'drone',
    status: 'running',
    message: '正在执行变量喷洒',
    updated_at: '2026-08-04T08:06:00+08:00',
    image_path: '/app/data/images/visual-acceptance.jpg',
    field: {
      field_id: 'field-visual-01',
      field_name: '郑州高标准农田 01',
      city: '郑州市',
      area_mu: 12.6,
      crop_cycle: { crop_name: '小麦' },
      geofence: [[113.58, 34.68], [113.72, 34.68], [113.72, 34.82], [113.58, 34.82]],
    },
    detections: preSpray.detections,
    weather: { summary: '晴', temperature: 27.4, humidity: 61, wind_speed: 3.2 },
    spray_summary: { spray_area_mu: 12.6, total_dosage: 1.2 },
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
      task_id: 'px4-visual-001',
      status: 'spraying',
      message: '变量喷洒中',
      progress: 62,
      current_waypoint_index: 4,
      instruction: {
        飞行路径: [[113.59, 34.69], [113.64, 34.69], [113.64, 34.73], [113.6, 34.73]],
        覆盖区域: { coordinates: [[113.58, 34.68], [113.72, 34.68], [113.72, 34.82], [113.58, 34.82]] },
        高度: 8,
        速度: 5,
        喷洒速率: '0.8 L/min',
        density_grid: preSpray.density_grid,
        density_metadata: preSpray.density_metadata,
        planning_mode: 'variable_rate',
      },
      position: { latitude_deg: 34.71, longitude_deg: 113.63 },
    },
    drone_timeline: [],
    recent_events: [
      { timestamp: '2026-08-04T08:00:00+08:00', stage: 'yolo', status: 'completed', message: '昆虫识别完成' },
      { timestamp: '2026-08-04T08:03:00+08:00', stage: 'decision', status: 'completed', message: '决策完成' },
      { timestamp: '2026-08-04T08:06:00+08:00', stage: 'drone', status: 'running', message: '变量喷洒中' },
    ],
    evaluation: {
      status: 'scheduled',
      kill_rate_threshold: 0.9,
      pre_pest_count: 25,
      retry_count: 0,
    },
  },
  recent_tasks: [],
}

export const historyResponse: WorkflowHistoryResponse = {
  total: 2,
  items: [
    {
      request_id: 'req-visual',
      current_stage: 'drone',
      status: 'running',
      message: '变量喷洒中',
      updated_at: '2026-08-04T08:06:00+08:00',
      field: workflowState.latest_task.field,
      detections: preSpray.detections,
      weather: workflowState.latest_task.weather,
      spray_summary: { spray_area_mu: 12.6 },
      decision: workflowState.latest_task.decision,
      drone: workflowState.latest_task.drone,
    },
    {
      request_id: 'req-completed',
      current_stage: 'evaluation',
      status: 'completed',
      message: '闭环评估达标',
      updated_at: '2026-08-03T09:00:00+08:00',
      field: { field_id: 'field-visual-01', field_name: '郑州高标准农田 01' },
      detections: [],
      weather: {},
      spray_summary: { spray_area_mu: 12.6 },
      decision: {},
      drone: { status: 'completed', progress: 100 },
    },
  ],
}

export const snapshotList: HeatmapSnapshotListResponse = {
  total: 2,
  limit: 80,
  offset: 0,
  items: [preSpray, reinspection],
}

export const comparison: HeatmapComparisonResponse = {
  request_id: 'req-visual',
  mission_id: 'mission-visual-01',
  iteration_number: 1,
  status: 'paired',
  pre_spray: preSpray,
  reinspection,
  metrics: {
    detection_count_change: -21,
    hotspot_cell_count_change: -9,
    peak_relative_heat_change: -0.58,
  },
}

export const mission: MissionDetail = {
  mission_row_id: 1,
  mission_uuid: 'mission-visual-01',
  original_request_id: 'req-visual',
  field_id: 'field-visual-01',
  status: 'active',
  kill_rate_threshold: 0.9,
  max_iterations: 3,
  current_iteration: 1,
  pest_types: ['aphid', 'planthopper'],
  pesticide_name: '吡虫啉',
  crop_name: '小麦',
  iterations: [
    {
      iteration_id: 1,
      iteration_number: 1,
      status: 'sprayed',
      heatmap_snapshot_id: preSpray.snapshot_id,
      heatmap_algorithm_version: preSpray.algorithm_version,
      spray_plan: {
        planning_mode: 'variable_rate',
        spray_schedule: [0.5, 1, 1.5],
        spray_rate_policy: {
          bands: [
            { label: '低热值', minimum: 0, maximum_exclusive: 0.3, multiplier: 0.5 },
            { label: '中热值', minimum: 0.3, maximum_exclusive: 0.7, multiplier: 1 },
            { label: '高热值', minimum: 0.7, maximum_exclusive: null, multiplier: 1.5 },
          ],
        },
      },
    },
  ],
}

function fulfillJson(route: Route, payload: unknown) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  })
}

export async function installApiMocks(page: Page) {
  await page.routeWebSocket(/\/api\/ws\/enhanced-state$/, (socket) => {
    socket.send(JSON.stringify({ workflow_state: workflowState }))
  })

  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (path === '/api/workflow/state') return fulfillJson(route, workflowState)
    if (path === '/api/workflow/history') return fulfillJson(route, historyResponse)
    if (path === '/api/heatmaps/latest') return fulfillJson(route, preSpray)
    if (path === '/api/heatmaps/snapshots') return fulfillJson(route, snapshotList)
    if (path === `/api/heatmaps/snapshots/${encodeURIComponent(preSpray.snapshot_id)}`) return fulfillJson(route, preSpray)
    if (path === `/api/heatmaps/snapshots/${encodeURIComponent(reinspection.snapshot_id)}`) return fulfillJson(route, reinspection)
    if (path === `/api/heatmaps/comparison/${encodeURIComponent(preSpray.request_id)}`) return fulfillJson(route, comparison)
    if (path === `/api/mission/${encodeURIComponent(mission.mission_uuid)}`) return fulfillJson(route, mission)
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"unmocked_e2e_route"}' })
  })
}
