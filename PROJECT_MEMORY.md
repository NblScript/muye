# Project Memory

## Current Priority

1. 维护并稳定当前已经接入的 `PX4 + Gazebo SITL + Muye` 演示链路，而不是回退到只靠虚拟无人机 API。
2. 继续扩展 SQLite 结构化存储和读取侧能力，保持 `JSONL + SQLite` 混合存储策略。
3. 继续完善河南农业数据 seed / import / 查询链路，服务于演示与后续报表能力。
4. 保留 `simulated` / `remote_api` / `px4` 三种无人机 backend 并存，方便本地联调、稳定演示和真实 SITL 切换。

## Confirmed Decisions

- 当前仓库已经不是“准备接 PX4”，而是“PX4 backend 已落地”：
  - `modules/px4_simulator.py` 已存在。
  - `modules/drone_controller.py` 已支持 `backend=px4`。
  - `main.py` 已支持 `--drone-backend px4` 与 PX4 环境变量覆盖。
  - `config/drone_config.json` 与 `.env.example` 已包含 PX4 配置。
- 当前仓库已经提供完整的 PX4 一键演示脚本族：
  - `scripts/run_px4_demo.sh`
  - `scripts/start_px4_visual_demo.sh`
  - `scripts/start_competition_mode.sh`
  - `scripts/start_all_in_one.sh`
- 非 PX4 的原始 demo 入口仍保留：
  - `scripts/start_demo.sh`
  - 适合继续走 `with-demo-stack + virtual drone` 的稳定演示路径
- PX4 演示默认采用仓库内置 Zurich SITL 演示地块，而不是直接飞业务配置里的河南地块：
  - `config/drone_config.json -> px4.demo_field`
  - `main.py -> _build_px4_demo_field_context()`
  - `PX4_USE_SITL_DEMO_FIELD=true` 时会自动启用
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
  - `app.py` 优先读取 SQLite，再用 JSONL 补实时阶段与时间线
- LLM 与 planner 的职责边界已经收敛：
  - `ai_decision.py` 只输出用药建议与农事建议
  - `mission_planner.py` 负责飞行路径、高度、速度、喷洒速率与气象限制
- 运行时地块上下文策略已经确定：
  - 优先使用 `PX4 SITL demo field`
  - 其次使用 `MUYE_ACTIVE_FIELD_ID`
  - 再从 SQLite `fields / field_crop_cycles` 解析
  - 最后才回退到 `config/drone_config.json`
  - 当回退配置被使用时，会自动 seed 到 SQLite，避免外键缺失

## Current Code Status

### Main Flow

- `main.py`
  - 负责系统装配、worker 队列、embedded YOLO / virtual drone 服务启动
  - 支持 `--with-yolo-api`、`--with-virtual-drone-api`、`--with-demo-stack`
  - 支持 `--drone-backend simulated|remote_api|px4`
  - 支持 `--no-capture-on-startup`
  - 已内建 PX4 环境变量覆盖和 demo field 切换逻辑
- `modules/drone_controller.py`
  - 已支持 simulated、remote API、PX4 三种执行路径
  - 无人机状态流会写入 SQLite `drone_mission_updates`
  - 最终状态会映射回 `spray_records.result_status`
- `modules/px4_simulator.py`
  - 已通过 `mavsdk` 接 PX4 SITL
  - 已支持连接、等待定位、上传任务、自动解锁、自动起飞、任务完成监听
  - 已支持航点接受半径、停留时间、飞越航点、原地转弯等演示控制参数

### PX4 Scripts

- `scripts/run_px4_demo.sh`
  - 一键跑通 `PX4 SITL -> Muye backend -> 示例图注入 -> 等待任务完成`
  - 会清理代理环境变量，避免 PX4 本地构建/运行受代理干扰
  - 支持 `--skip-px4`、`--keep-px4`、`--system-address`、`--world`
- `scripts/start_px4_visual_demo.sh`
  - 一键拉起 `PX4 SITL + Gazebo + Muye backend + Streamlit`
  - 可选自动拉起 `QGroundControl`
- `scripts/start_competition_mode.sh`
  - 包装 visual demo，并尝试自动打开浏览器，面向比赛现场展示
- `scripts/start_all_in_one.sh`
  - 面向最直接的一键入口，透传 QGC / browser / PX4 参数

### Non-PX4 Demo Script

- `scripts/start_demo.sh`
  - 继续保留为本地 YOLO + 虚拟无人机 + Streamlit 的基础演示入口
  - 适合作为 PX4 环境不可用时的稳定回退路径

### Database / Data Model

- `modules/sqlite_store.py`
  - 已完成旧库迁移、主 schema 初始化、索引、WAL / NORMAL
  - 已支持 `fetch_field_context()`、`fetch_task_views()` 等读取侧能力
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
- `scripts/migrate_to_v1_1.py`
  - 继续保留为 SQLite 旧库迁移工具
- `v1.1.1`
  - 代表 SQLite migration support 发布线，相关说明已进入 `CHANGELOG.md`
- `models/agri_models.py`
  - 已定义 `CropCatalog`、`Field`、`FieldCropCycle` SQLAlchemy 模型，作为农业数据层参考模型

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

- `app.py`
  - 已能识别 PX4 状态时间线并展示为 `PX4 SITL`
  - 已优先读 SQLite 任务历史
  - 已补任务历史检索、作业结论、结构化无人机状态、农药/天气/喷洒摘要
  - 仍用 JSONL 事件流补实时态和日志滚动

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

## Last Verified State

- 2026-04-16 已重新逐项核对当前仓库中的源码、配置、脚本、测试与文档：
  - `main.py`
  - `app.py`
  - `modules/*.py`
  - `scripts/*.sh`
  - `scripts/*.py`
  - `tests/*.py`
  - `README.md`
  - `config/drone_config.json`
  - `.env.example`
- 本次核对确认：
  - 记忆文件此前落后于代码状态
  - 当前仓库已经包含 PX4 接入和完整一键演示脚本
  - 当前仓库已经包含 SQLite 深化接入和农业数据扩展
- 当前本地测试已实际通过：
  - `PYTHONPATH=/home/qingking/muye /home/qingking/muye/.venv/bin/pytest -q`
  - 结果：`53 passed in 5.32s`
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

## Known Gaps / Risks

- PX4 代码虽然已接入，但真实运行仍依赖外部环境：
  - `PX4-Autopilot`
  - Gazebo Sim
  - `mavsdk`
  - 可选 `QGroundControl`
- 本次会话没有重新实际启动 `make px4_sitl gz_x500` 做端到端现场验证；本次验证重点是“仓库代码状态”和“记忆同步”。
- `pesticide_catalog` 当前仍是示例 seed，用于联调和字段关联，不是正式官方登记全量库。
- 河南历史天气导入能力已具备，但真实 CSV 仍需用户后续提供再做真实入库验证。

## Next Work

1. 在目标机器上实际复核一次 PX4 演示链：
   - `./scripts/run_px4_demo.sh`
   - 或 `./scripts/start_px4_visual_demo.sh --sample-image IP000000042.jpg`
2. 如果现场演示优先级最高，继续强化比赛模式：
   - 日志提示
   - QGC 检测
   - 浏览器拉起
   - 错误时的快速回退
3. 继续扩展 SQLite 读取侧，而不只是写入：
   - 更细粒度历史查询
   - 更清晰的报表/统计视图
   - 农业数据和喷洒记录联动查询
4. 继续补农业数据：
   - 正式农药目录
   - 真实河南天气 CSV
   - 更细的土壤/地块/作物属性

## Update Rule

每次出现下面任一情况，都必须同步更新本文件和 `CHANGELOG.md`：

- 架构方向变化
- 新增或替换关键运行方式
- 数据模型变化
- 仿真/飞控接入路线变化
- 演示链路验证结论变化
