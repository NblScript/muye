# 牧野智能农业害虫防治系统

`muye` 是一个基于 Python 的智能农业害虫防治项目，集成了无人机图像采集、YOLO 害虫识别、和风天气数据整合、千问 AI 决策和精准喷洒控制。项目采用异步任务流、模块化设计，并对外部 API 响应进行严格校验。

> 面向智慧农业演示与原型验证的端到端植保指挥系统。

## 项目简介

牧野将“虫情感知、气象感知、AI 决策、无人机执行、前端可视化”整合为一条完整链路，目标不是单点展示某个模型，而是提供一个可以真实联调、可视化演示、可持续扩展的智慧农业指挥中心原型。系统既支持本地离线能力验证，也支持接入真实天气服务和真实大模型接口，适合用于课程设计、路演演示、方案验证和后续工程化扩展。

核心亮点：

- 端到端闭环：从农田图片输入到虫害识别、药剂建议、飞行参数生成，再到虚拟无人机执行状态回放。
- 双模式运行：天气与千问均支持 `real/mock` 两种模式，兼顾真实联调与稳定演示。
- 本地可部署：YOLO 模型通过本地 API 服务封装，支持直接加载 `best.pt` 权重运行。
- 可视化指挥中心：基于 `Vite + React + TypeScript` 构建指挥大屏，统一承接图片上传、识别结果、天气/决策卡片、态势图、任务历史与事件日志。
- 工程化结构清晰：配置、模块、测试、虚拟服务、前端和事件总线分层明确，便于维护与继续开发。
- 混合存储起步：保留 JSONL 事件流，同时将主处理链摘要同步写入 SQLite，方便后续查询与扩展。
- 状态可追溯：无人机任务推进状态也会落入 SQLite，便于历史检索和后续报表扩展。

适用场景：

- 智慧农业项目演示与答辩
- 植保无人机调度原型验证
- YOLO + 大模型 + 外部 API 的系统集成实践
- 后续扩展为真实设备控制平台的工程起点

## 项目结构

```text
muye/
├── AGENTS.md                        # AI Agent 导航入口（~100行）
├── ARCHITECTURE.md                  # 架构总览（分层 + 数据流）
├── QUALITY_SCORE.md                 # 模块质量评分
├── CHANGELOG.md                     # 发行变更日志
├── PROJECT_MEMORY.md                # 当前优先级、架构决策和下一步计划
├── README.md                        # 项目总说明
├── requirements.txt                 # Python 依赖清单
│
├── app/                             # FastAPI 应用层
│   ├── main.py                      # 主入口 + 路由注册
│   ├── drone_api.py                 # 虚拟无人机 API（独立服务）
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
│   │   ├── ai_decision.py           # 千问决策 + jsonschema 校验
│   │   ├── decision_context.py      # 决策增强上下文
│   │   └── rag/                     # RAG 知识增强
│   │       ├── embeddings.py        # QwenEmbeddings (DashScope)
│   │       ├── vectorstore.py       # ChromaDB 向量库
│   │       ├── retriever.py         # DecisionRAGRetriever 检索
│   │       ├── knowledge_loader.py  # 农药知识加载
│   │       └── __init__.py
│   ├── drone/                       # 无人机域
│   │   ├── controller.py            # 无人机任务执行与状态回写
│   │   ├── mission_planner.py       # 飞行/喷洒规划
│   │   ├── px4_simulator.py         # PX4 SITL / MAVSDK 执行链路
│   │   ├── virtual_api.py           # 虚拟无人机 HTTP 服务
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
├── docs/                            # 精简文档系统 (Harness-style)
│   ├── design/                      # 设计文档
│   │   └── index.md                 # 核心信念 + 架构原则
│   ├── plans/                       # 执行计划
│   │   ├── active/                  # 正在执行的计划
│   │   ├── completed/               # 已完成的计划
│   │   ├── tech-debt.md             # 技术债务追踪
│   │   └── *.md                     # 历史计划
│   ├── reference/                   # 参考
│   │   ├── api.md                   # API 端点列表
│   │   └── data-model.md            # SQLite schema
│   ├── operations/                  # 运维
│   │   └── runbooks/                # 操作手册
│   └── WORKLOG.md                   # 会话级工作记录
│
├── frontend/                        # React 前端
│   ├── src/                         # 前端源码
│   ├── public/                      # 静态资源
│   ├── package.json                 # 前端依赖和脚本
│   ├── vite.config.ts               # Vite 配置与 API 代理
│   └── PROJECT_STRUCTURE.md         # 前端结构说明
│
├── scripts/                         # 辅助脚本
│   ├── start_demo.sh                # 演示模式启动
│   ├── start_px4_visual_demo.sh     # PX4 + Gazebo 演示
│   ├── start_competition_mode.sh    # 比赛模式
│   ├── start_all_in_one.sh          # 一键启动
│   ├── build_rag_knowledge.py       # 构建 RAG 向量知识库
│   └── import_*.py / generate_*.py  # 数据导入脚本
│
└── tests/                           # 自动化测试
    ├── test_main.py                 # 主入口 / API 契约 / 主流程测试
    ├── test_drone_controller.py     # 无人机 backend 测试
    ├── test_mission_planner.py      # 航线与演示 profile 测试
    ├── test_sqlite_migration.py     # SQLite schema / migration 测试
    ├── test_rag_embeddings.py       # RAG Embeddings API 契约测试
    ├── test_rag_retriever.py        # RAG Retriever 测试
    └── ...                          # 其余 AI / 天气 / YOLO / 虚拟无人机测试
```

## 当前开发主线

当前仓库推荐按下面的心智模型理解：

- `app/main.py`
  负责两件事：
  1. 农业处理主流程编排
  2. 给 React 大屏提供 `api_app`
- `app/drone_api.py`
  独立无人机 API 服务，负责虚拟任务状态机。
- `app/yolo_api.py`
  独立 YOLO 推理服务，接收图片返回害虫检测结果。
- `modules/` 核心业务逻辑按领域分组：`decision/`、`drone/`、`detection/`、`infra/`。
- `frontend/`
  是唯一前端主线，不再存在 Streamlit 页面
- `modules/infra/sqlite_store.py + modules/infra/event_bus.py`
  分别负责结构化历史和实时事件
- `scripts/start_demo.sh`
  是最直接的本地演示入口，会同时启动：
  - `app/main.py --with-demo-stack`
  - `uvicorn app.main:api_app`
  - `frontend` 的 Vite 开发服务器

## 目录导读

如果你是第一次接手这个仓库，建议按这个顺序看：

1. [AGENTS.md](AGENTS.md) — AI Agent 导航入口
2. [ARCHITECTURE.md](ARCHITECTURE.md) — 架构总览
3. [README.md](README.md) — 项目总说明
4. [PROJECT_MEMORY.md](PROJECT_MEMORY.md) — 当前优先级和决策
5. [frontend/PROJECT_STRUCTURE.md](frontend/PROJECT_STRUCTURE.md) — 前端结构
6. [tests/test_main.py](tests/test_main.py) — 主流程测试

## 功能说明

### 应用层（app/）

1. `app/main.py`
   - 装配 YOLO、天气、决策、无人机执行和 SQLite 写入链路。
   - 暴露前端聚合 API：`/health`、`/workflow/*`、`/dashboard/*`、`/tasks/*`、`/demo/*`、`/sim/*`。
   - 在一键演示模式下可同时接管本地 YOLO API 和虚拟无人机 API。

2. `app/drone_api.py`
   - 独立虚拟无人机 API 服务（端口 8001）。
   - 提供任务创建与任务状态查询接口。
   - 自动模拟排队、起飞、前往作业区、喷洒、返航和完成状态。

3. `app/yolo_api.py`
   - 独立本地 YOLO 推理 API 服务（端口 8002）。
   - 接收图片，返回害虫类型、置信度、位置信息。

### 核心业务层（modules/）

4. `modules/detection/` — 检测域
   - `image_processor.py`：异步调用 YOLO API，校验害虫类型、置信度、位置信息。
   - `local_yolo_api.py`：嵌入式 YOLO API，支持直接加载 `best.pt` 权重。
   - `data_collector.py`：每 24 小时自动触发无人机采图，使用 watchdog 监听新图片。

5. `modules/decision/` — 决策域
   - `ai_decision.py`：将害虫检测和天气信息整合成结构化文本，调用千问 API 输出用药建议 + 农事建议 JSON。使用 jsonschema 强制校验返回结构。已集成 RAG 检索增强：决策前自动检索农药知识库和历史案例，失败时降级不中断。
   - `decision_context.py`：决策增强上下文抽象。
   - `rag/`：RAG 决策增强模块（LangChain + ChromaDB）。
     - `embeddings.py`：QwenEmbeddings 封装阿里云 DashScope text-embedding-v3 API。
     - `vectorstore.py`：VectorStoreManager 管理 ChromaDB 向量库。
     - `retriever.py`：DecisionRAGRetriever 根据害虫类型和作物名称检索。
     - `knowledge_loader.py`：从 SQLite 或 JSON 文件加载农药知识。

6. `modules/drone/` — 无人机域
   - `controller.py`：无人机任务执行与状态回写。
   - `mission_planner.py`：飞行/喷洒规划。
   - `px4_simulator.py`：PX4 SITL / MAVSDK 执行链路。
   - `virtual_api.py`：虚拟无人机 HTTP 服务。

7. `modules/infra/` — 基础设施域
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

DRONE_API_URL="http://127.0.0.1:9010/missions"
DRONE_API_KEY="virtual-drone-token"
VIRTUAL_DRONE_HOST="127.0.0.1"
VIRTUAL_DRONE_PORT="9010"
VIRTUAL_DRONE_ALLOWED_IPS="127.0.0.1,::1"
SERVICE_CLIENT_IP="127.0.0.1"
```

说明：

- 请将训练好的权重文件放到 `models/best.pt`。
- 主流程会优先从 SQLite `fields` / `field_crop_cycles` 读取运行时地块上下文；`drone_config.json` 里的地块信息只作为回退配置。
- `drone_config.json` 中的 `field.weather_location` 或 `field.location.city` 用于回退天气地点查询，建议填写河南城市名，例如 `郑州`。
- 本地 YOLO API 默认读取 `YOLO_LOCAL_MODEL_PATH`，主流程默认调用 `YOLO_API_URL`。
- `YOLO_API_KEY` 同时用于主项目访问本地 YOLO API 的 Bearer Token。
- `MUYE_SQLITE_PATH` 默认是 `data/muye.db`，主处理链会把任务、检测、天气和决策摘要同步写入该库。
- `MUYE_ACTIVE_FIELD_ID` 可指定当前演示链路优先使用的数据库地块 ID。
- `drone_config.json` 中 `simulate_capture=true` 时，系统会自动生成一张最小 JPEG 作为采图结果，便于本地联调。
- `execution.simulate_only=true` 时，无人机喷洒任务只做本地模拟，不访问虚拟无人机 API。
- 使用 `--with-virtual-drone-api` 或 `--with-demo-stack` 时，主程序会自动接管无人机接口地址并关闭本地模拟模式。
- `DRONE_BACKEND=px4` 时，项目会改走 PX4 SITL / MAVSDK 执行链路。
- 本地 PX4 演示建议同时设置 `PX4_USE_SITL_DEMO_FIELD=true`，让任务使用仓库内置的 Zurich SITL 小地块，而不是直接飞往业务配置里的真实农田坐标。
- 当前比赛演示脚本默认使用 `PX4_SYSTEM_ADDRESS=udpin://0.0.0.0:14540`，直接监听 PX4 的 Onboard MAVLink 远端端口，现场启动更稳。

## 运行方式

推荐一键启动整套演示：

```bash
cd /home/qingking/muye
./scripts/start_demo.sh
```

如果你想启动后自动投喂仓库里的示例图片并触发一轮完整流程：

```bash
cd /home/qingking/muye
./scripts/start_demo.sh --sample-image IP000000042.jpg
```

如果当前机器上 `18000` 已被占用，也可以显式换一个前端 API 端口：

```bash
cd /home/qingking/muye
./scripts/start_demo.sh --api-port 18100
```

默认启动后：

- 后端主流程会以 `--with-demo-stack` 方式运行
- 演示脚本拉起的前端 API 会监听 `127.0.0.1:18000`
- 本地 YOLO API 会监听 `127.0.0.1:8010`
- 虚拟无人机 API 会监听 `127.0.0.1:9010`
- React 前端会监听 `127.0.0.1:8501`
- 按 `Ctrl+C` 会一起停止前后端进程

## PX4 SITL 演示

如果要把项目切到 PX4 仿真执行链路，推荐直接跑下面这条命令：

```bash
cd /home/qingking/muye
./scripts/run_px4_demo.sh
```

这条脚本会完成下面几件事：

- 启动 `~/PX4-Autopilot` 下的 `make px4_sitl gz_x500`
- 默认切到 `muye_demo_field` Gazebo 世界，场景里带演示农田、四角桩和可见边界
- 自动清理代理环境变量，避免 PX4 本地构建/运行链路被代理干扰
- 以 `DRONE_BACKEND=px4` 启动 Muye 后端和本地 YOLO API
- 强制切换到仓库内置的 Zurich SITL 演示地块
- 注入示例图 `IP000000042.jpg`，等待任务真正执行到 PX4 `completed`

如果 PX4 已经在另一个终端跑着，可以复用现有实例：

```bash
cd /home/qingking/muye
./scripts/run_px4_demo.sh --skip-px4
```

常用参数：

- `--px4-dir /path/to/PX4-Autopilot`：指定 PX4 仓库路径
- `--sample-image /path/to/image.jpg`：替换演示图片
- `--system-address udpin://0.0.0.0:14540`：覆盖 MAVSDK 连接地址
- `--world muye_demo_field`：覆盖 Gazebo 世界名称；如果想手工启动，也可执行 `PX4_GZ_WORLD=muye_demo_field make px4_sitl gz_x500`
- `--keep-px4`：演示结束后不关闭 PX4 SITL

如果比赛演示时希望把 `PX4/Gazebo + Muye 前端` 一起拉起来，直接运行：

```bash
cd /home/qingking/muye
./scripts/start_px4_visual_demo.sh --sample-image IP000000042.jpg
```

这条脚本会：

- 启动 `PX4 SITL + Gazebo`
- 以 `PX4` 模式启动 Muye 后端
- 启动 React 指挥大屏
- 如果本机已安装 `QGroundControl`，会自动尝试一并拉起

常用参数：

- `--skip-px4`：复用已运行的 PX4 SITL
- `--skip-qgc`：只看 Gazebo 和 Muye，不启动 QGroundControl
- `--qgc-path /path/to/QGroundControl.AppImage`：手工指定 QGroundControl 路径
- `--frontend-port 8501`：指定前端端口
- `--api-port 18100`：指定前端 API 端口，避免现场端口冲突

如果想切到“比赛模式”，让脚本在启动后自动拉起浏览器并给出现场展示提示，运行：

```bash
cd /home/qingking/muye
./scripts/start_competition_mode.sh --sample-image IP000000042.jpg
```

如果你只想记一个最直接的一键命令，直接运行：

```bash
cd /home/qingking/muye
./scripts/start_all_in_one.sh
```

这条脚本默认会：

- 拉起 `PX4 SITL + Gazebo`
- 拉起 Muye 后端
- 拉起 React 前端
- 自动打开浏览器中的控制台页面
- 自动尝试打开 `QGroundControl` 无人机页面

常用参数：

- `--with-sample`：启动后自动注入仓库内置演示图片，直接触发完整演示流程
- `--sample-image /path/to/image.jpg`：改用你自己的演示图片
- `--skip-px4`：复用已经运行中的 PX4
- `--skip-qgc`：不打开 QGroundControl
- `--skip-browser`：不自动打开网页

比赛模式额外参数：

- `--browser-cmd /usr/bin/firefox`：指定浏览器程序
- `--api-port 18100`：透传给底层 visual demo 脚本，覆盖前端 API 端口
- 其余 `PX4/QGC` 相关参数会透传给 `start_px4_visual_demo.sh`

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

## 工程记忆

为了避免后续协作时丢失上下文，项目内约定维护两份工程记忆文件：

- `PROJECT_MEMORY.md`
  - 记录当前优先级
  - 记录关键架构决策
  - 记录最近一次验证结论
  - 记录下一步计划
- `CHANGELOG.md`
  - 记录高层修改日志
  - 用来快速回顾最近版本做了什么
- `docs/WORKLOG.md`
  - 记录本轮协作做了什么
  - 记录当前交接点
  - 用来帮助新会话快速接上上一轮工作

后续每次涉及架构、数据模型、演示链路或关键运行方式变化时，都应同步更新这些记忆文件。

当前项目已经支持以下真实/模拟组合：

- YOLO：真实本地模型 `best.pt`
- 和风天气：真实接口
- 千问：支持真实接口，也支持通过 `QWEN_USE_MOCK` 切换为模拟模式
- 无人机：
  - `simulated`
  - 虚拟无人机 API
  - `PX4 SITL / MAVSDK`

当你的 [api_keys.env](/home/qingking/muye/config/api_keys.env) 中设置为：

```env
QWEATHER_USE_MOCK="false"
QWEN_USE_MOCK="false"
```

系统会运行在“真实天气 + 真实千问 + 当前 `DRONE_BACKEND` 指定的无人机 backend”模式。

推荐一键启动本地 YOLO API、虚拟无人机 API 与主系统：

```bash
cd /home/qingking/muye
python -m app.main --with-demo-stack
```

执行一次完整链路后退出：

```bash
cd /home/qingking/muye
python -m app.main --with-demo-stack --once
```

如果你希望分开启动，也可以先启动本地 YOLO API：

```bash
cd /home/qingking/muye
python yolo_api.py
```

再启动虚拟无人机 API：

```bash
cd /home/qingking/muye
python drone_api.py
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
python -m app.main --with-demo-stack
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
npm run dev -- --host 127.0.0.1 --port 8501
```

如果不是通过脚本启动，而是手工启动前端，且前端 API 不在默认 `18000`，需要显式指定代理目标：

```bash
cd /home/qingking/muye/frontend
MUYE_API_TARGET=http://127.0.0.1:18100 npm run dev -- --host 127.0.0.1 --port 8501
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
- 结构化业务数据默认写入 `data/muye.db`
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
- 虚拟无人机与 PX4 状态推进
- 千问决策 JSON Schema 校验与结构化输入构建
- SQLite 迁移、结构化历史读取与农业数据写入
- 主流程 `spray_records` / `pesticide_catalog` / 地块上下文联动

## 前端构建与缓存策略

为了解决 React 大屏初始构建产物过大、业务代码改动会牵连整包失效的问题，当前前端已启用显式代码分割。

当前 `frontend/vite.config.ts` 的拆包策略：

- `vendor-react`
  - `react`
  - `react-dom`
- `vendor-ui`
  - `antd`
  - `@ant-design/*`
  - `rc-*`
- `vendor-map`
  - `leaflet`
  - `react-leaflet`
- `vendor-misc`
  - 其余第三方依赖

这样做的效果是：

- 业务主包只保留当前页面和业务逻辑，首屏主业务 chunk 显著变小。
- 地图库和 UI 组件库被拆成独立 vendor chunk，更适合浏览器缓存复用。
- 当只修改业务代码时，只要相关 vendor 依赖内容没有变化，浏览器通常不需要重新下载 `vendor-map`、`vendor-ui` 等大包。

当前仓库构建结果中，文件名已经带内容哈希，例如：

- `vendor-map-*.js`
- `vendor-ui-*.js`
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
  - 当前稳定演示版本
  - 已支持真实 YOLO、真实和风天气、真实千问增强链路、虚拟无人机和可视化指挥中心前端

- `v0.3-initial`
  - 增加一键启动脚本 `scripts/start_demo.sh`
  - README 补齐完整演示启动流程与实际可用测试命令
  - 已验证后端全链路与 React 演示前端可一起运行

- `v1.3`
  - 已接入 `PX4 + Gazebo SITL` backend
  - 已补完整 PX4 一键演示脚本链
  - 已将 SQLite 深化接入主 pipeline、前端历史读取和农业数据层

## 部署建议

- 将 `config/api_keys.env` 中的示例值替换为真实密钥，避免提交到公共仓库。
- 若需要增强安全性，可在网关层补充 API 密钥认证、IP 白名单和速率限制。
- 如需监控，可在现有日志基础上接入 Prometheus/Grafana，并为 YOLO/Qwen/无人机接口增加指标采集。
- 上传接口当前默认限制单文件 `<= 10MB`，如果现场图片更大，需要同时调整后端常量和 Nginx `client_max_body_size`。
- `/demo/reset-events` 现在是破坏性操作，调用时必须显式带 `confirm=true`。
- `workflow/history.total` 当前返回的是“SQLite + event bus 合并、过滤、分页前”的真实总数；`items` 则严格受 `limit` 控制。
