import { describe, it, expect } from 'vitest'
import {
  asRecord,
  formatDateTime,
  formatNow,
  formatPestLabel,
  mapTaskEntry,
  modeColor,
  safeMetric,
  statusColor,
  summarizePests,
  toTaskStatus,
} from '../src/utils/dashboardUtils'

describe('asRecord', () => {
  it('returns the object when given a valid object', () => {
    const obj = { a: 1 }
    expect(asRecord(obj)).toBe(obj)
  })

  it('returns empty object for null/undefined/primitives', () => {
    expect(asRecord(null)).toEqual({})
    expect(asRecord(undefined)).toEqual({})
    expect(asRecord('string')).toEqual({})
    expect(asRecord(42)).toEqual({})
  })
})

describe('formatDateTime', () => {
  it('returns -- for null/undefined/empty', () => {
    expect(formatDateTime(null)).toBe('--')
    expect(formatDateTime(undefined)).toBe('--')
    expect(formatDateTime('')).toBe('--')
  })

  it('returns the raw string for invalid dates', () => {
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
  })

  it('formats a valid ISO date string', () => {
    const result = formatDateTime('2026-05-25T14:30:00Z')
    expect(result).not.toBe('--')
    expect(result).not.toBe('not-a-date')
    expect(result).toMatch(/\d{2}\/\d{2}/)
  })
})

describe('formatNow', () => {
  it('formats a Date object with year', () => {
    const result = formatNow(new Date(2026, 4, 25, 14, 30, 0))
    expect(result).toContain('2026')
    expect(result).toContain('14:30:00')
  })
})

describe('toTaskStatus', () => {
  it('maps spraying to 执行中', () => {
    expect(toTaskStatus('spraying')).toBe('执行中')
    expect(toTaskStatus('作业中')).toBe('执行中')
  })

  it('maps returning to 返航中', () => {
    expect(toTaskStatus('returning')).toBe('返航中')
    expect(toTaskStatus('返航')).toBe('返航中')
  })

  it('defaults to 待起飞', () => {
    expect(toTaskStatus('pending')).toBe('待起飞')
    expect(toTaskStatus('')).toBe('待起飞')
    expect(toTaskStatus('unknown')).toBe('待起飞')
  })
})

describe('statusColor', () => {
  it('returns correct colors', () => {
    expect(statusColor('执行中')).toBe('green')
    expect(statusColor('返航中')).toBe('amber')
    expect(statusColor('待起飞')).toBe('blue')
  })
})

describe('modeColor', () => {
  it('returns correct colors for modes', () => {
    expect(modeColor('mock')).toBe('amber')
    expect(modeColor('px4')).toBe('cyan')
    expect(modeColor('live')).toBe('green')
    expect(modeColor(undefined)).toBe('green')
  })
})

describe('formatPestLabel', () => {
  it('translates known pest codes to Chinese', () => {
    expect(formatPestLabel('aphid')).toBe('蚜虫')
    expect(formatPestLabel('armyworm')).toBe('粘虫')
    expect(formatPestLabel('red-spider')).toBe('红蜘蛛')
  })

  it('is case-insensitive', () => {
    expect(formatPestLabel('APHID')).toBe('蚜虫')
    expect(formatPestLabel('Armyworm')).toBe('粘虫')
  })

  it('returns the raw string for unknown pests', () => {
    expect(formatPestLabel('some-unknown-pest')).toBe('some-unknown-pest')
  })

  it('returns 未知害虫 for empty/null', () => {
    expect(formatPestLabel(null)).toBe('未知害虫')
    expect(formatPestLabel('')).toBe('未知害虫')
    expect(formatPestLabel(undefined)).toBe('未知害虫')
  })
})

describe('summarizePests', () => {
  it('returns empty summary for no detections', () => {
    const result = summarizePests([])
    expect(result.labels).toEqual([])
    expect(result.summary).toBe('未识别到害虫目标')
  })

  it('groups and counts pest types', () => {
    const result = summarizePests([
      { pest_type: 'aphid' },
      { pest_type: 'aphid' },
      { pest_type: 'armyworm' },
    ])
    expect(result.labels).toEqual(['蚜虫 × 2', '粘虫 × 1'])
    expect(result.summary).toBe('蚜虫 × 2，粘虫 × 1')
  })

  it('sorts by count descending', () => {
    const result = summarizePests([
      { pest_type: 'armyworm' },
      { pest_type: 'aphid' },
      { pest_type: 'aphid' },
      { pest_type: 'aphid' },
    ])
    expect(result.labels[0]).toBe('蚜虫 × 3')
  })
})

describe('safeMetric', () => {
  it('returns -- for null/undefined/empty', () => {
    expect(safeMetric(null)).toBe('--')
    expect(safeMetric(undefined)).toBe('--')
    expect(safeMetric('')).toBe('--')
  })

  it('appends suffix when present', () => {
    expect(safeMetric(42, ' ℃')).toBe('42 ℃')
    expect(safeMetric('10', '%')).toBe('10%')
  })

  it('converts value to string', () => {
    expect(safeMetric(0)).toBe('0')
    expect(safeMetric(false)).toBe('false')
  })
})

describe('mapTaskEntry', () => {
  it('maps a DashboardTaskEntry to TaskRecord', () => {
    const entry = {
      request_id: 'req-123',
      updated_at: '2026-05-25T10:00:00Z',
      status: 'spraying',
      current_stage: 'drone',
      field_name: '东区麦田',
      drone_label: 'PX4-01',
      progress: 65,
      pesticide_name: '吡虫啉',
      spray_area_mu: 12.5,
      is_current: true,
    }
    const result = mapTaskEntry(entry)
    expect(result.id).toBe('req-123')
    expect(result.fieldName).toBe('东区麦田')
    expect(result.droneName).toBe('PX4-01')
    expect(result.status).toBe('执行中')
    expect(result.progress).toBe(65)
    expect(result.pesticideName).toBe('吡虫啉')
    expect(result.sprayAreaText).toBe('12.5 亩')
    expect(result.isCurrent).toBe(true)
  })

  it('handles missing optional fields', () => {
    const entry = {
      request_id: 'req-456',
      status: 'pending',
      current_stage: '',
      field_name: '',
      drone_label: '',
      progress: 0,
      is_current: false,
    }
    const result = mapTaskEntry(entry)
    expect(result.pesticideName).toBe('--')
    expect(result.sprayAreaText).toBe('--')
    expect(result.updatedAt).toBe('--')
  })
})
