import { useState } from 'react'
import { Card, Drawer } from '../ui'
import type { RagContext, RagDocument, WorkflowDetectionEntry, WorkflowTaskState } from '../../types/workflow'
import type { ConsultationDetail, ExpertSummary } from '../../types/workflow'

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
  const hasRag = hasRagContext(task.rag_context)

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
  const isMultiAgent = Boolean(task.rag_context?.consultation_detail)
  const decisionPath = task.rag_context?.decision_path
  if (hasDecision) {
    const ragSource = decisionPath === 'expert'
      ? '专家模型（快速路径）'
      : decisionPath === 'escalated'
        ? '专家路径异常 → 多智能体升级'
        : isMultiAgent
          ? '多智能体会诊'
          : hasRag ? 'RAG 知识检索 + 千问大模型' : '千问大模型'
    ragFields.push({ label: '决策模式', value: ragSource })
  }
  if (hasRag) {
    const ctx = task.rag_context!
    const parts: string[] = []
    if (ctx.pesticides?.length) parts.push(`${ctx.pesticides.length} 条农药`)
    if (ctx.historical_cases?.length) parts.push(`${ctx.historical_cases.length} 条案例`)
    if (ctx.knowledge?.length) parts.push(`${ctx.knowledge.length} 条知识`)
    if (parts.length > 0) {
      ragFields.push({ label: '检索结果', value: parts.join('，') })
    }
  }
  if (agronomyTips.length > 0) {
    ragFields.push({ label: '农事建议', value: agronomyTips[0] })
  }
  if (task.rag_context?.confidence != null) {
    ragFields.push({ label: '会诊置信度', value: `${(task.rag_context.confidence * 100).toFixed(0)}%` })
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

function hasRagContext(ctx: RagContext | undefined): boolean {
  if (!ctx) return false
  return Boolean(
    (ctx.pesticides && ctx.pesticides.length > 0) ||
    (ctx.historical_cases && ctx.historical_cases.length > 0) ||
    (ctx.knowledge && ctx.knowledge.length > 0)
  )
}

function DocList({ title, docs, color }: { title: string; docs: RagDocument[]; color: string }) {
  if (docs.length === 0) return null
  return (
    <div style={{ marginBottom: 20 }}>
      <h4 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color, letterSpacing: '0.03em' }}>
        {title}
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {docs.map((doc, i) => (
          <div key={i} style={{
            padding: '10px 12px',
            background: 'var(--bg-surface)',
            borderRadius: 'var(--radius-sm)',
            borderLeft: `3px solid ${color}`,
            fontSize: 12,
            lineHeight: 1.6,
          }}>
            <div style={{ color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>{doc.content}</div>
            <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>
              相似度: {(doc.score * 100).toFixed(1)}%
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

interface DecisionFlowProps {
  task: WorkflowTaskState | null
}

export default function DecisionFlow({ task }: DecisionFlowProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const steps = buildSteps(task)
  const rag = task?.rag_context
  const decision = (task?.decision ?? {}) as Record<string, unknown>
  const medication = (decision['用药'] ?? {}) as Record<string, unknown>
  const agronomyTips = Array.isArray(decision['农事建议']) ? (decision['农事建议'] as string[]) : []
  const canExpand = hasRagContext(rag) || Object.keys(decision).length > 0

  return (
    <>
      <Card
        className="dashboard-card decision-flow-card"
        onClick={canExpand ? () => setDrawerOpen(true) : undefined}
        style={canExpand ? { cursor: 'pointer' } : undefined}
      >
        <span className="label-uppercase">AI 决策过程</span>
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
        {canExpand && (
          <div style={{ textAlign: 'right', marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            点击查看完整决策链路 →
          </div>
        )}
        {/* 专家模型快速路径摘要 */}
        {rag?.decision_path === 'expert' && (() => {
          const famScore = rag.familiarity_score ?? 0
          return (
            <div style={{
              marginTop: 10, padding: '8px 10px',
              background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)',
              borderLeft: '3px solid var(--accent-green)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-green)' }}>
                  专家模型快速路径
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  匹配度 {(famScore * 100).toFixed(0)}%
                </span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                已知害虫+作物组合，单模型快速决策
              </div>
            </div>
          )
        })()}
        {/* 专家路径升级摘要 */}
        {rag?.decision_path === 'escalated' && (() => {
          const famScore = rag.familiarity_score ?? 0
          return (
            <div style={{
              marginTop: 10, padding: '8px 10px',
              background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)',
              borderLeft: '3px solid var(--accent-amber)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-amber)' }}>
                  专家路径异常 → 多智能体升级
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  匹配度 {(famScore * 100).toFixed(0)}%
                </span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                专家模型输出异常，已自动升级到多智能体会诊
              </div>
            </div>
          )
        })()}
        {/* 多智能体会诊摘要卡片 */}
        {rag?.consultation_detail && (() => {
          const detail = rag.consultation_detail
          const experts = detail.experts ?? {}
          const confidence = rag.confidence ?? 0
          const agreement = rag.agreement ?? ''
          const activeCount = detail.active_count ?? Object.keys(experts).length
          const agreementLabel: Record<string, string> = {
            unanimous: '一致通过',
            majority: '多数通过',
            divided: '意见分歧',
            single_expert: '单专家',
            all_failed: '全部失败',
          }
          return (
            <div style={{
              marginTop: 10, padding: '8px 10px',
              background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)',
              borderLeft: '3px solid var(--accent-cyan)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-cyan)' }}>
                  多智能体会诊 · {activeCount} 位专家
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 600,
                  color: agreement === 'unanimous' ? 'var(--accent-green)'
                    : agreement === 'majority' ? 'var(--accent-amber)'
                    : agreement === 'all_failed' ? 'var(--accent-red)'
                    : 'var(--text-muted)',
                }}>
                  {agreementLabel[agreement] ?? agreement} · {(confidence * 100).toFixed(0)}%
                </span>
              </div>
              {Object.keys(experts).length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {Object.entries(experts).map(([role, info]) => (
                    <span key={role} style={{
                      fontSize: 10, padding: '2px 6px',
                      background: 'var(--bg-elevated)', borderRadius: 4,
                      color: 'var(--text-secondary)',
                    }}>
                      {info.name}: {info['农药名称']}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })()}
      </Card>

      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="AI 决策链路详情" width={460}>
        {/* 害虫检测 */}
        <section style={{ marginBottom: 24 }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: 'var(--accent-red)', letterSpacing: '0.03em' }}>
            🔍 害虫检测
          </h4>
          {task?.detections && task.detections.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {task.detections.map((d, i) => (
                <div key={i} style={{
                  padding: '8px 12px',
                  background: 'var(--bg-surface)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 12,
                  display: 'flex',
                  justifyContent: 'space-between',
                }}>
                  <span style={{ fontWeight: 600 }}>{d.pest_type ?? '未知'}</span>
                  <span style={{ color: 'var(--text-muted)' }}>
                    置信度 {d.confidence != null ? (d.confidence * 100).toFixed(1) + '%' : '-'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>暂无检测数据</div>
          )}
        </section>

        {/* RAG 知识检索 */}
        {rag && hasRagContext(rag) && (
          <section style={{ marginBottom: 24 }}>
            <h4 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: 'var(--accent-purple)', letterSpacing: '0.03em' }}>
              📚 RAG 知识检索
            </h4>
            {rag.crop_name && (
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 10 }}>
                作物: {rag.crop_name}
                {rag.pest_types && rag.pest_types.length > 0 && (
                  <> · 害虫: {rag.pest_types.join('、')}</>
                )}
              </div>
            )}
            <DocList title="农药推荐" docs={rag.pesticides ?? []} color="var(--accent-green)" />
            <DocList title="历史案例" docs={rag.historical_cases ?? []} color="var(--accent-amber)" />
            <DocList title="农业知识" docs={rag.knowledge ?? []} color="var(--accent-cyan)" />
          </section>
        )}

        {/* 多智能体会诊 */}
        {rag?.consultation_detail && (() => {
          const detail = rag.consultation_detail!
          const experts = detail.experts ?? {}
          const confidence = rag.confidence ?? 0
          const agreement = rag.agreement ?? ''
          const failedRoles = detail.failed_roles ?? []
          const votes = detail.vote_distribution ?? {}
          const agreementLabel: Record<string, string> = {
            unanimous: '一致通过',
            majority: '多数通过',
            divided: '意见分歧',
            single_expert: '单专家',
          }
          const agreementColor: Record<string, string> = {
            unanimous: 'var(--accent-green)',
            majority: 'var(--accent-amber)',
            divided: 'var(--accent-red)',
            single_expert: 'var(--text-muted)',
          }
          return (
            <section style={{ marginBottom: 24 }}>
              <h4 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: 'var(--accent-cyan)', letterSpacing: '0.03em' }}>
                🧑‍⚕️ 多智能体专家会诊
              </h4>
              {/* 置信度和一致性 */}
              <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                <div style={{
                  flex: 1, padding: '8px 12px', background: 'var(--bg-surface)',
                  borderRadius: 'var(--radius-sm)', textAlign: 'center',
                }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-cyan)' }}>
                    {(confidence * 100).toFixed(0)}%
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>会诊置信度</div>
                </div>
                <div style={{
                  flex: 1, padding: '8px 12px', background: 'var(--bg-surface)',
                  borderRadius: 'var(--radius-sm)', textAlign: 'center',
                }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: agreementColor[agreement] ?? 'var(--text-primary)' }}>
                    {agreementLabel[agreement] ?? agreement}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>专家一致性</div>
                </div>
              </div>
              {/* 各专家意见 */}
              {Object.entries(experts).length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                  {Object.entries(experts).map(([role, info]) => (
                    <div key={role} style={{
                      padding: '8px 12px', background: 'var(--bg-surface)',
                      borderRadius: 'var(--radius-sm)', fontSize: 12,
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    }}>
                      <div>
                        <span style={{ fontWeight: 600, marginRight: 8 }}>{info.name}</span>
                        <span style={{ color: 'var(--text-primary)' }}>{info['农药名称']}</span>
                      </div>
                      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                        权重 {(info.weight * 100).toFixed(0)}%
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {/* 失败专家 */}
              {failedRoles.length > 0 && (
                <div style={{ fontSize: 11, color: 'var(--accent-red)', marginBottom: 8 }}>
                  {failedRoles.length} 位专家调用失败，已降级处理
                </div>
              )}
              {/* 投票分布 */}
              {Object.keys(votes).length > 1 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>投票分布</div>
                  {Object.entries(votes).map(([name, weight]) => (
                    <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 12, minWidth: 80 }}>{name}</span>
                      <div style={{ flex: 1, height: 6, background: 'var(--bg-surface)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${weight * 100}%`, height: '100%', background: 'var(--accent-cyan)', borderRadius: 3 }} />
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{(weight * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )
        })()}

        {/* 决策结果 */}
        {Object.keys(decision).length > 0 && (
          <section style={{ marginBottom: 24 }}>
            <h4 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: 'var(--accent-green)', letterSpacing: '0.03em' }}>
              💊 用药方案
            </h4>
            {Boolean(medication['农药名称']) && (
              <div style={{ padding: '10px 12px', background: 'var(--accent-green-dim)', borderRadius: 'var(--radius-sm)', marginBottom: 8 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent-green)' }}>
                  {String(medication['农药名称'])}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                  {Boolean(medication['配比']) && <>配比: {String(medication['配比'])} </>}
                  {Boolean(medication['总量']) && <>· 总量: {String(medication['总量'])}</>}
                  {Boolean(medication['浓度']) && <> · 浓度: {String(medication['浓度'])}</>}
                </div>
              </div>
            )}
            {Array.isArray(medication['安全提示']) && (medication['安全提示'] as string[]).length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>安全提示</div>
                {(medication['安全提示'] as string[]).map((tip, i) => (
                  <div key={i} style={{ fontSize: 12, color: 'var(--text-primary)', paddingLeft: 10, borderLeft: '2px solid var(--accent-red)', marginBottom: 4 }}>
                    {tip}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* 农事建议 */}
        {agronomyTips.length > 0 && (
          <section>
            <h4 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: 'var(--accent-amber)', letterSpacing: '0.03em' }}>
              🌾 农事建议
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {agronomyTips.map((tip, i) => (
                <div key={i} style={{
                  padding: '8px 12px',
                  background: 'var(--bg-surface)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 12,
                  color: 'var(--text-primary)',
                  borderLeft: '3px solid var(--accent-amber)',
                }}>
                  {tip}
                </div>
              ))}
            </div>
          </section>
        )}
      </Drawer>
    </>
  )
}
