# 数据库 Schema

> 从源码 `models/` 目录提取。本文件为自动生成参考，以代码为准。

## 概述

- **数据库**：SQLite
- **路径**：`data/muye.db`（可通过 `MUYE_DB_PATH` 环境变量覆盖）
- **模式**：WAL（Write-Ahead Logging）

## 表分类

### 1. 演示管线运行时表

#### tasks

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 任务 ID |
| request_id | TEXT | NOT NULL, INDEX | 请求唯一标识 |
| status | TEXT | CHECK(pending/processing/completed/failed) | 任务状态 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | | 更新时间 |

#### detections

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 检测记录 ID |
| request_id | TEXT | INDEX | 关联请求 |
| pest_type | TEXT | | 害虫类型 |
| confidence | REAL | | 置信度 |
| bbox_x, bbox_y, bbox_w, bbox_h | REAL | | 边界框 |
| image_path | TEXT | | 标注图片路径 |

#### weather_snapshots

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 快照 ID |
| request_id | TEXT | INDEX | 关联请求 |
| temperature | REAL | | 温度 |
| humidity | REAL | | 湿度 |
| wind_speed | REAL | | 风速 |
| weather_desc | TEXT | | 天气描述 |
| captured_at | TIMESTAMP | | 采集时间 |

#### decisions

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 决策 ID |
| request_id | TEXT | INDEX | 关联请求 |
| pesticide_name | TEXT | | 推荐农药 |
| dosage | TEXT | | 用量 |
| reason | TEXT | | 决策理由 |
| rag_context | TEXT | | RAG 检索上下文 |
| created_at | TIMESTAMP | | 创建时间 |

#### drone_mission_updates

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 更新 ID |
| request_id | TEXT | INDEX | 关联请求 |
| status | TEXT | | 任务状态 |
| latitude | REAL | | 纬度 |
| longitude | REAL | | 经度 |
| altitude | REAL | | 高度 |
| progress | REAL | | 进度百分比 |
| updated_at | TIMESTAMP | | 更新时间 |

### 2. 农业基础/参考表

#### fields

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 农田 ID |
| name | TEXT | 农田名称 |
| area_mu | REAL | 面积（亩） |
| latitude | REAL | 中心纬度 |
| longitude | REAL | 中心经度 |
| soil_type | TEXT | 土壤类型 |

#### crop_catalog

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 作物 ID |
| name | TEXT | 作物名称 |
| variety | TEXT | 品种 |
| planting_season | TEXT | 种植季节 |
| growth_days | INTEGER | 生长周期（天） |

#### pesticide_catalog

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 农药 ID |
| name | TEXT | 农药名称 |
| target_pest | TEXT | 目标害虫 |
| dosage_per_mu | REAL | 每亩用量 |
| safety_interval | INTEGER | 安全间隔期（天） |

#### soil_records

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 记录 ID |
| field_id | INTEGER FK | 关联农田 |
| ph | REAL | pH 值 |
| organic_matter | REAL | 有机质含量 |
| nitrogen | REAL | 氮含量 |
| phosphorus | REAL | 磷含量 |
| potassium | REAL | 钾含量 |
| recorded_at | TIMESTAMP | 记录时间 |

### 3. 数据溯源表

#### data_sources

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 来源 ID |
| name | TEXT | 来源名称 |
| type | TEXT | 类型（csv/api/manual） |
| description | TEXT | 描述 |
| imported_at | TIMESTAMP | 导入时间 |

## 种子数据

河南演示数据位于 `data/seeds/henan/`：
- `fields.csv` — 演示农田
- `crop_catalog.csv` — 作物目录
- `field_crop_cycles.csv` — 种植周期
- `pesticide_catalog.json` — 农药目录
- `soil_records.csv` — 土壤记录

导入命令：
```bash
python scripts/import_henan_field_crop_seed_csv.py
python scripts/import_henan_soil_records_csv.py
python scripts/import_henan_reference_data.py
```
