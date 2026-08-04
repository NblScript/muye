import { PerspectiveCamera } from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { describe, expect, it } from 'vitest'

import {
  configureMapOrbitControls,
  MAP_CAMERA_TARGET,
} from '../src/assets/screen/map/cameraControls'

describe('sc-datav compatible map camera controls', () => {
  it('enables pan, zoom, and rotate with the reference project limits', () => {
    const camera = new PerspectiveCamera(50, 1, 1, 2000)
    camera.position.set(-50, 125, 250)
    const controls = new OrbitControls(camera, document.createElement('canvas'))

    configureMapOrbitControls(controls)

    expect(controls.enablePan).toBe(true)
    expect(controls.enableZoom).toBe(true)
    expect(controls.enableRotate).toBe(true)
    expect(controls.zoomSpeed).toBe(0.3)
    expect(controls.minDistance).toBe(100)
    expect(controls.maxDistance).toBe(300)
    expect(controls.maxPolarAngle).toBe(1.5)
    expect(controls.target.toArray()).toEqual([...MAP_CAMERA_TARGET])

    controls.dispose()
  })
})
