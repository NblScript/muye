import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import useMoveTo from '../src/assets/screen/hooks/useMoveTo'

function Probe({ onClickRestart }: { onClickRestart?: (restart: () => void) => void }) {
  const { ref, restart } = useMoveTo<HTMLDivElement>('toRight', 0.8, 0.5)
  return (
    <div>
      <button type="button" onClick={() => onClickRestart?.(restart)}>restart</button>
      <div ref={ref} data-testid="probe">内容</div>
    </div>
  )
}

function setMatchMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockReturnValue({
      matches,
      media: '(prefers-reduced-motion: reduce)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useMoveTo reduced motion', () => {
  it('keeps the final state without animation when reduced motion is preferred', () => {
    setMatchMedia(true)

    render(<Probe />)

    const probe = screen.getByTestId('probe')
    // 不应被 gsap 置为透明或移出屏幕：直接保持最终状态
    expect(probe.style.opacity).toBe('')
    expect(probe.style.transform).toBe('')
  })

  it('still creates the entrance tween in normal motion environments', () => {
    setMatchMedia(false)

    render(<Probe />)

    const probe = screen.getByTestId('probe')
    // gsap fromTo 创建时立即渲染起始状态：透明（位移在 jsdom 中无布局尺寸，不做断言）
    expect(Number(probe.style.opacity)).toBe(0)
  })
})
