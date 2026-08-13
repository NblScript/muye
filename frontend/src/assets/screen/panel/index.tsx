import { useEffect } from 'react'
import styled from 'styled-components'
import useMoveTo from '../hooks/useMoveTo'
import type { ScreenViewModel } from '../model'
import { useConfigStore } from '../store'
import AutoFit from './autoFit'
import Chart1 from './chart1'
import Chart2 from './chart2'
import Chart3 from './chart3'
import Chart4 from './chart4'
import Chart5 from './chart5'
import Chart6 from './chart6'
import Footer, { type FooterActions } from './footer'
import Header from './header'

const GridWrapper = styled.div`
  position: relative;
  isolation: isolate;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-template-rows: repeat(6, minmax(0, 1fr));
  gap: 20px;
  padding: 20px 20px 100px;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background: radial-gradient(circle at 50% 48%, transparent 35%, rgba(0, 0, 0, 0.72) 100%);
  }
`

const Card = styled.div`
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  padding: 15px;
  color: #fff;
  border: 1px solid rgba(141, 141, 141, 0.24);
  border-radius: 4px;
  background:
    linear-gradient(135deg, rgba(127, 229, 168, 0.035), transparent 42%),
    repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.018) 0 1px, transparent 1px 6px),
    rgba(12, 18, 19, 0.58);
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  pointer-events: auto;
  z-index: 9999;

  &::before, &::after {
    content: '';
    position: absolute;
    width: 10px;
    height: 10px;
    pointer-events: none;
    transition: all .3s ease;
  }
  &::before { top: -1px; left: -1px; border-top: 2px solid #7fe5a8; border-left: 2px solid #7fe5a8; }
  &::after { right: -1px; bottom: -1px; border-right: 2px solid #7fe5a8; border-bottom: 2px solid #7fe5a8; }
  &:hover::before, &:hover::after { width: 100%; height: 100%; opacity: .5; }
`

const CardTitle = styled.div`
  flex: 0 0 auto;
  margin-bottom: 10px;
  padding-left: 10px;
  border-left: 3px solid #7fe5a8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #fff;
  font-size: 18px;

  span { color: rgba(255,255,255,.36); font-size: 10px; font-weight: normal; }
`

const CardBody = styled.div`
  flex: 1;
  min-height: 0;
  position: relative;
`

export interface PanelProps {
  model: ScreenViewModel
  actions: FooterActions
}

export default function Panel({ model, actions }: PanelProps) {
  const { ref: topRef, restart: restartTop, reverse: reverseTop } = useMoveTo<HTMLDivElement>('toBottom', .6)
  const { ref: leftRef, restart: restartLeft, reverse: reverseLeft } = useMoveTo<HTMLDivElement>('toRight', .8, .5)
  const { ref: leftRef1, restart: restartLeft1, reverse: reverseLeft1 } = useMoveTo<HTMLDivElement>('toRight', .8, .6)
  const { ref: leftRef2, restart: restartLeft2, reverse: reverseLeft2 } = useMoveTo<HTMLDivElement>('toRight', .8, .7)
  const { ref: rightRef, restart: restartRight, reverse: reverseRight } = useMoveTo<HTMLDivElement>('toLeft', .8, .5)
  const { ref: rightRef1, restart: restartRight1, reverse: reverseRight1 } = useMoveTo<HTMLDivElement>('toLeft', .8, .6)
  const { ref: rightRef2, restart: restartRight2, reverse: reverseRight2 } = useMoveTo<HTMLDivElement>('toLeft', .8, .7)
  const { ref: bottomRef, restart: restartBottom } = useMoveTo<HTMLDivElement>('toTop', .8, .5)

  useEffect(() => {
    let started = false
    const start = () => {
      if (started) return
      started = true
      for (const restart of [restartTop, restartBottom, restartLeft, restartLeft1, restartLeft2, restartRight, restartRight1, restartRight2]) restart()
    }
    const unsubscribeMap = useConfigStore.subscribe((state) => state.mapPlayComplete, (complete) => {
      if (complete) start()
    })
    // 渐进降级：面板入场不得永久依赖 3D 场景的完成事件。
    // WebGL 初始化失败或软件渲染过慢时，地图时间轴可能永远不触发
    // mapPlayComplete，此时必须在有限时间内让信息面板强制入场，
    // 否则整屏信息会停留在透明状态。
    const fallbackTimer = window.setTimeout(start, 4000)
    const unsubscribeMode = useConfigStore.subscribe((state) => state.mode, (visible) => {
      const transitions = [
        [restartTop, reverseTop], [restartLeft, reverseLeft], [restartLeft1, reverseLeft1],
        [restartLeft2, reverseLeft2], [restartRight, reverseRight], [restartRight1, reverseRight1], [restartRight2, reverseRight2],
      ]
      for (const [restart, reverse] of transitions) {
        if (visible) restart()
        else reverse()
      }
    })
    return () => { unsubscribeMap(); unsubscribeMode(); window.clearTimeout(fallbackTimer) }
  }, [
    restartBottom, restartLeft, restartLeft1, restartLeft2, restartRight, restartRight1, restartRight2, restartTop,
    reverseLeft, reverseLeft1, reverseLeft2, reverseRight, reverseRight1, reverseRight2, reverseTop,
  ])

  return (
    <AutoFit>
      <Header ref={topRef} model={model} />
      <GridWrapper data-testid="command-panel-grid">
        <Card ref={leftRef} data-testid="panel-pests" style={{ gridArea: '1 / 1 / 3 / 2' }}>
          <CardTitle>昆虫识别与数量<span>PEST DETECTION</span></CardTitle>
          <CardBody><Chart1 pests={model.pests} /></CardBody>
        </Card>
        <Card ref={leftRef1} data-testid="panel-weather" style={{ gridArea: '3 / 1 / 5 / 2' }}>
          <CardTitle>气象与施药窗口<span>WEATHER WINDOW</span></CardTitle>
          <CardBody><Chart2 metrics={model.weather} ready={model.weatherReady} suitable={model.weatherSuitable} /></CardBody>
        </Card>
        <Card ref={leftRef2} data-testid="panel-pipeline" style={{ gridArea: '5 / 1 / 7 / 2' }}>
          <CardTitle>真实任务处理链<span>PIPELINE EVENTS</span></CardTitle>
          <CardBody><Chart3 stages={model.pipeline} /></CardBody>
        </Card>
        <Card ref={rightRef} data-testid="panel-decision" style={{ gridArea: '1 / 4 / 3 / 5' }}>
          <CardTitle>AI 会诊与防治方案<span>AI DECISION</span></CardTitle>
          <CardBody><Chart4 decision={model.decision} /></CardBody>
        </Card>
        <Card ref={rightRef1} data-testid="panel-drone" style={{ gridArea: '3 / 4 / 5 / 5' }}>
          <CardTitle>无人机执行状态<span>UAV MISSION</span></CardTitle>
          <CardBody><Chart5 drone={model.drone} /></CardBody>
        </Card>
        <Card ref={rightRef2} data-testid="panel-evaluation" style={{ gridArea: '5 / 4 / 7 / 5' }}>
          <CardTitle>虫情热力与防治闭环<span>HEAT & EVALUATION</span></CardTitle>
          <CardBody><Chart6 evaluation={model.evaluation} /></CardBody>
        </Card>
      </GridWrapper>
      <Footer ref={bottomRef} model={model} actions={actions} />
    </AutoFit>
  )
}
