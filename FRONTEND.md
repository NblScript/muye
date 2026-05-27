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
│   ├── models.ts      # 模型切换 API
│   ├── simMap.ts      # 仿真地图 API
│   └── workflow.ts    # 工作流 API
├── components/        # UI 组件
│   ├── dashboard/     # 仪表盘组件（DecisionFlow, DecisionExplainPanel, ExpertPanel, DJIStatusCard,
│   │                  #   DemoScenarioCards, ModelSwitcher, PipelineStepper, StatCard, TaskList, WeatherCard）
│   ├── map/           # 地图组件（FieldMap, StatusPanel/）
│   ├── ui/            # 通用 UI 组件（Alert, Button, Card, Drawer, Input, Progress, Select, Tag, Toast）
│   ├── workflow/      # 工作流组件（WorkflowPanel）
│   └── ErrorBoundary.tsx
├── hooks/             # 自定义 Hooks
│   ├── useDashboardState.ts   # Dashboard 页面全部状态与逻辑
│   ├── useEnhancedMapState.ts # 实时地图状态（WebSocket + HTTP 降级）
│   ├── useSimMapState.ts
│   └── useWebSocket.ts
├── pages/             # 页面级组件
│   ├── Dashboard.tsx  # 主仪表盘（纯渲染，逻辑在 useDashboardState）
│   ├── History.tsx    # 任务历史报表
│   ├── Px4Viewer.tsx  # PX4 可视化
│   └── Settings.tsx   # 系统设置页
├── layouts/           # 布局
│   └── MainLayout.tsx
├── types/             # TypeScript 类型
│   ├── dashboard.types.ts
│   ├── health.ts
│   ├── simMap.ts
│   └── workflow.ts    # 含 DJITelemetry, DJIStatus 类型
├── styles/            # 样式
│   ├── dashboard.css  # 主样式表（组件类、动画、响应式）
│   └── px4-viewer.css
├── utils/             # 工具函数
│   └── dashboardUtils.ts  # asRecord, modeColor, statusColor, summarizePests, formatPestLabel 等
├── App.tsx            # 根组件
├── main.tsx           # 入口
└── index.css          # 全局样式（CSS 变量、动画、工具类）
```

## 组件规范

### 组件组织

- **页面组件**（`pages/`）：路由级别的完整页面，组合多个功能组件
  - Dashboard 页面遵循 **Hook + 纯渲染** 模式：`useDashboardState()` 管理全部状态和事件处理，页面组件只负责 JSX 渲染
- **功能组件**（`components/dashboard/`, `components/map/`, `components/workflow/`）：特定功能区域
- **通用组件**（`components/ui/`）：可复用的基础 UI 组件
- **布局组件**（`layouts/`）：页面骨架和导航

### 组件编写规则

```typescript
// 1. 使用函数组件 + Hooks
// 2. Props 接口定义在组件上方
interface FieldMapProps {
  droneStatus?: string;
  detections?: WorkflowDetectionEntry[];
}

export function FieldMap({ droneStatus, detections }: FieldMapProps) {
  // 3. Hooks 在组件顶部
  // 4. 颜色常量语义化命名
  const C = { fieldActive: '#089cc5', fieldCompleted: '#16875a', ... };

  // 5. 使用 CSS 类替代 inline style（仅动态值保留 inline）
  return (
    <div className="field-map">
      <svg>...</svg>
    </div>
  );
}
```

## 状态管理

### 分层策略

| 层 | 用途 | 实现 |
|----|------|------|
| 页面状态 | Dashboard 全部状态 + 事件处理 | `useDashboardState()` Hook |
| 组件状态 | 单组件内部状态 | `useState` |
| 共享状态 | 跨组件状态 | React Context + Hooks |
| 服务端状态 | API 数据缓存 | 自定义 Hooks（`useEnhancedMapState`） |
| WebSocket 状态 | 实时数据 | `useWebSocket` Hook |

### useDashboardState 模式

Dashboard 页面使用 `useDashboardState()` 自定义 Hook 封装全部状态、派生数据、定时器和事件处理函数。页面组件仅负责渲染，不包含任何业务逻辑。

```typescript
// pages/Dashboard.tsx
export default function Dashboard() {
  const toast = useToast()
  const s = useDashboardState()
  return <div>...</div>  // 纯渲染
}

// hooks/useDashboardState.ts
export function useDashboardState() {
  // 全部 useState、useEffect、useMemo、事件处理函数
  return { demoMode, latestTask, handleUploadClick, ... }
}
```

## 样式规范

### 设计系统

- **主题**：暖色奶油色调（CSS 变量驱动），专为竞赛演示优化
- **全局样式**：`index.css` 定义 CSS 变量（`--accent-amber`, `--accent-red`, `--bg-card` 等）、动画关键帧（`fadeSlideUp`, `shimmer`）和工具类（`.page-container`, `.page-title`, `.color-error`）
- **组件样式**：`styles/dashboard.css` 包含所有组件 CSS 类
- **响应式**：大屏展示为主（1920x1080），支持 720px+ 移动端适配

### 样式编写规则

1. **禁止静态 inline style**：所有静态样式（颜色、布局、间距、字号）必须提取为 CSS 类
2. **动态值允许 inline**：仅百分比宽度（`width: ${progress}%`）、动态颜色查找可使用 `style={{}}`
3. **颜色常量**：SVG 组件中的硬编码颜色使用语义化常量对象（如 FieldMap 的 `const C = { fieldActive: '#089cc5', ... }`）
4. **CSS 修饰类**：颜色变体使用 `.is-red`, `.is-active` 等修饰类，不使用 inline `color`
5. **动画**：入场动画通过 `animation-delay` 配合 `:nth-child(n)` 实现交错效果

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
npx vitest run                  # 运行前端测试（52 个用例）
```

## 关键依赖

| 包 | 用途 |
|----|------|
| `axios` | HTTP 客户端 |
| `react-router-dom` | 路由 |
