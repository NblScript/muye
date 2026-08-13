declare module 'keli-heatmap.js' {
  interface HeatmapPoint {
    x: number
    y: number
    value: number
    radius?: number
  }

  interface HeatmapInstance {
    setData(data: { min?: number; max: number; data: HeatmapPoint[] }): HeatmapInstance
    _renderer: { canvas: HTMLCanvasElement }
  }

  interface HeatmapConfig {
    container: HTMLElement
    gradient?: Record<number, string>
    blur?: number
    radius?: number
    maxOpacity?: number
    minOpacity?: number
    width?: number
    height?: number
  }

  const heatmap: {
    create(config: HeatmapConfig): HeatmapInstance
  }

  export default heatmap
}
