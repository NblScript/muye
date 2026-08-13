import styled from 'styled-components'
import type { DroneMetric } from '../model'

const Wrapper = styled.div`
  height: 100%;
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
`

const ProgressRing = styled.div<{ $progress: number; $active: boolean }>`
  width: 102px;
  height: 102px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: conic-gradient(#7fe5a8 ${({ $progress }) => `${$progress}%`}, rgba(127, 229, 168, 0.1) 0);
  position: relative;
  box-shadow: ${({ $active }) => $active ? '0 0 22px rgba(127, 229, 168, 0.2)' : 'none'};

  &::after {
    content: '';
    position: absolute;
    inset: 8px;
    border-radius: 50%;
    background: rgba(6, 12, 13, 0.94);
    border: 1px solid rgba(127, 229, 168, 0.12);
  }
  .value { position: relative; z-index: 1; color: #7fe5a8; font-size: 25px; font-weight: 800; }
  .value small { display: block; color: rgba(255, 255, 255, 0.46); font-size: 9px; text-align: center; font-weight: 500; }
`

const Detail = styled.div`
  min-width: 0;
  .status { color: #7fe5a8; font-size: 19px; font-weight: 750; }
  .message { margin: 3px 0 9px; color: rgba(255, 255, 255, 0.56); font-size: 11px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
`

const Metrics = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 12px;

  div { min-width: 0; }
  span { display: block; color: rgba(255, 255, 255, 0.42); font-size: 9px; }
  strong { display: block; color: rgba(255, 255, 255, 0.82); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
`

export default function Chart5({ drone }: { drone: DroneMetric }) {
  const active = ['connecting', 'ready', 'takeoff', 'enroute', 'patrolling', 'spraying', 'inspecting', 'returning'].includes(drone.status)
  return (
    <Wrapper>
      <ProgressRing $progress={drone.progress} $active={active}>
        <div className="value">{drone.progress}%<small>任务进度</small></div>
      </ProgressRing>
      <Detail>
        <div className="status">{drone.statusLabel}</div>
        <div className="message" title={drone.message}>{drone.message}</div>
        <Metrics>
          <div><span>当前航点</span><strong>{drone.waypoint} / {drone.waypointTotal || '--'}</strong></div>
          <div><span>飞行高度</span><strong>{drone.altitude}{drone.altitude === '--' ? '' : ' m'}</strong></div>
          <div><span>飞行速度</span><strong>{drone.speed}{drone.speed === '--' ? '' : ' m/s'}</strong></div>
          <div><span>喷洒速率</span><strong>{drone.sprayRate}</strong></div>
        </Metrics>
      </Detail>
    </Wrapper>
  )
}
