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
    ? 'rgba(127, 229, 168, 0.1)'
    : $status === 'error'
      ? 'rgba(191, 81, 70, 0.09)'
      : 'rgba(255, 255, 255, 0.035)'};

  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: ${({ $status }) => $status === 'done'
      ? '#7fe5a8'
      : $status === 'active'
        ? '#7fe5a8'
        : $status === 'error'
          ? '#bf5146'
          : '#6f7776'};
    box-shadow: ${({ $status }) => $status === 'active' ? '0 0 10px rgba(127, 229, 168, 0.72)' : 'none'};
  }
  .name { color: rgba(255, 255, 255, 0.84); font-size: 12px; font-weight: 650; }
  .message { color: rgba(255, 255, 255, 0.5); font-size: 11px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
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
