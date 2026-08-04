import { type ChangeEvent, useCallback, useEffect, useRef, useState } from 'react'

import {
  confirmDroneTakeoff,
  fetchLatestHeatmap,
  uploadInspectionImage,
} from '../api/workflow'
import { useWorkflowRealtimeState } from './useWorkflowRealtimeState'
import { useToast } from '../components/ui'
import type { HeatmapSnapshotDetail, WorkflowTaskState } from '../types/workflow'
import { derivePipelineProgress } from '../utils/pipelineStages'
import { retainLatestEventBusTask } from '../utils/workflowState'

export function useDashboardState() {
  const toast = useToast()
  const [refreshing, setRefreshing] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [confirmingTakeoff, setConfirmingTakeoff] = useState(false)
  const [latestTask, setLatestTask] = useState<WorkflowTaskState | null>(null)
  const [latestHeatmap, setLatestHeatmap] = useState<HeatmapSnapshotDetail | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const notifiedReconnectCountRef = useRef(0)
  const heatmapRequestRef = useRef(0)

  const {
    data: wsData,
    connected,
    error: wsError,
    reconnectCount,
    refresh: refreshCombinedState,
  } = useWorkflowRealtimeState()

  const workflowLoading = refreshing || (!wsData && !wsError)

  useEffect(() => {
    setLatestTask((current) => retainLatestEventBusTask(current, wsData?.workflow_state))
  }, [wsData?.workflow_state])

  useEffect(() => {
    if (reconnectCount <= notifiedReconnectCountRef.current) return
    notifiedReconnectCountRef.current = reconnectCount
    toast.success('实时连接已恢复')
  }, [reconnectCount, toast])

  const rawFieldId = latestTask?.field?.field_id
  const activeFieldId = typeof rawFieldId === 'string' && rawFieldId.trim()
    ? rawFieldId.trim()
    : undefined

  const refreshHeatmap = useCallback(async (fieldId?: string) => {
    const requestNumber = heatmapRequestRef.current + 1
    heatmapRequestRef.current = requestNumber
    try {
      const snapshot = await fetchLatestHeatmap(fieldId)
      if (heatmapRequestRef.current === requestNumber) setLatestHeatmap(snapshot)
      return snapshot
    } catch {
      // Keep the last valid snapshot on transient API/connection failures.
      return null
    }
  }, [])

  useEffect(() => {
    void refreshHeatmap(activeFieldId)
  }, [activeFieldId, refreshHeatmap])

  // The API keeps a legacy PX4 demo fallback for older consumers. This screen
  // renders only real event-bus tasks and retains the last valid snapshot when
  // a transient WebSocket message contains no workflow state.
  const weather = latestTask?.weather ?? {}
  const pipelineProgress = derivePipelineProgress(latestTask)
  const showTakeoffBanner = String(latestTask?.drone?.status ?? '').toLowerCase() === 'pending_confirmation'

  const refreshWorkflow = async () => {
    setRefreshing(true)
    try {
      await Promise.all([refreshCombinedState(), refreshHeatmap(activeFieldId)])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '刷新工作流失败')
    } finally {
      setRefreshing(false)
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
      await uploadInspectionImage(file)
      toast.success(`图片已发送：${file.name}`)
      await refreshWorkflow()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '图片上传失败')
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  const handleConfirmTakeoff = async () => {
    setConfirmingTakeoff(true)
    try {
      await confirmDroneTakeoff()
      toast.success('已确认起飞')
      void refreshWorkflow()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '确认起飞失败')
    } finally {
      setConfirmingTakeoff(false)
    }
  }

  return {
    fileInputRef,
    connected,
    toast,
    workflowLoading,
    latestTask,
    latestHeatmap: latestHeatmap
      && activeFieldId
      && latestHeatmap.field_id
      && latestHeatmap.field_id !== activeFieldId
      ? null
      : latestHeatmap,
    pipelineProgress,
    showTakeoffBanner,
    weather,
    uploading,
    confirmingTakeoff,
    refreshWorkflow,
    handleUploadClick,
    handleUploadChange,
    handleConfirmTakeoff,
  }
}
