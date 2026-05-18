import { Card } from '../ui'
import { useEffect, useRef, useState } from 'react'

function useCountUp(target: number, duration = 1200): number {
  const [value, setValue] = useState(0)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (target === 0) {
      setValue(0)
      return
    }

    const start = performance.now()
    const from = 0

    const tick = (now: number) => {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      // ease-out cubic
      const eased = 1 - (1 - progress) ** 3
      setValue(Math.round(from + (target - from) * eased))

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick)
      }
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [target, duration])

  return value
}

function Sparkline({ data, color = '#3a9cb0' }: { data: number[]; color?: string }) {
  if (data.length < 2) return null

  const width = 80
  const height = 28
  const padding = 2
  const max = Math.max(...data, 1)
  const min = Math.min(...data, 0)
  const range = max - min || 1

  const points = data
    .map((v, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2)
      const y = height - padding - ((v - min) / range) * (height - padding * 2)
      return `${x},${y}`
    })
    .join(' ')

  return (
    <svg width={width} height={height} className="stat-sparkline">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

interface StatCardProps {
  label: string
  value: string | number
  unit: string
  footnote: string
  className?: string
  sparklineData?: number[]
  sparklineColor?: string
  animated?: boolean
}

export default function StatCard({
  label,
  value,
  unit,
  footnote,
  className,
  sparklineData,
  sparklineColor,
  animated = true,
}: StatCardProps) {
  const numericValue = typeof value === 'number' ? value : parseFloat(String(value))
  const isNumeric = !Number.isNaN(numericValue)
  const countUpValue = useCountUp(isNumeric ? numericValue : 0)
  const displayValue = animated && isNumeric ? countUpValue : value

  return (
    <Card className={`dashboard-card stat-card ${className ?? ''}`}>
      <div className="stat-card-top">
        <span className="label-uppercase">{label}</span>
        {sparklineData && <Sparkline data={sparklineData} color={sparklineColor} />}
      </div>
      <div className="stat-value">{isNumeric ? displayValue : value}</div>
      <span className="stat-unit">{unit}</span>
      <div className="stat-footnote">{footnote}</div>
    </Card>
  )
}
