import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import FieldMap from '../src/components/map/FieldMap'

describe('FieldMap drone marker', () => {
  it('renders a visual drone marker without the old text label', () => {
    render(<FieldMap droneStatus="spraying" />)

    expect(screen.getByRole('img', { name: '当前作业地图' })).toBeInTheDocument()
    expect(screen.queryByText('无人机')).not.toBeInTheDocument()
    expect(document.querySelector('[data-testid="drone-marker"]')).toBeInTheDocument()
  })
})
