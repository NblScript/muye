import { apiClient } from './client'
import type { SimMapStateResponse } from '../types/simMap'

export async function fetchSimMapState() {
  const response = await apiClient.get<SimMapStateResponse>('/sim/map-state')
  return response.data
}

export function buildSimMapWebSocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/sim/ws/map-state`
}

export function buildEnhancedMapWebSocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/enhanced-state`
}
