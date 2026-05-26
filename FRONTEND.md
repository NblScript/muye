# FRONTEND.md — 牧野前端开发规范

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| TypeScript | 6.x | 类型安全 |
| Vite | 8.x | 构建工具 |
| 自定义 UI | - | `components/ui/`（Card, Button, Tag, Toast, Drawer 等） |

## 目录结构

```
frontend/src/
├── api/               # API 调用层
│   ├── client.ts      # HTTP 客户端（axios/fetch 封装）
│   ├── health.ts      # 健康检查 API
│   ├── simMap.ts      # 仿真地图 API
│   └── workflow.ts    # 工作流 API
├── components/        # UI 组件
│   ├── dashboard/     # 仪表盘组件（DecisionFlow, DecisionExplainPanel, ExpertPanel, DJIStatusCard, ModelSwitcher, PipelineStepper, StatCard, TaskList, WeatherCard）
│   ├── map/           # 地图组件（FieldMap, StatusPanel/）
│   ├── ui/            # 通用 UI 组件（Alert, Button, Card, Drawer, Input, Progress, Select, Tag, Toast）
│   ├── workflow/      # 工作流组件（WorkflowPanel）
│   └── ErrorBoundary.tsx
├── hooks/             # 自定义 Hooks
│   ├── useEnhancedMapState.ts
│   ├── useSimMapState.ts
│   └── useWebSocket.ts
├── pages/             # 页面级组件
│   ├── Dashboard.tsx  # 主仪表盘
│   ├── History.tsx    # 任务历史
│   ├── Px4Viewer.tsx  # PX4 可视化
│   └── Settings.tsx   # 设置页
├── layouts/           # 布局
│   └── MainLayout.tsx
├── types/             # TypeScript 类型
│   ├── dashboard.types.ts
│   ├── health.ts
│   ├── simMap.ts
│   └── workflow.ts    # 含 DJITelemetry, DJIStatus 类型
├── styles/            # 样式
│   ├── dashboard.css
│   └── px4-viewer.css
├── utils/             # 工具函数
│   └── dashboardUtils.ts
├── App.tsx            # 根组件
├── main.tsx           # 入口
└── index.css          # 全局样式
```

## 组件规范

### 组件组织

- **页面组件**（`pages/`）：路由级别的完整页面，组合多个功能组件
- **功能组件**（`components/dashboard/`, `components/map/`, `components/workflow/`）：特定功能区域
- **通用组件**（`components/ui/`）：可复用的基础 UI 组件
- **布局组件**（`layouts/`）：页面骨架和导航

### 组件编写规则

```typescript
// 1. 使用函数组件 + Hooks
// 2. Props 接口定义在组件上方
interface FieldMapProps {
  points: SimPoint[];
  droneState?: SimDroneState;
  onPointClick?: (point: SimPoint) => void;
}

export function FieldMap({ points, droneState, onPointClick }: FieldMapProps) {
  // 3. Hooks 在组件顶部
  const [selectedPoint, setSelectedPoint] = useState<SimPoint | null>(null);
  
  // 4. 事件处理函数
  const handleClick = useCallback((point: SimPoint) => {
    setSelectedPoint(point);
    onPointClick?.(point);
  }, [onPointClick]);
  
  // 5. 渲染
  return (
    <div className="field-map">
      {/* SVG 地图渲染 */}
    </div>
  );
}
```

## 状态管理

### 分层策略

| 层 | 用途 | 实现 |
|----|------|------|
| 组件状态 | 单组件内部状态 | `useState` |
| 共享状态 | 跨组件状态 | React Context + Hooks |
| 服务端状态 | API 数据缓存 | 自定义 Hooks（`useSimMapState`） |
| WebSocket 状态 | 实时数据 | `useWebSocket` Hook |

### 数据获取模式

```typescript
// 优先使用 WebSocket 实时通道
// 降级到 HTTP 轮询
function useSimMapState() {
  const wsState = useWebSocket('/sim/ws');
  const [httpState, setHttpState] = useState<SimMapState | null>(null);
  
  useEffect(() => {
    if (!wsState.connected) {
      // WebSocket 断开时降级到 HTTP 轮询
      const interval = setInterval(async () => {
        const data = await simMapApi.getState();
        setHttpState(data);
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [wsState.connected]);
  
  return wsState.connected ? wsState.data : httpState;
}
```

## 样式规范

- **主题**：暗色主题（CSS 变量驱动）
- **全局样式**：`index.css` 定义 CSS 变量和基础样式
- **组件样式**：`components/ui/` 自定义组件 + `styles/dashboard.css`
- **响应式**：大屏展示为主，支持 1920x1080 分辨率
- **地图样式**：SVG 渲染，`styles/` 目录存放专用样式

## API 调用

```typescript
// api/client.ts — 统一 HTTP 客户端
const client = axios.create({
  baseURL: '/api',
  timeout: 10000,
});

// 响应拦截器：统一错误处理
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    Toast.error(error.response?.data?.detail || '请求失败');
    return Promise.reject(error);
  }
);
```

## 构建与开发

```bash
# 开发
cd frontend && npm run dev      # 启动开发服务器（端口 5173）

# 构建
npm run build                   # 生产构建到 dist/

# 测试
npm run test                    # 运行前端测试
```

## 关键依赖

| 包 | 用途 |
|----|------|
| `axios` | HTTP 客户端 |
| `react-router-dom` | 路由 |
| `leaflet` + `react-leaflet` | 地图渲染 |
