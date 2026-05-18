import { useEffect, useMemo, useState } from 'react'

import { fetchWorkflowHistory } from '../api/workflow'
import { Card, Empty, Select, Tag } from '../components/ui'
import type { WorkflowHistoryEntry, WorkflowHistoryResponse } from '../types/workflow'

const statusColorMap: Record<string, 'green' | 'red' | 'amber' | 'default'> = {
  completed: 'green',
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

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 24, fontWeight: 600 }}>喷洒历史报表</h2>

      <div style={{ display: 'flex', gap: 24, marginBottom: 24, flexWrap: 'wrap' }}>
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
