import { useEffect, useState } from 'react'
import { Card } from '../ui'
import { listModels, switchModel, type ModelInfo } from '../../api/models'

export default function ModelSwitcher() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [activeModel, setActiveModel] = useState('')
  const [switching, setSwitching] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    const data = await listModels()
    if (data) {
      setModels(data.models)
      setActiveModel(data.active_model)
    }
  }

  useEffect(() => {
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [])

  const handleSwitch = async (modelName: string) => {
    if (modelName === activeModel || switching) return
    setSwitching(true)
    setError('')
    const result = await switchModel(modelName)
    if (result) {
      setActiveModel(result.model_name)
      await load()
    } else {
      setError('切换失败')
    }
    setSwitching(false)
  }

  if (models.length === 0) return null

  return (
    <Card className="dashboard-card">
      <span className="label-uppercase">检测模型</span>
      <div className="model-switcher">
        <select
          value={activeModel}
          onChange={(e) => handleSwitch(e.target.value)}
          disabled={switching}
          className={`model-switcher-select ${switching ? 'is-switching' : ''}`}
        >
          {models.map((m) => (
            <option key={m.name} value={m.name} disabled={!m.available}>
              {m.description || m.name}{!m.available ? ' (不可用)' : ''}
            </option>
          ))}
        </select>

        {error && (
          <div className="model-switcher-error">{error}</div>
        )}

        {models.map((m) => m.name === activeModel && (
          <div key={m.name} className="model-switcher-info">
            设备: {m.device} · 路径: {m.path.split('/').pop()}
          </div>
        ))}
      </div>
    </Card>
  )
}
