import { describe, expect, it } from 'vitest'
import { Vector3 } from 'three'

import { buildRouteSegments } from '../src/assets/screen/map/routeGeometry'

describe('route geometry', () => {
  it('keeps each waypoint pair as a continuous segment', () => {
    const points = [
      new Vector3(0, 6, 0),
      new Vector3(10, 6, 0),
      new Vector3(10, 6, 8),
    ]

    const segments = buildRouteSegments(points)

    expect(segments).toHaveLength(2)
    expect(segments[0].start).toBe(points[0])
    expect(segments[1].end).toBe(points[2])
  })

  it('creates deterministic dash segments without extending past the route', () => {
    const segments = buildRouteSegments(
      [new Vector3(0, 0, 0), new Vector3(10, 0, 0)],
      true,
      2,
      1,
    )

    expect(segments).toHaveLength(4)
    expect(segments.map((segment) => [segment.start.x, segment.end.x])).toEqual([
      [0, 2],
      [3, 5],
      [6, 8],
      [9, 10],
    ])
  })

  it('ignores duplicate points', () => {
    expect(buildRouteSegments([
      new Vector3(1, 1, 1),
      new Vector3(1, 1, 1),
    ])).toEqual([])
  })
})
