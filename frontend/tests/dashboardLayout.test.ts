import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const dashboardCss = readFileSync(resolve(__dirname, '../src/styles/dashboard.css'), 'utf8')

describe('dashboard decision module layout', () => {
  it('keeps decision modules in the main grid while stretching them horizontally', () => {
    expect(dashboardCss).toContain("'center right'")
    expect(dashboardCss).toContain("'left left'")
  })

  it('does not stretch decision modules by forcing extra height', () => {
    expect(dashboardCss).not.toMatch(
      /\.decision-flow-card,\s*\.expert-panel-card,\s*\.decision-explain-card\s*\{\s*min-height:/s,
    )
    expect(dashboardCss).not.toMatch(
      /\.decision-flow-card \.panel-body,\s*\.expert-panel-card > \.panel-body,\s*\.decision-explain-card \.panel-body\s*\{\s*min-height:/s,
    )
  })
})
