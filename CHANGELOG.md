# Changelog

## v1.3

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

## v0.3-initial

- 新增 `scripts/start_demo.sh`，支持一键启动后端 demo 栈和 Streamlit 前端。
- README 更新为和真实运行方式一致，补充了一键启动、样例图触发和实际可用测试命令。
- 已验证前后端可以同时启动。
- 已验证样例图 `IP000000042.jpg` 可走通：
  - YOLO 识别
  - 天气获取
  - 千问决策
  - 虚拟无人机状态推进
  - pipeline completed

## v0.2-initial

- 支持真实 YOLO、真实和风天气、真实千问增强链路、虚拟无人机和可视化指挥中心前端。

## v0.1-initial

- 初始稳定版本，包含基础 YOLO、天气、千问、无人机控制和测试结构。
