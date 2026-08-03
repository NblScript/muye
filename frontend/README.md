# Muye Frontend

牧野前端是基于 React、TypeScript 和 Vite 的昆虫热力监测指挥大屏。

首页使用 Three.js 渲染一块虚拟田地，实时展示昆虫热力值、虫点、作业航线、无人机状态、AI 决策和复检结果。历史与设置页保留常规管理布局。

## Development

```bash
npm install
npm run dev
```

默认将 `/api` 代理到 `http://127.0.0.1:18000`，可通过 `MUYE_API_TARGET` 覆盖。

## Quality Checks

```bash
npm run lint
npm test
npm run build
```

## Data Flow

```text
FastAPI workflow state
        ↓ WebSocket / HTTP fallback
useWorkflowRealtimeState
        ↓
useDashboardState
        ↓
Screen view model
        ↓
Three.js virtual field + command panels
```

地图只表现项目内的虚拟田地，不依赖省级行政区地图或 Leaflet。
