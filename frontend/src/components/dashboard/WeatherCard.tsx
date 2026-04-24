import { Card, Typography } from 'antd'
import { safeMetric } from '../../utils/dashboardUtils'

type RecordType = Record<string, unknown>

interface WeatherCardProps {
  weather: RecordType
}

export default function WeatherCard({ weather }: WeatherCardProps) {
  const summary = String(weather.summary ?? '等待天气数据')

  return (
    <Card bordered={false} className="dashboard-card detail-card">
      <div className="detail-card-header">
        <Typography.Text className="panel-label">天气信息</Typography.Text>
        <Typography.Text className="detail-card-meta">{summary}</Typography.Text>
      </div>
      <div className="detail-metric-grid">
        <div className="detail-metric-card">
          <span>温度</span>
          <strong>{safeMetric(weather.temperature, ' ℃')}</strong>
        </div>
        <div className="detail-metric-card">
          <span>湿度</span>
          <strong>{safeMetric(weather.humidity, ' %')}</strong>
        </div>
        <div className="detail-metric-card">
          <span>风向</span>
          <strong>{safeMetric(weather.wind_direction)}</strong>
        </div>
        <div className="detail-metric-card">
          <span>风力</span>
          <strong>{safeMetric(weather.wind_scale_text)}</strong>
        </div>
        <div className="detail-metric-card">
          <span>风速</span>
          <strong>{safeMetric(weather.wind_speed, ' m/s')}</strong>
        </div>
      </div>
    </Card>
  )
}
