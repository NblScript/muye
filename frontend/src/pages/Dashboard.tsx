import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Card, Empty, Input, List, Select, Space, Tag, Typography, message } from 'antd'

import {
  buildTaskAnnotatedImageUrl,
  buildTaskOriginalImageUrl,
  fetchDashboardContext,
  fetchWorkflowHistory,
  fetchWorkflowState,
  resetDemoEvents,
  uploadDemoImage,
} from '../api/workflow'
import { StatCard, WeatherCard, TaskList } from '../components/dashboard'
import FieldMap from '../components/map/FieldMap'
import WorkflowPanel from '../components/workflow/WorkflowPanel'
import type {
  DashboardContextResponse,
  WorkflowHistoryResponse,
  WorkflowStateResponse,
} from '../types/workflow'
import {
  asRecord,
  formatDateTime,
  mapTaskEntry,
  modeColor,
  safeMetric,
  summarizePests,
} from '../utils/dashboardUtils'
import '../styles/dashboard.css'

export default function Dashboard() {
  const [messageApi, messageContextHolder] = message.useMessage()
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
    }, 2000)

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

  const { Text } = Typography

  return (
    <div className="dashboard-shell">
      {messageContextHolder}
      <section className="dashboard-command-strip">
          <Card bordered={false} className="dashboard-card command-card">
            <div className="command-strip-topline">
              <div>
                <Text className="panel-label">运行模式</Text>
                <div className="command-strip-title">智慧农业喷洒指挥系统</div>
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
            <StatCard
              label="当前作业面积"
              value={currentAreaDisplay}
              unit="亩"
              footnote={`数据来源：${spraySummary['spray_area_mu'] ? '喷洒记录' : field['area_mu'] ? '地块档案' : '暂无结构化面积'}`}
            />

            <StatCard
              label="在线设备数"
              value={onlineDevices}
              unit="台"
              footnote="数据来源：当前任务中的 PX4 / 作业无人机"
            />

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
            <TaskList tasks={recentTasks} />
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

          <WeatherCard weather={weather} />

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
    </div>
  )
}
