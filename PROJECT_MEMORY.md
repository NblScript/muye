# Project Memory

## Current Priority

1. 在现有 SQLite 起步版基础上继续扩展结构化业务存储，而不是回到只依赖 JSONL 和配置文件。
2. 把无人机路径、高度、喷洒速率、气象限制进一步从 LLM 建议里拆出来，收敛到系统 planner。
3. 补无人机状态流、历史农业数据和面向前端查询的结构化读取能力。
4. 仿真平台后续评估更专业路线，重点候选仍是 PX4/Gazebo，并按需评估 AirSim。

## Confirmed Decisions

- 项目当前已经具备完整演示链路：
  - 本地 YOLO
  - 真实天气
  - 真实千问
  - 虚拟无人机
  - Streamlit 前端
- `scripts/start_demo.sh` 是当前推荐的一键启动入口。
- 演示前端和后端已验证可以一起运行。
- 业务数据后续要引入 SQLite 存储。
- SQLite 采用“混合存储”策略：
  - 保留现有 JSONL 事件流，作为原始日志与调试信息
  - 新增 SQLite，作为结构化业务存储和前端查询来源
- 当前实现边界已确认：
  - 河南地块/作物核心模型文件已补齐：
    - `models/agri_models.py`
    - `CropCatalog`
    - `Field`
    - `FieldCropCycle`
  - 河南地块/作物 CSV 种子生成脚本已补齐：
    - `scripts/generate_henan_field_crop_seed_csv.py`
  - 河南地块/作物 CSV 导入脚本已补齐：
    - `scripts/import_henan_field_crop_seed_csv.py`
  - `modules/sqlite_store.py`、迁移脚本和回归测试已落地
  - 主演示链路 `MuyeApplication` 已开始同步写入 SQLite 起步表
  - 主演示链路现在会优先从 SQLite `fields` / `field_crop_cycles` 加载运行时地块上下文
  - Streamlit 前端已开始优先通过 SQLite 读取任务摘要与历史记录
  - `modules/event_bus.py` 仍保留，用于补实时阶段与事件日志
  - 无人机状态流已进入 SQLite `drone_mission_updates`
  - `tasks.field_id`、`fields.owner_user_id`、`crop_catalog.water_demand_coefficient` 已进入 SQLite 主 schema
  - AI 决策层与系统 planner 边界已重新收敛：
    - LLM 只输出用药建议与农事建议
    - `modules/mission_planner.py` 负责飞行路径、高度、喷洒速率和气象限制
  - 本轮审查驱动修复已完成：
    - `weather_history_daily` 允许同一站点同一天挂到多个地块，不再互相覆盖
    - 运行时地块选择不再默认取“第一块地”
    - 天气查询定位优先使用经纬度
    - `mission_planner` 已从“围栏顶点”升级为基础覆盖式往返航线
  - 河南参考数据第一批 seed 已落地：
    - `data_sources`
    - `agri_statistical_indicators`
    - 已附官方来源 URL 与摘录
- 河南历史天气已具备正式导入能力：
  - `weather_stations`
  - `weather_history_daily`
  - `scripts/import_henan_weather_history_csv.py`
  - 当前阻塞点：
    - 用户暂时无法下载河南天气 CSV
    - 先保留导入能力，后续拿到官方 CSV 后再做真实入库验证
- SQLite v1.1 已完成两阶段落地并已进入发布线：
  - PR #1 已合并：
    - `tasks.status` CHECK 约束
    - `request_id` 索引
    - WAL / NORMAL
  - PR #2 已合并：
    - `_migrate_v1_1()` 自动迁移旧库
    - `scripts/migrate_to_v1_1.py`
- `v1.1` tag 保持不动。
- 新版本 `v1.1.1` 已创建并发布，用于承载迁移支持版本说明。
- 旧库迁移回归测试、迁移文档和迁移事务修复已经完成并合入 `main`：
  - PR #3: `fix(sqlite): harden legacy DB migration and docs`
  - merge commit: `f544cc40adea68dd9c2bfe607c808c77fc98da06`
- 开发协作层面必须维护：
  - `PROJECT_MEMORY.md`
  - `CHANGELOG.md`

## Last Verified State

- `feat/sqlite-tuning` 分支本地验证通过：
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 结果：`19 passed`
- `feat/sqlite-migration-v1_1` 分支本地验证通过：
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 结果：`19 passed`
- 当前本地分支 `chore/sqlite-migration-regression-docs-v2` 已验证：
  - 提交：`3e03134 docs: update project memory after sqlite release closeout`
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 结果：`22 passed`
- 主流程 SQLite 接入回归测试已补充：
  - `tests/test_main.py::test_main_pipeline_writes_sqlite_records`
  - 结果：`passed`
- SQLite 历史读取与结构化检索测试已补充：
  - `tests/test_sqlite_migration.py::test_sqlite_store_fetch_task_views_supports_structured_history_queries`
  - 结果：`passed`
- 无人机状态流 SQLite 写入测试已补充：
  - `tests/test_drone_controller.py::test_drone_controller_persists_simulated_status_updates_to_sqlite`
  - 结果：`passed`
- 历史农业数据 schema 回归测试已补充：
  - `tests/test_sqlite_migration.py::test_sqlite_store_creates_agriculture_data_schema_scaffold`
  - 结果：`passed`
- 数据来源与统计指标写入测试已补充：
  - `tests/test_sqlite_migration.py::test_sqlite_store_supports_source_and_indicator_upserts`
  - 结果：`passed`
- 河南历史天气 CSV 导入测试已补充：
  - `tests/test_sqlite_migration.py::test_import_henan_weather_history_csv_imports_stations_and_daily_rows`
  - 结果：`passed`
- 河南地块/作物种子生成测试已补充：
  - `tests/test_henan_field_crop_seed_generation.py::test_generate_henan_field_crop_seed_csv_outputs_expected_files`
  - 结果：`passed`
- 河南地块/作物 CSV 导入与运行时字段解析测试已补充：
  - `tests/test_sqlite_migration.py::test_import_henan_field_crop_seed_csv_imports_and_resolves_runtime_context`
  - 结果：`passed`
- 主流程优先使用 SQLite 地块上下文测试已补充：
  - `tests/test_main.py::test_main_prefers_sqlite_field_context_over_static_config`
  - 结果：`passed`
- 运行时多地块歧义保护测试已补充：
  - `tests/test_main.py::test_main_rejects_ambiguous_field_context_without_explicit_selection`
  - 结果：`passed`
- 同站同日多地块天气写入测试已补充：
  - `tests/test_sqlite_migration.py::test_sqlite_store_supports_multiple_field_weather_rows_for_same_station_day`
  - 结果：`passed`
- 天气定位优先级测试已补充：
  - `tests/test_sqlite_migration.py::test_fetch_field_context_prefers_coordinates_for_weather_lookup`
  - 结果：`passed`
- planner 覆盖航线测试已补充：
  - `tests/test_mission_planner.py::test_mission_planner_generates_coverage_route_not_just_polygon_vertices`
  - 结果：`passed`
- 旧库迁移回归测试已补齐并通过：
  - `PYTHONPATH=. .venv/bin/pytest -q tests/test_sqlite_migration.py`
  - 结果：`1 passed`
- SQLite 相关回归已通过：
  - `PYTHONPATH=. .venv/bin/pytest -q tests/test_main.py tests/test_sqlite_migration.py`
  - 结果：`5 passed`
- 相关测试集合已通过：
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - 结果：`34 passed`
- `./scripts/start_demo.sh --sample-image IP000000042.jpg` 已验证：
  - 前端可访问
  - YOLO 可识别目标
  - 天气接口可用
  - 千问可生成决策
  - 虚拟无人机任务能走到 completed
  - pipeline 最终 completed

## SQLite Draft Schema

当前已确认的 SQLite 起步方案如下。

- 数据库文件名：
  - `muye.db`
- 存储策略：
  - JSONL 保留原始事件流
  - SQLite 存任务摘要、检测结果、天气快照和决策结果

### Table: `tasks`

- `request_id`: TEXT PRIMARY KEY
- `image_path`: TEXT
- `start_time`: DATETIME
- `end_time`: DATETIME
- `status`: TEXT

### Table: `detections`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `request_id`: TEXT
- `label`: TEXT
- `confidence`: REAL
- `bbox`: TEXT

### Table: `weather_snapshots`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `request_id`: TEXT
- `timestamp`: DATETIME
- `weather_data`: TEXT

### Table: `decisions`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `request_id`: TEXT
- `timestamp`: DATETIME
- `decision_text`: TEXT

### Table: `drone_mission_updates`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `request_id`: TEXT
- `timestamp`: DATETIME
- `task_id`: TEXT
- `status`: TEXT
- `message`: TEXT
- `progress`: INTEGER
- `current_waypoint_index`: INTEGER
- `instruction`: TEXT
- `medication`: TEXT

### Table: `fields`

- `field_id`: TEXT PRIMARY KEY
- `field_code`: TEXT UNIQUE
- `field_name`: TEXT
- `province`: TEXT
- `city`: TEXT
- `county`: TEXT
- `township`: TEXT
- `village`: TEXT
- `latitude`: REAL
- `longitude`: REAL
- `area_mu`: REAL
- `area_hectare`: REAL
- `geofence`: TEXT
- `soil_type`: TEXT
- `irrigation_type`: TEXT

### Table: `crop_catalog`

- `crop_code`: TEXT PRIMARY KEY
- `crop_name`: TEXT
- `category`: TEXT
- `variety`: TEXT

### Table: `field_crop_cycles`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `field_id`: TEXT
- `crop_code`: TEXT
- `year`: INTEGER
- `season`: TEXT
- `planting_date`: DATE
- `harvest_date`: DATE
- `area_mu`: REAL
- `expected_yield_kg`: REAL
- `actual_yield_kg`: REAL
- `status`: TEXT

### Table: `soil_records`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `field_id`: TEXT
- `sample_date`: DATE
- `depth_cm`: INTEGER
- `ph`: REAL
- `organic_matter_gkg`: REAL
- `alkali_hydrolyzable_nitrogen_mgkg`: REAL
- `available_phosphorus_mgkg`: REAL
- `available_potassium_mgkg`: REAL
- `moisture_percent`: REAL
- `salinity_gkg`: REAL
- `texture`: TEXT

### Table: `weather_history_daily`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `field_id`: TEXT
- `station_code`: TEXT
- `station_name`: TEXT
- `observation_date`: DATE
- `weather_summary`: TEXT
- `temperature_avg_c`: REAL
- `temperature_min_c`: REAL
- `temperature_max_c`: REAL
- `humidity_avg_percent`: REAL
- `precipitation_mm`: REAL
- `wind_speed_avg_mps`: REAL
- `wind_direction`: TEXT
- `sunshine_hours`: REAL

### Table: `weather_stations`

- `station_code`: TEXT PRIMARY KEY
- `station_name`: TEXT
- `province`: TEXT
- `city`: TEXT
- `county`: TEXT
- `latitude`: REAL
- `longitude`: REAL
- `elevation_m`: REAL
- `source_id`: TEXT

### Table: `pesticide_catalog`

- `pesticide_id`: TEXT PRIMARY KEY
- `registration_no`: TEXT UNIQUE
- `product_name`: TEXT
- `active_ingredient`: TEXT
- `formulation`: TEXT
- `toxicity`: TEXT
- `manufacturer`: TEXT
- `target_crops`: TEXT
- `target_pests`: TEXT
- `dilution_guidance`: TEXT

### Table: `spray_records`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `request_id`: TEXT
- `field_id`: TEXT
- `crop_cycle_id`: INTEGER
- `drone_task_id`: TEXT
- `pesticide_id`: TEXT
- `spray_date`: DATETIME
- `operator_name`: TEXT
- `spray_area_mu`: REAL
- `dosage_per_mu`: REAL
- `total_dosage`: REAL
- `dilution_ratio`: TEXT
- `spray_rate_lpm`: REAL
- `flight_height_m`: REAL
- `flight_speed_mps`: REAL
- `weather_snapshot`: TEXT
- `result_status`: TEXT

### Table: `data_sources`

- `source_id`: TEXT PRIMARY KEY
- `source_name`: TEXT
- `publisher`: TEXT
- `region_scope`: TEXT
- `source_type`: TEXT
- `source_url`: TEXT
- `access_level`: TEXT
- `retrieval_date`: DATE
- `license`: TEXT
- `notes`: TEXT

### Table: `agri_statistical_indicators`

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `region_level`: TEXT
- `region_name`: TEXT
- `province`: TEXT
- `city`: TEXT
- `county`: TEXT
- `year`: INTEGER
- `period`: TEXT
- `indicator_code`: TEXT
- `indicator_name`: TEXT
- `value`: REAL
- `unit`: TEXT
- `source_id`: TEXT
- `source_excerpt`: TEXT
- `raw_payload`: TEXT

### SQL DDL Draft

```sql
CREATE TABLE IF NOT EXISTS tasks (
  request_id TEXT PRIMARY KEY,
  image_path TEXT,
  start_time DATETIME,
  end_time DATETIME,
  status TEXT
);

CREATE TABLE IF NOT EXISTS detections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  label TEXT,
  confidence REAL,
  bbox TEXT,
  FOREIGN KEY (request_id) REFERENCES tasks(request_id)
);

CREATE TABLE IF NOT EXISTS weather_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  timestamp DATETIME,
  weather_data TEXT,
  FOREIGN KEY (request_id) REFERENCES tasks(request_id)
);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  timestamp DATETIME,
  decision_text TEXT,
  FOREIGN KEY (request_id) REFERENCES tasks(request_id)
);

CREATE TABLE IF NOT EXISTS drone_mission_updates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  timestamp DATETIME,
  task_id TEXT,
  status TEXT,
  message TEXT,
  progress INTEGER,
  current_waypoint_index INTEGER,
  instruction TEXT,
  medication TEXT,
  FOREIGN KEY (request_id) REFERENCES tasks(request_id)
);

CREATE TABLE IF NOT EXISTS fields (
  field_id TEXT PRIMARY KEY,
  field_code TEXT UNIQUE,
  field_name TEXT NOT NULL,
  province TEXT,
  city TEXT,
  county TEXT,
  township TEXT,
  village TEXT,
  latitude REAL,
  longitude REAL,
  area_mu REAL,
  area_hectare REAL,
  geofence TEXT,
  soil_type TEXT,
  irrigation_type TEXT,
  source TEXT,
  notes TEXT,
  created_at DATETIME,
  updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS crop_catalog (
  crop_code TEXT PRIMARY KEY,
  crop_name TEXT NOT NULL,
  category TEXT,
  variety TEXT,
  growth_cycle_days INTEGER,
  typical_planting_month TEXT,
  typical_harvest_month TEXT,
  source TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS field_crop_cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  field_id TEXT NOT NULL,
  crop_code TEXT NOT NULL,
  year INTEGER,
  season TEXT,
  planting_date DATE,
  harvest_date DATE,
  area_mu REAL,
  expected_yield_kg REAL,
  actual_yield_kg REAL,
  status TEXT,
  source TEXT,
  notes TEXT,
  FOREIGN KEY (field_id) REFERENCES fields(field_id),
  FOREIGN KEY (crop_code) REFERENCES crop_catalog(crop_code)
);

CREATE TABLE IF NOT EXISTS soil_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  field_id TEXT NOT NULL,
  sample_date DATE,
  depth_cm INTEGER,
  ph REAL,
  organic_matter_gkg REAL,
  alkali_hydrolyzable_nitrogen_mgkg REAL,
  available_phosphorus_mgkg REAL,
  available_potassium_mgkg REAL,
  moisture_percent REAL,
  salinity_gkg REAL,
  texture TEXT,
  source TEXT,
  raw_payload TEXT,
  FOREIGN KEY (field_id) REFERENCES fields(field_id)
);

CREATE TABLE IF NOT EXISTS weather_history_daily (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  field_id TEXT,
  station_code TEXT,
  station_name TEXT,
  observation_date DATE NOT NULL,
  weather_summary TEXT,
  temperature_avg_c REAL,
  temperature_min_c REAL,
  temperature_max_c REAL,
  humidity_avg_percent REAL,
  precipitation_mm REAL,
  wind_speed_avg_mps REAL,
  wind_direction TEXT,
  sunshine_hours REAL,
  source TEXT,
  raw_payload TEXT,
  FOREIGN KEY (field_id) REFERENCES fields(field_id)
);

CREATE TABLE IF NOT EXISTS weather_stations (
  station_code TEXT PRIMARY KEY,
  station_name TEXT NOT NULL,
  province TEXT,
  city TEXT,
  county TEXT,
  latitude REAL,
  longitude REAL,
  elevation_m REAL,
  source_id TEXT,
  notes TEXT,
  FOREIGN KEY (source_id) REFERENCES data_sources(source_id)
);

CREATE TABLE IF NOT EXISTS pesticide_catalog (
  pesticide_id TEXT PRIMARY KEY,
  registration_no TEXT UNIQUE,
  product_name TEXT NOT NULL,
  active_ingredient TEXT,
  formulation TEXT,
  toxicity TEXT,
  manufacturer TEXT,
  target_crops TEXT,
  target_pests TEXT,
  dilution_guidance TEXT,
  source TEXT,
  raw_payload TEXT
);

CREATE TABLE IF NOT EXISTS spray_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT,
  field_id TEXT NOT NULL,
  crop_cycle_id INTEGER,
  drone_task_id TEXT,
  pesticide_id TEXT,
  spray_date DATETIME NOT NULL,
  operator_name TEXT,
  spray_area_mu REAL,
  dosage_per_mu REAL,
  total_dosage REAL,
  dilution_ratio TEXT,
  spray_rate_lpm REAL,
  flight_height_m REAL,
  flight_speed_mps REAL,
  weather_snapshot TEXT,
  result_status TEXT,
  source TEXT,
  notes TEXT,
  FOREIGN KEY (request_id) REFERENCES tasks(request_id),
  FOREIGN KEY (field_id) REFERENCES fields(field_id),
  FOREIGN KEY (crop_cycle_id) REFERENCES field_crop_cycles(id),
  FOREIGN KEY (pesticide_id) REFERENCES pesticide_catalog(pesticide_id)
);

CREATE TABLE IF NOT EXISTS data_sources (
  source_id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL,
  publisher TEXT,
  region_scope TEXT,
  source_type TEXT,
  source_url TEXT NOT NULL,
  access_level TEXT,
  retrieval_date DATE,
  license TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS agri_statistical_indicators (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  region_level TEXT NOT NULL,
  region_name TEXT NOT NULL,
  province TEXT,
  city TEXT,
  county TEXT,
  year INTEGER NOT NULL,
  period TEXT NOT NULL,
  indicator_code TEXT NOT NULL,
  indicator_name TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT,
  source_id TEXT,
  source_excerpt TEXT,
  raw_payload TEXT,
  UNIQUE (
    region_level, region_name, province, city, county,
    year, period, indicator_code
  ),
  FOREIGN KEY (source_id) REFERENCES data_sources(source_id)
);
```

### Notes

- 这是当前确认的起步版 schema，用于先把结构化数据落库。
- 当前迁移路径的额外结论：
  - 旧库迁移前建议备份数据库
  - 旧库非法 `tasks.status` 会被规范化为 `error`
- 后续很可能继续扩展：
  - 无人机状态流
  - 历史农业数据
  - 更细的结构化字段
  但这些扩展暂未开始实施。

## Next Work

- 先把 `main` 本地同步到包含 PR #3 的最新状态。
- 在已接入的 SQLite 起步版基础上继续完善读取侧，而不只是写入：
  - 已完成前端查询接口
  - 已完成任务历史列表
  - 已完成结构化状态检索
- 在现有 SQLite 基础上继续扩展：
  - 历史农业数据导入
  - 面向前端查询的结构化读取接口
  - 更细粒度的无人机时序查询与统计
  - 农药数据的正式入库
- 河南地块/作物数据下一步：
  - 把 CSV seed 正式接入 SQLite 导入链
  - 再让 `fields` / `field_crop_cycles` 与天气、喷洒记录联动
- 河南天气数据的下一步提醒：
  - 等用户后续拿到官方天气 CSV
  - 直接运行 `scripts/import_henan_weather_history_csv.py`
  - 验证 `weather_stations` 与 `weather_history_daily` 实际入库结果
- 视需要补充 `v1.1.1` Release Notes 的迁移章节，使其与 `main` 当前状态完全一致。
- 后续再评估是否扩展：
  - 喷洒任务记录
  - 无人机状态流
  - 地块/作物/土壤/历史农业数据
- 把“LLM 决策”和“任务规划”拆层：
  - LLM 负责解释、建议、风险提示
  - 系统 planner 负责飞行参数和作业约束
- 评估仿真接入方案：
  - 先明确是否要对接 PX4/Gazebo
  - 再判断 AirSim 是否只保留为视觉仿真候选

## Update Rule

每次出现下面任一情况，都必须同步更新本文件和 `CHANGELOG.md`：

- 架构方向变化
- 新增或替换关键运行方式
- 数据模型变化
- 仿真/飞控接入路线变化
- 演示链路验证结论变化
