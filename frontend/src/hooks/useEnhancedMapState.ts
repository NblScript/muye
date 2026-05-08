import { useMemo } from 'react'

import { buildEnhancedMapWebSocketUrl, fetchSimMapState } from '../api/simMap'
import { fetchWorkflowState } from '../api/workflow'
import { useWebSocket } from './useWebSocket'
import type { SimMapStateResponse, WsEnhancedState } from '../types/simMap'

export type EnhancedMapConnectionStatus = 'connecting' | 'connected' | 'polling' | 'error'

export type EnhancedMapState = WsEnhancedState & {
  legacy_sim_map?: SimMapStateResponse | null
}

type UseEnhancedMapStateResult = {
  data: EnhancedMapState | null
  connected: boolean
  status: EnhancedMapConnectionStatus
  error: string | null
  reconnectCount: number
  refresh: () => Promise<void>
}

function buildFallbackState(
  workflowState: Awaited<ReturnType<typeof fetchWorkflowState>> | null,
  simMapState: SimMapStateResponse | null,
): EnhancedMapState {
  return {
    timestamp: Date.now() / 1000,
    drone: {
      id: 'px4-sitl',
      name: 'PX4 SITL 飞行器',
      status: 'connecting',
      message: '等待连接...',
      battery: { remaining: simMapState?.drones[0]?.battery ?? 0 },
      telemetry: { speed: 0 },
    },
    mission: {
      task_id: workflowState?.latest_task.request_id,
      status: workflowState?.latest_task.status ?? 'unknown',
      progress: workflowState?.latest_task.drone.progress ?? 0,
      current_waypoint: workflowState?.latest_task.drone.current_waypoint_index ?? 0,
      total_waypoints: 0,
      planned_route: [],
    },
    trajectory: {
      recent_points: [],
      total_distance: 0,
    },
    workflow_state: workflowState,
    legacy_sim_map: simMapState,
  }
}

export function useEnhancedMapState(): UseEnhancedMapStateResult {
  const url = useMemo(() => buildEnhancedMapWebSocketUrl(), [])
  const { data, connected, error, reconnectCount, refresh } = useWebSocket<EnhancedMapState>(
    url,
    async () => {
      const [workflowResult, simMapResult] = await Promise.allSettled([
        fetchWorkflowState(),
        fetchSimMapState(),
      ])

      if (workflowResult.status === 'rejected' && simMapResult.status === 'rejected') {
        throw workflowResult.reason instanceof Error
          ? workflowResult.reason
          : simMapResult.reason instanceof Error
            ? simMapResult.reason
            : new Error('实时地图状态加载失败')
      }

      return buildFallbackState(
        workflowResult.status === 'fulfilled' ? workflowResult.value : null,
        simMapResult.status === 'fulfilled' ? simMapResult.value : null,
      )
    },
    2000,
  )

  return {
    data,
    connected,
    status: connected ? 'connected' : error ? 'error' : data ? 'polling' : 'connecting',
    error,
    reconnectCount,
    refresh,
  }
}
