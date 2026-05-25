export interface WorkflowEventEntry {
  timestamp: string
  stage: string
  status: string
  message: string
  payload?: Record<string, unknown>
}

export interface WorkflowTimelineEntry {
  timestamp?: string | null
  status: string
  message: string
  progress?: number | null
  current_waypoint_index?: number | null
  task_id?: string | null
}

export interface WorkflowDetectionPosition {
  x1?: number
  y1?: number
  x2?: number
  y2?: number
}

export interface WorkflowDetectionEntry {
  pest_type?: string
  confidence?: number
  position?: WorkflowDetectionPosition
}

export interface WorkflowDroneInstruction {
  飞行路径?: [number, number][]
  覆盖区域?: {
    coordinates?: [number, number][]
  }
  高度?: number | string
  速度?: number | string
  喷洒速率?: number | string
}

export interface WorkflowDronePosition {
  latitude?: number
  longitude?: number
  latitude_deg?: number
  longitude_deg?: number
  absolute_altitude_m?: number
  relative_altitude_m?: number
}

export interface WorkflowDroneState {
  task_id?: string
  status?: string
  message?: string
  progress?: number
  current_waypoint_index?: number
  instruction?: WorkflowDroneInstruction
  position?: WorkflowDronePosition
}

export interface RagDocument {
  content: string
  score: number
  metadata?: Record<string, unknown>
}

export interface ExpertSummary {
  name: string
  weight: number
  农药名称: string
  总量: string
}

export interface ConsultationDetail {
  experts?: Record<string, ExpertSummary>
  failed_roles?: string[]
  active_count?: number
  vote_distribution?: Record<string, number>
}

export interface RagContext {
  pesticides?: RagDocument[]
  historical_cases?: RagDocument[]
  knowledge?: RagDocument[]
  pest_types?: string[]
  crop_name?: string | null
  consultation_detail?: ConsultationDetail
  confidence?: number
  agreement?: string
  decision_path?: 'expert' | 'multi_agent'
  familiarity_score?: number
}

export interface WorkflowTaskState {
  request_id: string
  current_stage: string
  status: string
  message: string
  updated_at?: string | null
  image_path?: string | null
  field: Record<string, unknown>
  detections: WorkflowDetectionEntry[]
  weather: Record<string, unknown>
  spray_summary: Record<string, unknown>
  decision: Record<string, unknown>
  rag_context?: RagContext
  drone: WorkflowDroneState
  drone_timeline: WorkflowTimelineEntry[]
  recent_events: WorkflowEventEntry[]
  error?: string | null
}

export interface DashboardTaskEntry {
  request_id: string
  updated_at?: string | null
  status: string
  current_stage: string
  field_name: string
  drone_label: string
  progress: number
  pesticide_name?: string | null
  spray_area_mu?: number | null
  is_current: boolean
}

export interface WorkflowStateResponse {
  source: 'event_bus' | 'fallback'
  event_count: number
  latest_task: WorkflowTaskState
  recent_tasks: DashboardTaskEntry[]
}

export interface WorkflowHistoryEntry {
  request_id: string
  current_stage: string
  status: string
  message: string
  updated_at?: string | null
  image_path?: string | null
  field: Record<string, unknown>
  detections: WorkflowDetectionEntry[]
  weather: Record<string, unknown>
  spray_summary: Record<string, unknown>
  decision: Record<string, unknown>
  drone: WorkflowDroneState
  error?: string | null
}

export interface WorkflowHistoryResponse {
  total: number
  items: WorkflowHistoryEntry[]
}

export interface DashboardContextResponse {
  modes: Record<string, string>
  upload_accept: string[]
}
