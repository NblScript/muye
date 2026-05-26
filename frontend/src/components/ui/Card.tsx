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
    <div className={`panel dashboard-card ${className}`} style={style} onClick={onClick}>
      {title && (
        <div className="panel-header">
          <span className="panel-title">{title}</span>
          {extra && <div>{extra}</div>}
        </div>
      )}
      <div className="panel-body">{children}</div>
    </div>
  )
}
