import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DecisionFlow from '../src/components/dashboard/DecisionFlow'

describe('DecisionFlow', () => {
  it('renders 3 steps with pending state when no task', () => {
    render(<DecisionFlow task={null} />)
    expect(screen.getByText('害虫输入')).toBeInTheDocument()
    expect(screen.getByText('知识检索')).toBeInTheDocument()
    expect(screen.getByText('用药方案')).toBeInTheDocument()
    expect(screen.getAllByText('等待数据')).toHaveLength(3)
  })

  it('shows detection info when detections exist', () => {
    const task = {
      request_id: 'test',
      current_stage: 'yolo',
      status: 'running',
      message: '',
      field: {},
      detections: [
        { pest_type: 'aphid', confidence: 0.95 },
        { pest_type: 'aphid', confidence: 0.88 },
      ],
      weather: {},
      spray_summary: {},
      decision: {},
      drone: {},
      drone_timeline: [],
      recent_events: [],
    }
    render(<DecisionFlow task={task} />)
    expect(screen.getByText('害虫种类')).toBeInTheDocument()
    expect(screen.getByText('aphid ×2')).toBeInTheDocument()
    expect(screen.getByText('检测目标数')).toBeInTheDocument()
  })

  it('shows decision mode when decision exists', () => {
    const task = {
      request_id: 'test',
      current_stage: 'decision',
      status: 'running',
      message: '',
      field: {},
      detections: [{ pest_type: 'aphid' }],
      weather: {},
      spray_summary: {},
      decision: { '用药': { '农药名称': '吡虫啉' } },
      rag_context: {
        decision_path: 'expert' as const,
        familiarity_score: 0.8,
        pesticides: [{ content: 'test', score: 0.9 }],
      },
      drone: {},
      drone_timeline: [],
      recent_events: [],
    }
    render(<DecisionFlow task={task} />)
    expect(screen.getByText('决策模式')).toBeInTheDocument()
    expect(screen.getByText('专家模型（快速路径）')).toBeInTheDocument()
  })

  it('shows medication info when decision has 用药', () => {
    const task = {
      request_id: 'test',
      current_stage: 'drone',
      status: 'running',
      message: '',
      field: {},
      detections: [],
      weather: {},
      spray_summary: {},
      decision: { '用药': { '农药名称': '噻虫嗪', '配比': '1:1000', '总量': '500ml' } },
      drone: {},
      drone_timeline: [],
      recent_events: [],
    }
    render(<DecisionFlow task={task} />)
    expect(screen.getByText('噻虫嗪')).toBeInTheDocument()
    expect(screen.getByText('1:1000')).toBeInTheDocument()
  })

  it('shows decision mode for escalated path', () => {
    const task = {
      request_id: 'test',
      current_stage: 'decision',
      status: 'running',
      message: '',
      field: {},
      detections: [],
      weather: {},
      spray_summary: {},
      decision: { '用药': {} },
      rag_context: {
        decision_path: 'escalated' as const,
        familiarity_score: 0.3,
        pesticides: [{ content: 'test', score: 0.5 }],
      },
      drone: {},
      drone_timeline: [],
      recent_events: [],
    }
    render(<DecisionFlow task={task} />)
    expect(screen.getAllByText('专家路径异常 → 多智能体升级').length).toBeGreaterThanOrEqual(1)
  })
})
