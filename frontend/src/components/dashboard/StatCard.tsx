import { Card, Typography } from 'antd'

interface StatCardProps {
  label: string
  value: string | number
  unit: string
  footnote: string
  className?: string
}

export default function StatCard({ label, value, unit, footnote, className }: StatCardProps) {
  return (
    <Card bordered={false} className={`dashboard-card stat-card ${className ?? ''}`}>
      <Typography.Text className="panel-label">{label}</Typography.Text>
      <div className="stat-value">{value}</div>
      <Typography.Text className="stat-unit">{unit}</Typography.Text>
      <div className="stat-footnote">{footnote}</div>
    </Card>
  )
}
