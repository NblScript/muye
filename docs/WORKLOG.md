# Worklog

## Current Session Summary

本轮已经完成：

- 已统一河南农业核心模型与 SQLite 主 schema：
  - `models/agri_models.py`
  - `modules/sqlite_store.py`
  - 对齐 `fields` / `crop_catalog` / `field_crop_cycles`
- 已补河南地块/作物 CSV 入库链路：
  - `scripts/generate_henan_field_crop_seed_csv.py`
  - `scripts/import_henan_field_crop_seed_csv.py`
- 已让主流程优先从 SQLite 读取运行时地块上下文：
  - `MUYE_ACTIVE_FIELD_ID`
  - `tasks.field_id`
  - `SqliteStore.fetch_field_context()`
- 已把飞行参数边界从 LLM 拆到系统 planner：
  - 新增 `modules/mission_planner.py`
  - `ai_decision.py` 只输出用药建议与农事建议
  - `drone_controller.py` / `main.py` 改为使用系统生成的执行参数
- 已把天气历史导入补成“站点 -> 最近地块”自动挂载：
  - `scripts/import_henan_weather_history_csv.py`
  - `SqliteStore.find_nearest_field_id()`
- 已修复前端合并 SQLite / JSONL 时覆盖掉结构化无人机状态的问题：
  - `app.py`

- 清理了本地工作区，把无关脏改动从功能分支上摘掉。
- 确认并合并了两个 SQLite 相关 PR：
  - PR #1: `feat(sqlite): add status CHECK, request_id indexes, WAL mode`
  - PR #2: `feat(sqlite): migration to enforce v1.1 constraints on existing DBs`
- 保持 `v1.1` tag 不变，并新建发布：
  - `v1.1.1 - SQLite migration support`
  - https://github.com/NblScript/muye/releases/tag/v1.1.1
- 补齐旧库迁移回归测试与迁移文档：
  - `tests/test_sqlite_migration.py`
  - `docs/06-operations/runbooks/sqlite-migration-v1_1.md`
  - `docs/08-testing/sqlite-migration-regression.md`
- 通过迁移回归测试定位并修复 `_migrate_v1_1()` 的事务处理问题。
- 创建并合并收尾 PR：
  - PR #3: `fix(sqlite): harden legacy DB migration and docs`
  - https://github.com/NblScript/muye/pull/3
- 重新检查当前本地项目状态并恢复工程上下文：
  - 已核对 `README.md`、`PROJECT_MEMORY.md`、`CHANGELOG.md`、`docs/WORKLOG.md`
  - 已核对 `main.py`、`modules/sqlite_store.py`、`modules/event_bus.py`
  - 已确认主演示链路当前仍以 JSONL 事件流为主，作为前端展示来源
  - 当前本地分支：`chore/sqlite-migration-regression-docs-v2`
  - 当前本地测试：`PYTHONPATH=. .venv/bin/pytest -q` -> `20 passed`
- 已开始把 SQLite 真正接入主 pipeline：
  - `enqueue_image()` 会写入 `tasks` queued
  - `_process_image()` 会写入 started / detections / weather / decision / completed|error
  - 现阶段仍保留 `FileEventBus` 作为前端实时展示来源
- 已补主流程写库测试：
  - `tests/test_main.py::test_main_pipeline_writes_sqlite_records`
- 已把前端读取层接到 SQLite：
  - `app.py` 会优先读取 SQLite 任务摘要
  - 再用 JSONL 事件流补当前阶段和实时日志
  - 侧边栏新增任务历史结构化检索
- 已补 SQLite 结构化读取测试：
  - `tests/test_sqlite_migration.py::test_sqlite_store_fetch_task_views_supports_structured_history_queries`
- 已把无人机状态流写进 SQLite：
  - 新增 `drone_mission_updates`
  - `DroneController` 模拟执行和远端状态轮询都会写入
  - 前端历史视图已可直接展示最新无人机结构化状态
- 已补无人机状态流写库测试：
  - `tests/test_drone_controller.py::test_drone_controller_persists_simulated_status_updates_to_sqlite`
- 已补农业数据层 schema scaffold：
  - `fields`
  - `crop_catalog`
  - `field_crop_cycles`
  - `soil_records`
  - `weather_history_daily`
  - `pesticide_catalog`
  - `spray_records`
- 已新增农业数据模型参考文档：
  - `docs/05-reference/data-model.md`
- 已补农业数据 schema 回归测试：
  - `tests/test_sqlite_migration.py::test_sqlite_store_creates_agriculture_data_schema_scaffold`
- 已补数据来源与统计指标层：
  - 新增 `data_sources`
  - 新增 `agri_statistical_indicators`
  - 新增河南参考数据 seed
  - 新增导入脚本 `scripts/import_henan_reference_data.py`
- 已补数据来源/统计指标写入测试：
  - `tests/test_sqlite_migration.py::test_sqlite_store_supports_source_and_indicator_upserts`
- 已补河南历史天气导入能力：
  - 新增 `weather_stations`
  - 新增 `scripts/import_henan_weather_history_csv.py`
  - 支持 CMA 日值 CSV 常见中文列名
- 已补河南历史天气导入测试：
  - `tests/test_sqlite_migration.py::test_import_henan_weather_history_csv_imports_stations_and_daily_rows`
- 已补河南地块/作物核心开发起点：
  - 新增 `models/agri_models.py`
  - 新增 `scripts/generate_henan_field_crop_seed_csv.py`
  - 生成 `crop_catalog.csv`、`fields.csv`、`field_crop_cycles.csv`
- 已补河南地块/作物 CSV 导入测试与主流程字段选择测试：
  - `tests/test_sqlite_migration.py::test_import_henan_field_crop_seed_csv_imports_and_resolves_runtime_context`
  - `tests/test_main.py::test_main_prefers_sqlite_field_context_over_static_config`
- 已补河南地块/作物 seed 测试：
  - `tests/test_henan_field_crop_seed_generation.py::test_generate_henan_field_crop_seed_csv_outputs_expected_files`
- 当前天气导入实际推进边界：
  - 用户暂时无法下载河南天气 CSV
  - 先暂停真实天气 CSV 入库
  - 后续一旦拿到文件，优先回到 `scripts/import_henan_weather_history_csv.py` 做实测导入
- 已完成本轮审查驱动修复收口：
  - `weather_history_daily` 不再因 `station_code + observation_date` 唯一性覆盖不同 `field_id` 的天气历史
  - 运行时地块解析改为显式选择，存在多块地时不再静默取数据库“第一块”
  - `fetch_field_context()` 天气定位优先使用地块经纬度，再回退到市/县
  - `mission_planner` 不再直接把地块围栏顶点当作航线，改为基础覆盖式往返路径
- 已补本轮修复对应回归测试：
  - `tests/test_main.py::test_main_rejects_ambiguous_field_context_without_explicit_selection`
  - `tests/test_sqlite_migration.py::test_sqlite_store_supports_multiple_field_weather_rows_for_same_station_day`
  - `tests/test_sqlite_migration.py::test_fetch_field_context_prefers_coordinates_for_weather_lookup`
  - `tests/test_mission_planner.py::test_mission_planner_generates_coverage_route_not_just_polygon_vertices`
- 当前本地测试：
  - `PYTHONPATH=/home/qingking/muye /home/qingking/muye/.venv/bin/pytest -q` -> `34 passed`

## User Intent Confirmed

当前优先事项已经从“先补工程记忆”切换为“先把 SQLite 发布线真正收口”：

1. SQLite 发布线已经收口
2. SQLite 读写、无人机状态流、农业 schema、河南参考 seed 和天气导入能力都已进入主链，下一步转入更细数据导入
3. 继续补 planner 与数据模型扩展

## Project-Level Memory Files

当前约定的三层记忆文件：

- `PROJECT_MEMORY.md`
  - 记录长期优先级、架构决策、已验证结论、下一步计划
- `CHANGELOG.md`
  - 记录版本级修改历史
- `docs/WORKLOG.md`
  - 记录这轮协作里做了什么、为什么做、下一轮从哪里接着做

## Next Handoff Point

下一轮如果继续推进，应优先做：

1. 先读：
   - `PROJECT_MEMORY.md`
   - `CHANGELOG.md`
   - `docs/WORKLOG.md`
2. 先确认是在当前本地分支继续推进，还是切回并同步 `main`。
3. 优先继续导入河南农业数据，再拆分：
   - 土壤数据
   - 农药目录
   - 喷洒记录
4. 再评估仿真平台接入路线

## Notes

- GitHub 当前已完成：
  - PR #1 merged
  - PR #2 merged
  - PR #3 merged
  - `v1.1.1` release created
- 今天登录过 GitHub CLI 完成远端操作。
