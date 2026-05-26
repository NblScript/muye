import { useEffect, useMemo, useRef, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import type { SimDroneState } from '../../types/simMap'
import type { WorkflowDetectionEntry } from '../../types/workflow'
import { mapCenter, type FieldPlot, type FieldStatus } from './mapData'
import { computeCommandPoint } from './commandPoint'

type FieldMapProps = {
  droneStatus?: string
  detections?: WorkflowDetectionEntry[]
  spraySchedule?: number[]
}

function fieldStatusStyle(status: FieldStatus) {
  if (status === '作业中') {
    return {
      stroke: '#089cc5',
      fill: '#089cc5',
      fillOpacity: 0.12,
    }
  }

  if (status === '已完成') {
    return {
      stroke: '#16875a',
      fill: '#16875a',
      fillOpacity: 0.12,
    }
  }

  return {
    stroke: '#6f63d9',
    fill: '#6f63d9',
    fillOpacity: 0.12,
  }
}

function droneStatusStyle(status: SimDroneState['status']) {
  if (status === '作业中') {
    return {
      stroke: '#089cc5',
      fill: '#089cc5',
    }
  }

  if (status === '返航') {
    return {
      stroke: '#6f63d9',
      fill: '#8a7cf0',
    }
  }

  return {
    stroke: '#6f63d9',
    fill: '#8a7cf0',
  }
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

const DRONE_SPEED = 0.004
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

      progressRef.current += DRONE_SPEED * dt
      if (progressRef.current > 1) {
        progressRef.current -= 1
      }

      const currentRoute = routeRef.current
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

export default function FieldMap({ droneStatus, detections = [], spraySchedule: _spraySchedule }: FieldMapProps) {
  const fallbackFieldPlot = buildDemoFallbackField()
  const primaryFieldPlot = fallbackFieldPlot
  const displayFieldPlots = [primaryFieldPlot]
  const commandPoint = computeCommandPoint(primaryFieldPlot.boundary, mapCenter)
  const fallbackRoutePoints = buildDemoFallbackRoute()
  const routePoints = buildCoverageRouteFromBoundary(primaryFieldPlot.boundary)
  const finalRoutePoints = routePoints.length >= 2 ? routePoints : fallbackRoutePoints
  const routeHoldPosition = resolveStaticRoutePosition(finalRoutePoints)
  const coveragePoints: LatLngTuple[] = []

  const isSpraying = droneStatus === 'spraying' || droneStatus === '作业中'
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

  // Density heatmap from detection positions
  const densityGrid = useMemo(() => {
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
  const telemetry = {
    altitude: 5,
    speed: 4.5,
    battery: activeDrones[0]?.battery ?? null,
  }
  const [showHeatmap, setShowHeatmap] = useState(true)
  const viewBox = '0 0 160 100'

  const densityColor = (d: number) => {
    if (d >= 0.8) return 'rgba(192, 96, 90, 0.35)'
    if (d >= 0.6) return 'rgba(196, 138, 42, 0.30)'
    if (d >= 0.3) return 'rgba(90, 138, 106, 0.25)'
    return 'rgba(90, 138, 106, 0.12)'
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
            <path d="M 8 0 L 0 0 0 8" fill="none" stroke="rgba(32, 91, 154, 0.10)" strokeWidth="0.35" />
          </pattern>
          <filter id="drone-glow">
            <feGaussianBlur stdDeviation="1.2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="trajectory-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#089cc5" />
            <stop offset="50%" stopColor="#6f63d9" />
            <stop offset="100%" stopColor="#d96d2d" />
          </linearGradient>
        </defs>

        <rect x="0" y="0" width="160" height="100" fill="#f6f9ff" />
        <rect x="0" y="0" width="160" height="100" fill="url(#map-grid)" opacity="0.7" />
        <rect
          x="0"
          y="0"
          width="160"
          height="100"
          fill="rgba(255, 255, 255, 0.46)"
          stroke="rgba(32, 91, 154, 0.12)"
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
                fill="#102033"
                stroke="rgba(255, 255, 255, 0.85)"
                strokeWidth="0.5"
                paintOrder="stroke"
              >
                {fieldItem.name}
              </text>
            </g>
          )
        })}

        {showHeatmap && densityGrid && densityGrid.length > 0 && (
          <g opacity="0.85">
            {densityGrid.map((cell, i) => (
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
            fill="#d96d2d"
            fillOpacity="0.08"
            stroke="#d96d2d"
            strokeWidth="0.8"
            strokeDasharray="2 2"
          />
        ) : null}

        {routePoints.length >= 2 ? (
          <>
            <polyline
              points={toSvgPoints(routePoints)}
              fill="none"
              stroke="rgba(255, 255, 255, 0.92)"
              strokeWidth="3.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <polyline
              points={toSvgPoints(routePoints)}
              fill="none"
              stroke="#0f766e"
              strokeWidth="1.8"
              strokeDasharray="3 1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {routePoints.map((point, index) => (
              <g key={`route-waypoint-${index}-${point[0].toFixed(3)}-${point[1].toFixed(3)}`}>
                <circle
                  cx={point[1]}
                  cy={point[0]}
                  r={index === 0 ? 2 : 1.35}
                  fill={index === 0 ? '#42d392' : '#16875a'}
                  stroke="rgba(255, 255, 255, 0.72)"
                  strokeWidth="0.7"
                />
                {index === 0 ? (
                  <text
                    x={point[1] + 1.8}
                    y={point[0] - 1.2}
                    fontSize="3"
                    fill="#102033"
                    stroke="rgba(255, 255, 255, 0.85)"
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
            <g key={markerKey} filter="url(#drone-glow)">
              <g opacity="0.86">
                <path
                  d={`M ${drone.position.x} ${drone.position.y + 1.8} L ${drone.position.x - 4.6} ${drone.position.y + 8.2} L ${drone.position.x + 4.6} ${drone.position.y + 8.2} Z`}
                  fill="#16875a"
                  fillOpacity="0.12"
                />
                <ellipse
                  cx={drone.position.x}
                  cy={drone.position.y + 8.2}
                  rx="5.2"
                  ry="1.35"
                  fill="#16875a"
                  fillOpacity="0.16"
                />
                <circle cx={drone.position.x - 2.8} cy={drone.position.y + 5.8} r="0.45" fill="#42d392" fillOpacity="0.52" />
                <circle cx={drone.position.x} cy={drone.position.y + 6.9} r="0.38" fill="#42d392" fillOpacity="0.46" />
                <circle cx={drone.position.x + 2.6} cy={drone.position.y + 5.5} r="0.42" fill="#42d392" fillOpacity="0.5" />
              </g>
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
                stroke="#102033"
                strokeWidth="0.4"
              />
              <text
                x={drone.position.x}
                y={drone.position.y - 3.4}
                textAnchor="middle"
                fontSize="3.2"
                fill="#102033"
                stroke="rgba(255, 255, 255, 0.88)"
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
              fill="#c73758"
              fillOpacity="0.15"
              stroke="#c73758"
              strokeWidth="0.5"
            />
            <circle
              cx={marker.point[1]}
              cy={marker.point[0]}
              r="0.8"
              fill="#c73758"
            />
          </g>
        ))}

        <g>
          <circle cx={commandPoint[1]} cy={commandPoint[0]} r="1.4" fill="#d78d1f" stroke="#102033" strokeWidth="0.4" />
          <circle cx={commandPoint[1]} cy={commandPoint[0]} r="2.8" fill="none" stroke="rgba(215, 141, 31, 0.25)" strokeWidth="0.7" />
          <text
            x={commandPoint[1] + 2.2}
            y={commandPoint[0] - 1.6}
            fontSize="3"
            fill="#102033"
            stroke="rgba(255, 255, 255, 0.84)"
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
            background: isSpraying ? 'rgba(22, 135, 90, 0.08)' : 'rgba(215, 141, 31, 0.08)',
            borderColor: isSpraying ? 'rgba(22, 135, 90, 0.2)' : 'rgba(215, 141, 31, 0.2)',
          }}
        >
          {isSpraying ? 'PX4 喷洒中' : '等待任务'}
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
                <span className="map-legend-dot" style={{ background: 'var(--accent-red)' }} />
                <span>检测点 ({detectionMarkers.length})</span>
              </div>
            )}
            {densityGrid && densityGrid.length > 0 && (
              <div className="map-legend-item" style={{ cursor: 'pointer' }} onClick={() => setShowHeatmap(!showHeatmap)}>
                <span className="map-legend-swatch" style={{ background: showHeatmap ? 'var(--accent-amber)' : 'var(--text-muted)', opacity: 0.5 }} />
                <span>{showHeatmap ? '隐藏热力图' : '显示热力图'}</span>
              </div>
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

      </aside>
    </div>
  )
}
