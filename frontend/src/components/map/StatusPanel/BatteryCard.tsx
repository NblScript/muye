import { Progress } from '../../ui'

import type { BatteryState } from '../../../types/simMap'

type BatteryCardProps = {
  battery: BatteryState
}

function formatNumber(value: number | null | undefined, digits = 1) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '--'
}

function normalizeBattery(value: number) {
  if (!Number.isFinite(value)) return 0
  return value <= 1 ? value * 100 : value
}

export default function BatteryCard({ battery }: BatteryCardProps) {
  const remaining = Math.max(0, Math.min(100, normalizeBattery(battery.remaining)))

  return (
    <section className="status-panel-card">
      <div className="status-panel-card-header">
        <span>电池</span>
        <strong>{remaining.toFixed(0)}%</strong>
      </div>
      <Progress
        percent={remaining}
        size="small"
        showInfo={false}
        strokeColor={remaining < 25 ? 'var(--accent-red)' : 'var(--accent-cyan)'}
      />
      <div className="status-panel-grid status-panel-grid-compact">
        <div>
          <span>电压</span>
          <strong>{formatNumber(battery.voltage)} V</strong>
        </div>
        <div>
          <span>电流</span>
          <strong>{formatNumber(battery.current)} A</strong>
        </div>
      </div>
    </section>
  )
}
