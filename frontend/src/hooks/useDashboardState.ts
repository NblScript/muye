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
import { useEnhancedMapState } from './useEnhancedMapState'
import { useToast } from '../components/ui'
import type { DashboardContextResponse, WorkflowHistoryResponse, WorkflowStateResponse } from '../types/workflow'
import {
  asRecord,
  formatDateTime,
  formatNow,
  mapTaskEntry,
  summarizePests,
  formatPestLabel,
} from '../utils/dashboardUtils'
import { deriveStages } from '../components/dashboard/PipelineStepper'

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

function isWorkflowStateResponse(value: unknown): value is WorkflowStateResponse {
  return Boolean(value && typeof value === 'object' && 'latest_task' in value && 'recent_tasks' in value)
}

export function useDashboardState() {
  const toast = useToast()
  const [demoMode, setDemoMode] = useState(false)
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
  const [px4Starting, setPx4Starting] = useState(false)
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

  // ── Timers ──
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

  // ── Derived state ──
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
    return d.toDateString() === new Date().toDateString()
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
  const originalImageUrl = latestTask
    ? `${buildTaskOriginalImageUrl(latestTask.request_id)}?t=${encodeURIComponent(latestTask.updated_at ?? '')}`
    : null
  const annotatedImageUrl = latestTask
    ? `${buildTaskAnnotatedImageUrl(latestTask.request_id)}?t=${encodeURIComponent(latestTask.updated_at ?? '')}`
    : null
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
  const windSpeed = Number(weather.wind_speed ?? weather.windSpeed ?? 0)
  const humidity = Number(weather.humidity ?? 0)
  const weatherOk = windSpeed <= 5 && humidity >= 40
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
  const combinedStatusError = workflowError ?? wsError ?? historyError
  const showTakeoffBanner = String(latestTask?.drone?.status ?? '').toLowerCase() === 'pending_confirmation'

  const commandMetaItems = [
    { label: '当前请求', value: latestTask?.request_id ? latestTask.request_id.slice(0, 12) : '--', emptyHint: '等待图像输入' },
    { label: '当前阶段', value: latestTask?.current_stage || '--', emptyHint: '系统就绪' },
    { label: '任务状态', value: latestTask?.status || '--', emptyHint: '无活跃任务' },
    { label: '总事件数', value: workflow?.event_count ?? '--', emptyHint: '等待事件记录' },
  ]

  // ── Handlers ──
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

  return {
    // UI state
    demoMode, setDemoMode,
    clock,
    fileInputRef,
    connected,

    // Workflow
    workflowLoading, workflowError, workflow,
    latestTask, hasCurrentTask,
    pipelineStages, pipelineProgress, activeStageLabel, heroTitle, heroStageSummary,
    showTakeoffBanner,

    // Task data
    field, spraySummary, decision, medication, weather,
    agronomyTips, safetyTips, detections, pestSummary,
    primaryPest, currentAreaDisplay, currentFieldName, currentCropName,
    onlineDevices, currentDetectionCount, todayTaskCount,
    recentTasks,
    detectionSparkline, areaSparkline,
    latestUpdateText, originalImageUrl, annotatedImageUrl,
    commandMetaItems, combinedStatusError,
    weatherOk,

    // History
    history, historyLoading, historyError,
    historyStatus, setHistoryStatus,
    historySearch, setHistorySearch,
    historyLimit, setHistoryLimit,

    // Context
    context,

    // Action states
    uploading, resetting, confirmingTakeoff,
    px4Running, px4Starting,

    // Handlers
    refreshHistory, refreshWorkflow,
    handleUploadClick, handleUploadChange,
    handleResetEvents, handleConfirmTakeoff,
    handlePx4Start, handlePx4Stop,
  }
}
