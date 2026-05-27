import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { path: '/', label: '指挥台', icon: '⊞' },
  { path: '/history', label: '历史报表', icon: '≡' },
  { path: '/settings', label: '设置', icon: '⚙' },
]

export default function MainLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1 className="sidebar-logo-text">牧野</h1>
          <span className="sidebar-logo-sub">MU YE</span>
        </div>
        <nav className="sidebar-nav">
          <div className="sidebar-section-label">导航</div>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => `sidebar-link ${isActive ? 'is-active' : ''}`}
            >
              <span className="sidebar-link-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="status-dot status-dot-green" />
          <span>系统就绪</span>
        </div>
      </aside>
      <div className="main-content">
        <div className="main-content-body">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
