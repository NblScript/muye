import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import MainLayout from '../src/layouts/MainLayout'

describe('MainLayout navigation', () => {
  it('does not expose the removed drone overview entry', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<div>dashboard</div>} />
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
