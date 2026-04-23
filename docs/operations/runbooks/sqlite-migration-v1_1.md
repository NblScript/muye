# SQLite Migration v1.1.1

## 适用范围

适用于从旧版 SQLite 结构升级到包含以下约束与索引的版本：

- `tasks.status` CHECK 约束：
  - `queued`
  - `running`
  - `completed`
  - `error`
- `detections.request_id` 索引
- `weather_snapshots.request_id` 索引
- `decisions.request_id` 索引

## 风险提示

- 迁移前建议先备份数据库文件。
- 旧库中不合法的 `tasks.status` 会被规范化为 `error`。
- 当前迁移只处理 v1.1.1 已知结构，不替代完整的长期数据治理。

## 自动迁移

从 `v1.1.1` 开始，应用启动时会自动执行 v1.1 迁移逻辑。

默认数据库路径：

- `data/muye.db`

也可以通过环境变量覆盖：

- `MUYE_DB_PATH=/path/to/your.db`

## 手动迁移

方式一：

```bash
cd /home/qingking/muye
MUYE_DB_PATH=data/muye.db python -m scripts.migrate_to_v1_1
```

方式二：

```bash
cd /home/qingking/muye
python scripts/migrate_to_v1_1.py --db data/muye.db
```

## 验证方式

建议迁移后至少验证以下几点：

1. 应用能正常启动
2. `tasks.status` 非法值已被规范化为 `error`
3. `detections / weather_snapshots / decisions` 上已存在 `request_id` 索引
4. 原有任务和子表数据未丢失

## 回归测试

仓库内已有针对“旧库升级”的回归测试：

- `tests/test_sqlite_migration.py`

运行方式：

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/pytest -q tests/test_sqlite_migration.py
```
