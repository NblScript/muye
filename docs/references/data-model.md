# 数据模型参考

> 牧野系统的数据模型定义。以代码 `models/` 目录为准。

## Pydantic 模型（API 层）

定义在 `models/schemas.py`：

### SimPoint

```python
class SimPoint(BaseModel):
    x: float
    y: float
```

### SimDroneState

```python
class SimDroneState(BaseModel):
    lat: float
    lng: float
    alt: float
    battery: float
    speed: float
    heading: float
```

### SimMapStateResponse

```python
class SimMapStateResponse(BaseModel):
    field: dict
    drone: SimDroneState
    trajectory: list[SimPoint]
    mission: dict
```

### WorkflowEventEntry

```python
class WorkflowEventEntry(BaseModel):
    request_id: str
    event_type: str
    source: str
    payload: dict
    timestamp: datetime
```

## 虫情检测与密度网格约定

当前产品使用一个活动田地。SQLite 可以保存多个 `fields` 记录，但运行时若存在多个地块，必须通过 `MUYE_ACTIVE_FIELD_ID` 明确选择；首页不做行政区或多田地聚合。

YOLO 检测项统一为 `pest_type / confidence / position`。`position` 接受两种明确坐标空间：

- `coordinate_space: "image_pixel"`：`x1/y1/x2/y2` 为原图像素坐标，必须同时提供正数 `image_width`、`image_height`。
- `coordinate_space: "image_normalized"`：检测框坐标已经归一化到 0–1。

本地 Ultralytics 适配器输出 `box.xyxy`，因此写入像素坐标和 `result.orig_shape`。官方定义可参见 [Ultralytics Predict 文档](https://docs.ultralytics.com/modes/predict/)；像素框缺少图像尺寸时会被密度计算拒绝，而不是默认塞入某个边缘网格。

变量喷洒指令中的 `density_grid[].density` 表示网格内 YOLO 置信度权重相对于本次任务最大网格权重的比例（0–1）。它用于本项目的相对热区展示与分档变率喷洒，不等同于每亩虫口密度、经济阈值或绝对发生量。

`density_metadata` 记录 `source`、`algorithm_version`、`density_kind`、`projection`、`normalization`、网格尺寸、检测框接收/拒绝数量和 `is_simulated`。真实检测当前使用 `relative-bbox-grid-v1`，固定演示面使用 `demo-synthetic-surface-v1`。当前 `image_frame_to_geofence_bbox` 投影假定图像覆盖整块田地且图像顶部对应北侧；如需绝对地理定位，应提供正射影像地理变换或逐帧相机位姿。

默认密度网格为 8×10。变量喷洒按航线对应网格行的最大相对热值分档：`>= 0.6` 使用基础速率 1.5 倍，`>= 0.3` 使用基础速率，低于 `0.3` 使用基础速率 0.5 倍，最终仍受飞行配置中的喷洒速率范围约束。

### 巡检与热力快照持久化

Phase 1 已增加三张独立表：

- `inspection_batches`：保存 `request_id`、`field_id`、采集时间、图片引用、来源、模拟标记、任务和轮次。
- `inspection_detections`：保存批次内逐图检测项、昆虫类别、置信度和完整检测框。
- `heatmap_snapshots`：保存完整 `density_grid`、`density_metadata`、算法版本、分类计数和总检测数。

首次 YOLO 结果会立即写入 `pre_spray` 快照；即使未发现昆虫或地块围栏无效，也会保存空网格或明确的 `unavailable` 元数据。复检结果写入 `reinspection` 快照，并关联 `mission_id` 与 `iteration_number`。旧任务仍可从 `drone_mission_updates.instruction` 只读转换为 `legacy-unversioned` 快照，不会回写或伪造新记录。

Phase 2 已提供最新快照、组合筛选列表、详情和喷洒前后配对 HTTP API。列表只枚举独立持久化快照；旧任务可以使用 `legacy:{request_id}` 详情 ID 触发只读转换，但不会伪装成新持久化记录。Phase 3 已完成跨任务趋势与筛选；Phase 4 在 `mission_iterations` 中保存每轮消费的 `heatmap_snapshot_id`、算法版本和 `spray_plan`，复检快照可作为下一轮变量喷洒输入。页面仍不得把独立归一化快照宣称为绝对虫口密度同比。实施顺序见 [昆虫热力图产品化执行计划](../exec-plans/2026-08-04-insect-heatmap-productization.md)。

## SQLAlchemy 模型（存储层）

定义在 `models/agri_models.py`：

### CropCatalog

作物目录，存储支持的作物类型信息。

### FieldCropStatus

农田作物状态，记录当前种植情况。

## 详细 Schema

完整的 SQLite 表结构参见 [数据库 Schema](../generated/db-schema.md)。
