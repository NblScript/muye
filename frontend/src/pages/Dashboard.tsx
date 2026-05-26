import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'

import {
  buildTaskAnnotatedImageUrl,
  buildTaskOriginalImageUrl,
  confirmDroneTakeoff,
  fetchDashboardContext,
  fetchWorkflowHistory,
  getPx4Status,
  resetDemoEvents,
  startPx4Demo,
  stopPx4Demo,
  uploadDemoImage,
} from '../api/workflow'
import { StatCard, WeatherCard, TaskList } from '../components/dashboard'
import DecisionFlow from '../components/dashboard/DecisionFlow'
import ExpertPanel from '../components/dashboard/ExpertPanel'
import PipelineStepper, { deriveStages } from '../components/dashboard/PipelineStepper'
import FieldMap from '../components/map/FieldMap'
import WorkflowPanel from '../components/workflow/WorkflowPanel'
import { Alert, Button, Card, Empty, Input, Select, Tag, useToast } from '../components/ui'
import { useEnhancedMapState } from '../hooks/useEnhancedMapState'
import type {
  DashboardContextResponse,
  WorkflowHistoryResponse,
  WorkflowStateResponse,
} from '../types/workflow'
import {
  asRecord,
  formatPestLabel,
  formatDateTime,
  formatNow,
  mapTaskEntry,
  modeColor,
  safeMetric,
  summarizePests,
} from '../utils/dashboardUtils'
import '../styles/dashboard.css'

const HERO_STAGE_LABELS: Record<string, string> = {
  upload: '图像上传',
  detection: 'YOLO识别',
  weather: '气象融合',
  decision: 'AI决策',
  drone: '无人机执行',
}

function clampPercent(value: unknown): number {
  const num = Number(value)
  if (!Number.isFinite(num)) return 0
  return Math.max(0, Math.min(100, Math.round(num)))
}

function isEmptyDisplayValue(value: unknown): boolean {
  return value === null || value === undefined || value === '' || value === '--'
}

function isWorkflowStateResponse(value: unknown): value is WorkflowStateResponse {
  return Boolean(
    value
    && typeof value === 'object'
    && 'latest_task' in value
    && 'recent_tasks' in value
  )
}

export default function Dashboard() {
  const toast = useToast()
  const [workflowLoading, setWorkflowLoading] = useState(true)
  const [workflowError, setWorkflowError] = useState<string | null>(null)
  const [context, setContext] = useState<DashboardContextResponse | null>(null)
  const [history, setHistory] = useState<WorkflowHistoryResponse | null>(null)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyStatus, setHistoryStatus] = useState('all')
  const [historySearch, setHistorySearch] = useState('')
  const [historyLimit, setHistoryLimit] = useState(12)
  const [uploading, setUploading] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [confirmingTakeoff, setConfirmingTakeoff] = useState(false)
  const [px4Running, setPx4Running] = useState(false)
  const [clock, setClock] = useState(() => formatNow(new Date()))
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const {
    data: wsData,
    connected,
    error: wsError,
    reconnectCount,
    refresh: refreshCombinedState,
  } = useEnhancedMapState()

  const workflow = isWorkflowStateResponse(wsData?.workflow_state) ? wsData.workflow_state : null
  useEffect(() => {
    const timer = setInterval(() => setClock(formatNow(new Date())), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    let active = true
    const loadContext = async () => {
      try {
        const next = await fetchDashboardContext()
        if (active) setContext(next)
      } catch (error) {
        if (active) console.error('Failed to load dashboard context', error)
      }
    }
    void loadContext()
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!wsData && !wsError) return
    setWorkflowLoading(false)
    if (wsData?.workflow_state) setWorkflowError(null)
  }, [wsData, wsError])

  useEffect(() => {
    if (reconnectCount < 1) return
    toast.success('实时连接已恢复')
  }, [reconnectCount])

  useEffect(() => {
    let active = true
    const loadHistory = async () => {
      try {
        const next = await fetchWorkflowHistory({
          limit: historyLimit,
          status: historyStatus,
          search: historySearch.trim() || undefined,
        })
        if (!active) return
        setHistory(next)
        setHistoryError(null)
      } catch (error) {
        if (!active) return
        setHistoryError(error instanceof Error ? error.message : '加载任务历史失败')
      } finally {
        if (active) setHistoryLoading(false)
      }
    }
    void loadHistory()
    return () => { active = false }
  }, [historyLimit, historyStatus, historySearch])

  const latestTask = workflow?.latest_task ?? null
  const field = asRecord(latestTask?.field)
  const spraySummary = asRecord(latestTask?.spray_summary)
  const decision = asRecord(latestTask?.decision)
  const medication = asRecord(decision['用药'])
  const weather = asRecord(latestTask?.weather)
  const agronomyTips = Array.isArray(decision['农事建议']) ? (decision['农事建议'] as string[]) : []
  const safetyTips = Array.isArray(medication['安全提示']) ? (medication['安全提示'] as string[]) : []
  const detections = latestTask?.detections ?? []
  const pestSummary = useMemo(() => summarizePests(detections), [detections])
  const primaryPest = detections.length > 0 ? formatPestLabel(detections[0]?.pest_type) : '等待识别'
  const currentArea = spraySummary['spray_area_mu'] ?? field['area_mu'] ?? '--'
  const currentAreaDisplay = typeof currentArea === 'number' || typeof currentArea === 'string' ? String(currentArea) : '--'
  const onlineDevices = latestTask?.drone?.task_id ? 1 : 0
  const rawRecentTasks = workflow?.recent_tasks ?? []
  const recentTasks = rawRecentTasks.map(mapTaskEntry)
  const currentDetectionCount = detections.length
  const todayTaskCount = rawRecentTasks.filter((t) => {
    if (!t.updated_at) return false
    const d = new Date(t.updated_at)
    if (Number.isNaN(d.getTime())) return false
    const today = new Date()
    return d.toDateString() === today.toDateString()
  }).length
  const detectionSparkline = rawRecentTasks.slice(0, 8).reverse().map((t) => t.progress ?? 0)
  const areaSparkline = rawRecentTasks.slice(0, 8).reverse().map((t) => {
    const num = t.spray_area_mu
    return typeof num === 'number' ? num : 0
  })
  const currentFieldName = String(field.field_name ?? field.field_id ?? '默认地块')
  const currentCropName = String(asRecord(field.crop_cycle).crop_name ?? '待识别作物')
  const missionProgress = Number(latestTask?.drone?.progress ?? 0)
  const taskProgress = clampPercent(missionProgress)
  const latestUpdateText = formatDateTime(latestTask?.updated_at)
  const originalImageUrl = latestTask ? `${buildTaskOriginalImageUrl(latestTask.request_id)}?t=${encodeURIComponent(latestTask.updated_at ?? '')}` : null
  const annotatedImageUrl = latestTask ? `${buildTaskAnnotatedImageUrl(latestTask.request_id)}?t=${encodeURIComponent(latestTask.updated_at ?? '')}` : null
  const combinedStatusError = workflowError ?? wsError ?? historyError
  const hasCurrentTask = Boolean(latestTask?.request_id)
  const pipelineStages = useMemo(() => deriveStages(latestTask), [latestTask])
  const activePipelineStage = pipelineStages.find((stage) => stage.status === 'active')
  const completedPipelineCount = pipelineStages.filter((stage) => stage.status === 'done').length
  const pipelineProgress = hasCurrentTask
    ? latestTask?.status === 'completed'
      ? 100
      : Math.max(taskProgress, Math.round((completedPipelineCount / Math.max(1, pipelineStages.length)) * 100))
    : 0
  const processedImageCount = latestTask?.image_path || uploading ? 1 : 0
  const activeStageKey = activePipelineStage?.key ?? ''
  const activeStageLabel = activePipelineStage
    ? HERO_STAGE_LABELS[activePipelineStage.key] ?? activePipelineStage.label
    : latestTask?.status === 'completed'
      ? '任务完成'
      : '等待输入'
  const heroTitle = uploading || activeStageKey === 'upload' || activeStageKey === 'detection'
    ? `▶ 正在识别虫情（已处理 ${processedImageCount} 张图像）`
    : !hasCurrentTask
      ? '智慧植保指挥平台'
      : latestTask?.status === 'completed'
        ? '✅ 本轮任务已完成'
        : activeStageKey === 'decision'
          ? '▶ 生成施药方案中…'
          : activeStageKey === 'drone'
            ? `▶ 无人机作业进行中（${taskProgress}%）`
            : '智慧植保指挥平台'
  const heroStageSummary = !hasCurrentTask
    ? '系统就绪，等待图像输入'
    : latestTask?.status === 'completed'
      ? '识别、决策与无人机执行闭环已完成'
      : activePipelineStage?.message ?? latestTask?.message ?? '任务正在推进'
  const commandMetaItems = [
    {
      label: '当前请求',
      value: latestTask?.request_id ? latestTask.request_id.slice(0, 12) : '--',
      emptyHint: '等待图像输入',
    },
    {
      label: '当前阶段',
      value: latestTask?.current_stage || '--',
      emptyHint: '系统就绪',
    },
    {
      label: '任务状态',
      value: latestTask?.status || '--',
      emptyHint: '无活跃任务',
    },
    {
      label: '总事件数',
      value: workflow?.event_count ?? '--',
      emptyHint: '等待事件记录',
    },
  ]

  const refreshHistory = async () => {
    setHistoryLoading(true)
    try {
      const next = await fetchWorkflowHistory({
        limit: historyLimit,
        status: historyStatus,
        search: historySearch.trim() || undefined,
      })
      setHistory(next)
      setHistoryError(null)
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : '刷新任务历史失败')
    } finally {
      setHistoryLoading(false)
    }
  }

  const refreshWorkflow = async () => {
    setWorkflowLoading(true)
    try {
      await refreshCombinedState()
      setWorkflowError(null)
    } catch (error) {
      setWorkflowError(error instanceof Error ? error.message : '刷新工作流失败')
    } finally {
      setWorkflowLoading(false)
    }
  }

  const handleUploadClick = () => {
    if (uploading) return
    fileInputRef.current?.click()
  }

  const handleUploadChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await uploadDemoImage(file)
      toast.success(`图片已发送：${file.name}`)
      await Promise.allSettled([refreshWorkflow(), refreshHistory()])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '图片上传失败')
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  const handleResetEvents = async () => {
    setResetting(true)
    try {
      await resetDemoEvents()
      toast.success('任务事件已清空')
      void refreshWorkflow()
      void refreshHistory()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '清空事件失败')
    } finally {
      setResetting(false)
    }
  }

  const handleConfirmTakeoff = async () => {
    setConfirmingTakeoff(true)
    try {
      await confirmDroneTakeoff()
      toast.success('已确认起飞')
      void refreshWorkflow()
      void refreshHistory()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '确认起飞失败')
    } finally {
      setConfirmingTakeoff(false)
    }
  }

  useEffect(() => {
    let active = true
    const check = async () => {
      try {
        const status = await getPx4Status()
        if (active) setPx4Running(status.running)
      } catch { /* ignore */ }
    }
    void check()
    const timer = window.setInterval(() => void check(), 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  const [px4Starting, setPx4Starting] = useState(false)

  const handlePx4Start = async () => {
    setPx4Starting(true)
    try {
      await startPx4Demo()
      toast.success('PX4 SITL 启动中…')
      setPx4Running(true)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'PX4 启动失败')
    } finally {
      setPx4Starting(false)
    }
  }

  const handlePx4Stop = async () => {
    try {
      await stopPx4Demo()
      toast.success('PX4 SITL 已停止')
      setPx4Running(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'PX4 停止失败')
    }
  }

  const showTakeoffBanner = String(latestTask?.drone?.status ?? '').toLowerCase() === 'pending_confirmation'

  return (
    <div className="dashboard-shell">
      <section className="dashboard-command-strip">
        <Card className="dashboard-card command-card">
          <div className="command-strip-topline">
            <div>
              <span className="panel-label">全自动闭环作业</span>
              <div className="command-strip-title">牧野智慧植保指挥平台</div>
              <div className="command-strip-subtitle">
                无人机定期航拍 → 图片自动进入识别管线 → 发现虫情后联动气象、RAG 知识与千问大模型生成施药方案 → 驱动无人机精准喷洒
              </div>
            </div>
            <div className="command-strip-right">
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <Tag color={modeColor(context?.modes.yolo)}>YOLO {context?.modes.yolo ?? '--'}</Tag>
                <Tag color={modeColor(context?.modes.weather)}>天气 {context?.modes.weather ?? '--'}</Tag>
                <Tag color={modeColor(context?.modes.qwen)}>千问 {context?.modes.qwen ?? '--'}</Tag>
                <Tag color={modeColor(context?.modes.drone)}>无人机 {context?.modes.drone ?? '--'}</Tag>
                <Tag color={connected ? 'green' : 'amber'} style={{ marginLeft: 8 }}>
                  {connected ? '实时' : '轮询'}
                </Tag>
              </div>
              <div className="command-clock">{clock}</div>
            </div>
          </div>

          <div className="demo-hero-grid">
            <div className="demo-hero-panel">
              <span className="panel-label">作业阶段</span>
              <div className="demo-hero-title">{heroTitle}</div>
              {hasCurrentTask ? (
                <>
                  <div className="hero-highlight">
                    <div className="hero-highlight-main">{primaryPest}</div>
                    <div className="hero-highlight-sub">
                      当前目标地块：{currentFieldName} · 当前作物：{currentCropName}
                    </div>
                  </div>
                  <div className="hero-bullet-list">
                    <div className="hero-bullet-item">
                      <strong>自动虫情识别</strong>
                      <span>图像到达后自动触发 YOLO 检测，无需人工干预</span>
                    </div>
                    <div className="hero-bullet-item">
                      <strong>知识增强决策</strong>
                      <span>融合实时气象、RAG 农药知识库与千问大模型生成施药方案</span>
                    </div>
                    <div className="hero-bullet-item">
                      <strong>无人机自主执行</strong>
                      <span>自动规划航线并联动 PX4 SITL 完成精准喷洒</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="hero-idle-guide">
                  <strong>系统自动监视 data/images/ 目录，无人机航拍图片落入后自动触发全链路处理</strong>
                  <span>可手动注入图像，触发同一条全自动管线：虫情识别 → 气象融合 → AI 决策 → 无人机执行</span>
                </div>
              )}
            </div>

            <div className="demo-hero-panel is-accent">
              <span className="panel-label">本轮任务状态</span>
              <div className="hero-progress-block">
                <div className="hero-progress-topline">
                  <div>
                    <span>当前阶段</span>
                    <strong>{activeStageLabel}</strong>
                  </div>
                  <strong>{pipelineProgress}%</strong>
                </div>
                <div className="hero-progress-track" aria-label={`本轮任务进度 ${pipelineProgress}%`}>
                  <span style={{ width: `${pipelineProgress}%` }} />
                </div>
                <div className="hero-stage-indicator" aria-label="本轮任务阶段">
                  {pipelineStages.map((stage, index) => (
                    <div key={stage.key} className="hero-stage-group">
                      <div className={`hero-stage-item is-${stage.status}`}>
                        <span className="hero-stage-dot" aria-hidden="true" />
                        <span>{HERO_STAGE_LABELS[stage.key] ?? stage.label}</span>
                      </div>
                      {index < pipelineStages.length - 1 && (
                        <span className={`hero-stage-connector ${stage.status === 'done' ? 'is-filled' : ''}`}>
                          →
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <div className="hero-storyline">
                <span className="hero-storyline-label">阶段说明</span>
                <strong>{heroStageSummary}</strong>
                <span>{hasCurrentTask ? `最后更新时间：${latestUpdateText}` : '等待任务启动'}</span>
              </div>
            </div>
          </div>

          <div className="command-strip-actions">
            <div className="command-action-group">
              <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png"
                className="upload-input"
                onChange={handleUploadChange}
              />
              <Button variant="primary" onClick={handleUploadClick} loading={uploading}>
                {uploading ? '管线处理中…' : '注入巡检图像'}
              </Button>
              <Button onClick={() => void refreshWorkflow()} loading={workflowLoading}>
                {workflowLoading ? '加载中…' : '重载实时画面'}
              </Button>
              <Button variant="danger" onClick={handleResetEvents} loading={resetting}>
                重置任务流程
              </Button>
              {px4Running ? (
                <Button variant="danger" onClick={() => void handlePx4Stop()}>
                  停止 PX4
                </Button>
              ) : (
                <Button variant="secondary" onClick={() => void handlePx4Start()} loading={px4Starting}>
                  {px4Starting ? 'PX4 启动中…' : '启动 PX4 仿真'}
                </Button>
              )}
            </div>

            <div className="command-strip-meta">
              {commandMetaItems.map((item) => {
                const isEmpty = isEmptyDisplayValue(item.value)
                return (
                  <div key={item.label} className="command-meta-item">
                    <span>{item.label}</span>
                    <strong className={isEmpty ? 'is-empty' : undefined}>{item.value}</strong>
                    {isEmpty && <small className="command-meta-hint">{item.emptyHint}</small>}
                  </div>
                )
              })}
            </div>
          </div>
        </Card>
      </section>

      <section className="dashboard-pipeline-strip">
        <Card className="dashboard-card">
          <PipelineStepper task={latestTask} />
        </Card>
      </section>

      {showTakeoffBanner ? (
        <Alert
          type="warning"
          message="无人机等待人工确认起飞"
          description={
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <span>当前任务已完成 AI 决策，点击按钮后继续执行无人机作业。</span>
              <Button variant="primary" size="lg" loading={confirmingTakeoff} onClick={handleConfirmTakeoff}>
                确认起飞
              </Button>
            </div>
          }
          className="dashboard-alert"
        />
      ) : null}

      {combinedStatusError ? (
        <Alert
          type="warning"
          message="部分实时数据暂不可用"
          description={combinedStatusError}
          className="dashboard-alert"
        />
      ) : null}

      <section className="mission-metric-ribbon" aria-label="作业关键指标">
        <StatCard
          className="stat-card-ribbon"
          label="当前作业面积"
          value={currentAreaDisplay}
          unit="亩"
          footnote={`数据来源：${spraySummary['spray_area_mu'] ? '喷洒记录' : field['area_mu'] ? '地块档案' : '暂无结构化面积'}`}
          sparklineData={areaSparkline}
          sparklineColor="var(--accent-green)"
        />

        <StatCard
          className="stat-card-ribbon"
          label="在线设备数"
          value={onlineDevices}
          unit="台"
          footnote="数据来源：当前任务中的 PX4 / 作业无人机"
        />

        <StatCard
          className="stat-card-ribbon"
          label="检测目标数"
          value={currentDetectionCount}
          unit="个"
          footnote={`数据来源：当前任务 YOLO 识别（${pestSummary.labels.length} 种害虫）`}
          sparklineData={detectionSparkline}
          sparklineColor="var(--accent-amber)"
        />

        <StatCard
          className="stat-card-ribbon"
          label="今日任务数"
          value={todayTaskCount}
          unit="条"
          footnote="数据来源：当日已完成/运行中的任务"
        />
      </section>

      <section className="dashboard-grid">
        <aside className="dashboard-column dashboard-column-left">
          <DecisionFlow task={latestTask} />
          {latestTask?.rag_context?.consultation_detail && (
            <Card className="dashboard-card">
              <ExpertPanel ragContext={latestTask.rag_context} />
            </Card>
          )}
        </aside>

        <main className="dashboard-column dashboard-column-center">
          <Card className="dashboard-card map-card map-card-hero">
            <div className="map-panel">
              <div className="map-header-strip">
                <span className="panel-label">无人机作业态势主视图</span>
                <span className="map-header-note">演示动画 / 地块边界 / 航线规划 / 检测点位</span>
              </div>
              <FieldMap droneStatus={latestTask?.drone?.status} />
            </div>
          </Card>
        </main>

        <aside className="dashboard-column dashboard-column-right">
          <TaskList tasks={recentTasks} />
        </aside>
      </section>

      <section className="dashboard-detail-grid">
        <Card className="dashboard-card image-card">
          <div className="detail-card-header">
            <span className="panel-label">农田原始输入</span>
            <span className="detail-card-meta">{latestTask?.image_path ?? '等待图片输入'}</span>
          </div>
          {originalImageUrl && latestTask?.image_path ? (
            <img src={originalImageUrl} alt="原始图片" className="detail-image" />
          ) : (
            <div className="detail-empty">请上传一张图片，或等待后端捕获图片。</div>
          )}
        </Card>

        <Card className="dashboard-card image-card">
          <div className="detail-card-header">
            <span className="panel-label">目标识别与标注</span>
            <span className="detail-card-meta">目标数 {detections.length}</span>
          </div>
          {annotatedImageUrl && latestTask?.image_path ? (
            <img src={annotatedImageUrl} alt="识别结果" className="detail-image" />
          ) : (
            <div className="detail-empty">等待识别结果。</div>
          )}
        </Card>

        <Card className="dashboard-card detail-card">
          <div className="detail-card-header">
            <span className="panel-label">识别摘要</span>
            <span className="detail-card-meta">
              种类 {pestSummary.labels.length} / 目标 {detections.length}
            </span>
          </div>
          <div className="pest-summary-main">{pestSummary.summary}</div>
          <div className="pill-wrap">
            {pestSummary.labels.length > 0 ? (
              pestSummary.labels.map((label) => (
                <span key={label} className="detail-pill is-success">
                  {label}
                </span>
              ))
            ) : (
              <span className="detail-pill is-muted">等待 YOLO 返回害虫名称</span>
            )}
          </div>
        </Card>

        <WeatherCard weather={weather} />

        <Card className="dashboard-card detail-card detail-card-wide">
          <div className="detail-card-header">
            <span className="panel-label">AI 决策与施药方案</span>
            <span className="detail-card-meta">{latestTask?.error ? `异常：${latestTask.error}` : '系统规划参数'}</span>
          </div>
          <div className="detail-metric-grid">
            <div className="detail-metric-card">
              <span>农药名称</span>
              <strong>{safeMetric(medication['农药名称'])}</strong>
            </div>
            <div className="detail-metric-card">
              <span>浓度</span>
              <strong>{safeMetric(medication['浓度'])}</strong>
            </div>
            <div className="detail-metric-card">
              <span>配比</span>
              <strong>{safeMetric(medication['配比'])}</strong>
            </div>
            <div className="detail-metric-card">
              <span>总量</span>
              <strong>{safeMetric(medication['总量'])}</strong>
            </div>
            <div className="detail-metric-card">
              <span>飞行高度</span>
              <strong>{safeMetric(asRecord(latestTask?.drone?.instruction)['高度'], ' m')}</strong>
            </div>
            <div className="detail-metric-card">
              <span>喷洒速率</span>
              <strong>{safeMetric(asRecord(latestTask?.drone?.instruction)['喷洒速率'])}</strong>
            </div>
          </div>

          <div className="detail-subsection">
            <span className="panel-label">安全提示</span>
            <div className="pill-wrap">
              {safetyTips.length > 0 ? (
                safetyTips.map((item) => (
                  <span key={item} className="detail-pill is-warning">
                    {item}
                  </span>
                ))
              ) : (
                <span className="detail-pill is-muted">暂无安全提示</span>
              )}
            </div>
          </div>

          <div className="detail-subsection">
            <span className="panel-label">农事建议</span>
            <div className="pill-wrap">
              {agronomyTips.length > 0 ? (
                agronomyTips.map((item) => (
                  <span key={item} className="detail-pill is-info">
                    {item}
                  </span>
                ))
              ) : (
                <span className="detail-pill is-muted">暂无农事建议</span>
              )}
            </div>
          </div>
        </Card>
      </section>

      <section className="dashboard-workflow-row">
        <Card className="dashboard-card workflow-card">
          <WorkflowPanel data={workflow} loading={workflowLoading} error={workflowError} />
        </Card>
      </section>

      <section className="dashboard-history-row">
        <Card className="dashboard-card history-card" title="任务历史检索">
          <div className="history-toolbar">
            <Select
              value={historyStatus}
              onChange={setHistoryStatus}
              options={[
                { label: '全部状态', value: 'all' },
                { label: '运行中', value: 'running' },
                { label: '已完成', value: 'completed' },
                { label: '异常', value: 'error' },
              ]}
            />
            <Input
              value={historySearch}
              onChange={setHistorySearch}
              placeholder="request_id / 图片路径 / 害虫类型"
              className="history-search"
            />
            <Select
              value={String(historyLimit)}
              onChange={(v) => setHistoryLimit(Number(v))}
              options={[
                { label: '12 条', value: '12' },
                { label: '24 条', value: '24' },
                { label: '40 条', value: '40' },
              ]}
            />
            <Button onClick={() => void refreshHistory()} loading={historyLoading}>
              查询
            </Button>
          </div>

          {historyError ? <Alert type="error" message={historyError} className="dashboard-alert" /> : null}

          {historyLoading && !history ? (
            <div className="history-empty">加载任务历史中...</div>
          ) : history && history.items.length > 0 ? (
            <div className="history-list">
              {history.items.map((item) => {
                const itemField = asRecord(item.field)
                const itemDecision = asRecord(item.decision)
                const itemMedication = asRecord(itemDecision['用药'])
                const itemWeather = asRecord(item.weather)

                return (
                  <div key={item.request_id} className="history-item">
                    <div className="history-topline">
                      <div>
                        <div className="history-request">{item.request_id}</div>
                        <div className="history-field">
                          {String(itemField.field_name ?? itemField.field_id ?? '未命名地块')}
                        </div>
                      </div>
                      <div className="history-tag-group">
                        <Tag color={item.status === 'completed' ? 'green' : item.status === 'error' ? 'red' : 'amber'}>
                          {item.status}
                        </Tag>
                        <Tag>{item.current_stage}</Tag>
                      </div>
                    </div>

                    <div className="history-message">{item.message || '暂无任务说明'}</div>

                    <div className="history-metrics">
                      <span>农药：{String(itemMedication['农药名称'] ?? '--')}</span>
                      <span>天气：{String(itemWeather.summary ?? '--')}</span>
                      <span>识别目标：{item.detections.length}</span>
                      <span>更新时间：{formatDateTime(item.updated_at)}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <Empty description="当前筛选条件下暂无结构化任务记录" />
          )}
        </Card>
      </section>

      {toast.holder}
    </div>
  )
}
