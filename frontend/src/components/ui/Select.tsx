import type { CSSProperties } from 'react'

type SelectOption = {
  label: string
  value: string
}

type SelectProps = {
  value: string
  options: SelectOption[]
  onChange: (value: string) => void
  placeholder?: string
  style?: CSSProperties
  className?: string
}

export default function Select({ value, options, onChange, placeholder, style, className = '' }: SelectProps) {
  return (
    <select
      className={`select ${className}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={style}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}
