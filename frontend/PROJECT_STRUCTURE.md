# Frontend Project Structure

```text
frontend/
├── public/                    # 静态资源，构建时原样拷贝
├── src/                       # 前端主源码目录
│   ├── api/                   # 与 FastAPI 通信的请求封装
│   │   ├── client.ts          # Axios 实例，统一 `/api` 前缀
│   │   ├── health.ts          # 健康检查接口
│   │   ├── simMap.ts          # PX4 仿真地图 HTTP / WebSocket 接口
│   │   └── workflow.ts        # 工作流、历史、上传、图片接口
│   ├── assets/                # 图片、图标等本地资源
│   ├── components/            # 可复用组件
│   │   ├── map/               # 地图相关组件与仿真数据
│   │   │   ├── FieldMap.tsx   # PX4 虚拟农田态势图组件
│   │   │   └── mapData.ts     # 虚拟农田边界与展示地图底稿
│   │   └── workflow/          # 任务流程与日志面板
│   │       └── WorkflowPanel.tsx # 无人机阶段流、进度和事件日志面板
│   ├── hooks/                 # 自定义 React Hooks
│   │   └── useSimMapState.ts  # WebSocket / polling 双通道地图状态 Hook
│   ├── layouts/               # 页面级布局组件预留目录
│   ├── pages/                 # 页面入口组件
│   │   └── Dashboard.tsx      # 当前唯一页面：智慧农业指挥大屏首页
│   ├── router/                # 路由配置预留目录
│   ├── styles/                # 全局或页面级样式
│   │   └── dashboard.css      # 指挥大屏样式
│   ├── types/                 # TypeScript 类型定义
│   │   ├── health.ts          # 健康检查响应类型
│   │   ├── simMap.ts          # 仿真地图接口类型
│   │   └── workflow.ts        # 工作流、历史、模式、检测结果类型
│   ├── utils/                 # 工具函数预留目录
│   ├── App.tsx                # 应用根组件
│   ├── index.css              # 全局基础样式
│   └── main.tsx               # React 挂载入口
├── index.html                 # Vite HTML 模板
├── package.json               # 前端依赖与脚本
├── tsconfig.json              # TypeScript 总配置
├── vite.config.ts             # Vite 配置与 FastAPI 代理
└── PROJECT_STRUCTURE.md       # 当前这份结构说明
```

## Notes

- 当前前端不是“展示壳子”，而是统一承接旧 Streamlit 功能后的主前端：
  - 图片上传
  - 原图 / 识别图对照
  - 天气 / 决策卡片
  - 工作流 / 事件日志
  - 历史检索
- `src/components/map/` 现在按 PX4 仿真场景设计，不依赖真实地图底图。
- 后续如果接真实后端数据，优先替换 `mapData.ts` 或继续扩展 `api/`，不要把接口逻辑直接塞进 `FieldMap.tsx`。
- 如果后续引入路由或多页面，优先把页面入口放到 `src/pages/`，公共壳子放到 `src/layouts/`。
- 当前 Vite 默认代理目标是 `http://127.0.0.1:18000`，也可通过 `MUYE_API_TARGET` 覆盖。
