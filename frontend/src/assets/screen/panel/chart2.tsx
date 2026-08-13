import styled from 'styled-components'
import type { PanelTone, WeatherMetric } from '../model'

const Grid = styled.div`
  height: 100%;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 10px;
`

const toneColor: Record<PanelTone, string> = {
  green: '#7fe5a8', amber: '#d6b56f', red: '#df7469', blue: '#78a8c5', muted: '#8c9695',
}

const Metric = styled.div<{ $tone: PanelTone }>`
  min-width: 0;
  padding: 12px 13px;
  border-radius: 8px;
  border: 1px solid ${({ $tone }) => `${toneColor[$tone]}35`};
  background: ${({ $tone }) => `${toneColor[$tone]}0d`};
  display: flex;
  flex-direction: column;
  justify-content: space-between;

  .label { color: rgba(255, 255, 255, 0.62); font-size: 12px; }
  .value { color: ${({ $tone }) => toneColor[$tone]}; font-size: 25px; font-weight: 750; line-height: 1.1; }
  .value.is-text { font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .unit { margin-left: 4px; color: rgba(255, 255, 255, 0.48); font-size: 11px; font-weight: 500; }
`

const Suitability = styled.div<{ $ok: boolean }>`
  position: absolute;
  top: 15px;
  right: 14px;
  padding: 3px 8px;
  border-radius: 999px;
  color: ${({ $ok }) => $ok ? '#7fe5a8' : '#d6b56f'};
  background: ${({ $ok }) => $ok ? 'rgba(127, 229, 168, 0.1)' : 'rgba(214, 181, 111, 0.12)'};
  font-size: 10px;
  letter-spacing: 0.08em;
`

export default function Chart2({ metrics, ready, suitable }: { metrics: WeatherMetric[]; ready: boolean; suitable: boolean }) {
  return (
    <>
      <Suitability $ok={suitable}>{!ready ? '等待数据' : suitable ? '适宜施药' : '气象风险'}</Suitability>
      <Grid>
        {metrics.map((item, index) => (
          <Metric key={item.label} $tone={item.tone}>
            <span className="label">{item.label}</span>
            <span className={`value ${index === 0 ? 'is-text' : ''}`} title={item.value}>
              {item.value}<span className="unit">{item.unit}</span>
            </span>
          </Metric>
        ))}
      </Grid>
    </>
  )
}
