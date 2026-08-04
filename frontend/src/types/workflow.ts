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
  coordinate_space?: 'image_pixel' | 'image_normalized' | string
  image_width?: number
  image_height?: number
}

export interface WorkflowDetectionEntry {
  image_path?: string | null
  pest_type?: string
  confidence?: number
  position?: WorkflowDetectionPosition
}

export interface DensityGridCell {
  row: number
  col: number
  density: number
  bounds: [number, number][]
}

export interface DensityGridMetadata {
  source?: string
  algorithm_version?: string
  density_kind?: string
  coordinate_space?: string
  projection?: string
  normalization?: string
  grid_rows?: number
  grid_cols?: number
  detection_count?: number
  accepted_detection_count?: number
  rejected_detection_count?: number
  is_simulated?: boolean
  status?: string
  reason?: string
}

export interface SprayRateBand {
  label: string
  minimum: number
  maximum_exclusive?: number | null
  multiplier: number
}

export interface SprayRatePolicy {
  basis?: string
  base_rate_lpm?: number | string | null
  bands?: SprayRateBand[]
}

export interface WorkflowDroneInstruction {
  飞行路径?: [number, number][]
  覆盖区域?: {
    coordinates?: [number, number][]
  }
  高度?: number | string
  速度?: number | string
  喷洒速率?: number | string
  density_grid?: DensityGridCell[]
  density_metadata?: DensityGridMetadata
  spray_schedule?: number[]
  source?: string
  planning_mode?: 'variable_rate' | 'uniform_fallback' | string
  heatmap_snapshot_id?: string | null
  heatmap_algorithm_version?: string | null
  heatmap_snapshot_source?: string
  heatmap_trace_status?: string
  degradation_reason?: string
  spray_rate_policy?: SprayRatePolicy
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
  llm_provider?: string
  reasoning?: string
}

export interface FamiliarityBreakdown {
  pesticide_match?: number
  historical_cases?: number
  crop_similarity?: number
  catalog_coverage?: number
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
  decision_path?: 'expert' | 'multi_agent' | 'escalated'
  familiarity_score?: number
  familiarity_breakdown?: FamiliarityBreakdown
}

export interface ComplianceEvidence {
  source: string
  title: string
  matched_fields: string[]
}

export interface ComplianceCheck {
  rule: string
  name: string
  status: 'passed' | 'warning' | 'blocked'
  message: string
  evidence: ComplianceEvidence[]
}

export interface ExecutionPolicy {
  takeoff_mode: 'auto' | 'manual' | 'blocked'
  reason: string
}

export interface ComplianceAlternative {
  pesticide: string
  reason: string
  score: number
}

export interface ComplianceResult {
  status: 'passed' | 'warning' | 'blocked'
  score: number
  summary: string
  checks: ComplianceCheck[]
  blocking_reasons: string[]
  warnings: string[]
  execution_policy: ExecutionPolicy
  alternatives: ComplianceAlternative[]
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
  compliance?: ComplianceResult
  rag_context?: RagContext
  drone: WorkflowDroneState
  drone_timeline: WorkflowTimelineEntry[]
  recent_events: WorkflowEventEntry[]
  error?: string | null
  evaluation?: EvaluationResult
  mission?: MissionDetail
}

export interface EvaluationResult {
  evaluation_id?: number
  status: string
  kill_rate?: number | null
  pre_pest_count?: number | null
  post_pest_count?: number | null
  kill_rate_threshold?: number
  action_time_hours?: number | null
  retry_count?: number
  scheduled_at?: string | null
  evaluated_at?: string | null
  notes?: string | null
  message?: string
  needs_confirmation?: boolean
}

export interface MissionIteration {
  iteration_id: number
  iteration_number: number
  spray_request_id?: string | null
  status: string
  pre_pest_count?: number | null
  post_pest_count?: number | null
  kill_rate?: number | null
  heatmap_snapshot_id?: string | null
  heatmap_algorithm_version?: string | null
  spray_plan?: WorkflowDroneInstruction
  spray_completed_at?: string | null
  inspected_at?: string | null
  evaluated_at?: string | null
  notes?: string | null
}

export interface MissionDetail {
  mission_row_id: number
  mission_uuid: string
  original_request_id: string
  field_id?: string | null
  status: string
  kill_rate_threshold: number
  max_iterations: number
  current_iteration: number
  final_kill_rate?: number | null
  pest_types: string[]
  pesticide_name?: string | null
  crop_name?: string | null
  created_at?: string | null
  completed_at?: string | null
  notes?: string | null
  iterations: MissionIteration[]
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

export type HeatmapInspectionKind = 'pre_spray' | 'reinspection'

export interface HeatmapSnapshotSummary {
  snapshot_id: string
  batch_id: string
  request_id: string
  field_id?: string | null
  mission_id?: string | null
  iteration_number: number
  inspection_kind: HeatmapInspectionKind
  captured_at: string
  algorithm_version: string
  pest_counts: Record<string, number>
  total_detection_count: number
  hotspot_cell_count: number
  peak_relative_heat: number
  source: string
  is_simulated: boolean
  legacy: boolean
  created_at?: string | null
}

export interface HeatmapSnapshotDetail extends HeatmapSnapshotSummary {
  density_grid: DensityGridCell[]
  density_metadata: DensityGridMetadata
  image_paths: string[]
  detections: WorkflowDetectionEntry[]
}

export interface HeatmapSnapshotListResponse {
  total: number
  limit: number
  offset: number
  items: HeatmapSnapshotSummary[]
}

export interface HeatmapComparisonMetrics {
  detection_count_change: number
  hotspot_cell_count_change: number
  peak_relative_heat_change: number
}

export interface HeatmapComparisonResponse {
  request_id: string
  mission_id?: string | null
  iteration_number: number
  status: 'paired' | 'pending_pre_spray' | 'pending_reinspection'
  pre_spray?: HeatmapSnapshotDetail | null
  reinspection?: HeatmapSnapshotDetail | null
  metrics?: HeatmapComparisonMetrics | null
}

export interface DashboardContextResponse {
  modes: Record<string, string>
  upload_accept: string[]
  demo_mode?: boolean
}

export type DemoReadinessStatus = 'ready' | 'degraded' | 'blocked'
export type DemoReadinessCheckStatus = 'ok' | 'warning' | 'error'

export interface DemoReadinessCheck {
  key: string
  label: string
  status: DemoReadinessCheckStatus
  detail: string
  reason?: string
  impact?: string
  system_action?: string
  human_action?: string
}

export interface DemoReadinessResponse {
  status: DemoReadinessStatus
  summary: {
    ok: number
    warning: number
    error: number
  }
  checks: Record<string, DemoReadinessCheck>
  issues: DemoReadinessCheck[]
}

export interface DJITelemetry {
  latitude: number
  longitude: number
  altitude: number
  battery_percent: number
  drone_model: string
  connected: boolean
  mode: string
}

export interface DJIStatus {
  backend: string
  execution_mode: string
  drone_model: string
  connected: boolean
}
