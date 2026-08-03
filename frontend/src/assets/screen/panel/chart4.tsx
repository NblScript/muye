import styled from 'styled-components'
import type { DecisionMetric } from '../model'

const Wrapper = styled.div`
  height: 100%;
  display: grid;
  grid-template-rows: auto auto 1fr;
  gap: 10px;
`

const Hero = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;

  .eyebrow { color: rgba(90, 74, 66, 0.55); font-size: 11px; letter-spacing: 0.12em; }
  .pesticide { color: #d95711; font-size: 27px; font-weight: 800; line-height: 1.15; }
  .path { margin-top: 4px; color: #7b6d63; font-size: 11px; }
`

const Score = styled.div<{ $status: DecisionMetric['complianceStatus'] }>`
  width: 58px;
  height: 58px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 4px solid ${({ $status }) => $status === 'passed' ? '#67a777' : $status === 'blocked' ? '#bf5146' : '#d79a3c'};
  background: rgba(255, 255, 255, 0.58);
  color: #4d4038;
  font-weight: 800;
  font-size: 18px;

  small { display: block; margin-top: -7px; color: #8b7d72; font-size: 8px; font-weight: 500; }
`

const Specs = styled.div`
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 7px;
`

const Spec = styled.div`
  padding: 7px 6px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(234, 88, 12, 0.11);
  min-width: 0;
  text-align: center;

  span { display: block; color: rgba(90, 74, 66, 0.5); font-size: 9px; }
  strong { display: block; margin-top: 2px; color: #5a4a42; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
`

const Summary = styled.div<{ $status: DecisionMetric['complianceStatus'] }>`
  align-self: end;
  padding: 8px 10px;
  border-left: 3px solid ${({ $status }) => $status === 'passed' ? '#67a777' : $status === 'blocked' ? '#bf5146' : '#d79a3c'};
  background: rgba(255, 255, 255, 0.48);
  color: #695a50;
  font-size: 11px;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
`

export default function Chart4({ decision }: { decision: DecisionMetric }) {
  const confidenceText = decision.confidence > 0 ? `${Math.round(decision.confidence * 100)}%` : '--'
  return (
    <Wrapper>
      <Hero>
        <div>
          <div className="eyebrow">AI RECOMMENDATION</div>
          <div className="pesticide">{decision.pesticide}</div>
          <div className="path">{decision.decisionPath} · 可信度 {confidenceText}</div>
        </div>
        <Score $status={decision.complianceStatus}>
          <div>{decision.complianceScore || '--'}<small>合规评分</small></div>
        </Score>
      </Hero>
      <Specs>
        <Spec><span>浓度</span><strong>{decision.concentration}</strong></Spec>
        <Spec><span>稀释配比</span><strong>{decision.dilution}</strong></Spec>
        <Spec><span>计划总量</span><strong>{decision.total}</strong></Spec>
        <Spec><span>参会专家</span><strong>{decision.expertCount || '--'} 位</strong></Spec>
      </Specs>
      <Summary $status={decision.complianceStatus}>{decision.complianceSummary}</Summary>
    </Wrapper>
  )
}
