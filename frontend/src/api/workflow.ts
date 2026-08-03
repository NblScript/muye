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

export async function uploadInspectionImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.post<{ filename: string; path: string }>('/workflow/inspection-image', formData)
  return response.data
}

export async function confirmDroneTakeoff() {
  const response = await apiClient.post<{ status: string }>('/drone/confirm-takeoff')
  return response.data
}
