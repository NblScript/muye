import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { path: '/', label: '指挥台', icon: '⊞' },
  { path: '/px4-viewer', label: 'PX4观察', icon: '◉' },
  { path: '/history', label: '历史报表', icon: '≡' },
  { path: '/settings', label: '设置', icon: '⚙' },
]

export default function MainLayout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">
          <h1 className="app-logo">牧野</h1>
          <span className="app-logo-sub">智农指挥台</span>
        </div>
        <nav className="app-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => `nav-link ${isActive ? 'is-active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="app-header-right">
          <span className="status-dot status-dot-green" />
        </div>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
