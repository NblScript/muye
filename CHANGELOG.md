# Changelog

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
