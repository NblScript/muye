"""Simulation map state endpoints."""

import asyncio
import logging
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from models.schemas import (
    BatteryState,
    DroneState,
    DroneStatusEnum,
    FieldState,
    GPSPosition,
    MissionState,
    SimMapStateResponse,
    TelemetryData,
    WorkflowStateResponse,
    WorkflowTaskState,
    WsEnhancedState,
)
from app.services import workflow_service
from app.services.map_simulator import Px4MapStateSimulator
from app.services.telemetry_service import get_telemetry_service
from modules.infra.common import safe_float

# Global simulator instance, set during app initialization
_simulator: Px4MapStateSimulator | None = None
logger = logging.getLogger(__name__)


def set_simulator(simulator: Px4MapStateSimulator) -> None:
    """Set the global simulator instance."""
    global _simulator
    _simulator = simulator


def get_simulator() -> Px4MapStateSimulator:
    """Get the global simulator instance."""
    if _simulator is None:
        raise RuntimeError("Simulator not initialized")
    return _simulator


async def get_sim_map_state() -> SimMapStateResponse:
    """Get simulation map state endpoint handler."""
    return get_simulator().snapshot()


async def sim_map_state_ws(websocket: WebSocket) -> None:
    """Legacy simulation map state websocket handler."""
    await websocket.accept()
    try:
        while True:
            snapshot = get_simulator().snapshot()
            await websocket.send_json(snapshot.model_dump())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


async def enhanced_state_ws(websocket: WebSocket) -> None:
    """Enhanced map state websocket handler with real telemetry state."""
    await websocket.accept()
    telemetry_service = get_telemetry_service()
    try:
        while True:
            try:
                workflow = workflow_service.build_workflow_state_response()
                _sync_telemetry_from_workflow(telemetry_service, workflow)
                mission_state = _build_mission_state(workflow)
                field_state = _build_field_state(workflow)
            except (OSError, ValueError) as exc:
                logger.warning("Transient error building workflow state: %s", exc)
                workflow = None
                mission_state = MissionState(status="unknown")
                field_state = None
            except Exception:
                logger.exception("Unexpected error building workflow state for websocket push")
                workflow = None
                mission_state = MissionState(status="unknown")
                field_state = None

            enhanced = WsEnhancedState(
                timestamp=time.time(),
                drone=telemetry_service.current_state or _default_drone_state(),
                mission=mission_state,
                trajectory=telemetry_service.get_trajectory_state(),
                field=field_state,
                workflow_state=workflow.model_dump() if workflow else None,
            )
            await websocket.send_json(enhanced.model_dump())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


def _default_drone_state() -> DroneState:
    """Build a safe default state before the first telemetry update."""
    return DroneState(
        id="px4-sitl",
        name="PX4 SITL 飞行器",
        status=DroneStatusEnum.CONNECTING,
        message="等待连接...",
        battery=BatteryState(remaining=0.0),
        telemetry=TelemetryData(),
    )


def _sync_telemetry_from_workflow(
    telemetry_service: Any,
    workflow: WorkflowStateResponse,
) -> None:
    """Update telemetry service from the latest workflow drone payload."""
    latest_task = workflow.latest_task
    drone = latest_task.drone or {}
    telemetry_service.update_from_drone_status(
        request_id=latest_task.request_id,
        task_id=_optional_str(drone.get("task_id")) or latest_task.request_id,
        status=str(drone.get("status") or latest_task.status or "connecting"),
        message=str(drone.get("message") or latest_task.message or ""),
        progress=_to_number(drone.get("progress")) or 0,
        current_waypoint_index=int(_to_number(drone.get("current_waypoint_index")) or 0),
        position=drone.get("position") if isinstance(drone.get("position"), dict) else None,
    )


def _build_mission_state(workflow: WorkflowStateResponse) -> MissionState:
    """Build mission state from workflow payload."""
    latest_task = workflow.latest_task
    drone = latest_task.drone or {}
    route = _extract_planned_route(latest_task)
    return MissionState(
        task_id=_optional_str(drone.get("task_id")) or latest_task.request_id,
        status=str(drone.get("status") or latest_task.status or "unknown"),
        progress=_to_number(drone.get("progress")) or 0.0,
        current_waypoint=int(_to_number(drone.get("current_waypoint_index")) or 0),
        total_waypoints=len(route),
        planned_route=route,
    )


def _build_field_state(workflow: WorkflowStateResponse) -> FieldState | None:
    """Build field state from workflow payload."""
    latest_task = workflow.latest_task
    field = latest_task.field or {}
    boundary = _extract_position_list(field.get("geofence"))
    if not field and not boundary:
        return None

    return FieldState(
        id=str(field.get("field_id") or "unknown"),
        name=str(field.get("field_name") or field.get("name") or "未命名地块"),
        boundary=boundary,
    )


def _extract_planned_route(latest_task: WorkflowTaskState) -> list[GPSPosition]:
    drone = latest_task.drone or {}
    instruction = drone.get("instruction") if isinstance(drone.get("instruction"), dict) else {}
    route = instruction.get("飞行路径") if isinstance(instruction, dict) else None
    return _extract_position_list(route)


def _extract_position_list(raw_points: Any) -> list[GPSPosition]:
    if not isinstance(raw_points, list):
        return []

    points: list[GPSPosition] = []
    now = time.time()
    for raw in raw_points:
        point = _position_from_raw(raw, timestamp=now)
        if point is not None:
            points.append(point)
    return points


def _position_from_raw(raw: Any, *, timestamp: float) -> GPSPosition | None:
    if isinstance(raw, dict):
        latitude = _to_number(raw.get("latitude") or raw.get("lat"))
        longitude = _to_number(raw.get("longitude") or raw.get("lng") or raw.get("lon"))
        altitude = _to_number(
            raw.get("altitude")
            or raw.get("relative_altitude_m")
            or raw.get("relative_altitude")
        )
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        longitude = _to_number(raw[0])
        latitude = _to_number(raw[1])
        altitude = _to_number(raw[2]) if len(raw) >= 3 else 0.0
    else:
        return None

    if latitude is None or longitude is None:
        return None

    return GPSPosition(
        latitude=latitude,
        longitude=longitude,
        altitude=altitude or 0.0,
        timestamp=timestamp,
    )


_to_number = safe_float


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def register_sim_routes(app: FastAPI, simulator: Px4MapStateSimulator) -> None:
    """Register simulation routes."""
    set_simulator(simulator)
    app.get("/sim/map-state", response_model=SimMapStateResponse)(get_sim_map_state)
    app.get("/api/sim/map-state", include_in_schema=False, response_model=SimMapStateResponse)(get_sim_map_state)
    app.websocket("/sim/ws/map-state")(sim_map_state_ws)
    app.websocket("/api/sim/ws/map-state")(sim_map_state_ws)
    app.websocket("/api/ws/enhanced-state")(enhanced_state_ws)
