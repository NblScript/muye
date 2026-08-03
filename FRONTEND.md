# FRONTEND.md — 牧野前端开发规范

## 前端定位

`frontend/` 是牧野唯一前端主线。首页是面向竞赛展示和真实作业监控的昆虫热力指挥大屏；历史与设置页用于任务追溯和运行诊断。

首页只展示来自后端 `event_bus` 的真实工作流数据。田地几何可以使用项目内的虚拟地块，但不得接入省级行政地图，也不得在前端随机生成虫情、天气、决策或无人机状态。

## 技术栈

| 技术 | 用途 |
|------|------|
| React 19 + TypeScript 6 | UI 与类型边界 |
| Vite 8 | 开发服务器、代理和生产构建 |
| Three.js + React Three Fiber | 虚拟田地、航线、无人机和热力层 |
| keli-heatmap.js | 生成热力纹理与高度灰度纹理 |
| styled-components | 指挥大屏组件样式 |
| Zustand | 大屏面板和图层开关状态 |
| GSAP | 地图入场与面板过渡 |
| Axios | HTTP API 客户端 |
| Vitest + React Testing Library | 单元与渲染测试 |

## 当前目录结构

```text
frontend/src/
├── api/
│   ├── client.ts              # /api 基础地址、超时和错误转换
│   ├── health.ts              # readiness/health
│   ├── realtime.ts            # WebSocket URL
│   └── workflow.ts            # 状态、历史、上传、起飞确认
├── assets/screen/
│   ├── Screen.tsx             # 指挥大屏组合入口
│   ├── model.ts               # WorkflowTaskState -> ScreenViewModel
│   ├── store.ts               # 大屏共享展示状态
│   ├── map/                   # Three.js 虚拟田地、热力层和航线几何
│   ├── panel/                 # 顶栏、轻量统计面板和底部操作栏
│   └── hooks/                 # 面板过渡工具
├── components/
│   ├── ui/                    # 历史/设置页共用基础组件
│   └── ErrorBoundary.tsx
├── hooks/
│   ├── useDashboardState.ts   # 首页状态、上传与起飞操作
│   ├── useWorkflowRealtimeState.ts
│   └── useWebSocket.ts        # WS 重连 + HTTP 轮询降级
├── layouts/MainLayout.tsx
├── pages/
│   ├── Dashboard.tsx          # 首页，懒加载 Screen
│   ├── History.tsx
│   └── Settings.tsx
├── types/
│   ├── health.ts
│   ├── workflow.ts
│   └── keli-heatmap.d.ts
├── utils/
│   ├── dashboardUtils.ts
│   ├── pipelineStages.ts
│   └── workflowState.ts       # 实时工作流校验与最后有效帧保留
├── App.tsx
├── index.css                  # 全局/辅助页面样式
└── main.tsx
```

删除或移动上述关键入口时，必须同步更新本文件、相关测试和 `vite.config.ts` 的构建分包规则。

## 首页数据流

```text
GET /api/workflow/state ─┐
                        ├─ useWebSocket / useWorkflowRealtimeState
WS /api/ws/enhanced-state ┘
            │
            ▼
retainLatestEventBusTask
            │
            ▼
useDashboardState
            │
            ▼
buildScreenViewModel
            │
       ┌────┴────┐
       ▼         ▼
  Three.js 地图   React/CSS 信息面板
```

数据边界规则：

1. 首页只接受 `source === "event_bus"` 且结构完整的 `latest_task`。
2. `source === "fallback"` 是旧消费者兼容数据，不能进入首页真实指标。
3. WebSocket 某一帧为 `workflow_state: null`、回退包或畸形包时，保留最后一帧有效任务，避免热力层闪烁。
4. WebSocket 断开后由 `useWebSocket` 启动 HTTP 轮询，并按指数退避重连；恢复后只提示一次。
5. 映射层必须容忍可选业务字段，但不能用硬编码演示值填充真实指标。

## 昆虫热力图规则

热力数据优先使用：

```text
latest_task.drone.instruction.density_grid
```

每个网格包含 `density`（0–1）和 GPS `bounds`。`density` 是检测置信度按网格累加、再除以当前任务最大网格权重得到的**相对热值**，不是每亩虫口数或农艺防治阈值。`buildScreenViewModel()` 将其归一化到虚拟田地坐标，`FieldHeatmap` 使用同一份数据生成彩色纹理和高度纹理。

`latest_task.drone.instruction.density_metadata` 标注热力数据的来源、坐标空间、投影方式、有效/拒绝检测框数量和 `is_simulated`。大屏必须显示真实或模拟来源；不得把演示热力值标成 YOLO 实测数据。

YOLO 像素检测框必须携带 `coordinate_space: "image_pixel"`、`image_width` 和 `image_height`；归一化框使用 `coordinate_space: "image_normalized"` 且坐标范围为 0–1。缺少图像尺寸的像素框不能参与真实密度网格。该约定与 Ultralytics 的 `xyxy`（像素）和 `xyxyn`（归一化）定义一致：<https://docs.ultralytics.com/modes/predict/>。

当后端尚未生成密度网格但已有检测框时，可由检测位置生成确定性的虫点热区；没有真实检测时保持空热力状态。禁止使用 `Math.random()`、定时扰动或每帧重算随机热点。

稳定性约束：

- 同一份 `heatCells` 内容不重建纹理。
- 纹理替换后必须释放旧的 `CanvasTexture`。
- 热力图可显隐，但显隐不能改变数据。
- 虚拟田地边界固定为项目内部坐标，真实 GPS 只用于地块内归一化。
- 当前投影把整张巡检图像的上、下、左、右边缘映射到地块外接矩形，默认图像北向且覆盖整个田块；接入正射影像或相机位姿前，不宣称单个虫点具有测绘级 GPS 精度。

## 组件和状态规范

- 页面组件只组合功能；上传、刷新、连接和起飞确认放在 `useDashboardState()`。
- 后端原始结构到展示结构的转换集中在 `assets/screen/model.ts`，面板组件不得重复解析业务 JSON。
- 跨地图和面板的纯展示状态使用 `assets/screen/store.ts`；服务端状态不得复制进 Zustand。
- 可复用的运行时校验放在 `utils/`，同时提供纯函数测试。
- Three.js 创建的纹理、材质、几何体或计时器必须在 effect cleanup 中释放。
- 不要在 render 阶段创建网络连接或 Three.js 资源。
- 首页使用固定相机目标保持竞赛展示视角；不要重新引入轨道控制或允许误操作改变视角。
- 地图标题、热力图例和等待提示使用 DOM 覆盖层，三维场景只渲染确实需要透视关系的对象。

## API 与代理

浏览器统一请求 `/api`：

- `GET /workflow/state`：最新工作流聚合状态
- `GET /workflow/history`：任务历史
- `POST /workflow/inspection-image`：上传巡检图像
- `POST /drone/confirm-takeoff`：人工确认起飞
- `GET /health`：设置页运行诊断
- `WS /ws/enhanced-state`：实时工作流状态

开发环境由 Vite 将 `/api` 代理到 `MUYE_API_TARGET`，默认 `http://127.0.0.1:18000`。WebSocket URL 必须通过 `api/realtime.ts` 生成，以自动适配 `ws/wss`。

## 样式与适配

- 首页大屏设计基准为 1920×1080，由 `panel/autoFit.tsx` 等比适配浏览器窗口。
- 首页视觉由 `assets/screen/` 内的 styled-components 管理；历史和设置页沿用 `index.css` 的全局变量。
- 信息必须在 16:9 屏幕完整可见；新增面板前先验证 1366×768、1920×1080 和浏览器缩放场景。
- 静态色值尽量集中在组件主题或语义常量中，动态坐标和进度允许 inline style。
- 动画只表达状态变化，不得让热力值、统计数字或连接状态持续闪烁。

## 测试要求

至少覆盖以下边界：

- `DashboardOverview.test.tsx`：首页把实时状态和操作传给大屏。
- `PestChart.test.tsx`：虫情统计数量、置信度、最多五类和空状态。
- `RouteGeometry.test.ts`：连续航线、虚线分段和重复航点边界。
- `ScreenModel.test.ts`：真实工作流到地块、虫情、决策、无人机、复检和热力模型的映射。
- `workflowState.test.ts`：空包、回退包和畸形包不会覆盖最后有效任务。
- `PipelineStepper.test.ts`：处理阶段和进度派生。
- `MainLayoutNavigation.test.tsx`：辅助页面导航。
- `dashboardUtils.test.ts`：公共展示工具。

提交前运行：

```bash
cd frontend
npm run lint
npm test -- --run
npm run build
```

构建中的大型 Three.js vendor chunk 提示目前是已知提示；首页 `Screen` 已懒加载，历史和设置页也按路由加载，不应把这些依赖重新合并进首屏入口 chunk。

## 常见错误

- 把后端 `fallback` 演示状态当成真实虫情。
- WebSocket 空包到达时把 `latestTask` 清空，造成热力层闪烁。
- 在前端用随机值补齐虫点、天气或无人机轨迹。
- 同时维护多套地图或 Dashboard 实现。
- 面板组件直接读取中文业务键并各自实现转换。
- 忘记释放 Three.js/GSAP 资源。
- 修改 API 字段后只改 TypeScript 类型，没有同步后端 schema 和契约测试。
