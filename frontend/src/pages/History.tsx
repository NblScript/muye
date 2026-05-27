import { useCallback, useEffect, useMemo, useState } from 'react'

import { fetchWorkflowHistory } from '../api/workflow'
import { Card, Empty, Select, Tag } from '../components/ui'
import type { WorkflowHistoryEntry, WorkflowHistoryResponse } from '../types/workflow'

const API_BASE = import.meta.env.VITE_API_URL || ''

const statusColorMap: Record<string, 'green' | 'red' | 'amber' | 'default'> = {
  completed: 'green',
  blocked: 'red',
  error: 'red',
  running: 'amber',
  pending: 'default',
}

export default function History() {
  const [data, setData] = useState<WorkflowHistoryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')

  useEffect(() => {
    let active = true

    const loadData = async () => {
      try {
        const result = await fetchWorkflowHistory({
          limit: 100,
          status: statusFilter === 'all' ? undefined : statusFilter,
        })
        if (active) {
          setData(result)
          setError(null)
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : '加载历史数据失败')
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void loadData()
    return () => { active = false }
  }, [statusFilter])

  const stats = useMemo(() => {
    if (!data) return { total: 0, totalArea: 0, successRate: 0 }
    const items = data.items
    const total = items.length
    const completed = items.filter((i) => i.status === 'completed').length
    const totalArea = items.reduce((sum, i) => {
      const area = i.spray_summary?.spray_area_mu
      return sum + (typeof area === 'number' ? area : 0)
    }, 0)
    const successRate = total > 0 ? Math.round((completed / total) * 100) : 0
    return { total, totalArea, successRate }
  }, [data])

  const openReport = useCallback((requestId: string) => {
    window.open(`${API_BASE}/api/tasks/${requestId}/report`, '_blank')
  }, [])

  // Daily trend data
  const trend = useMemo(() => {
    if (!data || data.items.length === 0) return null
    const byDay: Record<string, { total: number; completed: number }> = {}
    for (const item of data.items) {
      const ts = item.updated_at
      if (!ts) continue
      const day = new Date(ts).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
      if (!byDay[day]) byDay[day] = { total: 0, completed: 0 }
      byDay[day].total++
      if (item.status === 'completed') byDay[day].completed++
    }
    const entries = Object.entries(byDay).slice(-14)
    if (entries.length < 2) return null
    const maxTotal = Math.max(...entries.map(([, v]) => v.total), 1)
    return { entries, maxTotal }
  }, [data])

  const chartW = 480
  const chartH = 120
  const padX = 32
  const padY = 16
  const innerW = chartW - padX * 2
  const innerH = chartH - padY * 2

  return (
    <div className="page-container-lg">
      <h2 className="page-title">喷洒历史报表</h2>

      <div className="history-stats-row">
        <Card className="history-stat-card">
          <div className="history-stat-label">总任务数</div>
          <div className="history-stat-value">{stats.total}</div>
        </Card>
        <Card className="history-stat-card">
          <div className="history-stat-label">总喷洒面积(亩)</div>
          <div className="history-stat-value">{stats.totalArea.toFixed(2)}</div>
        </Card>
        <Card className="history-stat-card">
          <div className="history-stat-label">成功率</div>
          <div className={`history-stat-value ${stats.successRate >= 80 ? 'color-success' : 'color-error'}`}>
            {stats.successRate}%
          </div>
        </Card>
      </div>

      {trend && (
        <Card title="任务趋势" className="history-trend-card">
          <svg width="100%" height={chartH} viewBox={`0 0 ${chartW} ${chartH}`}>
            {/* Y-axis line */}
            <line x1={padX} y1={padY} x2={padX} y2={chartH - padY} stroke="var(--border-default)" strokeWidth="0.5" />
            <line x1={padX} y1={chartH - padY} x2={chartW - padX} y2={chartH - padY} stroke="var(--border-default)" strokeWidth="0.5" />

            {/* Total tasks polyline */}
            <polyline
              fill="none"
              stroke="var(--accent-amber)"
              strokeWidth="1.5"
              strokeLinejoin="round"
              points={trend.entries.map(([, v], i) => {
                const x = padX + (i / Math.max(trend.entries.length - 1, 1)) * innerW
                const y = chartH - padY - (v.total / trend.maxTotal) * innerH
                return `${x},${y}`
              }).join(' ')}
            />

            {/* Completed tasks polyline */}
            <polyline
              fill="none"
              stroke="var(--accent-green)"
              strokeWidth="1.5"
              strokeLinejoin="round"
              strokeDasharray="3 2"
              points={trend.entries.map(([, v], i) => {
                const x = padX + (i / Math.max(trend.entries.length - 1, 1)) * innerW
                const y = chartH - padY - (v.completed / trend.maxTotal) * innerH
                return `${x},${y}`
              }).join(' ')}
            />

            {/* X labels */}
            {trend.entries.map(([day], i) => {
              if (i % Math.ceil(trend.entries.length / 7) !== 0 && i !== trend.entries.length - 1) return null
              const x = padX + (i / Math.max(trend.entries.length - 1, 1)) * innerW
              return (
                <text key={day} x={x} y={chartH - 2} textAnchor="middle" fontSize="8" fill="var(--text-muted)">
                  {day}
                </text>
              )
            })}

            {/* Legend */}
            <line x1={padX + 4} y1={padY + 4} x2={padX + 20} y2={padY + 4} stroke="var(--accent-amber)" strokeWidth="1.5" />
            <text x={padX + 24} y={padY + 7} fontSize="8" fill="var(--text-secondary)">总任务</text>
            <line x1={padX + 60} y1={padY + 4} x2={padX + 76} y2={padY + 4} stroke="var(--accent-green)" strokeWidth="1.5" strokeDasharray="3 2" />
            <text x={padX + 80} y={padY + 7} fontSize="8" fill="var(--text-secondary)">已完成</text>
          </svg>
        </Card>
      )}

      <Card
        title="任务列表"
        extra={
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { label: '全部状态', value: 'all' },
              { label: '运行中', value: 'running' },
              { label: '已完成', value: 'completed' },
              { label: '已拦截', value: 'blocked' },
              { label: '异常', value: 'error' },
            ]}
          />
        }
      >
        {error ? (
          <div className="color-error">{error}</div>
        ) : !loading && data && data.items.length === 0 ? (
          <Empty description="暂无任务记录" />
        ) : (
          <div className="history-table-wrap">
            <table className="history-table">
              <thead>
                <tr>
                  <th>请求 ID</th>
                  <th>地块名称</th>
                  <th>状态</th>
                  <th>喷洒面积(亩)</th>
                  <th>更新时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((item: WorkflowHistoryEntry) => {
                  const field = item.field as Record<string, unknown>
                  const area = item.spray_summary?.spray_area_mu
                  return (
                    <tr key={item.request_id}>
                      <td className="history-td-id">{item.request_id}</td>
                      <td>{String(field?.field_name ?? field?.field_id ?? '--')}</td>
                      <td>
                        <Tag color={statusColorMap[item.status] ?? 'default'}>{item.status}</Tag>
                      </td>
                      <td className="mono">{typeof area === 'number' ? area.toFixed(2) : '--'}</td>
                      <td>{item.updated_at ? new Date(item.updated_at).toLocaleString('zh-CN') : '--'}</td>
                      <td>
                        <button
                          type="button"
                          className="btn-report"
                          onClick={() => { openReport(item.request_id) }}
                        >
                          报告
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
