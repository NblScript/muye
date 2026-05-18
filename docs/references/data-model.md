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

## SQLAlchemy 模型（存储层）

定义在 `models/agri_models.py`：

### CropCatalog

作物目录，存储支持的作物类型信息。

### FieldCropStatus

农田作物状态，记录当前种植情况。

## 详细 Schema

完整的 SQLite 表结构参见 [数据库 Schema](../generated/db-schema.md)。
