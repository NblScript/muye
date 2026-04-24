import type { LatLngTuple } from 'leaflet'
import type { SimDroneState, SimMapStateResponse } from '../../types/simMap'
import type { WorkflowTaskState } from '../../types/workflow'
import { mapCenter, type FieldPlot, type FieldStatus } from './mapData'

type FieldMapProps = {
  transport?: 'websocket' | 'polling'
  latestTask?: WorkflowTaskState | null
  simMapState?: SimMapStateResponse | null
}

type PointPair = [number, number]

function fieldStatusStyle(status: FieldStatus) {
  if (status === '作业中') {
    return {
      stroke: '#28d7ff',
      fill: '#13c2c2',
      fillOpacity: 0.2,
    }
  }

  if (status === '已完成') {
    return {
      stroke: '#52c41a',
      fill: '#52c41a',
      fillOpacity: 0.14,
    }
  }

  return {
    stroke: '#fadb14',
    fill: '#faad14',
    fillOpacity: 0.14,
  }
}

function droneStatusStyle(status: SimDroneState['status']) {
  if (status === '作业中') {
    return {
      stroke: '#22d3ee',
      fill: '#67e8f9',
    }
  }

  if (status === '返航') {
    return {
      stroke: '#f97316',
      fill: '#fdba74',
    }
  }

  return {
    stroke: '#818cf8',
    fill: '#a5b4fc',
  }
}

function toNumber(value: unknown) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {}
}

function toPointPairs(value: unknown): PointPair[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .map((item) => {
      if (!Array.isArray(item) || item.length < 2) {
        return null
      }
      const x = toNumber(item[0])
      const y = toNumber(item[1])
      if (x === null || y === null) {
        return null
      }
      return [x, y] as PointPair
    })
    .filter((item): item is PointPair => item !== null)
}

function toDronePointPair(value: unknown): PointPair | null {
  const position = asRecord(value)
  const longitude = toNumber(position.longitude ?? position.longitude_deg ?? position.lng)
  const latitude = toNumber(position.latitude ?? position.latitude_deg ?? position.lat)
  if (longitude === null || latitude === null) {
    return null
  }
  return [longitude, latitude]
}

function getFieldName(field: Record<string, unknown>) {
  return String(field.field_name ?? field.name ?? field.field_id ?? '未命名地块')
}

function getFieldCrop(field: Record<string, unknown>) {
  const cropCycle = asRecord(field.crop_cycle)
  return String(
    cropCycle.crop_name
      ?? field.crop_name
      ?? cropCycle.crop_code
      ?? field.crop_code
      ?? '未标注作物',
  )
}

function getFieldStatus(latestTask: WorkflowTaskState | null | undefined): FieldStatus {
  const droneStatus = String(latestTask?.drone?.status ?? '')
  const taskStatus = String(latestTask?.status ?? '')

  if (droneStatus === 'spraying' || droneStatus === '作业中' || taskStatus === 'running') {
    return '作业中'
  }
  if (droneStatus === 'completed' || droneStatus === '已完成' || taskStatus === 'completed') {
    return '已完成'
  }
  return '待作业'
}

function isSimulationCoordinatePairs(points: PointPair[]) {
  return points.every(([x, y]) => x >= 0 && x <= 160 && y >= 0 && y <= 100)
}

function buildCoordinateProjector(pointGroups: PointPair[][]) {
  const allPoints = pointGroups.flat()
  if (allPoints.length === 0) {
    return (points: PointPair[], minPoints: number): LatLngTuple[] => {
      if (points.length < minPoints) {
        return []
      }
      return points.map(([x, y]) => [y, x] as LatLngTuple)
    }
  }

  if (isSimulationCoordinatePairs(allPoints)) {
    return (points: PointPair[], minPoints: number): LatLngTuple[] => {
      if (points.length < minPoints) {
        return []
      }
      return points.map(([x, y]) => [y, x] as LatLngTuple)
    }
  }

  const xs = allPoints.map(([x]) => x)
  const ys = allPoints.map(([, y]) => y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const spanX = Math.max(maxX - minX, 1e-6)
  const spanY = Math.max(maxY - minY, 1e-6)
  const targetMinX = 22
  const targetMaxX = 138
  const targetMinY = 16
  const targetMaxY = 84

  return (points: PointPair[], minPoints: number): LatLngTuple[] => {
    if (points.length < minPoints) {
      return []
    }

    return points.map(([x, y]) => {
      const normalizedX = targetMinX + ((x - minX) / spanX) * (targetMaxX - targetMinX)
      const normalizedY = targetMinY + ((y - minY) / spanY) * (targetMaxY - targetMinY)
      return [normalizedY, normalizedX] as LatLngTuple
    })
  }
}

function buildSyntheticFieldBoundary(areaMu: number | null): LatLngTuple[] {
  const size = Math.min(22, Math.max(10, Math.sqrt(areaMu ?? 36)))
  const halfWidth = size
  const halfHeight = Math.max(8, size * 0.65)
  return [
    [50 - halfHeight, 80 - halfWidth],
    [50 - halfHeight, 80 + halfWidth],
    [50 + halfHeight, 80 + halfWidth],
    [50 + halfHeight, 80 - halfWidth],
  ]
}

function computeCenter(boundary: LatLngTuple[]): LatLngTuple {
  const total = boundary.reduce(
    (acc, [lat, lng]) => {
      acc.lat += lat
      acc.lng += lng
      return acc
    },
    { lat: 0, lng: 0 },
  )
  return [total.lat / boundary.length, total.lng / boundary.length]
}

function buildPrimaryFieldPlot(
  field: Record<string, unknown>,
  latestTask: WorkflowTaskState | null | undefined,
  projectedGeofence: LatLngTuple[],
  coveragePoints: LatLngTuple[],
): FieldPlot | null {
  if (Object.keys(field).length === 0) {
    return null
  }

  const areaMu = toNumber(field.area_mu) ?? 0
  const boundary = projectedGeofence.length >= 3
    ? projectedGeofence
    : coveragePoints.length >= 3
      ? coveragePoints
      : buildSyntheticFieldBoundary(areaMu)

  return {
    id: String(field.field_id ?? latestTask?.request_id ?? 'runtime-field'),
    name: getFieldName(field),
    crop: getFieldCrop(field),
    areaMu,
    status: getFieldStatus(latestTask),
    boundary,
    center: computeCenter(boundary),
  }
}

function mapDroneStatus(status: string): SimDroneState['status'] {
  const normalized = status.trim().toLowerCase()
  if (normalized === 'returning' || normalized === '返航' || normalized === 'completed') {
    return '返航'
  }
  return '作业中'
}

function interpolateRoutePosition(route: LatLngTuple[], progressPercent: number): LatLngTuple {
  if (route.length === 0) {
    return mapCenter
  }
  if (route.length === 1) {
    return route[0]
  }

  const normalizedProgress = Math.min(1, Math.max(0, progressPercent / 100))
  const scaledIndex = normalizedProgress * (route.length - 1)
  const lowerIndex = Math.floor(scaledIndex)
  const upperIndex = Math.min(route.length - 1, lowerIndex + 1)
  const segmentProgress = scaledIndex - lowerIndex
  const [startLat, startLng] = route[lowerIndex]
  const [endLat, endLng] = route[upperIndex]

  return [
    startLat + (endLat - startLat) * segmentProgress,
    startLng + (endLng - startLng) * segmentProgress,
  ]
}

function buildTaskDrivenDrones(
  latestTask: WorkflowTaskState | null | undefined,
  projectedRoute: LatLngTuple[],
  projectedPosition: LatLngTuple | null,
): SimDroneState[] {
  if (!latestTask) {
    return []
  }

  const drone = asRecord(latestTask.drone)
  const waypointIndexValue = Number(drone.current_waypoint_index)
  const progressValue = Number(drone.progress)
  const progressPercent = Number.isFinite(progressValue)
    ? Math.max(0, Math.min(100, progressValue))
    : 0
  const hasRouteRelativeWaypointIndex = Number.isFinite(waypointIndexValue)
    && waypointIndexValue >= 0
    && waypointIndexValue < projectedRoute.length
  const fallbackPosition = projectedRoute.length > 0
    ? (hasRouteRelativeWaypointIndex
      ? projectedRoute[waypointIndexValue]
      : interpolateRoutePosition(projectedRoute, progressPercent))
    : mapCenter
  const [lat, lng] = projectedPosition ?? fallbackPosition
  const taskId = String(drone.task_id ?? latestTask.request_id ?? 'px4-primary')

  return [
    {
      id: taskId,
      name: String(drone.task_id ?? 'PX4 SITL 飞行器'),
      status: mapDroneStatus(String(drone.status ?? latestTask.status ?? '作业中')),
      battery: 100,
      position: { x: lng, y: lat },
      route: projectedRoute.map(([routeLat, routeLng]) => ({ x: routeLng, y: routeLat })),
    },
  ]
}

function toLatLngPoint(x: number, y: number): LatLngTuple {
  return [y, x]
}

function buildSimRoutePoints(simMapState: SimMapStateResponse | null | undefined): LatLngTuple[] {
  const route = simMapState?.drones.find((item) => item.route.length >= 2)?.route ?? []
  return route.map((point) => toLatLngPoint(point.x, point.y))
}

function toSvgPoint([lat, lng]: LatLngTuple) {
  return `${lng},${lat}`
}

function toSvgPoints(points: LatLngTuple[]) {
  return points.map(toSvgPoint).join(' ')
}

function computeViewBox(pointGroups: LatLngTuple[][], fallbackCenter: LatLngTuple): string {
  const points = pointGroups.flat()
  if (points.length < 2) {
    return '0 0 160 100'
  }

  const xs = points.map(([, lng]) => lng)
  const ys = points.map(([lat]) => lat)
  const minX = Math.max(0, Math.min(...xs) - 8)
  const maxX = Math.min(160, Math.max(...xs) + 8)
  const minY = Math.max(0, Math.min(...ys) - 8)
  const maxY = Math.min(100, Math.max(...ys) + 8)
  const width = Math.max(24, maxX - minX)
  const height = Math.max(18, maxY - minY)

  if (!Number.isFinite(width) || !Number.isFinite(height)) {
    const [lat, lng] = fallbackCenter
    return `${Math.max(0, lng - 24)} ${Math.max(0, lat - 16)} 48 32`
  }

  return `${minX} ${minY} ${width} ${height}`
}

export default function FieldMap({ transport = 'polling', latestTask, simMapState }: FieldMapProps) {
  const instruction = asRecord(latestTask?.drone?.instruction)
  const medication = asRecord(asRecord(latestTask?.decision)['用药'])
  const field = asRecord(latestTask?.field)

  const rawFieldGeofence = toPointPairs(field.geofence)
  const rawPresetRoutePoints = toPointPairs(field.explicit_route)
  const rawInstructionRoutePoints = toPointPairs(instruction['飞行路径'])
  const rawRoutePoints = rawInstructionRoutePoints.length >= 2 ? rawInstructionRoutePoints : rawPresetRoutePoints
  const rawCoveragePoints = toPointPairs(asRecord(instruction['覆盖区域']).coordinates)
  const rawDronePoint = toDronePointPair(asRecord(latestTask?.drone).position)
  const projectPairs = buildCoordinateProjector([
    rawFieldGeofence,
    rawPresetRoutePoints,
    rawInstructionRoutePoints,
    rawRoutePoints,
    rawCoveragePoints,
    rawDronePoint ? [rawDronePoint] : [],
  ])

  const projectedGeofence = projectPairs(rawFieldGeofence, 3)
  const taskRoutePoints = projectPairs(rawRoutePoints, 1)
  const coveragePoints = projectPairs(rawCoveragePoints, 3)
  const projectedDronePosition = rawDronePoint ? projectPairs([rawDronePoint], 1)[0] : null
  const primaryFieldPlot = buildPrimaryFieldPlot(field, latestTask, projectedGeofence, coveragePoints)
  const displayFieldPlots = primaryFieldPlot ? [primaryFieldPlot] : []
  const simRoutePoints = buildSimRoutePoints(simMapState)
  const routePoints = taskRoutePoints.length >= 2 ? taskRoutePoints : simRoutePoints
  const activeDrones = latestTask
    ? buildTaskDrivenDrones(latestTask, routePoints, projectedDronePosition)
    : (simMapState?.drones.length ? simMapState.drones : [])
  const activeDroneCount = activeDrones.filter((item) => item.status === '作业中').length
  const totalAreaMu = displayFieldPlots.reduce((sum, item) => sum + item.areaMu, 0)
  const activeDronePointGroups = activeDrones.map((item) => [toLatLngPoint(item.position.x, item.position.y)])
  const routeSource = rawInstructionRoutePoints.length >= 2
    ? 'PX4 执行'
    : taskRoutePoints.length >= 2
      ? '后端预设'
      : simRoutePoints.length >= 2
        ? '仿真推送'
        : '暂无'
  const viewBox = computeViewBox(
    [
      ...displayFieldPlots.map((item) => item.boundary),
      coveragePoints,
      routePoints,
      ...activeDronePointGroups,
      ...(projectedDronePosition ? [[projectedDronePosition]] : []),
    ],
    primaryFieldPlot?.center ?? mapCenter,
  )

  return (
    <div className="field-map-shell">
      <svg
        className="field-map"
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="当前作业地图"
      >
        <defs>
          <pattern id="map-grid" width="8" height="8" patternUnits="userSpaceOnUse">
            <path d="M 8 0 L 0 0 0 8" fill="none" stroke="rgba(109, 211, 255, 0.16)" strokeWidth="0.35" />
          </pattern>
          <filter id="drone-glow">
            <feGaussianBlur stdDeviation="1.2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="0" y="0" width="160" height="100" fill="#07192b" />
        <rect x="0" y="0" width="160" height="100" fill="url(#map-grid)" opacity="0.7" />
        <rect
          x="0"
          y="0"
          width="160"
          height="100"
          fill="rgba(8, 26, 45, 0.28)"
          stroke="rgba(109, 211, 255, 0.22)"
          strokeWidth="0.5"
        />

        {displayFieldPlots.map((fieldItem) => {
          const style = fieldStatusStyle(fieldItem.status)
          return (
            <g key={fieldItem.id}>
              <polygon
                points={toSvgPoints(fieldItem.boundary)}
                fill={style.fill}
                fillOpacity={style.fillOpacity}
                stroke={style.stroke}
                strokeWidth="0.8"
              />
              <text
                x={fieldItem.center[1]}
                y={fieldItem.center[0]}
                textAnchor="middle"
                fontSize="4"
                fill="#eff9ff"
                stroke="rgba(5, 18, 31, 0.85)"
                strokeWidth="0.5"
                paintOrder="stroke"
              >
                {fieldItem.name}
              </text>
            </g>
          )
        })}

        {coveragePoints.length >= 3 ? (
          <polygon
            points={toSvgPoints(coveragePoints)}
            fill="#fb923c"
            fillOpacity="0.08"
            stroke="#f97316"
            strokeWidth="0.8"
            strokeDasharray="2 2"
          />
        ) : null}

        {routePoints.length >= 2 ? (
          <>
            <polyline
              points={toSvgPoints(routePoints)}
              fill="none"
              stroke="#22c55e"
              strokeWidth="1.1"
              strokeDasharray="2.6 2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {routePoints.map((point, index) => (
              <g key={`route-waypoint-${index}-${point[0].toFixed(3)}-${point[1].toFixed(3)}`}>
                <circle
                  cx={point[1]}
                  cy={point[0]}
                  r={index === 0 ? 1.5 : 1.1}
                  fill={index === 0 ? '#86efac' : '#22c55e'}
                  stroke="#14532d"
                  strokeWidth="0.5"
                />
                {index === 0 ? (
                  <text
                    x={point[1] + 1.8}
                    y={point[0] - 1.2}
                    fontSize="3"
                    fill="#d9ffe7"
                    stroke="rgba(5, 18, 31, 0.85)"
                    strokeWidth="0.4"
                    paintOrder="stroke"
                  >
                    起点
                  </text>
                ) : null}
              </g>
            ))}
          </>
        ) : null}

        {activeDrones.map((drone) => {
          const style = droneStatusStyle(drone.status)
          const markerKey = `${drone.id}-${drone.position.x.toFixed(4)}-${drone.position.y.toFixed(4)}`

          return (
            <g key={markerKey} filter="url(#drone-glow)">
              <circle
                cx={drone.position.x}
                cy={drone.position.y}
                r="2.8"
                fill={style.fill}
                fillOpacity="0.28"
                stroke={style.stroke}
                strokeWidth="0.7"
              />
              <circle
                cx={drone.position.x}
                cy={drone.position.y}
                r="1.5"
                fill={style.fill}
                stroke="#eff9ff"
                strokeWidth="0.4"
              />
              <text
                x={drone.position.x}
                y={drone.position.y - 3.4}
                textAnchor="middle"
                fontSize="3.2"
                fill="#eff9ff"
                stroke="rgba(5, 18, 31, 0.88)"
                strokeWidth="0.45"
                paintOrder="stroke"
              >
                无人机
              </text>
            </g>
          )
        })}

        <g>
          <circle cx={mapCenter[1]} cy={mapCenter[0]} r="1.4" fill="#22d3ee" stroke="#eff9ff" strokeWidth="0.4" />
          <circle cx={mapCenter[1]} cy={mapCenter[0]} r="2.8" fill="none" stroke="rgba(34, 211, 238, 0.34)" strokeWidth="0.7" />
          <text
            x={mapCenter[1] + 2.2}
            y={mapCenter[0] - 1.6}
            fontSize="3"
            fill="#dff6ff"
            stroke="rgba(5, 18, 31, 0.84)"
            strokeWidth="0.4"
            paintOrder="stroke"
          >
            指挥点
          </text>
        </g>
      </svg>

      <div className="map-overlay map-mission">
        <div className="map-overlay-title">当前任务指令</div>
        <div className="map-mission-grid">
          <div className="map-mission-item">
            <span>地块</span>
            <strong>{getFieldName(field)}</strong>
          </div>
          <div className="map-mission-item">
            <span>农药</span>
            <strong>{String(medication['农药名称'] ?? '暂无')}</strong>
          </div>
          <div className="map-mission-item">
            <span>作物</span>
            <strong>{getFieldCrop(field)}</strong>
          </div>
          <div className="map-mission-item">
            <span>航点</span>
            <strong>{routePoints.length}</strong>
          </div>
          <div className="map-mission-item">
            <span>航线源</span>
            <strong>{routeSource}</strong>
          </div>
          <div className="map-mission-item">
            <span>覆盖顶点</span>
            <strong>{coveragePoints.length}</strong>
          </div>
        </div>
      </div>

      <div className="map-overlay map-legend">
        <div className="map-overlay-title">图例</div>
        <div className="map-legend-list">
          <div className="map-legend-item">
            <span className="map-legend-swatch is-working" />
            <span>作业中地块</span>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-swatch is-waiting" />
            <span>待作业地块</span>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-swatch is-finished" />
            <span>已完成地块</span>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-dot is-drone-active" />
            <span>执行中无人机</span>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-line is-drone-planned" />
            <span>预设航线</span>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-dot is-drone-returning" />
            <span>返航中无人机</span>
          </div>
        </div>
      </div>

      <div className="map-overlay map-summary">
        <div className="map-summary-metric">
          <span className="map-summary-label">展示地块</span>
          <strong>{displayFieldPlots.length}</strong>
        </div>
        <div className="map-summary-metric">
          <span className="map-summary-label">仿真面积</span>
          <strong>{totalAreaMu} 亩</strong>
        </div>
        <div className="map-summary-metric">
          <span className="map-summary-label">活跃无人机</span>
          <strong>{activeDroneCount} 架</strong>
        </div>
        <div className="map-summary-metric">
          <span className="map-summary-label">数据链路</span>
          <strong>{transport === 'websocket' ? 'WebSocket' : 'Polling'}</strong>
        </div>
      </div>
    </div>
  )
}
