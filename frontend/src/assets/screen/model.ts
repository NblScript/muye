import type {
  ComplianceResult,
  MissionIteration,
  WorkflowEventEntry,
  WorkflowTaskState,
} from '../../types/workflow'

export type PanelTone = 'green' | 'amber' | 'red' | 'blue' | 'muted'

export interface PestMetric {
  name: string
  count: number
  confidence: number
}

export interface WeatherMetric {
  label: string
  value: string
  unit: string
  tone: PanelTone
}

export interface PipelineStageMetric {
  key: string
  label: string
  status: 'done' | 'active' | 'pending' | 'error'
  message: string
}

export interface DecisionMetric {
  pesticide: string
  concentration: string
  dilution: string
  total: string
  complianceStatus: ComplianceResult['status'] | 'pending'
  complianceScore: number
  complianceSummary: string
  decisionPath: string
  confidence: number
  expertCount: number
  advice: string[]
}

export interface DroneMetric {
  taskId: string
  status: string
  statusLabel: string
  message: string
  progress: number
  waypoint: number
  waypointTotal: number
  altitude: string
  speed: string
  sprayRate: string
  latitude: number | null
  longitude: number | null
}

export interface EvaluationMetric {
  status: string
  statusLabel: string
  killRate: number
  threshold: number
  beforeCount: number | null
  afterCount: number | null
  currentIteration: number
  maxIterations: number
  verdict: string
  iterations: MissionIteration[]
}

export interface FieldMetric {
  name: string
  province: string
  city: string
  county: string
  crop: string
  area: string
  pestCount: number
  riskLabel: string
}

export interface TwinPoint {
  x: number
  y: number
}

export interface TwinPestPoint extends TwinPoint {
  name: string
  confidence: number
}

export interface TwinHeatCell extends TwinPoint {
  width: number
  height: number
  density: number
}

export interface FieldTwinMetric {
  boundary: TwinPoint[]
  route: TwinPoint[]
  pestPoints: TwinPestPoint[]
  heatCells: TwinHeatCell[]
  dronePosition: TwinPoint | null
  boundarySource: 'virtual'
  hasRoute: boolean
}

export interface ScreenViewModel {
  requestId: string
  updatedAt: string
  connected: boolean
  status: string
  statusLabel: string
  message: string
  progress: number
  field: FieldMetric
  pests: PestMetric[]
  weather: WeatherMetric[]
  weatherReady: boolean
  weatherSuitable: boolean
  pipeline: PipelineStageMetric[]
  events: WorkflowEventEntry[]
  decision: DecisionMetric
  drone: DroneMetric
  evaluation: EvaluationMetric
  fieldTwin: FieldTwinMetric
}

const PEST_LABELS: Record<string, string> = {
  aphid: '蚜虫',
  planthopper: '稻飞虱',
  armyworm: '粘虫',
  bollworm: '棉铃虫',
  locust: '蝗虫',
  whitefly: '白粉虱',
  spider_mite: '红蜘蛛',
}

const DRONE_STATUS_LABELS: Record<string, string> = {
  submitted: '任务提交',
  queued: '等待执行',
  connecting: '连接飞控',
  connected: '飞控在线',
  ready: '定位就绪',
  uploaded: '航线上传',
  armed: '已解锁',
  pending_confirmation: '等待起飞确认',
  takeoff: '正在起飞',
  enroute: '前往作业区',
  patrolling: '巡检飞行',
  spraying: '变量喷洒',
  inspecting: '药效复检',
  returning: '自动返航',
  completed: '任务完成',
  failed: '任务失败',
  error: '执行异常',
}

const PIPELINE_STAGES = [
  { key: 'upload', label: '图像接入', eventStages: ['queue', 'upload', 'pipeline'] },
  { key: 'detection', label: '虫情识别', eventStages: ['yolo', 'detection'] },
  { key: 'weather', label: '气象采集', eventStages: ['weather'] },
  { key: 'decision', label: 'AI 会诊', eventStages: ['router', 'rag', 'decision'] },
  { key: 'compliance', label: '合规审核', eventStages: ['compliance'] },
  { key: 'drone', label: '无人机执行', eventStages: ['drone'] },
  { key: 'evaluation', label: '药效复检', eventStages: ['evaluation', 'mission'] },
]

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim()
    if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  }
  return ''
}

function firstNumber(...values: unknown[]): number | null {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value === 'string') {
      const match = value.match(/-?\d+(?:\.\d+)?/)
      if (match) return Number(match[0])
    }
  }
  return null
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function normalizeRate(value: number | null): number {
  if (value === null) return 0
  return Math.max(0, Math.min(1, value > 1 ? value / 100 : value))
}

function pestLabel(value: string): string {
  const normalized = value.trim().toLowerCase()
  return PEST_LABELS[normalized] ?? value.trim() ?? '未知害虫'
}

function buildPests(task: WorkflowTaskState | null): PestMetric[] {
  const grouped = new Map<string, { count: number; confidenceTotal: number }>()
  for (const detection of task?.detections ?? []) {
    const name = pestLabel(firstText(detection.pest_type, '未知害虫'))
    const confidence = normalizeRate(firstNumber(detection.confidence) ?? 0)
    const current = grouped.get(name) ?? { count: 0, confidenceTotal: 0 }
    current.count += 1
    current.confidenceTotal += confidence
    grouped.set(name, current)
  }
  return [...grouped.entries()]
    .map(([name, value]) => ({
      name,
      count: value.count,
      confidence: value.count ? value.confidenceTotal / value.count : 0,
    }))
    .sort((left, right) => right.count - left.count)
}

function metricTone(value: number | null, warning: (value: number) => boolean): PanelTone {
  if (value === null) return 'muted'
  return warning(value) ? 'amber' : 'green'
}

function buildWeather(source: Record<string, unknown>): {
  metrics: WeatherMetric[]
  ready: boolean
  suitable: boolean
} {
  const temperature = firstNumber(source.temperature, source.temp)
  const humidity = firstNumber(source.humidity)
  const wind = firstNumber(source.wind_speed, source.windSpeed)
  const summary = firstText(source.summary, source.text, '等待气象数据')
  const ready = temperature !== null || humidity !== null || wind !== null || summary !== '等待气象数据'
  const suitable = ready && wind !== null && wind <= 5 && humidity !== null && humidity >= 35 && humidity < 85

  return {
    ready,
    suitable,
    metrics: [
      {
        label: '实时天气',
        value: summary,
        unit: '',
        tone: summary === '等待气象数据' ? 'muted' : 'blue',
      },
      {
        label: '温度',
        value: temperature === null ? '--' : temperature.toFixed(1),
        unit: '°C',
        tone: metricTone(temperature, (value) => value < 5 || value > 35),
      },
      {
        label: '相对湿度',
        value: humidity === null ? '--' : humidity.toFixed(0),
        unit: '%',
        tone: metricTone(humidity, (value) => value < 35 || value >= 85),
      },
      {
        label: '平均风速',
        value: wind === null ? '--' : wind.toFixed(1),
        unit: 'm/s',
        tone: metricTone(wind, (value) => value > 5),
      },
    ],
  }
}

function eventStatus(event: WorkflowEventEntry | undefined): PipelineStageMetric['status'] {
  if (!event) return 'pending'
  const status = String(event.status ?? '').toLowerCase()
  if (status === 'error' || status === 'failed' || status === 'blocked') return 'error'
  if (['completed', 'passed', 'evaluated', 'created'].includes(status)) return 'done'
  return 'active'
}

function buildPipeline(task: WorkflowTaskState | null): PipelineStageMetric[] {
  const events = task?.recent_events ?? []
  return PIPELINE_STAGES.map((stage) => {
    const event = events.slice().reverse().find((item) => stage.eventStages.includes(item.stage))
    let status = eventStatus(event)
    if (stage.key === 'detection' && (task?.detections.length ?? 0) > 0) status = 'done'
    if (stage.key === 'decision' && Object.keys(task?.decision ?? {}).length > 0) status = 'done'
    if (stage.key === 'compliance' && task?.compliance) {
      status = task.compliance.status === 'blocked' ? 'error' : 'done'
    }
    if (stage.key === 'drone' && task?.drone?.status) {
      const droneStatus = task.drone.status.toLowerCase()
      status = ['completed', 'returning'].includes(droneStatus)
        ? 'done'
        : ['failed', 'error'].includes(droneStatus)
          ? 'error'
          : 'active'
    }
    if (stage.key === 'evaluation' && task?.evaluation?.status) {
      const evaluationStatus = task.evaluation.status.toLowerCase()
      status = ['completed', 'evaluated', 'effective'].includes(evaluationStatus) ? 'done' : 'active'
    }
    return {
      key: stage.key,
      label: stage.label,
      status,
      message: event?.message ?? (status === 'pending' ? '等待进入该阶段' : task?.message ?? ''),
    }
  })
}

function buildDecision(task: WorkflowTaskState | null): DecisionMetric {
  const medication = asRecord(task?.decision?.['用药'])
  const adviceRaw = task?.decision?.['农事建议']
  const advice = Array.isArray(adviceRaw) ? adviceRaw.map(String).filter(Boolean) : []
  const rag = task?.rag_context
  const compliance = task?.compliance
  const confidence = normalizeRate(firstNumber(rag?.confidence, rag?.familiarity_score))
  const decisionPath = rag?.decision_path === 'multi_agent'
    ? '多智能体会诊'
    : rag?.decision_path === 'escalated'
      ? '专家升级会诊'
      : rag?.decision_path === 'expert'
        ? '快速专家路径'
        : '等待决策路由'

  return {
    pesticide: firstText(medication['农药名称'], '等待 AI 推荐'),
    concentration: firstText(medication['浓度'], '--'),
    dilution: firstText(medication['配比'], '--'),
    total: firstText(medication['总量'], '--'),
    complianceStatus: compliance?.status ?? 'pending',
    complianceScore: firstNumber(compliance?.score) ?? 0,
    complianceSummary: compliance?.summary ?? '等待农药安全合规审核',
    decisionPath,
    confidence,
    expertCount: firstNumber(rag?.consultation_detail?.active_count) ?? 0,
    advice,
  }
}

function buildDrone(task: WorkflowTaskState | null, progress: number): DroneMetric {
  const drone = task?.drone
  const instruction = drone?.instruction
  const status = firstText(drone?.status, 'idle').toLowerCase()
  const position = drone?.position
  return {
    taskId: firstText(drone?.task_id, '--'),
    status,
    statusLabel: DRONE_STATUS_LABELS[status] ?? (status === 'idle' ? '待命' : status),
    message: firstText(drone?.message, task?.message, '等待无人机任务'),
    progress: clampPercent(firstNumber(drone?.progress, progress) ?? 0),
    waypoint: Math.max(0, Math.round(firstNumber(drone?.current_waypoint_index) ?? 0)),
    waypointTotal: instruction?.飞行路径?.length ?? 0,
    altitude: firstText(instruction?.高度, position?.relative_altitude_m, '--'),
    speed: firstText(instruction?.速度, '--'),
    sprayRate: firstText(instruction?.喷洒速率, '--'),
    latitude: firstNumber(position?.latitude_deg, position?.latitude),
    longitude: firstNumber(position?.longitude_deg, position?.longitude),
  }
}

function latestEvaluationEvent(events: WorkflowEventEntry[]): {
  event: WorkflowEventEntry | undefined
  payload: Record<string, unknown>
} {
  const event = events.slice().reverse().find((item) => item.stage === 'evaluation')
  return { event, payload: asRecord(event?.payload) }
}

function buildEvaluation(task: WorkflowTaskState | null): EvaluationMetric {
  const evaluation = task?.evaluation
  const mission = task?.mission
  const { event: evaluationEvent, payload: eventPayload } = latestEvaluationEvent(task?.recent_events ?? [])
  const killRate = normalizeRate(firstNumber(
    evaluation?.kill_rate,
    mission?.final_kill_rate,
    eventPayload.kill_rate,
  ))
  const threshold = normalizeRate(firstNumber(
    evaluation?.kill_rate_threshold,
    mission?.kill_rate_threshold,
    eventPayload.threshold,
  ) ?? 0.9)
  const status = firstText(
    evaluation?.status,
    mission?.status,
    eventPayload.status,
    evaluationEvent?.status,
    'pending',
  ).toLowerCase()
  const beforeCount = firstNumber(evaluation?.pre_pest_count, eventPayload.before_count, eventPayload.pre_pest_count)
  const afterCount = firstNumber(evaluation?.post_pest_count, eventPayload.after_count, eventPayload.post_pest_count)
  const currentIteration = Math.max(0, Math.round(firstNumber(
    mission?.current_iteration,
    eventPayload.rounds,
    evaluation?.retry_count,
  ) ?? 0))
  const maxIterations = Math.max(0, Math.round(firstNumber(mission?.max_iterations) ?? 0))
  const statusLabel = status === 'completed' || status === 'evaluated' || status === 'effective'
    ? '评估完成'
    : status === 'active' || status === 'inspecting'
      ? '复检进行中'
      : status === 'failed' || status === 'ineffective'
        ? '防治未达标'
        : '等待药效复检'
  const verdict = killRate <= 0
    ? '喷洒完成后将自动调度复检'
    : killRate >= threshold
      ? `杀灭率 ${(killRate * 100).toFixed(0)}%，达到闭环目标`
      : `尚差 ${((threshold - killRate) * 100).toFixed(0)}%，系统将进入下一轮`

  return {
    status,
    statusLabel,
    killRate,
    threshold,
    beforeCount,
    afterCount,
    currentIteration,
    maxIterations,
    verdict,
    iterations: mission?.iterations ?? [],
  }
}

function buildField(task: WorkflowTaskState | null, pests: PestMetric[]): FieldMetric {
  const field = asRecord(task?.field)
  const cropCycle = asRecord(field.crop_cycle)
  const pestCount = pests.reduce((sum, item) => sum + item.count, 0)
  const averageConfidence = pests.length
    ? pests.reduce((sum, item) => sum + item.confidence, 0) / pests.length
    : 0
  const riskLabel = pestCount === 0
    ? '暂无虫情'
    : pestCount >= 20 || averageConfidence >= 0.85
      ? '高风险'
      : pestCount >= 8 || averageConfidence >= 0.65
        ? '中风险'
        : '低风险'

  return {
    name: firstText(field.field_name, field.name, field.field_id, task ? '未命名地块' : '未绑定地块'),
    province: firstText(field.province, ''),
    city: firstText(field.city, ''),
    county: firstText(field.county, ''),
    crop: firstText(field.crop_name, cropCycle.crop_name, task?.mission?.crop_name, '--'),
    area: firstText(field.area_mu, task?.spray_summary?.spray_area_mu, '--'),
    pestCount,
    riskLabel,
  }
}

const VIRTUAL_FIELD_BOUNDARY: TwinPoint[] = [
  { x: 0.08, y: 0.12 },
  { x: 0.9, y: 0.06 },
  { x: 0.96, y: 0.88 },
  { x: 0.13, y: 0.94 },
]

type GeoBounds = { minX: number; maxX: number; minY: number; maxY: number }

function validGeoPoint(value: unknown): value is [number, number] {
  return Array.isArray(value)
    && value.length >= 2
    && Number.isFinite(Number(value[0]))
    && Number.isFinite(Number(value[1]))
}

function getGeoBounds(points: [number, number][]): GeoBounds | null {
  if (points.length === 0) return null
  const xs = points.map((point) => Number(point[0]))
  const ys = points.map((point) => Number(point[1]))
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  }
}

function normalizeGeoPoint(point: [number, number], bounds: GeoBounds): TwinPoint {
  const xSpan = bounds.maxX - bounds.minX
  const ySpan = bounds.maxY - bounds.minY
  const normalizedX = xSpan > 0 ? (point[0] - bounds.minX) / xSpan : 0.5
  const normalizedY = ySpan > 0 ? 1 - ((point[1] - bounds.minY) / ySpan) : 0.5
  return {
    x: 0.08 + Math.max(0, Math.min(1, normalizedX)) * 0.84,
    y: 0.08 + Math.max(0, Math.min(1, normalizedY)) * 0.84,
  }
}

function buildTwinPestPoints(task: WorkflowTaskState | null): TwinPestPoint[] {
  const detections = (task?.detections ?? []).slice(0, 24)
  const positioned = detections.map((detection) => {
    const position = detection.position
    const x1 = firstNumber(position?.x1)
    const x2 = firstNumber(position?.x2)
    const y1 = firstNumber(position?.y1)
    const y2 = firstNumber(position?.y2)
    return x1 !== null && x2 !== null && y1 !== null && y2 !== null
      ? { x: (x1 + x2) / 2, y: (y1 + y2) / 2 }
      : null
  })
  const xs = positioned.flatMap((point) => point ? [point.x] : [])
  const ys = positioned.flatMap((point) => point ? [point.y] : [])
  const minX = xs.length > 1 ? Math.min(...xs) : 0
  const maxX = xs.length > 1 ? Math.max(...xs) : 1
  const minY = ys.length > 1 ? Math.min(...ys) : 0
  const maxY = ys.length > 1 ? Math.max(...ys) : 1
  const goldenAngle = Math.PI * (3 - Math.sqrt(5))

  return detections.map((detection, index) => {
    const point = positioned[index]
    const fallbackRadius = 0.26 * Math.sqrt((index + 0.5) / Math.max(1, detections.length))
    const virtualX = point
      ? 0.2 + ((point.x - minX) / Math.max(1, maxX - minX)) * 0.6
      : 0.5 + Math.cos(index * goldenAngle) * fallbackRadius
    const virtualY = point
      ? 0.2 + ((point.y - minY) / Math.max(1, maxY - minY)) * 0.58
      : 0.49 + Math.sin(index * goldenAngle) * fallbackRadius
    return {
      x: Math.max(0.16, Math.min(0.84, virtualX)),
      y: Math.max(0.16, Math.min(0.82, virtualY)),
      name: pestLabel(firstText(detection.pest_type, '未知害虫')),
      confidence: normalizeRate(firstNumber(detection.confidence) ?? 0),
    }
  })
}

function interpolateRoute(route: TwinPoint[], progress: number): TwinPoint | null {
  if (route.length === 0) return null
  if (route.length === 1) return route[0]
  const scaled = Math.max(0, Math.min(1, progress)) * (route.length - 1)
  const startIndex = Math.floor(scaled)
  const endIndex = Math.min(route.length - 1, startIndex + 1)
  const factor = scaled - startIndex
  return {
    x: route[startIndex].x + (route[endIndex].x - route[startIndex].x) * factor,
    y: route[startIndex].y + (route[endIndex].y - route[startIndex].y) * factor,
  }
}

function buildFieldTwin(task: WorkflowTaskState | null): FieldTwinMetric {
  const instruction = task?.drone?.instruction
  const coverage = (instruction?.覆盖区域?.coordinates ?? []).filter(validGeoPoint)
  const rawRoute = (instruction?.飞行路径 ?? []).filter(validGeoPoint)
  const densityCells = instruction?.density_grid ?? []
  const densityPoints = densityCells.flatMap((cell) => cell.bounds.filter(validGeoPoint))
  const boundsSource = coverage.length >= 3 ? coverage : [...rawRoute, ...densityPoints]
  const geoBounds = getGeoBounds(boundsSource)
  const boundary = VIRTUAL_FIELD_BOUNDARY
  const route = geoBounds ? rawRoute.map((point) => normalizeGeoPoint(point, geoBounds)) : []
  const pestPoints = buildTwinPestPoints(task)
  const heatCells = geoBounds && densityCells.length > 0
    ? densityCells.flatMap<TwinHeatCell>((cell) => {
      const points = cell.bounds.filter(validGeoPoint)
      if (points.length < 2 || cell.density <= 0) return []
      const normalized = points.map((point) => normalizeGeoPoint(point, geoBounds))
      const xs = normalized.map((point) => point.x)
      const ys = normalized.map((point) => point.y)
      return [{
        x: Math.min(...xs),
        y: Math.min(...ys),
        width: Math.max(0.025, Math.max(...xs) - Math.min(...xs)),
        height: Math.max(0.025, Math.max(...ys) - Math.min(...ys)),
        density: normalizeRate(firstNumber(cell.density)),
      }]
    })
    : pestPoints.map((point) => ({
      x: point.x - 0.045,
      y: point.y - 0.045,
      width: 0.09,
      height: 0.09,
      density: point.confidence,
    }))

  const latitude = firstNumber(task?.drone?.position?.latitude_deg, task?.drone?.position?.latitude)
  const longitude = firstNumber(task?.drone?.position?.longitude_deg, task?.drone?.position?.longitude)
  const actualPosition = geoBounds && latitude !== null && longitude !== null
    ? normalizeGeoPoint([longitude, latitude], geoBounds)
    : null
  const progress = normalizeRate(firstNumber(task?.drone?.progress) ?? 0)
  const waypointIndex = Math.max(0, Math.round(firstNumber(task?.drone?.current_waypoint_index) ?? 0))
  const routePosition = route[waypointIndex] ?? interpolateRoute(route, progress)

  return {
    boundary,
    route,
    pestPoints,
    heatCells,
    dronePosition: actualPosition ?? routePosition,
    boundarySource: 'virtual',
    hasRoute: route.length >= 2,
  }
}

function taskStatusLabel(status: string): string {
  const normalized = status.toLowerCase()
  if (normalized === 'completed') return '本轮任务完成'
  if (normalized === 'failed' || normalized === 'error') return '任务异常'
  if (normalized === 'running' || normalized === 'active') return '任务执行中'
  return status && status !== 'idle' ? status : '系统待命'
}

export function buildScreenViewModel(
  task: WorkflowTaskState | null | undefined,
  weatherSource: Record<string, unknown> | undefined,
  progress = 0,
  connected = false,
): ScreenViewModel {
  const currentTask = task ?? null
  const pests = buildPests(currentTask)
  const weather = buildWeather(weatherSource ?? currentTask?.weather ?? {})
  const status = firstText(currentTask?.status, 'idle')
  return {
    requestId: firstText(currentTask?.request_id, '--'),
    updatedAt: firstText(currentTask?.updated_at, ''),
    connected,
    status,
    statusLabel: taskStatusLabel(status),
    message: firstText(currentTask?.message, '系统已就绪，等待巡检图像'),
    progress: clampPercent(progress),
    field: buildField(currentTask, pests),
    pests,
    weather: weather.metrics,
    weatherReady: weather.ready,
    weatherSuitable: weather.suitable,
    pipeline: buildPipeline(currentTask),
    events: currentTask?.recent_events ?? [],
    decision: buildDecision(currentTask),
    drone: buildDrone(currentTask, progress),
    evaluation: buildEvaluation(currentTask),
    fieldTwin: buildFieldTwin(currentTask),
  }
}
