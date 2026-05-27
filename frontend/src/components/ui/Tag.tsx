import type { CSSProperties, ReactNode } from 'react'

export type TagColor = 'amber' | 'purple' | 'green' | 'red' | 'blue' | 'cyan' | 'orange' | 'default'

type TagProps = {
  color?: TagColor
  className?: string
  style?: CSSProperties
  children: ReactNode
}

export default function Tag({ color = 'default', className = '', style, children }: TagProps) {
  return <span className={`tag tag-${color} ${className}`.trim()} style={style}>{children}</span>
}
