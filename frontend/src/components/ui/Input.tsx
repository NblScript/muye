import type { InputHTMLAttributes } from 'react'

type InputProps = {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
  className?: string
} & Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'>

export default function Input({ value, onChange, className = '', ...rest }: InputProps) {
  return (
    <input
      className={`input ${className}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      {...rest}
    />
  )
}
