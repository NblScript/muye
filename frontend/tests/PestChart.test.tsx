import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import Chart1 from '../src/assets/screen/panel/chart1'

describe('insect count panel', () => {
  it('renders at most five pests with count and confidence', () => {
    render(<Chart1 pests={[
      { name: '蚜虫', count: 12, confidence: 0.932 },
      { name: '稻飞虱', count: 8, confidence: 0.86 },
      { name: '粘虫', count: 5, confidence: 0.78 },
      { name: '白粉虱', count: 3, confidence: 0.74 },
      { name: '红蜘蛛', count: 2, confidence: 0.69 },
      { name: '蝗虫', count: 1, confidence: 0.61 },
    ]} />)

    const chart = screen.getByLabelText('昆虫识别统计')
    expect(within(chart).getByText('蚜虫')).toBeInTheDocument()
    expect(within(chart).getByText('12 只')).toBeInTheDocument()
    expect(within(chart).getByText('平均置信度 93.2%')).toBeInTheDocument()
    expect(within(chart).queryByText('蝗虫')).not.toBeInTheDocument()
  })

  it('renders a clear waiting state before detections arrive', () => {
    render(<Chart1 pests={[]} />)

    expect(screen.getByText('等待 YOLO 虫情识别')).toBeInTheDocument()
  })
})
