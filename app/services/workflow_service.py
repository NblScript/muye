"""Workflow service for building workflow state responses."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from models.schemas import (
    DashboardTaskEntry,
    HistoryTaskEntry,
    WorkflowEventEntry,
    WorkflowHistoryResponse,
    WorkflowStateResponse,
    WorkflowTaskState,
    WorkflowTimelineEntry,
)
from modules.infra.common import DATA_DIR
from modules.infra.event_bus import build_task_views, load_events
from modules.infra.sqlite_store import SqliteStore

from app.deps import iso_utc_offset


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@lru_cache(maxsize=1)
def _get_sqlite_path() -> Path:
    """Get the SQLite path (cached)."""
    return Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))


@lru_cache(maxsize=1)
def get_sqlite_store() -> SqliteStore:
    """Get the shared SqliteStore instance (singleton)."""
    return SqliteStore(_get_sqlite_path())


def load_sqlite_task_views(
    limit: int = 40,
    *,
    status: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Load task views from SQLite using shared store."""
    return get_sqlite_store().fetch_task_views(limit=limit, status=status, search=search)


def count_sqlite_tasks(
    *,
    status: str | None = None,
    search: str | None = None,
) -> int:
    """Count tasks in SQLite using shared store."""
    return get_sqlite_store().count_task_views(status=status, search=search)


def clear_demo_runtime_state() -> None:
    """Clear demo runtime state from SQLite using shared store."""
    get_sqlite_store().clear_runtime_task_data()


def task_history_status(task: dict[str, Any]) -> str:
    """Get the status for task history display."""
    return str((task.get("drone") or {}).get("status") or task.get("status") or "-")


def matches_history_filters(
    task: dict[str, Any],
    *,
    status: str | None = None,
    search: str | None = None,
) -> bool:
    """Check if a task matches history filters."""
    if status and task_history_status(task) != status:
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


def merge_runtime_field_hints(
    field: dict[str, Any] | None,
    drone: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge runtime field hints from drone instruction."""
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


def merge_sqlite_tasks_with_events(
    sqlite_tasks: list[dict[str, Any]],
    event_tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge SQLite tasks with event tasks."""
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
        merged_task["field"] = merge_runtime_field_hints(
            merged_task.get("field", {}) or {},
            merged_task.get("drone", {}) or {},
        )
        seen_request_ids.add(request_id)
        merged.append(merged_task)

    for event_task in event_tasks:
        request_id = str(event_task["request_id"])
        if request_id not in seen_request_ids:
            merged_event_task = dict(event_task)
            merged_event_task["field"] = merge_runtime_field_hints(
                merged_event_task.get("field", {}) or {},
                merged_event_task.get("drone", {}) or {},
            )
            merged.append(merged_event_task)

    merged.sort(
        key=lambda task: str(task.get("updated_at") or task.get("created_at") or ""),
        reverse=True,
    )
    return merged


def build_fallback_workflow_state() -> WorkflowStateResponse:
    """Build a fallback workflow state for demo purposes."""
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
            timestamp=iso_utc_offset(42),
            status="connecting",
            message="PX4 链路已建立，等待飞控握手",
            progress=12,
            current_waypoint_index=0,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=iso_utc_offset(34),
            status="connected",
            message="飞控连接完成，开始检查定位状态",
            progress=24,
            current_waypoint_index=0,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=iso_utc_offset(28),
            status="ready",
            message="定位与 Home 点正常，允许上传任务",
            progress=38,
            current_waypoint_index=0,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=iso_utc_offset(20),
            status="uploaded",
            message="作业航线已上传至 PX4",
            progress=52,
            current_waypoint_index=1,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=iso_utc_offset(12),
            status="armed",
            message="飞控已解锁，等待执行起飞",
            progress=66,
            current_waypoint_index=1,
            task_id="px4-demo-flow",
        ),
        WorkflowTimelineEntry(
            timestamp=iso_utc_offset(4),
            status="spraying",
            message="虚拟农田喷洒执行中",
            progress=78,
            current_waypoint_index=3,
            task_id="px4-demo-flow",
        ),
    ]
    recent_events = [
        WorkflowEventEntry(
            timestamp=iso_utc_offset(44),
            stage="drone",
            status="connecting",
            message="PX4 遥测链路接通",
        ),
        WorkflowEventEntry(
            timestamp=iso_utc_offset(32),
            stage="drone",
            status="connected",
            message="飞控握手完成",
        ),
        WorkflowEventEntry(
            timestamp=iso_utc_offset(18),
            stage="drone",
            status="uploaded",
            message="覆盖式喷洒航线上传成功",
        ),
        WorkflowEventEntry(
            timestamp=iso_utc_offset(5),
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
        updated_at=iso_utc_offset(3),
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


def build_recent_task_entries(
    tasks: list[dict[str, Any]],
    *,
    current_request_id: str,
    limit: int = 6,
) -> list[DashboardTaskEntry]:
    """Build recent task entries for dashboard."""
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


def load_task_by_request_id(request_id: str) -> dict[str, Any] | None:
    """Load a task by request ID."""
    tasks = merge_sqlite_tasks_with_events(
        load_sqlite_task_views(limit=120, search=request_id),
        build_task_views(load_events(limit=500)),
    )
    for task in tasks:
        if str(task.get("request_id") or "") == request_id:
            return task
    return None


def build_workflow_state_response() -> WorkflowStateResponse:
    """Build the workflow state response."""
    events = load_events(limit=500)
    event_tasks = build_task_views(events)
    tasks = merge_sqlite_tasks_with_events(load_sqlite_task_views(limit=40), event_tasks)
    if not tasks:
        return build_fallback_workflow_state()

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
        fallback = build_fallback_workflow_state()
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
        fallback.recent_tasks = build_recent_task_entries(tasks, current_request_id=fallback.latest_task.request_id)
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
        recent_tasks=build_recent_task_entries(tasks, current_request_id=str(latest.get("request_id") or "-")),
    )


def build_history_response(
    *,
    limit: int = 12,
    status: str | None = None,
    search: str | None = None,
) -> WorkflowHistoryResponse:
    """Build the workflow history response."""
    import modules.infra.event_bus as _eb

    normalized_status = None if status in {None, "", "all"} else status

    # Use module-level attribute references so tests can monkeypatch
    count_fn = count_sqlite_tasks
    load_fn = load_sqlite_task_views
    load_events_fn = _eb.load_events
    build_task_views_fn = _eb.build_task_views

    sqlite_total = count_fn(status=normalized_status, search=search)
    sqlite_limit = max(limit, sqlite_total, 1)
    tasks = merge_sqlite_tasks_with_events(
        load_fn(limit=sqlite_limit, status=normalized_status, search=search),
        build_task_views_fn(load_events_fn(limit=500)),
    )
    filtered_tasks = [
        task
        for task in tasks
        if matches_history_filters(task, status=normalized_status, search=search)
    ]
    paged_tasks = filtered_tasks[:limit]
    items = [
        HistoryTaskEntry(
            request_id=str(task.get("request_id") or "-"),
            current_stage=str(task.get("current_stage") or "-"),
            status=task_history_status(task),
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


# Image helper functions

def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe storage."""
    suffix = Path(filename).suffix.lower() or ".jpg"
    stem = Path(filename).stem
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", stem).strip("-")
    return f"{normalized or 'upload'}{suffix}"


def image_media_type(path: Path) -> str:
    """Get the media type for an image file."""
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
