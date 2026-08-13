import styled from 'styled-components'
import type { PestMetric } from '../model'

const Empty = styled.div`
  height: 100%;
  display: grid;
  place-items: center;
  color: rgba(255, 255, 255, 0.48);
  font-size: 14px;
  letter-spacing: 0.08em;
`

const List = styled.div`
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
`

const Row = styled.div`
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr) 48px;
  align-items: center;
  gap: 11px;
  min-height: 31px;
`

const PestName = styled.span`
  overflow: hidden;
  color: rgba(255, 255, 255, 0.86);
  font-size: 14px;
  font-weight: 650;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
`

const Track = styled.div`
  position: relative;
  height: 9px;
  border-radius: 999px;
  background: rgba(127, 229, 168, 0.1);
`

const Fill = styled.div<{ $percent: number }>`
  position: absolute;
  inset: 0 auto 0 0;
  width: ${({ $percent }) => `${$percent}%`};
  min-width: 15px;
  border-radius: inherit;
  background: linear-gradient(90deg, #4f8a72 0%, #7fe5a8 100%);
  box-shadow: 0 0 9px rgba(127, 229, 168, 0.24);

  &::after {
    content: '';
    position: absolute;
    top: 50%;
    right: -6px;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(223, 255, 238, 0.92);
    border-radius: 50%;
    background: #7fe5a8;
    box-shadow: 0 0 10px rgba(127, 229, 168, 0.5);
    transform: translateY(-50%);
  }
`

const Count = styled.span`
  color: #7fe5a8;
  font-size: 13px;
  font-weight: 750;
  white-space: nowrap;
`

const Confidence = styled.span`
  grid-column: 2 / 4;
  margin-top: -10px;
  color: rgba(255, 255, 255, 0.42);
  font-size: 10px;
  letter-spacing: 0.02em;
`

export default function Chart1({ pests }: { pests: PestMetric[] }) {
  if (pests.length === 0) return <Empty>等待 YOLO 虫情识别</Empty>

  const data = pests.slice(0, 5)
  const maxCount = Math.max(1, ...data.map((item) => item.count))

  return (
    <List aria-label="昆虫识别统计">
      {data.map((pest) => {
        const confidence = Math.max(0, Math.min(1, pest.confidence))
        const percent = Math.max(4, (pest.count / maxCount) * 94)
        const detail = `${pest.name}，检测 ${pest.count} 只，平均置信度 ${(confidence * 100).toFixed(1)}%`
        return (
          <Row key={pest.name} aria-label={detail} title={detail}>
            <PestName>{pest.name}</PestName>
            <Track aria-hidden="true"><Fill $percent={percent} /></Track>
            <Count>{pest.count} 只</Count>
            <Confidence>平均置信度 {(confidence * 100).toFixed(1)}%</Confidence>
          </Row>
        )
      })}
    </List>
  )
}
