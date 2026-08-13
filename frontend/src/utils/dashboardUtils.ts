import type { TagColor } from '../components/ui/Tag'

export function modeColor(value?: string): TagColor {
  if (!value) return 'green'

  const normalized = value.toLowerCase()
  if (['online', 'running', 'ok', 'live'].includes(normalized)) return 'green'
  if (['offline', 'stopped', 'error'].includes(normalized)) return 'red'
  if (['mock', 'sim', 'simulation'].includes(normalized)) return 'amber'
  if (normalized === 'px4') return 'cyan'
  return 'default'
}
