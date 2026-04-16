# 牧野智能农业害虫防治系统

`muye` 是一个基于 Python 的智能农业害虫防治项目，集成了无人机图像采集、YOLO 害虫识别、和风天气数据整合、千问 AI 决策和精准喷洒控制。项目采用异步任务流、模块化设计，并对外部 API 响应进行严格校验。

> 面向智慧农业演示与原型验证的端到端植保指挥系统。

## 项目简介

牧野将“虫情感知、气象感知、AI 决策、无人机执行、前端可视化”整合为一条完整链路，目标不是单点展示某个模型，而是提供一个可以真实联调、可视化演示、可持续扩展的智慧农业指挥中心原型。系统既支持本地离线能力验证，也支持接入真实天气服务和真实大模型接口，适合用于课程设计、路演演示、方案验证和后续工程化扩展。

核心亮点：

- 端到端闭环：从农田图片输入到虫害识别、药剂建议、飞行参数生成，再到虚拟无人机执行状态回放。
- 双模式运行：天气与千问均支持 `real/mock` 两种模式，兼顾真实联调与稳定演示。
- 本地可部署：YOLO 模型通过本地 API 服务封装，支持直接加载 `best.pt` 权重运行。
- 可视化指挥中心：基于 Streamlit 构建前端面板，能够实时展示识别结果、天气信息、AI 建议、无人机状态与事件日志。
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
├── .env.example                 # 环境变量模板
├── CHANGELOG.md                 # 高层修改日志
├── PROJECT_MEMORY.md            # 当前优先级、架构决策和下一步计划
├── docs/
│   └── WORKLOG.md               # 会话级工作记录与交接点
├── app.py                       # Streamlit 可视化演示面板
├── config/                      # 项目配置目录
│   ├── api_keys.env             # 本地运行时密钥与接口地址配置
│   ├── drone_config.json        # 地块、围栏、飞行限制等无人机配置
│   └── yolo_config.yaml         # YOLO 推理服务相关配置
├── data/                        # 运行期数据目录
│   ├── images/                  # 无人机采集图像与演示上传图片
│   ├── logs/                    # 系统日志与事件总线文件
│   └── muye.db                  # SQLite 结构化业务存储
├── models/                      # 本地模型目录
│   └── README.md                # 模型放置说明
├── modules/                     # 核心业务模块
│   ├── __init__.py              # 模块包初始化文件
│   ├── ai_decision.py           # 千问决策与结构化提示词组装
│   ├── common.py                # 公共工具、日志与路径管理
│   ├── data_collector.py        # 图片采集与目录监听
│   ├── drone_controller.py      # 无人机指令校验与任务执行
│   ├── event_bus.py             # 基于 JSONL 的演示事件总线
│   ├── image_processor.py       # YOLO API 调用与识别结果校验
│   ├── local_yolo_api.py        # 本地 YOLO 模型 HTTP 服务
│   ├── mission_planner.py       # 系统级飞行与喷洒参数规划
│   ├── virtual_drone_api.py     # 虚拟无人机 HTTP 服务
│   └── weather_integration.py   # 和风天气接入与字段映射
├── drone_api.py                 # 虚拟无人机 API 启动入口
├── scripts/                     # 启动、seed 生成与导入辅助脚本
│   ├── generate_henan_field_crop_seed_csv.py # 生成河南地块/作物/cycle CSV
│   ├── generate_henan_soil_seed_csv.py       # 生成河南土壤检测 seed CSV
│   ├── import_henan_field_crop_seed_csv.py   # 导入河南地块/作物/cycle CSV
│   ├── import_henan_reference_data.py        # 导入河南统计指标 seed
│   ├── import_henan_soil_records_csv.py      # 导入河南土壤检测 CSV
│   ├── import_henan_weather_history_csv.py   # 导入河南历史天气 CSV
│   ├── run_px4_demo.sh          # 一键跑通 PX4 SITL 联调演示
│   ├── start_all_in_one.sh      # 一键拉起前后端、浏览器和无人机演示页面
│   └── start_demo.sh            # 一键启动后端 demo 栈和 Streamlit 前端
├── tests/                       # 单元测试目录
│   ├── test_ai_decision.py      # 千问决策测试
│   ├── test_event_bus.py        # 事件总线测试
│   ├── test_image_processor.py  # YOLO 识别流程测试
│   ├── test_local_yolo_api.py   # 本地 YOLO API 测试
│   ├── test_main.py             # 主入口辅助逻辑测试
│   ├── test_virtual_drone_api.py # 虚拟无人机状态流测试
│   └── test_weather_integration.py # 和风天气两步调用测试
├── main.py                      # 后端主入口与一键演示调度器
├── requirements.txt             # Python 依赖清单
├── yolo_api.py                  # 本地 YOLO API 启动入口
└── README.md                    # 项目说明文档
```

## 功能说明

1. `data_collector.py`
   - 每 24 小时自动触发无人机采图。
   - 使用 `watchdog` 实时监听 `data/images/` 新图片。
   - 图片命名格式为 `YYYYMMDD-HHMMSS.jpg`。

2. `image_processor.py`
   - 异步调用 YOLO API。
   - 校验害虫类型、置信度、位置信息。
   - 过滤低于置信度阈值的检测结果。
   - 已默认接到本地 YOLO `best.pt` API。

3. `local_yolo_api.py` + `yolo_api.py`
   - 将本地 `models/best.pt` 封装为 HTTP API。
   - 暴露 `/health` 和 `/detect` 两个接口。
   - 支持 Bearer Token 鉴权、IP 白名单、速率限制和批量推理。

4. `weather_integration.py`
   - 先调用和风天气城市查询接口获取 `Location ID`。
   - 再调用和风天气实况天气接口获取天气数据。
   - 将返回字段统一映射为项目内部格式：温度、湿度、风向、风力、天气概况。

5. `ai_decision.py`
   - 将害虫检测和天气信息整合成结构化文本。
   - 调用千问 API 输出“用药建议 + 农事建议”JSON。
   - 飞行路径、高度、喷洒速率和气象限制不再由 LLM 生成。
   - 使用 `jsonschema` 强制校验返回结构。

6. `drone_controller.py` + `mission_planner.py`
   - `mission_planner.py` 负责从地块围栏、天气和飞控约束生成系统执行参数。
   - `drone_controller.py` 负责校验气象限制、地理围栏和飞行控制参数。
   - 支持 `simulated`、虚拟无人机 API 和 `PX4 SITL / MAVSDK` 三种执行链路。

7. `main.py`
   - 使用 `asyncio` 组织采集、识别、决策、执行全流程。
   - 通过异步队列避免并发场景下的资源竞争。
   - 支持一键同时启动本地 YOLO API、虚拟无人机 API 和主系统，也支持切到 PX4 backend。

8. `event_bus.py`
   - 采用 `JSONL` 文件作为简单事件总线。
   - 后端关键节点会写入带时间戳、阶段和状态的事件。
   - Streamlit 面板通过轮询同一份事件文件实现跨进程展示。

9. `app.py`
   - 基于 Streamlit 的演示面板。
   - 支持上传图片、原图/识别图对比、天气/决策卡片、无人机进度和实时日志。

10. `virtual_drone_api.py` + `drone_api.py`
   - 提供虚拟无人机任务创建与任务状态查询接口。
   - 自动模拟排队、起飞、前往作业区、喷洒、返航和完成状态。

## 安装依赖

```bash
cd /home/qingking/muye
pip install -r requirements.txt
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

默认启动后：

- 后端主流程会以 `--with-demo-stack` 方式运行
- 本地 YOLO API 会监听 `127.0.0.1:8010`
- 虚拟无人机 API 会监听 `127.0.0.1:9010`
- Streamlit 前端会监听 `127.0.0.1:8501`
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
- 启动 Streamlit 演示面板
- 如果本机已安装 `QGroundControl`，会自动尝试一并拉起

常用参数：

- `--skip-px4`：复用已运行的 PX4 SITL
- `--skip-qgc`：只看 Gazebo 和 Muye，不启动 QGroundControl
- `--qgc-path /path/to/QGroundControl.AppImage`：手工指定 QGroundControl 路径
- `--frontend-port 8501`：指定 Streamlit 端口

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
- 拉起 Streamlit 前端
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
python main.py --with-demo-stack
```

执行一次完整链路后退出：

```bash
cd /home/qingking/muye
python main.py --with-demo-stack --once
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
python main.py
```

## 可视化演示面板

后端与前端通过同一个事件文件连接：

- 事件总线文件：`data/logs/demo_events.jsonl`
- 图片投喂目录：`data/images/`

如果你已经使用一键脚本启动，这一节可以跳过。

手动启动时，推荐使用两个终端同时启动：

终端 1，启动后端主流程：

```bash
cd /home/qingking/muye
. .venv/bin/activate
python main.py --with-demo-stack
```

终端 2，启动 Streamlit 前端：

```bash
cd /home/qingking/muye
. .venv/bin/activate
streamlit run app.py --server.headless true
```

启动后：

1. 在 Streamlit 左侧栏上传图片
2. 前端会将图片写入 `data/images/`
3. 后端监听到新图片后，依次执行 YOLO、天气、千问和无人机流程
4. 事件总线持续写入 `data/logs/demo_events.jsonl`
5. Streamlit 自动轮询并刷新原图、识别框、天气卡片、AI 建议和无人机状态
6. Streamlit 左侧栏会直接显示当前是 `real` 还是 `mock` 模式

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
  - 已验证后端全链路与 Streamlit 演示前端可一起运行

- `v1.3`
  - 已接入 `PX4 + Gazebo SITL` backend
  - 已补完整 PX4 一键演示脚本链
  - 已将 SQLite 深化接入主 pipeline、前端历史读取和农业数据层

## 部署建议

- 将 `config/api_keys.env` 中的示例值替换为真实密钥，避免提交到公共仓库。
- 若需要增强安全性，可在网关层补充 API 密钥认证、IP 白名单和速率限制。
- 如需监控，可在现有日志基础上接入 Prometheus/Grafana，并为 YOLO/Qwen/无人机接口增加指标采集。
