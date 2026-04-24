import { useEffect, useMemo, useState } from 'react'
import { Card, Empty, Select, Space, Statistic, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { fetchWorkflowHistory } from '../api/workflow'
import type { WorkflowHistoryEntry, WorkflowHistoryResponse } from '../types/workflow'

const { Title } = Typography

const statusColorMap: Record<string, string> = {
  completed: 'success',
  error: 'error',
  running: 'processing',
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
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadData()
    return () => {
      active = false
    }
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

  const columns: ColumnsType<WorkflowHistoryEntry> = [
    {
      title: '请求 ID',
      dataIndex: 'request_id',
      key: 'request_id',
      ellipsis: true,
      width: 180,
    },
    {
      title: '地块名称',
      key: 'field_name',
      render: (_, record) => {
        const field = record.field as Record<string, unknown>
        return String(field?.field_name ?? field?.field_id ?? '--')
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={statusColorMap[status] ?? 'default'}>{status}</Tag>
      ),
    },
    {
      title: '喷洒面积(亩)',
      key: 'spray_area_mu',
      width: 130,
      render: (_, record) => {
        const area = record.spray_summary?.spray_area_mu
        return typeof area === 'number' ? area.toFixed(2) : '--'
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (val: string | null | undefined) => (val ? new Date(val).toLocaleString('zh-CN') : '--'),
    },
  ]

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Title level={4} style={{ marginBottom: 24 }}>
        喷洒历史报表
      </Title>

      <Space size={24} style={{ marginBottom: 24 }} wrap>
        <Card>
          <Statistic title="总任务数" value={stats.total} />
        </Card>
        <Card>
          <Statistic title="总喷洒面积(亩)" value={stats.totalArea} precision={2} />
        </Card>
        <Card>
          <Statistic
            title="成功率"
            value={stats.successRate}
            suffix="%"
            valueStyle={{ color: stats.successRate >= 80 ? '#3f8600' : '#cf1322' }}
          />
        </Card>
      </Space>

      <Card
        title="任务列表"
        extra={
          <Select
            value={statusFilter}
            style={{ width: 140 }}
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
          <Typography.Text type="danger">{error}</Typography.Text>
        ) : !loading && data && data.items.length === 0 ? (
          <Empty description="暂无任务记录" />
        ) : (
          <Table<WorkflowHistoryEntry>
            rowKey="request_id"
            columns={columns}
            dataSource={data?.items ?? []}
            loading={loading}
            pagination={{ pageSize: 10 }}
            size="middle"
          />
        )}
      </Card>
    </div>
  )
}
