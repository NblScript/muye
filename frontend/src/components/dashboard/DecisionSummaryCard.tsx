import { Card } from '../ui'
import type { WorkflowTaskState } from '../../types/workflow'
import { asRecord, safeMetric, summarizePests } from '../../utils/dashboardUtils'

type Props = {
  task?: WorkflowTaskState | null
}

const POLICY_LABELS: Record<string, string> = {
  auto: '自动起飞',
  manual: '人工确认',
  blocked: '禁止执行',
}

const COMPLIANCE_LABELS: Record<string, string> = {
  passed: '合规检查通过',
  warning: '合规存在风险提示',
  blocked: '合规阻断执行',
}

function getMedication(task?: WorkflowTaskState | null): Record<string, unknown> {
  return asRecord(asRecord(task?.decision)['用药'])
}

function getConsultationText(task?: WorkflowTaskState | null): string {
  const detail = task?.rag_context?.consultation_detail
  if (!detail) {
    const path = task?.rag_context?.decision_path
    if (path === 'expert') return '专家快速路径'
    if (path === 'escalated') return '已升级复核'
    return '等待会诊'
  }

  const count = detail.active_count ?? Object.keys(detail.experts ?? {}).length
  const agreement = task?.rag_context?.agreement === 'majority' ? '多数通过' : '形成结论'
  return `多智能体会诊 ${count} 位专家，${agreement}`
}

export default function DecisionSummaryCard({ task }: Props) {
  const detections = task?.detections ?? []
  const pestSummary = summarizePests(detections)
  const pestText = pestSummary.labels.length > 0 ? `识别到 ${pestSummary.labels.join('，')}` : '等待虫情识别'
  const candidateCount = task?.rag_context?.pesticides?.length ?? 0
  const candidateText = candidateCount > 0 ? `候选药剂 ${candidateCount} 个` : '等待 RAG 候选药剂'
  const medication = getMedication(task)
  const pesticideName = safeMetric(medication['农药名称'])
  const total = safeMetric(medication['总量'])
  const complianceStatus = task?.compliance?.status
  const complianceText = complianceStatus
    ? COMPLIANCE_LABELS[complianceStatus] ?? String(complianceStatus)
    : '等待合规检查'
  const policy = task?.compliance?.execution_policy?.takeoff_mode
  const policyText = policy ? POLICY_LABELS[policy] ?? String(policy) : '等待执行策略'
  const cropName = safeMetric(asRecord(asRecord(task?.field).crop_cycle).crop_name) === '--'
    ? '待识别作物'
    : String(asRecord(asRecord(task?.field).crop_cycle).crop_name)

  return (
    <Card className="decision-summary-card">
      <span className="panel-label">本轮决策摘要</span>
      <div className="decision-summary-main">
        <strong>{pestText}</strong>
        <span>
          {candidateText} → {getConsultationText(task)} → {complianceText} → {policyText}
        </span>
      </div>
      <div className="decision-summary-grid">
        <div>
          <span>当前作物</span>
          <strong>{cropName}</strong>
        </div>
        <div>
          <span>推荐药剂</span>
          <strong>{pesticideName}</strong>
        </div>
        <div>
          <span>计划用量</span>
          <strong>{total}</strong>
        </div>
        <div>
          <span>执行策略</span>
          <strong>{policyText}</strong>
        </div>
      </div>
    </Card>
  )
}
