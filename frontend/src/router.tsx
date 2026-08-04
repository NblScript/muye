import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type AnchorHTMLAttributes,
  type MouseEvent,
  type ReactNode,
} from 'react'

interface RouterContextValue {
  pathname: string
  navigate: (path: string) => void
}

const RouterContext = createContext<RouterContextValue | null>(null)

function subscribe(listener: () => void) {
  window.addEventListener('popstate', listener)
  return () => window.removeEventListener('popstate', listener)
}

function getPathname() {
  return window.location.pathname
}

export function BrowserRouter({ children }: { children: ReactNode }) {
  const pathname = useSyncExternalStore(subscribe, getPathname, () => '/')
  const navigate = useCallback((path: string) => {
    if (path === window.location.pathname) return
    window.history.pushState(null, '', path)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, [])
  const value = useMemo(() => ({ pathname, navigate }), [navigate, pathname])

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>
}

// The route hook intentionally shares the tiny router module with its provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useLocation() {
  const router = useContext(RouterContext)
  if (!router) throw new Error('useLocation must be used inside BrowserRouter')
  return { pathname: router.pathname }
}

interface NavLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'className' | 'href'> {
  to: string
  end?: boolean
  className?: string | ((state: { isActive: boolean }) => string)
}

export function NavLink({ to, end = false, className, onClick, ...props }: NavLinkProps) {
  const router = useContext(RouterContext)
  if (!router) throw new Error('NavLink must be used inside BrowserRouter')

  const isActive = end
    ? router.pathname === to
    : router.pathname === to || router.pathname.startsWith(`${to}/`)
  const resolvedClassName = typeof className === 'function' ? className({ isActive }) : className

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)
    if (
      event.defaultPrevented
      || event.button !== 0
      || event.metaKey
      || event.altKey
      || event.ctrlKey
      || event.shiftKey
    ) return
    event.preventDefault()
    router.navigate(to)
  }

  return <a {...props} href={to} className={resolvedClassName} onClick={handleClick} />
}
