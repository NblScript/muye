import styled from 'styled-components'
import type { EvaluationMetric } from '../model'

const Wrapper = styled.div`
  height: 100%;
  display: grid;
  grid-template-columns: 105px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
`

const KillRate = styled.div<{ $passed: boolean }>`
  text-align: center;
  .number { color: ${({ $passed }) => $passed ? '#7fe5a8' : '#d6b56f'}; font-size: 35px; font-weight: 850; line-height: 1; }
  .label { margin-top: 6px; color: rgba(255, 255, 255, 0.5); font-size: 10px; letter-spacing: 0.12em; }
`

const Detail = styled.div`
  min-width: 0;
  .status { color: rgba(255, 255, 255, 0.84); font-size: 15px; font-weight: 700; }
  .verdict { margin-top: 3px; color: rgba(255, 255, 255, 0.52); font-size: 10px; line-height: 1.45; }
`

const Track = styled.div`
  margin: 10px 0 8px;
  height: 7px;
  border-radius: 999px;
  background: rgba(127, 229, 168, 0.09);
  position: relative;
  overflow: hidden;
  .fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, #4f8a72, #7fe5a8); }
  .threshold { position: absolute; top: -2px; bottom: -2px; width: 2px; background: #d6b56f; }
`

const Stats = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  div { padding: 5px 6px; border-radius: 5px; background: rgba(255,255,255,0.04); text-align: center; }
  span { display: block; color: rgba(255,255,255,0.4); font-size: 8px; }
  strong { display: block; color: rgba(255,255,255,0.82); font-size: 12px; }
`

export default function Chart6({ evaluation }: { evaluation: EvaluationMetric }) {
  const passed = evaluation.killRate >= evaluation.threshold && evaluation.killRate > 0
  const percent = Math.round(evaluation.killRate * 100)
  const thresholdPercent = Math.round(evaluation.threshold * 100)
  return (
    <Wrapper>
      <KillRate $passed={passed}>
        <div className="number">{evaluation.killRate > 0 ? `${percent}%` : '--'}</div>
        <div className="label">PEST KILL RATE</div>
      </KillRate>
      <Detail>
        <div className="status">{evaluation.statusLabel}</div>
        <div className="verdict">{evaluation.verdict}</div>
        <Track title={`目标阈值 ${thresholdPercent}%`}>
          <div className="fill" style={{ width: `${percent}%` }} />
          <div className="threshold" style={{ left: `${thresholdPercent}%` }} />
        </Track>
        <Stats>
          <div><span>喷洒前</span><strong>{evaluation.beforeCount ?? '--'} 只</strong></div>
          <div><span>复检后</span><strong>{evaluation.afterCount ?? '--'} 只</strong></div>
          <div><span>闭环轮次</span><strong>{evaluation.currentIteration || '--'} / {evaluation.maxIterations || '--'}</strong></div>
        </Stats>
      </Detail>
    </Wrapper>
  )
}
