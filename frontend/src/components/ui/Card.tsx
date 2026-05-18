import type { CSSProperties, MouseEventHandler, ReactNode } from 'react'

type CardProps = {
  title?: ReactNode
  extra?: ReactNode
  className?: string
  style?: CSSProperties
  onClick?: MouseEventHandler<HTMLDivElement>
  children: ReactNode
}

export default function Card({ title, extra, className = '', style, onClick, children }: CardProps) {
  return (
    <div className={`glass-card dashboard-card ${className}`} style={style} onClick={onClick}>
      {title && (
        <div className="card-header">
          <span className="card-title">{title}</span>
          {extra && <div>{extra}</div>}
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  )
}
