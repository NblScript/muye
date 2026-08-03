import { type ChangeEvent, useEffect, useRef, useState } from 'react'

import {
  confirmDroneTakeoff,
  uploadInspectionImage,
} from '../api/workflow'
import { useWorkflowRealtimeState } from './useWorkflowRealtimeState'
import { useToast } from '../components/ui'
import type { WorkflowTaskState } from '../types/workflow'
import { derivePipelineProgress } from '../utils/pipelineStages'
import { retainLatestEventBusTask } from '../utils/workflowState'

export function useDashboardState() {
  const toast = useToast()
  const [refreshing, setRefreshing] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [confirmingTakeoff, setConfirmingTakeoff] = useState(false)
  const [latestTask, setLatestTask] = useState<WorkflowTaskState | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const notifiedReconnectCountRef = useRef(0)

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

  // The API keeps a legacy PX4 demo fallback for older consumers. This screen
  // renders only real event-bus tasks and retains the last valid snapshot when
  // a transient WebSocket message contains no workflow state.
  const weather = latestTask?.weather ?? {}
  const pipelineProgress = derivePipelineProgress(latestTask)
  const showTakeoffBanner = String(latestTask?.drone?.status ?? '').toLowerCase() === 'pending_confirmation'

  const refreshWorkflow = async () => {
    setRefreshing(true)
    try {
      await refreshCombinedState()
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
