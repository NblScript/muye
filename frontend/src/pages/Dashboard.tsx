import { lazy, Suspense } from 'react'
import Loading from '../assets/screen/loading'
import { useDashboardState } from '../hooks/useDashboardState'

const Screen = lazy(() => import('../assets/screen/Screen'))

export default function Dashboard() {
  const state = useDashboardState()
  const {
    fileInputRef,
    uploading,
    workflowLoading,
    confirmingTakeoff,
    showTakeoffBanner,
    connected,
    latestTask,
    weather,
    pipelineProgress,
    handleUploadChange,
    handleUploadClick,
    handleConfirmTakeoff,
    refreshWorkflow,
    toast,
  } = state

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept=".jpg,.jpeg,.png"
        style={{ display: 'none' }}
        onChange={handleUploadChange}
      />
      <Suspense fallback={<Loading />}>
        <Screen
          weather={weather}
          latestTask={latestTask}
          progress={pipelineProgress}
          connected={connected}
          actions={{
            uploading,
            workflowLoading,
            confirmingTakeoff,
            showTakeoff: showTakeoffBanner,
            onUpload: handleUploadClick,
            onRefresh: () => { void refreshWorkflow() },
            onConfirmTakeoff: () => { void handleConfirmTakeoff() },
          }}
        />
      </Suspense>
      {toast?.holder}
    </>
  )
}
