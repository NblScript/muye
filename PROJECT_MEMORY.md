# Project Memory

## Current Priority

1. 先补工程记忆与修改日志，避免后续协作时丢失上下文。
2. 再逐步把业务数据迁移到 SQLite，而不是继续只依赖 JSONL 和配置文件。
3. 无人机路径、高度、喷洒速率、气象限制应由系统规则和规划器处理，不应主要依赖 LLM 推理。
4. 仿真平台后续需要评估更专业的路线，重点候选是 PX4/Gazebo，以及按需评估 AirSim。

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
- 开发协作层面必须维护：
  - `PROJECT_MEMORY.md`
  - `CHANGELOG.md`

## Last Verified State

- `PYTHONPATH=. .venv/bin/pytest -q` 通过。
- `./scripts/start_demo.sh --sample-image IP000000042.jpg` 已验证：
  - 前端可访问
  - YOLO 可识别目标
  - 天气接口可用
  - 千问可生成决策
  - 虚拟无人机任务能走到 completed
  - pipeline 最终 completed

## Next Work

- 设计 SQLite schema，至少覆盖：
  - 地块
  - 作物周期
  - 图片与检测结果
  - 天气历史
  - 决策结果
  - 喷洒任务记录
  - 无人机状态流
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
