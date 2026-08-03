import type { ComponentProps } from 'react'
import styled from 'styled-components'
import type { ScreenViewModel } from '../model'
import { useConfigStore } from '../store'

const Wrapper = styled.div`
  position: absolute;
  bottom: 0;
  width: 100%;
  height: 100px;
`

const Buttons = styled.div`
  position: absolute;
  z-index: 10;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 720px;
  height: 80px;
  padding-bottom: 20px;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  gap: 22px;
`

const Button = styled.button<{ $active?: boolean; $urgent?: boolean }>`
  position: relative;
  width: 50px;
  height: 50px;
  overflow: hidden;
  border: 1px solid rgba(234,88,12,.2);
  border-radius: 12px;
  color: #d35400;
  background: rgba(255,255,255,.9);
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  pointer-events: auto;
  transition: all .3s cubic-bezier(.4,0,.2,1);

  &::before { content: ''; position: absolute; inset: 0; background: linear-gradient(135deg,rgba(234,88,12,.1),transparent); opacity: 0; transition: opacity .3s; }
  &:hover:not(:disabled) { transform: translateY(-5px) scale(1.1); border-color: #ff6715; box-shadow: 0 0 15px rgba(255,103,21,.4); color: #ff6715; }
  &:hover::before { opacity: 1; }
  &:disabled { opacity: .42; cursor: not-allowed; }

  ${({ $active, $urgent }) => ($active || $urgent) && `
    width: 60px;
    height: 60px;
    margin-bottom: 5px;
    border: none;
    color: white;
    background: linear-gradient(135deg, ${$urgent ? '#c43a21' : '#ff6715'} 0%, ${$urgent ? '#eb6b32' : '#ff8c00'} 100%);
    box-shadow: 0 4px 15px rgba(255,103,21,.5);
  `}

  svg { position: relative; z-index: 1; width: 24px; height: 24px; }
`

const Bg = () => (
  <svg viewBox="0 0 1920 100" preserveAspectRatio="none" width="100%" height="100%">
    <defs><linearGradient id="footer-gradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff5e8" stopOpacity=".5" /><stop offset="1" stopColor="#fff5e8" /></linearGradient></defs>
    <path d="M0,100 H1920 V100 Q1600,100 1450,100 Q1300,80 1200,60 Q960,10 720,60 Q620,80 470,100 Q320,100 0,100 Z" fill="url(#footer-gradient)" />
    <path d="M0,100 Q320,100 470,100 Q620,80 720,60 Q960,10 1200,60 Q1300,80 1450,100 Q1600,100 1920,100" fill="none" stroke="#ff6715" strokeWidth="1" strokeOpacity=".4" />
    <path d="M720,60 Q960,10 1200,60" fill="none" stroke="#ff6715" strokeWidth="2" strokeLinecap="round" />
  </svg>
)

const UploadIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><path d="M7 8l5-5 5 5M12 3v12" /></svg>
const CloudIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.5 19H7a5 5 0 01-.8-9.94A7 7 0 0119.7 11.5 4 4 0 0117.5 19z" /></svg>
const RotationIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 7h-5V2" /><path d="M20 7a9 9 0 10.6 9" /></svg>
const ModeIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>
const HeatIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22a7 7 0 007-7c0-5-7-13-7-13S5 10 5 15a7 7 0 007 7z" /><path d="M9 16c1.2-2 2.1-3.1 3-5 1.5 2.1 3 3.5 3 5a3 3 0 01-6 0z" /></svg>
const PestIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="13" rx="5" ry="7" /><path d="M9 6L7 3M15 6l2-3M7 10H3M17 10h4M7 15H3M17 15h4M9 20l-2 2M15 20l2 2M12 6v14" /></svg>
const RefreshIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 7h-5V2" /><path d="M20 7a9 9 0 10.6 9" /></svg>
const TakeoffIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3l4 8h-3v8h-2v-8H8l4-8z" /><path d="M4 21h16" /></svg>

export interface FooterActions {
  uploading: boolean
  workflowLoading: boolean
  confirmingTakeoff: boolean
  showTakeoff: boolean
  onUpload: () => void
  onRefresh: () => void
  onConfirmTakeoff: () => void
}

export interface FooterProps extends ComponentProps<typeof Wrapper> {
  model: ScreenViewModel
  actions: FooterActions
}

export default function Footer({ model, actions, ...props }: FooterProps) {
  const { cloud, rotation, mode, heat, bar, toggle } = useConfigStore()
  return (
    <Wrapper {...props}>
      <Bg />
      <Buttons aria-label="大屏控制区">
        <Button title="接入巡检图像" $active={actions.uploading} disabled={actions.uploading} onClick={actions.onUpload}><UploadIcon /></Button>
        <Button title="云层效果" $active={cloud} onClick={() => toggle('cloud')}><CloudIcon /></Button>
        <Button title="旋转底座" $active={rotation} onClick={() => toggle('rotation')}><RotationIcon /></Button>
        <Button title="显示业务面板" $active={mode} onClick={() => toggle('mode')}><ModeIcon /></Button>
        <Button title="显示昆虫热力值" $active={heat} disabled={model.fieldTwin.heatCells.length === 0} onClick={() => toggle('heat')}><HeatIcon /></Button>
        <Button title="显示虫点标记" $active={bar} disabled={model.fieldTwin.pestPoints.length === 0} onClick={() => toggle('bar')}><PestIcon /></Button>
        <Button title="同步真实数据" disabled={actions.workflowLoading} onClick={actions.onRefresh}><RefreshIcon /></Button>
        {actions.showTakeoff && <Button title="确认执行真实任务" $urgent disabled={actions.confirmingTakeoff} onClick={actions.onConfirmTakeoff}><TakeoffIcon /></Button>}
      </Buttons>
    </Wrapper>
  )
}
