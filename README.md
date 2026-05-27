# 牧野智能农业害虫防治系统

`muye` 是一个基于 Python 的智能农业害虫防治项目，集成了无人机图像采集、YOLO 害虫识别、和风天气数据整合、千问 AI 决策和精准喷洒控制。项目采用异步任务流、模块化设计，并对外部 API 响应进行严格校验。

> 面向智慧农业作业验证的端到端植保指挥系统。

## 项目简介

牧野将“虫情感知、气象感知、AI 决策、无人机执行、前端可视化”整合为一条完整链路，目标不是单点展示某个模型，而是提供一个可以真实联调、可视化运行、可持续扩展的智慧农业指挥中心原型。系统既支持本地离线能力验证，也支持接入真实天气服务、真实大模型接口和 PX4 SITL 飞行链路，适合用于植保无人机调度原型验证、方案验证和后续工程化扩展。

核心亮点：

- 端到端闭环：从农田图片输入到虫害识别、药剂建议、飞行参数生成，再到 PX4 SITL 执行状态回放。
- 多模型多智能体会诊：3 个专家角色（昆虫学家/农学家/植保专家）分别调用 Qwen、DeepSeek、小米 MiMo 并行推理，加权投票汇总决策。
- 决策路由与自动升级：DecisionRouter 评估场景熟悉度，熟悉场景走快速专家路径，陌生场景走多智能体会诊；专家路径失败时自动升级到多智能体，保证决策总能产出。
- LLM 调用容错：指数退避重试（最多 2 次），仅重试 5xx 和网络错误，4xx 不重试。
- RAG 知识增强：农药目录 30 条、作物目录 5 种、害虫同义词 27 组、历史决策 200+ 条，向量检索增强决策质量。
- 单一作业流程：无人机执行统一收敛到 PX4 SITL 链路，避免运行时在虚拟模式和 PX4 模式之间切换。
- 本地可部署：YOLO 模型通过本地 API 服务封装，支持直接加载 `best.pt` 权重运行。
- 可视化指挥中心：基于 `Vite + React + TypeScript` 构建指挥大屏，统一承接图片上传、识别结果、天气/决策卡片、态势图、任务历史与事件日志。
- 工程化结构清晰：配置、模块、测试、前端和事件总线分层明确，便于维护与继续开发。
- 混合存储起步：保留 JSONL 事件流，同时将主处理链摘要同步写入 SQLite，方便后续查询与扩展。
- 状态可追溯：无人机任务推进状态也会落入 SQLite，便于历史检索和后续报表扩展。

适用场景：

- 植保无人机调度原型验证
- YOLO + 大模型 + 外部 API 的系统集成实践
- 后续扩展为真实设备控制平台的工程起点

## 项目技术说明

### 1. 项目定位与建设目标

`muye` 是一个面向智慧农业害虫防治场景的端到端原型系统。系统围绕“虫情感知、气象感知、AI 决策、无人机执行、前端可视化”构建完整闭环，目标不是单点展示某个模型能力，而是验证一个可联调、可运行、可扩展的智慧植保指挥中心方案。

项目建设目标包括：

- 实现农田害虫图像的自动识别与结果结构化输出
- 引入天气、知识库、历史案例等上下文信息，生成更可靠的施药建议
- 将 AI 决策结果转化为可执行的无人机航线与喷洒参数
- 通过前端指挥大屏实时展示任务状态、地图态势和处理流程
- 对关键运行过程进行结构化存储，便于追溯、检索和后续统计分析

从系统形态上看，项目可以作为植保无人机调度原型，也可以作为后续接入真实设备、真实数据和正式规则引擎的工程起点。

### 2. 总体技术架构

项目采用前后端分离、领域模块化和混合存储的架构设计，整体分为五层：

1. 前端展示层  
   位于 `frontend/`，技术栈为 `React + Vite + TypeScript`。  
   负责承接指挥大屏、作业地图、任务面板、图片对照、天气卡片、决策信息、流程状态和历史记录等展示能力。

2. 应用编排层  
   位于 `app/`，技术栈为 `FastAPI`。  
   负责聚合业务模块、装配 API、统一对前端暴露接口，同时承担主处理链调度能力。

3. 核心业务层  
   位于 `modules/`，按领域拆分为：
   - `detection`：害虫检测与图像处理
   - `decision`：AI 决策与 RAG 知识增强
   - `drone`：无人机控制、任务规划与 PX4 仿真
   - `infra`：天气、事件总线、SQLite 存储、公共工具

4. 数据模型层  
   位于 `models/`。  
   定义 Pydantic schema 和农业数据参考模型，作为前后端接口与数据结构的统一边界。

5. 数据与配置层  
   位于 `data/` 与 `config/`。  
   负责运行数据、日志、种子数据、SQLite 数据库、Chroma 向量库及 YAML/JSON 配置管理。

### 3. 核心业务流程

系统完整数据流如下：

1. 用户上传农田图片，或由数据采集服务自动写入图片目录
2. 检测模块调用 YOLO 模型服务，输出害虫类别、置信度与位置信息
3. 天气模块获取当前气象数据
4. 决策模块结合害虫结果、天气信息、可选结构化上下文与 RAG 检索结果，经路由评估后走专家路径（单 Qwen 快速决策）或多智能体会诊（3 模型并行投票）生成施药建议；专家路径失败时自动升级
5. 无人机模块基于地块、天气和决策结果规划飞行路径、高度、速度、喷洒速率和覆盖区域
6. 当起飞模式为 `manual` 时，系统等待人工确认；为 `auto` 时则直接继续
7. 控制模块驱动 PX4 SITL 执行任务；进入喷洒阶段前会自动关联启动 PX4
8. 前端通过 HTTP + WebSocket 获取实时状态、地图态势和任务日志
9. SQLite 与事件总线分别记录结构化任务摘要和实时事件流

这条主链路体现了项目的核心价值：将“识别、分析、决策、执行、展示”整合成一个统一系统，而非若干孤立模块的拼接。

### 4. 关键模块设计

#### 4.1 检测模块 detection

检测域主要由 `modules/detection/` 提供能力。

- `image_processor.py`  
  负责调用 YOLO API 并对返回结果做校验，保证后续链路拿到的是统一格式的 `pest_type / confidence / position`。
- `local_yolo_api.py`  
  负责封装本地 YOLO 模型服务，支持直接加载模型权重运行。
- `data_collector.py`  
  负责定时采图与目录监听，支持模拟采图和自动入队处理。

技术上，检测模块通过独立 API 服务与主流程解耦，使模型服务可以单独替换、调优或外置部署，不会影响应用层编排逻辑。

#### 4.2 决策模块 decision

决策域是系统的智能核心，主要位于 `modules/decision/`。

- `ai_decision.py`
  将害虫检测、天气信息、地块上下文整合为结构化 prompt，调用千问模型输出施药建议和农事建议。
  为避免大模型输出不稳定，系统使用 `jsonschema` 对结果做结构化校验，确保输出满足预期字段约束。

- `router.py`
  DecisionRouter 路由层，评估当前场景的熟悉度（40% 农药匹配 + 25% 历史案例 + 20% 相似度 + 15% 目录匹配），决定走快速专家路径还是多智能体会诊。专家路径失败时自动升级到多智能体会诊（`decision_path=”escalated”`）。

- `decision_context.py`
  提供可插拔的结构化增强上下文能力。
  当启用配置项后，可从 SQLite 中提取土壤、历史天气、候选农药等数据拼入决策输入；未启用时则保持基础链路简洁，避免强依赖数据库参与决策。

- `agents/` — 多智能体会诊子系统
  - `consultation.py`：ExpertConsultation 会诊编排，并行调用 3 个不同 LLM（Qwen/DeepSeek/小米 MiMo），支持指数退避重试
  - `voting.py`：加权投票 + 置信度计算 + 分歧检测
  - `expert_roles.py`：3 个专家角色定义（昆虫学家/农学家/植保专家）

系统明确将职责切分为：

- 大模型负责”用药建议”和”农事建议”
- 任务规划器负责”飞行路径、喷洒参数、气象限制”等执行细节

这种边界划分提高了系统可控性，也更符合工程实践。

#### 4.3 RAG 知识增强模块

RAG 模块位于 `modules/decision/rag/`，是决策增强的重要组成部分。

当前实现包含：

- `embeddings.py`  
  `QwenEmbeddings` 封装 DashScope 的 `text-embedding-v3` 接口
- `vectorstore.py`  
  `VectorStoreManager` 管理 ChromaDB 持久化向量库
- `retriever.py`  
  `DecisionRAGRetriever` 负责基于害虫类型和作物名称进行知识检索
- `knowledge_loader.py`  
  负责从 SQLite、JSON 种子数据和 `docs/` 文档加载知识条目

当前向量库支持三个 collection：

- `pesticides`：农药知识（30 条农药目录，覆盖小麦/玉米/水稻/棉花/大豆的杀虫剂和杀菌剂）
- `decisions`：历史决策案例（200+ 条，基于 IP102 害虫数据集生成）
- `agri_knowledge`：文档型农业知识（5 种作物、27 组害虫同义词）

系统在每次 AI 决策前执行 RAG 检索，将相关农药推荐、历史案例和农业知识片段拼接到 prompt 中；如果检索失败，系统只记录告警并自动降级到基础决策模式，不阻塞主流程。

为了适配比赛演示与中英标签混用场景，RAG 检索器还增加了 demo 级害虫同义词归一化，如 `aphid / 蚜虫`、`rice-planthopper / 稻飞虱` 等，提高检索命中率。

此外，主流程已经支持在决策完成后将新决策异步增量写入 `COLLECTION_DECISIONS`，使系统可以在演示过程中逐步积累历史案例，而不完全依赖手动重建向量库。

#### 4.4 无人机模块 drone

无人机域位于 `modules/drone/`，负责把 AI 输出转换为可执行作业任务。

核心组件包括：

- `controller.py`  
  统一控制无人机执行链路，当前对外运行流程固定为 `px4`。
- `mission_planner.py`  
  根据地块、天气和决策结果生成航线、飞行高度、速度、喷洒速率和覆盖区域
- `px4_simulator.py`  
  对接 `PX4 SITL + MAVSDK Mission`，负责连接、定位等待、读取已上传 Mission、解锁、启动任务、任务跟踪和完成监听。默认只启动 QGC/PX4 已规划并上传的 Mission，牧野不上传航点，也不接管起飞高度。
当前现场流程固定采用人工确认起飞。  
决策完成后系统发布 `pending_confirmation` 事件，前端显示“确认起飞”按钮；操作人员确认后，系统自动启动 PX4 SITL 并继续执行喷洒航线。

PX4 工作流程包含连接、定位等待、原生 Mission 准备、解锁、任务启动和完成状态回写，前端通过任务状态和地图态势同步呈现。

#### 4.5 基础设施模块 infra

基础设施域位于 `modules/infra/`，承担全局支撑能力。

- `event_bus.py`  
  采用 JSONL 文件事件总线，作为跨模块实时通信与时间线回放来源。  
  它是系统领域间通信的唯一事件通道，降低模块间耦合。
- `sqlite_store.py`  
  提供 SQLite schema 管理、迁移、写入与查询能力。  
  当前已落地任务、检测、天气、决策、无人机状态更新、农业基础数据、喷洒记录等多张表。
- `weather.py`  
  封装和风天气接口，支持 `real/mock` 双模式。
- `common.py`  
  管理日志、目录、配置加载和公共工具函数。

系统采用 `JSONL + SQLite` 混合存储策略：

- JSONL 负责实时事件流和前端时序展示
- SQLite 负责结构化摘要、历史检索和农业数据支撑

### 5. 前端展示系统设计

前端位于 `frontend/`，是当前唯一前端主线，技术栈为 `React + Vite + TypeScript`。

前端的主要职责是把复杂的处理链路转化为“评委和用户能看懂的系统行为”。当前承载能力包括：

- 首页指挥大屏
- 地图态势展示
- 图片上传
- 原图 / 标注图对照
- 天气卡片
- AI 决策卡片
- 工作流步骤条
- 无人机执行面板
- 任务历史检索
- WebSocket 实时状态接收与断线降级轮询

地图组件 `FieldMap.tsx` 当前已经不依赖 Leaflet 运行时地图容器，而是改为纯 SVG 虚拟农田渲染，直接绘制：

- 地块边界
- 覆盖区域
- 飞行路径
- 无人机位置
- 检测点位
- 指挥点

这种实现方式更适合比赛演示，因为它对外部地图底图无依赖，也减少了底图加载、容器初始化和缩放适配带来的不稳定因素。

### 6. 系统运行方式

当前项目有两个启动入口：**演示入口**（竞赛评审）和**生产入口**（24h 自动巡检）。

#### 演示入口（demo.sh）

```bash
./scripts/prepare.sh   # 环境准备
./scripts/demo.sh      # 演示主入口
```

`demo.sh` 固定走”单张图片 → AI 决策 → 人工确认起飞 → PX4 喷洒”流程，支持：

- `--image <path>`
- `--api-port`
- `--frontend-port`
- `--skip-precheck`
- `--skip-inject`

#### 生产入口（run.sh）

```bash
./scripts/prepare.sh --production  # 环境准备 + 生产检查
./scripts/run.sh                   # 24h 自动巡检循环
```

`run.sh` 启动即采集、自动起飞、PX4 SITL 真实仿真、任务闭环自动重试至杀灭率达标，支持：

- `--api-port`
- `--frontend-port`
- `--no-frontend`（无头运行）
- `--skip-precheck`

| 配置项 | demo.sh | run.sh |
|--------|---------|--------|
| 起飞模式 | manual（人工确认） | auto（自动起飞） |
| PX4 模式 | animated_demo | sitl |
| 图片采集 | 手动注入单张 | 启动即采集，每 24h 循环 |
| 前端 | 必须启动 | 可选 |
| 环境配置 | mock | `.env.production` |

当前默认部署拓扑为：

- 主 API：`18000`
- YOLO API：`8010`
- 前端：`5173`

需要注意的是，部分旧文档仍保留过期端口描述，当前应以脚本和应用代码中的实际配置为准。

### 7. 测试与质量保障

项目配有较完整的自动化测试体系，覆盖主流程、API 契约、无人机控制、SQLite 迁移、RAG 检索、脚本导入和前端部分逻辑。

核心测试包括：

- `tests/test_main.py`：主入口与主流程
- `tests/test_drone_controller.py`：无人机执行逻辑
- `tests/test_mission_planner.py`：航线规划
- `tests/test_sqlite_migration.py`：数据库迁移与兼容
- `tests/test_rag_embeddings.py`：Embedding 接口契约
- `tests/test_rag_retriever.py`：RAG 查询逻辑
- `tests/test_knowledge_loader.py`：知识加载与增量索引构造

从工程策略看，项目强调：

- 改动前先跑测试
- 新功能必须补测试
- 实际行为变化需要同步文档和项目记忆

### 8. 项目创新点与工程特点

本项目的创新不只在于模型组合，而在于系统级整合，主要体现在：

1. 从识别到执行的完整闭环  
   项目不是“识别结果展示”或“AI 建议生成”这种单环节系统，而是贯通到无人机任务执行与前端态势展示。

2. 多源信息参与决策
   决策不是只基于害虫图像，而是同时结合天气、农药知识、历史案例和结构化农业数据上下文。

3. 多模型多智能体会诊
   3 个专家角色分别调用不同 LLM 并行推理，加权投票汇总，提高决策质量和多样性。专家路径失败时自动升级到多智能体会诊。

4. 智能路由与自适应降级
   DecisionRouter 根据场景熟悉度选择最优决策路径，专家路径失败时自动升级，LLM 调用支持指数退避重试。

5. 大模型与规划器职责分离
   避免让大模型直接生成飞控参数，而是由规则化任务规划器完成飞行路径与喷洒约束，提升工程可控性。

6. 单一 PX4 工作流程
   无人机执行固定走 PX4 SITL，避免运行时在虚拟模式与 PX4 模式之间切换。

7. 混合存储策略
   使用 `JSONL + SQLite + ChromaDB` 分别处理实时事件、结构化历史和向量知识，结构简单但功能完整。

8. 前端虚拟农田态势图
   通过纯 SVG 实现作业地图，更适合答辩和比赛场景下的稳定展示。

### 9. 当前局限与后续扩展方向

虽然系统主链路已经打通，但当前仍存在一些工程边界：

- `QwenEmbeddings` 和真实天气接口依赖外部 API Key
- PX4 仿真链路在真实环境中仍依赖外部组件，如 Gazebo、MAVSDK、QGroundControl
- 决策增强上下文目前仍以”把结构化数据拼入 prompt”为主，尚未形成正式规则引擎
- 前端在比赛演示场景下仍可进一步打磨讲解节奏、布局和动画效果

后续扩展方向可包括：

- 引入 reranking 或更强检索策略提升 RAG 质量
- 扩展农业统计、报表与决策可解释性
- 接入真实无人机硬件链路
- 引入更精细的任务调度与多机协同能力

### 10. 总结

`muye` 是一个围绕智慧农业害虫防治场景构建的系统级原型平台。它的价值不在于单独证明 YOLO、LLM 或 PX4 中某一项技术，而在于将这些能力有机整合为一个可运行、可展示、可演进的闭环系统。

从当前代码与文档状态来看，项目已经具备以下工程特征：

- 主链路闭环打通
- 前后端边界明确
- 模块职责清晰
- 数据留痕完整
- 演示模式稳定
- 后续扩展路径清楚

## 项目结构

```text
muye/
├── AGENTS.md                        # AI Agent 情境地图（核心入口）
├── ARCHITECTURE.md                  # 架构总览（分层 + 依赖规则）
├── CLAUDE.md                        # 最高命令（文档同步强制规则）
├── CHANGELOG.md                     # 发行变更日志
├── DESIGN.md                        # 通用设计指南
├── FRONTEND.md                      # 前端开发规范
├── PLANS.md                         # 高层路线图
├── PRODUCT_SENSE.md                 # 产品理念和用户故事
├── QUALITY_SCORE.md                 # 质量评分标准
├── RELIABILITY.md                   # 可靠性要求和 SLO
├── SECURITY.md                      # 安全规范
├── README.md                        # 项目总说明
├── requirements.txt                 # Python 依赖清单
│
├── app/                             # FastAPI 应用层
│   ├── main.py                      # 主入口 + 路由注册
│   ├── yolo_api.py                  # 本地 YOLO API（独立服务）
│   ├── config.py                    # 环境解析与配置工具
│   ├── deps.py                      # 运行时依赖访问辅助
│   ├── routes/                      # API 路由
│   │   ├── health.py                # /health 健康检查
│   │   ├── workflow.py              # /workflow/* 工作流接口
│   │   ├── dashboard.py             # /dashboard/context
│   │   ├── demo.py                  # /demo/* 演示接口
│   │   ├── tasks.py                 # /tasks/* 图片接口
│   │   ├── sim.py                   # /sim/* 模拟接口 + WebSocket
│   │   └── __init__.py
│   └── services/                    # 应用服务
│       ├── workflow_service.py      # 工作流聚合服务
│       ├── map_simulator.py         # 地图状态模拟器
│       └── __init__.py
│
├── modules/                         # 核心业务逻辑（按领域分组）
│   ├── decision/                    # 决策域
│   │   ├── ai_decision.py           # 千问决策 + jsonschema 校验 + 专家路径自动升级
│   │   ├── router.py                # DecisionRouter 路由层
│   │   ├── decision_context.py      # 决策增强上下文
│   │   ├── agents/                  # 多智能体会诊
│   │   │   ├── consultation.py      # ExpertConsultation 会诊编排 + LLM 重试
│   │   │   ├── voting.py            # 加权投票机制
│   │   │   ├── expert_roles.py      # 专家角色定义
│   │   │   └── knowledge_loader.py  # 知识加载器
│   │   └── rag/                     # RAG 知识增强
│   │       ├── embeddings.py        # QwenEmbeddings (DashScope)
│   │       ├── vectorstore.py       # ChromaDB 向量库
│   │       ├── retriever.py         # DecisionRAGRetriever 检索
│   │       └── __init__.py
│   ├── drone/                       # 无人机域
│   │   ├── controller.py            # 无人机任务执行与状态回写
│   │   ├── mission_planner.py       # 飞行/喷洒规划
│   │   ├── px4_simulator.py         # PX4 SITL / MAVSDK 执行链路
│   │   └── __init__.py
│   ├── detection/                   # 检测域
│   │   ├── image_processor.py       # YOLO 识别调用与校验
│   │   ├── local_yolo_api.py        # 嵌入式 YOLO API
│   │   ├── data_collector.py        # 图片采集与目录监听
│   │   └── __init__.py
│   ├── infra/                       # 基础设施域
│   │   ├── common.py                # 公共路径、日志、配置加载
│   │   ├── event_bus.py             # JSONL 事件总线
│   │   ├── sqlite_store.py          # SQLite schema/读写封装
│   │   ├── weather.py               # 和风天气接入 (原 weather_integration)
│   │   └── __init__.py
│   └── __init__.py
│
├── models/                          # 数据模型
│   ├── schemas.py                   # 前端 API Pydantic schema
│   ├── agri_models.py               # SQLAlchemy 农业数据参考模型
│   └── README.md
│
├── config/                          # 运行配置
│   ├── api_keys.env                 # 本地密钥和接口地址
│   ├── drone_config.json            # 地块、围栏、飞行约束
│   └── yolo_config.yaml             # YOLO 推理服务配置
│
├── data/                            # 运行期数据
│   ├── images/                      # 上传/自动采集图片
│   ├── logs/                        # 系统日志和 JSONL 事件流
│   ├── seeds/                       # 河南参考 seed/CSV/JSON
│   ├── chroma_db/                   # RAG 向量知识库
│   └── muye.db                      # SQLite 结构化业务库
│
├── docs/                            # Agent-First 文档系统
│   ├── design-docs/                 # 设计文档
│   │   ├── index.md                 # 设计文档索引
│   │   └── core-beliefs.md          # 核心工程信念
│   ├── exec-plans/                  # 执行计划
│   │   ├── active/                  # 正在执行的计划
│   │   ├── completed/               # 已完成的计划
│   │   └── tech-debt-tracker.md     # 技术债务追踪
│   ├── generated/                   # 自动生成文档
│   │   └── db-schema.md             # SQLite schema
│   ├── product-specs/               # 产品规格
│   │   └── demo-pipeline.md         # 演示流程规格
│   └── references/                  # 参考文档
│       ├── api.md                   # API 端点列表
│       ├── data-model.md            # 数据模型
│       └── rag-llms.txt             # RAG 使用指南
│
├── frontend/                        # React 前端
│   ├── src/                         # 前端源码
│   ├── public/                      # 静态资源
│   ├── package.json                 # 前端依赖和脚本
│   ├── vite.config.ts               # Vite 配置与 API 代理
│   └── PROJECT_STRUCTURE.md         # 前端结构说明
│
├── scripts/                         # 辅助脚本
│   ├── prepare.sh                   # 环境准备（依赖检查、演示图片）
│   ├── demo.sh                      # 一键演示主入口
│   ├── precheck.sh                  # 环境检查工具库
│   ├── build_rag_knowledge.py       # 构建 RAG 向量知识库
│   ├── seed_history.py              # 历史决策种子生成（基于 IP102 数据集）
│   └── import_*.py / generate_*.py  # 数据导入脚本
│
└── tests/                           # 自动化测试
    ├── test_main.py                 # 主入口 / API 契约 / 主流程测试
    ├── test_ai_decision.py          # AI 决策引擎测试（含升级路径）
    ├── test_consultation.py         # 多智能体会诊测试（含 LLM 重试）
    ├── test_router.py               # 决策路由测试
    ├── test_voting.py               # 投票机制测试
    ├── test_drone_controller.py     # PX4 执行链路测试
    ├── test_mission_planner.py      # 航线与演示 profile 测试
    ├── test_sqlite_migration.py     # SQLite schema / migration 测试
    ├── test_rag_embeddings.py       # RAG Embeddings API 契约测试
    ├── test_rag_retriever.py        # RAG Retriever 测试
    └── ...                          # 其余 AI / 天气 / YOLO 测试
```

## 当前开发主线

当前仓库推荐按下面的心智模型理解：

- `app/main.py`
  负责两件事：
  1. 农业处理主流程编排
  2. 给 React 大屏提供 `api_app`
- `app/yolo_api.py`
  独立 YOLO 推理服务，接收图片返回害虫检测结果。
- `modules/` 核心业务逻辑按领域分组：`decision/`、`drone/`、`detection/`、`infra/`。
- `frontend/`
  是唯一前端主线，不再存在 Streamlit 页面
- `modules/infra/sqlite_store.py + modules/infra/event_bus.py`
  分别负责结构化历史和实时事件
- `scripts/demo.sh`
  是最直接的本地运行入口，会同时启动：
  - `app/main:api_app` (FastAPI 主 API)
  - `app.yolo_api:app` (YOLO 推理 API)
  - `frontend` 的 Vite 开发服务器
  - 自动注入巡检图片

## 目录导读

如果你是第一次接手这个仓库，建议按这个顺序看：

1. [AGENTS.md](AGENTS.md) — AI Agent 情境地图（核心入口）
2. [ARCHITECTURE.md](ARCHITECTURE.md) — 架构总览
3. [CLAUDE.md](CLAUDE.md) — 最高命令（文档同步规则）
4. [README.md](README.md) — 项目总说明
5. [frontend/PROJECT_STRUCTURE.md](frontend/PROJECT_STRUCTURE.md) — 前端结构
6. [tests/test_main.py](tests/test_main.py) — 主流程测试

## 功能说明

### 应用层（app/）

1. `app/main.py`
   - 装配 YOLO、天气、决策、无人机执行和 SQLite 写入链路。
   - 暴露前端聚合 API：`/health`、`/workflow/*`、`/dashboard/*`、`/tasks/*`、`/demo/*`、`/sim/*`。
   - 在一键运行模式下可接管本地 YOLO API，主流程固定走 PX4 SITL。

2. `app/yolo_api.py`
   - 独立本地 YOLO 推理 API 服务（端口 8010）。
   - 接收图片，返回害虫类型、置信度、位置信息。

### 核心业务层（modules/）

3. `modules/detection/` — 检测域
   - `image_processor.py`：异步调用 YOLO API，校验害虫类型、置信度、位置信息。
   - `local_yolo_api.py`：嵌入式 YOLO API，支持直接加载 `best.pt` 权重。
   - `data_collector.py`：每 24 小时自动触发无人机采图，使用 watchdog 监听新图片。

4. `modules/decision/` — 决策域
   - `ai_decision.py`：将害虫检测和天气信息整合成结构化文本，调用千问 API 输出用药建议 + 农事建议 JSON。使用 jsonschema 强制校验返回结构。已集成 RAG 检索增强：决策前自动检索农药知识库和历史案例，失败时降级不中断。
   - `decision_context.py`：决策增强上下文抽象。
   - `rag/`：RAG 决策增强模块（LangChain + ChromaDB）。
     - `embeddings.py`：QwenEmbeddings 封装阿里云 DashScope text-embedding-v3 API。
     - `vectorstore.py`：VectorStoreManager 管理 ChromaDB 向量库。
     - `retriever.py`：DecisionRAGRetriever 根据害虫类型和作物名称检索。
     - `knowledge_loader.py`：从 SQLite 或 JSON 文件加载农药知识。

5. `modules/drone/` — 无人机域
   - `controller.py`：无人机任务执行与状态回写。
   - `mission_planner.py`：飞行/喷洒规划。
   - `px4_simulator.py`：PX4 SITL / MAVSDK 执行链路。

6. `modules/infra/` — 基础设施域
   - `common.py`：公共路径、日志、配置加载。
   - `event_bus.py`：JSONL 事件总线，跨模块通信的唯一通道。
   - `sqlite_store.py`：SQLite schema 和读写封装。
   - `weather.py`：和风天气接入与映射，支持 real/mock 双模式。

8. `frontend/`
   - 基于 Vite + React + TypeScript 的唯一前端。
   - 统一承接图片上传、原图/识别图对比、天气/决策卡片、无人机工作流、态势图、任务历史和实时日志。

## 安装依赖

```bash
cd /home/qingking/muye
pip install -r requirements.txt
```

前端开发依赖安装：

```bash
cd /home/qingking/muye/frontend
npm install
```

如果你已经安装了项目内虚拟环境，也可以直接使用：

```bash
cd /home/qingking/muye
. .venv/bin/activate
```

## 环境变量配置

项目提供两个环境配置参考文件：

- [`.env.example`](/home/qingking/muye/.env.example)：模板文件
- [`api_keys.env`](/home/qingking/muye/config/api_keys.env)：当前项目运行时读取的配置文件

和风天气开发者 Key 获取方式：

1. 访问 `https://console.qweather.com`
2. 注册并登录和风天气开发者平台
3. 创建项目并申请 API Key
4. 将 Key 写入 `QWEATHER_API_KEY`

推荐配置示例：

```env
YOLO_API_URL="http://127.0.0.1:8010/detect"
YOLO_API_KEY="muye-local-yolo-token"
YOLO_LOCAL_MODEL_PATH="models/best.pt"
YOLO_LOCAL_HOST="127.0.0.1"
YOLO_LOCAL_PORT="8010"

QWEN_API_URL="https://your-qwen-compatible-endpoint/v1/chat/completions"
QWEN_API_KEY="replace-with-your-qwen-key"
QWEN_MODEL="qwen-max"

QWEATHER_API_KEY="在此填入你的和风天气API_KEY"
QWEATHER_GEO_URL="https://api.qweather.com/geo/v2/city/lookup"
QWEATHER_WEATHER_URL="https://api.qweather.com/v7/weather/now"

DRONE_BACKEND="px4"
PX4_SYSTEM_ADDRESS="udpin://0.0.0.0:14540"
PX4_AUTO_START_ON_SPRAY="true"
SERVICE_CLIENT_IP="127.0.0.1"
```

说明：

- 请将训练好的权重文件放到 `models/best.pt`。
- 主流程中的业务数据仍可从 SQLite `fields` / `field_crop_cycles` 读取；PX4 实际执行默认走 `native_mission + use_existing_mission`，只调用 MAVSDK Mission 插件启动 QGC/PX4 已上传 Mission，不使用河南/业务地块经纬度作为飞控航点。
- `drone_config.json` 中的 `field.weather_location` 或 `field.location.city` 只作为业务天气查询回退，不作为 PX4 飞控航点来源。
- 本地 YOLO API 默认读取 `YOLO_LOCAL_MODEL_PATH`，主流程默认调用 `YOLO_API_URL`。
- `YOLO_API_KEY` 同时用于主项目访问本地 YOLO API 的 Bearer Token。
- `MUYE_SQLITE_PATH` 默认是 `~/.muye/data/muye.db`，主处理链会把任务、检测、天气和决策摘要同步写入该库。
- `MUYE_ACTIVE_FIELD_ID` 可指定当前作业链路优先使用的数据库地块 ID。
- `drone_config.json` 中 `simulate_capture=true` 时，系统会自动生成一张最小 JPEG 作为采图结果，便于本地联调。
- `DRONE_BACKEND` 环境变量控制无人机后端选择（`px4` PX4 SITL 仿真 | `dji_osdk` DJI OSDK 真实无人机），默认 `px4`。
- 本地 PX4 运行默认使用 `px4.execution_mode=native_mission` 和 `px4.use_existing_mission=true`；后端会先读取 PX4 中已有 Mission，确认存在航点后才调用 `start_mission()`。
- 前端地图大屏不绑定 PX4 航线，继续只做任务动画演示；PX4 中的真实 SITL 飞机按 QGroundControl/PX4 中规划并上传的 Mission 飞行。
- 如 PX4 中没有已上传 Mission，系统会直接提示先在 QGroundControl 中规划航线并 Upload 到飞机，不再由牧野临时生成或上传航点。
- PX4 实际飞行不会用业务 planner 的河南经纬度航线生成飞控航点；业务 planner 的经纬度航线只用于前端展示和任务记录。
- 使用步骤：先启动 PX4/QGroundControl，规划航线并 Upload 到飞机；再运行 `bash scripts/demo.sh`，前端确认起飞后牧野只调用 `start_mission()`。
- 演示模式下 `return_to_launch_after_mission=false`，固定本地航线末尾回到起飞点附近，避免额外 RTL 造成观感上偏离路线。
- 当前脚本默认使用 `PX4_SYSTEM_ADDRESS=udpin://0.0.0.0:14540`，直接监听 PX4 的 Onboard MAVLink 远端端口。

## 运行方式

### 环境准备

```bash
cd /home/qingking/muye
./scripts/prepare.sh
```

检查 Python/Node.js 依赖、准备巡检图片、确认 YOLO 模型。

### 演示模式（竞赛评审）

```bash
cd /home/qingking/muye
./scripts/demo.sh
```

脚本会启动主 API、后台处理链、YOLO API 和 React 前端，然后只投喂一张巡检图片。
决策完成后前端显示”确认起飞”，操作人员点击确认后，系统自动启动 PX4 SITL 并执行喷洒航线。

**demo.sh 参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--image <path>` | `data/samples` 第一张图片 | 指定本轮投喂图片 |
| `--api-port <port>` | `18000` | API 端口 |
| `--frontend-port <port>` | `5173` | 前端端口 |
| `--skip-precheck` | - | 跳过环境检查 |
| `--skip-inject` | - | 跳过图片投喂 |

### 生产模式（24h 自动巡检）

```bash
cd /home/qingking/muye
./scripts/run.sh
```

启动后自动采集图片 → YOLO 检测 → AI 决策 → 自动喷洒 → 自动复检 → 多轮循环至杀灭率达标，每 24 小时重复一次。

**run.sh 参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--api-port <port>` | `18000` | API 端口 |
| `--frontend-port <port>` | `5173` | 前端端口 |
| `--no-frontend` | - | 不启动前端（无头运行） |
| `--skip-precheck` | - | 跳过环境检查 |

生产模式需先配置 `.env.production`（API Key、PX4 SITL 等），详见 `scripts/run.sh --help`。

### 默认启动后

- 主 API 监听 `127.0.0.1:18000`
- YOLO API 监听 `127.0.0.1:8010`
- React 前端监听 `127.0.0.1:5173`
- 按 `Ctrl+C` 会一起停止所有服务

### 接入真实无人机

系统支持通过 DJI OSDK 后端对接 Matrice 系列行业级无人机（M300 / M350 / 30T）。接入步骤：

1. 配置环境变量（`.env.production`）：

   ```bash
   DRONE_BACKEND=dji_osdk
   DJI_OSDK_EXECUTION_MODE=osdk_real
   DJI_OSDK_SERIAL_PORT=/dev/ttyACM0
   DJI_OSDK_BAUD_RATE=921600
   DJI_OSDK_DRONE_MODEL=Matrice 30T
   ```

2. 确认无人机已通过串口连接（默认 `/dev/ttyACM0`）

3. 启动系统：`./scripts/run.sh`

无真实硬件时，可使用 `DJI_OSDK_EXECUTION_MODE=osdk_sim` 进行仿真测试，无需任何物理设备。

## 河南参考数据导入

仓库已经内置第一批河南参考数据 seed，当前包含：

- 官方数据来源登记
- 河南省农业统计指标
- 河南农药目录示例 seed

相关文件：

- [`sources.json`](/home/qingking/muye/data/seeds/henan/sources.json)
- [`agri_statistical_indicators.json`](/home/qingking/muye/data/seeds/henan/agri_statistical_indicators.json)
- [`pesticide_catalog.json`](/home/qingking/muye/data/seeds/henan/pesticide_catalog.json)
- [`import_henan_reference_data.py`](/home/qingking/muye/scripts/import_henan_reference_data.py)

导入方式：

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/python scripts/import_henan_reference_data.py
```

导入后的数据会写入：

- `data_sources`
- `agri_statistical_indicators`
- `pesticide_catalog`

其中 `pesticide_catalog` 当前是本地联调用的河南示例目录 seed，用于打通喷洒记录与农药目录关联；后续应替换为正式导出的官方登记数据。

所有导入记录都带有来源 URL、发布单位和来源摘录，便于后续核验。

## 河南地块与作物种子

当前仓库已补齐河南地块、作物目录和种植季 CSV seed，并提供数据库导入脚本。

生成 CSV：

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/python scripts/generate_henan_field_crop_seed_csv.py
```

导入 SQLite：

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/python scripts/import_henan_field_crop_seed_csv.py
```

导入后会写入：

- `fields`
- `crop_catalog`
- `field_crop_cycles`

当前历史天气导入脚本也会优先根据站点经纬度和区县信息，把天气日值自动挂到最近的河南地块上。

## 河南土壤检测种子

当前仓库已经补齐一份河南土壤检测示例 seed，并提供生成脚本和导入脚本。

相关文件：

- [`soil_records.csv`](/home/qingking/muye/data/seeds/henan/soil_records.csv)
- [`generate_henan_soil_seed_csv.py`](/home/qingking/muye/scripts/generate_henan_soil_seed_csv.py)
- [`import_henan_soil_records_csv.py`](/home/qingking/muye/scripts/import_henan_soil_records_csv.py)

重新生成 CSV：

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/python scripts/generate_henan_soil_seed_csv.py
```

导入 SQLite：

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/python scripts/import_henan_soil_records_csv.py
```

导入后会写入：

- `soil_records`

当前 `soil_records.csv` 主要用于本地联调和后续决策扩展验证；等你拿到真实土壤检测数据后，可以直接替换为真实 CSV 再走同一条导入链。

## 文档系统

项目采用 Agent-First 文档体系，所有知识存储在 Git 仓库中：

- `AGENTS.md` — AI Agent 情境地图，每次对话的核心入口
- `CLAUDE.md` — 最高命令，强制规则：修改代码必须同步更新文档
- `ARCHITECTURE.md` — 架构分层和依赖规则
- `DESIGN.md` — 设计指南和命名约定
- `docs/design-docs/` — 设计文档和核心工程信念
- `docs/exec-plans/` — 执行计划和技术债务
- `docs/generated/` — 自动生成文档（DB Schema）
- `docs/product-specs/` — 产品规格
- `docs/references/` — API、数据模型、RAG 参考

每次涉及架构、数据模型、演示链路或关键运行方式变化时，运行 `python3 scripts/verify_docs.py` 验证文档一致性。

当前项目推荐运行组合：

- YOLO：真实本地模型 `best.pt`
- 和风天气：真实接口
- 千问：支持真实接口，也支持通过 `QWEN_USE_MOCK` 切换为模拟模式
- 无人机：`PX4 SITL / MAVSDK`

当你的 [api_keys.env](/home/qingking/muye/config/api_keys.env) 中设置为：

```env
QWEATHER_USE_MOCK="false"
QWEN_USE_MOCK="false"
```

系统会运行在“真实天气 + 真实千问 + PX4 SITL”模式。

推荐一键启动本地 YOLO API 与主系统：

```bash
cd /home/qingking/muye
python -m app.main --with-yolo-api --drone-backend px4
```

可通过 `--drone-backend dji_osdk` 或设置 `DRONE_BACKEND=dji_osdk` 切换到 DJI OSDK 真实无人机。

执行一次完整链路后退出：

```bash
cd /home/qingking/muye
python -m app.main --with-yolo-api --drone-backend px4 --once
```

如果你希望分开启动，也可以先启动本地 YOLO API：

```bash
cd /home/qingking/muye
python -m app.yolo_api
```

可选检查：

```bash
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:9010/health
```

再启动主系统：

```bash
cd /home/qingking/muye
python -m app.main
```

## 可视化演示面板

后端与前端通过同一个事件文件连接：

- 事件总线文件：`data/logs/demo_events.jsonl`
- 图片投喂目录：`data/images/`

如果你已经使用一键脚本启动，这一节可以跳过。

手动启动时，推荐使用三个终端同时启动：

终端 1，启动后端主流程：

```bash
cd /home/qingking/muye
. .venv/bin/activate
python -m app.main --with-yolo-api --drone-backend px4
```

终端 2，启动前端 API：

```bash
cd /home/qingking/muye
. .venv/bin/activate
python -m uvicorn app.main:api_app --host 127.0.0.1 --port 18000
```

终端 3，启动 React 前端：

```bash
cd /home/qingking/muye
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

如果不是通过脚本启动，而是手工启动前端，且前端 API 不在默认 `18000`，需要显式指定代理目标：

```bash
cd /home/qingking/muye/frontend
MUYE_API_TARGET=http://127.0.0.1:18100 npm run dev -- --host 127.0.0.1 --port 5173
```

启动后：

1. 在 React 大屏顶部操作条上传图片
2. 前端会通过 `/api/demo/upload-image` 将图片写入 `data/images/`
3. 后端监听到新图片后，依次执行 YOLO、天气、千问和无人机流程
4. 事件总线持续写入 `data/logs/demo_events.jsonl`
5. React 前端会刷新原图、识别框、天气卡片、AI 建议、态势图和无人机状态
6. 顶部运行模式条会直接显示当前是 `real` 还是 `mock` 模式

## 日志与数据

- 无人机图片存放在 `data/images/`
- 系统日志存放在 `data/logs/system.log`
- 实时事件总线存放在 `data/logs/demo_events.jsonl`
- 结构化业务数据默认写入 `~/.muye/data/muye.db`
- 日志会记录 `request_id`、`client_ip`、`duration_ms` 等字段

## 测试

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/pytest -q
```

测试覆盖：

- YOLO 检测结果过滤与响应校验
- 事件总线的写入、清空与任务视图聚合
- 和风天气地点查询与天气实况两步流程
- 本地 YOLO API 的鉴权与标准输出格式
- PX4 状态推进
- 千问决策 JSON Schema 校验与结构化输入构建
- 决策路由评分与路径选择
- 多智能体会诊编排、投票、置信度计算
- LLM 调用重试（5xx 重试、4xx 不重试、网络错误重试、重试耗尽）
- 专家路径自动升级到多智能体会诊
- SQLite 迁移、结构化历史读取与农业数据写入
- 主流程 `spray_records` / `pesticide_catalog` / 地块上下文联动

## 前端构建与缓存策略

为了解决 React 大屏初始构建产物过大、业务代码改动会牵连整包失效的问题，当前前端已启用显式代码分割。

当前 `frontend/vite.config.ts` 的拆包策略：

- `vendor-react`
  - `react`
  - `react-dom`
- `vendor-map`
  - `leaflet`
  - `react-leaflet`
- `vendor-misc`
  - 其余第三方依赖

这样做的效果是：

- 业务主包只保留当前页面和业务逻辑，首屏主业务 chunk 显著变小。
- 地图库被拆成独立 vendor chunk，更适合浏览器缓存复用。
- 当只修改业务代码时，只要相关 vendor 依赖内容没有变化，浏览器通常不需要重新下载 `vendor-map` 等大包。

当前仓库构建结果中，文件名已经带内容哈希，例如：

- `vendor-map-*.js`
- `vendor-react-*.js`
- `index-*.js`

这意味着缓存策略已经具备“按内容变更失效”的前提条件：

- 业务代码变更但 vendor 内容不变时，vendor 文件名不会变化，浏览器可以继续复用缓存。
- 只有当对应 chunk 内容真的变化时，哈希才会变化，浏览器才会重新请求新文件。

需要注意：

- `Vite` 只负责生成带 hash 的静态资源文件名，不负责最终线上缓存头。
- 如果希望浏览器“长效缓存”这些大包，部署时还需要让静态资源服务器对 `dist/assets/*` 返回长期缓存头。

推荐部署策略：

- `index.html`
  - 使用短缓存或 `no-cache`
- `dist/assets/*.js`
  - 使用长期缓存，例如 `Cache-Control: public, max-age=31536000, immutable`
- `dist/assets/*.css`
  - 使用长期缓存，例如 `Cache-Control: public, max-age=31536000, immutable`

因此，当前前端代码分割配置已经满足“vendor 大包可长期缓存”的技术前提；真正的长效缓存是否生效，取决于部署层是否按上面的方式配置静态资源缓存头。

仓库里已经补了一份可直接参考的 Nginx 现场演示示例配置：

- [`deploy/nginx.conf`](/home/qingking/muye/deploy/nginx.conf)
- [`deploy/muye_backend.service`](/home/qingking/muye/deploy/muye_backend.service)

该配置已经覆盖三件事：

- 对 `dist/assets/*` 设置一年 `immutable` 长缓存
- 对 `index.html` 设置 `no-cache`
- 对 `/api/` 做反向代理，并为前端路由开启 `history` 模式回退
- 默认走本地网络 HTTP，降低比赛现场证书与域名依赖

`deploy/muye_backend.service` 则用于把 `FastAPI + Uvicorn` 作为 `systemd` 服务托管，满足：

- 后台常驻运行
- 开机自启
- 进程崩溃后自动重启

当前示例假设：

- 系统 Python 在 `/usr/bin/python3`
- 后端代码目录在 `/var/www/muye/backend`
- 虚拟环境在 `/var/www/muye/backend/.venv`
- Uvicorn 监听 `127.0.0.1:8000`

补充说明：

- 当前后端没有额外挂载独立静态资源目录，任务原图和识别图仍通过后端 API 动态返回，因此 Nginx 不需要再单独 `alias` 一套后端静态目录。
- 当前前端地图实时态势使用 `/api/sim/ws/map-state`，`deploy/nginx.conf` 中 `/api/` 已包含 `Upgrade/Connection` 头透传，可支持 WebSocket。
- `deploy/muye_backend.service` 已加入 `EnvironmentFile=/var/www/muye/backend/.env`，并显式使用 `.venv/bin/uvicorn`。
- 服务文件内已补部署备注：上线后应先对 `/var/www/muye/backend/data` 执行 `chown -R www-data:www-data`。
- 当前 `deploy/nginx.conf` 以“比赛现场优先”为默认口径：`HTTP + 本地局域网访问 + WebSocket + 大文件上传`；如果后续要上公网，再单独补 HTTPS 站点配置。

## 版本记录

- `v1.1.1`
  - SQLite 迁移支持发布线
  - 补齐旧库迁移工具 `scripts/migrate_to_v1_1.py`
  - 补齐迁移回归测试与迁移文档

- `v0.1-initial`
  - 项目初始稳定版本
  - 包含基础的 YOLO、天气、千问、无人机控制和测试结构

- `v0.2-initial`
  - 当前稳定运行版本
  - 已支持真实 YOLO、真实和风天气、真实千问增强链路、PX4 SITL 和可视化指挥中心前端

- `v0.3-initial`
  - 增加一键启动脚本 `scripts/demo.sh`
  - README 补齐完整演示启动流程与实际可用测试命令
  - 已验证后端全链路与 React 演示前端可一起运行

- `v1.3`
  - 已接入 `PX4 + Gazebo SITL` backend
  - 已补完整 PX4 一键演示脚本链
  - 已将 SQLite 深化接入主 pipeline、前端历史读取和农业数据层

- `v1.4`
  - 多模型多智能体会诊：Qwen + DeepSeek + 小米 MiMo 三模型并行推理，加权投票
  - DecisionRouter 路由层：熟悉度评估，专家路径 vs 多智能体会诊自动选择
  - 专家路径自动升级：失败时降级到多智能体会诊，保证决策总能产出
  - LLM 调用指数退避重试：5xx/网络错误自动恢复
  - RAG 知识库扩充：农药 30 条、作物 5 种、害虫同义词 27 组、历史决策 200+ 条
  - 历史决策种子脚本：基于 IP102 害虫数据集生成 mock 历史决策

## 部署建议

- 将 `config/api_keys.env` 中的示例值替换为真实密钥，避免提交到公共仓库。
- 若需要增强安全性，可在网关层补充 API 密钥认证、IP 白名单和速率限制。
- 如需监控，可在现有日志基础上接入 Prometheus/Grafana，并为 YOLO/Qwen/无人机接口增加指标采集。
- 上传接口当前默认限制单文件 `<= 10MB`，如果现场图片更大，需要同时调整后端常量和 Nginx `client_max_body_size`。
- `/demo/reset-events` 现在是破坏性操作，调用时必须显式带 `confirm=true`。
- `workflow/history.total` 当前返回的是“SQLite + event bus 合并、过滤、分页前”的真实总数；`items` 则严格受 `limit` 控制。
