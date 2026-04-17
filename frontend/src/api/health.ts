import { apiClient } from './client'
import type { HealthResponse } from '../types/health'

export async function fetchHealth() {
  const response = await apiClient.get<HealthResponse>('/health')
  return response.data
}
