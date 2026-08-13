import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import MainLayout from '../src/layouts/MainLayout'
import { BrowserRouter } from '../src/router'

describe('MainLayout navigation', () => {
  it('gives the command screen the complete viewport', () => {
    window.history.replaceState(null, '', '/')
    render(
      <BrowserRouter>
        <MainLayout><div>dashboard</div></MainLayout>
      </BrowserRouter>,
    )

    expect(screen.getByText('dashboard').closest('.app-shell')).toHaveClass('app-shell-command')
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  })

  it('keeps navigation on regular pages without the removed drone entry', async () => {
    window.history.replaceState(null, '', '/history')
    render(
      <BrowserRouter>
        <MainLayout><div>history</div></MainLayout>
      </BrowserRouter>,
    )

    expect(screen.getByText('指挥台')).toBeInTheDocument()
    expect(screen.getByText('历史报表')).toBeInTheDocument()
    expect(screen.getByText('设置')).toBeInTheDocument()
    expect(screen.queryByText('无人机总览图')).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('设置'))
    expect(window.location.pathname).toBe('/settings')
    expect(screen.getByText('设置').closest('a')).toHaveClass('is-active')
  })
})
