import { useEffect, useMemo, useRef, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import type { SimDroneState } from '../../types/simMap'
import type { DensityGridCell, WorkflowDetectionEntry } from '../../types/workflow'
import { mapCenter, type FieldPlot, type FieldStatus } from './mapData'
import { computeCommandPoint } from './commandPoint'

const C = {
  fieldActive: '#089cc5',
  fieldCompleted: '#16875a',
  fieldIdle: '#6f63d9',
  droneActive: '#089cc5',
  droneReturningStroke: '#6f63d9',
  droneReturningFill: '#8a7cf0',
  trajectoryStart: '#089cc5',
  trajectoryMid: '#6f63d9',
  trajectoryEnd: '#d96d2d',
  mapBg: '#f6f9ff',
  text: '#102033',
  textStroke: 'rgba(255, 255, 255, 0.85)',
  textStrokeLight: 'rgba(255, 255, 255, 0.88)',
  textStrokeLight2: 'rgba(255, 255, 255, 0.84)',
  coverage: '#d96d2d',
  plannedRoute: '#0f766e',
  waypointStart: '#42d392',
  detection: '#c73758',
  commandPoint: '#d78d1f',
  heatmapHigh: 'rgba(235, 40, 35, 0.92)',
  heatmapMedium: 'rgba(235, 165, 15, 0.82)',
  heatmapLow: 'rgba(35, 190, 95, 0.65)',
  heatmapMinimal: 'rgba(35, 190, 95, 0.40)',
  gridStroke: 'rgba(32, 91, 154, 0.10)',
  overlayFill: 'rgba(255, 255, 255, 0.46)',
  overlayStroke: 'rgba(32, 91, 154, 0.12)',
  routeOutline: 'rgba(255, 255, 255, 0.92)',
  waypointStroke: 'rgba(255, 255, 255, 0.72)',
  sprayingBg: 'rgba(22, 135, 90, 0.08)',
  sprayingBorder: 'rgba(22, 135, 90, 0.2)',
  waitingBg: 'rgba(215, 141, 31, 0.08)',
  waitingBorder: 'rgba(215, 141, 31, 0.2)',
  commandRing: 'rgba(215, 141, 31, 0.25)',
}

type FieldMapProps = {
  droneStatus?: string
  detections?: WorkflowDetectionEntry[]
  spraySchedule?: number[] | null
  densityGrid?: DensityGridCell[] | null
  instructionRoute?: [number, number][] | null
  instructionCoverage?: [number, number][] | null
}

function fieldStatusStyle(status: FieldStatus) {
  if (status === '作业中') {
    return { stroke: C.fieldActive, fill: C.fieldActive, fillOpacity: 0.12 }
  }

  if (status === '已完成') {
    return { stroke: C.fieldCompleted, fill: C.fieldCompleted, fillOpacity: 0.12 }
  }

  return { stroke: C.fieldIdle, fill: C.fieldIdle, fillOpacity: 0.12 }
}

function droneStatusStyle(status: SimDroneState['status']) {
  if (status === '作业中') {
    return { stroke: C.droneActive, fill: C.droneActive }
  }

  if (status === '返航') {
    return { stroke: C.droneReturningStroke, fill: C.droneReturningFill }
  }

  return { stroke: C.droneReturningStroke, fill: C.droneReturningFill }
}

function buildDemoFallbackField(): FieldPlot {
  const boundary: LatLngTuple[] = [
    [22, 34],
    [22, 126],
    [78, 126],
    [78, 34],
  ]

  return {
    id: 'demo-fallback-field',
    name: '默认植保作业田',
    crop: '小麦',
    areaMu: 56,
    status: '作业中',
    boundary,
    center: computeCenter(boundary),
  }
}

function buildDemoFallbackRoute(): LatLngTuple[] {
  return [
    [28, 40],
    [28, 120],
    [38, 120],
    [38, 40],
    [48, 40],
    [48, 120],
    [58, 120],
    [58, 40],
    [68, 40],
    [68, 120],
  ]
}

function buildCoverageRouteFromBoundary(boundary: LatLngTuple[]): LatLngTuple[] {
  if (boundary.length < 3) {
    return buildDemoFallbackRoute()
  }

  const latitudes = boundary.map(([lat]) => lat)
  const longitudes = boundary.map(([, lng]) => lng)
  const minLat = Math.min(...latitudes)
  const maxLat = Math.max(...latitudes)
  const minLng = Math.min(...longitudes)
  const maxLng = Math.max(...longitudes)
  const latSpan = maxLat - minLat
  const lngSpan = maxLng - minLng

  if (!Number.isFinite(latSpan) || !Number.isFinite(lngSpan) || latSpan <= 0 || lngSpan <= 0) {
    return buildDemoFallbackRoute()
  }

  const top = minLat + latSpan * 0.14
  const bottom = maxLat - latSpan * 0.14
  const left = minLng + lngSpan * 0.12
  const right = maxLng - lngSpan * 0.12
  const laneCount = 6
  const route: LatLngTuple[] = []

  for (let index = 0; index < laneCount; index += 1) {
    const lat = top + ((bottom - top) * index) / Math.max(1, laneCount - 1)
    const lane: LatLngTuple[] = [
      [lat, left],
      [lat, right],
    ]
    route.push(...(index % 2 === 0 ? lane : lane.reverse()))
  }

  return route
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

const DRONE_STRAIGHT_SPEED = 0.004
const DRONE_TURN_SPEED = 0.016
const DRONE_TURN_ZONE = 0.015

type GpsBounds = { minLon: number; maxLon: number; minLat: number; maxLat: number }

function computeGpsBounds(coords: [number, number][]): GpsBounds {
  const lons = coords.map((c) => c[0])
  const lats = coords.map((c) => c[1])
  return { minLon: Math.min(...lons), maxLon: Math.max(...lons), minLat: Math.min(...lats), maxLat: Math.max(...lats) }
}

function computeSvgBounds(boundary: LatLngTuple[]): GpsBounds {
  const lngs = boundary.map((p) => p[1])
  const lats = boundary.map((p) => p[0])
  return { minLon: Math.min(...lngs), maxLon: Math.max(...lngs), minLat: Math.min(...lats), maxLat: Math.max(...lats) }
}

function projectGpsToSvg(
  gpsPoint: [number, number],
  gpsBounds: GpsBounds,
  svgBounds: GpsBounds,
): LatLngTuple {
  const lonSpan = gpsBounds.maxLon - gpsBounds.minLon || 1
  const latSpan = gpsBounds.maxLat - gpsBounds.minLat || 1
  const nLng = (gpsPoint[0] - gpsBounds.minLon) / lonSpan
  const nLat = (gpsPoint[1] - gpsBounds.minLat) / latSpan
  const svgLat = svgBounds.minLat + nLat * (svgBounds.maxLat - svgBounds.minLat)
  const svgLng = svgBounds.minLon + nLng * (svgBounds.maxLon - svgBounds.minLon)
  return [svgLat, svgLng]
}

function sprayRateColor(normalized: number): string {
  if (normalized >= 0.7) return 'rgba(192, 96, 90, 0.9)'
  if (normalized >= 0.4) return 'rgba(196, 138, 42, 0.85)'
  return 'rgba(90, 138, 106, 0.75)'
}

function resolveStaticRoutePosition(route: LatLngTuple[]) {
  if (route.length === 0) {
    return mapCenter
  }
  return route[0]
}

function useAnimatedDrones(
  baseDrones: SimDroneState[],
  route: LatLngTuple[],
  animationKey: string,
  shouldAnimate: boolean,
): SimDroneState[] {
  const [animated, setAnimated] = useState(baseDrones)
  const progressRef = useRef(0)
  const rafRef = useRef<number | null>(null)
  const baseDronesRef = useRef(baseDrones)
  const routeRef = useRef(route)

  useEffect(() => {
    baseDronesRef.current = baseDrones
    routeRef.current = route
  }, [baseDrones, route])

  useEffect(() => {
    if (!shouldAnimate) {
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

      const currentRoute = routeRef.current
      const segCount = Math.max(1, currentRoute.length - 1)
      const currentSeg = progressRef.current * segCount
      const nearestWaypointDist = Math.min(
        Math.abs(currentSeg - Math.round(currentSeg)),
        Math.abs(currentSeg),
        Math.abs(currentSeg - segCount),
      )
      const nearTurn = nearestWaypointDist < DRONE_TURN_ZONE * segCount
      const speed = nearTurn ? DRONE_TURN_SPEED : DRONE_STRAIGHT_SPEED

      progressRef.current += speed * dt
      if (progressRef.current > 1) {
        progressRef.current -= 1
      }

      if (currentRoute.length < 2) {
        rafRef.current = requestAnimationFrame(tick)
        return
      }

      const p = Math.max(0, Math.min(0.999, Number.isFinite(progressRef.current) ? progressRef.current : 0))
      const scaled = p * (currentRoute.length - 1)
      const lo = Math.floor(scaled)
      const hi = Math.min(currentRoute.length - 1, lo + 1)
      const t = scaled - lo
      const start = currentRoute[lo]
      const end = currentRoute[hi]
      if (!start || !end) {
        progressRef.current = 0
        rafRef.current = requestAnimationFrame(tick)
        return
      }
      const [lat0, lng0] = start
      const [lat1, lng1] = end
      const lat = lat0 + (lat1 - lat0) * t
      const lng = lng0 + (lng1 - lng0) * t

      const drones = baseDronesRef.current
      setAnimated(
        drones.map((d) => ({
          ...d,
          position: { x: lng, y: lat },
          status: d.status,
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
  }, [route.length, baseDrones.length, animationKey, shouldAnimate])

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

export default function FieldMap({ droneStatus, detections = [], spraySchedule, densityGrid, instructionRoute, instructionCoverage }: FieldMapProps) {
  const fallbackFieldPlot = buildDemoFallbackField()
  const primaryFieldPlot = fallbackFieldPlot
  const displayFieldPlots = [primaryFieldPlot]
  const commandPoint = computeCommandPoint(primaryFieldPlot.boundary, mapCenter)
  const fallbackRoutePoints = buildDemoFallbackRoute()

  // Project backend GPS route into SVG space when available
  const routePoints = useMemo(() => {
    if (instructionRoute && instructionRoute.length >= 2 && instructionCoverage && instructionCoverage.length >= 3) {
      const gpsBounds = computeGpsBounds(instructionCoverage)
      const svgBounds = computeSvgBounds(primaryFieldPlot.boundary)
      return instructionRoute.map((pt) => projectGpsToSvg(pt, gpsBounds, svgBounds))
    }
    return buildCoverageRouteFromBoundary(primaryFieldPlot.boundary)
  }, [instructionRoute, instructionCoverage, primaryFieldPlot.boundary])

  const finalRoutePoints = routePoints.length >= 2 ? routePoints : fallbackRoutePoints
  const routeHoldPosition = resolveStaticRoutePosition(finalRoutePoints)
  const coveragePoints: LatLngTuple[] = []

  const isSpraying = droneStatus === 'spraying' || droneStatus === '作业中' || droneStatus === 'patrolling'
  const droneStatusForStyle = isSpraying ? '作业中' : '待命'

  const baseDrones = [{
    id: 'demo-fallback-drone',
    name: '植保无人机 01',
    status: droneStatusForStyle as SimDroneState['status'],
    battery: 86,
    position: { x: routeHoldPosition[1], y: routeHoldPosition[0] },
    route: finalRoutePoints.map(([lat, lng]) => ({ x: lng, y: lat })),
  }]

  const activeDrones = useAnimatedDrones(
    baseDrones,
    finalRoutePoints,
    `drone-${droneStatus ?? 'idle'}`,
    isSpraying,
  )
  const displayedSprayTrailPoints = finalRoutePoints
  const isDemoFallback = true
  const detectionMarkers = useMemo(
    () => buildDetectionMarkerData(detections, primaryFieldPlot.center),
    [detections, primaryFieldPlot.center],
  )

  // Backend density grid projected from GPS to SVG
  const projectedDensityGrid = useMemo(() => {
    if (!densityGrid || densityGrid.length === 0 || !instructionCoverage || instructionCoverage.length < 3) return null
    const gpsBounds = computeGpsBounds(instructionCoverage)
    const svgBounds = computeSvgBounds(primaryFieldPlot.boundary)
    return densityGrid
      .filter((cell) => cell.density > 0.05)
      .map((cell) => {
        const [svgLat1, svgLng1] = projectGpsToSvg(cell.bounds[0], gpsBounds, svgBounds)
        const [svgLat2, svgLng2] = projectGpsToSvg(cell.bounds[1], gpsBounds, svgBounds)
        return {
          x: Math.min(svgLng1, svgLng2),
          y: Math.min(svgLat1, svgLat2),
          w: Math.abs(svgLng2 - svgLng1),
          h: Math.abs(svgLat2 - svgLat1),
          density: cell.density,
        }
      })
  }, [densityGrid, instructionCoverage, primaryFieldPlot.boundary])

  // Fallback: local density grid from detection positions
  const localDensityGrid = useMemo(() => {
    if (detectionMarkers.length === 0) return null
    const boundary = primaryFieldPlot.boundary
    const lats = boundary.map((p: LatLngTuple) => p[0])
    const lngs = boundary.map((p: LatLngTuple) => p[1])
    const minLat = Math.min(...lats), maxLat = Math.max(...lats)
    const minLng = Math.min(...lngs), maxLng = Math.max(...lngs)
    const rows = 6, cols = 8
    const grid: number[][] = Array.from({ length: rows }, () => Array(cols).fill(0))
    let maxVal = 0
    for (const m of detectionMarkers) {
      const lat = m.point[0], lng = m.point[1]
      const r = Math.min(Math.floor(((lat - minLat) / (maxLat - minLat)) * rows), rows - 1)
      const c = Math.min(Math.floor(((lng - minLng) / (maxLng - minLng)) * cols), cols - 1)
      if (r >= 0 && c >= 0) {
        grid[r][c] += m.confidence
        maxVal = Math.max(maxVal, grid[r][c])
      }
    }
    if (maxVal <= 0) return null
    const cellW = (maxLng - minLng) / cols
    const cellH = (maxLat - minLat) / rows
    const cells = []
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const d = grid[r][c] / maxVal
        if (d > 0.05) {
          cells.push({ x: minLng + c * cellW, y: minLat + r * cellH, w: cellW, h: cellH, density: d })
        }
      }
    }
    return cells
  }, [detectionMarkers, primaryFieldPlot.boundary])

  const effectiveDensityGrid = projectedDensityGrid ?? localDensityGrid
  const telemetry = {
    altitude: 5,
    speed: 4.5,
    battery: activeDrones[0]?.battery ?? null,
  }
  const [showHeatmap, setShowHeatmap] = useState(true)
  const viewBox = '0 0 160 100'

  const densityColor = (d: number) => {
    if (d >= 0.8) return C.heatmapHigh
    if (d >= 0.6) return C.heatmapMedium
    if (d >= 0.3) return C.heatmapLow
    return C.heatmapMinimal
  }

  return (
    <div className="field-map-shell">
      <div className="field-map-canvas">
        <svg
          className="field-map"
          viewBox={viewBox}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="当前作业地图"
        >
        <defs>
          <pattern id="map-grid" width="8" height="8" patternUnits="userSpaceOnUse">
            <path d="M 8 0 L 0 0 0 8" fill="none" stroke={C.gridStroke} strokeWidth="0.35" />
          </pattern>
          <filter id="drone-glow">
            <feGaussianBlur stdDeviation="1.2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="trajectory-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={C.trajectoryStart} />
            <stop offset="50%" stopColor={C.trajectoryMid} />
            <stop offset="100%" stopColor={C.trajectoryEnd} />
          </linearGradient>
        </defs>

        <rect x="0" y="0" width="160" height="100" fill={C.mapBg} />
        <rect x="0" y="0" width="160" height="100" fill="url(#map-grid)" opacity="0.7" />
        <rect
          x="0"
          y="0"
          width="160"
          height="100"
          fill={C.overlayFill}
          stroke={C.overlayStroke}
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
                fill={C.text}
                stroke={C.textStroke}
                strokeWidth="0.5"
                paintOrder="stroke"
              >
                {fieldItem.name}
              </text>
            </g>
          )
        })}

        {showHeatmap && effectiveDensityGrid && effectiveDensityGrid.length > 0 && (
          <g opacity="0.92">
            {effectiveDensityGrid.map((cell, i) => (
              <rect
                key={`density-${i}`}
                x={cell.x}
                y={cell.y}
                width={cell.w}
                height={cell.h}
                fill={densityColor(cell.density)}
                rx="0.5"
              />
            ))}
          </g>
        )}

        {coveragePoints.length >= 3 ? (
          <polygon
            points={toSvgPoints(coveragePoints)}
            fill={C.coverage}
            fillOpacity="0.08"
            stroke={C.coverage}
            strokeWidth="0.8"
            strokeDasharray="2 2"
          />
        ) : null}

        {routePoints.length >= 2 ? (
          <>
            <polyline
              points={toSvgPoints(routePoints)}
              fill="none"
              stroke={C.routeOutline}
              strokeWidth="3.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {spraySchedule && spraySchedule.length > 0 ? (
              // Variable-rate: per-lane colored segments
              spraySchedule.map((rate, laneIdx) => {
                const startPt = routePoints[laneIdx * 2]
                const endPt = routePoints[laneIdx * 2 + 1]
                if (!startPt || !endPt) return null
                const maxRate = Math.max(...spraySchedule)
                const minRate = Math.min(...spraySchedule)
                const normalized = maxRate > minRate ? (rate - minRate) / (maxRate - minRate) : 0.5
                const color = sprayRateColor(normalized)
                const width = 1.4 + normalized * 1.6
                return (
                  <line
                    key={`spray-lane-${laneIdx}`}
                    x1={startPt[1]} y1={startPt[0]}
                    x2={endPt[1]} y2={endPt[0]}
                    stroke={color}
                    strokeWidth={width}
                    strokeLinecap="round"
                  />
                )
              })
            ) : (
              // Uniform rate: standard dashed route
              <polyline
                points={toSvgPoints(routePoints)}
                fill="none"
                stroke={C.plannedRoute}
                strokeWidth="1.8"
                strokeDasharray="3 1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            )}

            {routePoints.map((point, index) => (
              <g key={`route-waypoint-${index}-${point[0].toFixed(3)}-${point[1].toFixed(3)}`}>
                <circle
                  cx={point[1]}
                  cy={point[0]}
                  r={index === 0 ? 2 : 1.35}
                  fill={index === 0 ? '#42d392' : '#16875a'}
                  stroke={C.waypointStroke}
                  strokeWidth="0.7"
                />
                {index === 0 ? (
                  <text
                    x={point[1] + 1.8}
                    y={point[0] - 1.2}
                    fontSize="3"
                    fill={C.text}
                    stroke={C.textStroke}
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

        {displayedSprayTrailPoints.length >= 2 ? (
          <path
            d={toPathD(displayedSprayTrailPoints)}
            fill="none"
            stroke="url(#trajectory-gradient)"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}

        {activeDrones.map((drone) => {
          const style = droneStatusStyle(drone.status)
          const markerKey = `${drone.id}-${drone.position.x.toFixed(4)}-${drone.position.y.toFixed(4)}`

          return (
            <g
              key={markerKey}
              data-testid="drone-marker"
              filter="url(#drone-glow)"
              aria-label="植保无人机"
              transform={`translate(${drone.position.x} ${drone.position.y})`}
            >
              <circle r="9.8" fill={style.fill} fillOpacity="0.10" stroke={style.stroke} strokeOpacity="0.58" strokeWidth="0.65">
                <animate attributeName="r" values="7.4;10.2;7.4" dur="2.2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.95;0.36;0.95" dur="2.2s" repeatCount="indefinite" />
              </circle>
              <circle r="5.7" fill="rgba(255,255,255,0.10)" stroke={style.stroke} strokeWidth="0.55" strokeDasharray="1.4 1.1" />

              {isSpraying ? (
                <g opacity="0.86">
                  <path d="M -5.8 4.4 Q 0 10.8 5.8 4.4 L 3.1 11.4 L -3.1 11.4 Z" fill={C.waypointStart} fillOpacity="0.18" stroke={C.waypointStart} strokeWidth="0.45" />
                  <circle cx="-3.2" cy="7.8" r="0.52" fill={C.waypointStart} fillOpacity="0.82" />
                  <circle cx="0" cy="9.1" r="0.42" fill={C.waypointStart} fillOpacity="0.72" />
                  <circle cx="3.2" cy="7.8" r="0.52" fill={C.waypointStart} fillOpacity="0.82" />
                </g>
              ) : null}

              <g stroke={style.stroke} strokeWidth="0.9" strokeLinecap="round">
                <line x1="-5.8" y1="-3.8" x2="5.8" y2="3.8" />
                <line x1="5.8" y1="-3.8" x2="-5.8" y2="3.8" />
                <line x1="-4.8" y1="0" x2="4.8" y2="0" />
              </g>

              {[
                [-6.5, -4.4, -18],
                [6.5, -4.4, 18],
                [-6.5, 4.4, 18],
                [6.5, 4.4, -18],
              ].map(([cx, cy, rotate], index) => (
                <g key={`rotor-${index}`} transform={`translate(${cx} ${cy}) rotate(${rotate})`}>
                  <ellipse rx="2.65" ry="0.9" fill={style.fill} fillOpacity="0.24" stroke={style.stroke} strokeWidth="0.48">
                    <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="0.55s" repeatCount="indefinite" />
                  </ellipse>
                  <circle r="0.7" fill={style.fill} stroke={C.textStrokeLight} strokeWidth="0.25" />
                </g>
              ))}

              <path d="M -2.2 -1.45 L 0 -3.7 L 2.2 -1.45 L 2.2 1.55 Q 0 2.5 -2.2 1.55 Z" fill={style.fill} stroke={C.textStrokeLight} strokeWidth="0.42" />
              <circle cx="0" cy="0.15" r="0.72" fill="#eaf6ff" fillOpacity="0.88" />
              <path d="M -1.8 2.3 L -3.2 4.1 M 1.8 2.3 L 3.2 4.1" stroke={style.stroke} strokeWidth="0.62" strokeLinecap="round" />
            </g>
          )
        })}

        {detectionMarkers.map((marker, index) => (
          <g key={`det-${index}-${marker.pest}`}>
            <circle
              cx={marker.point[1]}
              cy={marker.point[0]}
              r="1.8"
              fill={C.detection}
              fillOpacity="0.15"
              stroke={C.detection}
              strokeWidth="0.5"
            />
            <circle
              cx={marker.point[1]}
              cy={marker.point[0]}
              r="0.8"
              fill={C.detection}
            />
          </g>
        ))}

        <g>
          <circle cx={commandPoint[1]} cy={commandPoint[0]} r="1.4" fill={C.commandPoint} stroke={C.text} strokeWidth="0.4" />
          <circle cx={commandPoint[1]} cy={commandPoint[0]} r="2.8" fill="none" stroke={C.commandRing} strokeWidth="0.7" />
          <text
            x={commandPoint[1] + 2.2}
            y={commandPoint[0] - 1.6}
            fontSize="3"
            fill={C.text}
            stroke={C.textStrokeLight2}
            strokeWidth="0.4"
            paintOrder="stroke"
          >
            指挥点
          </text>
        </g>
      </svg>

      {isDemoFallback && (
        <div
          className="map-overlay"
          style={{
            top: 18,
            right: 18,
            padding: '6px 12px',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: isSpraying ? 'var(--accent-green)' : 'var(--accent-amber)',
            background: isSpraying ? C.sprayingBg : C.waitingBg,
            borderColor: isSpraying ? C.sprayingBorder : C.waitingBorder,
          }}
        >
          {isSpraying ? '喷洒中' : '等待任务'}
        </div>
      )}
      </div>

      <aside className="field-map-sidecar" aria-label="地图状态信息">
        <section className="map-info-card map-legend" aria-label="地图图例">
          <div className="map-info-card-title">地图图例</div>
          <div className="map-legend-list">
            <div className="map-legend-item">
              <span className="map-legend-swatch is-working" />
              <span>作业中地块</span>
            </div>
            <div className="map-legend-item">
              <span className="map-legend-dot is-drone-active" />
              <span>无人机位置</span>
            </div>
            <div className="map-legend-item">
              <span className="map-legend-line is-drone-planned" />
              <span>规划航线</span>
            </div>
            {detectionMarkers.length > 0 && (
              <div className="map-legend-item">
                <span className="map-legend-dot is-detection" />
                <span>检测点 ({detectionMarkers.length})</span>
              </div>
            )}
            {effectiveDensityGrid && effectiveDensityGrid.length > 0 && (
              <div className="map-legend-item is-interactive" onClick={() => setShowHeatmap(!showHeatmap)}>
                <span className={`map-legend-swatch ${showHeatmap ? 'is-active' : 'is-inactive'}`} />
                <span>{showHeatmap ? '隐藏密度热力图' : '显示密度热力图'}</span>
              </div>
            )}
            {spraySchedule && spraySchedule.length > 0 && (
              <>
                <div className="map-legend-item">
                  <span className="map-legend-swatch" style={{ background: 'rgba(192, 96, 90, 0.9)' }} />
                  <span>高密度区域 (高喷洒量)</span>
                </div>
                <div className="map-legend-item">
                  <span className="map-legend-swatch" style={{ background: 'rgba(196, 138, 42, 0.85)' }} />
                  <span>中密度区域 (标准喷洒)</span>
                </div>
                <div className="map-legend-item">
                  <span className="map-legend-swatch" style={{ background: 'rgba(90, 138, 106, 0.75)' }} />
                  <span>低密度区域 (低喷洒量)</span>
                </div>
              </>
            )}
          </div>
        </section>

        {(telemetry.altitude !== null || telemetry.speed !== null || telemetry.battery !== null) && (
          <section className="map-info-card map-telemetry" aria-label="飞行参数">
            <div className="map-info-card-title">飞行参数</div>
            <div className="map-telemetry-grid">
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
          </section>
        )}

        {effectiveDensityGrid && effectiveDensityGrid.length > 0 && (
          <section className="map-info-card map-density-stats" aria-label="密度统计">
            <div className="map-info-card-title">密度统计</div>
            <div className="map-telemetry-grid">
              <div className="map-telemetry-item">
                <span>网格数</span>
                <strong>{effectiveDensityGrid.length}</strong>
              </div>
              <div className="map-telemetry-item">
                <span>最高密度</span>
                <strong>{Math.max(...effectiveDensityGrid.map((c) => c.density)).toFixed(2)}</strong>
              </div>
              {spraySchedule && spraySchedule.length > 0 && (
                <div className="map-telemetry-item">
                  <span>喷洒速率</span>
                  <strong>{Math.min(...spraySchedule).toFixed(1)}–{Math.max(...spraySchedule).toFixed(1)} L/min</strong>
                </div>
              )}
            </div>
          </section>
        )}

      </aside>
    </div>
  )
}
