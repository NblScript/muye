# ARCHITECTURE.md — 牧野系统架构总览

## 系统定位

牧野（muye）是一个端到端的智慧农业害虫防治演示与原型系统：
害虫检测 → 气象采集 → AI 决策 → 无人机执行 → 大屏展示

## 架构分层

```
┌──────────────────────────────────────────────┐
│              frontend/ (React + Vite)         │
│         指挥大屏 · 地图 · 任务面板            │
├──────────────────────────────────────────────┤
│              app/ (FastAPI 应用层)             │
│   routes/ → services/ → deps.py → config.py  │
├──────────────────────────────────────────────┤
│            modules/ (核心业务逻辑)             │
│  detection/  decision/  drone/  infra/        │
├──────────────────────────────────────────────┤
│            models/ (数据模型)                  │
│           Pydantic schema + SQLAlchemy ORM    │
├──────────────────────────────────────────────┤
│    data/ (SQLite + ChromaDB)  config/         │
│           持久化层 + 配置层                    │
└──────────────────────────────────────────────┘
```

## 依赖规则（严格）

**允许的依赖方向**（箭头表示"可以依赖"）：

```
frontend/ → app/routes/ → app/services/ → modules/ → models/ → config/
                                                         ↘ data/
```

**禁止的依赖**：
- `modules/` 不得 import `app/` 中的任何模块
- `models/` 不得 import `modules/` 或 `app/`
- `config/` 不得 import 任何业务代码
- `modules/` 业务子域之间不得直接调用彼此的业务能力；跨业务域协作必须通过 EventBus 或应用层编排
- `modules/infra/` 是公共基础设施层，允许被 `detection`、`decision`、`drone` 等业务域依赖

**跨域通信**：
- 唯一通道：`modules/infra/event_bus.py` 中的 `EventBus`
- 事件格式：JSON，写入 `data/logs/demo_events.jsonl`
- 禁止业务域之间直接函数调用；应用层可编排多个业务域，基础设施工具可被业务域直接使用

**横切关注点**（日志、配置、存储）：
- 通过 `modules/infra/common.py` 提供统一接口
- 日志：结构化 JSON 格式，写入 `data/logs/`
- 配置：`app/config.py` 统一加载，`config/` 目录存放配置文件

## 领域模型

### 1. detection（检测域）

- **入口**：`app/yolo_api.py` — 独立 FastAPI 服务（端口 8010）
- **核心**：`modules/detection/`
  - `image_processor.py` — YOLO 推理 + 结果校验
  - `data_collector.py` — 目录监听 + 图像队列
  - `local_yolo_api.py` — 本地 YOLO 模型封装
- **数据流**：上传图片 → YOLO 推理 → 标注图片 + 害虫列表

### 2. decision（决策域）

- **入口**：通过 `app/services/workflow_service.py` 调用
- **核心**：`modules/decision/`
  - `router.py` — DecisionRouter，路由层（`MUYE_ROUTER_ENABLED=true` 启用），评估熟悉度后选择专家路径或多智能体会诊。专家路径失败时自动升级到多智能体会诊（`decision_path="escalated"`）
  - `ai_decision.py` — DecisionEngine，调用 Qwen API（支持单 LLM 和多智能体会诊两种模式）
  - `decision_context.py` — SqliteDecisionContextProvider
  - `rag/` — RAG 子系统
    - `embeddings.py` — QwenEmbeddings 适配器
    - `vectorstore.py` — ChromaDB 向量存储
    - `retriever.py` — DecisionRAGRetriever（害虫感知过滤）
  - `agents/` — 多智能体会诊子系统（`MUYE_MULTI_AGENT_ENABLED=true` 启用）
    - `expert_roles.py` — 3 个专家角色定义（昆虫学家/农学家/植保专家），各角色通过 `llm_provider` 字段指定 LLM 提供商
    - `consultation.py` — ExpertConsultation 会诊编排（接收 `providers` 字典，并行调用 3 个不同 LLM + 降级 + 指数退避重试）
    - `voting.py` — 加权投票 + 置信度计算 + 分歧检测
    - `knowledge_loader.py` — 知识加载器
- **数据流**：害虫列表 + 天气 → RAG 检索 → [路由评估] → 专家路径（单 Qwen）或多智能体会诊（3 模型） → 用药/农事建议 JSON
- **知识库规模**：农药目录 30 条、作物目录 5 种、害虫同义词 27 组、历史决策 200+ 条

### 3. drone（无人机域）

- **入口**：`app/routes/drone.py` — PX4 启停、确认起飞、DJI 无人机接口
- **核心**：`modules/drone/`
  - `controller.py` — DroneController，编排任务执行（通过后端抽象层）
  - `mission_planner.py` — 航线生成 + 喷洒参数
  - `px4_simulator.py` — PX4 SITL 集成（MAVSDK）
  - `field_context_resolver.py` — 农田上下文解析
  - `backends/` — 后端抽象层
    - `base.py` — DroneBackend ABC（connect/disconnect/execute_spray_mission/get_telemetry/get_status）
    - `px4_backend.py` — PX4Backend，包装 PX4Simulator
    - `dji_osdk.py` — DJIOSDKBackend，DJI OSDK 对接（osdk_sim 仿真 + osdk_real 真机）
    - `__init__.py` — 后端注册表（BACKEND_REGISTRY + resolve_backend）
- **后端切换**：`config/drone_config.json` → `execution.backend` 字段（`px4` / `dji_osdk`）
- **数据流**：决策结果 → 任务规划 → 航线生成 → [手动确认] → 后端执行（PX4 或 DJI OSDK）
- **起飞模式**：`manual`（等待确认）/ `auto`（自主），由 `config/drone_config.json` 配置

### 4. infra（基础设施域）

- **核心**：`modules/infra/`
  - `event_bus.py` — FileEventBus，跨域事件通信
  - `weather.py` — 和风天气 API 集成
  - `common.py` — 常量、日志、环境加载、JSON/YAML 工具
  - `sqlite_store/` — 模块化 SQLite 存储
    - `base.py` — 基础存储
    - `task.py` — 任务操作
    - `field.py` — 农田操作
    - `catalog.py` — 目录操作
    - `agri_data.py` — 农业数据操作

## 数据流总图

```
用户上传图片
    │
    ▼
YOLO 检测 (detection)
    │ 害虫列表
    ▼
天气采集 (infra/weather)
    │ 害虫 + 天气
    ▼
RAG 检索 (decision/rag) ──→ 农药知识库 (ChromaDB)
    │ 增强上下文
    ▼
路由评估 (decision/router)  ←── MUYE_ROUTER_ENABLED=true
    │ familiarity_score
    ├─ ≥ 0.6 + 农药匹配 ≥ 2 → 专家路径（单 Qwen LLM 快速决策）
    │   └─ 失败时自动升级 → 多智能体会诊（decision_path="escalated"）
    └─ 否则 → 多智能体会诊（3 专家 × 3 模型并行 → 加权投票，LLM 调用支持指数退避重试）
    │ 用药建议 + 农事建议
    ▼
任务规划 (drone/mission_planner)
    │ 航线参数
    ▼
起飞确认 (manual: 等待人工 / auto: 自动继续)
    │
    ▼
无人机执行 (drone/controller → PX4/SITL)
    │
    ▼
大屏展示 (frontend)
```

## 部署拓扑

```
端口 18000: app/main.py → api_app (主 API)
端口 8010:  app/yolo_api.py (YOLO 推理 API)
端口 5173:  frontend/ (Vite 开发服务器)
```

**生产部署**：`deploy/nginx.conf` 反向代理 + `deploy/muye_backend.service` systemd 服务

## 设计决策记录

| 决策 | 理由 | 替代方案 |
|------|------|----------|
| SQLite 为主存储 | 零运维，单文件可移植 | PostgreSQL（过度工程） |
| 事件总线解耦 | 领域间松耦合 | 直接函数调用（紧耦合） |
| RAG 降级策略 | 检索失败不中断主流程 | 严格依赖（单点故障） |
| 领域子包分组 | 按业务边界组织代码 | 按技术层分组 |
| jsonschema 校验 | 强制 LLM 输出结构 | 纯 prompt 约束（不可靠） |
| JSONL 事件流 | 可追溯、可重放 | 内存事件（不可持久化） |
| 独立 YOLO 服务 | 检测与主 API 解耦 | 内嵌推理（阻塞主流程） |
| 多模型多智能体会诊 | 多视角投票提高决策质量，不同 LLM 增加多样性 | 单 LLM 决策（单一视角） |
| 配置开关控制 | 渐进式启用新功能 | 硬切换（风险高） |
| 决策路由层 | 熟悉场景走快速路径节省延迟，陌生场景走多模型保质量 | 固定路径（无法兼顾效率与质量） |
| 专家路径自动升级 | 专家路径失败时降级到多智能体会诊，保证决策总能产出 | 直接报错（决策中断） |
| LLM 调用指数退避重试 | 瞬态网络/5xx 错误自动恢复，减少单次失败导致专家退出投票 | 单次调用失败即放弃 |
| 检测模型热切换 | yolo_config.yaml 定义模型 profile，/models/switch 运行时切换 | 硬编码单一模型（需重启） |
| 决策 provider 配置化 | model_config.yaml 映射角色→provider，启动时加载覆盖 | 硬编码在 expert_roles.py（改代码才能换） |
| 无人机后端抽象层 | DroneBackend ABC + 注册表，PX4/DJI OSDK 可切换 | 硬编码单一后端（无法扩展） |
| DJI OSDK 仿真模式 | 无硬件时 GPS 插值模拟飞行，接口与真机一致 | 仅真机可用（开发受阻） |
| SLO 指标采集 | 进程内 WindowCounter 滑动窗口，零外部依赖 | Prometheus/外部监控（竞赛环境过重） |
| API 限流中间件 | 滑动窗口 per-IP 限流，防止单客户端过载 | 无限流（演示时可能被意外打爆） |
