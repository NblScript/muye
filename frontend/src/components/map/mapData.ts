import type { LatLngTuple } from 'leaflet'

export type FieldStatus = '作业中' | '待作业' | '已完成'

export type DroneStatus = '执行中' | '待命中' | '返航中'

export type FieldPlot = {
  id: string
  name: string
  crop: string
  areaMu: number
  status: FieldStatus
  center: LatLngTuple
  boundary: LatLngTuple[]
}

export type DroneRecord = {
  id: string
  name: string
  model: string
  status: DroneStatus
  battery: number
  speedKmh: number
  assignedField: string
  position: LatLngTuple
  trail: LatLngTuple[]
}

export const simulationBounds: [LatLngTuple, LatLngTuple] = [
  [0, 0],
  [100, 160],
]

export const mapCenter: LatLngTuple = [50, 80]
