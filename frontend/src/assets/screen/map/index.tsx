import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import styled from 'styled-components'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { ScreenViewModel } from '../model'
import { configureMapOrbitControls } from './cameraControls'
import Lights from './lights'
import Scene from './scene'

const CanvasWrapper = styled.div`
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
`

const Overlay = styled.div`
  position: absolute;
  inset: 0;
  z-index: 20;
  pointer-events: none;
  color: #fff;
`

const FieldTitle = styled.div`
  position: absolute;
  top: 15%;
  left: 50%;
  min-width: 290px;
  padding: 8px 12px;
  border: 1px solid rgba(141, 141, 141, 0.28);
  border-radius: 5px;
  background: rgba(16, 22, 23, 0.72);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(10px);
  text-align: center;
  transform: translateX(-50%);

  strong { display: block; font-size: 14px; }
  span { display: block; margin-top: 3px; color: rgba(255, 255, 255, 0.58); font-size: 10px; }
`

const SnapshotControls = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 7px;
  pointer-events: auto;

  label { color: rgba(255, 255, 255, 0.68); font-size: 9px; }
  select {
    max-width: 132px;
    padding: 3px 6px;
    border: 1px solid rgba(127, 229, 168, 0.34);
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.44);
    color: #fff;
    font-size: 9px;
  }
`

const HeatLegend = styled.div`
  position: absolute;
  top: 38%;
  left: calc(50% + 235px);
  width: 78px;
  padding: 9px;
  border: 1px solid rgba(141, 141, 141, 0.26);
  border-radius: 5px;
  background: rgba(16, 22, 23, 0.72);
  box-shadow: 0 12px 26px rgba(0, 0, 0, 0.26);
  backdrop-filter: blur(10px);
  font-size: 9px;

  .title { margin-bottom: 6px; font-weight: 700; }
  .source { margin-bottom: 6px; color: rgba(255, 255, 255, 0.58); line-height: 1.35; }
  .scale { height: 94px; border-radius: 4px; background: linear-gradient(to top, #2769d8, #1fc2e1, #3bcf65, #d6da31, #ffad32, #ef2d20); }
  .range { display: flex; justify-content: space-between; margin-top: 3px; }
  .summary { margin-top: 7px; line-height: 1.5; }
  .snapshot { margin-top: 7px; color: rgba(255, 255, 255, 0.62); line-height: 1.4; }
`

const Waiting = styled.div`
  position: absolute;
  top: 48%;
  left: 50%;
  width: 250px;
  padding: 12px 15px;
  border: 1px solid rgba(127, 229, 168, 0.28);
  border-radius: 5px;
  background: rgba(16, 22, 23, 0.82);
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
  text-align: center;
  transform: translate(-50%, -50%);
`

function MapOrbitControls() {
  const camera = useThree((state) => state.camera)
  const domElement = useThree((state) => state.gl.domElement)
  const controlsRef = useRef<OrbitControls | null>(null)

  useEffect(() => {
    const controls = new OrbitControls(camera, domElement)
    configureMapOrbitControls(controls)
    controlsRef.current = controls
    return () => {
      controls.dispose()
      controlsRef.current = null
    }
  }, [camera, domElement])

  useFrame(() => controlsRef.current?.update())
  return null
}

function FieldShadow() {
  return (
    <mesh rotation-x={-Math.PI / 2} position={[18, 0.15, -2]} scale={[1.25, 0.76, 1]}>
      <circleGeometry args={[78, 64]} />
      <meshBasicMaterial color="#080d0e" transparent opacity={0.32} depthWrite={false} />
    </mesh>
  )
}

type MapProps = {
  model: ScreenViewModel
  pestOptions: { value: string; label: string }[]
  selectedPestType: string
  onSelectPest: (value: string) => void
}

function formatSnapshotTime(value: string) {
  if (!value) return '等待快照'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function Map({ model, pestOptions, selectedPestType, onSelectPest }: MapProps) {
  const cells = model.fieldTwin.heatCells
  const average = cells.length ? cells.reduce((sum, cell) => sum + cell.density, 0) / cells.length : 0
  const hotspotCount = cells.filter((cell) => cell.density >= 0.7).length

  return (
    <CanvasWrapper data-testid="command-map">
      <Canvas
        flat
        camera={{ position: [-50, 125, 250], fov: 50, far: 2000, near: 1 }}
        dpr={[1, 1.5]}
        gl={{ antialias: false }}
      >
        <color attach="background" args={['#26282a']} />
        <MapOrbitControls />
        <Lights />
        <FieldShadow />
        <Scene model={model} />
      </Canvas>
      <Overlay>
        <FieldTitle data-testid="field-title">
          <strong>昆虫密度热力值地图</strong>
          <span>{model.field.name} · {model.field.crop} · 检测 {model.field.pestCount} 只</span>
          <SnapshotControls>
            <label htmlFor="dashboard-pest-filter">虫种</label>
            <select
              id="dashboard-pest-filter"
              aria-label="首页虫种筛选"
              value={selectedPestType}
              onChange={(event) => onSelectPest(event.target.value)}
            >
              <option value="all">全部虫种</option>
              {pestOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </SnapshotControls>
        </FieldTitle>
        <HeatLegend data-testid="heat-legend">
          <div className="title">虫情相对热值</div>
          <div className="source">{model.fieldTwin.densitySourceLabel}</div>
          <div className="scale" />
          <div className="range"><span>低</span><span>高</span></div>
          <div className="summary">
            平均 {Math.round(average * 100)}<br />热点 {hotspotCount} 个
            {model.fieldTwin.densityAcceptedCount !== null && <><br />批次有效框 {model.fieldTwin.densityAcceptedCount} 个</>}
          </div>
          <div className="snapshot">
            {model.fieldTwin.snapshotInspectionKind}<br />
            {formatSnapshotTime(model.fieldTwin.snapshotCapturedAt)}
            {model.fieldTwin.snapshotAlgorithmVersion && <><br />{model.fieldTwin.snapshotAlgorithmVersion}</>}
          </div>
        </HeatLegend>
        {model.requestId === '--' && <Waiting>等待接入巡检图像并生成昆虫密度热力值</Waiting>}
      </Overlay>
    </CanvasWrapper>
  )
}
