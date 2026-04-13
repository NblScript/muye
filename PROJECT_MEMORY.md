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
- SQLite 采用“混合存储”策略：
  - 保留现有 JSONL 事件流，作为原始日志与调试信息
  - 新增 SQLite，作为结构化业务存储和前端查询来源
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
```

### Notes

- 这是当前确认的起步版 schema，用于先把结构化数据落库。
- 下一轮真正接入 SQLite 时，应先从 `tasks` 主表开始。
- 后续很可能继续扩展：
  - 无人机状态流
  - 历史农业数据
  - 更细的结构化字段
  但这些扩展暂未开始实施。

## Next Work

- 按当前已确认的 draft schema 接入 SQLite：
  - 先建 `tasks`
  - 再接 `detections`
  - 再接 `weather_snapshots`
  - 再接 `decisions`
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
