import { useEffect, useState, type ComponentProps } from 'react'
import styled from 'styled-components'
import type { ScreenViewModel } from '../model'

const TitleWrapper = styled.div`
  position: relative;
  width: 100%;
  height: 80px;
  flex: 0 0 80px;
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 5;
  pointer-events: none;
  color: #fff;
  border: 1px solid rgba(141, 141, 141, 0.22);
  background: rgba(12, 18, 19, 0.58);
  backdrop-filter: blur(10px);
`

const Title = styled.div`
  color: #fff;
  font-size: 36px;
  font-weight: 700;
  letter-spacing: 8px;
  text-align: center;
  text-shadow: 0 0 18px rgba(127, 229, 168, 0.16);

  &::after {
    content: 'MUYE PEST HEATMAP COMMAND CENTER';
    display: block;
    margin-top: -5px;
    color: rgba(127, 229, 168, 0.62);
    font-size: 10px;
    letter-spacing: 9px;
  }
`

const SideInfo = styled.div<{ $side: 'left' | 'right' }>`
  position: absolute;
  top: 14px;
  ${({ $side }) => $side}: 30px;
  width: 300px;
  color: rgba(255,255,255,.82);
  text-align: ${({ $side }) => $side};
  .primary { font-size: 13px; font-weight: 650; }
  .secondary { margin-top: 4px; color: rgba(255,255,255,.42); font-size: 10px; }
`

const LiveDot = styled.span<{ $online: boolean }>`
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 50%;
  background: ${({ $online }) => $online ? '#7fe5a8' : '#d6b56f'};
  box-shadow: 0 0 9px currentColor;
`

const Bg = styled.svg.attrs({ viewBox: '0 0 1920 82', preserveAspectRatio: 'none' })`
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
`

function formatClock(date: Date) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(date)
}

export interface HeaderProps extends ComponentProps<typeof TitleWrapper> { model: ScreenViewModel }

export default function Header({ model, ...props }: HeaderProps) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <TitleWrapper {...props}>
      <Bg>
        <defs>
          <radialGradient id="header-glow" cx="50%" cy="50%" fx="100%" fy="50%" r="50%"><stop offset="0%" stopColor="#fff" /><stop offset="100%" stopColor="#fff" stopOpacity="0" /></radialGradient>
          <mask id="header-line-left"><circle r="100" fill="url(#header-glow)"><animateMotion dur="3s" path="M0,60 L620,60 L670,80 L960,80" repeatCount="indefinite" /></circle></mask>
          <mask id="header-line-right"><circle r="100" fill="url(#header-glow)"><animateMotion dur="3s" path="M1920,60 L1300,60 L1250,80 L960,80" repeatCount="indefinite" /></circle></mask>
        </defs>
        <path d="M0,0 L1920,0 L1920,60 L1300,60 L1250,80 L670,80 L620,60 L0,60 Z" fill="rgba(16,22,23,.62)" />
        <path d="M0,60 L620,60 L670,80 L1250,80 L1300,60 L1920,60" fill="none" stroke="rgba(127,229,168,.52)" strokeWidth="1" />
        <path d="M0,60 L620,60 L670,80 L960,80" fill="none" stroke="#7fe5a8" strokeWidth="3" mask="url(#header-line-left)" />
        <path d="M1920,60 L1300,60 L1250,80 L960,80" fill="none" stroke="#7fe5a8" strokeWidth="3" mask="url(#header-line-right)" />
      </Bg>
      <SideInfo $side="left"><div className="primary"><LiveDot $online={model.connected} />{model.connected ? '实时数据链路' : '轮询数据链路'}</div><div className="secondary">任务 {model.requestId}</div></SideInfo>
      <Title>牧野昆虫热力监测大屏</Title>
      <SideInfo $side="right"><div className="primary">{formatClock(now)}</div><div className="secondary">{model.field.name} · {model.statusLabel}</div></SideInfo>
    </TitleWrapper>
  )
}
