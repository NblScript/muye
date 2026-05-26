# API 参考

> 牧野系统所有 HTTP API 端点。基础路径：`http://localhost:18000`

## 健康检查

### GET /health

系统健康状态检查。

**响应**：
```json
{
  "status": "healthy",
  "timestamp": "2026-05-18T10:00:00Z"
}
```

## 检测模型管理

> 以下端点在 YOLO API 服务上（端口 8010）

### GET /models

列出可用检测模型及当前激活模型。

**响应**：
```json
{
  "active_model": "yolov8n",
  "models": [
    {
      "name": "yolov8n",
      "path": "models/best.pt",
      "device": "auto",
      "description": "YOLOv8 默认模型",
      "available": true,
      "active": true
    }
  ]
}
```

### POST /models/switch

切换检测模型（运行时热切换，无需重启）。

**请求**：
```json
{
  "model_name": "yolov8s"
}
```

**响应**：
```json
{
  "model_name": "yolov8s",
  "model_path": "/path/to/yolov8s.pt",
  "device": "auto",
  "description": "YOLOv8 小模型"
}
```

## 工作流

### GET /workflow/state

获取当前工作流状态。

**响应**：
```json
{
  "current_step": "detection",
  "steps": [
    {"name": "upload", "status": "completed"},
    {"name": "detection", "status": "in_progress"},
    {"name": "weather", "status": "pending"},
    {"name": "decision", "status": "pending"},
    {"name": "drone", "status": "pending"}
  ],
  "request_id": "req_abc123"
}
```

### GET /workflow/history

获取工作流历史记录。

**查询参数**：
- `limit` (int, 可选): 返回条数，默认 20

**响应**：
```json
{
  "history": [
    {
      "request_id": "req_abc123",
      "status": "completed",
      "started_at": "2026-05-18T10:00:00Z",
      "completed_at": "2026-05-18T10:05:00Z"
    }
  ]
}
```

## 仪表盘

### GET /dashboard/context

获取仪表盘上下文数据（天气、最新决策、任务统计）。

**响应**：
```json
{
  "weather": {"temperature": 25, "humidity": 60, "desc": "晴"},
  "latest_decision": {"pesticide": "吡虫啉", "dosage": "10ml/亩"},
  "stats": {"total_tasks": 5, "completed": 4, "failed": 1}
}
```

## 演示

### POST /demo/upload-image

上传害虫图片触发检测流程。

**请求**：`multipart/form-data`
- `file`: 图片文件（.jpg, .png, .bmp，< 10MB）

**响应**：
```json
{
  "request_id": "req_abc123",
  "status": "processing"
}
```

### POST /demo/reset-events

重置事件流（清空 `data/logs/demo_events.jsonl`）。

**响应**：
```json
{
  "status": "reset",
  "message": "Events cleared"
}
```

## 任务

### GET /tasks/{request_id}

获取指定任务详情。

**响应**：
```json
{
  "request_id": "req_abc123",
  "status": "completed",
  "detections": [...],
  "weather": {...},
  "decision": {...},
  "drone_mission": {...}
}
```

### GET /tasks/{request_id}/original-image

获取原始上传图片。

### GET /tasks/{request_id}/annotated-image

获取 YOLO 标注后的图片。

## 仿真

### GET /sim/map-state

获取仿真地图状态（农田、无人机位置、轨迹）。

**响应**：
```json
{
  "field": {"points": [...]},
  "drone": {"lat": 47.397, "lng": 8.545, "alt": 5, "battery": 85},
  "trajectory": [{"lat": 47.397, "lng": 8.545}],
  "mission": {"status": "in_progress", "progress": 0.6}
}
```

### WebSocket /sim/ws/map-state

实时仿真地图状态推送。

### WebSocket /api/ws/enhanced-state

增强状态推送（含 GPS 坐标、遥测数据、任务进度）。

**消息格式**：
```json
{
  "type": "state_update",
  "data": {
    "drone": {...},
    "mission": {...},
    "timestamp": "2026-05-18T10:00:00Z"
  }
}
```

## 无人机

### POST /drone/confirm-takeoff

确认无人机起飞（manual 模式下）。

**响应**：
```json
{
  "status": "confirmed",
  "message": "Takeoff confirmed"
}
```

### GET /drone/px4-status

获取 PX4 SITL 运行状态。

### GET /drone/dji/status

获取 DJI 无人机连接状态。

**响应**：
```json
{
  "backend": "dji_osdk",
  "execution_mode": "osdk_sim",
  "drone_model": "Matrice 30T",
  "connected": false
}
```

### GET /drone/dji/telemetry

获取 DJI 无人机遥测数据（位置、电量、高度）。

**响应**：
```json
{
  "latitude": 34.7467,
  "longitude": 113.6241,
  "altitude": 0.0,
  "battery_percent": 100.0,
  "drone_model": "Matrice 30T",
  "connected": false,
  "mode": "osdk_sim"
}
```

### POST /drone/dji/connect

连接 DJI 无人机（osdk_real 模式需硬件，osdk_sim 模式立即返回）。

**响应**：
```json
{
  "status": "connected",
  "backend": "dji_osdk",
  "execution_mode": "osdk_sim",
  "drone_model": "Matrice 30T",
  "connected": true
}
```

### POST /drone/dji/disconnect

断开 DJI 无人机连接。

**响应**：
```json
{
  "status": "disconnected"
}
```

## SLO 监控

### GET /slo

获取 SLO 指标快照（API 成功率、管线完成率、WebSocket 稳定性、系统可用性）。

**响应**：
```json
{
  "api_success_rate": {"current": 1.0, "target": 0.99},
  "pipeline_completion_rate": {"current": 1.0, "target": 0.95},
  "websocket_stability": {"current": 1.0, "target": 0.99},
  "system_availability": {"current": 1.0, "target": 0.999},
  "window_seconds": 60,
  "timestamp": "2026-05-26T10:00:00Z"
}
```
