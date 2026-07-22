import { StatCard, WeatherCard, TaskList } from '../components/dashboard'
import DecisionFlow from '../components/dashboard/DecisionFlow'
import DecisionSummaryCard from '../components/dashboard/DecisionSummaryCard'
import DecisionExplainPanel from '../components/dashboard/DecisionExplainPanel'
import ExpertPanel from '../components/dashboard/ExpertPanel'
import PipelineStepper from '../components/dashboard/PipelineStepper'
import FieldMap from '../components/map/FieldMap'
import WorkflowPanel from '../components/workflow/WorkflowPanel'
import { Alert, Button, Card, Empty, Input, Select, Tag, useToast } from '../components/ui'
import { useDashboardState } from '../hooks/useDashboardState'
import { asRecord, modeColor, safeMetric } from '../utils/dashboardUtils'
import '../styles/dashboard.css'

const HERO_STAGE_LABELS: Record<string, string> = {
  upload: '图像上传',
  detection: 'YOLO识别',
  weather: '气象融合',
  decision: 'AI决策',
  drone: '无人机执行',
}

function isEmptyDisplayValue(value: unknown): boolean {
  return value === null || value === undefined || value === '' || value === '--'
}

export default function Dashboard() {
  const toast = useToast()
  const s = useDashboardState()

  return (
    <div className={`dashboard-shell${s.demoMode ? ' demo-mode' : ''}`}>
      <div className="demo-mode-bar">
        <button
          type="button"
          className={`demo-mode-toggle${s.demoMode ? ' is-active' : ''}`}
          onClick={() => { s.setDemoMode((v) => !v) }}
        >
          {s.demoMode ? '✕ 退出展示模式' : '▶ 进入展示模式'}
        </button>
        {s.demoMode && <span className="demo-mode-hint">已隐藏技术细节，展示决策叙事</span>}
      </div>
      <section className="dashboard-command-strip">
        <Card className="dashboard-card command-card">
          <div className="command-strip-topline">
            <div>
              <span className="panel-label">全自动闭环作业</span>
              <div className="command-strip-title">牧野智慧植保指挥平台</div>
              <div className="command-strip-subtitle">
                无人机定期航拍 → 图片自动进入识别管线 → 发现虫情后联动气象、RAG 知识与千问大模型生成施药方案 → 驱动无人机精准喷洒
              </div>
            </div>
            <div className="command-strip-right">
              <div className="tag-row">
                <Tag color={modeColor(s.context?.modes.yolo)}>YOLO {s.context?.modes.yolo ?? '--'}</Tag>
                <Tag color={modeColor(s.context?.modes.weather)}>天气 {s.context?.modes.weather ?? '--'}</Tag>
                <Tag color={modeColor(s.context?.modes.qwen)}>千问 {s.context?.modes.qwen ?? '--'}</Tag>
                <Tag color={modeColor(s.context?.modes.drone)}>无人机 {s.context?.modes.drone ?? '--'}</Tag>
                <Tag color={s.connected ? 'green' : 'amber'} className="tag-ml">
                  {s.connected ? '实时' : '轮询'}
                </Tag>
              </div>
              <div className="command-clock">{s.clock}</div>
            </div>
          </div>

          <div className="demo-hero-grid">
            <div className="demo-hero-panel">
              <span className="panel-label">作业阶段</span>
              <div className="demo-hero-title">{s.heroTitle}</div>
              {s.hasCurrentTask ? (
                <>
                  <div className="hero-highlight">
                    <div className="hero-highlight-main">{s.primaryPest}</div>
                    <div className="hero-highlight-sub">
                      当前目标地块：{s.currentFieldName} · 当前作物：{s.currentCropName}
                    </div>
                  </div>
                  <div className="hero-bullet-list">
                    <div className="hero-bullet-item">
                      <strong>自动虫情识别</strong>
                      <span>图像到达后自动触发 YOLO 检测，无需人工干预</span>
                    </div>
                    <div className="hero-bullet-item">
                      <strong>知识增强决策</strong>
                      <span>融合实时气象、RAG 农药知识库与千问大模型生成施药方案</span>
                    </div>
                    <div className="hero-bullet-item">
                      <strong>无人机自主执行</strong>
                      <span>自动规划航线并联动无人机完成精准喷洒</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="hero-idle-guide">
                  <strong>系统自动监视 data/images/ 目录，无人机航拍图片落入后自动触发全链路处理</strong>
                  <span>可手动注入图像，触发同一条全自动管线：虫情识别 → 气象融合 → AI 决策 → 无人机执行</span>
                </div>
              )}
            </div>

            <div className="demo-hero-panel is-accent">
              <span className="panel-label">本轮任务状态</span>
              <div className="hero-progress-block">
                <div className="hero-progress-topline">
                  <div>
                    <span>当前阶段</span>
                    <strong>{s.activeStageLabel}</strong>
                  </div>
                  <strong>{s.pipelineProgress}%</strong>
                </div>
                <div className="hero-progress-track" aria-label={`本轮任务进度 ${s.pipelineProgress}%`}>
                  <span style={{ width: `${s.pipelineProgress}%` }} />
                </div>
                <div className="hero-stage-indicator" aria-label="本轮任务阶段">
                  {s.pipelineStages.map((stage, index) => (
                    <div key={stage.key} className="hero-stage-group">
                      <div className={`hero-stage-item is-${stage.status}`}>
                        <span className="hero-stage-dot" aria-hidden="true" />
                        <span>{HERO_STAGE_LABELS[stage.key] ?? stage.label}</span>
                      </div>
                      {index < s.pipelineStages.length - 1 && (
                        <span className={`hero-stage-connector ${stage.status === 'done' ? 'is-filled' : ''}`}>
                          →
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <div className="hero-storyline">
                <span className="hero-storyline-label">阶段说明</span>
                <strong>{s.heroStageSummary}</strong>
                <span>{s.hasCurrentTask ? `最后更新时间：${s.latestUpdateText}` : '等待任务启动'}</span>
              </div>
            </div>
          </div>

          <div className="command-strip-actions">
            <div className="command-action-group">
              <input
                ref={s.fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png"
                className="upload-input"
                onChange={s.handleUploadChange}
              />
              <Button variant="primary" onClick={s.handleUploadClick} loading={s.uploading}>
                {s.uploading ? '管线处理中…' : '注入巡检图像'}
              </Button>
              <Button onClick={() => void s.refreshWorkflow()} loading={s.workflowLoading}>
                {s.workflowLoading ? '加载中…' : '重载实时画面'}
              </Button>
              <Button variant="danger" onClick={s.handleResetEvents} loading={s.resetting}>
                重置任务流程
              </Button>
              {s.px4Running ? (
                <Button variant="danger" onClick={() => void s.handlePx4Stop()}>
                  停止无人机
                </Button>
              ) : (
                <Button variant="secondary" onClick={() => void s.handlePx4Start()} loading={s.px4Starting}>
                  {s.px4Starting ? '无人机启动中…' : '启动无人机'}
                </Button>
              )}
            </div>

            <div className="command-strip-meta">
              {s.commandMetaItems.map((item) => {
                const isEmpty = isEmptyDisplayValue(item.value)
                return (
                  <div key={item.label} className="command-meta-item">
                    <span>{item.label}</span>
                    <strong className={isEmpty ? 'is-empty' : undefined}>{item.value}</strong>
                    {isEmpty && <small className="command-meta-hint">{item.emptyHint}</small>}
                  </div>
                )
              })}
            </div>
          </div>
        </Card>
      </section>

      <section className="dashboard-pipeline-strip">
        <Card className="dashboard-card">
          <PipelineStepper task={s.latestTask} />
        </Card>
      </section>


      {s.combinedStatusError ? (
        <Alert
          type="warning"
          message="部分实时数据暂不可用"
          description={s.combinedStatusError}
          className="dashboard-alert"
        />
      ) : null}

      <section className="mission-metric-ribbon" aria-label="作业关键指标">
        <StatCard
          className="stat-card-ribbon"
          label="当前作业面积"
          value={s.currentAreaDisplay}
          unit="亩"
          footnote={`数据来源：${s.spraySummary['spray_area_mu'] ? '喷洒记录' : s.field['area_mu'] ? '地块档案' : '暂无结构化面积'}`}
          sparklineData={s.areaSparkline}
          sparklineColor="var(--accent-green)"
        />

        <StatCard
          className="stat-card-ribbon"
          label="在线设备数"
          value={s.onlineDevices}
          unit="台"
          footnote="数据来源：当前作业无人机"
        />

        <StatCard
          className="stat-card-ribbon"
          label="检测目标数"
          value={s.currentDetectionCount}
          unit="个"
          footnote={`数据来源：当前任务 YOLO 识别（${s.pestSummary.labels.length} 种害虫）`}
          sparklineData={s.detectionSparkline}
          sparklineColor="var(--accent-amber)"
        />

        <StatCard
          className="stat-card-ribbon"
          label="今日任务数"
          value={s.todayTaskCount}
          unit="条"
          footnote="数据来源：当日已完成/运行中的任务"
        />
      </section>

      <section className="dashboard-grid">
        <aside className="dashboard-column dashboard-column-left">
          <DecisionSummaryCard task={s.latestTask} />
          <DecisionFlow task={s.latestTask} />
          {s.latestTask?.rag_context?.consultation_detail && (
            <Card className="dashboard-card expert-panel-card">
              <ExpertPanel ragContext={s.latestTask.rag_context} />
            </Card>
          )}
          <DecisionExplainPanel task={s.latestTask} />
        </aside>

        <main className="dashboard-column dashboard-column-center">
          <Card className="dashboard-card map-card map-card-hero">
            <div className="map-panel">
              <div className="map-header-strip">
                <span className="panel-label">无人机作业态势主视图</span>
                <span className="map-header-note">展示动画 / 地块边界 / 航线规划 / 检测点位</span>
              </div>
              <FieldMap
                droneStatus={s.latestTask?.drone?.status}
                detections={s.latestTask?.detections}
                densityGrid={s.densityGrid}
                spraySchedule={s.spraySchedule}
                instructionRoute={s.instructionRoute}
                instructionCoverage={s.instructionCoverage}
              />
            </div>
          </Card>
        </main>

        <aside className="dashboard-column dashboard-column-right">
          <TaskList tasks={s.recentTasks} />
        </aside>
      </section>

      <section className="dashboard-detail-grid">
        <Card className="dashboard-card image-card">
          <div className="detail-card-header">
            <span className="panel-label">农田原始输入</span>
            <span className="detail-card-meta">{s.latestTask?.image_path ?? '等待图片输入'}</span>
          </div>
          {s.originalImageUrl && s.latestTask?.image_path ? (
            <img src={s.originalImageUrl} alt="原始图片" className="detail-image" />
          ) : (
            <div className="detail-empty">请上传一张图片，或等待后端捕获图片。</div>
          )}
        </Card>

        <Card className="dashboard-card image-card">
          <div className="detail-card-header">
            <span className="panel-label">目标识别与标注</span>
            <span className="detail-card-meta">目标数 {s.detections.length}</span>
          </div>
          {s.annotatedImageUrl && s.latestTask?.image_path ? (
            <img src={s.annotatedImageUrl} alt="识别结果" className="detail-image" />
          ) : (
            <div className="detail-empty">等待识别结果。</div>
          )}
        </Card>

        <Card className="dashboard-card detail-card">
          <div className="detail-card-header">
            <span className="panel-label">识别摘要</span>
            <span className="detail-card-meta">
              种类 {s.pestSummary.labels.length} / 目标 {s.detections.length}
            </span>
          </div>
          <div className="pest-summary-main">{s.pestSummary.summary}</div>
          <div className="pill-wrap">
            {s.pestSummary.labels.length > 0 ? (
              s.pestSummary.labels.map((label) => (
                <span key={label} className="detail-pill is-success">
                  {label}
                </span>
              ))
            ) : (
              <span className="detail-pill is-muted">等待 YOLO 返回害虫名称</span>
            )}
          </div>
        </Card>

        <WeatherCard weather={s.weather} />

        <Card className="dashboard-card detail-card detail-card-wide">
          <div className="detail-card-header">
            <span className="panel-label">AI 决策与施药方案</span>
            <span className="detail-card-meta">{s.latestTask?.error ? `异常：${s.latestTask.error}` : '系统规划参数'}</span>
          </div>
          <div className="detail-metric-grid">
            <div className="detail-metric-card">
              <span>农药名称</span>
              <strong>{safeMetric(s.medication['农药名称'])}</strong>
            </div>
            <div className="detail-metric-card">
              <span>浓度</span>
              <strong>{safeMetric(s.medication['浓度'])}</strong>
            </div>
            <div className="detail-metric-card">
              <span>配比</span>
              <strong>{safeMetric(s.medication['配比'])}</strong>
            </div>
            <div className="detail-metric-card">
              <span>总量</span>
              <strong>{safeMetric(s.medication['总量'])}</strong>
            </div>
            <div className="detail-metric-card">
              <span>飞行高度</span>
              <strong>{safeMetric(asRecord(s.latestTask?.drone?.instruction)['高度'], ' m')}</strong>
            </div>
            <div className="detail-metric-card">
              <span>喷洒速率</span>
              <strong>{safeMetric(asRecord(s.latestTask?.drone?.instruction)['喷洒速率'])}</strong>
            </div>
          </div>

          <div className="detail-subsection">
            <span className="panel-label">安全提示</span>
            <div className="pill-wrap">
              {s.safetyTips.length > 0 ? (
                s.safetyTips.map((item) => (
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
            <span className="panel-label">农事建议</span>
            <div className="pill-wrap">
              {s.agronomyTips.length > 0 ? (
                s.agronomyTips.map((item) => (
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
        <Card className="dashboard-card workflow-card">
          <WorkflowPanel data={s.workflow} loading={s.workflowLoading} error={s.workflowError} onConfirmed={() => void s.refreshWorkflow()} />
        </Card>
      </section>

      <section className="dashboard-history-row">
        <Card className="dashboard-card history-card" title="任务历史检索">
          <div className="history-toolbar">
            <Select
              value={s.historyStatus}
              onChange={s.setHistoryStatus}
              options={[
                { label: '全部状态', value: 'all' },
                { label: '运行中', value: 'running' },
                { label: '已完成', value: 'completed' },
                { label: '异常', value: 'error' },
              ]}
            />
            <Input
              value={s.historySearch}
              onChange={s.setHistorySearch}
              placeholder="request_id / 图片路径 / 害虫类型"
              className="history-search"
            />
            <Select
              value={String(s.historyLimit)}
              onChange={(v) => s.setHistoryLimit(Number(v))}
              options={[
                { label: '12 条', value: '12' },
                { label: '24 条', value: '24' },
                { label: '40 条', value: '40' },
              ]}
            />
            <Button onClick={() => void s.refreshHistory()} loading={s.historyLoading}>
              查询
            </Button>
          </div>

          {s.historyError ? <Alert type="error" message={s.historyError} className="dashboard-alert" /> : null}

          {s.historyLoading && !s.history ? (
            <div className="history-empty">加载任务历史中...</div>
          ) : s.history && s.history.items.length > 0 ? (
            <div className="history-list">
              {s.history.items.map((item) => {
                const itemField = asRecord(item.field)
                const itemDecision = asRecord(item.decision)
                const itemMedication = asRecord(itemDecision['用药'])
                const itemWeather = asRecord(item.weather)

                return (
                  <div key={item.request_id} className="history-item">
                    <div className="history-topline">
                      <div>
                        <div className="history-request">{item.request_id}</div>
                        <div className="history-field">
                          {String(itemField.field_name ?? itemField.field_id ?? '未命名地块')}
                        </div>
                      </div>
                      <div className="history-tag-group">
                        <Tag color={item.status === 'completed' ? 'green' : item.status === 'error' ? 'red' : 'amber'}>
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
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <Empty description="当前筛选条件下暂无结构化任务记录" />
          )}
        </Card>
      </section>

      {toast.holder}
    </div>
  )
}
