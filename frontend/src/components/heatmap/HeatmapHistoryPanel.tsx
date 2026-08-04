import { useEffect, useMemo, useState } from 'react'

import {
  fetchHeatmapComparison,
  fetchHeatmapSnapshot,
  fetchHeatmapSnapshots,
  fetchMission,
} from '../../api/workflow'
import type {
  HeatmapComparisonResponse,
  HeatmapInspectionKind,
  HeatmapSnapshotDetail,
  HeatmapSnapshotListResponse,
  HeatmapSnapshotSummary,
  MissionDetail,
} from '../../types/workflow'
import { pestLabel } from '../../assets/screen/model'
import { Card, Empty, Select, Tag } from '../ui'

type FilterState = {
  pestType: string
  source: string
  inspectionKind: string
  capturedFrom: string
  capturedTo: string
}

type TrendMetric = {
  key: 'detections' | 'hotspots' | 'peak'
  label: string
  color: string
  values: number[]
  formatValue: (value: number) => string
}

const EMPTY_FILTERS: FilterState = {
  pestType: 'all',
  source: 'all',
  inspectionKind: 'all',
  capturedFrom: '',
  capturedTo: '',
}

const SOURCE_LABELS: Record<string, string> = {
  yolo_bbox: 'YOLO 实测',
  demo_seed: '演示种子',
  legacy_task: '旧任务兼容',
  legacy_yolo: '旧版 YOLO',
}

const DEFAULT_SOURCE_OPTIONS = ['yolo_bbox', 'demo_seed', 'legacy_task']

function formatDateTime(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value || '--'
  return parsed.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatShortDate(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '--'
  return parsed.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function inspectionLabel(kind: HeatmapInspectionKind) {
  return kind === 'reinspection' ? '喷洒后复检' : '喷洒前巡检'
}

function sourceLabel(source: string) {
  return SOURCE_LABELS[source] ?? source
}

function toCapturedBoundary(value: string, endOfDay: boolean) {
  if (!value) return undefined
  const localTime = new Date(`${value}T${endOfDay ? '23:59:59.999' : '00:00:00.000'}`)
  return Number.isNaN(localTime.getTime()) ? undefined : localTime.toISOString()
}

function relativeHeatColor(value: number) {
  const normalized = Math.max(0, Math.min(1, value))
  if (normalized >= 0.7) return `rgba(192, 96, 90, ${0.38 + normalized * 0.5})`
  if (normalized >= 0.3) return `rgba(196, 138, 42, ${0.32 + normalized * 0.55})`
  return `rgba(90, 138, 106, ${0.16 + normalized * 0.65})`
}

function signed(value: number, digits = 0) {
  const rounded = value.toFixed(digits)
  return value > 0 ? `+${rounded}` : rounded
}

function HeatmapGrid({ snapshot, label }: { snapshot: HeatmapSnapshotDetail; label: string }) {
  const { cells, rows, cols } = useMemo(() => {
    const metadataRows = Number(snapshot.density_metadata.grid_rows)
    const metadataCols = Number(snapshot.density_metadata.grid_cols)
    const maxRow = Math.max(-1, ...snapshot.density_grid.map((cell) => cell.row))
    const maxCol = Math.max(-1, ...snapshot.density_grid.map((cell) => cell.col))
    const rowCount = Math.max(1, Number.isFinite(metadataRows) ? metadataRows : 0, maxRow + 1)
    const colCount = Math.max(1, Number.isFinite(metadataCols) ? metadataCols : 0, maxCol + 1)
    const densityByCell = new Map(
      snapshot.density_grid.map((cell) => [`${cell.row}:${cell.col}`, Math.max(0, Math.min(1, cell.density))]),
    )
    const normalizedCells = Array.from({ length: rowCount * colCount }, (_, index) => {
      const row = Math.floor(index / colCount)
      const col = index % colCount
      return { row, col, density: densityByCell.get(`${row}:${col}`) ?? 0 }
    })
    return { cells: normalizedCells, rows: rowCount, cols: colCount }
  }, [snapshot])

  return (
    <div className="heatmap-grid-card">
      <div className="heatmap-grid-heading">
        <strong>{label}</strong>
        <span>{inspectionLabel(snapshot.inspection_kind)} · {formatDateTime(snapshot.captured_at)}</span>
      </div>
      <div
        className="heatmap-grid-visual"
        role="img"
        aria-label={`${label}，${rows} 行 ${cols} 列相对热值网格`}
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {cells.map((cell) => (
          <span
            key={`${cell.row}:${cell.col}`}
            className="heatmap-grid-cell"
            style={{ background: relativeHeatColor(cell.density) }}
            title={`第 ${cell.row + 1} 行第 ${cell.col + 1} 列：相对热值 ${(cell.density * 100).toFixed(0)}%`}
          />
        ))}
      </div>
      <div className="heatmap-grid-legend" aria-hidden="true">
        <span>低</span><i /><span>高</span>
      </div>
      <div className="heatmap-grid-facts">
        <span>检测 {snapshot.total_detection_count}</span>
        <span>热点 {snapshot.hotspot_cell_count}</span>
        <span>峰值 {(snapshot.peak_relative_heat * 100).toFixed(0)}%</span>
      </div>
    </div>
  )
}

function TrendSparkline({ metric, labels }: { metric: TrendMetric; labels: string[] }) {
  const width = 520
  const height = 62
  const pad = 5
  const maximum = Math.max(...metric.values, metric.key === 'peak' ? 1 : 0, 1)
  const points = metric.values.map((value, index) => {
    const x = pad + (index / Math.max(metric.values.length - 1, 1)) * (width - pad * 2)
    const y = height - pad - (value / maximum) * (height - pad * 2)
    return `${x},${y}`
  }).join(' ')
  const latest = metric.values.at(-1) ?? 0

  return (
    <div className="heatmap-trend-series">
      <div className="heatmap-trend-series-heading">
        <span><i style={{ background: metric.color }} />{metric.label}</span>
        <strong>{metric.formatValue(latest)}</strong>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`${metric.label}趋势，共 ${metric.values.length} 个快照`}
      >
        <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="var(--border-default)" />
        <polyline points={points} fill="none" stroke={metric.color} strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="heatmap-trend-axis"><span>{labels[0]}</span><span>{labels.at(-1)}</span></div>
    </div>
  )
}

function HeatmapTrend({ items }: { items: HeatmapSnapshotSummary[] }) {
  const ordered = useMemo(
    () => [...items]
      .sort((left, right) => new Date(left.captured_at).getTime() - new Date(right.captured_at).getTime())
      .slice(-30),
    [items],
  )
  if (ordered.length === 0) return <Empty description="当前筛选条件下暂无趋势数据" />

  const labels = ordered.map((item) => formatShortDate(item.captured_at))
  const metrics: TrendMetric[] = [
    {
      key: 'detections',
      label: '检测数量',
      color: 'var(--accent-amber)',
      values: ordered.map((item) => item.total_detection_count),
      formatValue: (value) => `${Math.round(value)} 只`,
    },
    {
      key: 'hotspots',
      label: '热点网格',
      color: 'var(--accent-red)',
      values: ordered.map((item) => item.hotspot_cell_count),
      formatValue: (value) => `${Math.round(value)} 个`,
    },
    {
      key: 'peak',
      label: '峰值相对热值',
      color: 'var(--accent-cyan)',
      values: ordered.map((item) => item.peak_relative_heat),
      formatValue: (value) => `${Math.round(value * 100)}%`,
    },
  ]

  return (
    <div>
      <div className="heatmap-trend-grid">
        {metrics.map((metric) => <TrendSparkline key={metric.key} metric={metric} labels={labels} />)}
      </div>
      <p className="heatmap-analysis-note">
        显示当前筛选结果中最近 30 个快照；三条曲线分别缩放。每次快照独立归一化，峰值相对热值不用于跨批次判断绝对虫口密度。
      </p>
    </div>
  )
}

function ComparisonMetric({ label, value, suffix = '' }: { label: string; value: number; suffix?: string }) {
  const tone = value < 0 ? 'is-improved' : value > 0 ? 'is-increased' : 'is-flat'
  return (
    <div className={`heatmap-comparison-metric ${tone}`}>
      <span>{label}</span>
      <strong>{signed(value, suffix ? 1 : 0)}{suffix}</strong>
    </div>
  )
}

const DEGRADATION_LABELS: Record<string, string> = {
  invalid_geofence: '地块边界不可用，已降级为均匀喷洒',
  no_valid_detection_coordinates: '检测框缺少有效定位，已降级为均匀喷洒',
  variable_planning_unavailable: '变量规划不可用，已降级为均匀喷洒',
}

function findSnapshotConsumer(mission: MissionDetail | null, snapshotId: string) {
  return mission?.iterations.find((iteration) => iteration.heatmap_snapshot_id === snapshotId) ?? null
}

function HeatmapSprayTrace({
  snapshot,
  mission,
  error,
}: {
  snapshot: HeatmapSnapshotDetail
  mission: MissionDetail | null
  error: string | null
}) {
  if (error) return <div className="heatmap-trace-note color-error">{error}</div>

  const iteration = findSnapshotConsumer(mission, snapshot.snapshot_id)
  if (!iteration) {
    return (
      <div className="heatmap-trace-note">
        {snapshot.mission_id
          ? '该快照已进入闭环，目前尚未被后续喷洒迭代消费。'
          : '该快照尚未关联闭环喷洒任务。'}
      </div>
    )
  }

  const plan = iteration.spray_plan ?? {}
  const policy = plan.spray_rate_policy
  const schedule = plan.spray_schedule ?? []
  const scheduleRange = schedule.length > 0
    ? `${Math.min(...schedule).toFixed(2)}–${Math.max(...schedule).toFixed(2)} L/min`
    : '均匀喷洒'
  const variableRate = plan.planning_mode === 'variable_rate'

  return (
    <div className="heatmap-spray-trace" aria-label="热力快照作业追溯">
      <div className="heatmap-spray-trace-heading">
        <strong>作业追溯</strong>
        <Tag color={variableRate ? 'green' : 'amber'}>
          {variableRate ? '变量喷洒' : '均匀降级'}
        </Tag>
      </div>
      <div className="heatmap-trace-facts">
        <span>闭环第 {iteration.iteration_number} 轮</span>
        <span>算法 {iteration.heatmap_algorithm_version ?? snapshot.algorithm_version}</span>
        <span>喷洒范围 {scheduleRange}</span>
      </div>
      {policy?.bands && policy.bands.length > 0 && (
        <div className="heatmap-rate-policy">
          {policy.bands.map((band) => (
            <span key={`${band.minimum}-${band.multiplier}`}>
              {band.label} {band.maximum_exclusive == null
                ? `≥${Math.round(band.minimum * 100)}%`
                : `${Math.round(band.minimum * 100)}–${Math.round(band.maximum_exclusive * 100)}%`}
              {' '}×{band.multiplier}
            </span>
          ))}
        </div>
      )}
      {plan.degradation_reason && (
        <p>{DEGRADATION_LABELS[plan.degradation_reason] ?? plan.degradation_reason}</p>
      )}
    </div>
  )
}

function HeatmapComparison({ comparison }: { comparison: HeatmapComparisonResponse | null }) {
  if (!comparison) {
    return <Empty description="该巡检暂未形成可读取的喷洒前后对比" />
  }

  const statusText = comparison.status === 'paired'
    ? '已配对'
    : comparison.status === 'pending_reinspection'
      ? '等待喷洒后复检'
      : '等待喷洒前巡检'

  return (
    <div className="heatmap-comparison">
      <div className="heatmap-comparison-status">
        <Tag color={comparison.status === 'paired' ? 'green' : 'amber'}>{statusText}</Tag>
        <span>闭环第 {comparison.iteration_number} 轮</span>
      </div>
      {comparison.metrics && (
        <div className="heatmap-comparison-metrics">
          <ComparisonMetric label="检测数量变化" value={comparison.metrics.detection_count_change} />
          <ComparisonMetric label="热点网格变化" value={comparison.metrics.hotspot_cell_count_change} />
          <ComparisonMetric
            label="峰值相对热值变化"
            value={comparison.metrics.peak_relative_heat_change * 100}
            suffix=" 个百分点"
          />
        </div>
      )}
      <div className="heatmap-comparison-grids">
        {comparison.pre_spray
          ? <HeatmapGrid snapshot={comparison.pre_spray} label="喷洒前" />
          : <Empty description="缺少喷洒前快照" />}
        {comparison.reinspection
          ? <HeatmapGrid snapshot={comparison.reinspection} label="喷洒后" />
          : <Empty description="等待复检快照" />}
      </div>
      <p className="heatmap-analysis-note">
        并列图不使用闪烁动画。检测数与热点变化仅描述本次巡检结果；正式杀灭率和效果结论以后端任务评估为准。
      </p>
    </div>
  )
}

export default function HeatmapHistoryPanel() {
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS)
  const [data, setData] = useState<HeatmapSnapshotListResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadedFilterKey, setLoadedFilterKey] = useState('')
  const [knownPestTypes, setKnownPestTypes] = useState<string[]>([])
  const [knownSources, setKnownSources] = useState<string[]>(DEFAULT_SOURCE_OPTIONS)
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null)
  const [detailState, setDetailState] = useState<{
    snapshotId: string
    snapshot: HeatmapSnapshotDetail | null
    comparison: HeatmapComparisonResponse | null
    mission: MissionDetail | null
    error: string | null
    missionError: string | null
  } | null>(null)

  const invalidDateRange = Boolean(
    filters.capturedFrom
    && filters.capturedTo
    && filters.capturedFrom > filters.capturedTo,
  )
  const filterKey = JSON.stringify(filters)
  const loading = !invalidDateRange && loadedFilterKey !== filterKey
  const visibleError = invalidDateRange
    ? '开始日期不能晚于结束日期'
    : loadedFilterKey === filterKey ? error : null

  useEffect(() => {
    if (invalidDateRange) return

    let active = true
    void fetchHeatmapSnapshots({
      pest_type: filters.pestType === 'all' ? undefined : filters.pestType,
      source: filters.source === 'all' ? undefined : filters.source,
      inspection_kind: filters.inspectionKind === 'all'
        ? undefined
        : filters.inspectionKind as HeatmapInspectionKind,
      captured_from: toCapturedBoundary(filters.capturedFrom, false),
      captured_to: toCapturedBoundary(filters.capturedTo, true),
      limit: 100,
    }).then((result) => {
      if (!active) return
      setData(result)
      setError(null)
      setLoadedFilterKey(filterKey)
      setKnownPestTypes((current) => [...new Set([
        ...current,
        ...result.items.flatMap((item) => Object.keys(item.pest_counts)),
      ])].sort((left, right) => left.localeCompare(right, 'zh-CN')))
      setKnownSources((current) => [...new Set([
        ...current,
        ...result.items.map((item) => item.source),
      ])].sort((left, right) => sourceLabel(left).localeCompare(sourceLabel(right), 'zh-CN')))
    }).catch((reason: unknown) => {
      if (!active) return
      setError(reason instanceof Error ? reason.message : '加载虫情热力快照失败')
      setLoadedFilterKey(filterKey)
    })

    return () => { active = false }
  }, [filters, filterKey, invalidDateRange])

  const effectiveSelectedSnapshotId = data?.items.some((item) => item.snapshot_id === selectedSnapshotId)
    ? selectedSnapshotId
    : data?.items[0]?.snapshot_id ?? null

  const selectedSummary = useMemo(
    () => data?.items.find((item) => item.snapshot_id === effectiveSelectedSnapshotId) ?? null,
    [data, effectiveSelectedSnapshotId],
  )

  useEffect(() => {
    if (!selectedSummary) return

    let active = true
    Promise.allSettled([
      fetchHeatmapSnapshot(selectedSummary.snapshot_id),
      fetchHeatmapComparison(selectedSummary.request_id, selectedSummary.iteration_number),
      selectedSummary.mission_id
        ? fetchMission(selectedSummary.mission_id)
        : Promise.resolve(null),
    ]).then(([snapshotResult, comparisonResult, missionResult]) => {
      if (!active) return
      const snapshot = snapshotResult.status === 'fulfilled' ? snapshotResult.value : null
      const detailError = snapshotResult.status === 'rejected'
        ? snapshotResult.reason instanceof Error
          ? snapshotResult.reason.message
          : '加载热力快照详情失败'
        : null
      setDetailState({
        snapshotId: selectedSummary.snapshot_id,
        snapshot,
        comparison: comparisonResult.status === 'fulfilled' ? comparisonResult.value : null,
        mission: missionResult.status === 'fulfilled' ? missionResult.value : null,
        error: detailError,
        missionError: missionResult.status === 'rejected'
          ? missionResult.reason instanceof Error
            ? missionResult.reason.message
            : '加载喷洒追溯失败'
          : null,
      })
    })

    return () => { active = false }
  }, [selectedSummary])

  const detailMatchesSelection = detailState?.snapshotId === selectedSummary?.snapshot_id
  const selectedSnapshot = detailState && detailMatchesSelection ? detailState.snapshot : null
  const comparison = detailState && detailMatchesSelection ? detailState.comparison : null
  const mission = detailState && detailMatchesSelection ? detailState.mission : null
  const detailError = detailState && detailMatchesSelection ? detailState.error : null
  const missionError = detailState && detailMatchesSelection ? detailState.missionError : null
  const detailLoading = Boolean(selectedSummary && !detailMatchesSelection)

  const updateFilter = <Key extends keyof FilterState>(key: Key, value: FilterState[Key]) => {
    setFilters((current) => ({ ...current, [key]: value }))
  }

  return (
    <section className="heatmap-history-section" aria-labelledby="heatmap-history-title">
      <div className="heatmap-section-title">
        <div>
          <h3 id="heatmap-history-title">虫情热力历史</h3>
          <p>按虫种、来源和巡检时间追溯相对热值快照，并查看喷洒前后变化。</p>
        </div>
        <Tag color="cyan">{data?.total ?? 0} 个快照</Tag>
      </div>

      <Card title="快照筛选" extra={loading ? <span className="heatmap-loading-label">正在更新…</span> : undefined}>
        <div className="heatmap-filter-grid">
          <label>
            <span>昆虫种类</span>
            <Select
              value={filters.pestType}
              onChange={(value) => updateFilter('pestType', value)}
              options={[
                { value: 'all', label: '全部虫种' },
                ...knownPestTypes.map((value) => ({ value, label: pestLabel(value) })),
              ]}
            />
          </label>
          <label>
            <span>数据来源</span>
            <Select
              value={filters.source}
              onChange={(value) => updateFilter('source', value)}
              options={[
                { value: 'all', label: '全部来源' },
                ...knownSources.map((value) => ({ value, label: sourceLabel(value) })),
              ]}
            />
          </label>
          <label>
            <span>巡检阶段</span>
            <Select
              value={filters.inspectionKind}
              onChange={(value) => updateFilter('inspectionKind', value)}
              options={[
                { value: 'all', label: '全部阶段' },
                { value: 'pre_spray', label: '喷洒前巡检' },
                { value: 'reinspection', label: '喷洒后复检' },
              ]}
            />
          </label>
          <label>
            <span>开始日期</span>
            <input
              type="date"
              value={filters.capturedFrom}
              onChange={(event) => updateFilter('capturedFrom', event.target.value)}
            />
          </label>
          <label>
            <span>结束日期</span>
            <input
              type="date"
              value={filters.capturedTo}
              min={filters.capturedFrom || undefined}
              onChange={(event) => updateFilter('capturedTo', event.target.value)}
            />
          </label>
          <button type="button" className="btn-report heatmap-filter-reset" onClick={() => setFilters(EMPTY_FILTERS)}>
            清除筛选
          </button>
        </div>
        {invalidDateRange && <div className="heatmap-inline-error">开始日期不能晚于结束日期</div>}
      </Card>

      <Card title="虫情指标趋势" className="heatmap-history-card">
        {visibleError ? <div className="color-error">{visibleError}</div> : <HeatmapTrend items={data?.items ?? []} />}
      </Card>

      <Card title="热力快照" className="heatmap-history-card">
        {visibleError ? (
          <div className="color-error">{visibleError}</div>
        ) : !loading && (data?.items.length ?? 0) === 0 ? (
          <Empty description="当前筛选条件下暂无热力快照" />
        ) : (
          <div className="history-table-wrap">
            <table className="history-table heatmap-snapshot-table">
              <thead>
                <tr>
                  <th>采集时间</th>
                  <th>虫种</th>
                  <th>阶段</th>
                  <th>检测数</th>
                  <th>热点网格</th>
                  <th>峰值热值</th>
                  <th>来源</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((item) => (
                  <tr key={item.snapshot_id} className={item.snapshot_id === effectiveSelectedSnapshotId ? 'is-selected' : ''}>
                    <td>{formatDateTime(item.captured_at)}</td>
                    <td>{Object.entries(item.pest_counts).map(([name, count]) => `${pestLabel(name)} ${count}`).join('、') || '--'}</td>
                    <td>{inspectionLabel(item.inspection_kind)}</td>
                    <td className="mono">{item.total_detection_count}</td>
                    <td className="mono">{item.hotspot_cell_count}</td>
                    <td className="mono">{Math.round(item.peak_relative_heat * 100)}%</td>
                    <td>
                      <Tag color={item.is_simulated ? 'amber' : 'green'}>
                        {item.is_simulated ? '模拟' : '实测'} · {sourceLabel(item.source)}
                      </Tag>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn-report"
                        aria-pressed={item.snapshot_id === effectiveSelectedSnapshotId}
                        onClick={() => setSelectedSnapshotId(item.snapshot_id)}
                      >
                        查看
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selectedSummary && (
        <div className="heatmap-detail-layout">
          <Card title="选中快照" className="heatmap-history-card">
            {detailError ? (
              <div className="color-error">{detailError}</div>
            ) : detailLoading && !selectedSnapshot ? (
              <div className="heatmap-detail-loading">正在加载快照详情…</div>
            ) : selectedSnapshot ? (
              <>
                <div className="heatmap-detail-meta">
                  <span>请求 <code>{selectedSnapshot.request_id}</code></span>
                  <span>算法 {selectedSnapshot.algorithm_version}</span>
                  <span>{selectedSnapshot.legacy ? '旧数据只读转换' : 'SQLite 持久快照'}</span>
                </div>
                <HeatmapGrid snapshot={selectedSnapshot} label="本次巡检热力" />
                <HeatmapSprayTrace
                  snapshot={selectedSnapshot}
                  mission={mission}
                  error={missionError}
                />
              </>
            ) : null}
          </Card>
          <Card title="喷洒前后对比" className="heatmap-history-card heatmap-comparison-card">
            {detailLoading && !comparison
              ? <div className="heatmap-detail-loading">正在配对闭环快照…</div>
              : <HeatmapComparison comparison={comparison} />}
          </Card>
        </div>
      )}
    </section>
  )
}
