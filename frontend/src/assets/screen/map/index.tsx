import { Canvas, useFrame, useThree } from '@react-three/fiber'
import styled from 'styled-components'
import type { ScreenViewModel } from '../model'
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
  color: #665044;
`

const FieldTitle = styled.div`
  position: absolute;
  top: 15%;
  left: 50%;
  min-width: 250px;
  padding: 8px 12px;
  border: 1px solid rgba(234, 88, 12, 0.25);
  border-radius: 5px;
  background: rgba(255, 245, 232, 0.9);
  box-shadow: 0 8px 24px rgba(100, 65, 35, 0.12);
  text-align: center;
  transform: translateX(-50%);

  strong { display: block; font-size: 14px; }
  span { display: block; margin-top: 3px; color: rgba(90, 74, 66, 0.58); font-size: 10px; }
`

const HeatLegend = styled.div`
  position: absolute;
  top: 38%;
  left: calc(50% + 235px);
  width: 78px;
  padding: 9px;
  border: 1px solid rgba(234, 88, 12, 0.18);
  border-radius: 5px;
  background: rgba(255, 247, 236, 0.9);
  box-shadow: 0 8px 20px rgba(100, 65, 35, 0.1);
  font-size: 9px;

  .title { margin-bottom: 6px; font-weight: 700; }
  .source { margin-bottom: 6px; color: rgba(90, 74, 66, 0.58); line-height: 1.35; }
  .scale { height: 94px; border-radius: 4px; background: linear-gradient(to top, #2769d8, #1fc2e1, #3bcf65, #d6da31, #ffad32, #ef2d20); }
  .range { display: flex; justify-content: space-between; margin-top: 3px; }
  .summary { margin-top: 7px; line-height: 1.5; }
`

const Waiting = styled.div`
  position: absolute;
  top: 48%;
  left: 50%;
  width: 250px;
  padding: 12px 15px;
  border: 1px solid rgba(234, 88, 12, 0.2);
  border-radius: 5px;
  background: rgba(255, 250, 242, 0.9);
  color: #806d60;
  font-size: 12px;
  text-align: center;
  transform: translate(-50%, -50%);
`

function FixedCameraTarget() {
  const camera = useThree((state) => state.camera)
  useFrame(() => camera.lookAt(18, 4, -2))
  return null
}

function FieldShadow() {
  return (
    <mesh rotation-x={-Math.PI / 2} position={[18, 0.15, -2]} scale={[1.25, 0.76, 1]}>
      <circleGeometry args={[78, 64]} />
      <meshBasicMaterial color="#79583f" transparent opacity={0.13} depthWrite={false} />
    </mesh>
  )
}

export default function Map({ model }: { model: ScreenViewModel }) {
  const cells = model.fieldTwin.heatCells
  const average = cells.length ? cells.reduce((sum, cell) => sum + cell.density, 0) / cells.length : 0
  const hotspotCount = cells.filter((cell) => cell.density >= 0.7).length

  return (
    <CanvasWrapper>
      <Canvas flat camera={{ position: [-50, 125, 250], fov: 50, far: 2000, near: 1 }} dpr={[1, 2]}>
        <color attach="background" args={['#fff5e8']} />
        <FixedCameraTarget />
        <Lights />
        <FieldShadow />
        <Scene model={model} />
      </Canvas>
      <Overlay>
        <FieldTitle>
          <strong>昆虫密度热力值地图</strong>
          <span>{model.field.name} · {model.field.crop} · 检测 {model.field.pestCount} 只</span>
        </FieldTitle>
        <HeatLegend>
          <div className="title">虫情相对热值</div>
          <div className="source">{model.fieldTwin.densitySourceLabel}</div>
          <div className="scale" />
          <div className="range"><span>低</span><span>高</span></div>
          <div className="summary">
            平均 {Math.round(average * 100)}<br />热点 {hotspotCount} 个
            {model.fieldTwin.densityAcceptedCount !== null && <><br />有效框 {model.fieldTwin.densityAcceptedCount} 个</>}
          </div>
        </HeatLegend>
        {model.requestId === '--' && <Waiting>等待接入巡检图像并生成昆虫密度热力值</Waiting>}
      </Overlay>
    </CanvasWrapper>
  )
}
