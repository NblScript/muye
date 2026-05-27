import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import DemoReadinessBar from '../src/components/dashboard/DemoReadinessBar'
import DecisionSummaryCard from '../src/components/dashboard/DecisionSummaryCard'
import type { WorkflowTaskState } from '../src/types/workflow'

const sampleTask: WorkflowTaskState = {
  request_id: 'req-smoke',
  current_stage: 'drone',
  status: 'running',
  message: '无人机执行中',
  field: { crop_cycle: { crop_name: '小麦' } },
  detections: [
    { pest_type: 'aphid', confidence: 0.92 },
    { pest_type: 'aphid', confidence: 0.88 },
  ],
  weather: { wind_speed: 3.2, humidity: 61 },
  spray_summary: {},
  decision: {
    用药: {
      农药名称: '吡虫啉',
      总量: '1.2 L',
    },
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
    pesticides: [{ content: '吡虫啉适用于蚜虫', score: 0.91 }],
    confidence: 0.86,
    agreement: 'majority',
    decision_path: 'multi_agent',
    consultation_detail: {
      active_count: 3,
      experts: {
        entomologist: { name: '昆虫学家', weight: 0.4, 农药名称: '吡虫啉', 总量: '1.2 L' },
        agronomist: { name: '农学家', weight: 0.35, 农药名称: '吡虫啉', 总量: '1.1 L' },
        pesticide_specialist: { name: '植保专家', weight: 0.25, 农药名称: '噻虫嗪', 总量: '1.0 L' },
      },
      failed_roles: [],
      vote_distribution: { 吡虫啉: 0.67, 噻虫嗪: 0.33 },
    },
  },
  drone: { status: 'spraying', task_id: 'drone-task' },
  drone_timeline: [],
  recent_events: [],
}

describe('DemoReadinessBar', () => {
  it('summarizes the live demo chain status', () => {
    render(
      <DemoReadinessBar
        connected
        workflowLoading={false}
        workflowError={null}
        latestTask={sampleTask}
        qwenMode="live"
        px4Running
        readiness={{
          status: 'degraded',
          summary: { ok: 8, warning: 1, error: 1 },
          checks: {
            rag: {
              key: 'rag',
              label: 'RAG',
              status: 'error',
              detail: '已启用',
              reason: 'RAG 配置或向量库依赖不可用',
              impact: '候选药剂和知识依据可能不完整',
              system_action: '合规链路会要求人工复核来源',
              human_action: '检查 RAG_ENABLED、QWEN_API_KEY 和 Chroma 数据',
            },
            px4: {
              key: 'px4',
              label: 'PX4',
              status: 'warning',
              detail: '未就绪',
              reason: 'PX4 进程未启动或 MAVLink 端口未就绪',
              impact: '真实 PX4 执行动画可能不可用',
              system_action: '切换为 animated_demo 或展示已记录任务状态',
              human_action: '点击启动 PX4 仿真',
            },
          },
          issues: [
            {
              key: 'rag',
              label: 'RAG',
              status: 'error',
              detail: '已启用',
              reason: 'RAG 配置或向量库依赖不可用',
              impact: '候选药剂和知识依据可能不完整',
              system_action: '合规链路会要求人工复核来源',
              human_action: '检查 RAG_ENABLED、QWEN_API_KEY 和 Chroma 数据',
            },
            {
              key: 'px4',
              label: 'PX4',
              status: 'warning',
              detail: '未就绪',
              reason: 'PX4 进程未启动或 MAVLink 端口未就绪',
              impact: '真实 PX4 执行动画可能不可用',
              system_action: '切换为 animated_demo 或展示已记录任务状态',
              human_action: '点击启动 PX4 仿真',
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('演示链路状态')).toBeInTheDocument()
    expect(screen.getByText('后端')).toBeInTheDocument()
    expect(screen.getByText('WebSocket')).toBeInTheDocument()
    expect(screen.getByText('最新任务')).toBeInTheDocument()
    expect(screen.getAllByText('RAG').length).toBeGreaterThan(0)
    expect(screen.getByText('LLM')).toBeInTheDocument()
    expect(screen.getByText('多智能体')).toBeInTheDocument()
    expect(screen.getAllByText('PX4').length).toBeGreaterThan(0)
    expect(screen.getByText('无人机')).toBeInTheDocument()
    expect(screen.getByText('候选药剂和知识依据可能不完整')).toBeInTheDocument()
    expect(screen.getByText('检查 RAG_ENABLED、QWEN_API_KEY 和 Chroma 数据')).toBeInTheDocument()
  })
})

describe('DecisionSummaryCard', () => {
  it('connects detection, RAG candidates, consultation, compliance, and execution policy', () => {
    render(<DecisionSummaryCard task={sampleTask} />)

    expect(screen.getByText('本轮决策摘要')).toBeInTheDocument()
    expect(screen.getByText(/识别到 蚜虫 × 2/)).toBeInTheDocument()
    expect(screen.getByText(/候选药剂 1 个/)).toBeInTheDocument()
    expect(screen.getByText(/多智能体会诊 3 位专家/)).toBeInTheDocument()
    expect(screen.getByText(/合规检查通过/)).toBeInTheDocument()
    expect(screen.getAllByText(/自动起飞/).length).toBeGreaterThan(0)
  })
})

vi.mock('../src/hooks/useDashboardState', () => ({
  useDashboardState: () => ({
    demoMode: false,
    setDemoMode: vi.fn(),
    clock: '2026/05/27 21:00:00',
    fileInputRef: { current: null },
    connected: true,
    workflowLoading: false,
    workflowError: null,
    workflow: { latest_task: sampleTask, recent_tasks: [], event_count: 8, source: 'event_bus' },
    latestTask: sampleTask,
    hasCurrentTask: true,
    pipelineStages: [],
    pipelineProgress: 100,
    activeStageLabel: '无人机执行',
    heroTitle: '本轮任务执行中',
    heroStageSummary: '识别、决策与执行链路已启动',
    showTakeoffBanner: false,
    field: sampleTask.field,
    spraySummary: {},
    decision: sampleTask.decision,
    medication: { 农药名称: '吡虫啉', 总量: '1.2 L' },
    weather: sampleTask.weather,
    agronomyTips: [],
    safetyTips: [],
    detections: sampleTask.detections,
    pestSummary: { labels: ['蚜虫 × 2'], summary: '蚜虫 × 2' },
    primaryPest: '蚜虫',
    currentAreaDisplay: '12',
    currentFieldName: '默认地块',
    currentCropName: '小麦',
    onlineDevices: 1,
    currentDetectionCount: 2,
    todayTaskCount: 1,
    recentTasks: [],
    detectionSparkline: [50, 80],
    areaSparkline: [12],
    latestUpdateText: '05/27 21:00:00',
    originalImageUrl: null,
    annotatedImageUrl: null,
    commandMetaItems: [],
    combinedStatusError: null,
    weatherOk: true,
    history: null,
    historyLoading: false,
    historyError: null,
    historyStatus: 'all',
    setHistoryStatus: vi.fn(),
    historySearch: '',
    setHistorySearch: vi.fn(),
    historyLimit: 12,
    setHistoryLimit: vi.fn(),
    context: { modes: { qwen: 'live', yolo: 'live', weather: 'live', drone: 'px4' } },
    demoReadiness: {
      status: 'ready',
      summary: { ok: 10, warning: 0, error: 0 },
      checks: {},
      issues: [],
    },
    uploading: false,
    resetting: false,
    confirmingTakeoff: false,
    px4Running: true,
    px4Starting: false,
    refreshHistory: vi.fn(),
    refreshWorkflow: vi.fn(),
    handleUploadClick: vi.fn(),
    handleUploadChange: vi.fn(),
    handleResetEvents: vi.fn(),
    handleConfirmTakeoff: vi.fn(),
    handlePx4Start: vi.fn(),
    handlePx4Stop: vi.fn(),
  }),
}))

vi.mock('../src/components/map/FieldMap', () => ({
  default: () => <div data-testid="field-map-smoke">地图已渲染</div>,
}))

vi.mock('../src/components/workflow/WorkflowPanel', () => ({
  default: () => <div>工作流面板</div>,
}))

describe('Dashboard smoke', () => {
  it('renders demo status, decision summary, map, multi-agent panel, and decision basis', async () => {
    const { default: Dashboard } = await import('../src/pages/Dashboard')

    render(<Dashboard />)

    expect(screen.getByText('演示链路状态')).toBeInTheDocument()
    expect(screen.getByText('本轮决策摘要')).toBeInTheDocument()
    expect(screen.getByTestId('field-map-smoke')).toBeInTheDocument()
    expect(screen.getByText('多智能体专家会诊')).toBeInTheDocument()
    expect(screen.getByText('农药安全合规推理链')).toBeInTheDocument()
  })
})
