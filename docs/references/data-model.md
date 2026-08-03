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

YOLO 检测项统一为 `pest_type / confidence / position`。`position` 接受两种明确坐标空间：

- `coordinate_space: "image_pixel"`：`x1/y1/x2/y2` 为原图像素坐标，必须同时提供正数 `image_width`、`image_height`。
- `coordinate_space: "image_normalized"`：检测框坐标已经归一化到 0–1。

本地 Ultralytics 适配器输出 `box.xyxy`，因此写入像素坐标和 `result.orig_shape`。官方定义可参见 [Ultralytics Predict 文档](https://docs.ultralytics.com/modes/predict/)；像素框缺少图像尺寸时会被密度计算拒绝，而不是默认塞入某个边缘网格。

变量喷洒指令中的 `density_grid[].density` 表示网格内 YOLO 置信度权重相对于本次任务最大网格权重的比例（0–1）。它用于本项目的相对热区展示与分档变率喷洒，不等同于每亩虫口密度、经济阈值或绝对发生量。

`density_metadata` 记录 `source`、`density_kind`、`projection`、`normalization`、网格尺寸、检测框接收/拒绝数量和 `is_simulated`。当前 `image_frame_to_geofence_bbox` 投影假定图像覆盖整块田地且图像顶部对应北侧；如需绝对地理定位，应提供正射影像地理变换或逐帧相机位姿。

## SQLAlchemy 模型（存储层）

定义在 `models/agri_models.py`：

### CropCatalog

作物目录，存储支持的作物类型信息。

### FieldCropStatus

农田作物状态，记录当前种植情况。

## 详细 Schema

完整的 SQLite 表结构参见 [数据库 Schema](../generated/db-schema.md)。
