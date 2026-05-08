import { Card, Typography } from 'antd'
import type { WorkflowDetectionEntry, WorkflowTaskState } from '../../types/workflow'

const { Text } = Typography

interface StepData {
  key: string
  label: string
  icon: string
  fields: { label: string; value: string }[]
  active: boolean
  done: boolean
}

function buildSteps(task: WorkflowTaskState | null): StepData[] {
  if (!task) {
    return [
      { key: 'input', label: '害虫输入', icon: '🔍', fields: [], active: false, done: false },
      { key: 'rag', label: '知识检索', icon: '📚', fields: [], active: false, done: false },
      { key: 'output', label: '用药方案', icon: '💊', fields: [], active: false, done: false },
    ]
  }

  const detections: WorkflowDetectionEntry[] = task.detections ?? []
  const decision = (task.decision ?? {}) as Record<string, unknown>
  const medication = (decision['用药'] ?? {}) as Record<string, unknown>
  const agronomyTips = Array.isArray(decision['农事建议']) ? (decision['农事建议'] as string[]) : []

  const hasDetections = detections.length > 0
  const hasDecision = Object.keys(decision).length > 0
  const hasMedication = Object.keys(medication).length > 0

  // Count pest types
  const pestCounts = new Map<string, number>()
  for (const d of detections) {
    const type = String(d.pest_type ?? 'unknown')
    pestCounts.set(type, (pestCounts.get(type) ?? 0) + 1)
  }
  const pestLabels = [...pestCounts.entries()].map(([k, v]) => `${k} ×${v}`)

  const inputFields: { label: string; value: string }[] = []
  if (pestLabels.length > 0) {
    inputFields.push({ label: '害虫种类', value: pestLabels.join('，') })
  }
  if (detections.length > 0) {
    inputFields.push({ label: '检测目标数', value: String(detections.length) })
  }

  const ragFields: { label: string; value: string }[] = []
  if (hasDecision) {
    ragFields.push({ label: '知识来源', value: 'RAG + 千问大模型' })
  }
  if (agronomyTips.length > 0) {
    ragFields.push({ label: '农事建议', value: agronomyTips[0] })
  }

  const outputFields: { label: string; value: string }[] = []
  if (medication['农药名称']) {
    outputFields.push({ label: '农药名称', value: String(medication['农药名称']) })
  }
  if (medication['配比']) {
    outputFields.push({ label: '配比', value: String(medication['配比']) })
  }
  if (medication['总量']) {
    outputFields.push({ label: '总量', value: String(medication['总量']) })
  }

  return [
    {
      key: 'input',
      label: '害虫输入',
      icon: '🔍',
      fields: inputFields,
      active: hasDetections && !hasDecision,
      done: hasDetections,
    },
    {
      key: 'rag',
      label: '知识检索',
      icon: '📚',
      fields: ragFields,
      active: hasDetections && hasDecision && !hasMedication,
      done: hasDecision,
    },
    {
      key: 'output',
      label: '用药方案',
      icon: '💊',
      fields: outputFields,
      active: hasMedication,
      done: hasMedication,
    },
  ]
}

interface DecisionFlowProps {
  task: WorkflowTaskState | null
}

export default function DecisionFlow({ task }: DecisionFlowProps) {
  const steps = buildSteps(task)

  return (
    <Card bordered={false} className="dashboard-card decision-flow-card">
      <Text className="panel-label">AI 决策过程</Text>
      <div className="decision-flow-steps">
        {steps.map((step, index) => (
          <div key={step.key} className="decision-flow-step-group">
            <div className={`decision-flow-step is-${step.done ? 'done' : step.active ? 'active' : 'pending'}`}>
              <div className="decision-flow-step-icon">{step.icon}</div>
              <div className="decision-flow-step-content">
                <div className="decision-flow-step-label">{step.label}</div>
                {step.fields.length > 0 ? (
                  <div className="decision-flow-step-fields">
                    {step.fields.map((f) => (
                      <div key={f.label} className="decision-flow-field">
                        <span>{f.label}</span>
                        <strong>{f.value}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="decision-flow-step-empty">等待数据</div>
                )}
              </div>
            </div>
            {index < steps.length - 1 && (
              <div className={`decision-flow-arrow is-${steps[index + 1].done || steps[index + 1].active ? 'filled' : 'empty'}`}>
                →
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}
