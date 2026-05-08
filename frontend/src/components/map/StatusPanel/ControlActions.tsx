import { Button } from 'antd'
import { PauseCircleOutlined, RollbackOutlined } from '@ant-design/icons'

type ControlActionsProps = {
  disabled?: boolean
}

export default function ControlActions({ disabled = true }: ControlActionsProps) {
  return (
    <section className="status-panel-actions" aria-label="无人机控制">
      <Button size="small" icon={<RollbackOutlined />} disabled={disabled}>
        返航
      </Button>
      <Button size="small" icon={<PauseCircleOutlined />} disabled={disabled}>
        悬停
      </Button>
    </section>
  )
}
