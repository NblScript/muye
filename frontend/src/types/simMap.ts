import type { WorkflowStateResponse } from './workflow'

export interface SimPoint {
  x: number
  y: number
}

export type SimDroneStatus = '作业中' | '返航'

export interface SimDroneState {
  id: string
  name: string
  status: SimDroneStatus
  battery: number
  position: SimPoint
  route: SimPoint[]
}

export interface SimMapStateResponse {
  timestamp: number
  drones: SimDroneState[]
}

export interface WsCombinedState {
  timestamp: number
  sim_map: SimMapStateResponse | null
  workflow_state: WorkflowStateResponse | null
}
