import { Button } from '../../ui'

type ControlActionsProps = {
  disabled?: boolean
}

export default function ControlActions({ disabled = true }: ControlActionsProps) {
  return (
    <section className="status-panel-actions" aria-label="无人机控制">
      <Button size="sm" icon={<svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>} disabled={disabled}>
        返航
      </Button>
      <Button size="sm" icon={<svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="10" y1="15" x2="10" y2="9"/><line x1="14" y1="15" x2="14" y2="9"/></svg>} disabled={disabled}>
        悬停
      </Button>
    </section>
  )
}
