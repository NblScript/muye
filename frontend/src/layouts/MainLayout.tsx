import { Layout, Menu, Typography } from 'antd'
import {
  DashboardOutlined,
  HistoryOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '指挥台' },
  { key: '/history', icon: <HistoryOutlined />, label: '历史报表' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
]

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header style={{ display: 'flex', alignItems: 'center' }}>
        <Typography.Title
          level={4}
          style={{ color: '#fff', margin: 0, marginRight: 32, whiteSpace: 'nowrap' }}
        >
          牧野智农指挥台
        </Typography.Title>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Layout.Header>
      <Layout.Content style={{ padding: '16px' }}>
        <Outlet />
      </Layout.Content>
    </Layout>
  )
}
