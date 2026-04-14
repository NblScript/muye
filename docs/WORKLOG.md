# Worklog

## Current Session Summary

本轮已经完成：

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

## User Intent Confirmed

当前优先事项已经从“先补工程记忆”切换为“先把 SQLite 发布线真正收口”：

1. SQLite 发布线已经收口
2. 下一步转入 planner 与数据模型扩展
3. 继续补结构化查询与后续工程化能力

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
2. 先把本地 `main` 同步到最新远端状态。
3. 再拆分：
   - LLM 决策层
   - 系统规划层
4. 再评估仿真平台接入路线

## Notes

- GitHub 当前已完成：
  - PR #1 merged
  - PR #2 merged
  - PR #3 merged
  - `v1.1.1` release created
- 今天登录过 GitHub CLI 完成远端操作。
