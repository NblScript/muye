import { BarChart, PictorialBarChart, type BarSeriesOption, type PictorialBarSeriesOption } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  type GridComponentOption,
  type TooltipComponentOption,
} from 'echarts/components'
import type { ComposeOption } from 'echarts/core'
import { LabelLayout } from 'echarts/features'
import styled from 'styled-components'
import Chart from '../Chart'
import type { PestMetric } from '../model'

type BarOption = ComposeOption<
  BarSeriesOption | PictorialBarSeriesOption | TooltipComponentOption | GridComponentOption
>

const Empty = styled.div`
  height: 100%;
  display: grid;
  place-items: center;
  color: rgba(90, 74, 66, 0.55);
  font-size: 14px;
  letter-spacing: 0.08em;
`

export default function Chart1({ pests }: { pests: PestMetric[] }) {
  if (pests.length === 0) return <Empty>等待 YOLO 虫情识别</Empty>

  const data = pests.slice(0, 5)
  const maxCount = Math.max(1, ...data.map((item) => item.count))

  return (
    <Chart<BarOption>
      use={[BarChart, PictorialBarChart, GridComponent, TooltipComponent, LabelLayout]}
      option={{
        grid: { top: 8, bottom: 4, left: 82, right: 48 },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
          backgroundColor: 'rgba(255, 248, 238, 0.96)',
          borderColor: '#e9a34b',
          textStyle: { color: '#4e4038' },
          formatter: (params) => {
            const items = Array.isArray(params) ? params : [params]
            const index = Number(items[0]?.dataIndex ?? 0)
            const pest = data[index]
            return pest
              ? `${pest.name}<br/>检测数量：${pest.count}<br/>平均置信度：${(pest.confidence * 100).toFixed(1)}%`
              : ''
          },
        },
        xAxis: { show: false, max: Math.ceil(maxCount * 1.18) },
        yAxis: {
          type: 'category',
          inverse: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: '#5a4a42', fontSize: 14, margin: 14 },
          data: data.map((item) => item.name),
        },
        series: [
          {
            type: 'bar',
            barWidth: 9,
            showBackground: true,
            backgroundStyle: { color: 'rgba(234, 88, 12, 0.08)', borderRadius: 6 },
            itemStyle: {
              borderRadius: 6,
              color: {
                type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
                colorStops: [
                  { offset: 0, color: '#f6c56d' },
                  { offset: 1, color: '#ea580c' },
                ],
              },
            },
            label: {
              show: true,
              position: 'right',
              color: '#b84f10',
              fontWeight: 700,
              formatter: (params) => `${params.value ?? 0} 只`,
            },
            data: data.map((item) => item.count),
          },
          {
            type: 'pictorialBar',
            symbol: 'circle',
            symbolSize: 15,
            symbolPosition: 'end',
            z: 4,
            itemStyle: { color: '#ffb34d', shadowColor: '#ea580c', shadowBlur: 12 },
            data: data.map((item) => item.count),
          },
        ],
      }}
    />
  )
}
