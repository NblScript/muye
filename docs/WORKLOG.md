# Worklog

## Current Session Summary

本轮已经完成：

- 识别并熟悉了 `muye` 项目的核心架构：
  - 图片采集
  - YOLO 识别
  - 天气获取
  - 千问决策
  - 虚拟无人机执行
  - Streamlit 演示前端
- 实际验证了完整链路可运行：
  - `PYTHONPATH=. .venv/bin/pytest -q` 通过
  - 样例图 `IP000000042.jpg` 能跑通完整流程
- 新增了一键启动脚本：
  - `scripts/start_demo.sh`
- 更新了 README，补齐启动方式和测试命令
- 创建并推送了版本：
  - `v0.3-initial`

## User Intent Confirmed

当前优先事项不是继续扩展业务功能，而是先解决协作记忆问题：

1. 项目要有持久记忆
2. 项目要有修改日志
3. 新开会话时，应该能通过项目内文档快速恢复上下文

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
2. 直接从已确认的 SQLite 起步 schema 开始落地
   - `tasks`
   - `detections`
   - `weather_snapshots`
   - `decisions`
3. 再拆分：
   - LLM 决策层
   - 系统规划层
4. 再评估仿真平台接入路线

## Notes

- 用户明确提出：
  - SQLite 应该作为结构化业务存储
  - 历史农业数据要补齐
  - 分析结果应该入库
  - 无人机路径/高度/喷洒速率/气象限制不应主要由 LLM 推理
- SQLite 起步表结构已经写入 `PROJECT_MEMORY.md`
- SQLite 标准 SQL 建表草案已经写入 `PROJECT_MEMORY.md`
- 这些方向已经确认，但当前还没有开始正式代码改造。
