import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Card, Empty, Input, Layout, List, Select, Space, Tag, Typography, message } from 'antd'

import {
  buildTaskAnnotatedImageUrl,
  buildTaskOriginalImageUrl,
  fetchDashboardContext,
  fetchWorkflowHistory,
  fetchWorkflowState,
  resetDemoEvents,
  uploadDemoImage,
} from '../api/workflow'
import FieldMap from '../components/map/FieldMap'
import WorkflowPanel from '../components/workflow/WorkflowPanel'
import type {
  DashboardContextResponse,
  DashboardTaskEntry,
  WorkflowDetectionEntry,
  WorkflowHistoryResponse,
  WorkflowStateResponse,
} from '../types/workflow'
import '../styles/dashboard.css'

const { Header, Content } = Layout
const { Title, Text } = Typography

type TaskRecord = {
  id: string
  droneName: string
  fieldName: string
  status: '执行中' | '待起飞' | '返航中'
  progress: number
  pesticideName: string
  sprayAreaText: string
  updatedAt: string
  isCurrent: boolean
}

type PestSummary = {
  labels: string[]
  summary: string
}

function toTaskStatus(status: string): TaskRecord['status'] {
  if (status === 'spraying' || status === '作业中') {
    return '执行中'
  }
  if (status === 'returning' || status === '返航') {
    return '返航中'
  }
  return '待起飞'
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return '--'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function formatNow(value: Date) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(value)
}

function mapTaskEntry(item: DashboardTaskEntry): TaskRecord {
  return {
    id: item.request_id,
    droneName: item.drone_label,
    fieldName: item.field_name,
    status: toTaskStatus(item.status),
    progress: Number(item.progress ?? 0),
    pesticideName: item.pesticide_name ?? '--',
    sprayAreaText: item.spray_area_mu !== null && item.spray_area_mu !== undefined ? `${item.spray_area_mu} 亩` : '--',
    updatedAt: formatDateTime(item.updated_at),
    isCurrent: item.is_current,
  }
}

function statusColor(status: TaskRecord['status']) {
  if (status === '执行中') {
    return 'green'
  }
  if (status === '返航中') {
    return 'gold'
  }
  return 'blue'
}

function summarizePests(detections: WorkflowDetectionEntry[]): PestSummary {
  if (detections.length === 0) {
    return {
      labels: [],
      summary: '未识别到害虫目标',
    }
  }

  const counts = new Map<string, number>()
  for (const detection of detections) {
    const pestType = String(detection.pest_type ?? 'unknown')
    counts.set(pestType, (counts.get(pestType) ?? 0) + 1)
  }

  const ordered = [...counts.entries()].sort((left, right) => {
    if (right[1] !== left[1]) {
      return right[1] - left[1]
    }
    return left[0].localeCompare(right[0], 'zh-CN')
  })

  const labels = ordered.map(([name, count]) => `${name} × ${count}`)
  return {
    labels,
    summary: labels.join('，'),
  }
}

function modeColor(value?: string) {
  if (value === 'mock') {
    return 'gold'
  }
  if (value === 'px4') {
    return 'cyan'
  }
  if (value === 'virtual_api') {
    return 'geekblue'
  }
  if (value === 'simulated') {
    return 'purple'
  }
  return 'green'
}

function safeMetric(value: unknown, suffix = '') {
  if (value === null || value === undefined || value === '') {
    return '--'
  }
  return `${String(value)}${suffix}`
}

export default function Dashboard() {
  const [messageApi, messageContextHolder] = message.useMessage()
  const [now, setNow] = useState(() => new Date())
  const [workflow, setWorkflow] = useState<WorkflowStateResponse | null>(null)
  const [workflowLoading, setWorkflowLoading] = useState(true)
  const [workflowError, setWorkflowError] = useState<string | null>(null)
  const [context, setContext] = useState<DashboardContextResponse | null>(null)
  const [history, setHistory] = useState<WorkflowHistoryResponse | null>(null)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyStatus, setHistoryStatus] = useState('all')
  const [historySearch, setHistorySearch] = useState('')
  const [historyLimit, setHistoryLimit] = useState(12)
  const [uploading, setUploading] = useState(false)
  const [resetting, setResetting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(new Date())
    }, 1000)

    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    let active = true

    const loadWorkflow = async () => {
      try {
        const next = await fetchWorkflowState()
        if (!active) {
          return
        }
        setWorkflow(next)
        setWorkflowError(null)
      } catch (error) {
        if (!active) {
          return
        }
        setWorkflowError(error instanceof Error ? error.message : '加载工作流失败')
      } finally {
        if (active) {
          setWorkflowLoading(false)
        }
      }
    }

    const loadContext = async () => {
      try {
        const next = await fetchDashboardContext()
        if (active) {
          setContext(next)
        }
      } catch (error) {
        if (active) {
          console.error('Failed to load dashboard context', error)
        }
      }
    }

    void loadWorkflow()
    void loadContext()
    const timer = window.setInterval(() => {
      void loadWorkflow()
    }, 500)

    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    let active = true

    const loadHistory = async () => {
      try {
        const next = await fetchWorkflowHistory({
          limit: historyLimit,
          status: historyStatus,
          search: historySearch.trim() || undefined,
        })
        if (!active) {
          return
        }
        setHistory(next)
        setHistoryError(null)
      } catch (error) {
        if (!active) {
          return
        }
        setHistoryError(error instanceof Error ? error.message : '加载任务历史失败')
      } finally {
        if (active) {
          setHistoryLoading(false)
        }
      }
    }

    void loadHistory()
    return () => {
      active = false
    }
  }, [historyLimit, historyStatus, historySearch])

  const latestTask = workflow?.latest_task ?? null
  const field = asRecord(latestTask?.field)
  const spraySummary = asRecord(latestTask?.spray_summary)
  const decision = asRecord(latestTask?.decision)
  const medication = asRecord(decision['用药'])
  const weather = asRecord(latestTask?.weather)
  const agronomyTips = Array.isArray(decision['农事建议']) ? (decision['农事建议'] as string[]) : []
  const safetyTips = Array.isArray(medication['安全提示']) ? (medication['安全提示'] as string[]) : []
  const detections = latestTask?.detections ?? []
  const pestSummary = useMemo(() => summarizePests(detections), [detections])
  const currentArea = spraySummary['spray_area_mu'] ?? field['area_mu'] ?? '--'
  const currentAreaDisplay = typeof currentArea === 'number' || typeof currentArea === 'string' ? String(currentArea) : '--'
  const onlineDevices = latestTask?.drone?.task_id ? 1 : 0
  const recentTasks = (workflow?.recent_tasks ?? []).map(mapTaskEntry)
  const originalImageUrl = latestTask ? `${buildTaskOriginalImageUrl(latestTask.request_id)}?t=${encodeURIComponent(latestTask.updated_at ?? '')}` : null
  const annotatedImageUrl = latestTask ? `${buildTaskAnnotatedImageUrl(latestTask.request_id)}?t=${encodeURIComponent(latestTask.updated_at ?? '')}` : null
  const combinedStatusError = workflowError ?? historyError

  const refreshHistory = async () => {
    setHistoryLoading(true)
    try {
      const next = await fetchWorkflowHistory({
        limit: historyLimit,
        status: historyStatus,
        search: historySearch.trim() || undefined,
      })
      setHistory(next)
      setHistoryError(null)
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : '刷新任务历史失败')
    } finally {
      setHistoryLoading(false)
    }
  }

  const refreshWorkflow = async () => {
    setWorkflowLoading(true)
    try {
      const next = await fetchWorkflowState()
      setWorkflow(next)
      setWorkflowError(null)
    } catch (error) {
      setWorkflowError(error instanceof Error ? error.message : '刷新工作流失败')
    } finally {
      setWorkflowLoading(false)
    }
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleUploadChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    setUploading(true)
    try {
      await uploadDemoImage(file)
      messageApi.success(`图片已发送：${file.name}`)
      void refreshWorkflow()
      void refreshHistory()
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '图片上传失败')
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  const handleResetEvents = async () => {
    setResetting(true)
    try {
      await resetDemoEvents()
      messageApi.success('演示事件已清空')
      void refreshWorkflow()
      void refreshHistory()
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '清空事件失败')
    } finally {
      setResetting(false)
    }
  }

  return (
    <Layout className="dashboard-shell">
      {messageContextHolder}
      <Header className="dashboard-header">
        <div>
          <Text className="dashboard-kicker">MUYE SMART AGRI COMMAND</Text>
          <Title className="dashboard-title" level={1}>
            牧野智农 · 智慧农业指挥中心
          </Title>
        </div>
        <div className="dashboard-clock">
          <Text className="clock-label">当前时间</Text>
          <Text className="clock-value">{formatNow(now)}</Text>
        </div>
      </Header>

      <Content className="dashboard-content">
        <section className="dashboard-command-strip">
          <Card bordered={false} className="dashboard-card command-card">
            <div className="command-strip-topline">
              <div>
                <Text className="panel-label">运行模式</Text>
                <div className="command-strip-title">统一后的 React 指挥台已承接旧版演示功能</div>
              </div>
              <Space wrap>
                <Tag color={modeColor(context?.modes.yolo)}>YOLO {context?.modes.yolo ?? '--'}</Tag>
                <Tag color={modeColor(context?.modes.weather)}>天气 {context?.modes.weather ?? '--'}</Tag>
                <Tag color={modeColor(context?.modes.qwen)}>千问 {context?.modes.qwen ?? '--'}</Tag>
                <Tag color={modeColor(context?.modes.drone)}>无人机 {context?.modes.drone ?? '--'}</Tag>
              </Space>
            </div>

            <div className="command-strip-actions">
              <div className="command-action-group">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".jpg,.jpeg,.png"
                  className="upload-input"
                  onChange={handleUploadChange}
                />
                <Button type="primary" onClick={handleUploadClick} loading={uploading}>
                  上传农田图片
                </Button>
                <Button onClick={() => void refreshWorkflow()} loading={workflowLoading}>
                  刷新主视图
                </Button>
                <Button danger onClick={handleResetEvents} loading={resetting}>
                  清空演示事件
                </Button>
              </div>

              <div className="command-strip-meta">
                <div className="command-meta-item">
                  <span>当前请求</span>
                  <strong>{latestTask?.request_id.slice(0, 12) ?? '--'}</strong>
                </div>
                <div className="command-meta-item">
                  <span>当前阶段</span>
                  <strong>{latestTask?.current_stage ?? '--'}</strong>
                </div>
                <div className="command-meta-item">
                  <span>任务状态</span>
                  <strong>{latestTask?.status ?? '--'}</strong>
                </div>
                <div className="command-meta-item">
                  <span>总事件数</span>
                  <strong>{workflow?.event_count ?? '--'}</strong>
                </div>
              </div>
            </div>
          </Card>
        </section>

        {combinedStatusError ? (
          <Alert
            type="warning"
            showIcon
            message="部分实时数据暂不可用"
            description={combinedStatusError}
            className="dashboard-alert"
          />
        ) : null}

        <section className="dashboard-grid">
          <aside className="dashboard-column dashboard-column-left">
            <Card bordered={false} className="dashboard-card stat-card">
              <Text className="panel-label">当前作业面积</Text>
              <div className="stat-value">{currentAreaDisplay}</div>
              <Text className="stat-unit">亩</Text>
              <div className="stat-footnote">
                数据来源：{spraySummary['spray_area_mu'] ? '喷洒记录' : field['area_mu'] ? '地块档案' : '暂无结构化面积'}
              </div>
            </Card>

            <Card bordered={false} className="dashboard-card stat-card">
              <Text className="panel-label">在线设备数</Text>
              <div className="stat-value">{onlineDevices}</div>
              <Text className="stat-unit">台</Text>
              <div className="stat-footnote">数据来源：当前任务中的 PX4 / 作业无人机</div>
            </Card>

            <Card bordered={false} className="dashboard-card suggestion-card">
              <Text className="panel-label">千问建议</Text>
              <div className="suggestion-main">{String(medication['农药名称'] ?? '暂无建议')}</div>
              <div className="suggestion-meta">
                配比：{String(medication['配比'] ?? '--')} / 总量：{String(medication['总量'] ?? '--')}
              </div>
              <div className="suggestion-list">
                {agronomyTips.length > 0 ? (
                  agronomyTips.slice(0, 3).map((tip, index) => (
                    <div key={`${tip}-${index}`} className="suggestion-item">
                      {tip}
                    </div>
                  ))
                ) : (
                  <div className="suggestion-empty">当前任务暂无千问农事建议</div>
                )}
              </div>
            </Card>
          </aside>

          <main className="dashboard-column dashboard-column-center">
            <Card bordered={false} className="dashboard-card map-card">
              <div className="map-panel">
                <div className="map-header-strip">
                  <Text className="panel-label">作业地图总览</Text>
                  <Text className="map-header-note">PX4 SITL / Virtual Field / React Leaflet</Text>
                </div>
                <FieldMap latestTask={latestTask} />
              </div>
            </Card>
          </main>

          <aside className="dashboard-column dashboard-column-right">
            <Card bordered={false} className="dashboard-card task-card" title="当前任务 / 最近任务">
              <List
                itemLayout="vertical"
                locale={{ emptyText: '当前没有可展示的任务队列' }}
                dataSource={recentTasks}
                renderItem={(item) => (
                  <List.Item className="task-item">
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      <div className="task-topline">
                        <Text className="task-id">{item.id}</Text>
                        <div className="task-tag-group">
                          {item.isCurrent ? <Tag color="cyan">当前</Tag> : null}
                          <Tag color={statusColor(item.status)}>{item.status}</Tag>
                        </div>
                      </div>

                      <div className="task-name">{item.droneName}</div>
                      <div className="task-field">{item.fieldName}</div>

                      <div className="task-meta">
                        <Text className="task-meta-text">农药：{item.pesticideName}</Text>
                        <Text className="task-meta-text">进度：{item.progress}%</Text>
                      </div>

                      <div className="task-meta">
                        <Text className="task-meta-text">面积：{item.sprayAreaText}</Text>
                        <Text className="task-meta-text">更新：{item.updatedAt}</Text>
                      </div>

                      <div className="task-progress-track">
                        <div className="task-progress-bar" style={{ width: `${item.progress}%` }} />
                      </div>
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          </aside>
        </section>

        <section className="dashboard-detail-grid">
          <Card bordered={false} className="dashboard-card image-card">
            <div className="detail-card-header">
              <Text className="panel-label">原始图片</Text>
              <Text className="detail-card-meta">{latestTask?.image_path ?? '等待图片输入'}</Text>
            </div>
            {originalImageUrl && latestTask?.image_path ? (
              <img src={originalImageUrl} alt="原始图片" className="detail-image" />
            ) : (
              <div className="detail-empty">请上传一张图片，或等待后端捕获图片。</div>
            )}
          </Card>

          <Card bordered={false} className="dashboard-card image-card">
            <div className="detail-card-header">
              <Text className="panel-label">YOLO 识别结果</Text>
              <Text className="detail-card-meta">目标数 {detections.length}</Text>
            </div>
            {annotatedImageUrl && latestTask?.image_path ? (
              <img src={annotatedImageUrl} alt="识别结果" className="detail-image" />
            ) : (
              <div className="detail-empty">等待识别结果。</div>
            )}
          </Card>

          <Card bordered={false} className="dashboard-card detail-card">
            <div className="detail-card-header">
              <Text className="panel-label">害虫识别摘要</Text>
              <Text className="detail-card-meta">
                种类 {pestSummary.labels.length} / 目标 {detections.length}
              </Text>
            </div>
            <div className="pest-summary-main">{pestSummary.summary}</div>
            <div className="pill-wrap">
              {pestSummary.labels.length > 0 ? (
                pestSummary.labels.map((label) => (
                  <span key={label} className="detail-pill is-success">
                    {label}
                  </span>
                ))
              ) : (
                <span className="detail-pill is-muted">等待 YOLO 返回害虫名称</span>
              )}
            </div>
          </Card>

          <Card bordered={false} className="dashboard-card detail-card">
            <div className="detail-card-header">
              <Text className="panel-label">天气信息</Text>
              <Text className="detail-card-meta">{String(weather.summary ?? '等待天气数据')}</Text>
            </div>
            <div className="detail-metric-grid">
              <div className="detail-metric-card">
                <span>温度</span>
                <strong>{safeMetric(weather.temperature, ' ℃')}</strong>
              </div>
              <div className="detail-metric-card">
                <span>湿度</span>
                <strong>{safeMetric(weather.humidity, ' %')}</strong>
              </div>
              <div className="detail-metric-card">
                <span>风向</span>
                <strong>{safeMetric(weather.wind_direction)}</strong>
              </div>
              <div className="detail-metric-card">
                <span>风力</span>
                <strong>{safeMetric(weather.wind_scale_text)}</strong>
              </div>
              <div className="detail-metric-card">
                <span>风速</span>
                <strong>{safeMetric(weather.wind_speed, ' m/s')}</strong>
              </div>
            </div>
          </Card>

          <Card bordered={false} className="dashboard-card detail-card detail-card-wide">
            <div className="detail-card-header">
              <Text className="panel-label">决策与执行参数</Text>
              <Text className="detail-card-meta">{latestTask?.error ? `异常：${latestTask.error}` : '系统规划参数'}</Text>
            </div>
            <div className="detail-metric-grid">
              <div className="detail-metric-card">
                <span>农药名称</span>
                <strong>{safeMetric(medication['农药名称'])}</strong>
              </div>
              <div className="detail-metric-card">
                <span>浓度</span>
                <strong>{safeMetric(medication['浓度'])}</strong>
              </div>
              <div className="detail-metric-card">
                <span>配比</span>
                <strong>{safeMetric(medication['配比'])}</strong>
              </div>
              <div className="detail-metric-card">
                <span>总量</span>
                <strong>{safeMetric(medication['总量'])}</strong>
              </div>
              <div className="detail-metric-card">
                <span>飞行高度</span>
                <strong>{safeMetric(asRecord(latestTask?.drone?.instruction)['高度'], ' m')}</strong>
              </div>
              <div className="detail-metric-card">
                <span>喷洒速率</span>
                <strong>{safeMetric(asRecord(latestTask?.drone?.instruction)['喷洒速率'])}</strong>
              </div>
            </div>

            <div className="detail-subsection">
              <Text className="panel-label">安全提示</Text>
              <div className="pill-wrap">
                {safetyTips.length > 0 ? (
                  safetyTips.map((item) => (
                    <span key={item} className="detail-pill is-warning">
                      {item}
                    </span>
                  ))
                ) : (
                  <span className="detail-pill is-muted">暂无安全提示</span>
                )}
              </div>
            </div>

            <div className="detail-subsection">
              <Text className="panel-label">农事建议</Text>
              <div className="pill-wrap">
                {agronomyTips.length > 0 ? (
                  agronomyTips.map((item) => (
                    <span key={item} className="detail-pill is-info">
                      {item}
                    </span>
                  ))
                ) : (
                  <span className="detail-pill is-muted">暂无农事建议</span>
                )}
              </div>
            </div>
          </Card>
        </section>

        <section className="dashboard-workflow-row">
          <Card bordered={false} className="dashboard-card workflow-card">
            <WorkflowPanel data={workflow} loading={workflowLoading} error={workflowError} />
          </Card>
        </section>

        <section className="dashboard-history-row">
          <Card bordered={false} className="dashboard-card history-card" title="任务历史检索">
            <div className="history-toolbar">
              <Select
                value={historyStatus}
                style={{ width: 160 }}
                onChange={setHistoryStatus}
                options={[
                  { label: '全部状态', value: 'all' },
                  { label: '运行中', value: 'running' },
                  { label: '已完成', value: 'completed' },
                  { label: '异常', value: 'error' },
                ]}
              />
              <Input
                value={historySearch}
                onChange={(event) => setHistorySearch(event.target.value)}
                placeholder="request_id / 图片路径 / 害虫类型"
                className="history-search"
              />
              <Select
                value={historyLimit}
                style={{ width: 120 }}
                onChange={setHistoryLimit}
                options={[
                  { label: '12 条', value: 12 },
                  { label: '24 条', value: 24 },
                  { label: '40 条', value: 40 },
                ]}
              />
              <Button onClick={() => void refreshHistory()} loading={historyLoading}>
                查询
              </Button>
            </div>

            {historyError ? <Alert type="error" showIcon message={historyError} className="dashboard-alert" /> : null}

            {historyLoading && !history ? (
              <div className="history-empty">加载任务历史中...</div>
            ) : history && history.items.length > 0 ? (
              <List
                dataSource={history.items}
                renderItem={(item) => {
                  const itemField = asRecord(item.field)
                  const itemDecision = asRecord(item.decision)
                  const itemMedication = asRecord(itemDecision['用药'])
                  const itemWeather = asRecord(item.weather)

                  return (
                    <List.Item className="history-item">
                      <div className="history-topline">
                        <div>
                          <div className="history-request">{item.request_id}</div>
                          <div className="history-field">
                            {String(itemField.field_name ?? itemField.field_id ?? '未命名地块')}
                          </div>
                        </div>
                        <div className="history-tag-group">
                          <Tag color={item.status === 'completed' ? 'success' : item.status === 'error' ? 'error' : 'processing'}>
                            {item.status}
                          </Tag>
                          <Tag>{item.current_stage}</Tag>
                        </div>
                      </div>

                      <div className="history-message">{item.message || '暂无任务说明'}</div>

                      <div className="history-metrics">
                        <span>农药：{String(itemMedication['农药名称'] ?? '--')}</span>
                        <span>天气：{String(itemWeather.summary ?? '--')}</span>
                        <span>识别目标：{item.detections.length}</span>
                        <span>更新时间：{formatDateTime(item.updated_at)}</span>
                      </div>
                    </List.Item>
                  )
                }}
              />
            ) : (
              <Empty description="当前筛选条件下暂无结构化任务记录" />
            )}
          </Card>
        </section>
      </Content>
    </Layout>
  )
}
