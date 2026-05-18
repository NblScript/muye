import type { CSSProperties, ReactNode } from 'react'

export type TagColor = 'amber' | 'purple' | 'green' | 'red' | 'blue' | 'cyan' | 'orange' | 'default'

type TagProps = {
  color?: TagColor
  style?: CSSProperties
  children: ReactNode
}

export default function Tag({ color = 'default', style, children }: TagProps) {
  return <span className={`tag tag-${color}`} style={style}>{children}</span>
}
