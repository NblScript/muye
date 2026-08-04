import type { OrbitControls } from 'three/addons/controls/OrbitControls.js'

export const MAP_CAMERA_TARGET = [18, 4, -2] as const

export function configureMapOrbitControls(controls: OrbitControls) {
  controls.enablePan = true
  controls.enableZoom = true
  controls.enableRotate = true
  controls.zoomSpeed = 0.3
  controls.minDistance = 100
  controls.maxDistance = 300
  controls.maxPolarAngle = 1.5
  controls.target.set(...MAP_CAMERA_TARGET)
  controls.update()
}
