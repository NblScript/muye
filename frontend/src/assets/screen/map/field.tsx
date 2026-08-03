import { Html, Line } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { gsap } from 'gsap'
import { useLayoutEffect, useMemo, useRef } from 'react'
import { Color, Group, Mesh, Vector3 } from 'three'
import type { ScreenViewModel, TwinPoint } from '../model'
import { useConfigStore } from '../store'
import FieldHeatmap from './fieldHeatmap'

const FIELD_WIDTH = 118
const FIELD_DEPTH = 78

function fieldPosition(point: TwinPoint, height = 5): [number, number, number] {
  return [
    (point.x - 0.5) * FIELD_WIDTH,
    height,
    (point.y - 0.5) * FIELD_DEPTH,
  ]
}

function densityColor(value: number) {
  if (value >= 0.8) return '#e95518'
  if (value >= 0.55) return '#f59e0b'
  if (value >= 0.3) return '#f5c85b'
  return '#77a66b'
}

function Drone({ model }: { model: ScreenViewModel }) {
  const groupRef = useRef<Group>(null!)
  const rotorRefs = useRef<Mesh[]>([])
  const visible = useConfigStore((state) => state.drone)
  const position = model.fieldTwin.dronePosition

  useFrame((_, delta) => {
    rotorRefs.current.forEach((rotor) => { rotor.rotation.y += delta * 18 })
    if (groupRef.current) groupRef.current.position.y = 15 + Math.sin(performance.now() / 450) * 0.8
  })

  if (!position || !visible) return null
  const [x, , z] = fieldPosition(position, 15)

  return (
    <group ref={groupRef} position={[x, 15, z]} scale={0.72}>
      <mesh castShadow><boxGeometry args={[7, 1.6, 4.5]} /><meshStandardMaterial color="#fff5e8" metalness={0.35} roughness={0.36} /></mesh>
      <mesh position={[0, -1.25, 0]} castShadow><boxGeometry args={[2.6, 1.6, 2.6]} /><meshStandardMaterial color="#ea580c" /></mesh>
      {([[-5, 0, -4], [5, 0, -4], [-5, 0, 4], [5, 0, 4]] as [number, number, number][]).map((offset, index) => (
        <group key={index} position={offset}>
          <mesh rotation-y={index % 2 ? Math.PI / 4 : -Math.PI / 4}><boxGeometry args={[8, .35, .45]} /><meshStandardMaterial color="#6b5144" /></mesh>
          <mesh ref={(mesh) => { if (mesh) rotorRefs.current[index] = mesh }} position-y={0.5}>
            <cylinderGeometry args={[3.2, 3.2, .16, 24]} />
            <meshBasicMaterial color="#ea580c" transparent opacity={0.46} />
          </mesh>
        </group>
      ))}
      <pointLight color="#ff7a2e" intensity={2.5} distance={20} position={[0, -2, 0]} />
    </group>
  )
}

export default function Field({ model }: { model: ScreenViewModel }) {
  const groupRef = useRef<Group>(null!)
  const camera = useThree((state) => state.camera)
  const showHeat = useConfigStore((state) => state.heat)
  const showPests = useConfigStore((state) => state.bar)
  const route = useMemo(
    () => model.fieldTwin.route.map((point) => new Vector3(...fieldPosition(point, 6.2))),
    [model.fieldTwin.route],
  )
  const completedRoute = useMemo(() => {
    if (route.length < 2 || model.drone.progress <= 0) return []
    const lastIndex = Math.max(1, Math.min(route.length, Math.ceil((model.drone.progress / 100) * route.length)))
    return route.slice(0, lastIndex)
  }, [route, model.drone.progress])
  const heatSummary = useMemo(() => {
    const cells = model.fieldTwin.heatCells
    const average = cells.length ? cells.reduce((sum, cell) => sum + cell.density, 0) / cells.length : 0
    const hotspotCount = cells.filter((cell) => cell.density >= 0.7).length
    return { average, hotspotCount }
  }, [model.fieldTwin.heatCells])

  useLayoutEffect(() => {
    if (!groupRef.current) return
    groupRef.current.scale.setScalar(0.01)
    const timeline = gsap.timeline({ onComplete: () => useConfigStore.setState({ mapPlayComplete: true }) })
    timeline.to(camera.position, { x: 58, y: 124, z: 166, duration: 1.8, ease: 'circ.out' })
    timeline.to(groupRef.current.scale, { x: 1, y: 1, z: 1, duration: 0.9, ease: 'circ.out' }, 1.45)
    return () => { timeline.kill() }
  }, [camera])

  return (
    <group ref={groupRef} position={[18, 2, -2]}>
      <mesh position={[0, 1, 0]} castShadow receiveShadow>
        <boxGeometry args={[FIELD_WIDTH + 8, 3, FIELD_DEPTH + 8]} />
        <meshStandardMaterial color="#c98d52" metalness={0.08} roughness={0.88} />
      </mesh>
      <mesh position={[0, 3, 0]} receiveShadow>
        <boxGeometry args={[FIELD_WIDTH, 2, FIELD_DEPTH]} />
        <meshStandardMaterial color="#6f8f57" roughness={0.94} />
      </mesh>

      {Array.from({ length: 16 }, (_, index) => {
        const z = -FIELD_DEPTH / 2 + 4 + index * ((FIELD_DEPTH - 8) / 15)
        return (
          <group key={index} position={[0, 4.3, z]}>
            <mesh castShadow receiveShadow>
              <boxGeometry args={[FIELD_WIDTH - 7, 1.2, 1.45]} />
              <meshStandardMaterial color={index % 2 ? '#8aae68' : '#769b59'} roughness={0.9} />
            </mesh>
            {Array.from({ length: 18 }, (_, cropIndex) => (
              <mesh key={cropIndex} position={[-FIELD_WIDTH / 2 + 7 + cropIndex * 6.15, 1.25, 0]} castShadow>
                <coneGeometry args={[0.7, 2.5, 5]} />
                <meshStandardMaterial color={cropIndex % 3 ? '#5f8d4d' : '#739f55'} />
              </mesh>
            ))}
          </group>
        )
      })}

      {showHeat && <FieldHeatmap model={model} width={FIELD_WIDTH} depth={FIELD_DEPTH} />}

      {showPests && model.fieldTwin.pestPoints.map((point, index) => {
        const [x, , z] = fieldPosition(point, 6)
        const height = 4 + point.confidence * 10
        return (
          <group key={`${point.name}-${index}`} position={[x, 5.2, z]}>
            <mesh position-y={height / 2} castShadow>
              <cylinderGeometry args={[0.42, 1.15, height, 10]} />
              <meshStandardMaterial color={new Color(densityColor(point.confidence))} emissive="#8b2c08" emissiveIntensity={0.24} />
            </mesh>
            <mesh rotation-x={-Math.PI / 2} position-y={0.2}>
              <ringGeometry args={[1.2, 2.3, 28]} />
              <meshBasicMaterial color="#ea580c" transparent opacity={0.62} />
            </mesh>
          </group>
        )
      })}

      {route.length >= 2 && <Line points={route} color="#e9a23b" lineWidth={2.2} dashed dashSize={2.5} gapSize={1.5} />}
      {completedRoute.length >= 2 && <Line points={completedRoute} color="#ea580c" lineWidth={4} />}
      <Drone model={model} />

      <Html position={[0, 10, -FIELD_DEPTH / 2 - 5]} center distanceFactor={110} zIndexRange={[10, 30]}>
        <div style={{ minWidth: 250, padding: '8px 12px', border: '1px solid rgba(234,88,12,.25)', borderRadius: 5, background: 'rgba(255,245,232,.9)', color: '#665044', textAlign: 'center', boxShadow: '0 8px 24px rgba(100,65,35,.12)' }}>
          <strong style={{ display: 'block', fontSize: 14 }}>昆虫密度热力值地图</strong>
          <span style={{ display: 'block', marginTop: 3, color: 'rgba(90,74,66,.58)', fontSize: 10 }}>{model.field.name} · {model.field.crop} · 检测 {model.field.pestCount} 只</span>
        </div>
      </Html>

      <Html position={[FIELD_WIDTH / 2 + 10, 9, 4]} center distanceFactor={110} zIndexRange={[10, 30]}>
        <div style={{ width: 78, padding: '9px', border: '1px solid rgba(234,88,12,.18)', borderRadius: 5, background: 'rgba(255,247,236,.9)', color: '#6c5749', fontSize: 9, boxShadow: '0 8px 20px rgba(100,65,35,.1)' }}>
          <div style={{ marginBottom: 6, fontWeight: 700 }}>虫情热力值</div>
          <div style={{ height: 94, borderRadius: 4, background: 'linear-gradient(to top,#2769d8,#1fc2e1,#3bcf65,#d6da31,#ffad32,#ef2d20)' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}><span>低</span><span>高</span></div>
          <div style={{ marginTop: 7, lineHeight: 1.5 }}>平均 {Math.round(heatSummary.average * 100)}<br />热点 {heatSummary.hotspotCount} 个</div>
        </div>
      </Html>

      {model.requestId === '--' && (
        <Html position={[0, 12, 0]} center distanceFactor={110} zIndexRange={[10, 30]}>
          <div style={{ width: 250, padding: '12px 15px', border: '1px solid rgba(234,88,12,.2)', borderRadius: 5, background: 'rgba(255,250,242,.9)', color: '#806d60', textAlign: 'center', fontSize: 12 }}>
            等待接入巡检图像并生成昆虫密度热力值
          </div>
        </Html>
      )}
    </group>
  )
}
