import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  fetchHeatmapComparison,
  fetchHeatmapSnapshot,
  fetchHeatmapSnapshots,
  fetchMission,
} from '../src/api/workflow'
import HeatmapHistoryPanel from '../src/components/heatmap/HeatmapHistoryPanel'
import type {
  HeatmapComparisonResponse,
  HeatmapSnapshotDetail,
  HeatmapSnapshotSummary,
  MissionDetail,
} from '../src/types/workflow'

vi.mock('../src/api/workflow', () => ({
  fetchHeatmapSnapshots: vi.fn(),
  fetchHeatmapSnapshot: vi.fn(),
  fetchHeatmapComparison: vi.fn(),
  fetchMission: vi.fn(),
}))

const grid = [
  { row: 0, col: 0, density: 1, bounds: [[113.1, 34.1], [113.2, 34.2]] as [number, number][] },
  { row: 0, col: 1, density: 0.35, bounds: [[113.2, 34.1], [113.3, 34.2]] as [number, number][] },
]

const preSummary: HeatmapSnapshotSummary = {
  snapshot_id: 'heatmap:req-1:pre_spray:1',
  batch_id: 'inspection:req-1:pre_spray:1',
  request_id: 'req-1',
  field_id: 'field-1',
  mission_id: 'mission-1',
  iteration_number: 1,
  inspection_kind: 'pre_spray',
  captured_at: '2026-08-01T02:00:00Z',
  algorithm_version: 'density-grid-v1',
  pest_counts: { aphid: 12 },
  total_detection_count: 12,
  hotspot_cell_count: 3,
  peak_relative_heat: 1,
  source: 'yolo_bbox',
  is_simulated: false,
  legacy: false,
}

const postSummary: HeatmapSnapshotSummary = {
  ...preSummary,
  snapshot_id: 'heatmap:req-1:reinspection:1',
  batch_id: 'inspection:req-1:reinspection:1',
  inspection_kind: 'reinspection',
  captured_at: '2026-08-02T02:00:00Z',
  pest_counts: { aphid: 4 },
  total_detection_count: 4,
  hotspot_cell_count: 1,
  peak_relative_heat: 0.65,
}

function detail(summary: HeatmapSnapshotSummary): HeatmapSnapshotDetail {
  return {
    ...summary,
    density_grid: grid,
    density_metadata: { grid_rows: 1, grid_cols: 2, source: summary.source },
    image_paths: ['/tmp/inspection.jpg'],
    detections: Array.from({ length: summary.total_detection_count }, () => ({
      pest_type: 'aphid',
      confidence: 0.9,
    })),
  }
}

const comparison: HeatmapComparisonResponse = {
  request_id: 'req-1',
  mission_id: 'mission-1',
  iteration_number: 1,
  status: 'paired',
  pre_spray: detail(preSummary),
  reinspection: detail(postSummary),
  metrics: {
    detection_count_change: -8,
    hotspot_cell_count_change: -2,
    peak_relative_heat_change: -0.35,
  },
}

const mission: MissionDetail = {
  mission_row_id: 1,
  mission_uuid: 'mission-1',
  original_request_id: 'req-1',
  field_id: 'field-1',
  status: 'active',
  kill_rate_threshold: 0.9,
  max_iterations: 3,
  current_iteration: 2,
  pest_types: ['aphid'],
  iterations: [{
    iteration_id: 2,
    iteration_number: 2,
    spray_request_id: 'req-1',
    status: 'spraying',
    heatmap_snapshot_id: postSummary.snapshot_id,
    heatmap_algorithm_version: 'density-grid-v1',
    spray_plan: {
      planning_mode: 'variable_rate',
      heatmap_snapshot_id: postSummary.snapshot_id,
      heatmap_algorithm_version: 'density-grid-v1',
      spray_schedule: [0.6, 1.2, 1.8],
      spray_rate_policy: {
        basis: 'lane_max_relative_heat',
        base_rate_lpm: 1.2,
        bands: [
          { label: '低热值', minimum: 0, maximum_exclusive: 0.3, multiplier: 0.5 },
          { label: '中热值', minimum: 0.3, maximum_exclusive: 0.6, multiplier: 1 },
          { label: '高热值', minimum: 0.6, maximum_exclusive: null, multiplier: 1.5 },
        ],
      },
    },
  }],
}

describe('HeatmapHistoryPanel', () => {
  beforeEach(() => {
    vi.mocked(fetchHeatmapSnapshots).mockReset().mockResolvedValue({
      total: 2,
      limit: 100,
      offset: 0,
      items: [postSummary, preSummary],
    })
    vi.mocked(fetchHeatmapSnapshot).mockReset().mockImplementation(async (snapshotId) => (
      snapshotId === postSummary.snapshot_id ? detail(postSummary) : detail(preSummary)
    ))
    vi.mocked(fetchHeatmapComparison).mockReset().mockResolvedValue(comparison)
    vi.mocked(fetchMission).mockReset().mockResolvedValue(mission)
  })

  it('renders traceable snapshot trends, detail, and a static before-after comparison', async () => {
    render(<HeatmapHistoryPanel />)

    expect(screen.getByRole('heading', { name: '虫情热力历史' })).toBeInTheDocument()
    expect(await screen.findByText('2 个快照')).toBeInTheDocument()
    expect(screen.getByText('检测数量')).toBeInTheDocument()
    expect(screen.getAllByText('热点网格')).not.toHaveLength(0)
    expect(screen.getByText('峰值相对热值')).toBeInTheDocument()
    expect(screen.getAllByText('实测 · YOLO 实测')).toHaveLength(2)

    expect(await screen.findByRole('img', { name: /本次巡检热力，1 行 2 列/ })).toBeInTheDocument()
    expect(screen.getByText('已配对')).toBeInTheDocument()
    expect(screen.getByText('-8')).toBeInTheDocument()
    expect(screen.getByText('-2')).toBeInTheDocument()
    expect(screen.getByText('-35.0 个百分点')).toBeInTheDocument()
    expect(screen.getByLabelText('热力快照作业追溯')).toBeInTheDocument()
    expect(screen.getByText('变量喷洒')).toBeInTheDocument()
    expect(screen.getByText('低热值 0–30% ×0.5')).toBeInTheDocument()
    expect(screen.getByText('喷洒范围 0.60–1.80 L/min')).toBeInTheDocument()
    expect(screen.getByText(/正式杀灭率和效果结论以后端任务评估为准/)).toBeInTheDocument()
  })

  it('maps source, pest, stage, and date controls to the snapshot query contract', async () => {
    const user = userEvent.setup()
    render(<HeatmapHistoryPanel />)

    await screen.findByText('2 个快照')
    await user.selectOptions(screen.getByLabelText('昆虫种类'), 'aphid')
    await user.selectOptions(screen.getByLabelText('数据来源'), 'demo_seed')
    await user.selectOptions(screen.getByLabelText('巡检阶段'), 'reinspection')
    await user.type(screen.getByLabelText('开始日期'), '2026-08-01')
    await user.type(screen.getByLabelText('结束日期'), '2026-08-03')
    const expectedFrom = new Date('2026-08-01T00:00:00.000').toISOString()
    const expectedTo = new Date('2026-08-03T23:59:59.999').toISOString()

    await waitFor(() => {
      expect(fetchHeatmapSnapshots).toHaveBeenLastCalledWith(expect.objectContaining({
        pest_type: 'aphid',
        source: 'demo_seed',
        inspection_kind: 'reinspection',
        captured_from: expectedFrom,
        captured_to: expectedTo,
        limit: 100,
      }))
    })
  })
})
