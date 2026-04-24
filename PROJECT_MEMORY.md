# Project Memory

## Highest Will

1. 对项目做出任何实际处理后，必须立即同步更新 `PROJECT_MEMORY.md`。
2. 如果本次处理已经改变版本行为、对外接口、运行方式或演示口径，必须同时同步更新 `CHANGELOG.md`。
3. 项目记忆必须以当前仓库真实代码、脚本、配置、测试和文档为准，不能沿用过期印象。
4. 如发现“代码已变但记忆未变”，应优先修正记忆，再继续后续工作。

## Current Priority

1. 维护并稳定当前已经接入的 `PX4 + Gazebo SITL + Muye` 演示链路，而不是回退到只靠虚拟无人机 API。
2. 以 `frontend/` 下的 `Vite + React + TypeScript` 指挥大屏为当前前端主线，继续补齐工作流闭环、态势图和演示体验。
3. 继续扩展 SQLite 结构化存储和读取侧能力，保持 `JSONL + SQLite` 混合存储策略。
4. 继续完善河南农业数据 seed / import / 查询链路，服务于演示与后续报表能力。
5. 保留 `simulated` / `remote_api` / `px4` 三种无人机 backend 并存，方便本地联调、稳定演示和真实 SITL 切换。

## Confirmed Decisions

- 当前仓库已经不是“准备接 PX4”，而是“PX4 backend 已落地”：
  - `modules/px4_simulator.py` 已存在。
  - `modules/drone_controller.py` 已支持 `backend=px4`。
  - `app/main.py` 已支持 `--drone-backend px4` 与 PX4 环境变量覆盖。
  - `config/drone_config.json` 与 `.env.example` 已包含 PX4 配置。
- 当前仓库已经提供完整的 PX4 一键演示脚本族：
  - `scripts/run_px4_demo.sh`
  - `scripts/start_px4_visual_demo.sh`
  - `scripts/start_competition_mode.sh`
  - `scripts/start_all_in_one.sh`
  - `scripts/start_showtime.sh`
  - 其中 `start_demo.sh` / `start_px4_visual_demo.sh` 已明确改为同时启动：
    - `app/main.py` 主流程
    - `uvicorn app.main:api_app`（脚本当前固定使用 `127.0.0.1:18000`）
    - `frontend/` 下的 Vite React 前端
  - 当前脚本已继续优化为支持 `--api-port`，方便现场环境避让端口冲突
- 当前仓库已经结束“双前端并存”阶段：
  - `frontend/` 下的 `Vite + React + TypeScript` 是唯一前端主线
  - 旧 `app.py` Streamlit 前端已删除
  - 旧前端中的上传、图片对照、天气/决策卡片、事件日志、历史检索能力已迁入 React 大屏
- 非 PX4 的原始 demo 入口仍保留：
  - `scripts/start_demo.sh`
  - 适合继续走 `with-demo-stack + virtual drone` 的稳定演示路径
- PX4 演示默认采用仓库内置 Zurich SITL 演示地块，而不是直接飞业务配置里的河南地块：
  - `config/drone_config.json -> px4.demo_field`
  - `app/main.py -> _build_px4_demo_field_context()`
  - `PX4_USE_SITL_DEMO_FIELD=true` 时会自动启用
  - 当前 demo field 已调整为更大的 `冬小麦` 演示田，名称为 `PX4 SITL 冬小麦演示田`
  - 当前配置中的演示田面积约为 `5.6 亩`，围栏约 `72m x 52m`，显式演示航线约 `61.9m x 40m`
- PX4 演示链路默认策略已经明确：
  - 后端切到 `DRONE_BACKEND=px4`
  - 使用本地 YOLO API
  - 天气与千问在演示脚本中默认走 mock，保证稳定性
  - MAVSDK 连接地址默认 `udpin://0.0.0.0:14540`
- 当前无人机 backend 是三路并存：
  - `simulated`
  - `remote_api`
  - `px4`
- SQLite 路线已经从“草案”进入“主链路落地”：
  - `tasks`
  - `detections`
  - `weather_snapshots`
  - `decisions`
  - `drone_mission_updates`
  - `fields`
  - `crop_catalog`
  - `field_crop_cycles`
  - `soil_records`
  - `weather_stations`
  - `weather_history_daily`
  - `pesticide_catalog`
  - `spray_records`
  - `data_sources`
  - `agri_statistical_indicators`
- 主处理链和前端的存储边界已经稳定：
  - `modules/event_bus.py` 继续保留，负责实时事件流和日志
  - `modules/sqlite_store.py` 负责结构化任务摘要、历史记录和农业数据
  - `app/main.py -> api_app` 负责把 SQLite、JSONL 事件流和图片/上传操作统一暴露给 React 前端
- 当前 FastAPI 入口已经开始做模块化拆分，而不是继续把所有 API 与辅助逻辑堆在 `app/main.py`：
  - `routes/` 负责按领域注册接口
  - `services/` 负责工作流聚合与地图状态服务
  - `core/` 负责配置与依赖访问
  - `models/schemas.py` 负责 API 的 Pydantic schema
- 新前端面向大屏的后端接口已进入 `app/main.py -> api_app`：
  - `GET /health` 与 `GET /api/health`
  - `GET /sim/map-state` 与 `GET /api/sim/map-state`
  - `GET /workflow/state` 与 `GET /api/workflow/state`
  - `GET /workflow/history` 与 `GET /api/workflow/history`
  - `GET /dashboard/context` 与 `GET /api/dashboard/context`
  - `POST /demo/upload-image` 与 `POST /api/demo/upload-image`
  - `POST /demo/reset-events` 与 `POST /api/demo/reset-events`
  - `GET /tasks/{request_id}/original-image`
  - `GET /tasks/{request_id}/annotated-image`
  - `WS /sim/ws/map-state` 与 `WS /api/sim/ws/map-state`
- `workflow/state` 的数据来源策略已经确定：
  - 优先把 SQLite 结构化任务视图与 JSONL / event bus 时间线合并
  - 同时向前端提供 `latest_task` 与 `recent_tasks`
  - 当真实时间线不足时，回退到可演示的 PX4 workflow fallback，保证大屏不断档
- PX4 仿真地图展示策略已经调整为“虚拟农田”而非真实地理底图：
  - 前端 `FieldMap.tsx` 当前已改为纯 `SVG` 作业地图渲染，不再依赖 React Leaflet 运行态
  - 中心区域优先展示当前真实任务地块、多架无人机、作业航线和指挥中心
  - 旧版 3 个静态演示地块已经从前端源码删除，不再作为 fallback 展示
  - 当前地图会展示当前任务的执行航线、地块面、覆盖区域和无人机点位
  - 航线来源当前优先使用 `latest_task.drone.instruction.飞行路径`，以匹配 PX4 实际执行航线；只有任务指令缺失时才回退 `field.explicit_route`
  - `app/main.py -> Px4MapStateSimulator` 当前也已改为静态快照，不再让无人机点位和电量随时间自行变化
  - 这是为了匹配 PX4 SITL / 虚拟农田演示场景，而不是现实经纬度地图
- 新前端的仿真态势刷新策略已完成重构（2026-04-24）：
  - 后端 WebSocket `/sim/ws/map-state` 现在推送合并状态 `WsCombinedState`（sim_map + workflow_state）
  - 前端 `useWebSocket` hook 已重写，支持：
    - 指数退避自动重连（1s → 2s → 4s → ... → 30s 上限）
    - 连接断开时自动降级到 HTTP polling
    - 重连成功时显示 toast 提示
  - `Dashboard.tsx` 现在通过 WebSocket 统一接收 `sim_map` 与 `workflow_state`
  - 断连时降级为并行调用 `/sim/map-state` + `/workflow/state` 轮询
  - `FieldMap.tsx` 无人机位置数据源优先级调整为：
    - 优先使用 `simMapState.drones`（仿真推送）
    - 回退到 `latest_task.drone.position`（任务驱动）
  - 前端顶部增加连接状态指示器（"实时" 绿色 / "轮询" 橙色）
- LLM 与 planner 的职责边界已经收敛：
  - `ai_decision.py` 只输出用药建议与农事建议
  - `mission_planner.py` 负责飞行路径、高度、速度、喷洒速率与气象限制
- 决策输入与数据库的关系已经调整为“可插拔增强”，而不是“默认硬依赖数据库参与决策”：
  - `modules/ai_decision.py` 当前支持注入 `decision_context_provider`
  - 默认情况下，决策层只使用害虫检测、实时天气和基础地块上下文
  - 只有显式开启 `MUYE_ENABLE_SQLITE_DECISION_CONTEXT=true` 时，才会把 SQLite 中的土壤、历史天气、候选农药等结构化数据拼入决策输入
  - 这条策略是为了先稳定主链路，再为后续 CSV / seed / 正式数据导入后的数据库参与决策预留接入点
- 运行时地块上下文策略已经确定：
  - 优先使用 `PX4 SITL demo field`
  - 其次使用 `MUYE_ACTIVE_FIELD_ID`
  - 再从 SQLite `fields / field_crop_cycles` 解析
  - 最后才回退到 `config/drone_config.json`
  - 当回退配置被使用时，会自动 seed 到 SQLite，避免外键缺失
- RAG 决策增强链路已落地：
  - `modules/rag/` 已实现完整的 LangChain RAG 框架
  - `QwenEmbeddings` 封装阿里云 DashScope text-embedding-v3 API
  - `VectorStoreManager` 管理 ChromaDB 向量库，支持 `pesticides` 与 `decisions` 两个 collection
  - `DecisionRAGRetriever` 根据害虫类型 + 作物名称检索相关农药推荐和历史案例
  - `DecisionEngine` 已集成 `rag_retriever` 注入，RAG 检索文本拼入决策 prompt
  - RAG 失败时只记录 warning 和 `rag:error` 事件，不中断原决策流程
  - 通过 `event_bus` 发布 `rag:running/completed/error` 事件供前端展示
  - `scripts/build_rag_knowledge.py` 用于构建向量知识库，首启时自动灌入农药目录

## Current Code Status

### Main Flow

- `app/main.py`
  - 当前主要负责系统装配、worker 队列、embedded YOLO / virtual drone 服务启动，以及 FastAPI app 组装
  - 支持 `--with-yolo-api`、`--with-virtual-drone-api`、`--with-demo-stack`
  - 支持 `--drone-backend simulated|remote_api|px4`
  - 支持 `--no-capture-on-startup`
  - 已内建 PX4 环境变量覆盖和 demo field 切换逻辑
  - 当前已把 health / workflow / dashboard / demo / tasks / sim 路由注册下放到 `routes/*.py`
- `core/config.py`
  - 当前承接 loopback host、YOLO URL 与环境布尔值解析等配置工具
- `core/deps.py`
  - 当前承接 runtime dependency 访问，如 embedded YOLO runner 和时间格式化辅助
- `models/schemas.py`
  - 当前承接前端 API 的主要 Pydantic schema：
    - `WorkflowStateResponse`
    - `WorkflowHistoryResponse`
    - `DashboardContextResponse`
    - `SimMapStateResponse`
    - `WsCombinedState`（合并 WebSocket 推送 schema）
- `services/workflow_service.py`
  - 当前承接工作流状态、历史记录、SQLite/event bus 聚合、上传文件名清洗等服务层逻辑
- `services/map_simulator.py`
  - 当前承接 `Px4MapStateSimulator`
- `routes/health.py`
  - 当前承接 `/health` 与 `/api/health`
- `routes/workflow.py`
  - 当前承接 `/workflow/state` 与 `/workflow/history`
- `routes/dashboard.py`
  - 当前承接 `/dashboard/context`
- `routes/demo.py`
  - 当前承接 `/demo/upload-image` 与 `/demo/reset-events`
- `routes/tasks.py`
  - 当前承接任务原图 / 标注图读取接口
- `routes/sim.py`
  - 当前承接 `/sim/map-state` 与 `/sim/ws/map-state`
  - WebSocket 推送已改为合并 `WsCombinedState`（sim_map + workflow_state），workflow 构建失败时降级为 null
- `modules/drone_controller.py`
  - 已支持 simulated、remote API、PX4 三种执行路径
  - 无人机状态流会写入 SQLite `drone_mission_updates`
  - 最终状态会映射回 `spray_records.result_status`
- `modules/px4_simulator.py`
  - 已通过 `mavsdk` 接 PX4 SITL
  - 已支持连接、等待定位、上传任务、自动解锁、自动起飞、任务完成监听
  - 已支持航点接受半径、停留时间、飞越航点、原地转弯等演示控制参数
- `modules/rag/__init__.py`
  - RAG 模块统一导出入口
- `modules/rag/embeddings.py`
  - `QwenEmbeddings` 类封装阿里云 DashScope text-embedding-v3 API
  - 支持 API key、dimensions、timeout 配置
- `modules/rag/vectorstore.py`
  - `VectorStoreManager` 管理 ChromaDB 持久化向量库
  - 支持 `COLLECTION_PESTICIDES` 和 `COLLECTION_DECISIONS` 两个 collection
  - 提供文档添加、相似度检索、批量导入等能力
- `modules/rag/retriever.py`
  - `DecisionRAGRetriever` 根据害虫类型 + 作物名称检索相关农药和历史案例
  - `RetrievedContext` 格式化检索结果为 prompt 文本
  - 支持按害虫类型过滤农药推荐结果
- `modules/rag/knowledge_loader.py`
  - 从 SQLite `pesticide_catalog` 或 JSON 文件加载农药知识
  - 支持从 `docs/` 目录加载 markdown 文档
- `modules/ai_decision.py`
  - 已集成 `rag_retriever` 注入
  - 新增 `_build_rag_context_text()` 方法，在决策前检索相关知识
  - RAG 检索文本拼入 `build_structured_input_text()` 的 prompt
  - 失败降级：只记录 warning 和 `rag:error` 事件，不中断原流程

### PX4 Scripts

- `scripts/run_px4_demo.sh`
  - 一键跑通 `PX4 SITL -> Muye backend -> 示例图注入 -> 等待任务完成`
  - 会清理代理环境变量，避免 PX4 本地构建/运行受代理干扰
  - 支持 `--skip-px4`、`--keep-px4`、`--system-address`、`--world`
  - 已增加 PX4 日志大小守卫，默认将单个 PX4 日志限制在 `100MB` 内，超限时仅保留最近 `50MB`
- `scripts/start_px4_visual_demo.sh`
  - 一键拉起 `PX4 SITL + Gazebo + Muye backend + frontend API + React frontend`
  - 可选自动拉起 `QGroundControl`
  - 已增加 PX4 日志大小守卫，默认将单个 PX4 日志限制在 `100MB` 内，超限时仅保留最近 `50MB`
- `scripts/start_competition_mode.sh`
  - 包装 visual demo，并尝试自动打开浏览器，面向比赛现场展示
- `scripts/start_all_in_one.sh`
  - 面向最直接的一键入口，透传 QGC / browser / PX4 参数
- `scripts/start_showtime.sh`
  - 当前作为更高层的一键展示入口
  - 默认启动稳定的 React + backend demo stack
  - 通过 `--with-px4` 可切到 PX4/Gazebo 比赛演示链
  - 默认优先自动注入仓库内置样例图，减少现场手工操作

### Non-PX4 Demo Script

- `scripts/start_demo.sh`
  - 继续保留为本地 YOLO + 虚拟无人机 + frontend API + React frontend 的基础演示入口
  - 适合作为 PX4 环境不可用时的稳定回退路径
- `scripts/test_api.py`
  - 当前作为最小化后端 API 探测脚本
  - 可快速检查运行中的 `/api/health`、`/api/dashboard/context`、`/api/workflow/state` 与 `/api/workflow/history`

### Database / Data Model

- `modules/sqlite_store.py`
  - 已完成旧库迁移、主 schema 初始化、索引、WAL / NORMAL
  - 已支持 `fetch_field_context()`、`fetch_task_views()`、`fetch_decision_support_context()` 等读取侧能力
  - 已支持 `upsert_*` 写入：
    - `upsert_field()`
    - `upsert_crop_catalog_record()`
    - `upsert_field_crop_cycle()`
    - `upsert_soil_record()`
    - `upsert_weather_station()`
    - `upsert_weather_history_daily()`
    - `upsert_pesticide_catalog_record()`
    - `upsert_data_source()`
    - `upsert_agri_statistical_indicator()`
    - `upsert_spray_record()`
- `modules/decision_context.py`
  - 已新增决策增强上下文抽象
  - 当前落地 `SqliteDecisionContextProvider`
  - 负责把 SQLite 中的地块画像、最新土壤记录、近期历史天气和候选农药整理成可选决策输入
- `scripts/migrate_to_v1_1.py`
  - 继续保留为 SQLite 旧库迁移工具
- `v1.1.1`
  - 代表 SQLite migration support 发布线，相关说明已进入 `CHANGELOG.md`
- `models/agri_models.py`
  - 已定义 `CropCatalog`、`Field`、`FieldCropCycle` SQLAlchemy 模型，作为农业数据层参考模型

### RAG Knowledge Build

- `scripts/build_rag_knowledge.py`
  - 独立脚本用于构建 RAG 向量知识库
  - 支持 `--rebuild` 清空后重建
  - 默认加载农药目录和 docs 知识文档

### Seed / Import Scripts

- 已落地河南数据脚本：
  - `scripts/generate_henan_field_crop_seed_csv.py`
  - `scripts/import_henan_field_crop_seed_csv.py`
  - `scripts/generate_henan_soil_seed_csv.py`
  - `scripts/import_henan_soil_records_csv.py`
  - `scripts/import_henan_reference_data.py`
  - `scripts/import_henan_weather_history_csv.py`
- 已存在的示例 seed：
  - `data/seeds/henan/field_crop_seed/*.csv`
  - `data/seeds/henan/soil_records.csv`
  - `data/seeds/henan/pesticide_catalog.json`
  - `data/seeds/henan/sources.json`
  - `data/seeds/henan/agri_statistical_indicators.json`

### Frontend

- `frontend/`
  - 当前采用 `Vite + React + TypeScript`
  - 已接入 `Ant Design` 深色指挥大屏样式
  - 已落地 `Dashboard.tsx` 作为首页
  - 已清理未使用的 Vite 初始化模板残留文件（`App.css`、`src/assets/*`、`public/icons.svg`），当前前端静态资源以实际页面所需文件为准
  - 仓库级运行缓存与构建产物（如根目录/模块 `__pycache__`、`.pytest_cache`、`frontend/dist`）不属于源码结构，可按需清理
  - 左栏已改为真实结构化数据驱动，而不是伪造的“18 台设备 / 固定喷洒面积”
  - 中间已接入 PX4 虚拟农田态势图 `FieldMap.tsx`
  - 地图当前只展示真实当前任务地块；静态 3 地块演示数据已删除
  - 地图当前不再绘制无人机路线线条和系统规划航线线条
  - 下方已补 `WorkflowPanel.tsx`，承接旧前端的任务阶段、日志感与闭环流程体验
  - 右栏已改为“当前任务 / 最近任务”，数据来自 `workflow/state.recent_tasks`
  - 已承接旧前端功能：
    - 图片上传
    - 原图 / 识别图对照
    - 害虫识别摘要
    - 天气信息
    - 千问建议与安全提示
    - 任务历史检索
    - 运行模式展示
  - `useWebSocket` hook 已重写，支持指数退避自动重连、轮询降级、重连 toast
  - Dashboard 通过 WebSocket 统一接收合并状态，断连降级轮询
  - FieldMap 优先使用 simMapState 无人机数据，回退任务驱动
  - 连接状态指示器：实时（绿）/ 轮询（橙）
- `tests/test_main.py`
  - 已补 React 前端 API 契约测试
  - 当前策略是不依赖 `TestClient`，而是直接调用 endpoint 函数，降低 pytest 在当前环境中的阻塞概率
  - 当前 monkeypatch 仍主要通过 `main.*` 注入，因此拆分后的路由 / 服务层需要显式桥接这些测试替换点
  - 已新增 WebSocket 合并推送韧性测试：workflow 构建失败时 sim_map 仍正常推送、workflow_state 降级为 null
- `frontend/PROJECT_STRUCTURE.md`
  - 已随当前 Vite 前端真实目录同步
  - 各目录均带中文注释，供后续继续扩展
  - 已补 `useSimMapState.ts`、图片上传/历史/API 封装等当前真实结构

## Key Differences From Older Memory

- 旧记忆里“PX4 尚未落代码、还在等待后续接入”的表述已经过时。
- 当前真实状态是：
  - PX4 backend 已接入
  - PX4 demo field 已配置
  - PX4 CLI / env / backend route 已接入
  - PX4 一键演示脚本已完整存在
  - PX4 相关测试已补齐
- 旧记忆里“SQLite 还是起步草案”的表述也不准确。
- 当前真实状态是：
  - SQLite 已写入主 pipeline
  - SQLite 已接前端历史读取
  - 农业数据 schema、seed、import、query 已落一整层
- 旧记忆里“前端仍主要依赖 Streamlit 展示”的表述已经失效。
- 当前真实状态是：
  - 旧 `app.py` 已删除
  - `frontend/` 是唯一前端主线
  - React 前端已具备 PX4 虚拟农田态势图、工作流闭环面板、千问建议卡片、图片对照、任务历史与上传操作
- 旧记忆里“统计卡片使用固定 mock 数值”的理解已经失效。
- 当前真实状态是：
  - 作业面积优先取 `spray_summary.spray_area_mu` 或地块 `area_mu`
  - 在线设备数当前按 `latest_task.drone.task_id` 推导单机在线状态，并非直接读取 `sim/map-state`
  - 千问建议卡片直接读取结构化 `decision`

## Last Verified State

- 2026-04-17 已重新逐项核对当前仓库中的源码、配置、脚本、测试与文档：
  - `app/main.py`
  - `modules/*.py`
  - `scripts/*.sh`
  - `scripts/*.py`
  - `tests/*.py`
  - `README.md`
  - `config/drone_config.json`
  - `.env.example`
  - `frontend/src/**/*.tsx`
  - `frontend/src/**/*.ts`
  - `frontend/src/styles/*.css`
  - `frontend/PROJECT_STRUCTURE.md`
- 本次核对确认：
  - 记忆文件此前落后于代码状态
  - 当前仓库已经包含 PX4 接入和完整一键演示脚本
  - 当前仓库已经包含 SQLite 深化接入和农业数据扩展
- 当前仓库新增确认的前端 / API 状态：
  - `frontend` 构建已通过 `npm run build`
  - `GET /health` 已不再只返回固定 `{"status":"ok"}`，而是返回结构化检查结果：
    - SQLite 连通性
    - `data/` 目录写权限
    - 内嵌 YOLO runner 存活状态（如有）
    - 任一失败时返回 `503`
  - `GET /workflow/state` 可返回包含 `latest_task` 与 `recent_tasks` 的结构化 JSON
  - Vite 默认代理目标已统一到 `127.0.0.1:18000`，与当前演示脚本保持一致
  - Vite 已显式配置 `manualChunks`，当前拆包策略是：
    - `vendor-react`
    - `vendor-ui`
    - `vendor-map`
    - `vendor-misc`
  - 当前 `dist/assets/*` 产物名已带内容 hash，可为浏览器复用未变更的 vendor chunk 提供前提
  - 但 `vendor-map` / `vendor-ui` / `vendor-misc` 是否真正实现长效缓存，仍取决于部署层是否给 `dist/assets/*` 返回长期缓存头；`index.html` 应保持短缓存或 `no-cache`
  - 仓库已新增 `deploy/nginx.conf` 示例，当前推荐的部署层缓存口径是：
    - `dist/assets/*` -> `Cache-Control: public, max-age=31536000, immutable`
    - `index.html` -> `no-cache`
    - `/api/` -> 反向代理到后端，并保留 SPA history fallback
    - 默认采用比赛现场优先的 HTTP 配置，而不是强依赖 HTTPS
  - 仓库已新增 `deploy/muye_backend.service` 示例，当前推荐的后端生产托管口径是：
    - 通过 `systemd` 运行 `uvicorn app.main:api_app`
    - 监听 `127.0.0.1:8000`
    - 由 Nginx 统一反代 `/api/`
    - 保持单进程 Uvicorn，避免当前内存态 map/workflow 数据在多 worker 下分裂
    - 通过 `EnvironmentFile=/var/www/muye/backend/.env` 读取环境变量
    - 显式使用 `/var/www/muye/backend/.venv/bin/uvicorn`
  - 当前后端没有额外挂载独立静态目录；任务图片仍经由 API 动态返回
  - 后端已提供 `/api/sim/ws/map-state`，因此 Nginx `/api/` 代理仍需要支持 WebSocket upgrade
  - 但当前前端主地图真实渲染来源已改为 WebSocket 合并推送 `WsCombinedState`，不再是单独轮询 `/workflow/state`
  - 上传安全校验已补齐：
    - `/demo/upload-image` 现在要求真实可解码图片内容
    - 单文件默认上限 `10MB`
  - reset 语义已收敛：
    - `/demo/reset-events` 必须显式带 `confirm=true`
    - 会同时清空 SQLite 任务运行态数据和 JSONL event bus
  - 历史接口 `workflow/history.total` 已改为“SQLite + event bus 合并后”的真实总数，不再等于当前页条数
  - 历史接口 `workflow/history` 已改为合并后再做 `limit` 截断，避免 event-only 任务突破分页
  - 决策增强上下文开关已新增：
    - `MUYE_ENABLE_SQLITE_DECISION_CONTEXT=false` 时，数据库默认不参与决策 prompt
    - `MUYE_ENABLE_SQLITE_DECISION_CONTEXT=true` 时，才会启用 `SqliteDecisionContextProvider`
- 历史已验证的本地测试记录：
  - `PYTHONPATH=/home/qingking/muye /home/qingking/muye/.venv/bin/pytest -q`
  - 当前最近结果：`77 passed in 9.13s`（含 RAG 测试）
  - `PYTHONPATH=. .venv/bin/pytest tests/test_ai_decision.py tests/test_decision_context.py`
  - 当前最近结果：`7 passed in 0.11s`
- 2026-04-17 已追加完成一次真实运行态核对：
  - 通过 `scripts/start_px4_visual_demo.sh --api-port 18001 --frontend-port 8503 --skip-qgc` 拉起 PX4/Gazebo/后端/前端演示栈
  - `http://127.0.0.1:18001/api/workflow/state` 已确认返回 `PX4 SITL 冬小麦演示田` 与 `冬小麦`
  - 通过向 `data/images/` 注入样例图触发了新的 PX4 任务：`request_id=d0ea63f05c1443f6be9c8666760e7bc6`
  - API 中 `latest_task.drone.position` 已出现真实经纬度和高度
  - 连续 5 个样本里经度从 `8.5454265` 变化到 `8.5455685`，已确认前端可跟随 PX4 实时移动，而不是假动画
- 关键测试覆盖已确认存在：
  - `tests/test_main.py`
    - PX4 backend override
    - PX4 demo field override
    - 主流程 SQLite 写入
    - `spray_records` 状态回填
    - `pesticide_catalog` 关联
    - SQLite 地块上下文选择
  - `tests/test_drone_controller.py`
    - simulated 状态写库
    - PX4 状态写库
    - PX4 mission completion / address normalize / waypoint timing / pivot turn
  - `tests/test_mission_planner.py`
    - 覆盖式航线
    - presentation profile
    - explicit demo route
  - `tests/test_event_bus.py`
    - PX4 时间线压缩
  - `tests/test_sqlite_migration.py`
    - 旧库迁移
    - 结构化历史读取
    - 农业 schema
    - spray / pesticide / soil / weather history / field context
  - `tests/test_ai_decision.py`
    - decision context provider 注入
    - 决策 prompt 可选增强上下文拼接
  - `tests/test_decision_context.py`
    - SQLite 决策增强上下文聚合
    - 土壤 / 历史天气 / 候选农药读取
  - `tests/test_rag_embeddings.py`
    - QwenEmbeddings API 请求/响应契约测试
    - API key 校验、空输入处理、请求体格式验证
  - `tests/test_rag_retriever.py`
    - DecisionRAGRetriever 查询参数测试
    - 害虫类型过滤测试
    - crop_name 从 field_context 提取测试
    - RetrievedContext 格式化测试

## Known Gaps / Risks

- PX4 代码虽然已接入，但真实运行仍依赖外部环境：
  - `PX4-Autopilot`
  - Gazebo Sim
  - `mavsdk`
  - 可选 `QGroundControl`
- `app/main.py` 中虽然已提供 WebSocket 地图推送接口，但当前运行环境缺少 `websockets` / `wsproto` 时会出现 upgrade 失败：
  - 前端已内建指数退避重连 + polling fallback，因此功能可用
  - 但控制台和代理日志会有噪声，后续可通过补依赖或关闭 WS 尝试来收敛
- 新前端当前仍存在少量 Ant Design v6 deprecation warning：
  - 不影响构建和演示
  - 但后续可以顺手清理 `Card/List/Space` 的旧属性用法
- 本次会话没有重新实际启动 `make px4_sitl gz_x500` 做端到端现场验证；本次验证重点是“仓库代码状态”和“记忆同步”。
- `pesticide_catalog` 当前仍是示例 seed，用于联调和字段关联，不是正式官方登记全量库。
- 河南历史天气导入能力已具备，但真实 CSV 仍需用户后续提供再做真实入库验证。
- `SqliteDecisionContextProvider` 当前只是"预留并可启用"的增强层，不应被误解为正式农业知识决策引擎：
  - 当前更多是把导入后的结构化数据喂给 LLM
  - 真正的规则引擎、权重体系和可解释决策仍需后续继续收敛
- RAG 链路虽然已落地，但当前仍有几个待收敛点：
  - 向量库默认只灌入农药目录，历史决策案例需要真实任务积累后才能有效检索
  - `QwenEmbeddings` 依赖阿里云 DashScope API，需要 `QWEN_API_KEY` 环境变量
  - ChromaDB 数据存储在 `data/chroma_db/`，当前未加入 `.gitignore`，大库场景需注意
  - embedding 维度默认 1024，与 Qwen text-embedding-v3 的推荐配置一致，但可根据需求调整
- 2026-04-17 已再次核对前端重写后的地图链路，确认当前展示原则更新为：
  - 地图不再展示静态三地块
  - 地图不再展示独立仿真移动无人机或旧航线回放
  - 地图无人机位置优先取 `workflow/state.latest_task.drone`
  - 地块名称 / 作物 / geofence 允许由当前 PX4 任务指令覆盖旧 SQLite 字段，数据库保留为补充数据源
- 2026-04-17 前端作业地图渲染方式已再次调整：
  - 原先 `FieldMap.tsx` 使用 `React Leaflet + CRS.Simple`
  - 现场出现“文本数据会更新，但地图层不动/不可见”后，已切换为纯 `SVG` 渲染
  - 当前地块面、覆盖区、预设航线、起点航点和无人机位置都由 React 直接输出到 SVG
  - 因此后续若再出现“地图不动”，应优先排查数据投影和组件状态，而不是 Leaflet 容器初始化
- 2026-04-17 已进一步定位 PX4 演示链真实故障根因并修复代码：
  - 旧 PX4 演示航线总长约 `719m`，而 `target_speed_mps=1.0`、`mission_timeout_seconds=180`
  - 这会导致大地块演示必然在中途超时，不是“前端单独不动”
  - `modules/px4_simulator.py` 现已改为：
    - 依据真实遥测位置反算其在预设航线上的投影进度
    - 输出与前端 22 点航线一致的 `current_waypoint_index`
    - 对位置事件做距离 / 时间节流，避免 event bus 被高频抖动刷爆
    - 按航线长度、速度和 pivot 转向停留动态估算实际 mission timeout
  - `config/drone_config.json` 现已把 PX4 冬小麦演示速度提升到 `4.5m/s`，默认 timeout 提升到 `300s`
  - 因此后续前端应跟随 PX4 真正位置变化，而不是再依赖 mission item 索引越界后的假插值
- 2026-04-17 已确认最新运行时任务数据应表现为：
  - `field.field_name = PX4 SITL 冬小麦演示田`
  - `field.crop_cycle.crop_name = 冬小麦`
  - `drone.task_id` 为 `px4-*`
  - 前端地图通过统一坐标投影让地块边界、覆盖区和无人机航点对齐
- 2026-04-17 已定位并修复一个 PX4 前端显示细节问题：
  - PX4 返回的 `current_waypoint_index` 不是前端喷洒航线的纯 0..N 索引
  - 当该索引超过前端航线长度时，旧实现会把无人机钉死在最后一个点
  - 该问题现已从后端 PX4 进度源头修正：
    - 前端拿到的 `current_waypoint_index` 已尽量保持为真实喷洒航线索引
    - 位置展示优先使用 PX4 实时遥测位置，避免继续依赖越界索引回退策略
- 2026-04-23 已完成 RAG 决策增强链路集成：
  - `modules/rag/` 全套落地：QwenEmbeddings、VectorStoreManager、DecisionRAGRetriever、knowledge_loader
  - `modules/ai_decision.py` 已集成 RAG 检索，失败时降级不中断
  - 新增 `tests/test_rag_embeddings.py` 和 `tests/test_rag_retriever.py`
  - 全量回归：77 passed in 9.13s
  - Git 提交：`ee27b87 feat(rag): integrate DecisionRAGRetriever into DecisionEngine pipeline`
- 2026-04-17 已按当前 `muye` 仓库真实状态修订一份对外项目计划书：
  - 修订文件：`/home/qingking/牧野智农(1)-muye修订版.docx`
  - 并已复制回用户微信文件目录，文件名为 `牧野智农(1)-muye修订版.docx`
  - 对外口径已从旧版设想统一修正为当前真实工程方案：
    - 前端为 `Vite + React + TypeScript` 指挥大屏，而非 `Uni-app + Streamlit`
    - 后端主入口为 `FastAPI`
    - 数据层当前以 `SQLite + JSONL event bus + 本地文件存储` 为主，而非 `PostgreSQL + Neo4j + MinIO`
    - 无人机演示链当前强调 `simulated / remote_api / px4` 三套后端与 PX4 可视化演示
    - 明确保留“数据库导入真实农业数据后参与决策”的后续规划
- 2026-04-22 已确认后端正在从单文件入口向模块化 FastAPI 结构演进：
  - `app/main.py` 已明显瘦身
  - 新增 `core/`、`routes/`、`services/`、`models/schemas.py`
  - 当前这轮重构的重点不是改接口语义，而是拆分组织结构
  - 测试兼容策略也已同步调整：
    - `routes/health.py -> collect_health_status()` 会检查 `main._check_*` monkeypatch，并兼容无参 lambda / 正常有参函数
    - `services/workflow_service.py -> build_history_response()` 已加入对 `main` 模块 monkeypatch 的桥接，避免测试替换失效
    - `routes/tasks.py` 已通过 `_get_annotate_fn()` 优先使用 `main._annotate_image`

## Next Work

1. 每次后续改动后，先同步 `PROJECT_MEMORY.md`，必要时同步 `CHANGELOG.md`，再结束本轮工作。
2. 在目标机器上实际复核一次 PX4 演示链：
   - `./scripts/run_px4_demo.sh`
   - 或 `./scripts/start_px4_visual_demo.sh --sample-image IP000000042.jpg`
3. 如果现场演示优先级最高，继续强化比赛模式：
   - 日志提示
   - QGC 检测
   - 浏览器拉起
   - 错误时的快速回退
4. 继续扩展 SQLite 读取侧，而不只是写入：
   - 更细粒度历史查询
   - 更清晰的报表/统计视图
   - 农业数据和喷洒记录联动查询
   - 继续扩展 `SqliteDecisionContextProvider` 的取数与裁剪策略，避免后续 prompt 膨胀
5. 继续补农业数据：
   - 正式农药目录
   - 真实河南天气 CSV
   - 更细的土壤/地块/作物属性
6. 继续完善 RAG 链路：
   - 将历史决策自动灌入向量库，积累检索语料
   - 考虑将 `docs/` 知识文档纳入向量检索
   - 评估是否需要增加重排序（reranking）层
   - 将 `data/chroma_db/` 加入 `.gitignore`

## Update Rule

每次出现下面任一情况，都必须同步更新本文件和 `CHANGELOG.md`：

- 架构方向变化
- 新增或替换关键运行方式
- 数据模型变化
- 仿真/飞控接入路线变化
- 演示链路验证结论变化
