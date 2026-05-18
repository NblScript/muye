type ProgressProps = {
  percent: number
  color?: string
  height?: number
  className?: string
  size?: 'small' | 'default'
  showInfo?: boolean
  strokeColor?: string
}

export default function Progress({ percent, color, height = 8, className = '', size, strokeColor }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, percent))
  const resolvedColor = strokeColor || color
  const resolvedHeight = size === 'small' ? 4 : height
  return (
    <div className={`progress-track ${className}`} style={{ height: resolvedHeight }}>
      <div
        className="progress-fill"
        style={{
          width: `${clamped}%`,
          background: resolvedColor || undefined,
        }}
      />
    </div>
  )
}
