import type { WsEnhancedState } from '../../../types/simMap'
import BatteryCard from './BatteryCard'
import ControlActions from './ControlActions'
import DroneStatusCard from './DroneStatusCard'
import ProgressCard from './ProgressCard'
import TelemetryCard from './TelemetryCard'

type StatusPanelProps = {
  state: WsEnhancedState
}

export default function StatusPanel({ state }: StatusPanelProps) {
  return (
    <aside className="status-panel" aria-label="无人机实时状态">
      <DroneStatusCard drone={state.drone} />
      <TelemetryCard drone={state.drone} />
      <ProgressCard mission={state.mission} trajectory={state.trajectory} />
      <BatteryCard battery={state.drone.battery} />
      <ControlActions />
    </aside>
  )
}
