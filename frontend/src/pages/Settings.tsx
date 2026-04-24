import { useEffect, useState } from 'react'
import { Card, Form, Input, Switch, Typography, Descriptions, Tag, Space, message } from 'antd'

import { fetchDashboardContext } from '../api/workflow'
import type { DashboardContextResponse } from '../types/workflow'

const { Title } = Typography

const modeColor = (mode?: string): string => {
  if (!mode) return 'default'
  const m = mode.toLowerCase()
  if (m === 'online' || m === 'running') return 'success'
  if (m === 'offline' || m === 'stopped') return 'error'
  if (m === 'sim' || m === 'simulation') return 'warning'
  return 'default'
}

export default function Settings() {
  const [context, setContext] = useState<DashboardContextResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [messageApi, contextHolder] = message.useMessage()

  useEffect(() => {
    let active = true

    const loadContext = async () => {
      try {
        const result = await fetchDashboardContext()
        if (active) {
          setContext(result)
        }
      } catch {
        // silently ignore
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadContext()
    return () => {
      active = false
    }
  }, [])

  const handleSave = () => {
    messageApi.success('设置已保存（本地预览）')
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      {contextHolder}
      <Title level={4} style={{ marginBottom: 24 }}>
        系统设置
      </Title>

      <Card title="运行模式" loading={loading} style={{ marginBottom: 24 }}>
        {context ? (
          <Descriptions column={2} bordered size="middle">
            {Object.entries(context.modes).map(([key, value]) => (
              <Descriptions.Item key={key} label={key.toUpperCase()}>
                <Tag color={modeColor(value)}>{value}</Tag>
              </Descriptions.Item>
            ))}
          </Descriptions>
        ) : (
          <Typography.Text type="secondary">无法获取运行模式</Typography.Text>
        )}
      </Card>

      <Card title="应用配置">
        <Form layout="vertical" onFinish={handleSave}>
          <Form.Item label="后端 API 地址" name="apiBase" initialValue="/api">
            <Input placeholder="例如: http://localhost:8000/api" />
          </Form.Item>

          <Form.Item label="刷新间隔(ms)" name="refreshInterval" initialValue={2000}>
            <Input type="number" min={500} max={30000} step={500} />
          </Form.Item>

          <Form.Item label="启用 WebSocket" name="enableWebSocket" valuePropName="checked" initialValue>
            <Switch />
          </Form.Item>

          <Form.Item label="自动刷新" name="autoRefresh" valuePropName="checked" initialValue>
            <Switch />
          </Form.Item>

          <Space>
            <button type="submit" style={{ display: 'none' }} />
          </Space>
        </Form>
      </Card>
    </div>
  )
}
