import { useEffect, useMemo, useRef, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import type { GPSPosition, SimDroneState, SimMapStateResponse, WsEnhancedState } from '../../types/simMap'
import type { WorkflowDetectionEntry, WorkflowTaskState } from '../../types/workflow'
import { mapCenter, type FieldPlot, type FieldStatus } from './mapData'
import { computeCommandPoint } from './commandPoint'
import StatusPanel from './StatusPanel'

type FieldMapProps = {
  transport?: 'websocket' | 'polling'
  latestTask?: WorkflowTaskState | null
  simMapState?: SimMapStateResponse | null
  enhancedState?: WsEnhancedState | null
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

function gpsPositionsToPointPairs(points: GPSPosition[] | null | undefined): PointPair[] {
  if (!Array.isArray(points)) {
    return []
  }

  return points
    .map((point) => {
      const latitude = toNumber(point.latitude)
      const longitude = toNumber(point.longitude)
      if (latitude === null || longitude === null) {
        return null
      }
      return [longitude, latitude] as PointPair
    })
    .filter((item): item is PointPair => item !== null)
}

function gpsPositionToPointPair(point: GPSPosition | null | undefined): PointPair[] {
  if (!point) {
    return []
  }
  return gpsPositionsToPointPairs([point])
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
  enhancedState: WsEnhancedState | null | undefined,
): SimDroneState[] {
  if (!latestTask && !enhancedState) {
    return []
  }

  const drone = asRecord(latestTask?.drone)
  const waypointIndexValue = Number(drone.current_waypoint_index)
  const progressValue = Number(enhancedState?.mission.progress ?? drone.progress)
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
  const taskId = String(enhancedState?.drone.id ?? drone.task_id ?? latestTask?.request_id ?? 'px4-primary')

  return [
    {
      id: taskId,
      name: String(enhancedState?.drone.name ?? drone.task_id ?? 'PX4 SITL 飞行器'),
      status: mapDroneStatus(String(enhancedState?.drone.status ?? drone.status ?? latestTask?.status ?? '作业中')),
      battery: Math.round(enhancedState?.drone.battery.remaining ?? 100),
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

function toPathD(points: LatLngTuple[]) {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point[1]} ${point[0]}`)
    .join(' ')
}

const DRONE_SPEED = 0.012

function useAnimatedDrones(
  baseDrones: SimDroneState[],
  route: LatLngTuple[],
  taskStatus: string,
  skipAnimation: boolean,
): SimDroneState[] {
  const [animated, setAnimated] = useState(baseDrones)
  const progressRef = useRef(0)
  const rafRef = useRef<number | null>(null)
  const baseDronesRef = useRef(baseDrones)
  const routeRef = useRef(route)
  const taskStatusRef = useRef(taskStatus)

  useEffect(() => {
    baseDronesRef.current = baseDrones
    routeRef.current = route
    taskStatusRef.current = taskStatus
  }, [baseDrones, route, taskStatus])

  useEffect(() => {
    if (skipAnimation) {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      setAnimated(baseDrones)
      return
    }

    if (route.length < 2 || baseDrones.length === 0) {
      setAnimated(baseDrones)
      return
    }

    const basePos = baseDrones[0].position
    let closest = 0
    let minDist = Infinity
    for (let i = 0; i < route.length; i++) {
      const dy = route[i][0] - basePos.y
      const dx = route[i][1] - basePos.x
      const d = dx * dx + dy * dy
      if (d < minDist) {
        minDist = d
        closest = i
      }
    }
    progressRef.current = closest / Math.max(1, route.length - 1)

    let lastTime = performance.now()

    const tick = (now: number) => {
      const dt = Math.min((now - lastTime) / 1000, 0.1)
      lastTime = now

      progressRef.current += DRONE_SPEED * dt
      if (progressRef.current > 1) {
        progressRef.current -= 1
      }

      const p = progressRef.current
      const scaled = p * (routeRef.current.length - 1)
      const lo = Math.floor(scaled)
      const hi = Math.min(routeRef.current.length - 1, lo + 1)
      const t = scaled - lo
      const [lat0, lng0] = routeRef.current[lo]
      const [lat1, lng1] = routeRef.current[hi]
      const lat = lat0 + (lat1 - lat0) * t
      const lng = lng0 + (lng1 - lng0) * t

      const drones = baseDronesRef.current
      setAnimated(
        drones.map((d) => ({
          ...d,
          position: { x: lng, y: lat },
          status: taskStatusRef.current === 'completed' ? '作业中' : d.status,
        })),
      )

      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.length, baseDrones.length, taskStatus, skipAnimation])

  return animated
}

function buildDetectionMarkerData(
  detections: WorkflowDetectionEntry[],
  center: LatLngTuple,
): { point: LatLngTuple; pest: string; confidence: number }[] {
  if (detections.length === 0) return []

  const [centerLat, centerLng] = center
  const count = Math.min(detections.length, 12)
  const goldenAngle = Math.PI * (3 - Math.sqrt(5)) // ~137.5°, spreads points evenly
  const baseRadius = 8

  return detections.slice(0, count).map((det, i) => {
    const angle = goldenAngle * i
    const r = baseRadius * Math.sqrt((i + 0.5) / count) // spiral distribution
    const jitterLat = Math.cos(angle) * r
    const jitterLng = Math.sin(angle) * r
    return {
      point: [centerLat + jitterLat, centerLng + jitterLng] as LatLngTuple,
      pest: String(det.pest_type ?? '未知'),
      confidence: det.confidence ?? 0,
    }
  })
}

export default function FieldMap({ transport: _transport, latestTask, simMapState, enhancedState }: FieldMapProps) {
  const instruction = asRecord(latestTask?.drone?.instruction)
  const taskField = asRecord(latestTask?.field)
  const field = enhancedState?.field
    ? {
      ...taskField,
      field_id: enhancedState.field.id,
      field_name: enhancedState.field.name,
    }
    : taskField

  const enhancedFieldBoundary = gpsPositionsToPointPairs(enhancedState?.field?.boundary)
  const rawFieldGeofence = enhancedFieldBoundary.length >= 3 ? enhancedFieldBoundary : toPointPairs(field.geofence)
  const rawPresetRoutePoints = toPointPairs(field.explicit_route)
  const rawInstructionRoutePoints = toPointPairs(instruction['飞行路径'])
  const enhancedRoutePoints = gpsPositionsToPointPairs(enhancedState?.mission.planned_route)
  const rawRoutePoints = enhancedRoutePoints.length >= 2
    ? enhancedRoutePoints
    : rawInstructionRoutePoints.length >= 2
      ? rawInstructionRoutePoints
      : rawPresetRoutePoints
  const rawCoveragePoints = toPointPairs(asRecord(instruction['覆盖区域']).coordinates)
  const rawTrajectoryPoints = gpsPositionsToPointPairs(enhancedState?.trajectory.recent_points)
  const rawDronePosition = gpsPositionToPointPair(enhancedState?.drone.position)
  const projectPairs = buildCoordinateProjector([
    rawFieldGeofence,
    rawPresetRoutePoints,
    rawInstructionRoutePoints,
    rawRoutePoints,
    rawCoveragePoints,
    rawTrajectoryPoints,
    rawDronePosition,
  ])

  const projectedGeofence = projectPairs(rawFieldGeofence, 3)
  const taskRoutePoints = projectPairs(rawRoutePoints, 1)
  const coveragePoints = projectPairs(rawCoveragePoints, 3)
  const projectedTrajectoryPoints = projectPairs(rawTrajectoryPoints, 2)
  const projectedDronePosition = projectPairs(rawDronePosition, 1)[0] ?? null
  const primaryFieldPlot = buildPrimaryFieldPlot(field, latestTask, projectedGeofence, coveragePoints)
  const displayFieldPlots = primaryFieldPlot ? [primaryFieldPlot] : []
  const commandPoint = computeCommandPoint(primaryFieldPlot?.boundary ?? [], mapCenter)
  const simRoutePoints = buildSimRoutePoints(simMapState)
  const routePoints = taskRoutePoints.length >= 2 ? taskRoutePoints : simRoutePoints

  // Detect PX4 real position from telemetry
  const droneData = asRecord(latestTask?.drone)
  const px4PositionRaw = asRecord(droneData.position)
  const hasPx4Lat = toNumber(px4PositionRaw.latitude) !== null
  const hasPx4Lng = toNumber(px4PositionRaw.longitude) !== null
  const px4Status = String(droneData.status ?? '').toLowerCase()
  const isPx4Flying = hasPx4Lat && hasPx4Lng
    && ['takeoff', 'spraying', 'enroute', 'returning'].includes(px4Status)

  // Build drones: use task-driven (PX4) when available, simMap as fallback when no task
  const baseDrones = latestTask
    ? buildTaskDrivenDrones(latestTask, routePoints, projectedDronePosition, enhancedState)
    : enhancedState
      ? buildTaskDrivenDrones(null, routePoints, projectedDronePosition, enhancedState)
    : (simMapState?.drones.length ? simMapState.drones : [])

  const taskStatus = String(latestTask?.status ?? '')
  // PX4 flying → use real position directly, skip animation
  // No PX4 → animate along route for demo effect
  const activeDrones = useAnimatedDrones(baseDrones, routePoints, taskStatus, isPx4Flying)
  const detections = latestTask?.detections ?? []
  const detectionMarkers = useMemo(
    () => buildDetectionMarkerData(detections, primaryFieldPlot?.center ?? mapCenter),
    [detections, primaryFieldPlot?.center],
  )
  const droneInstruction = asRecord(latestTask?.drone?.instruction)
  const telemetry = {
    altitude: toNumber(droneInstruction['高度']),
    speed: toNumber(droneInstruction['速度']),
    battery: simMapState?.drones[0]?.battery ?? null,
  }
  const viewBox = '0 0 160 100'

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
          <linearGradient id="trajectory-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#818cf8" />
            <stop offset="50%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>
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

        {projectedTrajectoryPoints.length >= 2 ? (
          <path
            d={toPathD(projectedTrajectoryPoints)}
            fill="none"
            stroke="url(#trajectory-gradient)"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
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

        {detectionMarkers.map((marker, index) => (
          <g key={`det-${index}-${marker.pest}`}>
            <circle
              cx={marker.point[1]}
              cy={marker.point[0]}
              r="1.8"
              fill="#ef4444"
              fillOpacity="0.2"
              stroke="#ef4444"
              strokeWidth="0.5"
            />
            <circle
              cx={marker.point[1]}
              cy={marker.point[0]}
              r="0.8"
              fill="#f87171"
            />
          </g>
        ))}

        <g>
          <circle cx={commandPoint[1]} cy={commandPoint[0]} r="1.4" fill="#22d3ee" stroke="#eff9ff" strokeWidth="0.4" />
          <circle cx={commandPoint[1]} cy={commandPoint[0]} r="2.8" fill="none" stroke="rgba(34, 211, 238, 0.34)" strokeWidth="0.7" />
          <text
            x={commandPoint[1] + 2.2}
            y={commandPoint[0] - 1.6}
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

      <div className="map-overlay map-legend">
        <div className="map-legend-list">
          <div className="map-legend-item">
            <span className="map-legend-swatch is-working" />
            <span>作业中</span>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-dot is-drone-active" />
            <span>无人机</span>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-line is-drone-planned" />
            <span>航线</span>
          </div>
          {detectionMarkers.length > 0 && (
            <div className="map-legend-item">
              <span className="map-legend-dot" style={{ background: '#f87171' }} />
              <span>检测点 ({detectionMarkers.length})</span>
            </div>
          )}
        </div>
      </div>

      {(telemetry.altitude !== null || telemetry.speed !== null || telemetry.battery !== null) && (
        <div className="map-overlay map-telemetry">
          {telemetry.altitude !== null && (
            <div className="map-telemetry-item">
              <span>高度</span>
              <strong>{telemetry.altitude} m</strong>
            </div>
          )}
          {telemetry.speed !== null && (
            <div className="map-telemetry-item">
              <span>速度</span>
              <strong>{telemetry.speed} m/s</strong>
            </div>
          )}
          {telemetry.battery !== null && (
            <div className="map-telemetry-item">
              <span>电量</span>
              <strong>{telemetry.battery}%</strong>
            </div>
          )}
        </div>
      )}

      {enhancedState ? <StatusPanel state={enhancedState} /> : null}
    </div>
  )
}
