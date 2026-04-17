from __future__ import annotations

import argparse
import asyncio
import io
import logging
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import uvicorn
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from PIL import Image, ImageDraw, UnidentifiedImageError
from pydantic import BaseModel, Field

from modules.ai_decision import DecisionEngine
from modules.common import (
    CONFIG_DIR,
    DATA_DIR,
    IMAGES_DIR,
    build_logger,
    ensure_runtime_dirs,
    generate_request_id,
    load_environment,
    load_json,
    load_yaml,
    log_event,
)
from modules.data_collector import DataCollectorService
from modules.decision_context import SqliteDecisionContextProvider
from modules.drone_controller import DroneController
from modules.event_bus import FileEventBus
from modules.image_processor import ImageProcessor
from modules.local_yolo_api import create_app as create_local_yolo_app
from modules.local_yolo_api import load_local_yolo_settings
from modules.event_bus import build_task_views, load_events
from modules.sqlite_store import SqliteStore
from modules.virtual_drone_api import create_virtual_drone_app, load_virtual_drone_settings
from modules.weather_integration import WeatherClient


class SimPoint(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class SimDroneState(BaseModel):
    id: str
    name: str
    status: str
    battery: int = Field(ge=0, le=100)
    position: SimPoint
    route: list[SimPoint]


class SimMapStateResponse(BaseModel):
    timestamp: float
    drones: list[SimDroneState]


class WorkflowEventEntry(BaseModel):
    timestamp: str
    stage: str
    status: str
    message: str


class WorkflowTimelineEntry(BaseModel):
    timestamp: str | None = None
    status: str
    message: str
    progress: int | None = None
    current_waypoint_index: int | None = None
    task_id: str | None = None


class WorkflowTaskState(BaseModel):
    request_id: str
    current_stage: str
    status: str
    message: str
    updated_at: str | None = None
    image_path: str | None = None
    field: dict[str, Any]
    detections: list[dict[str, Any]]
    weather: dict[str, Any]
    spray_summary: dict[str, Any]
    decision: dict[str, Any]
    drone: dict[str, Any]
    drone_timeline: list[WorkflowTimelineEntry]
    recent_events: list[WorkflowEventEntry]
    error: str | None = None


class DashboardTaskEntry(BaseModel):
    request_id: str
    updated_at: str | None = None
    status: str
    current_stage: str
    field_name: str
    drone_label: str
    progress: int
    pesticide_name: str | None = None
    spray_area_mu: float | None = None
    is_current: bool = False


class WorkflowStateResponse(BaseModel):
    source: str
    event_count: int
    latest_task: WorkflowTaskState
    recent_tasks: list[DashboardTaskEntry]


class DashboardContextResponse(BaseModel):
    modes: dict[str, str]
    upload_accept: list[str]


class HistoryTaskEntry(BaseModel):
    request_id: str
    current_stage: str
    status: str
    message: str
    updated_at: str | None = None
    image_path: str | None = None
    field: dict[str, Any]
    detections: list[dict[str, Any]]
    weather: dict[str, Any]
    spray_summary: dict[str, Any]
    decision: dict[str, Any]
    drone: dict[str, Any]
    error: str | None = None


class WorkflowHistoryResponse(BaseModel):
    total: int
    items: list[HistoryTaskEntry]


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SimDroneBlueprint:
    drone_id: str
    name: str
    status: str
    route: tuple[tuple[float, float], ...]
    speed_units_per_second: float
    battery_start: int
    battery_floor: int
    battery_drain_per_second: float
    phase_offset: float = 0.0


class Px4MapStateSimulator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._drones = (
            SimDroneBlueprint(
                drone_id="drone-a07",
                name="植保无人机 A-07",
                status="作业中",
                route=((24, 29), (34, 31), (48, 34), (54, 40), (42, 36)),
                speed_units_per_second=6.5,
                battery_start=86,
                battery_floor=34,
                battery_drain_per_second=0.22,
                phase_offset=0.0,
            ),
            SimDroneBlueprint(
                drone_id="drone-c12",
                name="植保无人机 C-12",
                status="返航",
                route=((104, 78), (98, 74), (94, 70), (90, 66), (80, 50)),
                speed_units_per_second=4.2,
                battery_start=58,
                battery_floor=18,
                battery_drain_per_second=0.18,
                phase_offset=0.35,
            ),
        )

    def snapshot(self) -> SimMapStateResponse:
        with self._lock:
            drones = [self._build_drone_state(blueprint) for blueprint in self._drones]
        return SimMapStateResponse(timestamp=time.time(), drones=drones)

    def _build_drone_state(self, blueprint: SimDroneBlueprint) -> SimDroneState:
        anchor = blueprint.route[0] if blueprint.route else (0.0, 0.0)
        route = [SimPoint(x=x, y=y) for x, y in blueprint.route]
        return SimDroneState(
            id=blueprint.drone_id,
            name=blueprint.name,
            status=blueprint.status,
            battery=blueprint.battery_start,
            position=SimPoint(x=anchor[0], y=anchor[1]),
            route=route,
        )


simulator = Px4MapStateSimulator()
api_app = FastAPI(title="Muye Frontend API", version="1.3.0")
embedded_yolo_runner_for_health: EmbeddedYoloApiRunner | None = None


def _iso_utc_offset(seconds_ago: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds_ago))


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "false").lower() in {"1", "true", "yes", "on"}


def _current_mode_labels() -> dict[str, str]:
    drone_backend = os.getenv("DRONE_BACKEND", "simulated").lower()
    drone_mode = {
        "px4": "px4",
        "remote_api": "virtual_api",
        "simulated": "simulated",
    }.get(drone_backend, drone_backend or "simulated")
    return {
        "yolo": "real",
        "weather": "mock" if _truthy_env("QWEATHER_USE_MOCK") else "real",
        "qwen": "mock" if _truthy_env("QWEN_USE_MOCK") else "real",
        "drone": drone_mode,
    }


def _sanitize_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower() or ".jpg"
    stem = Path(filename).stem
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", stem).strip("-")
    return f"{normalized or 'upload'}{suffix}"


def _save_uploaded_image(uploaded_file: UploadFile, content: bytes) -> Path:
    ensure_runtime_dirs()
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    filename = _sanitize_filename(uploaded_file.filename or "upload.jpg")
    target = IMAGES_DIR / f"{timestamp}-{filename}"
    target.write_bytes(content)
    return target


def _validate_uploaded_image_content(content: bytes) -> None:
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="file_too_large")

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="invalid_image_content") from exc


def _annotate_image(image_path: str | Path, detections: list[dict[str, Any]]) -> Image.Image | None:
    target = Path(image_path)
    if not target.exists():
        return None

    image = Image.open(target).convert("RGB")
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    width = max(2, int(min(image.size) * 0.005))

    for detection in detections:
        position = detection.get("position", {})
        box = (
            float(position.get("x1", 0)),
            float(position.get("y1", 0)),
            float(position.get("x2", 0)),
            float(position.get("y2", 0)),
        )
        label = f"{detection.get('pest_type', 'unknown')} {float(detection.get('confidence', 0)):.2f}"
        draw.rectangle(box, outline="#FF7A00", width=width)
        text_anchor = (box[0] + 4, max(box[1] - 20, 0))
        draw.rectangle(
            (
                text_anchor[0] - 2,
                text_anchor[1] - 2,
                text_anchor[0] + len(label) * 7,
                text_anchor[1] + 16,
            ),
            fill="#FF7A00",
        )
        draw.text(text_anchor, label, fill="white")

    return annotated


def _image_media_type(path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")


def _build_fallback_workflow_state() -> WorkflowStateResponse:
    demo_instruction = {
        "飞行路径": [[24, 29], [34, 31], [48, 34], [54, 40], [42, 36]],
        "覆盖区域": {
            "coordinates": [[20, 26], [22, 40], [48, 42], [46, 24]],
        },
        "高度": 12,
        "速度": 4.5,
        "喷洒速率": "1.8 L/min",
    }
    timeline = [
        WorkflowTimelineEntry(
            timestamp=_iso_utc_offset(42),
            status="connecting",
            message="PX4 链路已建立，等待飞控握手",
            progress=12,
            current_waypoint_index=0,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=_iso_utc_offset(34),
            status="connected",
            message="飞控连接完成，开始检查定位状态",
            progress=24,
            current_waypoint_index=0,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=_iso_utc_offset(28),
            status="ready",
            message="定位与 Home 点正常，允许上传任务",
            progress=38,
            current_waypoint_index=0,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=_iso_utc_offset(20),
            status="uploaded",
            message="作业航线已上传至 PX4",
            progress=52,
            current_waypoint_index=1,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=_iso_utc_offset(12),
            status="armed",
            message="飞控已解锁，等待执行起飞",
            progress=66,
            current_waypoint_index=1,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=_iso_utc_offset(4),
            status="spraying",
            message="虚拟农田喷洒执行中",
            progress=78,
            current_waypoint_index=3,
            task_id="px4-demo-flow",
        ),
    ]
    recent_events = [
        WorkflowEventEntry(
            timestamp=_iso_utc_offset(44),
            stage="drone",
            status="connecting",
            message="PX4 遥测链路接通",
        ),
        WorkflowEventEntry(
            timestamp=_iso_utc_offset(32),
            stage="drone",
            status="connected",
            message="飞控握手完成",
        ),
        WorkflowEventEntry(
            timestamp=_iso_utc_offset(18),
            stage="drone",
            status="uploaded",
            message="覆盖式喷洒航线上传成功",
        ),
        WorkflowEventEntry(
            timestamp=_iso_utc_offset(5),
            stage="drone",
            status="spraying",
            message="PX4 仿真任务正在执行喷洒路径",
        ),
    ]
    latest_task = WorkflowTaskState(
        request_id="px4-demo-fallback",
        current_stage="drone",
        status="running",
        message="当前暂无事件总线任务，展示 PX4 仿真流程示例",
        updated_at=_iso_utc_offset(3),
        image_path=None,
        field={},
        detections=[],
        weather={},
        spray_summary={},
        decision={},
        drone={
            "task_id": "px4-demo-flow",
            "status": "spraying",
            "message": "虚拟农田喷洒执行中",
            "progress": 78,
            "current_waypoint_index": 3,
            "instruction": demo_instruction,
        },
        drone_timeline=timeline,
        recent_events=recent_events,
        error=None,
    )
    return WorkflowStateResponse(
        source="fallback",
        event_count=0,
        latest_task=latest_task,
        recent_tasks=[],
    )


def _load_sqlite_task_views(
    limit: int = 40,
    *,
    status: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    sqlite_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    store = SqliteStore(sqlite_path)
    try:
        return store.fetch_task_views(limit=limit, status=status, search=search)
    finally:
        store.close()


def _count_sqlite_tasks(
    *,
    status: str | None = None,
    search: str | None = None,
) -> int:
    sqlite_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    store = SqliteStore(sqlite_path)
    try:
        return store.count_task_views(status=status, search=search)
    finally:
        store.close()


def _task_history_status(task: dict[str, Any]) -> str:
    return str((task.get("drone") or {}).get("status") or task.get("status") or "-")


def _matches_history_filters(
    task: dict[str, Any],
    *,
    status: str | None = None,
    search: str | None = None,
) -> bool:
    if status and _task_history_status(task) != status:
        return False

    if not search:
        return True

    keyword = search.strip().lower()
    if not keyword:
        return True

    candidates = [
        str(task.get("request_id") or ""),
        str(task.get("field_id") or ""),
        str((task.get("field") or {}).get("field_id") or ""),
        str((task.get("field") or {}).get("field_name") or ""),
        str(task.get("image_path") or ""),
    ]
    for detection in task.get("detections", []) or []:
        candidates.append(str(detection.get("label") or ""))
        candidates.append(str(detection.get("pest_type") or ""))

    return any(keyword in candidate.lower() for candidate in candidates if candidate)


def _clear_demo_runtime_state() -> None:
    sqlite_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    store = SqliteStore(sqlite_path)
    try:
        store.clear_runtime_task_data()
    finally:
        store.close()


def _merge_runtime_field_hints(
    field: dict[str, Any] | None,
    drone: dict[str, Any] | None,
) -> dict[str, Any]:
    merged_field = dict(field or {})
    instruction = (drone or {}).get("instruction") or {}
    if not isinstance(instruction, dict):
        return merged_field

    field_id = str(instruction.get("field_id") or "").strip()
    field_name = str(instruction.get("field_name") or "").strip()
    crop_name = str(instruction.get("crop_name") or "").strip()
    coverage = instruction.get("覆盖区域") or {}
    coordinates = coverage.get("coordinates") if isinstance(coverage, dict) else None

    if field_id:
        merged_field["field_id"] = field_id
    if field_name:
        merged_field["field_name"] = field_name
        merged_field["name"] = field_name
    if crop_name:
        crop_cycle = merged_field.get("crop_cycle")
        merged_crop_cycle = dict(crop_cycle) if isinstance(crop_cycle, dict) else {}
        merged_crop_cycle["crop_name"] = crop_name
        merged_field["crop_cycle"] = merged_crop_cycle
        merged_field["crop_name"] = crop_name
    if isinstance(coordinates, list) and len(coordinates) >= 3:
        merged_field["geofence"] = coordinates

    return merged_field


def _merge_sqlite_tasks_with_events(
    sqlite_tasks: list[dict[str, Any]],
    event_tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    event_by_request = {str(task["request_id"]): task for task in event_tasks}
    merged: list[dict[str, Any]] = []
    seen_request_ids: set[str] = set()

    for sqlite_task in sqlite_tasks:
        request_id = str(sqlite_task["request_id"])
        event_task = event_by_request.get(request_id)
        merged_task = dict(sqlite_task)
        if event_task:
            merged_task["updated_at"] = event_task.get("updated_at") or sqlite_task.get("updated_at")
            merged_task["current_stage"] = event_task.get("current_stage") or sqlite_task.get("current_stage")
            merged_task["status"] = event_task.get("status") or sqlite_task.get("status")
            merged_task["message"] = event_task.get("message") or sqlite_task.get("message")
            merged_task["image_path"] = sqlite_task.get("image_path") or event_task.get("image_path")
            merged_task["field"] = sqlite_task.get("field") or event_task.get("field", {})
            merged_task["spray_summary"] = sqlite_task.get("spray_summary") or event_task.get("spray_summary", {})
            merged_task["detections"] = sqlite_task.get("detections") or event_task.get("detections", [])
            merged_task["weather"] = sqlite_task.get("weather") or event_task.get("weather", {})
            merged_task["decision"] = sqlite_task.get("decision") or event_task.get("decision", {})
            merged_task["drone"] = {
                **(sqlite_task.get("drone") or {}),
                **(event_task.get("drone") or {}),
            }
            merged_task["drone_timeline"] = event_task.get("drone_timeline", [])
            merged_task["events"] = event_task.get("events", [])
            merged_task["error"] = event_task.get("error") or sqlite_task.get("error")
        merged_task["field"] = _merge_runtime_field_hints(
            merged_task.get("field", {}) or {},
            merged_task.get("drone", {}) or {},
        )
        seen_request_ids.add(request_id)
        merged.append(merged_task)

    for event_task in event_tasks:
        request_id = str(event_task["request_id"])
        if request_id not in seen_request_ids:
            merged_event_task = dict(event_task)
            merged_event_task["field"] = _merge_runtime_field_hints(
                merged_event_task.get("field", {}) or {},
                merged_event_task.get("drone", {}) or {},
            )
            merged.append(merged_event_task)

    merged.sort(
        key=lambda task: str(task.get("updated_at") or task.get("created_at") or ""),
        reverse=True,
    )
    return merged


def _build_workflow_state_response() -> WorkflowStateResponse:
    events = load_events(limit=500)
    event_tasks = build_task_views(events)
    tasks = _merge_sqlite_tasks_with_events(_load_sqlite_task_views(limit=40), event_tasks)
    if not tasks:
        return _build_fallback_workflow_state()

    latest = next(
        (
            task
            for task in tasks
            if task.get("drone_timeline")
            or (task.get("drone") or {}).get("status")
            or (task.get("drone") or {}).get("task_id")
        ),
        None,
    )
    if latest is None:
        fallback = _build_fallback_workflow_state()
        latest_structured = tasks[0]
        fallback.latest_task = fallback.latest_task.model_copy(
            update={
                "request_id": str(latest_structured.get("request_id") or fallback.latest_task.request_id),
                "current_stage": str(latest_structured.get("current_stage") or fallback.latest_task.current_stage),
                "status": str(latest_structured.get("status") or fallback.latest_task.status),
                "message": str(latest_structured.get("message") or fallback.latest_task.message),
                "updated_at": latest_structured.get("updated_at") or fallback.latest_task.updated_at,
                "image_path": latest_structured.get("image_path"),
                "field": latest_structured.get("field", {}) or {},
                "detections": latest_structured.get("detections", []) or [],
                "weather": latest_structured.get("weather", {}) or {},
                "spray_summary": latest_structured.get("spray_summary", {}) or {},
                "decision": latest_structured.get("decision", {}) or {},
                "error": latest_structured.get("error"),
            }
        )
        fallback.recent_tasks = _build_recent_task_entries(tasks, current_request_id=fallback.latest_task.request_id)
        return fallback.model_copy(update={"event_count": len(events)})

    timeline = [
        WorkflowTimelineEntry(
            timestamp=item.get("timestamp"),
            status=str(item.get("status") or ""),
            message=str(item.get("message") or ""),
            progress=item.get("progress"),
            current_waypoint_index=item.get("current_waypoint_index"),
            task_id=item.get("task_id"),
        )
        for item in latest.get("drone_timeline", [])
    ]
    recent_events = [
        WorkflowEventEntry(
            timestamp=str(item.get("timestamp") or ""),
            stage=str(item.get("stage") or ""),
            status=str(item.get("status") or ""),
            message=str(item.get("message") or ""),
        )
        for item in latest.get("events", [])[-24:]
    ]
    latest_task = WorkflowTaskState(
        request_id=str(latest.get("request_id") or "-"),
        current_stage=str(latest.get("current_stage") or "-"),
        status=str(latest.get("status") or "-"),
        message=str(latest.get("message") or ""),
        updated_at=latest.get("updated_at"),
        image_path=latest.get("image_path"),
        field=latest.get("field", {}) or {},
        detections=latest.get("detections", []) or [],
        weather=latest.get("weather", {}) or {},
        spray_summary=latest.get("spray_summary", {}) or {},
        decision=latest.get("decision", {}) or {},
        drone=latest.get("drone", {}) or {},
        drone_timeline=timeline,
        recent_events=recent_events,
        error=latest.get("error"),
    )
    return WorkflowStateResponse(
        source="event_bus",
        event_count=len(events),
        latest_task=latest_task,
        recent_tasks=_build_recent_task_entries(tasks, current_request_id=str(latest.get("request_id") or "-")),
    )


def _build_history_response(
    *,
    limit: int = 12,
    status: str | None = None,
    search: str | None = None,
) -> WorkflowHistoryResponse:
    normalized_status = None if status in {None, "", "all"} else status
    sqlite_total = _count_sqlite_tasks(status=normalized_status, search=search)
    sqlite_limit = max(limit, sqlite_total, 1)
    tasks = _merge_sqlite_tasks_with_events(
        _load_sqlite_task_views(limit=sqlite_limit, status=normalized_status, search=search),
        build_task_views(load_events(limit=500)),
    )
    filtered_tasks = [
        task
        for task in tasks
        if _matches_history_filters(task, status=normalized_status, search=search)
    ]
    paged_tasks = filtered_tasks[:limit]
    items = [
        HistoryTaskEntry(
            request_id=str(task.get("request_id") or "-"),
            current_stage=str(task.get("current_stage") or "-"),
            status=_task_history_status(task),
            message=str(task.get("message") or ""),
            updated_at=task.get("updated_at"),
            image_path=task.get("image_path"),
            field=task.get("field", {}) or {},
            detections=task.get("detections", []) or [],
            weather=task.get("weather", {}) or {},
            spray_summary=task.get("spray_summary", {}) or {},
            decision=task.get("decision", {}) or {},
            drone=task.get("drone", {}) or {},
            error=task.get("error"),
        )
        for task in paged_tasks
    ]
    return WorkflowHistoryResponse(total=len(filtered_tasks), items=items)


def _load_task_by_request_id(request_id: str) -> dict[str, Any] | None:
    tasks = _merge_sqlite_tasks_with_events(
        _load_sqlite_task_views(limit=120, search=request_id),
        build_task_views(load_events(limit=500)),
    )
    for task in tasks:
        if str(task.get("request_id") or "") == request_id:
            return task
    return None


def _build_recent_task_entries(
    tasks: list[dict[str, Any]],
    *,
    current_request_id: str,
    limit: int = 6,
) -> list[DashboardTaskEntry]:
    entries: list[DashboardTaskEntry] = []
    ordered_tasks: list[dict[str, Any]] = []
    current_task = next(
        (task for task in tasks if str(task.get("request_id") or "-") == current_request_id),
        None,
    )
    if current_task is not None:
        ordered_tasks.append(current_task)
    ordered_tasks.extend(
        task
        for task in tasks
        if str(task.get("request_id") or "-") != current_request_id
    )

    for task in ordered_tasks[:limit]:
        field = task.get("field") or {}
        spray_summary = task.get("spray_summary") or {}
        decision = task.get("decision") or {}
        medication = decision.get("用药") or {}
        drone = task.get("drone") or {}
        entries.append(
            DashboardTaskEntry(
                request_id=str(task.get("request_id") or "-"),
                updated_at=task.get("updated_at"),
                status=str(drone.get("status") or task.get("status") or "-"),
                current_stage=str(task.get("current_stage") or "-"),
                field_name=str(
                    field.get("field_name")
                    or field.get("field_code")
                    or field.get("field_id")
                    or "未命名地块"
                ),
                drone_label=str(
                    drone.get("message")
                    or drone.get("task_id")
                    or task.get("message")
                    or "农业任务"
                ),
                progress=int(drone.get("progress") or 0),
                pesticide_name=str(medication.get("农药名称")) if medication.get("农药名称") else None,
                spray_area_mu=spray_summary.get("spray_area_mu"),
                is_current=str(task.get("request_id") or "-") == current_request_id,
            )
        )
    return entries


@api_app.get("/health", response_model=None)
@api_app.get("/api/health", include_in_schema=False, response_model=None)
async def api_health() -> Any:
    payload, healthy = _collect_health_status()
    if healthy:
        return payload
    return JSONResponse(status_code=503, content=payload)


@api_app.get("/sim/map-state", response_model=SimMapStateResponse)
@api_app.get("/api/sim/map-state", include_in_schema=False, response_model=SimMapStateResponse)
async def get_sim_map_state() -> SimMapStateResponse:
    return simulator.snapshot()


@api_app.get("/workflow/state", response_model=WorkflowStateResponse)
@api_app.get("/api/workflow/state", include_in_schema=False, response_model=WorkflowStateResponse)
async def get_workflow_state() -> WorkflowStateResponse:
    return _build_workflow_state_response()


@api_app.get("/dashboard/context", response_model=DashboardContextResponse)
@api_app.get("/api/dashboard/context", include_in_schema=False, response_model=DashboardContextResponse)
async def get_dashboard_context() -> DashboardContextResponse:
    return DashboardContextResponse(
        modes=_current_mode_labels(),
        upload_accept=["jpg", "jpeg", "png"],
    )


@api_app.get("/workflow/history", response_model=WorkflowHistoryResponse)
@api_app.get("/api/workflow/history", include_in_schema=False, response_model=WorkflowHistoryResponse)
async def get_workflow_history(
    limit: int = Query(default=12, ge=1, le=80),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> WorkflowHistoryResponse:
    return _build_history_response(limit=limit, status=status, search=search)


@api_app.post("/demo/upload-image")
@api_app.post("/api/demo/upload-image", include_in_schema=False)
async def upload_demo_image(file: UploadFile = File(...)) -> dict[str, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing_filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="unsupported_file_type")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")

    _validate_uploaded_image_content(content)
    target = _save_uploaded_image(file, content)
    return {
        "filename": target.name,
        "path": str(target),
    }


@api_app.post("/demo/reset-events")
@api_app.post("/api/demo/reset-events", include_in_schema=False)
async def reset_demo_events(confirm: bool = False) -> dict[str, str]:
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm_required")

    _clear_demo_runtime_state()
    FileEventBus().clear()
    return {"status": "cleared"}


@api_app.get("/tasks/{request_id}/original-image")
@api_app.get("/api/tasks/{request_id}/original-image", include_in_schema=False)
async def get_task_original_image(request_id: str) -> FileResponse:
    task = _load_task_by_request_id(request_id)
    if task is None or not task.get("image_path"):
        raise HTTPException(status_code=404, detail="task_image_not_found")

    image_path = Path(str(task["image_path"]))
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="image_file_not_found")

    return FileResponse(image_path, media_type=_image_media_type(image_path))


@api_app.get("/tasks/{request_id}/annotated-image")
@api_app.get("/api/tasks/{request_id}/annotated-image", include_in_schema=False)
async def get_task_annotated_image(request_id: str) -> StreamingResponse:
    task = _load_task_by_request_id(request_id)
    if task is None or not task.get("image_path"):
        raise HTTPException(status_code=404, detail="task_image_not_found")

    annotated = _annotate_image(str(task["image_path"]), task.get("detections", []) or [])
    if annotated is None:
        raise HTTPException(status_code=404, detail="annotated_image_not_found")

    buffer = io.BytesIO()
    annotated.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


@api_app.websocket("/sim/ws/map-state")
@api_app.websocket("/api/sim/ws/map-state")
async def sim_map_state_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(simulator.snapshot().model_dump())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


def _parse_env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _check_sqlite_health() -> dict[str, Any]:
    sqlite_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    store = SqliteStore(sqlite_path)
    try:
        row = store.fetch_one("SELECT 1 AS ok")
        if not row or int(row.get("ok") or 0) != 1:
            raise RuntimeError("sqlite_query_failed")
        return {"status": "ok", "path": str(sqlite_path)}
    finally:
        store.close()


def _check_data_dir_health() -> dict[str, Any]:
    ensure_runtime_dirs()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    probe_fd, probe_path = tempfile.mkstemp(prefix=".health-", dir=str(DATA_DIR))
    try:
        with os.fdopen(probe_fd, "w", encoding="utf-8") as handle:
            handle.write("ok")
        Path(probe_path).unlink(missing_ok=True)
        return {"status": "ok", "path": str(DATA_DIR)}
    except Exception:
        Path(probe_path).unlink(missing_ok=True)
        raise


def _check_embedded_yolo_health() -> dict[str, Any]:
    runner = embedded_yolo_runner_for_health
    if runner is None:
        return {"status": "skipped", "detail": "no_embedded_yolo_runner"}

    if runner.server_task is None:
        raise RuntimeError("embedded_yolo_runner_not_started")

    if runner.server_task.done():
        error = runner.server_task.exception()
        if error:
            raise RuntimeError(f"embedded_yolo_runner_exited: {error}") from error
        raise RuntimeError("embedded_yolo_runner_exited")

    return {
        "status": "ok",
        "detect_url": runner.detect_url,
        "health_url": runner.health_url,
    }


def _collect_health_status() -> tuple[dict[str, Any], bool]:
    checks: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, checker in (
        ("sqlite", _check_sqlite_health),
        ("data_dir", _check_data_dir_health),
        ("embedded_yolo", _check_embedded_yolo_health),
    ):
        try:
            result = checker()
        except Exception as exc:
            result = {"status": "error", "detail": str(exc)}

        checks[name] = result
        if result.get("status") == "error":
            failures.append(name)

    payload: dict[str, Any] = {
        "status": "ok" if not failures else "error",
        "checks": checks,
    }
    if failures:
        payload["failures"] = failures
    return payload, not failures


def _resolve_loopback_host(host: str) -> str:
    if host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    return host


def _build_local_yolo_urls(host: str, port: int) -> tuple[str, str]:
    access_host = _resolve_loopback_host(host)
    detect_url = f"http://{access_host}:{port}/detect"
    health_url = f"http://{access_host}:{port}/health"
    return detect_url, health_url


class EmbeddedYoloApiRunner:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.settings = load_local_yolo_settings()
        self.detect_url, self.health_url = _build_local_yolo_urls(
            self.settings.host,
            self.settings.port,
        )
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        started = time.perf_counter()
        request_id = generate_request_id()
        app = create_local_yolo_app(settings=self.settings, logger=self.logger)
        config = uvicorn.Config(
            app=app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        self.server = server
        self.server_task = asyncio.create_task(server.serve())

        try:
            await self._wait_until_ready()
            log_event(
                self.logger,
                logging.INFO,
                "内嵌 YOLO API 已启动",
                request_id=request_id,
                duration_ms=(time.perf_counter() - started) * 1000,
                detect_url=self.detect_url,
                health_url=self.health_url,
            )
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        if not self.server_task:
            return

        self.server.should_exit = True  # type: ignore[union-attr]
        try:
            await asyncio.wait_for(self.server_task, timeout=5)
        except asyncio.TimeoutError:
            self.server_task.cancel()
            await asyncio.gather(self.server_task, return_exceptions=True)
        finally:
            self.server_task = None
            self.server = None

    async def _wait_until_ready(self, timeout_seconds: float = 30, interval_seconds: float = 0.2) -> None:
        deadline = time.monotonic() + timeout_seconds
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            while time.monotonic() < deadline:
                if self.server_task and self.server_task.done():
                    error = self.server_task.exception()
                    if error:
                        raise RuntimeError(f"内嵌 YOLO API 启动失败: {error}") from error
                    raise RuntimeError("内嵌 YOLO API 意外退出")
                try:
                    response = await client.get(self.health_url)
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(interval_seconds)
        raise TimeoutError(f"等待 YOLO API 就绪超时: {self.health_url}")


class EmbeddedDroneApiRunner:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.settings = load_virtual_drone_settings()
        access_host = _resolve_loopback_host(self.settings.host)
        self.api_url = f"http://{access_host}:{self.settings.port}/missions"
        self.health_url = f"http://{access_host}:{self.settings.port}/health"
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        started = time.perf_counter()
        request_id = generate_request_id()
        app = create_virtual_drone_app(settings=self.settings, logger=self.logger)
        config = uvicorn.Config(
            app=app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        self.server = server
        self.server_task = asyncio.create_task(server.serve())

        try:
            await self._wait_until_ready()
            log_event(
                self.logger,
                logging.INFO,
                "内嵌虚拟无人机 API 已启动",
                request_id=request_id,
                duration_ms=(time.perf_counter() - started) * 1000,
                api_url=self.api_url,
                health_url=self.health_url,
            )
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        if not self.server_task:
            return

        self.server.should_exit = True  # type: ignore[union-attr]
        try:
            await asyncio.wait_for(self.server_task, timeout=5)
        except asyncio.TimeoutError:
            self.server_task.cancel()
            await asyncio.gather(self.server_task, return_exceptions=True)
        finally:
            self.server_task = None
            self.server = None

    async def _wait_until_ready(self, timeout_seconds: float = 30, interval_seconds: float = 0.2) -> None:
        deadline = time.monotonic() + timeout_seconds
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            while time.monotonic() < deadline:
                if self.server_task and self.server_task.done():
                    error = self.server_task.exception()
                    if error:
                        raise RuntimeError(f"内嵌虚拟无人机 API 启动失败: {error}") from error
                    raise RuntimeError("内嵌虚拟无人机 API 意外退出")
                try:
                    response = await client.get(self.health_url)
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(interval_seconds)
        raise TimeoutError(f"等待虚拟无人机 API 就绪超时: {self.health_url}")


class MuyeApplication:
    def __init__(self) -> None:
        ensure_runtime_dirs()
        load_environment()
        self.logger = build_logger("muye")
        self.drone_config = load_json(CONFIG_DIR / "drone_config.json")
        self._apply_runtime_drone_overrides()
        self.yolo_config = load_yaml(CONFIG_DIR / "yolo_config.yaml")
        self.event_bus = FileEventBus()
        self.client_ip = os.getenv(
            "SERVICE_CLIENT_IP",
            self.drone_config.get("network", {}).get("client_ip", "127.0.0.1"),
        )
        sqlite_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
        self.sqlite_store = SqliteStore(sqlite_path, logger=self.logger)

        self.queue: asyncio.Queue[tuple[str, Path, dict[str, Any]]] = asyncio.Queue()
        self.pending_images: set[str] = set()
        self.worker_tasks: list[asyncio.Task[None]] = []

        self.yolo_api_url = os.getenv("YOLO_API_URL", "http://127.0.0.1:8010/detect")
        self.image_processor = ImageProcessor(
            api_url=self.yolo_api_url,
            api_key=os.getenv("YOLO_API_KEY", ""),
            confidence_threshold=float(
                os.getenv(
                    "YOLO_CONFIDENCE_THRESHOLD",
                    self.yolo_config.get("confidence_threshold", 0.25),
                )
            ),
            timeout_seconds=float(self.yolo_config.get("timeout_seconds", 20)),
            batch_size=int(self.yolo_config.get("batch_size", 4)),
            headers=self.yolo_config.get("request_headers", {}),
            logger=self.logger,
        )
        self.weather_client = WeatherClient(
            geo_api_url=os.getenv(
                "QWEATHER_GEO_URL",
                "https://geoapi.qweather.com/v2/city/lookup",
            ),
            weather_api_url=os.getenv(
                "QWEATHER_WEATHER_URL",
                "https://devapi.qweather.com/v7/weather/now",
            ),
            api_key=os.getenv("QWEATHER_API_KEY", ""),
            use_mock=os.getenv("QWEATHER_USE_MOCK", "false").lower() in {"1", "true", "yes", "on"},
            mock_weather={
                "temperature": os.getenv("QWEATHER_MOCK_TEMPERATURE", "26"),
                "humidity": os.getenv("QWEATHER_MOCK_HUMIDITY", "58"),
                "summary": os.getenv("QWEATHER_MOCK_SUMMARY", "多云"),
                "wind_direction": os.getenv("QWEATHER_MOCK_WIND_DIRECTION", "东南风"),
                "wind_scale_text": os.getenv("QWEATHER_MOCK_WIND_SCALE", "2"),
                "wind_speed": os.getenv("QWEATHER_MOCK_WIND_SPEED", "3.3"),
            },
            timeout_seconds=float(
                self.drone_config.get("execution", {}).get("request_timeout_seconds", 15)
            ),
            logger=self.logger,
        )
        decision_context_provider = None
        if os.getenv("MUYE_ENABLE_SQLITE_DECISION_CONTEXT", "false").lower() in {"1", "true", "yes", "on"}:
            decision_context_provider = SqliteDecisionContextProvider(self.sqlite_store)
        self.decision_engine = DecisionEngine(
            api_url=os.getenv("QWEN_API_URL", ""),
            api_key=os.getenv("QWEN_API_KEY", ""),
            model=os.getenv("QWEN_MODEL", "qwen-max"),
            weather_client=self.weather_client,
            use_mock=os.getenv("QWEN_USE_MOCK", "false").lower() in {"1", "true", "yes", "on"},
            timeout_seconds=30,
            logger=self.logger,
            event_bus=self.event_bus,
            decision_context_provider=decision_context_provider,
        )
        self.drone_controller = DroneController(
            drone_config=self.drone_config,
            api_url=os.getenv("DRONE_API_URL", ""),
            api_key=os.getenv("DRONE_API_KEY", ""),
            timeout_seconds=float(
                self.drone_config.get("execution", {}).get("request_timeout_seconds", 15)
            ),
            logger=self.logger,
            event_bus=self.event_bus,
            sqlite_store=self.sqlite_store,
        )
        self.data_collector = DataCollectorService(
            images_dir=IMAGES_DIR,
            drone_config=self.drone_config,
            on_new_image=self.enqueue_image,
            logger=self.logger,
        )

    def _apply_runtime_drone_overrides(self) -> None:
        execution = self.drone_config.setdefault("execution", {})
        px4_config = self.drone_config.setdefault("px4", {})

        backend = os.getenv("DRONE_BACKEND")
        if backend:
            execution["backend"] = backend.strip().lower()

        if execution.get("backend") == "simulated":
            execution["simulate_only"] = True
        elif execution.get("backend") in {"remote_api", "px4"}:
            execution["simulate_only"] = False

        if os.getenv("PX4_SYSTEM_ADDRESS"):
            px4_config["system_address"] = os.getenv("PX4_SYSTEM_ADDRESS")
        if os.getenv("PX4_CONNECT_TIMEOUT_SECONDS"):
            px4_config["connect_timeout_seconds"] = float(os.getenv("PX4_CONNECT_TIMEOUT_SECONDS", "30"))
        if os.getenv("PX4_MISSION_TIMEOUT_SECONDS"):
            px4_config["mission_timeout_seconds"] = float(os.getenv("PX4_MISSION_TIMEOUT_SECONDS", "180"))

        px4_config["auto_arm"] = _parse_env_bool(
            os.getenv("PX4_AUTO_ARM"),
            bool(px4_config.get("auto_arm", True)),
        )
        px4_config["auto_start_mission"] = _parse_env_bool(
            os.getenv("PX4_AUTO_START_MISSION"),
            bool(px4_config.get("auto_start_mission", True)),
        )
        px4_config["return_to_launch_after_mission"] = _parse_env_bool(
            os.getenv("PX4_RETURN_TO_LAUNCH_AFTER_MISSION"),
            bool(px4_config.get("return_to_launch_after_mission", True)),
        )
        px4_config["require_global_position"] = _parse_env_bool(
            os.getenv("PX4_REQUIRE_GLOBAL_POSITION"),
            bool(px4_config.get("require_global_position", True)),
        )
        px4_config["prefer_demo_field"] = _parse_env_bool(
            os.getenv("PX4_USE_SITL_DEMO_FIELD"),
            bool(px4_config.get("prefer_demo_field", False)),
        )
        if os.getenv("PX4_ACCEPTANCE_RADIUS_M"):
            px4_config["acceptance_radius_m"] = float(os.getenv("PX4_ACCEPTANCE_RADIUS_M", "2.0"))

    def configure_embedded_yolo_api(self, detect_url: str) -> None:
        self.yolo_api_url = detect_url
        self.image_processor.api_url = detect_url

    def configure_drone_backend(self, backend: str) -> None:
        normalized = backend.strip().lower()
        self.drone_config.setdefault("execution", {})["backend"] = normalized
        self.drone_config["execution"]["simulate_only"] = normalized == "simulated"

    def configure_embedded_drone_api(self, api_url: str) -> None:
        self.configure_drone_backend("remote_api")
        self.drone_controller.api_url = api_url

    async def start(
        self,
        *,
        workers: int = 1,
        enable_scheduler: bool = True,
        capture_on_startup: bool | None = None,
    ) -> None:
        worker_count = max(1, workers)
        self.worker_tasks = [
            asyncio.create_task(self._worker(index + 1)) for index in range(worker_count)
        ]
        await self.data_collector.start(
            enable_scheduler=enable_scheduler,
            capture_on_startup=capture_on_startup,
        )
        log_event(
            self.logger,
            logging.INFO,
            "主处理链已启动",
            request_id=generate_request_id(),
            client_ip=self.client_ip,
            workers=worker_count,
            enable_scheduler=enable_scheduler,
            capture_on_startup=(
                self.data_collector.capture_on_startup
                if capture_on_startup is None
                else capture_on_startup
            ),
        )

    async def shutdown(self) -> None:
        await self.data_collector.shutdown()
        for task in self.worker_tasks:
            task.cancel()
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        await self.image_processor.close()
        await self.decision_engine.close()
        await self.weather_client.close()
        await self.drone_controller.close()
        self.sqlite_store.close()

    async def enqueue_image(self, image_path: Path) -> None:
        ready = await self._wait_until_ready(image_path)
        if not ready:
            log_event(
                self.logger,
                logging.ERROR,
                "图片文件未就绪，已跳过",
                request_id=generate_request_id(),
                client_ip=self.client_ip,
                image_path=str(image_path),
            )
            return

        key = str(image_path.resolve())
        if key in self.pending_images:
            return

        request_id = generate_request_id()
        try:
            field_context = self._resolve_runtime_field_context()
        except Exception as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "运行时地块上下文解析失败",
                request_id=request_id,
                client_ip=self.client_ip,
                image_path=str(image_path),
                error=str(exc),
            )
            return
        self.pending_images.add(key)
        await self.queue.put((request_id, image_path, field_context))
        self._sqlite_write(
            request_id,
            "mark_task_queued",
            lambda: self.sqlite_store.mark_task_queued(
                request_id,
                str(image_path),
                field_id=field_context.get("field_id"),
            ),
        )
        self.event_bus.publish(
            request_id=request_id,
            stage="queue",
            status="queued",
            message="图片已进入处理队列",
            payload={
                "image_path": str(image_path),
                "filename": image_path.name,
                "field_id": field_context.get("field_id"),
                "field_name": field_context.get("name"),
            },
        )
        log_event(
            self.logger,
            logging.INFO,
            "新图片已进入处理队列",
            request_id=request_id,
            client_ip=self.client_ip,
            image_path=str(image_path),
            queue_size=self.queue.qsize(),
        )

    async def run_forever(
        self,
        workers: int,
        capture_on_startup: bool | None = None,
    ) -> None:
        await self.start(workers=workers, capture_on_startup=capture_on_startup)
        await asyncio.Event().wait()

    async def run_once(self, workers: int, timeout_seconds: int) -> None:
        await self.start(workers=workers, enable_scheduler=False, capture_on_startup=False)
        await self.data_collector.capture_image()
        await asyncio.wait_for(self.queue.join(), timeout=timeout_seconds)

    async def _worker(self, worker_id: int) -> None:
        while True:
            request_id, image_path, field_context = await self.queue.get()
            try:
                await self._process_image(request_id, image_path, field_context, worker_id)
            finally:
                self.pending_images.discard(str(image_path.resolve()))
                self.queue.task_done()

    async def _process_image(
        self,
        request_id: str,
        image_path: Path,
        field_context: dict[str, Any],
        worker_id: int,
    ) -> None:
        started = time.perf_counter()
        try:
            self._sqlite_write(
                request_id,
                "mark_task_started",
                lambda: self.sqlite_store.mark_task_started(
                    request_id,
                    str(image_path),
                    field_id=field_context.get("field_id"),
                ),
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="pipeline",
                status="running",
                message="开始处理图片",
                payload={
                    "image_path": str(image_path),
                    "worker_id": worker_id,
                    "field_id": field_context.get("field_id"),
                    "field_name": field_context.get("name"),
                },
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="yolo",
                status="running",
                message="正在执行 YOLO 识别",
                payload={"image_path": str(image_path)},
            )
            detections = await self.image_processor.detect_pests(
                image_path=image_path,
                request_id=request_id,
                client_ip=self.client_ip,
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="yolo",
                status="completed",
                message="YOLO 识别完成",
                payload={"image_path": str(image_path), "detections": detections},
            )
            self._sqlite_write(
                request_id,
                "replace_detections",
                lambda: self.sqlite_store.replace_detections(request_id, detections),
            )
            if not detections:
                self._sqlite_write(
                    request_id,
                    "mark_task_finished_no_detections",
                    lambda: self.sqlite_store.mark_task_finished(request_id, "completed"),
                )
                self.event_bus.publish(
                    request_id=request_id,
                    stage="pipeline",
                    status="completed",
                    message="未发现超过阈值的害虫目标",
                    payload={"image_path": str(image_path), "detections": []},
                )
                log_event(
                    self.logger,
                    logging.INFO,
                    "未发现超过阈值的害虫目标",
                    request_id=request_id,
                    client_ip=self.client_ip,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    image_path=str(image_path),
                    worker_id=worker_id,
                )
                return

            bundle = await self.decision_engine.generate_decision(
                pest_detections=detections,
                field_context=field_context,
                request_id=request_id,
                client_ip=self.client_ip,
            )
            execution_plan = self.drone_controller.plan_spray_mission(
                field_context=field_context,
                current_weather=bundle["weather"],
            )
            self._sqlite_write(
                request_id,
                "add_weather_snapshot",
                lambda: self.sqlite_store.add_weather_snapshot(request_id, bundle["weather"]),
            )
            self._sqlite_write(
                request_id,
                "add_decision",
                lambda: self.sqlite_store.add_decision(request_id, bundle["decision"]),
            )
            result = await self.drone_controller.execute_spray_mission(
                decision=bundle["decision"],
                current_weather=bundle["weather"],
                request_id=request_id,
                client_ip=self.client_ip,
                execution_plan=execution_plan,
                field_context=field_context,
            )
            spray_record = self._build_spray_record(
                request_id=request_id,
                field_context=field_context,
                decision=bundle["decision"],
                weather=bundle["weather"],
                execution_plan=execution_plan,
                mission_result=result,
            )
            if spray_record is not None:
                self._sqlite_write(
                    request_id,
                    "upsert_spray_record",
                    lambda: self.sqlite_store.upsert_spray_record(spray_record),
                )
            self._sqlite_write(
                request_id,
                "mark_task_finished_success",
                lambda: self.sqlite_store.mark_task_finished(request_id, "completed"),
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="pipeline",
                status="completed",
                message="整条处理链执行成功",
                payload={
                    "image_path": str(image_path),
                    "detections": detections,
                    "weather": bundle["weather"],
                    "decision": bundle["decision"],
                    "execution_plan": execution_plan,
                    "mission_result": result,
                },
            )
            log_event(
                self.logger,
                logging.INFO,
                "整条处理链执行成功",
                request_id=request_id,
                client_ip=self.client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                image_path=str(image_path),
                worker_id=worker_id,
                detections=detections,
                execution_plan=execution_plan,
                mission_result=result,
            )
        except Exception as exc:
            self._sqlite_write(
                request_id,
                "mark_task_finished_error",
                lambda: self.sqlite_store.mark_task_finished(request_id, "error"),
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="pipeline",
                status="error",
                message="图片处理链执行失败",
                payload={"image_path": str(image_path), "error": str(exc)},
            )
            log_event(
                self.logger,
                logging.ERROR,
                "图片处理链执行失败",
                request_id=request_id,
                client_ip=self.client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                image_path=str(image_path),
                worker_id=worker_id,
                error=str(exc),
            )

    def _resolve_runtime_field_context(self) -> dict[str, Any]:
        if self._should_use_px4_demo_field():
            return self._build_px4_demo_field_context()

        configured_field_id = str(self.drone_config.get("field", {}).get("field_id") or "").strip() or None
        env_field_id = os.getenv("MUYE_ACTIVE_FIELD_ID")
        preferred_field_id = env_field_id or configured_field_id
        field_count_row = self.sqlite_store.fetch_one("SELECT COUNT(*) AS total FROM fields")
        field_count = int(field_count_row["total"]) if field_count_row else 0
        if preferred_field_id:
            field_context = self.sqlite_store.fetch_field_context(field_id=preferred_field_id)
            if field_context:
                if env_field_id or not self._should_ignore_config_fallback_field(preferred_field_id):
                    return field_context
            elif env_field_id or field_count > 0:
                raise RuntimeError(f"指定地块不存在: {preferred_field_id}")
        real_field_context = self._resolve_non_fallback_field_context()
        if real_field_context:
            return real_field_context
        field_context = self.sqlite_store.fetch_field_context()
        if field_context:
            return field_context
        return self._build_config_field_context()

    def _should_use_px4_demo_field(self) -> bool:
        execution = self.drone_config.get("execution", {})
        px4_config = self.drone_config.get("px4", {})
        return execution.get("backend") == "px4" and bool(px4_config.get("prefer_demo_field", False))

    def _build_px4_demo_field_context(self) -> dict[str, Any]:
        px4_config = self.drone_config.get("px4", {})
        demo_field = px4_config.get("demo_field") or {}
        location = demo_field.get("location", {})
        geofence = demo_field.get("geofence", [])
        if len(geofence) < 3:
            raise RuntimeError("PX4 SITL 演示地块缺少有效 geofence 配置")
        field_context = {
            "field_id": demo_field.get("field_id", "px4-sitl-demo"),
            "name": demo_field.get("name", "PX4 SITL 演示地块"),
            "weather_location": demo_field.get("weather_location") or location.get("city") or "Zurich",
            "area_mu": demo_field.get("area_mu", 1.0),
            "soil_type": demo_field.get("soil_type", "demo"),
            "geofence": geofence,
            "explicit_route": demo_field.get("explicit_route"),
            "presentation_profile": demo_field.get("presentation_profile"),
            "location": {
                "province": location.get("province"),
                "city": location.get("city"),
                "county": location.get("county"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
            "crop_cycle": demo_field.get("crop_cycle"),
        }
        self._seed_field_context(
            field_context,
            source="px4_sitl_demo",
            notes="Auto-seeded from config/drone_config.json PX4 SITL demo field.",
        )
        return field_context

    def _build_config_field_context(self) -> dict[str, Any]:
        field = self.drone_config.get("field", {})
        location = field.get("location", {})
        field_context = {
            "field_id": field.get("field_id"),
            "name": field.get("name", "默认示范田"),
            "weather_location": field.get("weather_location") or location.get("city"),
            "area_mu": field.get("area_mu"),
            "soil_type": field.get("soil_type"),
            "geofence": field.get("geofence", []),
            "location": {
                "province": location.get("province"),
                "city": location.get("city"),
                "county": location.get("county"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
            "crop_cycle": None,
        }
        self._seed_field_context(
            field_context,
            source="drone_config_fallback",
            notes="Auto-seeded from config/drone_config.json fallback context.",
            skip_if_any_field_exists=True,
        )
        return field_context

    def _seed_field_context(
        self,
        field_context: dict[str, Any],
        *,
        source: str,
        notes: str,
        skip_if_any_field_exists: bool = False,
    ) -> None:
        field_id = str(field_context.get("field_id") or "").strip()
        if not field_id:
            return
        location = field_context.get("location", {})
        existing_field = self.sqlite_store.fetch_one(
            """
            SELECT field_id
            FROM fields
            WHERE field_id = ?
            """,
            (field_id,),
        )
        if existing_field is not None:
            return
        if skip_if_any_field_exists:
            field_count_row = self.sqlite_store.fetch_one("SELECT COUNT(*) AS total FROM fields")
            field_count = int(field_count_row["total"]) if field_count_row else 0
            if field_count > 0:
                return
        try:
            self.sqlite_store.upsert_field(
                {
                    "field_id": field_id,
                    "field_code": field_id.upper(),
                    "field_name": field_context.get("name") or field_id,
                    "province": location.get("province"),
                    "city": location.get("city"),
                    "county": location.get("county"),
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "area_mu": field_context.get("area_mu"),
                    "geofence": field_context.get("geofence"),
                    "soil_type": field_context.get("soil_type"),
                    "source": source,
                    "notes": notes,
                }
            )
        except Exception as exc:
            log_event(
                self.logger,
                logging.WARNING,
                "配置地块回写 SQLite 失败",
                client_ip=self.client_ip,
                sqlite_path=str(self.sqlite_store.db_path),
                field_id=field_id,
                error=str(exc),
            )

    def _build_spray_record(
        self,
        *,
        request_id: str,
        field_context: dict[str, Any],
        decision: dict[str, Any],
        weather: dict[str, Any],
        execution_plan: dict[str, Any],
        mission_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        field_id = str(field_context.get("field_id") or "").strip()
        if not field_id:
            return None

        medication = decision.get("用药") or {}
        crop_cycle = field_context.get("crop_cycle") or {}
        crop_cycle_id = crop_cycle.get("id")
        pesticide_name = str(medication.get("农药名称") or "").strip()
        pesticide_row = None
        if pesticide_name:
            pesticide_row = self.sqlite_store.fetch_one(
                """
                SELECT pesticide_id
                FROM pesticide_catalog
                WHERE product_name = ?
                ORDER BY pesticide_id ASC
                LIMIT 1
                """,
                (pesticide_name,),
            )

        total_dosage = self._parse_total_dosage_liters(medication.get("总量"))
        spray_area_mu = self._extract_numeric_value(field_context.get("area_mu"))
        dosage_per_mu = None
        if total_dosage is not None and spray_area_mu and spray_area_mu > 0:
            dosage_per_mu = round(total_dosage / spray_area_mu, 4)

        notes_parts = []
        if pesticide_name:
            notes_parts.append(f"农药名称={pesticide_name}")
        if medication.get("浓度"):
            notes_parts.append(f"浓度={medication['浓度']}")
        if medication.get("安全提示"):
            notes_parts.append(
                "安全提示=" + "；".join(str(item) for item in medication.get("安全提示", []))
            )
        if decision.get("农事建议"):
            notes_parts.append(
                "农事建议=" + "；".join(str(item) for item in decision.get("农事建议", []))
            )

        return {
            "request_id": request_id,
            "field_id": field_id,
            "crop_cycle_id": crop_cycle_id,
            "drone_task_id": mission_result.get("task_id") or mission_result.get("mission_id"),
            "pesticide_id": pesticide_row["pesticide_id"] if pesticide_row else None,
            "spray_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "spray_area_mu": spray_area_mu,
            "dosage_per_mu": dosage_per_mu,
            "total_dosage": total_dosage,
            "dilution_ratio": medication.get("配比"),
            "spray_rate_lpm": execution_plan.get("喷洒速率"),
            "flight_height_m": execution_plan.get("高度"),
            "flight_speed_mps": execution_plan.get("速度"),
            "weather_snapshot": weather,
            "result_status": self._normalize_spray_result_status(mission_result),
            "source": "main_pipeline",
            "notes": " | ".join(notes_parts) if notes_parts else None,
        }

    def _should_ignore_config_fallback_field(self, field_id: str) -> bool:
        row = self.sqlite_store.fetch_one(
            """
            SELECT source
            FROM fields
            WHERE field_id = ?
            """,
            (field_id,),
        )
        if row is None or row.get("source") != "drone_config_fallback":
            return False
        non_fallback_row = self.sqlite_store.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM fields
            WHERE source IS NULL OR source != 'drone_config_fallback'
            """
        )
        non_fallback_count = int(non_fallback_row["total"]) if non_fallback_row else 0
        return non_fallback_count > 0

    def _resolve_non_fallback_field_context(self) -> dict[str, Any] | None:
        non_fallback_row = self.sqlite_store.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM fields
            WHERE source IS NULL OR source != 'drone_config_fallback'
            """
        )
        non_fallback_count = int(non_fallback_row["total"]) if non_fallback_row else 0
        if non_fallback_count == 0:
            return None
        if non_fallback_count > 1:
            raise RuntimeError("检测到多个地块，请显式设置 MUYE_ACTIVE_FIELD_ID")
        selected = self.sqlite_store.fetch_one(
            """
            SELECT field_id
            FROM fields
            WHERE source IS NULL OR source != 'drone_config_fallback'
            ORDER BY city ASC, field_name ASC
            LIMIT 1
            """
        )
        if selected is None:
            return None
        return self.sqlite_store.fetch_field_context(field_id=str(selected["field_id"]))

    def _normalize_spray_result_status(self, mission_result: dict[str, Any]) -> str:
        status = str(
            mission_result.get("final_status")
            or mission_result.get("last_known_status")
            or mission_result.get("status")
            or "planned"
        ).strip().lower()
        if status in {"completed", "simulated"}:
            return "completed"
        if status in {"failed", "error"}:
            return "failed"
        if status in {"cancelled", "canceled"}:
            return "cancelled"
        if status in {
            "takeoff",
            "enroute",
            "spraying",
            "returning",
            "running",
            "in_progress",
            "processing",
        }:
            return "in_progress"
        return "planned"

    def _extract_numeric_value(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if not match:
            return None
        return float(match.group(0))

    def _parse_total_dosage_liters(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text:
            return None

        normalized = text.replace(" ", "")
        unit_match = re.search(r"(-?\d+(?:\.\d+)?)(mL|ml|ML|毫升|L|l|升)", normalized)
        if unit_match:
            amount = float(unit_match.group(1))
            unit = unit_match.group(2).lower()
            if unit in {"ml", "毫升"}:
                return round(amount / 1000, 6)
            return amount

        return self._extract_numeric_value(text)

    def _sqlite_write(
        self,
        request_id: str,
        operation: str,
        callback: Callable[[], None],
    ) -> None:
        try:
            callback()
        except Exception as exc:
            log_event(
                self.logger,
                logging.WARNING,
                "SQLite 写入失败",
                request_id=request_id,
                client_ip=self.client_ip,
                operation=operation,
                sqlite_path=str(self.sqlite_store.db_path),
                error=str(exc),
            )

    async def _wait_until_ready(
        self,
        image_path: Path,
        retries: int = 10,
        delay_seconds: float = 0.2,
    ) -> bool:
        last_size = -1
        for _ in range(retries):
            if image_path.exists():
                current_size = image_path.stat().st_size
                if current_size > 0 and current_size == last_size:
                    return True
                last_size = current_size
            await asyncio.sleep(delay_seconds)
        return image_path.exists() and image_path.stat().st_size > 0


async def _async_main(args: argparse.Namespace) -> None:
    global embedded_yolo_runner_for_health
    app = MuyeApplication()
    embedded_yolo_runner: EmbeddedYoloApiRunner | None = None
    embedded_drone_runner: EmbeddedDroneApiRunner | None = None
    try:
        if args.drone_backend:
            app.configure_drone_backend(args.drone_backend)

        if args.with_yolo_api or args.with_demo_stack:
            embedded_yolo_runner = EmbeddedYoloApiRunner(logger=app.logger)
            embedded_yolo_runner_for_health = embedded_yolo_runner
            app.configure_embedded_yolo_api(embedded_yolo_runner.detect_url)
            await embedded_yolo_runner.start()
            app.logger.info(
                "一键模式已接管 YOLO API 目标地址: %s",
                embedded_yolo_runner.detect_url,
            )
        else:
            app.logger.info(
                "当前使用外部 YOLO API: %s",
                app.yolo_api_url,
            )

        if args.with_virtual_drone_api or args.with_demo_stack:
            embedded_drone_runner = EmbeddedDroneApiRunner(logger=app.logger)
            app.configure_embedded_drone_api(embedded_drone_runner.api_url)
            await embedded_drone_runner.start()
            app.logger.info(
                "演示模式已接管虚拟无人机 API 地址: %s",
                embedded_drone_runner.api_url,
            )

        if args.once:
            await app.run_once(workers=args.workers, timeout_seconds=args.timeout)
        else:
            await app.run_forever(
                workers=args.workers,
                capture_on_startup=False if args.no_capture_on_startup else None,
            )
    finally:
        await app.shutdown()
        if embedded_yolo_runner:
            await embedded_yolo_runner.stop()
        embedded_yolo_runner_for_health = None
        if embedded_drone_runner:
            await embedded_drone_runner.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="牧野智能农业害虫防治系统")
    parser.add_argument("--once", action="store_true", help="执行一次采集与处理流程后退出")
    parser.add_argument(
        "--with-yolo-api",
        action="store_true",
        help="在主进程内一并启动本地 YOLO API，再启动农业防治主系统",
    )
    parser.add_argument(
        "--with-virtual-drone-api",
        action="store_true",
        help="在主进程内一并启动虚拟无人机 API，并接管无人机任务执行",
    )
    parser.add_argument(
        "--with-demo-stack",
        action="store_true",
        help="一键启动本地 YOLO API、虚拟无人机 API 和农业防治主系统",
    )
    parser.add_argument(
        "--drone-backend",
        choices=["simulated", "remote_api", "px4"],
        help="覆盖无人机执行后端，可选 simulated、remote_api、px4",
    )
    parser.add_argument(
        "--no-capture-on-startup",
        action="store_true",
        help="启动后不立即自动采图，适合由外部脚本投喂指定演示图片",
    )
    parser.add_argument("--workers", type=int, default=1, help="图片处理并发 worker 数量")
    parser.add_argument("--timeout", type=int, default=60, help="--once 模式的等待超时时间")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
