import { useState } from 'react'

interface Scenario {
  id: string
  name: string
  desc: string
  icon: string
  image: string
}

const SCENARIOS: Scenario[] = [
  {
    id: 'aphid_normal',
    name: '小麦蚜虫',
    desc: '正常天气，RAG 启用，顺利施药',
    icon: '🦟',
    image: 'aphids_01.jpg',
  },
  {
    id: 'planthopper_humid',
    name: '稻飞虱',
    desc: '高湿天气，合规风险提示',
    icon: '🐛',
    image: 'brown_planthopper_01.jpg',
  },
  {
    id: 'wind_high',
    name: '风速过高',
    desc: '大风天气，AI 建议暂缓喷洒',
    icon: '💨',
    image: 'aphids_02.jpg',
  },
  {
    id: 'rag_down',
    name: 'RAG 故障',
    desc: '知识库不可用，降级但流程不中断',
    icon: '📚',
    image: 'aphids_01.jpg',
  },
  {
    id: 'px4_down',
    name: 'PX4 离线',
    desc: '无人机仿真不可用，动画演示模式',
    icon: '🚁',
    image: 'aphids_02.jpg',
  },
]

interface Props {
  apiBase?: string
  onStarted?: (scenarioId: string) => void
}

export default function DemoScenarioCards({ apiBase = '/api', onStarted }: Props) {
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleRun = async (scenario: Scenario) => {
    setLoading(scenario.id)
    setError(null)

    try {
      const resp = await fetch(`${apiBase}/demo/reset-events`, { method: 'POST' })
      if (!resp.ok) throw new Error('重置事件失败')

      const formData = new FormData()
      formData.append('file', scenario.image)

      const uploadResp = await fetch(`${apiBase}/demo/upload-image`, {
        method: 'POST',
        body: formData,
      })

      if (!uploadResp.ok) {
        const body = await uploadResp.json().catch(() => ({}))
        throw new Error(body.detail || '上传失败')
      }

      onStarted?.(scenario.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={{ padding: '0 12px', marginBottom: 8 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>演示场景</div>
      <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
        {SCENARIOS.map((s) => {
          const isLoading = loading === s.id
          return (
            <button
              key={s.id}
              onClick={() => handleRun(s)}
              disabled={loading !== null}
              style={{
                flex: '0 0 auto',
                width: 140,
                padding: '8px 10px',
                background: isLoading ? 'var(--bg-elevated)' : 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                cursor: loading ? 'wait' : 'pointer',
                textAlign: 'left',
                transition: 'var(--transition-fast)',
                opacity: loading !== null && !isLoading ? 0.5 : 1,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 16 }}>{s.icon}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {s.name}
                </span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                {s.desc}
              </div>
            </button>
          )
        })}
      </div>
      {error && (
        <div style={{ fontSize: 11, color: 'var(--accent-red)', marginTop: 4 }}>{error}</div>
      )}
    </div>
  )
}
