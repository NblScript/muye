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
- 旧库迁移回归测试已补齐并通过：
  - `PYTHONPATH=. .venv/bin/pytest -q tests/test_sqlite_migration.py`
  - 结果：`1 passed`
- SQLite 相关回归已通过：
  - `PYTHONPATH=. .venv/bin/pytest -q tests/test_main.py tests/test_sqlite_migration.py`
  - 结果：`4 passed`
- 相关测试集合已通过：
  - `PYTHONPATH=. .venv/bin/pytest -q tests/test_ai_decision.py tests/test_event_bus.py tests/test_image_processor.py tests/test_local_yolo_api.py tests/test_main.py tests/test_virtual_drone_api.py tests/test_weather_integration.py tests/test_sqlite_migration.py`
  - 结果：`20 passed`
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
- 在现有 SQLite 基础上继续扩展：
  - 无人机状态流
  - 历史农业数据
  - 面向前端查询的结构化读取接口
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
