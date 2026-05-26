export interface ModelInfo {
  name: string
  path: string
  device: string
  description: string
  available: boolean
  active: boolean
}

export interface ModelsResponse {
  active_model: string
  models: ModelInfo[]
}

export async function listModels(): Promise<ModelsResponse | null> {
  try {
    const resp = await fetch('http://localhost:8010/models')
    if (!resp.ok) return null
    return resp.json()
  } catch {
    return null
  }
}

export async function switchModel(modelName: string): Promise<{ model_name: string } | null> {
  try {
    const resp = await fetch('http://localhost:8010/models/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_name: modelName }),
    })
    if (!resp.ok) return null
    return resp.json()
  } catch {
    return null
  }
}
