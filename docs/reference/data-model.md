# SQLite Data Model

当前 `muye` 的 SQLite 数据层分为两部分：

1. 演示主链运行数据
2. 农业基础与历史数据
3. 数据来源与统计指标

## 1. 演示主链运行数据

这些表已经接入主流程，当前会持续写入：

- `tasks`
- `detections`
- `weather_snapshots`
- `decisions`
- `drone_mission_updates`

用途：

- 支撑当前前端展示
- 保存识别、决策、无人机状态历史
- 为后续任务追踪、回溯分析和报表扩展做底层存储

## 2. 农业基础与历史数据

这些表是本轮新增的“数据结构预留层”，先有 schema，后续再导入河南数据。

### `fields`

地块主数据。

关键字段：

- `field_id`
- `field_code`
- `field_name`
- `province`
- `city`
- `county`
- `township`
- `village`
- `latitude`
- `longitude`
- `area_mu`
- `area_hectare`
- `geofence`
- `soil_type`
- `irrigation_type`

用途：

- 绑定河南各地块基础信息
- 存放地理围栏和位置坐标
- 作为土壤、天气、喷洒记录的关联中心

### `crop_catalog`

作物字典表。

关键字段：

- `crop_code`
- `crop_name`
- `category`
- `variety`
- `growth_cycle_days`
- `typical_planting_month`
- `typical_harvest_month`

用途：

- 统一河南项目中的作物编码和名称
- 为地块种植季、农药适用范围、历史统计做标准化关联

### `field_crop_cycles`

地块种植季表。

关键字段：

- `field_id`
- `crop_code`
- `year`
- `season`
- `planting_date`
- `harvest_date`
- `area_mu`
- `expected_yield_kg`
- `actual_yield_kg`
- `status`

用途：

- 表达“某块地在某年某季种了什么”
- 为历史天气、土壤、喷洒记录提供种植上下文

### `soil_records`

土壤检测与采样记录。

关键字段：

- `field_id`
- `sample_date`
- `depth_cm`
- `ph`
- `organic_matter_gkg`
- `alkali_hydrolyzable_nitrogen_mgkg`
- `available_phosphorus_mgkg`
- `available_potassium_mgkg`
- `moisture_percent`
- `salinity_gkg`
- `texture`

用途：

- 保存土壤化验结果
- 为后续病虫害、施药和作物规划提供基础输入

### `weather_history_daily`

历史天气日表。

关键字段：

- `field_id`
- `station_code`
- `station_name`
- `observation_date`
- `weather_summary`
- `temperature_avg_c`
- `temperature_min_c`
- `temperature_max_c`
- `humidity_avg_percent`
- `precipitation_mm`
- `wind_speed_avg_mps`
- `wind_direction`
- `sunshine_hours`

用途：

- 接河南历史天气数据
- 支撑“天气回看”“历史分析”“地块风险趋势”

### `weather_stations`

气象站维表。

关键字段：

- `station_code`
- `station_name`
- `province`
- `city`
- `county`
- `latitude`
- `longitude`
- `elevation_m`
- `source_id`

用途：

- 记录河南历史天气导入所依赖的站点元数据
- 给 `weather_history_daily` 提供站点维度和位置说明
- 方便后续把地块与最近气象站做映射

### `pesticide_catalog`

农药字典表。

关键字段：

- `pesticide_id`
- `registration_no`
- `product_name`
- `active_ingredient`
- `formulation`
- `toxicity`
- `manufacturer`
- `target_crops`
- `target_pests`
- `dilution_guidance`

用途：

- 存放中国农药信息网等来源的规范化农药信息
- 后续给喷洒记录、决策建议、适药校验使用

### `spray_records`

喷洒作业记录表。

关键字段：

- `request_id`
- `field_id`
- `crop_cycle_id`
- `drone_task_id`
- `pesticide_id`
- `spray_date`
- `operator_name`
- `spray_area_mu`
- `dosage_per_mu`
- `total_dosage`
- `dilution_ratio`
- `spray_rate_lpm`
- `flight_height_m`
- `flight_speed_mps`
- `weather_snapshot`
- `result_status`

用途：

- 保存真实或模拟喷洒历史
- 后续可用于农药使用记录、复盘和合规统计

## 3. 数据来源与统计指标

### `data_sources`

数据来源注册表。

关键字段：

- `source_id`
- `source_name`
- `publisher`
- `region_scope`
- `source_type`
- `source_url`
- `access_level`
- `retrieval_date`

用途：

- 给河南数据导入保留统一来源登记
- 明确每类数据来自哪个官方入口
- 支持后续做来源追踪、更新和人工核验

### `agri_statistical_indicators`

农业统计指标表。

关键字段：

- `region_level`
- `region_name`
- `province`
- `city`
- `county`
- `year`
- `period`
- `indicator_code`
- `indicator_name`
- `value`
- `unit`
- `source_id`
- `source_excerpt`

用途：

- 保存河南省公开统计公报、农业普查等结构化指标
- 先落“可公开获取的官方统计”，再逐步补更细粒度业务数据
- 让数据不仅有值，还有可追溯来源

## 河南参考数据 seed

当前仓库已经加入第一批河南参考数据 seed：

- [sources.json](/home/qingking/muye/data/seeds/henan/sources.json)
- [agri_statistical_indicators.json](/home/qingking/muye/data/seeds/henan/agri_statistical_indicators.json)

对应导入脚本：

- [import_henan_reference_data.py](/home/qingking/muye/scripts/import_henan_reference_data.py)
- [import_henan_weather_history_csv.py](/home/qingking/muye/scripts/import_henan_weather_history_csv.py)

运行方式：

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/python scripts/import_henan_reference_data.py
```

河南历史天气 CSV 导入方式：

```bash
cd /home/qingking/muye
PYTHONPATH=. .venv/bin/python scripts/import_henan_weather_history_csv.py /path/to/henan_weather.csv
```

该脚本当前支持 CMA 日值 CSV 的常见中文列名，例如：

- `站号`
- `站名`
- `日期`
- `平均气温`
- `最低气温`
- `最高气温`
- `平均相对湿度`
- `降水量`
- `平均风速`
- `风向`
- `日照时数`
- `天气概况`

## 当前设计原则

- 先把表结构稳定下来，再导数据
- 当前以河南数据为首批目标，但 schema 不把自己写死成“只能河南”
- 保留 `source` / `raw_payload` / `notes` 这类字段，方便后续接不同来源的数据
- 不把历史农业数据强行塞进 `tasks` 这类演示表，避免运行数据和业务底库混杂

## 下一步建议

推荐导入顺序：

1. `data_sources`
2. `agri_statistical_indicators`
3. `weather_stations`
4. `weather_history_daily`
5. `fields`
6. `crop_catalog`
7. `field_crop_cycles`
8. `pesticide_catalog`
9. `soil_records`
10. `spray_records`
