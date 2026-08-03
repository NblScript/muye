import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import MainLayout from '../src/layouts/MainLayout'

describe('MainLayout navigation', () => {
  it('gives the command screen the complete viewport', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<div>dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('dashboard').closest('.app-shell')).toHaveClass('app-shell-command')
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  })

  it('keeps navigation on regular pages without the removed drone entry', () => {
    render(
      <MemoryRouter initialEntries={['/history']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/history" element={<div>history</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('指挥台')).toBeInTheDocument()
    expect(screen.getByText('历史报表')).toBeInTheDocument()
    expect(screen.getByText('设置')).toBeInTheDocument()
    expect(screen.queryByText('无人机总览图')).not.toBeInTheDocument()
  })
})
