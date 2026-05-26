export type HealthResponse = {
  status: string
  checks?: Record<string, HealthCheck>
  failures?: string[]
  [key: string]: unknown
}

export type HealthCheck = {
  status: string
  detail?: string
  path?: string
  [key: string]: unknown
}
