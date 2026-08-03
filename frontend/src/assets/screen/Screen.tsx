import { useEffect, useMemo } from 'react'
import styled from 'styled-components'
import type { WorkflowTaskState } from '../../types/workflow'
import Map from './map'
import { buildScreenViewModel } from './model'
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
  background: #fff5e8;
`

export interface ScreenProps {
  weather?: Record<string, unknown>
  latestTask?: WorkflowTaskState | null
  progress?: number
  connected?: boolean
  actions: FooterActions
}

export default function Screen({ weather, latestTask, progress = 0, connected = false, actions }: ScreenProps) {
  useEffect(() => {
    useConfigStore.getState().reset()
    return () => useConfigStore.getState().reset()
  }, [])

  const model = useMemo(
    () => buildScreenViewModel(latestTask, weather, progress, connected),
    [latestTask, weather, progress, connected],
  )

  return (
    <Wrapper>
      <Map model={model} />
      <Panel model={model} actions={actions} />
    </Wrapper>
  )
}
