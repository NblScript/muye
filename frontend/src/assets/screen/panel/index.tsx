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
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-template-rows: repeat(6, minmax(0, 1fr));
  gap: 20px;
  padding: 20px 20px 100px;
`

const Card = styled.div`
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  padding: 15px;
  border: 1px solid rgba(255, 145, 0, 0.3);
  border-radius: 4px;
  background: rgba(255, 245, 232, 0.65);
  backdrop-filter: blur(4px);
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
  &::before { top: -1px; left: -1px; border-top: 2px solid #ea580c; border-left: 2px solid #ea580c; }
  &::after { right: -1px; bottom: -1px; border-right: 2px solid #ea580c; border-bottom: 2px solid #ea580c; }
  &:hover::before, &:hover::after { width: 100%; height: 100%; opacity: .5; }
`

const CardTitle = styled.div`
  flex: 0 0 auto;
  margin-bottom: 10px;
  padding-left: 10px;
  border-left: 4px solid #fdb961;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #5a4a42;
  font-size: 18px;

  span { color: rgba(0,0,0,.4); font-size: 10px; font-weight: normal; }
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
    const unsubscribeMap = useConfigStore.subscribe((state) => state.mapPlayComplete, (complete) => {
      if (!complete) return
      for (const restart of [restartTop, restartBottom, restartLeft, restartLeft1, restartLeft2, restartRight, restartRight1, restartRight2]) restart()
    })
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
    return () => { unsubscribeMap(); unsubscribeMode() }
  }, [
    restartBottom, restartLeft, restartLeft1, restartLeft2, restartRight, restartRight1, restartRight2, restartTop,
    reverseLeft, reverseLeft1, reverseLeft2, reverseRight, reverseRight1, reverseRight2, reverseTop,
  ])

  return (
    <AutoFit>
      <Header ref={topRef} model={model} />
      <GridWrapper>
        <Card ref={leftRef} style={{ gridArea: '1 / 1 / 3 / 2' }}>
          <CardTitle>昆虫识别与数量<span>PEST DETECTION</span></CardTitle>
          <CardBody><Chart1 pests={model.pests} /></CardBody>
        </Card>
        <Card ref={leftRef1} style={{ gridArea: '3 / 1 / 5 / 2' }}>
          <CardTitle>气象与施药窗口<span>WEATHER WINDOW</span></CardTitle>
          <CardBody><Chart2 metrics={model.weather} ready={model.weatherReady} suitable={model.weatherSuitable} /></CardBody>
        </Card>
        <Card ref={leftRef2} style={{ gridArea: '5 / 1 / 7 / 2' }}>
          <CardTitle>真实任务处理链<span>PIPELINE EVENTS</span></CardTitle>
          <CardBody><Chart3 stages={model.pipeline} /></CardBody>
        </Card>
        <Card ref={rightRef} style={{ gridArea: '1 / 4 / 3 / 5' }}>
          <CardTitle>AI 会诊与防治方案<span>AI DECISION</span></CardTitle>
          <CardBody><Chart4 decision={model.decision} /></CardBody>
        </Card>
        <Card ref={rightRef1} style={{ gridArea: '3 / 4 / 5 / 5' }}>
          <CardTitle>无人机执行状态<span>UAV MISSION</span></CardTitle>
          <CardBody><Chart5 drone={model.drone} /></CardBody>
        </Card>
        <Card ref={rightRef2} style={{ gridArea: '5 / 4 / 7 / 5' }}>
          <CardTitle>虫情热力与防治闭环<span>HEAT & EVALUATION</span></CardTitle>
          <CardBody><Chart6 evaluation={model.evaluation} /></CardBody>
        </Card>
      </GridWrapper>
      <Footer ref={bottomRef} model={model} actions={actions} />
    </AutoFit>
  )
}
