import { Vector3 } from 'three'

export interface RouteSegment {
  start: Vector3
  end: Vector3
}

export function buildRouteSegments(
  points: Vector3[],
  dashed = false,
  dashLength = 2.5,
  gapLength = 1.5,
): RouteSegment[] {
  const segments: RouteSegment[] = []

  for (let index = 1; index < points.length; index += 1) {
    const start = points[index - 1]
    const end = points[index]
    const distance = start.distanceTo(end)
    if (distance <= 0) continue

    if (!dashed) {
      segments.push({ start, end })
      continue
    }

    const step = Math.max(0.1, dashLength) + Math.max(0, gapLength)
    for (let offset = 0; offset < distance; offset += step) {
      const dashEnd = Math.min(offset + Math.max(0.1, dashLength), distance)
      segments.push({
        start: start.clone().lerp(end, offset / distance),
        end: start.clone().lerp(end, dashEnd / distance),
      })
    }
  }

  return segments
}
