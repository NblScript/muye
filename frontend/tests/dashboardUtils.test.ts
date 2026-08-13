import { describe, expect, it } from 'vitest'
import { modeColor } from '../src/utils/dashboardUtils'

describe('modeColor', () => {
  it('maps runtime modes to status colors', () => {
    expect(modeColor('mock')).toBe('amber')
    expect(modeColor('px4')).toBe('cyan')
    expect(modeColor('live')).toBe('green')
    expect(modeColor('error')).toBe('red')
    expect(modeColor(undefined)).toBe('green')
  })
})
