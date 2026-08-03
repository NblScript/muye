import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ScreenProps } from '../src/assets/screen/Screen'
import type { WorkflowTaskState } from '../src/types/workflow'

const sampleTask: WorkflowTaskState = {
  request_id: 'req-smoke',
  current_stage: 'drone',
  status: 'running',
  message: '无人机执行中',
  field: { crop_cycle: { crop_name: '小麦' } },
  detections: [{ pest_type: 'aphid', confidence: 0.92 }],
  weather: { wind_speed: 3.2, humidity: 61 },
  spray_summary: {},
  decision: { 用药: { 农药名称: '吡虫啉', 总量: '1.2 L' } },
  drone: { status: 'spraying', task_id: 'drone-task' },
  drone_timeline: [],
  recent_events: [],
}

vi.mock('../src/hooks/useDashboardState', () => ({
  useDashboardState: () => ({
    fileInputRef: { current: null },
    connected: true,
    workflowLoading: false,
    latestTask: sampleTask,
    pipelineProgress: 100,
    showTakeoffBanner: false,
    weather: sampleTask.weather,
    uploading: false,
    confirmingTakeoff: false,
    refreshWorkflow: vi.fn(),
    handleUploadClick: vi.fn(),
    handleUploadChange: vi.fn(),
    handleConfirmTakeoff: vi.fn(),
    toast: { holder: null },
  }),
}))

vi.mock('../src/assets/screen/Screen', () => ({
  default: ({ latestTask, connected, progress, actions }: ScreenProps) => (
    <main aria-label="牧野昆虫热力监测大屏">
      <h1>牧野昆虫热力监测大屏</h1>
      <section>昆虫密度热力值地图</section>
      <section>昆虫识别与数量</section>
      <section>AI 会诊与防治方案</section>
      <section>无人机执行状态</section>
      <section>虫情热力与防治闭环</section>
      <span>{connected ? '实时连接' : '轮询连接'}</span>
      <span>任务 {latestTask?.request_id}</span>
      <span>进度 {progress}%</span>
      <button type="button" onClick={actions.onUpload}>接入巡检图像</button>
    </main>
  ),
}))

describe('Dashboard smoke', () => {
  it('passes live Muye workflow data into the redesigned command screen', async () => {
    const { default: Dashboard } = await import('../src/pages/Dashboard')

    render(<Dashboard />)

    expect(await screen.findByRole('heading', { name: '牧野昆虫热力监测大屏' })).toBeInTheDocument()
    expect(screen.getByText('昆虫密度热力值地图')).toBeInTheDocument()
    expect(screen.getByText('昆虫识别与数量')).toBeInTheDocument()
    expect(screen.getByText('AI 会诊与防治方案')).toBeInTheDocument()
    expect(screen.getByText('无人机执行状态')).toBeInTheDocument()
    expect(screen.getByText('虫情热力与防治闭环')).toBeInTheDocument()
    expect(screen.getByText('实时连接')).toBeInTheDocument()
    expect(screen.getByText('任务 req-smoke')).toBeInTheDocument()
    expect(screen.getByText('进度 100%')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '接入巡检图像' })).toBeInTheDocument()
  })
})
