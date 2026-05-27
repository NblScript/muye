# 数据库 Schema

> 从源码 `modules/infra/sqlite_store/base.py` 提取。本文件为自动生成参考，以代码为准。

## 概述

- **数据库**：SQLite
- **路径**：`data/muye.db`（可通过 `MUYE_DB_PATH` 环境变量覆盖）
- **模式**：WAL（Write-Ahead Logging）
- **表数量**：20
- **SqliteStore 类**：通过 Mixin 组合（MissionMixin → EvaluationMixin → CatalogMixin → AgriDataMixin → FieldMixin → TaskMixin → BaseMixin）

## 表分类

### 1. 演示管线运行时表

#### tasks

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| request_id | TEXT | PK | 请求唯一标识 |
| field_id | TEXT | | 关联地块 ID |
| image_path | TEXT | | 输入图片路径 |
| start_time | DATETIME | | 任务开始时间 |
| end_time | DATETIME | | 任务结束时间 |
| status | TEXT | CHECK(queued/running/completed/blocked/error) | 任务状态 |

#### detections

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| request_id | TEXT | FK → tasks, INDEX | 关联请求 |
| label | TEXT | | 检测标签 |
| confidence | REAL | | 置信度 |
| bbox | TEXT | JSON | 边界框坐标 |

#### weather_snapshots

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| request_id | TEXT | FK → tasks, INDEX | 关联请求 |
| timestamp | DATETIME | | 采集时间 |
| weather_data | TEXT | JSON | 天气数据（温度/湿度/风速等） |

#### decisions

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| request_id | TEXT | FK → tasks, INDEX | 关联请求 |
| timestamp | DATETIME | | 决策时间 |
| decision_text | TEXT | JSON | 决策结果（用药/农事建议等） |

#### drone_mission_updates

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| request_id | TEXT | FK → tasks, INDEX | 关联请求 |
| timestamp | DATETIME | | 更新时间 |
| task_id | TEXT | | 无人机任务 ID |
| status | TEXT | | 任务状态 |
| message | TEXT | | 状态消息 |
| progress | INTEGER | | 进度百分比 |
| current_waypoint_index | INTEGER | | 当前航点索引 |
| instruction | TEXT | JSON | 飞行指令（含 density_grid、spray_schedule 等） |
| medication | TEXT | JSON | 用药信息 |

#### pending_actions

跨进程人工确认动作（起飞确认）。

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| request_id | TEXT | NOT NULL, UNIQUE(request_id, action_type) | 关联请求 |
| action_type | TEXT | NOT NULL | 动作类型（如 takeoff_confirmation） |
| status | TEXT | CHECK(pending/confirmed/expired/cancelled) | 动作状态 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| confirmed_at | DATETIME | | 确认时间 |
| expires_at | DATETIME | | 过期时间 |

#### task_evaluations

喷洒后效果评估闭环。决策完成时创建，等待药效期后自动复检评估。

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| original_request_id | TEXT | FK → tasks, INDEX | 原始喷洒请求 |
| reinspect_request_id | TEXT | FK → tasks | 复检请求 |
| status | TEXT | CHECK(scheduled/inspecting/evaluated/retry_scheduled/passed/cancelled) | 评估状态 |
| scheduled_at | DATETIME | NOT NULL | 评估创建时间 |
| inspected_at | DATETIME | | 复检执行时间 |
| evaluated_at | DATETIME | | 评估完成时间 |
| pre_pest_count | INTEGER | | 喷洒前害虫数量 |
| post_pest_count | INTEGER | | 复检时害虫数量 |
| kill_rate | REAL | | 杀灭率 |
| kill_rate_threshold | REAL | DEFAULT 0.7 | 杀灭率达标阈值 |
| action_time_hours | REAL | | 药效等待时间 |
| retry_request_id | TEXT | FK → tasks | 重试请求 ID |
| retry_count | INTEGER | DEFAULT 0 | 重试次数 |
| notes | TEXT | | 备注 |

#### missions

任务闭环主表。每次检测→决策→喷洒→复检流程创建一条，支持多轮迭代直到杀灭率达标。

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| mission_id | TEXT | UNIQUE | 任务闭环唯一标识（UUID） |
| original_request_id | TEXT | INDEX | 触发该闭环的原始请求 |
| field_id | TEXT | | 关联地块 |
| status | TEXT | CHECK(active/completed/failed/cancelled) | 闭环状态 |
| kill_rate_threshold | REAL | DEFAULT 0.9 | 杀灭率达标阈值 |
| max_iterations | INTEGER | DEFAULT 3 | 最大迭代次数 |
| current_iteration | INTEGER | DEFAULT 0 | 当前迭代轮次 |
| final_kill_rate | REAL | | 最终杀灭率 |
| total_pre_pest_count | INTEGER | | 喷洒前害虫总数 |
| total_post_pest_count | INTEGER | | 复检后害虫总数 |
| pest_types | TEXT | | 检测到的害虫类型列表 |
| pesticide_name | TEXT | | 使用的农药名称 |
| crop_name | TEXT | | 作物名称 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| completed_at | DATETIME | | 完成时间 |
| notes | TEXT | | 备注 |

#### mission_iterations

任务闭环迭代明细。每轮喷洒→复检→评估对应一条记录。

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| mission_id | TEXT | NOT NULL, UNIQUE(mission_id, iteration_number) | 关联任务闭环 |
| iteration_number | INTEGER | NOT NULL | 迭代号（从 1 开始） |
| spray_request_id | TEXT | | 本轮喷洒请求 ID |
| evaluation_id | INTEGER | | 关联效果评估记录 |
| status | TEXT | CHECK(pending/spraying/inspecting/evaluated/passed/failed) | 迭代状态 |
| pre_pest_count | INTEGER | | 本轮喷洒前害虫数量 |
| post_pest_count | INTEGER | | 本轮复检时害虫数量 |
| kill_rate | REAL | | 本轮杀灭率 |
| captured_images | TEXT | | 复检拍摄的图片路径列表 |
| created_at | DATETIME | NOT NULL | 迭代创建时间 |
| spray_completed_at | DATETIME | | 喷洒完成时间 |
| inspected_at | DATETIME | | 复检执行时间 |
| evaluated_at | DATETIME | | 评估完成时间 |
| notes | TEXT | | 备注 |

### 2. 农业基础/参考表

#### fields

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| field_id | TEXT | PK | 地块唯一标识 |
| field_code | TEXT | UNIQUE | 地块编码 |
| field_name | TEXT | NOT NULL | 地块名称 |
| owner_user_id | TEXT | | 所有者用户 ID |
| province | TEXT | | 省份 |
| city | TEXT | INDEX(city, county) | 城市 |
| county | TEXT | | 区县 |
| township | TEXT | | 乡镇 |
| village | TEXT | | 村 |
| latitude | REAL | | 中心纬度 |
| longitude | REAL | | 中心经度 |
| area_mu | REAL | | 面积（亩） |
| area_hectare | REAL | | 面积（公顷） |
| geofence | TEXT | | 地块围栏坐标（JSON） |
| soil_type | TEXT | | 土壤类型 |
| irrigation_type | TEXT | | 灌溉方式 |
| source | TEXT | | 数据来源 |
| notes | TEXT | | 备注 |
| created_at | DATETIME | | 创建时间 |
| updated_at | DATETIME | | 更新时间 |

#### crop_catalog

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| crop_code | TEXT | PK | 作物编码 |
| crop_name | TEXT | NOT NULL | 作物名称 |
| category | TEXT | | 分类（粮食/油料/蔬菜/果树/其他） |
| variety | TEXT | | 品种 |
| growth_cycle_days | INTEGER | | 生长周期（天） |
| water_demand_coefficient | REAL | | 需水系数 |
| typical_planting_month | TEXT | | 典型种植月份 |
| typical_harvest_month | TEXT | | 典型收获月份 |
| source | TEXT | | 数据来源 |
| notes | TEXT | | 备注 |

#### field_crop_cycles

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| field_id | TEXT | FK → fields, INDEX | 关联地块 |
| crop_code | TEXT | FK → crop_catalog, INDEX | 关联作物 |
| year | INTEGER | | 种植年份 |
| season | TEXT | | 种植季节 |
| planting_date | DATE | | 播种日期 |
| harvest_date | DATE | | 收获日期 |
| area_mu | REAL | | 种植面积（亩） |
| expected_yield_kg | REAL | | 预期产量（公斤） |
| actual_yield_kg | REAL | | 实际产量（公斤） |
| status | TEXT | CHECK(planned/planted/growing/harvested/cancelled) | 生长状态 |
| source | TEXT | | 数据来源 |
| notes | TEXT | | 备注 |

#### pesticide_catalog

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| pesticide_id | TEXT | PK | 农药 ID |
| registration_no | TEXT | UNIQUE | 登记证号 |
| product_name | TEXT | NOT NULL | 产品名称 |
| active_ingredient | TEXT | | 有效成分 |
| formulation | TEXT | | 剂型 |
| toxicity | TEXT | | 毒性等级 |
| manufacturer | TEXT | | 生产厂家 |
| target_crops | TEXT | | 适用作物 |
| target_pests | TEXT | | 防治对象 |
| dilution_guidance | TEXT | | 稀释指导 |
| source | TEXT | | 数据来源 |
| raw_payload | TEXT | | 原始数据 |

#### soil_records

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| field_id | TEXT | FK → fields, INDEX(field_id, sample_date) | 关联地块 |
| sample_date | DATE | | 采样日期 |
| depth_cm | INTEGER | | 采样深度（cm） |
| ph | REAL | | pH 值 |
| organic_matter_gkg | REAL | | 有机质（g/kg） |
| alkali_hydrolyzable_nitrogen_mgkg | REAL | | 碱解氮（mg/kg） |
| available_phosphorus_mgkg | REAL | | 有效磷（mg/kg） |
| available_potassium_mgkg | REAL | | 速效钾（mg/kg） |
| moisture_percent | REAL | | 含水率（%） |
| salinity_gkg | REAL | | 盐分（g/kg） |
| texture | TEXT | | 质地 |
| source | TEXT | | 数据来源 |
| raw_payload | TEXT | | 原始数据 |

### 3. 气象数据表

#### weather_stations

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| station_code | TEXT | PK | 气象站编码 |
| station_name | TEXT | NOT NULL | 气象站名称 |
| province | TEXT | INDEX(city, county) | 省份 |
| city | TEXT | | 城市 |
| county | TEXT | | 区县 |
| latitude | REAL | | 纬度 |
| longitude | REAL | | 经度 |
| elevation_m | REAL | | 海拔（米） |
| source_id | TEXT | FK → data_sources | 数据来源 |
| notes | TEXT | | 备注 |

#### weather_history_daily

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| field_id | TEXT | FK → fields, INDEX(field_id, observation_date) | 关联地块 |
| station_code | TEXT | INDEX(station_code, observation_date) | 气象站编码 |
| station_name | TEXT | | 气象站名称 |
| observation_date | DATE | NOT NULL | 观测日期 |
| weather_summary | TEXT | | 天气概况 |
| temperature_avg_c | REAL | | 平均温度（℃） |
| temperature_min_c | REAL | | 最低温度（℃） |
| temperature_max_c | REAL | | 最高温度（℃） |
| humidity_avg_percent | REAL | | 平均湿度（%） |
| precipitation_mm | REAL | | 降水量（mm） |
| wind_speed_avg_mps | REAL | | 平均风速（m/s） |
| wind_direction | TEXT | | 风向 |
| sunshine_hours | REAL | | 日照时数 |
| source | TEXT | | 数据来源 |
| raw_payload | TEXT | | 原始数据 |

### 4. 喷洒记录表

#### spray_records

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| request_id | TEXT | FK → tasks, INDEX | 关联请求 |
| field_id | TEXT | FK → fields, INDEX(field_id, spray_date) | 关联地块 |
| crop_cycle_id | INTEGER | FK → field_crop_cycles, INDEX | 关联种植周期 |
| drone_task_id | TEXT | | 无人机任务 ID |
| pesticide_id | TEXT | FK → pesticide_catalog | 关联农药 |
| spray_date | DATETIME | NOT NULL | 喷洒时间 |
| operator_name | TEXT | | 操作员 |
| spray_area_mu | REAL | | 喷洒面积（亩） |
| dosage_per_mu | REAL | | 亩用量 |
| total_dosage | REAL | | 总用量 |
| dilution_ratio | TEXT | | 稀释倍数 |
| spray_rate_lpm | REAL | | 喷洒速率（L/min） |
| flight_height_m | REAL | | 飞行高度（m） |
| flight_speed_mps | REAL | | 飞行速度（m/s） |
| weather_snapshot | TEXT | JSON | 喷洒时天气快照 |
| result_status | TEXT | CHECK(planned/in_progress/completed/failed/cancelled) | 喷洒结果状态 |
| source | TEXT | | 数据来源 |
| notes | TEXT | | 备注 |

### 5. 数据溯源表

#### data_sources

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| source_id | TEXT | PK | 来源 ID |
| source_name | TEXT | NOT NULL | 来源名称 |
| publisher | TEXT | | 发布机构 |
| region_scope | TEXT | | 区域范围 |
| source_type | TEXT | | 类型（csv/api/manual） |
| source_url | TEXT | NOT NULL | 数据 URL |
| access_level | TEXT | | 访问级别 |
| retrieval_date | DATE | | 获取日期 |
| license | TEXT | | 许可协议 |
| notes | TEXT | | 备注 |

#### agri_statistical_indicators

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录 ID |
| region_level | TEXT | NOT NULL | 区域层级 |
| region_name | TEXT | NOT NULL | 区域名称 |
| province | TEXT | INDEX(province, city, county, year) | 省份 |
| city | TEXT | | 城市 |
| county | TEXT | | 区县 |
| year | INTEGER | NOT NULL | 年份 |
| period | TEXT | NOT NULL | 统计周期 |
| indicator_code | TEXT | NOT NULL, INDEX | 指标编码 |
| indicator_name | TEXT | NOT NULL | 指标名称 |
| value | REAL | NOT NULL | 指标值 |
| unit | TEXT | | 单位 |
| source_id | TEXT | FK → data_sources | 数据来源 |
| source_excerpt | TEXT | | 来源摘要 |
| raw_payload | TEXT | | 原始数据 |

UNIQUE(region_level, region_name, province, city, county, year, period, indicator_code)

## 种子数据

河南演示数据导入命令：
```bash
python scripts/import_henan_field_crop_seed_csv.py
python scripts/import_henan_soil_records_csv.py
python scripts/import_henan_reference_data.py
python scripts/import_henan_weather_history_csv.py
```
