import { useEffect, useMemo, useRef } from 'react'
import { type ThreeElements } from '@react-three/fiber'
import heatmapJs from 'keli-heatmap.js'
import {
  CanvasTexture,
  Color,
  DoubleSide,
  type Mesh,
  type PlaneGeometry,
  type ShaderMaterial,
} from 'three'
import type { ScreenViewModel } from '../model'
import { useConfigStore } from '../store'

interface FieldHeatmapProps extends Omit<ThreeElements['group'], 'visible'> {
  model: ScreenViewModel
  width: number
  depth: number
}

export default function FieldHeatmap({ model, width, depth, ...groupProps }: FieldHeatmapProps) {
  const meshRef = useRef<Mesh<PlaneGeometry, ShaderMaterial>>(null!)
  const visible = useConfigStore((state) => state.heat)
  const heatCellsSnapshot = JSON.stringify(model.fieldTwin.heatCells)
  const uniforms = useMemo(() => ({
    heatMap: { value: null as CanvasTexture | null },
    greyMap: { value: null as CanvasTexture | null },
    zScale: { value: 0.65 },
    baseColor: { value: new Color('#ffffff') },
    opacity: { value: 0.76 },
  }), [])

  useEffect(() => {
    const heatCells = JSON.parse(heatCellsSnapshot) as ScreenViewModel['fieldTwin']['heatCells']
    const canvasWidth = 640
    const canvasHeight = 420
    const container = document.createElement('div')
    container.style.cssText = 'position:absolute;left:-9999px;top:-9999px;width:640px;height:420px;'
    document.body.appendChild(container)

    const gradient = {
      0.18: '#2769d8',
      0.36: '#1fc2e1',
      0.52: '#3bcf65',
      0.68: '#d6da31',
      0.82: '#ffad32',
      1: '#ef2d20',
    }
    const heatmap = heatmapJs.create({
      container,
      gradient,
      blur: 0.72,
      radius: 28,
      maxOpacity: 0.78,
      width: canvasWidth,
      height: canvasHeight,
    })
    const greymap = heatmapJs.create({
      container,
      gradient: { 0: '#000000', 1: '#ffffff' },
      blur: 0.72,
      radius: 28,
      maxOpacity: 1,
      width: canvasWidth,
      height: canvasHeight,
    })

    const source = heatCells
      .filter((cell) => cell.density >= 0.035)
      .map((cell) => ({
        x: Math.round((cell.x + cell.width / 2) * canvasWidth),
        y: Math.round((cell.y + cell.height / 2) * canvasHeight),
        value: Math.max(1, Math.round(Math.pow(cell.density, 1.12) * 100)),
        radius: Math.max(18, Math.min(38, Math.round(Math.max(cell.width * canvasWidth, cell.height * canvasHeight) * 1.05))),
      }))
    heatmap.setData({ min: 0, max: 100, data: source })
    greymap.setData({ min: 0, max: 100, data: source })

    const heatTexture = new CanvasTexture(heatmap._renderer.canvas)
    const greyTexture = new CanvasTexture(greymap._renderer.canvas)
    heatTexture.needsUpdate = true
    greyTexture.needsUpdate = true
    meshRef.current.material.uniforms.heatMap.value = heatTexture
    meshRef.current.material.uniforms.greyMap.value = greyTexture

    return () => {
      heatTexture.dispose()
      greyTexture.dispose()
      container.remove()
    }
  }, [heatCellsSnapshot, uniforms])

  return (
    <group visible={visible && model.fieldTwin.heatCells.length > 0} {...groupProps}>
      <mesh ref={meshRef} rotation-x={-Math.PI / 2} position-y={5.55} renderOrder={12}>
        <planeGeometry args={[width, depth, 128, 96]} />
        <shaderMaterial
          transparent
          depthWrite={false}
          side={DoubleSide}
          vertexShader={`
            varying vec2 vUv;
            uniform float zScale;
            uniform sampler2D greyMap;
            void main() {
              vUv = uv;
              vec4 density = texture2D(greyMap, uv);
              vec3 transformed = vec3(position.x, position.y, position.z + zScale * density.a);
              gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
            }
          `}
          fragmentShader={`
            varying vec2 vUv;
            uniform sampler2D heatMap;
            uniform vec3 baseColor;
            uniform float opacity;
            void main() {
              vec4 heat = texture2D(heatMap, vUv);
              gl_FragColor = vec4(heat.rgb * baseColor, heat.a * opacity);
            }
          `}
          uniforms={uniforms}
        />
      </mesh>
    </group>
  )
}
