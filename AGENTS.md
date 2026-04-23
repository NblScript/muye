# AGENTS.md — AI Agent Navigation Entry

> 短入口，渐进式披露。更多细节见深层文档。

## 快速定位

| 你想做什么？ | 去哪里 |
|-------------|--------|
| 理解整体架构 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 查看模块质量评分 | [QUALITY_SCORE.md](QUALITY_SCORE.md) |
| 新增 API 端点 | [docs/reference/api.md](docs/reference/api.md) |
| 修改数据模型 | [docs/reference/data-model.md](docs/reference/data-model.md) |
| 查看设计原则 | [docs/design/index.md](docs/design/index.md) |
| 追踪技术债务 | [docs/plans/tech-debt.md](docs/plans/tech-debt.md) |
| 查看实施计划 | [docs/plans/](docs/plans/) |
| 运维手册 | [docs/operations/runbooks/](docs/operations/runbooks/) |

## 代码结构

```
muye/
├── app/                 # FastAPI 应用层
│   ├── main.py         # 主入口，路由注册
│   ├── routes/         # API 端点
│   ├── services/       # 业务服务
│   ├── deps.py         # 依赖注入
│   └── config.py       # 配置解析
├── modules/             # 核心业务逻辑（按领域）
│   ├── decision/      # AI 决策 + RAG
│   ├── drone/         # 无人机控制 + PX4
│   ├── detection/     # YOLO 检测
│   └── infra/         # 共享基础设施
├── models/             # Pydantic schema
├── config/             # 配置文件
├── data/               # 运行时数据
├── frontend/           # React 前端
├── tests/              # 测试（77个）
└── docs/               # 文档
```

## 领域边界

| 领域 | 职责 | 关键模块 |
|------|------|----------|
| decision | AI 决策 + 知识增强 | `modules/decision/` |
| drone | 无人机控制 + 任务规划 | `modules/drone/` |
| detection | 图像识别 + 数据采集 | `modules/detection/` |
| infra | 事件总线 + 存储 + 天气 | `modules/infra/` |

## 启动命令

```bash
# 启动主 API
.venv/bin/uvicorn app.main:api_app --reload

# 启动无人机 API
.venv/bin/uvicorn app.drone_api:app --port 8001

# 启动 YOLO API
.venv/bin/uvicorn app.yolo_api:app --port 8002

# 运行测试
.venv/bin/python -m pytest -q tests/
```

## 关键约定

1. **import 路径**：`from modules.<domain>.<module>` 如 `from modules.decision.ai_decision`
2. **配置加载**：通过 `app.config.get_config()` 获取统一配置
3. **事件总线**：`modules.infra.event_bus` 是跨模块通信的唯一通道
4. **数据存储**：`modules.infra.sqlite_store` 是唯一数据持久层

## Agent 工作流程

1. 先读 `ARCHITECTURE.md` 理解全局
2. 再读 `QUALITY_SCORE.md` 了解模块健康度
3. 改代码前先读对应领域的模块代码
4. 改完后运行测试：`.venv/bin/python -m pytest -q tests/`
5. 更新相关文档（如有 API 变更）

---
*此文件保持 100 行以内，是导航入口，不是百科全书。*
