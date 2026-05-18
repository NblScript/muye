import FieldMap from '../components/map/FieldMap'
import { useEnhancedMapState } from '../hooks/useEnhancedMapState'
import '../styles/px4-viewer.css'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function formatMetric(value: number | undefined, suffix: string) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--'
  }
  return `${value.toFixed(1)}${suffix}`
}

export default function Px4Viewer() {
  const { data, status, error } = useEnhancedMapState()
  const workflow = asRecord(data?.workflow_state)
  const latestTask = asRecord(workflow.latest_task)
  const drone = asRecord(latestTask.drone)
  const field = asRecord(latestTask.field)
  const telemetry = data?.drone
  const battery = telemetry?.battery
  const position = telemetry?.position

  return (
    <div className="px4-viewer-shell">
      <section className="px4-viewer-hero glass-card">
        <div className="px4-viewer-hero-top">
          <div>
            <span className="label-uppercase">PX4 观察页</span>
            <h1>固定航线演示观察</h1>
            <p>
              只显示当前麦田、无人机路径和实时飞行状态，用来替代不稳定的 Gazebo 本地窗口。
            </p>
          </div>
          <div className="px4-viewer-connection">
            <span className={`viewer-status viewer-status-${status}`}>{status}</span>
            {error ? <small>{error}</small> : null}
          </div>
        </div>

        <div className="px4-viewer-metrics">
          <div className="px4-viewer-metric">
            <span>当前状态</span>
            <strong>{String(drone.status ?? latestTask.status ?? '--')}</strong>
          </div>
          <div className="px4-viewer-metric">
            <span>任务进度</span>
            <strong>{Number(drone.progress ?? 0)}%</strong>
          </div>
          <div className="px4-viewer-metric">
            <span>飞行高度</span>
            <strong>{formatMetric(position?.altitude, ' m')}</strong>
          </div>
          <div className="px4-viewer-metric">
            <span>飞行速度</span>
            <strong>{formatMetric(telemetry?.telemetry?.speed, ' m/s')}</strong>
          </div>
          <div className="px4-viewer-metric">
            <span>电量</span>
            <strong>{formatMetric(battery?.remaining, '%')}</strong>
          </div>
          <div className="px4-viewer-metric">
            <span>地块</span>
            <strong>{String(field.field_name ?? field.field_id ?? '--')}</strong>
          </div>
        </div>
      </section>

      <section className="px4-viewer-map glass-card">
        <div className="px4-viewer-map-header">
          <div>
            <span className="label-uppercase">动画场景</span>
            <h2>麦田与无人机轨迹</h2>
          </div>
          <div className="px4-viewer-map-meta">
            <span>任务号：{String(latestTask.request_id ?? '--').slice(0, 12)}</span>
            <span>航点：{Number(drone.current_waypoint_index ?? 0)}</span>
          </div>
        </div>
        <div className="px4-viewer-map-stage">
          <FieldMap droneStatus={String(drone.status ?? '')} />
        </div>
      </section>
    </div>
  )
}
