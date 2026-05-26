import { apiClient } from './client'
import type { HealthResponse } from '../types/health'

export async function fetchHealth() {
  const response = await apiClient.get<HealthResponse>('/health', {
    validateStatus: (status) => status < 600,
  })
  return response.data
}
