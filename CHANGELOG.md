# Changelog

> 顶部记录当前未发布变更；下方保留早期开发记录，其中部分实现已经被后续版本替代。

## Unreleased (2026-08-04)

### 昆虫热力指挥大屏

- 首页统一为 React + Three.js 单田地昆虫热力大屏，不接省级行政地图。
- 热力值改为稳定的后端任务数据；WebSocket 空包或回退包不会清除最后有效热力帧。
- 前端不再随机生成虫情，模拟种子与真实 YOLO 检测具有明确来源标记。
- 移除 ECharts 与 Drei 依赖，历史和设置页按路由懒加载。

### YOLO 与热力数据契约

- Ultralytics 像素检测框携带原图尺寸和坐标空间，缺少尺寸的像素框不进入真实密度网格。
- `density_metadata` 记录来源、投影、归一化、接收/拒绝数量和模拟标记，并随任务持久化。
- 明确 `density` 是本次任务内相对热值，不是每亩虫口数或农艺防治阈值。

### 巡检与热力快照数据层

- 新增 `inspection_batches`、`inspection_detections` 和 `heatmap_snapshots`，独立保存喷洒前巡检与药效复检数据。
- 快照持久化 `field_id`、`request_id`、图片引用、分类计数、完整相对热值网格、来源、模拟标记和算法版本。
- 快照通过 `mission_id`、`iteration_number` 和 `inspection_kind` 关联喷洒/复检闭环；进程重启后不依赖事件日志即可恢复。
- 旧任务可从历史无人机指令只读转换为 `legacy-unversioned` 快照，不修改原始数据。

### 热力快照查询 API

- 新增最新快照、分页列表、完整详情和喷洒前后配对接口。
- 列表支持按地块、任务、虫种、采集时间、来源、巡检类型和模拟标记组合筛选。
- 对分页范围、时间倒置、非法巡检类型、空结果和不存在快照提供稳定边界响应；列表摘要同时返回热点网格数与峰值相对热值。

### 热力历史分析与对比

- 首页增加虫种筛选和持久快照时间/算法标识；选择单一虫种时根据该虫种原始检测框重建子集热力，不复用全虫种网格冒充筛选结果。
- 历史页增加虫种、来源、巡检阶段和起止日期筛选，并展示可追溯的快照列表与相对热值网格。
- 新增检测数量、热点网格数量、峰值相对热值趋势，以及无闪烁的喷洒前后并列对比；页面明确跨快照独立归一化和正式药效结论边界。
- 移除缺失坐标检测框的前端虚拟散点，不再为无法定位的虫情补造田间位置。
- 新增 Playwright 真实 Chromium 布局验收，在 1366×768、1920×1080 和 1920@125% 等效区域验证大屏面板/中央地图不重叠以及历史页局部滚动边界；CI 保留六张截图与失败 trace。
- 升级 Axios 并移除处于安全公告窗口期的 React Router；三个静态页面改用浏览器 History API 轻量导航，生产依赖 high/critical 审计清零并接入 CI。

### 变量喷洒追溯闭环

- `mission_iterations` 持久化每轮喷洒消费的 `heatmap_snapshot_id`、热力算法版本和完整喷洒计划。
- 初次喷洒绑定喷洒前快照；复检快照会成为下一轮变量喷洒的输入，不再默认退回均匀规划。
- 喷洒计划显式记录变量/均匀模式、降级原因和低/中/高热值对应的 0.5/1.0/1.5 倍喷洒策略。
- 任务 API 和历史页显示快照到喷洒轮次、算法版本及速率范围的完整追溯关系。

### 生产启动与容器配置

- 新增 `.env.production.example`，修复 `prepare.sh --production` 参数解析和模型路径检查。
- 生产 PX4 默认使用 `real` MAVSDK 执行链路；未知模式不再静默降级成动画。
- 本地 YOLO 模型缺失时启动立即失败。
- 修复 Docker Compose 构建路径、端口、挂载、健康检查和确定性本地联调配置。
- 新增独立 `docker-compose.smoke.yml` 和 `scripts/docker_smoke.sh`，用显式标记的固定检测器验证前端代理、图片上传、目录监听、YOLO 请求与工作流状态；默认真实模型入口仍保持缺权重快速失败。
- 新增 `docker-compose.real-smoke.yml` 和 `scripts/docker_real_smoke.sh`：使用独立数据卷验证真实权重加载、样本推理、像素框尺寸与公开 HTTP 链路；默认 Compose 改用跨进程 readiness 并将宿主机端口限制在回环地址。
- 修复后端镜像在 Debian trixie 上构建失败：`libgl1-mesa-glx` 已被移除，改用 `libgl1` 提供 OpenCV 所需的 `libGL.so.1`。

### 文档与质量

- 新增昆虫热力图产品规格和产品化执行计划，固定单田地、来源可追溯和相对热值边界。
- 新增 6 场景固定热力回归集，覆盖 3 类 IP102 害虫、空检测、缺少坐标和非法围栏；图片、完整网格、航线与喷洒速率均以 SHA-256 锁定并接入赛前总检查。
- 新增 GitHub Actions CI，使用只读权限并行执行 Python 3.11 后端/数据/文档检查、Node.js 22 前端质量/真浏览器布局检查，以及 Docker Compose 配置、双镜像构建和隔离端到端冒烟；固定评测报告、前端产物、视口截图和失败 trace 保留 14 天。
- 同步更新架构、产品理念、安全、设计、质量基线、路线图和文档索引。
- 当前验证基线：后端 372 passed / 1 skipped，前端 33 个 Vitest + 6 个 Playwright 场景，固定数据回归、构建与文档校验通过。

## 2026-05 基线（已归档）

### 密度热力图 + 变量喷洒可视化

- **前端密度热力图渲染**：后端 `density_grid` 数据通过 workflow state 传递到前端，GPS→SVG 投影渲染
- **变量喷洒航线着色**：每条航线段按喷洒速率差异化着色（高密度红/中密度琥珀/低密度绿）+ 粗细变化
- **图例与统计**：地图图例增加三级密度标注，侧边栏增加密度统计卡片（网格数、最高密度、喷洒速率范围）
- **无人机转弯加速**：直线速度不变，转弯区域（靠近航点）速度提高至 4 倍
- **Bug 修复**：`GET /drone/density-map` 端点 SQL 查询错误（`tasks.drone_instruction` 列不存在，改为 `drone_mission_updates.instruction`）
- **Demo seed 数据**：注入模拟密度网格（8×10 格，中心高密度梯度分布）和差异化喷洒速率

### 文档全面更新

- **db-schema.md**：从实际 DDL 重写，补齐 8 个缺失表，修正全部列定义
- **api.md**：补齐 `/demo/readiness`、`/drone/start-px4-demo`、`/drone/stop-px4-demo` 端点
- **索引文件**：新增 `docs/knowledge/index.md`、`docs/superpowers/index.md`
- **测试数据**：更新 DESIGN.md/QUALITY_SCORE.md 测试数量（347+ 后端，60 前端）
- **PRODUCT_SENSE.md**：暗色主题→暖色主题
- **PLANS.md**：补齐多智能体会诊、合规推理链、密度热力图等已完成项

### Bug 修复（6 项）

- **PX4 进程未被终止**：`app/routes/drone.py` 中 `_kill_px4_process` 是 async 函数但调用处缺少 `await`，导致 PX4 进程无法被终止。修复：添加 `await`，测试改用 `AsyncMock`
- **评估取消状态不一致**：`cancel_evaluation` 写入 DB 状态为 `evaluated` 但 API 返回 `cancelled`，且 CHECK 约束不含 `cancelled`。修复：CHECK 约束添加 `cancelled`，写入改为 `cancelled`，文档同步
- **任务循环未跟踪**：`_run_mission_loop` 的 `asyncio.create_task` 未加入 `_background_tasks`，关闭时无法取消。修复：添加到 `_background_tasks` 并注册 done callback
- **评估上下文内存泄漏**：`_evaluation_contexts` 字典只增不减。修复：在 `_run_mission_loop` 的 `finally` 块中清理
- **复检产生虚假 YOLO 事件**：复检时 `_detect_pests` 向事件总线发布事件覆盖原始任务状态。修复：`_detect_pests` 新增 `publish_events` 参数，复检时传 `False`
- **`get_sqlite_store` 线程不安全**：手动单例无锁保护，且 `_SQLITE_PATH` 在模块导入时求值导致测试隔离失效。修复：添加 `threading.Lock`，路径改为惰性计算，新增 `reset_sqlite_store()` 供测试使用

### 无人机后端配置化

- 解除 `--drone-backend` 的 px4 硬编码限制，支持通过 `DRONE_BACKEND` 环境变量切换后端
- `app/main.py` 删除 `execution["backend"] = "px4"` 硬覆盖，改为从配置和环境变量读取
- `configure_drone_backend()` 改为基于 `BACKEND_REGISTRY` 注册表校验
- `run.sh` 从 `DRONE_BACKEND` 环境变量读取后端（默认 `px4`），支持 `DRONE_BACKEND=dji_osdk` 切换到 DJI OSDK
- `.env.production` 添加无人机后端和 DJI OSDK 配置项

## 2026-05 开发记录（已归档）

- 演示天气固定：
  - `scripts/demo.sh` 启动时强制使用本地天气数据，并将演示湿度固定为 `70%`
  - 避免真实和风天气接口返回值波动影响前端大屏和 AI 决策链展示

- PX4 Mission 航线执行修正：
  - `PX4Simulator` 会确保本地航线第一个 setpoint 就是当前起飞点，避免飞机起飞后先斜飞到远处矩形角点
  - `scripts/demo.sh` 每次启动都会写入显式 `local_route.points`，PX4 演示固定按 `12m x 8m` 本地米制矩形扫线飞行
  - `config/drone_config.json` 默认 PX4 本地航线同步改为显式固定航点，最后一个航点回到当前起飞点附近，便于 SITL 中稳定观察
  - PX4 执行链路从 Offboard setpoint 切换为 MAVSDK Mission 插件，默认 `execution_mode=native_mission`
  - 默认启用 `px4.use_existing_mission=true`，只启动 QGroundControl/PX4 已规划并上传的 Mission，牧野不上传航点、不接管起飞高度
  - 启动前会读取 PX4 中已有 Mission；没有航点时直接提示先在 QGroundControl 中规划并 Upload 航线
  - 前端地图大屏继续只做动画展示，PX4 中的真实 SITL 飞机按 QGC/PX4 Mission 飞行
  - 演示模式关闭 `return_to_launch_after_mission`，避免固定 Mission 结束后额外 RTL 造成观感上偏离路线
  - 验证：`.venv/bin/python -m pytest tests/test_px4_simulator.py -q`

- 前端地图大屏布局调整：
  - `FieldMap` 将地图图例、飞行参数和无人机实时状态从 SVG 画布绝对叠层中移出，改为独立信息栏展示
  - 大屏下地图主画布保留地块、航线、无人机、检测点和指挥点，减少信息遮挡
  - 平板和手机断点改为信息栏下排/单列布局，避免状态卡片压在地图上
  - 地图大屏不再接入 PX4 实时遥测、PX4 字段边界、PX4 计划航线或后端 sim map；前端只基于任务规划航线/默认航线做循环动画展示
  - 当前任务缺少规划航线时，地图会根据地块边界自动生成覆盖式往返航线，并加粗航线描边，保证大屏始终可见
  - 验证：`cd frontend && npm run build`

- 无人机运行链路收敛为单一 PX4 工作流程：
  - `scripts/demo.sh` 现在固定为单轮现场流程：一键启动前后端和 YOLO，只投喂一张巡检图片，前端人工确认起飞后自动启动 PX4 SITL
  - `scripts/demo.sh` 删除原无人机模式切换参数和虚拟模式分支，固定以 `--with-yolo-api --drone-backend px4` 启动主流程
  - `config/drone_config.json` 默认改为 `execution.backend=px4`、`simulate_only=false`
  - PX4 执行链路固定使用 `native_mission + use_existing_mission`，只启动 PX4/QGC 已上传 Mission，不再使用河南/业务地块经纬度作为飞控航点
  - `config/drone_config.json` 新增 `px4.local_route`，用本地米制宽高和扫线数量定义 PX4 实际飞行图形
  - PX4 实际飞行不再使用业务 planner 的经纬度航线缩放形状；即使配置里误开 `use_planner_shape`，后端也会回退到本地米制扫线
  - PX4 本地航线现在按连接时读取到的当前全局位置锚定，避免把业务航线或错误地块经纬度当成实际起点
  - `app/main.py` 运行时强制 `px4.execution_mode=native_mission`，避免环境变量或配置切回旧 Offboard 控制路径
  - `PX4Simulator` 默认执行分支改为只启动 QGC/PX4 已规划 Mission；保留上传固定 Mission 的代码路径但 demo 默认不使用
  - `PX4Simulator` 状态 payload 回到 PX4 Mission 位置回传，前端遥测层仅用于展示，不参与 PX4 控制
  - `app/main.py` 删除原多模式无人机栈入口，`--drone-backend` 固定为 `px4`
  - 删除原独立无人机 API 服务和对应测试
  - `modules/drone/controller.py` 删除远程 API / 本地模拟执行分支，直接执行 PX4 SITL
  - 前端工作流文案和无人机链路展示收敛为 PX4 SITL
  - README、ARCHITECTURE、PROJECT_MEMORY、项目说明同步更新为单一 PX4 运行口径

- 前端首页已按比赛演示场景重构为“答辩导向”视图：
  - [`frontend/src/pages/Dashboard.tsx`](/home/qingking/muye/frontend/src/pages/Dashboard.tsx) 新增演示抬头、答辩讲解重点、本轮演示状态和作品亮点区块
  - 首页信息组织从“工程控制台”改为“项目价值 → 闭环流程 → 实时态势 → 当前成果”
  - 保留原有上传、刷新、清空事件、PX4 停止和人工确认起飞入口，避免影响现场操作
- 视觉主题已调成更适合大屏投放与答辩展示的方向：
  - [`frontend/src/index.css`](/home/qingking/muye/frontend/src/index.css) 更新全局配色、背景和字体令牌
  - [`frontend/src/styles/dashboard.css`](/home/qingking/muye/frontend/src/styles/dashboard.css) 增加演示英雄区、亮点卡片和更清晰的卡片层次
- 评委可读性优化：
  - [`frontend/src/utils/dashboardUtils.ts`](/home/qingking/muye/frontend/src/utils/dashboardUtils.ts) 新增害虫标签中文映射，避免首页直接展示 `aphid` 这类英文 slug
- 验证：
  - `cd frontend && npm run build`
  - 构建通过

- RAG 检索链继续收敛到更接近真实 demo 的状态：
  - `modules/decision/rag/retriever.py` 已从只查 `pesticides` 与 `decisions` 扩展为同时查询 `agri_knowledge`
  - 新增 demo 级害虫同义词归一化，缓解 `aphid/蚜虫`、`rice-planthopper/稻飞虱` 这类中英标签混用
  - `RetrievedContext` 中的分数展示统一改为“参考值”，避免把 Chroma 返回值误读为严格相似度
- 主流程现在会在 AI 决策完成并写入 SQLite 后，异步把新决策增量写入 `COLLECTION_DECISIONS`：
  - 新增 `build_historical_decision_document()`
  - `app/main.py` 新增后台增量索引任务调度与容错日志
  - 不阻塞图片处理主链路，索引失败只记 warning
- 新增测试覆盖：
  - `tests/test_rag_retriever.py`
  - `tests/test_knowledge_loader.py`
  - `tests/test_main.py::test_main_incrementally_indexes_decision_into_rag`
  - 定向回归：20 passed in 1.02s
- 本轮验证：
  - `.venv/bin/python -m pytest tests/test_drone_controller.py tests/test_field_context_resolver.py tests/test_main.py::test_main_reads_px4_backend_override tests/test_main.py::test_main_reads_px4_demo_field_override tests/test_main.py::test_main_forces_px4_demo_field tests/test_main.py::test_default_field_matches_px4_demo_field -q`
  - `.venv/bin/python -m pytest tests/test_px4_simulator.py tests/test_drone_controller.py tests/test_field_context_resolver.py tests/test_main.py::test_main_reads_px4_backend_override tests/test_main.py::test_main_reads_px4_demo_field_override tests/test_main.py::test_main_forces_px4_demo_field tests/test_main.py::test_default_field_matches_px4_demo_field -q`
  - `cd frontend && npm run build`

## v1.6 (2026-04-29)

- 演示脚本精简：
  - 将 10 个冗余脚本合并为 `scripts/prepare.sh` + `scripts/demo.sh` + `scripts/precheck.sh`
  - 已删除：start_demo.sh、run_px4_demo.sh、start_px4_visual_demo.sh、start_competition_mode.sh、start_all_in_one.sh、start_showtime.sh、precheck_demo.sh、prepare_demo_images.sh、start_demo_with_all_images.sh
  - `demo.sh` 当时支持无人机模式切换、`--takeoff manual|auto`、`--api-port`、`--frontend-port`
  - `prepare.sh` 支持 `--images-only`、`--check-only`、`--rag`，从 IP102 数据集复制真实害虫图片
- 无人机手动/自动起飞模式：
  - `config/drone_config.json` 新增 `execution.takeoff_mode`：`manual`（默认）/ `auto`
  - manual 模式：AI 决策后暂停，前端显示"确认起飞"按钮，评审可查看决策结果
  - 新增 `POST /drone/confirm-takeoff` 端点
  - 新增 `app/routes/drone.py`
  - 前端 `WorkflowPanel.tsx` 在 `pending_confirmation` 状态显示确认按钮
  - `app/deps.py` 新增全局 `takeoff_confirmation_event: asyncio.Event`
- 新增测试：
  - `test_confirm_drone_takeoff_returns_503_when_not_initialized`
  - `test_confirm_drone_takeoff_sets_event`
  - `test_confirm_drone_takeoff_returns_already_confirmed`
- 文档更新：
  - README.md 更新为新脚本入口
  - ARCHITECTURE.md 更新端口和数据流

## v1.5.1 (2026-04-29)

- 修复三个关键 Bug：
  - **重置事件链路失败**：前端 `resetDemoEvents()` 现正确传入 `confirm=true` 参数
  - **启动采图重复入队竞态**：删除 `capture_image()` 中的主动回调，完全依赖 watchdog 监听
  - **上传文件名不唯一**：使用 UUID 确保文件名唯一，避免同一秒上传覆盖
- 修改文件：
  - `frontend/src/api/workflow.ts`
  - `modules/detection/data_collector.py`
  - `app/routes/demo.py`
  - `tests/test_data_collector.py`
- 全量回归：150 passed in 6.68s

## v1.5

- RAG 决策增强链路已落地：
  - 新增 `modules/rag/` 完整 LangChain RAG 框架：
    - `embeddings.py` — `QwenEmbeddings` 封装阿里云 DashScope text-embedding-v3 API
    - `vectorstore.py` — `VectorStoreManager` 管理 ChromaDB 持久化向量库，支持 `pesticides` 与 `decisions` 两个 collection
    - `retriever.py` — `DecisionRAGRetriever` 根据害虫类型 + 作物名称检索相关农药推荐和历史案例；`RetrievedContext` 格式化检索结果为 prompt 文本
    - `knowledge_loader.py` — 从 SQLite `pesticide_catalog` 或 JSON 文件加载农药知识，支持从 `docs/` 目录加载 markdown 文档
    - `__init__.py` — 统一导出入口
  - `modules/ai_decision.py` 已集成 `rag_retriever` 注入：
    - 新增 `_build_rag_context_text()` 方法，在决策前检索相关知识
    - RAG 检索文本拼入 `build_structured_input_text()` 的 prompt
    - 失败降级：只记录 warning 和 `rag:error` 事件，不中断原决策流程
    - 通过 `event_bus` 发布 `rag:running/completed/error` 事件供前端展示
  - `main.py` 已集成 RAG 初始化 helper，默认启用但完全容错；首启时自动灌入农药目录知识库
  - 新增 `scripts/build_rag_knowledge.py` 用于构建 RAG 向量知识库，支持 `--rebuild` 清空重建
  - `requirements.txt` 新增 LangChain RAG 依赖：
    - `langchain>=0.3.0`
    - `langchain-community>=0.3.0`
    - `langchain-openai>=0.3.0`
    - `chromadb>=0.5.0`
    - `langchain-chroma>=0.2.0`
  - 新增测试覆盖：
    - `tests/test_rag_embeddings.py` — QwenEmbeddings API 请求/响应契约测试
    - `tests/test_rag_retriever.py` — DecisionRAGRetriever 查询参数、害虫类型过滤、crop_name 提取、RetrievedContext 格式化测试
- 后端继续模块化拆分：
  - `main.py` 进一步瘦身，路由注册下放到 `routes/*.py`
  - 新增 `core/config.py` 承接配置工具
  - 新增 `core/deps.py` 承接运行时依赖访问
  - 新增 `models/schemas.py` 承接前端 API Pydantic schema
  - 新增 `services/workflow_service.py` 承接工作流聚合服务层
- 全量回归测试：77 passed in 9.13s

## v1.4

- SQLite 决策增强上下文已正式接入当前主线：
  - 新增 `modules/decision_context.py`
  - `modules/ai_decision.py` 支持按开关注入 SQLite 农业上下文
  - `modules/sqlite_store.py` 扩展农业数据与决策支撑查询能力
- 前端已完成从旧 Streamlit 方案向 `Vite + React + TypeScript` 指挥大屏的主线迁移：
  - `frontend/` 成为唯一前端实现
  - `main.py -> api_app` 新增工作流、历史、上传、图片查看等接口
  - `scripts/start_demo.sh` / `scripts/start_px4_visual_demo.sh` 已切换到 React 前端链路
- PX4 可视化演示链进一步稳定化：
  - `modules/px4_simulator.py` 现在按真实遥测位置反算航线进度
  - 前端作业地图已切换为纯 `SVG` 渲染，避免运行态地图容器导致的不可见问题
  - `config/drone_config.json` 更新了冬小麦演示地块、演示航线和超时参数
  - `scripts/start_px4_visual_demo.sh` 与 `scripts/run_px4_demo.sh` 已增加 PX4 日志大小守卫，避免 `px4-visual-sitl-*.log` 与 `px4-sitl-*.log` 单次运行暴涨到数 GB
- 新增比赛与部署辅助能力：
  - 新增 `scripts/start_showtime.sh`
  - 新增 `deploy/nginx.conf` 与 `deploy/muye_backend.service`
  - `README.md`、`PROJECT_MEMORY.md`、`docs/WORKLOG.md` 已同步到当前真实工程口径

## v1.3

- 决策链路已调整为“数据库增强上下文可插拔，但默认关闭”：
  - `modules/ai_decision.py` 新增 `decision_context_provider` 注入位
  - 默认情况下，千问决策仍只使用害虫检测、实时天气和基础地块上下文
  - 只有显式设置 `MUYE_ENABLE_SQLITE_DECISION_CONTEXT=true` 时，才会把 SQLite 中的土壤、历史天气、候选农药等信息拼入决策输入
- 新增 [`modules/decision_context.py`](/home/qingking/muye/modules/decision_context.py)：
  - 定义决策增强上下文抽象
  - 落地 `SqliteDecisionContextProvider`
- `modules/sqlite_store.py` 新增 `fetch_decision_support_context()`，用于聚合：
  - 地块画像
  - 最新土壤记录
  - 近期历史天气
  - 候选农药目录
- 新增回归测试：
  - [`tests/test_ai_decision.py`](/home/qingking/muye/tests/test_ai_decision.py) 已覆盖 decision context provider 注入与 prompt 拼接
  - [`tests/test_decision_context.py`](/home/qingking/muye/tests/test_decision_context.py) 已覆盖 SQLite 决策增强上下文聚合
- React 前端已统一承接旧 Streamlit 面板能力：
  - 图片上传
  - 原图 / 识别图对照
  - 害虫识别摘要
  - 天气信息 / 千问建议 / 安全提示
  - 任务历史检索
  - 运行模式展示
- `main.py -> api_app` 新增前端迁移所需接口：
  - `/dashboard/context`
  - `/workflow/history`
  - `/demo/upload-image`
  - `/demo/reset-events`
  - `/tasks/{request_id}/original-image`
  - `/tasks/{request_id}/annotated-image`
- `workflow/state` 已扩展返回 `image_path`、`detections`、`weather` 和 `error`，供 React 前端直接渲染旧版功能区块。
- 旧 `app.py` Streamlit 前端已删除，当前仓库只保留 `frontend/` 作为前端实现。
- `scripts/start_demo.sh` 与 `scripts/start_px4_visual_demo.sh` 已切到启动 `Vite` React 前端，不再依赖 Streamlit。
- `scripts/start_demo.sh` 与 `scripts/start_px4_visual_demo.sh` 现在会同时拉起 `uvicorn main:api_app`，并在脚本链路中固定使用 `127.0.0.1:18000` 作为前端 API 端口，确保 React 前端代理到真实后端 API，而不是空的 `127.0.0.1:8000`。
- `frontend/vite.config.ts` 默认代理目标已统一为 `127.0.0.1:18000`，与当前演示脚本和手工启动说明保持一致。
- `scripts/start_demo.sh` / `scripts/start_px4_visual_demo.sh` 已支持 `--api-port`，`scripts/start_competition_mode.sh` / `scripts/start_all_in_one.sh` 已透传该参数，便于现场避让端口冲突。
- 新增 [`scripts/start_showtime.sh`](/home/qingking/muye/scripts/start_showtime.sh) 作为更高层的一键展示入口：
  - 默认启动稳定的 React + backend demo stack
  - `--with-px4` 时切换到 PX4/Gazebo 比赛演示链
  - 默认会在可用时自动注入仓库内置样例图，减少现场手工操作
- [`frontend/src/components/map/FieldMap.tsx`](/home/qingking/muye/frontend/src/components/map/FieldMap.tsx) 已删除旧版 3 个静态演示地块 fallback：
  - 地图现在只展示真实当前任务地块
  - 如有地块围栏则做归一化后渲染；无围栏时退回当前任务的覆盖区或合成轮廓
- PX4 实时位置跟随链路已打通：
  - [`modules/px4_simulator.py`](/home/qingking/muye/modules/px4_simulator.py) 现在会把 `telemetry.position()` 回传到任务事件
  - [`modules/drone_controller.py`](/home/qingking/muye/modules/drone_controller.py) 会把 `position` 写入无人机状态 payload
  - [`main.py`](/home/qingking/muye/main.py) 会在 `workflow/state` 中合并 SQLite 任务视图和 event bus 中更实时的 `drone` 字段
  - [`frontend/src/components/map/FieldMap.tsx`](/home/qingking/muye/frontend/src/components/map/FieldMap.tsx) 现在优先跟随 `latest_task.drone.position`
  - [`frontend/src/pages/Dashboard.tsx`](/home/qingking/muye/frontend/src/pages/Dashboard.tsx) 已把 `workflow/state` 轮询收紧到 `500ms`
- 前端地图中的航线已改为与 PX4 执行航线对齐：
  - [`frontend/src/components/map/FieldMap.tsx`](/home/qingking/muye/frontend/src/components/map/FieldMap.tsx) 现在优先读取 `drone.instruction.飞行路径`
  - 只有任务指令航线缺失时，才回退到 `field.explicit_route`
- [`frontend/src/components/map/FieldMap.tsx`](/home/qingking/muye/frontend/src/components/map/FieldMap.tsx) 已移除地图上的无人机轨迹线和系统规划航线线条：
  - 当前只保留真实地块面、覆盖区域和无人机点位
  - [`frontend/src/components/map/mapData.ts`](/home/qingking/muye/frontend/src/components/map/mapData.ts) 中旧的静态路线示例也已删除
- `main.py` 中的 [`Px4MapStateSimulator`](/home/qingking/muye/main.py) 已改为静态快照：
  - `/sim/map-state` 与 `/api/sim/map-state` 不再让无人机点位和电量随时间自行漂移
  - 当前地图上的无人机点位保持静止，避免继续呈现“自动巡航”演示效果
- [`config/drone_config.json`](/home/qingking/muye/config/drone_config.json) 中的 `px4.demo_field` 已调整：
  - 演示地块面积现已放大到约 `5.6 亩`
  - 地块名称调整为 `PX4 SITL 冬小麦演示田`
  - `crop_cycle.crop_name` 改为 `冬小麦`
  - `geofence` 已放大到约 `72m x 52m`
  - `explicit_route` 已放大到约 `61.9m x 40m`
  - `presentation_profile.lane_spacing_m` 与演示航线一并同步
- [`/home/qingking/PX4-Autopilot/Tools/simulation/gz/worlds/muye_demo_field.sdf`](/home/qingking/PX4-Autopilot/Tools/simulation/gz/worlds/muye_demo_field.sdf) 已同步重做 PX4 农田场景：
  - 删除会误导视感的旧小尺寸静态绿条作物
  - 放大土地区块、边界、沟垄和周边设施间距
  - 增加覆盖整块演示田的冬小麦冠层，让 Gazebo 中能直接看到更大的小麦田
- `frontend/vite.config.ts` 已增加 `manualChunks`：
  - `react` / `react-dom` 拆到 `vendor-react`
  - `antd` / `@ant-design/*` / `rc-*` 拆到 `vendor-ui`
  - `leaflet` / `react-leaflet` 拆到 `vendor-map`
  - 其余第三方依赖归入 `vendor-misc`
  - 目标是改善首屏缓存命中并降低主业务 chunk 变更频率
- `README.md` 已补充“前端构建与缓存策略”说明：
  - 明确记录当前代码分割方案和大包拆分边界
  - 明确说明 `vendor-map`、`vendor-ui` 等产物使用内容 hash 文件名
  - 明确说明浏览器长效缓存是否真正生效，还取决于部署层是否为 `dist/assets/*` 返回长期 `Cache-Control`
- 新增 [`deploy/nginx.conf`](/home/qingking/muye/deploy/nginx.conf) 作为比赛现场优先的部署示例：
  - `dist/assets/*` 返回一年期 `immutable` 缓存头
  - `index.html` 明确设置为 `no-cache`
  - `/api/` 反向代理到 `127.0.0.1:8000`
  - 非静态资源路径回退到 `index.html`，支持 SPA history 路由
  - 默认采用本地网络 HTTP，降低现场域名和证书依赖
- 新增 [`deploy/muye_backend.service`](/home/qingking/muye/deploy/muye_backend.service)：
  - 以 `systemd` 托管 `uvicorn main:api_app`
  - 约定后端目录为 `/var/www/muye/backend`
  - 约定 Python 为 `/usr/bin/python3`
  - 支持开机自启、崩溃自动重启
- `deploy/nginx.conf` 已补生产化细节：
  - `/api/` 代理增加 WebSocket 所需升级头、长连接超时和关闭代理缓冲
  - 新增 `client_max_body_size 20m`，避免图片上传被默认限制拦截
- `main.py` 已补生产级后端加固：
  - `/demo/upload-image` 现在会校验真实图片内容，并限制单文件不超过 `10MB`
  - `/health` 不再只返回固定 `ok`，而是检查 SQLite、`data/` 目录写权限和内嵌 YOLO runner 状态；任一失败时返回 `503`
  - `/workflow/history.total` 已改为返回“SQLite + event bus 合并后”的真实匹配总数，而不是当前页条数
  - `/workflow/history` 现在会在合并后再应用 `limit`，避免 event-only 任务突破分页限制
  - `/demo/reset-events` 现在必须显式传 `confirm=true`，并会同时清空 SQLite 任务运行态数据和 event bus
- `modules/sqlite_store.py` 新增：
  - `count_task_views()`
  - `clear_runtime_task_data()`
- `deploy/muye_backend.service` 已补生产化细节：
  - 新增 `EnvironmentFile=/var/www/muye/backend/.env`
  - 显式使用 `/var/www/muye/backend/.venv/bin/uvicorn`
  - 在文件注释中补充 `data/` 目录 `chown` 提示
- `requirements.txt` 已移除 `streamlit` / `streamlit-autorefresh`，并补入 `Pillow` 作为图片标注接口依赖。
- `tests/test_main.py` 已改为直接调用 endpoint 函数校验前端 API 契约，不再依赖 `TestClient`，当前文件测试可稳定通过。
- 新增 [`scripts/test_api.py`](/home/qingking/muye/scripts/test_api.py) 作为最小化后端接口探测脚本，可独立验证运行中的 `/api/health`、`/api/dashboard/context`、`/api/workflow/state` 与 `/api/workflow/history`。
- 新增并确认 `frontend/` 为当前新一代前端主线：
  - 采用 `Vite + React + TypeScript`
  - 使用 `Ant Design` 深色大屏风格
  - 补充 [`frontend/PROJECT_STRUCTURE.md`](/home/qingking/muye/frontend/PROJECT_STRUCTURE.md) 说明当前目录结构与中文注释
- 新增智慧农业指挥大屏首页：
  - [`frontend/src/pages/Dashboard.tsx`](/home/qingking/muye/frontend/src/pages/Dashboard.tsx)
  - 顶部显示“牧野智农 · 智慧农业指挥中心”和实时时钟
  - 左侧显示当前作业面积、在线设备数和千问建议卡片
  - 右侧显示“当前任务 / 最近任务”列表
  - 底部补回工作流闭环面板，恢复旧 Streamlit 的流程感
- 新增 PX4 虚拟农田态势图组件：
  - [`frontend/src/components/map/FieldMap.tsx`](/home/qingking/muye/frontend/src/components/map/FieldMap.tsx)
  - 使用 React Leaflet + `CRS.Simple`，不再依赖真实地理底图
  - 展示虚拟地块、无人机位置、航线与指挥中心
- 新增前端工作流接口与类型：
  - [`frontend/src/api/workflow.ts`](/home/qingking/muye/frontend/src/api/workflow.ts)
  - [`frontend/src/types/workflow.ts`](/home/qingking/muye/frontend/src/types/workflow.ts)
  - [`frontend/src/components/workflow/WorkflowPanel.tsx`](/home/qingking/muye/frontend/src/components/workflow/WorkflowPanel.tsx)
- `main.py` 新增面向新前端的 API 聚合层：
  - `api_app = FastAPI(title="Muye Frontend API", version="1.3.0")`
  - 新增 `/health`、`/sim/map-state`、`/workflow/state`
  - 同时提供 `/api/*` 兼容路径
  - 新增 `/sim/ws/map-state` WebSocket 推送入口
- `workflow/state` 现在会合并 SQLite 结构化任务与 event bus 时间线：
  - 返回 `latest_task`
  - 返回 `recent_tasks`
  - 当前任务不足时会回退到可演示的 PX4 workflow fallback
- 前端统计卡片不再使用脱离实际的固定 mock 数字：
  - 作业面积改为优先读取 `spray_summary.spray_area_mu` 或地块 `area_mu`
  - 在线设备数当前按 `latest_task.drone.task_id` 推导单机在线状态
  - 千问建议直接读取结构化 `decision`
- `/sim/map-state` 与 `/sim/ws/map-state` 仍然保留并可供前端接入：
  - 但当前 React 大屏主地图的真实渲染来源仍是 `/workflow/state -> latest_task`
  - 也就是说，主地图已经跟随 PX4 实时位置，但并不是直接由 `sim/map-state` 驱动
- 当前运行环境的 WebSocket 依赖尚不完整，地图实时刷新会自动回退 HTTP polling：
  - 功能可正常演示
  - 但控制台存在 upgrade 失败日志噪声
- 2026-04-16 起，将“每次项目处理后必须同步更新 [`PROJECT_MEMORY.md`](/home/qingking/muye/PROJECT_MEMORY.md)，必要时同步 [`CHANGELOG.md`](/home/qingking/muye/CHANGELOG.md)”提升为项目最高规则。

- 当前仓库已正式接入 `PX4 + Gazebo SITL` 执行链路，不再只是接入方案记录：
  - 新增 [`modules/px4_simulator.py`](/home/qingking/muye/modules/px4_simulator.py)
  - [`modules/drone_controller.py`](/home/qingking/muye/modules/drone_controller.py) 已支持 `backend=px4`
  - [`main.py`](/home/qingking/muye/main.py) 已支持 `--drone-backend px4` 和 PX4 环境变量覆盖
  - [`.env.example`](/home/qingking/muye/.env.example) 与 [`config/drone_config.json`](/home/qingking/muye/config/drone_config.json) 已补齐 PX4 配置
- 新增完整 PX4 一键演示脚本链：
  - [`scripts/run_px4_demo.sh`](/home/qingking/muye/scripts/run_px4_demo.sh)
  - [`scripts/start_px4_visual_demo.sh`](/home/qingking/muye/scripts/start_px4_visual_demo.sh)
  - [`scripts/start_competition_mode.sh`](/home/qingking/muye/scripts/start_competition_mode.sh)
  - [`scripts/start_all_in_one.sh`](/home/qingking/muye/scripts/start_all_in_one.sh)
- 已在 [`config/drone_config.json`](/home/qingking/muye/config/drone_config.json) 中加入 PX4 SITL 演示地块、显式演示航线和展示参数。
- 已在 [`README.md`](/home/qingking/muye/README.md) 中补充 PX4 SITL、可视化演示、比赛模式和全量一键命令说明。
- 已补 PX4 相关测试：
  - [`tests/test_main.py`](/home/qingking/muye/tests/test_main.py)
  - [`tests/test_drone_controller.py`](/home/qingking/muye/tests/test_drone_controller.py)
  - [`tests/test_mission_planner.py`](/home/qingking/muye/tests/test_mission_planner.py)
  - [`tests/test_event_bus.py`](/home/qingking/muye/tests/test_event_bus.py)
- 新增 [`data/seeds/henan/soil_records.csv`](/home/qingking/muye/data/seeds/henan/soil_records.csv) 作为河南土壤检测示例 seed。
- 新增 [`scripts/generate_henan_soil_seed_csv.py`](/home/qingking/muye/scripts/generate_henan_soil_seed_csv.py) 和 [`scripts/import_henan_soil_records_csv.py`](/home/qingking/muye/scripts/import_henan_soil_records_csv.py)。
- 新增 `modules/sqlite_store.py` 的 `upsert_soil_record()`。
- 补充土壤 seed 生成、导入和 upsert 测试：
  - `tests/test_henan_field_crop_seed_generation.py`
  - `tests/test_sqlite_migration.py`
- `scripts/import_henan_reference_data.py` 现在会同步导入河南农药目录示例 seed 到 SQLite `pesticide_catalog`。
- 新增 [`data/seeds/henan/pesticide_catalog.json`](/home/qingking/muye/data/seeds/henan/pesticide_catalog.json)，用于本地联调和喷洒记录关联验证。
- 新增 `modules/sqlite_store.py` 的 `upsert_pesticide_catalog_record()`。
- 主处理链在 `pesticide_catalog` 存在同名产品时，会把 `spray_records.pesticide_id` 正式关联起来。
- 补充农药目录导入与主链关联测试：
  - `tests/test_sqlite_migration.py`
  - `tests/test_main.py`
- 主处理链执行成功后，新增把喷洒作业摘要同步写入 SQLite `spray_records`：
  - 关联 `request_id`
  - 关联 `field_id` / `crop_cycle_id`
  - 回填无人机任务 ID、喷洒速率、飞行高度、飞行速度、天气快照和结果状态
  - 从 AI 用药建议中提取总量 / 配比，并计算基础 `dosage_per_mu`
- 当系统退回 `config/drone_config.json` 地块上下文时，会自动把该地块 seed 到 SQLite `fields`，避免后续喷洒记录因缺少外键地块而落库失败。
- 新增喷洒记录写入回归测试：
  - `tests/test_main.py`
  - `tests/test_sqlite_migration.py`
- 修复 `weather_history_daily` 写入逻辑，允许同一气象站同一天的记录挂载到多个 `field_id`，避免多地块天气历史互相覆盖。
- 修复主流程运行时地块解析：存在多块地时必须显式指定，不再默认取数据库中的第一块地。
- 调整地块天气上下文解析优先级，改为优先使用经纬度匹配天气，再回退到市/县信息。
- 修复 `modules/mission_planner.py` 的航线生成逻辑，不再直接使用地块围栏顶点，改为基础覆盖式往返航线。
- 补充本轮修复对应回归测试：
  - `tests/test_main.py`
  - `tests/test_sqlite_migration.py`
  - `tests/test_mission_planner.py`
- 新增河南地块/作物核心模型：
  - `models/agri_models.py`
  - 包含 `CropCatalog`、`Field`、`FieldCropCycle`
- 新增河南地块/作物 CSV 种子生成脚本：
  - `scripts/generate_henan_field_crop_seed_csv.py`
  - 生成河南范围内的地块、作物和种植季记录
- 新增河南地块/作物 CSV 导入脚本：
  - `scripts/import_henan_field_crop_seed_csv.py`
  - 将 `crop_catalog.csv`、`fields.csv`、`field_crop_cycles.csv` 导入 SQLite
- 新增种子生成测试：
  - `tests/test_henan_field_crop_seed_generation.py`
- 新增导入与运行时地块解析测试：
  - `tests/test_sqlite_migration.py`
  - `tests/test_main.py`
- 主处理链开始同步写入 SQLite：
  - `tasks`
  - `detections`
  - `weather_snapshots`
  - `decisions`
- 主处理链现在会优先从 SQLite `fields` / `field_crop_cycles` 读取运行时地块，而不是依赖静态单地块配置。
- `tasks` 新增 `field_id` 关联；`fields` 新增 `owner_user_id`；`crop_catalog` 新增 `water_demand_coefficient`。
- 新增 `modules/mission_planner.py`：
  - 飞行路径、高度、喷洒速率和气象限制改由系统 planner 生成
  - LLM 决策层只保留用药建议和农事建议
- Streamlit 前端开始优先从 SQLite 读取任务摘要，并用 JSONL 事件流补实时阶段、无人机状态和日志。
- Streamlit 前端已能识别 PX4 状态时间线，并在任务历史中展示结构化无人机状态与作业结论。
- 前端决策卡片改为区分：
  - AI 用药建议
  - 系统规划参数
- 新增结构化任务历史检索：
  - 状态过滤
  - 关键字检索（`request_id` / 图片路径 / 害虫类型）
  - 最近任务数量控制
- 新增 SQLite 无人机状态流：
  - `drone_mission_updates`
  - 模拟执行与远端轮询都会写入
  - 前端任务历史可直接展示最新无人机结构化状态
- 新增农业数据层 schema 预留：
  - `fields`
  - `crop_catalog`
  - `field_crop_cycles`
  - `soil_records`
  - `weather_history_daily`
  - `pesticide_catalog`
  - `spray_records`
- 新增数据来源与统计指标表：
  - `data_sources`
  - `agri_statistical_indicators`
- 新增河南参考数据 seed 与导入脚本：
  - `data/seeds/henan/sources.json`
  - `data/seeds/henan/agri_statistical_indicators.json`
  - `scripts/import_henan_reference_data.py`
- 新增河南历史天气导入能力：
  - `weather_stations`
  - `scripts/import_henan_weather_history_csv.py`
  - 支持 CMA 日值 CSV 常见中文列名导入
  - 导入时会优先按站点经纬度和区县自动匹配最近地块
- 新增农业数据模型参考文档：
  - `docs/05-reference/data-model.md`
- 保留现有 JSONL 事件流作为前端展示与调试来源，不替换 `FileEventBus`。
- 新增 `MUYE_SQLITE_PATH` 环境变量，默认指向 `data/muye.db`。
- 新增 `MUYE_ACTIVE_FIELD_ID` 环境变量，用于指定当前运行时优先使用的数据库地块。
- 补充 SQLite 读写回归测试：
  - `tests/test_main.py`
  - `tests/test_drone_controller.py`
  - `tests/test_sqlite_migration.py`
- 2026-04-16 已重新核对仓库状态并同步更新工程记忆文件，修正此前“PX4 尚未落代码”的过时描述：
  - [`PROJECT_MEMORY.md`](/home/qingking/muye/PROJECT_MEMORY.md)
  - [`docs/WORKLOG.md`](/home/qingking/muye/docs/WORKLOG.md)

## v1.1.1

- 在 `v1.1` 持久化优化基础上新增旧库迁移支持发布线。
- PR #1 已合并：
  - `tasks.status` CHECK 约束
  - `request_id` 索引
  - WAL / NORMAL
- PR #2 已合并：
  - `_migrate_v1_1()` 自动迁移旧库
  - `scripts/migrate_to_v1_1.py`
- PR #3 已合并：
  - `tests/test_sqlite_migration.py`
  - `docs/06-operations/runbooks/sqlite-migration-v1_1.md`
  - `docs/08-testing/sqlite-migration-regression.md`
  - 修复 `_migrate_v1_1()` 在旧库路径上的事务处理问题
- 已创建 Release：
  - `v1.1.1 - SQLite migration support`

## v1.1.1 后续开发记录（已归档）

- 修复 PX4 演示任务“前端不动 / 3 分钟后超时”的根因：
  - [`modules/px4_simulator.py`](/home/qingking/muye/modules/px4_simulator.py) 不再把高频遥测抖动直接等价为 `spraying`
  - 改为基于真实经纬度投影回预设航线，计算当前航点索引和进度百分比
  - `current_waypoint_index` 现在回到前端 22 点喷洒航线的索引语义，不再泄露 PX4 内部插入的 pivot mission item 索引
  - PX4 位置事件已加节流，避免单次任务向 event bus 写入数千条无效位置抖动
  - PX4 mission timeout 改为按航线长度、速度和转向停留时长动态估算后取更大值，避免大地块演示在任务中途被错误判定为超时
- `config/drone_config.json` 已将 PX4 冬小麦演示航线速度提升到 `4.5m/s`，默认 mission timeout 提升到 `300s`，让大地块演示既能看见实时移动，也不至于过早失败。
- [`frontend/src/components/map/FieldMap.tsx`](/home/qingking/muye/frontend/src/components/map/FieldMap.tsx) 已从 `React Leaflet` 运行态渲染切到纯 `SVG` 作业地图：
  - 不再依赖地图容器初始化、`fitBounds` 或 `invalidateSize`
  - 地块、覆盖区、预设航线、起点航点和无人机位置均由 React 直接绘制
  - 目的就是解决“文本数据在更新，但地图层不动或不可见”的现场问题
- 前端地图 `frontend/src/components/map/FieldMap.tsx` 改为只展示当前任务驱动的 PX4 / 作业无人机，不再回退到静态演示无人机。
- 修复前端地图坐标归一化逻辑，统一地块 geofence、覆盖区域和飞行路径的投影，避免无人机与地块错位。
- 前端任务面板继续显示地块名、作物名，但数据优先来自当前运行时任务。
- `frontend/src/pages/Dashboard.tsx` 去掉旧 `sim/map-state` 对地图无人机展示的主导作用，在线设备统计改为基于当前任务无人机。
- `main.py` 新增运行时地块字段覆盖逻辑：
  - 当 `drone.instruction` 提供 `field_id` / `field_name` / `crop_name` / `覆盖区域` 时，优先覆盖旧 SQLite 任务视图中的地块信息
  - 数据库仍保留为补充来源，满足后续导入真实农业数据后参与决策的要求
- 修复 PX4 前端无人机“看起来不动”的问题：
  - 真实 PX4 任务会返回超出前端喷洒航线长度的 `current_waypoint_index`
  - 旧实现会把该索引直接夹到最后一个航点，导致无人机长期停在终点
  - 新实现在线路索引越界时改为基于 `drone.progress` 沿当前航线插值，保持可见移动
- 已验证当前 `workflow state` 可返回：
  - `field.field_name = PX4 SITL 冬小麦演示田`
  - `field.crop_cycle.crop_name = 冬小麦`
  - `drone.task_id = px4-*`

## v0.3-initial

- 新增 `scripts/start_demo.sh`，支持一键启动后端 demo 栈和 Streamlit 前端。
- README 更新为和真实运行方式一致，补充了一键启动、样例图触发和实际可用测试命令。
- 已验证前后端可以同时启动。
- 已验证样例图 `IP000000042.jpg` 可走通：
  - YOLO 识别
  - 天气获取
  - 千问决策
  - PX4 状态推进
  - pipeline completed

## v0.2-initial

- 支持真实 YOLO、真实和风天气、真实千问增强链路、PX4 SITL 和可视化指挥中心前端。

## v0.1-initial

- 初始稳定版本，包含基础 YOLO、天气、千问、无人机控制和测试结构。
