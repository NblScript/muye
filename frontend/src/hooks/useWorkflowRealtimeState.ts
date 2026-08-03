import { useMemo } from 'react'

import { buildWorkflowWebSocketUrl } from '../api/realtime'
import { fetchWorkflowState } from '../api/workflow'
import type { WorkflowStateResponse } from '../types/workflow'
import { useWebSocket } from './useWebSocket'

export type WorkflowRealtimeState = {
  workflow_state?: WorkflowStateResponse | Record<string, unknown> | null
}

export function useWorkflowRealtimeState() {
  const url = useMemo(() => buildWorkflowWebSocketUrl(), [])

  return useWebSocket<WorkflowRealtimeState>(
    url,
    async () => ({ workflow_state: await fetchWorkflowState() }),
    2000,
  )
}
