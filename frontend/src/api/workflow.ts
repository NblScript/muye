import { apiClient } from './client'
import type {
  DashboardContextResponse,
  WorkflowHistoryResponse,
  WorkflowStateResponse,
} from '../types/workflow'

export async function fetchWorkflowState() {
  const response = await apiClient.get<WorkflowStateResponse>('/workflow/state')
  return response.data
}

export async function fetchWorkflowHistory(params: {
  limit?: number
  status?: string
  search?: string
}) {
  const response = await apiClient.get<WorkflowHistoryResponse>('/workflow/history', {
    params,
  })
  return response.data
}

export async function fetchDashboardContext() {
  const response = await apiClient.get<DashboardContextResponse>('/dashboard/context')
  return response.data
}

export async function uploadDemoImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.post<{ filename: string; path: string }>('/demo/upload-image', formData)
  return response.data
}

export async function resetDemoEvents() {
  const response = await apiClient.post<{ status: string }>('/demo/reset-events', null, {
    params: { confirm: true }
  })
  return response.data
}

export async function confirmDroneTakeoff() {
  const response = await apiClient.post<{ status: string }>('/drone/confirm-takeoff')
  return response.data
}

export function buildTaskOriginalImageUrl(requestId: string) {
  return `/api/tasks/${requestId}/original-image`
}

export function buildTaskAnnotatedImageUrl(requestId: string) {
  return `/api/tasks/${requestId}/annotated-image`
}

export async function startPx4Demo(options?: { px4_dir?: string; world?: string; skip_px4?: boolean }) {
  const response = await apiClient.post<{ status: string; pid?: string; world?: string; log?: string }>(
    '/drone/start-px4-demo',
    options ?? {},
  )
  return response.data
}

export async function stopPx4Demo() {
  const response = await apiClient.post<{ status: string }>('/drone/stop-px4-demo')
  return response.data
}

export async function getPx4Status() {
  const response = await apiClient.get<{ running: boolean; ready: boolean; pid?: number }>('/drone/px4-status')
  return response.data
}
