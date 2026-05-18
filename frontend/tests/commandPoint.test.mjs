import assert from 'node:assert/strict'
import test from 'node:test'

import { computeCommandPoint } from '../src/components/map/commandPoint.ts'

test('computeCommandPoint places the command point just left of the field centerline', () => {
  const boundary = [
    [16, 22],
    [16, 138],
    [84, 138],
    [84, 22],
  ]

  const [lat, lng] = computeCommandPoint(boundary)

  assert.equal(lat, 50)
  assert.ok(lng < 22)
  assert.ok(lng >= 8)
})

test('computeCommandPoint falls back to the provided center when boundary is missing', () => {
  const point = computeCommandPoint([], [50, 80])

  assert.deepEqual(point, [50, 80])
})
