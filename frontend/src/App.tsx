import { lazy, Suspense } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import { BrowserRouter, useLocation } from './router'

const History = lazy(() => import('./pages/History'))
const Settings = lazy(() => import('./pages/Settings'))

function CurrentRoute() {
  const { pathname } = useLocation()
  const page = pathname === '/history'
    ? <History />
    : pathname === '/settings'
      ? <Settings />
      : <Dashboard />

  return <MainLayout>{page}</MainLayout>
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<div className="route-loading"><span className="spinner" /></div>}>
          <CurrentRoute />
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
