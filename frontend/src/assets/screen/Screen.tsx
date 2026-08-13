import { useEffect, useMemo, useState } from 'react'
import styled from 'styled-components'
import type { HeatmapSnapshotDetail, WorkflowTaskState } from '../../types/workflow'
import Map from './map'
import { buildScreenViewModel, pestLabel } from './model'
import Panel from './panel'
import type { FooterActions } from './panel/footer'
import { useConfigStore } from './store'

const Wrapper = styled.div`
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #26282a;
`

export interface ScreenProps {
  weather?: Record<string, unknown>
  latestTask?: WorkflowTaskState | null
  latestHeatmap?: HeatmapSnapshotDetail | null
  progress?: number
  connected?: boolean
  actions: FooterActions
}

export default function Screen({
  weather,
  latestTask,
  latestHeatmap,
  progress = 0,
  connected = false,
  actions,
}: ScreenProps) {
  const [selectedPestType, setSelectedPestType] = useState('all')

  useEffect(() => {
    useConfigStore.getState().reset()
    return () => useConfigStore.getState().reset()
  }, [])

  const pestOptions = useMemo(() => {
    const values = latestHeatmap
      ? Object.keys(latestHeatmap.pest_counts)
      : (latestTask?.detections ?? []).map((item) => item.pest_type ?? '').filter(Boolean)
    return [...new Set(values)]
      .sort((left, right) => left.localeCompare(right, 'zh-CN'))
      .map((value) => ({ value, label: pestLabel(value) }))
  }, [latestHeatmap, latestTask?.detections])

  const effectiveSelectedPestType = selectedPestType === 'all'
    || pestOptions.some((option) => option.value === selectedPestType)
    ? selectedPestType
    : 'all'

  const model = useMemo(
    () => buildScreenViewModel(
      latestTask,
      weather,
      progress,
      connected,
      latestHeatmap ?? null,
      effectiveSelectedPestType,
    ),
    [latestTask, weather, progress, connected, latestHeatmap, effectiveSelectedPestType],
  )

  return (
    <Wrapper data-testid="command-screen">
      <Map
        model={model}
        pestOptions={pestOptions}
        selectedPestType={effectiveSelectedPestType}
        onSelectPest={setSelectedPestType}
      />
      <Panel model={model} actions={actions} />
    </Wrapper>
  )
}
