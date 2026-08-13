import { apiClient } from './client'
import type {
  DashboardContextResponse,
  HeatmapComparisonResponse,
  HeatmapSnapshotDetail,
  HeatmapSnapshotListResponse,
  HeatmapInspectionKind,
  MissionDetail,
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

export async function fetchLatestHeatmap(fieldId?: string) {
  const response = await apiClient.get<HeatmapSnapshotDetail>('/heatmaps/latest', {
    params: fieldId ? { field_id: fieldId } : undefined,
  })
  return response.data
}

export async function fetchHeatmapSnapshots(params: {
  field_id?: string
  request_id?: string
  mission_id?: string
  pest_type?: string
  source?: string
  is_simulated?: boolean
  inspection_kind?: HeatmapInspectionKind
  captured_from?: string
  captured_to?: string
  limit?: number
  offset?: number
} = {}) {
  const response = await apiClient.get<HeatmapSnapshotListResponse>('/heatmaps/snapshots', { params })
  return response.data
}

export async function fetchHeatmapSnapshot(snapshotId: string) {
  const response = await apiClient.get<HeatmapSnapshotDetail>(
    `/heatmaps/snapshots/${encodeURIComponent(snapshotId)}`,
  )
  return response.data
}

export async function fetchHeatmapComparison(requestId: string, iterationNumber?: number) {
  const response = await apiClient.get<HeatmapComparisonResponse>(
    `/heatmaps/comparison/${encodeURIComponent(requestId)}`,
    { params: iterationNumber ? { iteration_number: iterationNumber } : undefined },
  )
  return response.data
}

export async function fetchMission(missionId: string) {
  const response = await apiClient.get<MissionDetail>(
    `/mission/${encodeURIComponent(missionId)}`,
  )
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
