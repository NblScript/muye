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
- `modules/` 子域之间不得直接 import（必须通过 EventBus）

**跨域通信**：
- 唯一通道：`modules/infra/event_bus.py` 中的 `EventBus`
- 事件格式：JSON，写入 `data/logs/demo_events.jsonl`
- 禁止跨域直接函数调用

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
  - `ai_decision.py` — DecisionEngine，调用 Qwen API（支持单 LLM 和多智能体会诊两种模式）
  - `decision_context.py` — SqliteDecisionContextProvider
  - `rag/` — RAG 子系统
    - `embeddings.py` — QwenEmbeddings 适配器
    - `vectorstore.py` — ChromaDB 向量存储
    - `retriever.py` — DecisionRAGRetriever（害虫感知过滤）
  - `agents/` — 多智能体会诊子系统（`MUYE_MULTI_AGENT_ENABLED=true` 启用）
    - `expert_roles.py` — 3 个专家角色定义（昆虫学家/农学家/植保专家）
    - `consultation.py` — ExpertConsultation 会诊编排（并行调用 + 降级）
    - `voting.py` — 加权投票 + 置信度计算 + 分歧检测
    - `knowledge_loader.py` — 知识加载器
- **数据流**：害虫列表 + 天气 → RAG 检索 → Qwen API → 用药/农事建议 JSON

### 3. drone（无人机域）

- **入口**：`app/routes/drone.py` — PX4 启停与确认起飞接口
- **核心**：`modules/drone/`
  - `controller.py` — DroneController，编排任务执行
  - `mission_planner.py` — 航线生成 + 喷洒参数
  - `px4_simulator.py` — PX4 SITL 集成（MAVSDK）
  - `field_context_resolver.py` — 农田上下文解析
- **数据流**：决策结果 → 任务规划 → 航线生成 → [手动确认] → PX4 SITL 执行
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
Qwen 决策 (decision/ai_decision)
    │ 单 LLM 模式：直接输出
    │ 多智能体模式：3 专家并行 → 加权投票
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
| 多智能体会诊 | 多视角投票提高决策质量 | 单 LLM 决策（单一视角） |
| 配置开关控制 | 渐进式启用新功能 | 硬切换（风险高） |
