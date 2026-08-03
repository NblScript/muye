import styled from 'styled-components'
import type { PipelineStageMetric } from '../model'

const List = styled.div`
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 5px;
`

const Row = styled.div<{ $status: PipelineStageMetric['status'] }>`
  min-height: 27px;
  display: grid;
  grid-template-columns: 10px 70px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  padding: 4px 7px;
  border-radius: 5px;
  background: ${({ $status }) => $status === 'active'
    ? 'rgba(234, 88, 12, 0.09)'
    : $status === 'error'
      ? 'rgba(191, 81, 70, 0.09)'
      : 'rgba(255, 255, 255, 0.42)'};

  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: ${({ $status }) => $status === 'done'
      ? '#4f8f63'
      : $status === 'active'
        ? '#ea580c'
        : $status === 'error'
          ? '#bf5146'
          : '#d6c9bc'};
    box-shadow: ${({ $status }) => $status === 'active' ? '0 0 10px rgba(234, 88, 12, 0.85)' : 'none'};
  }
  .name { color: #56483f; font-size: 12px; font-weight: 650; }
  .message { color: rgba(90, 74, 66, 0.58); font-size: 11px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
`

export default function Chart3({ stages }: { stages: PipelineStageMetric[] }) {
  return (
    <List>
      {stages.map((stage) => (
        <Row key={stage.key} $status={stage.status} title={stage.message}>
          <span className="dot" />
          <span className="name">{stage.label}</span>
          <span className="message">{stage.message}</span>
        </Row>
      ))}
    </List>
  )
}
