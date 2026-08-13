# Frontend Project Structure

```text
frontend/
├── public/                         # 字体和原样复制的静态资源
├── src/
│   ├── api/
│   │   ├── client.ts               # Axios `/api` 客户端
│   │   ├── health.ts               # 健康检查
│   │   ├── realtime.ts             # 工作流 WebSocket 地址
│   │   └── workflow.ts             # 工作流、历史和控制接口
│   ├── assets/screen/
│   │   ├── Screen.tsx              # 指挥大屏入口
│   │   ├── model.ts                # 后端状态到大屏视图模型的映射
│   │   ├── map/                    # Three.js 虚拟田地与静态热力图
│   │   └── panel/                  # 虫情、天气、决策、无人机和评估面板
│   ├── components/ui/              # 历史和设置页共享 UI
│   ├── hooks/
│   │   ├── useDashboardState.ts    # 首页交互状态
│   │   ├── useWorkflowRealtimeState.ts # WebSocket / HTTP 降级入口
│   │   └── useWebSocket.ts         # 重连与轮询机制
│   ├── layouts/MainLayout.tsx      # 大屏与常规页面布局切换
│   ├── pages/
│   │   ├── Dashboard.tsx           # 昆虫热力监测大屏
│   │   ├── History.tsx             # 任务历史
│   │   └── Settings.tsx            # 系统状态与配置
│   ├── types/                      # API 与热力图库类型
│   ├── utils/                      # 状态颜色与管线进度纯函数
│   ├── App.tsx                     # 路由入口
│   ├── index.css                   # 全局与常规页面样式
│   └── main.tsx                    # React 挂载入口
├── tests/                          # 当前入口和纯业务映射测试
├── package.json
└── vite.config.ts                  # API 代理与依赖分包
```

## Boundaries

- 昆虫热力图使用真实工作流的 `density_grid`，没有数据时保持空状态。
- 虚拟田地负责可视化，不在前端制造后端任务或随机热力数据。
- 首页不请求历史列表；历史查询只在 `/history` 页面发生。
- 省级地图、Leaflet 旧地图和旧演示仪表盘已移除。
