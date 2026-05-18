import type { ReactNode } from 'react'

type AlertType = 'warning' | 'error' | 'info' | 'success'

type AlertProps = {
  type: AlertType
  message: string
  description?: ReactNode
  className?: string
}

export default function Alert({ type, message, description, className = '' }: AlertProps) {
  return (
    <div className={`alert alert-${type} ${className}`}>
      <div>{message}</div>
      {description && <div style={{ marginTop: 4, fontSize: 13, opacity: 0.85 }}>{description}</div>}
    </div>
  )
}
