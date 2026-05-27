# AGENTS.md — 牧野智能体情境地图

> 本文件是 AI 智能体每次运行时的核心情境入口。所有信息均以本仓库为唯一权威来源。

## 项目概述

牧野（muye）是一个端到端智慧农业害虫防治演示系统，用于大学竞赛（挑战杯、计算机设计大赛）。

**核心管线**：害虫检测 → 气象采集 → AI 决策 → 无人机执行 → 效果评估 → 大屏展示

**成功标准**：
- 竞赛演示全程稳定，无中断
- 评委能清晰看到 AI 决策过程和无人机自主执行
- 系统可在单机（WSL2）环境下一键启动

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 19 + TypeScript 6 + Vite 8（暖色大屏，CSS 变量驱动，useDashboardState Hook 模式） |
| 后端 | Python 3.x + FastAPI + SQLAlchemy |
| AI | YOLOv8（检测，可切换模型）+ Qwen/DeepSeek/Xiaomi（多模型决策，provider 可配置）+ LangChain RAG + ChromaDB + DecisionRouter（路由） |
| 无人机 | PX4 SITL + MAVSDK（仿真）/ DJI OSDK（行业级无人机） |
| 存储 | SQLite（结构化）+ JSONL（事件流）+ ChromaDB（向量） |

## 服务端口

| 服务 | 端口 | 入口 |
|------|------|------|
| 主 API | 18000 | `app/main:api_app` |
| YOLO API | 8010 | `app/yolo_api:app` |
| 前端 | 5173 | Vite dev server |

## 健康检查

| 端点 | 用途 |
|------|------|
| `GET /live` | 只检查 FastAPI 进程存活，不触碰 SQLite/YOLO/PX4/RAG |
| `GET /health` | readiness 诊断，检查依赖状态和当前生效配置 |

## 关键指导原则

1. **演示优先**：稳定性 > 功能丰富度。任何改动必须通过 `./scripts/demo.sh` 验证。
2. **事件驱动**：业务域之间的协作必须通过 `EventBus`（`modules/infra/event_bus.py`）或应用层编排；`modules/infra/` 作为公共基础设施层可被业务域直接依赖。
3. **渐进降级**：RAG 检索失败时发出警告事件，不阻断主流程。
4. **结构化输出**：LLM 返回必须用 jsonschema 校验，不依赖纯 prompt 约束。
5. **SQLite 优先**：单文件零运维，适合竞赛场景。不引入 PostgreSQL。
6. **Agent-First 文档**：所有知识存储在 Git 仓库中，文档结构便于 AI 推理和导航。

## 架构分层与依赖规则

详见 [ARCHITECTURE.md](ARCHITECTURE.md)

```
frontend/ → app/ (routes → services) → modules/ (领域逻辑) → models/ (数据模型) → config/ + data/
```

**依赖流向**：UI → Runtime → Service → Domain → Infra/Repo → Config → Types（不可反向）。业务域之间不直接调用，基础设施层允许被业务域依赖。

## 领域模块

| 域 | 路径 | 职责 |
|----|------|------|
| detection | `modules/detection/` | YOLO 推理 + 图像处理 |
| decision | `modules/decision/` | AI 决策 + RAG 知识增强 + 路由（Router）+ 多智能体会诊 + 合规推理链 |
| drone | `modules/drone/` | 无人机控制 + 任务规划 + 变量喷洒（DensityMap）+ 后端抽象（PX4/DJI OSDK） |
| infra | `modules/infra/` | 事件总线 + SQLite + 天气 + 公共工具 + 效果评估（EvaluationMixin） |

## 后端应用服务

| 服务 | 职责 |
|------|------|
| `app/services/workflow_service.py` | 工作流状态构建、任务合并、历史查询、SqliteStore 单例（`get_sqlite_store()`） |
| `app/services/takeoff_confirmation_service.py` | SQLite-backed 起飞确认状态机，兼容旧文件标记 |
| `app/services/px4_process_service.py` | PX4 SITL 进程管理 helper：PID 文件、端口探测、进程识别、日志与停止 |
| `app/services/pipeline_policy_service.py` | 主处理链合规执行策略解析：blocked/manual/auto |
| `app/services/pipeline_planning_service.py` | 主处理链喷洒规划选择：变量喷洒优先，失败回退均匀路径 |
| `app/services/map_simulator.py` | 模拟 PX4 地图状态用于演示大屏 |
| `app/services/telemetry_service.py` | PX4 遥测状态管理、轨迹缓冲 |
| `app/main.py`（评估编排） | `_schedule_reinspection`、`_run_reinspection`、`_evaluate_effectiveness` 闭环评估管线阶段 |

## 演示脚本

```bash
./scripts/prepare.sh   # 环境准备（依赖检查、演示图片、RAG 知识库）
./scripts/demo.sh      # 一键演示主入口（通过 env var 注入配置，不修改 config 文件）
./scripts/demo_scenario.sh <场景名> # 预设演示场景（aphid_normal|planthopper_humid|wind_high|rag_down|px4_down）
./scripts/demo_smoke.sh # 烟雾测试（验证 API + mock 链路，不依赖 PX4）
./scripts/demo_doctor.sh # 现场诊断报告（health/SLO/workflow/事件流/错误日志）
python scripts/eval_fixed_set.py --output data/eval/latest_report.md # 固定样例评测集报告
./scripts/check.sh     # 竞赛总验证（关键路径测试 + 前端构建 + 文档校验；MUYE_FULL_CHECK=1 开启全量回归）
./scripts/precheck.sh  # 可 source 的环境检查工具库
```

**demo.sh 参数**：`--mode virtual|px4` · `--takeoff manual|auto` · `--api-port` · `--frontend-port`

## 文档导航

| 文档 | 用途 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构、分层规则、依赖约束 |
| [DESIGN.md](DESIGN.md) | 通用设计指南、命名约定、错误处理 |
| [FRONTEND.md](FRONTEND.md) | 前端开发规范 |
| [PLANS.md](PLANS.md) | 高层级路线图 |
| [PRODUCT_SENSE.md](PRODUCT_SENSE.md) | 产品理念、用户故事 |
| [QUALITY_SCORE.md](QUALITY_SCORE.md) | 质量评分标准 |
| [RELIABILITY.md](RELIABILITY.md) | 可靠性要求、SLO |
| [SECURITY.md](SECURITY.md) | 安全规范 |
| [docs/design-docs/](docs/design-docs/index.md) | 设计文档索引 |
| [docs/exec-plans/](docs/exec-plans/tech-debt-tracker.md) | 执行计划与技术债务 |
| [docs/generated/](docs/generated/db-schema.md) | 自动生成文档（DB Schema） |
| [docs/product-specs/](docs/product-specs/index.md) | 产品规格说明 |
| [docs/references/api.md](docs/references/api.md) | API 端点参考 |
| [docs/references/data-model.md](docs/references/data-model.md) | 数据模型参考 |
| [docs/references/rag-llms.txt](docs/references/rag-llms.txt) | RAG/LangChain 使用指南 |
| [docs/superpowers/specs/](docs/superpowers/) | 技术创新设计规格 |
| [docs/project-plan.md](docs/project-plan.md) | 项目计划书 |

## 当前活跃计划

- 无活跃执行计划。查看 [技术债务追踪器](docs/exec-plans/tech-debt-tracker.md) 了解待处理项。

## 外部依赖

| 服务 | 用途 | 配置项 |
|------|------|--------|
| 和风天气 | 实时气象数据 | `QWEATHER_API_KEY` |
| 千问 API (Qwen) | AI 决策（昆虫学家）+ RAG 向量化 | `DASHSCOPE_API_KEY` / `QWEN_API_URL` / `QWEN_MODEL` |
| DeepSeek | AI 决策（农学家） | `DEEPSEEK_API_KEY` / `DEEPSEEK_API_URL` / `DEEPSEEK_MODEL` |
| 小米 MiMo | AI 决策（植保专家） | `XIAOMI_API_KEY` / `XIAOMI_API_URL` / `XIAOMI_MODEL` |
| DashScope | RAG 文本向量化 | `DASHSCOPE_API_KEY` |
| PX4 SITL | 无人机仿真 | 自动启动 |
| DJI OSDK | 行业级无人机对接（Matrice/M300/M350） | `config/drone_config.json` → `dji_osdk` 节 |
| YOLO 模型 | 害虫图像识别 | 本地 ONNX 权重 |
| DecisionRouter | 路由决策路径（专家/多智能体） | `MUYE_ROUTER_ENABLED`（bool，默认 false）· `MUYE_ROUTER_FAMILIARITY_THRESHOLD`（float，默认 0.6） |
| 模型切换 | 检测模型热切换 + 决策 provider 映射 | `config/yolo_config.yaml` → `models` + `active_model`；`config/model_config.yaml` → `expert_providers` |

## 农药安全合规推理链

位于 AI 决策与无人机执行之间，审核推荐农药的安全性。

```text
AI 推荐农药 → 合规推理链（5 项检查）→ passed/warning/blocked → 自动执行/人工确认/拦截
```

**五项检查**：`source_match`（来源验证）· `crop_match`（作物适用性）· `pest_match`（防治对象匹配）· `toxicity_risk`（毒性安全）· `weather_risk`（天气约束）

**执行策略**：
- `passed` → 按配置的 takeoff_mode 执行
- `warning` → 强制人工确认（即使配置为 auto）
- `blocked` → 禁止启动无人机

每项检查携带 `evidence`（来源 + 匹配字段），顶层返回 `summary`（规则拼接）、`execution_policy`、`alternatives`（blocked/warning 时从 RAG 候选中推荐替代农药，最多 3 条，排除高毒/剧毒品种）。

**知识库规模**：80 条农药（5 级毒性）· 7 种作物 · 238 个 RAG 知识文档块

**代码**：`modules/decision/compliance.py`
**设计文档**：`docs/superpowers/specs/2026-05-26-pesticide-compliance-reasoning-chain-design.md`

## 闭环效果评估

喷洒完成后自动进入效果评估闭环，量化农药防治效果。

**流程**：无人机喷洒完成 → 调度复检（`_schedule_reinspection`）→ 等待预计见效时间 → 定时复检（`_run_reinspection`）→ 效果评估（`_evaluate_effectiveness`）→ 写入 `task_evaluations` 表

**评估结论**：`effective`（害虫显著减少）/ `partial`（部分减少）/ `ineffective`（无显著变化）

**API 端点**：
- `GET /api/evaluation/{request_id}` — 获取单条评估记录
- `GET /api/evaluations` — 获取全部评估记录（支持 `status` 过滤）
- `POST /api/evaluation/{request_id}/cancel` — 取消待执行评估

**数据存储**：`task_evaluations` 表（SQLite），由 `EvaluationMixin`（`modules/infra/sqlite_store/evaluation.py`）管理

**决策扩展**：`DECISION_SCHEMA` 新增 `预计见效时间` 字段，评估配置定义在 `app/config_types.py`

**前端展示**：`EvaluationCard` 组件 + `PipelineStepper` 新增评估阶段

**`WorkflowTaskState` 扩展**：新增可选 `evaluation` 字段，携带评估状态和评分

## 遇到无法解决的问题

本项目为个人竞赛项目。如智能体遇到无法通过代码和文档解决的问题，应：
1. 在代码中搜索相关注释和 docstring
2. 查看 `git log` 了解最近变更
3. 检查 `data/logs/` 下的日志文件
4. 向用户发出明确的问题描述和建议

## 多智能体会诊

### 路由层（Router）

系统支持决策路由（默认关闭）。通过 `MUYE_ROUTER_ENABLED=true` 启用。

路由层位于 RAG 检索与决策执行之间，通过 `DecisionRouter`（`modules/decision/router.py`）评估当前场景的熟悉度，决定走快速专家路径还是多智能体会诊。

**评分公式**：40% 农药匹配 + 25% 历史案例 + 20% 相似度 + 15% 目录匹配

**路由规则**：
- 熟悉度 ≥ 0.6 且农药匹配 ≥ 2 → **专家路径**（expert）：单 Qwen LLM 快速决策
- 否则 → **多智能体会诊**（multi_agent）：3 模型并行会诊

**专家路径自动升级**：当专家路径失败（JSON 解析错误、HTTP 5xx、网络超时等）且存在 `consultation` 模块时，自动升级到多智能体会诊路径。`decision_path` 设为 `"escalated"`。无 `consultation` 模块时保持原抛异常行为。

**事件**：
- 路由决策产生 `stage="router", status="routed"` 事件，包含 `path`、`familiarity_score`、`reason` 字段
- 升级时产生 `stage="router", status="escalated"` 事件，包含 `from`、`to`、`reason` 字段

**前端展示**：
- 专家路径：绿色"专家模型快速路径"徽章
- 多智能体路径：青色会诊卡片
- 升级路径：橙色"专家路径异常 → 多智能体升级"徽章

### 多智能体会诊

系统支持多智能体专家会诊模式（默认关闭）。通过 `MUYE_MULTI_AGENT_ENABLED=true` 启用。

启用后，决策管线变为：3 个专家角色分别调用不同 LLM 提供商并行推理，各自从 RAG 检索不同知识，加权投票汇总后输出决策。

| 专家角色 | LLM 提供商 | 模型 |
|---------|-----------|------|
| 昆虫学家 | Qwen（千问） | `qwen-max-latest` |
| 农学家 | DeepSeek | `deepseek-chat` |
| 植保专家 | Xiaomi Mimic | `mimo-v2.5-pro` |

`ExpertConsultation` 通过 `providers` 字典接收各角色的 LLM 配置（api_url/api_key/model），每个专家角色通过 `llm_provider` 字段指定所用提供商。单 LLM 路径仍作为降级后备。

**LLM 调用重试**：`_invoke_llm()` 支持指数退避重试（最多 2 次，共 3 次尝试）。仅重试 5xx 和网络错误，4xx 不重试。退避间隔 0.5s → 1s。

代码位于 `modules/decision/agents/`：
- `expert_roles.py` — 角色定义（含 `llm_provider` 字段）
- `consultation.py` — 会诊编排（接收 `providers` 字典）
- `voting.py` — 投票机制
