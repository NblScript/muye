# SQLite Migration Regression

本测试用于验证“旧版数据库 -> v1.1.1 结构”的迁移路径是否稳定。

## 覆盖目标

- 旧版 `tasks` 表无 CHECK 约束
- 子表无 `request_id` 索引
- 旧数据在迁移后仍保留
- 非法 `status` 会被规范化为 `error`

## 对应用例

- `tests/test_sqlite_migration.py`

## 运行方式

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/pytest -q tests/test_sqlite_migration.py
```

## 通过标准

- 测试通过
- `tasks` 表结构包含 CHECK 约束
- 子表存在 `request_id` 索引
- 原有记录未丢失
