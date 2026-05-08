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

export type DroneStatus = 'connecting' | 'ready' | 'takeoff' | 'spraying' | 'returning' | 'completed' | 'error'

export interface GPSPosition {
  latitude: number
  longitude: number
  altitude: number
  absolute_altitude?: number
  heading?: number
  speed?: number
  timestamp: number
}

export interface TelemetryData {
  speed: number
  ground_speed?: number
  air_speed?: number
  heading?: number
  climb_rate?: number
}

export interface BatteryState {
  remaining: number
  voltage?: number
  current?: number
  temperature?: number
}

export interface DroneState {
  id: string
  name: string
  status: DroneStatus
  message: string
  position?: GPSPosition
  battery: BatteryState
  telemetry: TelemetryData
}

export interface MissionState {
  task_id?: string
  status: string
  progress: number
  current_waypoint: number
  total_waypoints: number
  planned_route: GPSPosition[]
}

export interface TrajectoryState {
  recent_points: GPSPosition[]
  total_distance: number
}

export interface FieldState {
  id: string
  name: string
  boundary: GPSPosition[]
}

export interface WsEnhancedState {
  timestamp: number
  drone: DroneState
  mission: MissionState
  trajectory: TrajectoryState
  field?: FieldState
  workflow_state?: WorkflowStateResponse | Record<string, unknown> | null
}

export interface WsCombinedState {
  timestamp: number
  sim_map: SimMapStateResponse | null
  workflow_state: WorkflowStateResponse | null
}
