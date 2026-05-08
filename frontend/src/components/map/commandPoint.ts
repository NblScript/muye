import type { LatLngTuple } from 'leaflet'

import { mapCenter } from './mapData.ts'

export function computeCommandPoint(
  boundary: LatLngTuple[],
  fallback: LatLngTuple = mapCenter,
): LatLngTuple {
  if (boundary.length < 3) {
    return fallback
  }

  const longitudes = boundary.map(([, lng]) => lng)
  const latitudes = boundary.map(([lat]) => lat)
  const minLng = Math.min(...longitudes)
  const maxLng = Math.max(...longitudes)
  const minLat = Math.min(...latitudes)
  const maxLat = Math.max(...latitudes)
  const fieldWidth = Math.max(maxLng - minLng, 1)
  const gap = Math.min(12, Math.max(6, fieldWidth * 0.08))

  return [
    (minLat + maxLat) / 2,
    Math.max(8, minLng - gap),
  ]
}
