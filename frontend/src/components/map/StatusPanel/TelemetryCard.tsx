import type { DroneState } from '../../../types/simMap'

type TelemetryCardProps = {
  drone: DroneState
}

function formatNumber(value: number | null | undefined, digits = 1) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '--'
}

function formatCoordinate(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(6) : '--'
}

export default function TelemetryCard({ drone }: TelemetryCardProps) {
  const position = drone.position
  const telemetry = drone.telemetry
  const heading = telemetry.heading ?? position?.heading
  const speed = telemetry.speed ?? position?.speed

  return (
    <section className="status-panel-card">
      <div className="status-panel-card-header">
        <span>遥测</span>
      </div>
      <div className="status-panel-grid">
        <div>
          <span>高度</span>
          <strong>{formatNumber(position?.altitude)} m</strong>
        </div>
        <div>
          <span>速度</span>
          <strong>{formatNumber(speed)} m/s</strong>
        </div>
        <div>
          <span>航向</span>
          <strong>{formatNumber(heading, 0)} deg</strong>
        </div>
        <div>
          <span>爬升率</span>
          <strong>{formatNumber(telemetry.climb_rate)} m/s</strong>
        </div>
      </div>
      <div className="status-panel-coordinate">
        <span>{formatCoordinate(position?.latitude)}</span>
        <span>{formatCoordinate(position?.longitude)}</span>
      </div>
    </section>
  )
}
