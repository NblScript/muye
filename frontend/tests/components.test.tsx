import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatCard from '../src/components/dashboard/StatCard'
import WeatherCard from '../src/components/dashboard/WeatherCard'
import TaskList from '../src/components/dashboard/TaskList'
import ExpertPanel from '../src/components/dashboard/ExpertPanel'
import DecisionExplainPanel from '../src/components/dashboard/DecisionExplainPanel'
import type { WorkflowTaskState } from '../src/types/workflow'

describe('StatCard', () => {
  it('renders label, value, and unit', () => {
    render(<StatCard label="作业面积" value={42} unit="亩" footnote="测试数据" />)
    expect(screen.getByText('作业面积')).toBeInTheDocument()
    expect(screen.getByText('亩')).toBeInTheDocument()
    expect(screen.getByText('测试数据')).toBeInTheDocument()
  })

  it('renders string values directly', () => {
    render(<StatCard label="状态" value="--" unit="" footnote="无数据" />)
    expect(screen.getByText('--')).toBeInTheDocument()
  })
})

describe('WeatherCard', () => {
  it('renders weather summary', () => {
    const weather = { summary: '晴天 25℃', temperature: 25, humidity: 60 }
    render(<WeatherCard weather={weather} />)
    expect(screen.getByText('天气信息')).toBeInTheDocument()
    expect(screen.getByText('晴天 25℃')).toBeInTheDocument()
  })

  it('renders placeholder when no data', () => {
    render(<WeatherCard weather={{}} />)
    expect(screen.getByText('等待天气数据')).toBeInTheDocument()
  })

  it('renders temperature and humidity metrics', () => {
    const weather = { temperature: 28, humidity: 75, wind_speed: 3.2 }
    render(<WeatherCard weather={weather} />)
    expect(screen.getByText('28 ℃')).toBeInTheDocument()
    expect(screen.getByText('75 %')).toBeInTheDocument()
    expect(screen.getByText('3.2 m/s')).toBeInTheDocument()
  })
})

describe('TaskList', () => {
  it('renders empty state when no tasks', () => {
    render(<TaskList tasks={[]} />)
    expect(screen.getByText('当前没有可展示的任务队列')).toBeInTheDocument()
  })

  it('renders task items', () => {
    const tasks = [
      {
        id: 'req-001',
        droneName: 'PX4-01',
        fieldName: '东区麦田',
        status: '执行中' as const,
        progress: 65,
        pesticideName: '吡虫啉',
        sprayAreaText: '12 亩',
        updatedAt: '05/25 14:30',
        isCurrent: true,
      },
    ]
    render(<TaskList tasks={tasks} />)
    expect(screen.getByText('req-001')).toBeInTheDocument()
    expect(screen.getByText('PX4-01')).toBeInTheDocument()
    expect(screen.getByText('东区麦田')).toBeInTheDocument()
    expect(screen.getByText(/吡虫啉/)).toBeInTheDocument()
    expect(screen.getByText('当前')).toBeInTheDocument()
  })

  it('renders custom title', () => {
    render(<TaskList tasks={[]} title="自定义标题" />)
    expect(screen.getByText('自定义标题')).toBeInTheDocument()
  })
})

describe('ExpertPanel', () => {
  it('renders nothing when no consultation detail', () => {
    const { container } = render(<ExpertPanel ragContext={undefined} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing when consultation_detail is missing', () => {
    const { container } = render(<ExpertPanel ragContext={{ pesticides: [] }} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders expert cards and consultation summary', () => {
    const ragContext = {
      confidence: 0.85,
      agreement: 'majority',
      decision_path: 'multi_agent' as const,
      consultation_detail: {
        active_count: 3,
        experts: {
          entomologist: { name: '昆虫学家', weight: 0.4, '农药名称': '吡虫啉', '总量': '500ml' },
          agronomist: { name: '农学家', weight: 0.35, '农药名称': '噻虫嗪', '总量': '400ml' },
          plant_protection: { name: '植保专家', weight: 0.25, '农药名称': '吡虫啉', '总量': '450ml' },
        },
        failed_roles: [],
        vote_distribution: { '吡虫啉': 0.65, '噻虫嗪': 0.35 },
      },
    }
    render(<ExpertPanel ragContext={ragContext} />)

    expect(screen.getByText('多智能体专家会诊')).toBeInTheDocument()
    expect(screen.getByText('3 位专家参与')).toBeInTheDocument()
    expect(screen.getByText('昆虫学家')).toBeInTheDocument()
    expect(screen.getByText('农学家')).toBeInTheDocument()
    expect(screen.getByText('植保专家')).toBeInTheDocument()
    expect(screen.getAllByText('多数通过').length).toBeGreaterThan(0)
    expect(screen.getByText('会诊结论')).toBeInTheDocument()
  })

  it('renders detailed consultation metadata for each expert', () => {
    const ragContext = {
      confidence: 0.65,
      agreement: 'majority',
      decision_path: 'multi_agent' as const,
      consultation_detail: {
        active_count: 3,
        experts: {
          entomologist: { name: '昆虫学家', weight: 0.4, '农药名称': '吡虫啉', '总量': '1.2 L' },
          agronomist: { name: '农学家', weight: 0.35, '农药名称': '噻虫嗪', '总量': '1.0 L' },
          pesticide_specialist: { name: '植保专家', weight: 0.25, '农药名称': '吡虫啉', '总量': '1.1 L' },
        },
        failed_roles: [],
        vote_distribution: { '吡虫啉': 0.65, '噻虫嗪': 0.35 },
      },
    }

    render(<ExpertPanel ragContext={ragContext} />)

    expect(screen.getByText('决策路径')).toBeInTheDocument()
    expect(screen.getByText('失败专家')).toBeInTheDocument()
    expect(screen.getByText('昆虫分类与危害评估')).toBeInTheDocument()
    expect(screen.getByText('作物阶段与农艺约束')).toBeInTheDocument()
    expect(screen.getByText('药剂安全与合规复核')).toBeInTheDocument()
    expect(screen.getByText('模型 Qwen')).toBeInTheDocument()
    expect(screen.getByText('权重 40%')).toBeInTheDocument()
    expect(screen.getByText('总量 1.2 L')).toBeInTheDocument()
    expect(screen.getAllByText('采用').length).toBeGreaterThan(0)
    expect(screen.getByText('最终采用')).toBeInTheDocument()
    expect(screen.getByText('由昆虫学家方案进入执行')).toBeInTheDocument()
  })

  it('renders failed expert status', () => {
    const ragContext = {
      confidence: 0.5,
      agreement: 'single_expert',
      consultation_detail: {
        active_count: 1,
        experts: {
          entomologist: { name: '昆虫学家', weight: 1, '农药名称': '吡虫啉', '总量': '500ml' },
          agronomist: { name: '农学家', weight: 0, '农药名称': '', '总量': '' },
        },
        failed_roles: ['agronomist'],
        vote_distribution: { '吡虫啉': 1 },
      },
    }
    render(<ExpertPanel ragContext={ragContext} />)
    expect(screen.getByText('调用失败，已降级处理')).toBeInTheDocument()
  })
})

describe('DecisionExplainPanel', () => {
  it('renders pesticide compliance review result', () => {
    const task: WorkflowTaskState = {
      request_id: 'req-compliance',
      current_stage: 'decision',
      status: 'running',
      message: '千问决策生成完成',
      field: {},
      detections: [{ pest_type: 'aphid', confidence: 0.92 }],
      weather: { wind_speed: 6.1, humidity: 88 },
      spray_summary: {},
      decision: {
        用药: {
          农药名称: '吡虫啉',
          安全提示: ['佩戴防护装备'],
        },
      },
      compliance: {
        status: 'warning',
        score: 76,
        summary: '风险提示：吡虫啉存在风险——当前风速6.1m/s偏高，注意药液漂移风险',
        checks: [
          { rule: 'source_match', name: '来源验证', status: 'passed', message: '吡虫啉来自 RAG 农药候选', evidence: [] },
          { rule: 'weather_risk', name: '天气约束', status: 'warning', message: '当前风速6.1m/s偏高，注意药液漂移风险', evidence: [{ source: 'weather_api', title: '实时气象', matched_fields: ['wind_speed'] }] },
        ],
        blocking_reasons: [],
        warnings: ['当前风速6.1m/s偏高，注意药液漂移风险'],
        execution_policy: { takeoff_mode: 'manual', reason: '需人工确认' },
        alternatives: [],
      },
      drone: {},
      drone_timeline: [],
      recent_events: [],
    }

    render(<DecisionExplainPanel task={task} />)

    expect(screen.getByText('农药安全合规推理链')).toBeInTheDocument()
    expect(screen.getByText('风险提示')).toBeInTheDocument()
    expect(screen.getByText('76/100')).toBeInTheDocument()
    expect(screen.getByText('当前风速6.1m/s偏高，注意药液漂移风险')).toBeInTheDocument()
  })
})
