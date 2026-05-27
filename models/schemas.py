"""Pydantic model definitions for API schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SimPoint(BaseModel):
    """Simulation point coordinates."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)


class SimDroneState(BaseModel):
    """Simulated drone state."""

    id: str
    name: str
    status: str
    battery: int = Field(ge=0, le=100)
    position: SimPoint
    route: list[SimPoint]


class SimMapStateResponse(BaseModel):
    """Response model for map state."""

    timestamp: float
    drones: list[SimDroneState]


class WorkflowEventEntry(BaseModel):
    """Single event entry in workflow timeline."""

    timestamp: str
    stage: str
    status: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowTimelineEntry(BaseModel):
    """Timeline entry for drone operations."""

    timestamp: str | None = None
    status: str
    message: str
    progress: int | None = None
    current_waypoint_index: int | None = None
    task_id: str | None = None


class WorkflowTaskState(BaseModel):
    """Complete state of a workflow task."""

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
    compliance: dict[str, Any] = {}
    rag_context: dict[str, Any] = {}
    drone: dict[str, Any]
    drone_timeline: list[WorkflowTimelineEntry]
    recent_events: list[WorkflowEventEntry]
    error: str | None = None
    evaluation: dict[str, Any] = {}
    mission: dict[str, Any] = {}


class DashboardTaskEntry(BaseModel):
    """Dashboard task list entry."""

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
    """Response model for workflow state."""

    source: str
    event_count: int
    latest_task: WorkflowTaskState
    recent_tasks: list[DashboardTaskEntry]


class DashboardContextResponse(BaseModel):
    """Response model for dashboard context."""

    modes: dict[str, str]
    upload_accept: list[str]


class HistoryTaskEntry(BaseModel):
    """History task entry for workflow history endpoint."""

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
    """Response model for workflow history."""

    total: int
    items: list[HistoryTaskEntry]


class DroneStatusEnum(str, Enum):
    """Normalized drone status values for enhanced websocket state."""

    CONNECTING = "connecting"
    READY = "ready"
    TAKEOFF = "takeoff"
    SPRAYING = "spraying"
    RETURNING = "returning"
    COMPLETED = "completed"
    ERROR = "error"


class GPSPosition(BaseModel):
    """Real GPS position from PX4 telemetry."""

    latitude: float
    longitude: float
    altitude: float
    absolute_altitude: float | None = None
    heading: float | None = None
    speed: float | None = None
    timestamp: float


class TelemetryData(BaseModel):
    """Drone telemetry data."""

    speed: float = 0.0
    ground_speed: float | None = None
    air_speed: float | None = None
    heading: float | None = None
    climb_rate: float | None = None


class BatteryState(BaseModel):
    """Drone battery state."""

    voltage: float | None = None
    current: float | None = None
    remaining: float
    temperature: float | None = None


class DroneState(BaseModel):
    """Enhanced drone state for websocket push."""

    id: str
    name: str
    status: DroneStatusEnum
    message: str = ""
    position: GPSPosition | None = None
    battery: BatteryState
    telemetry: TelemetryData


class MissionState(BaseModel):
    """Current mission state for websocket push."""

    task_id: str | None = None
    status: str
    progress: float = 0.0
    current_waypoint: int = 0
    total_waypoints: int = 0
    planned_route: list[GPSPosition] = Field(default_factory=list)


class TrajectoryState(BaseModel):
    """Recent trajectory and accumulated distance."""

    recent_points: list[GPSPosition] = Field(default_factory=list)
    total_distance: float = 0.0


class FieldState(BaseModel):
    """Field boundary state for websocket push."""

    id: str
    name: str
    boundary: list[GPSPosition] = Field(default_factory=list)


class WsEnhancedState(BaseModel):
    """Enhanced state for WebSocket push."""

    timestamp: float
    drone: DroneState
    mission: MissionState
    trajectory: TrajectoryState
    field: FieldState | None = None
    workflow_state: dict[str, Any] | None = None


class WsCombinedState(BaseModel):
    """Combined state for WebSocket push."""

    timestamp: float
    sim_map: SimMapStateResponse | None = None
    workflow_state: WorkflowStateResponse | None = None


class EvaluationResult(BaseModel):
    """Pesticide effectiveness evaluation result."""

    evaluation_id: int
    original_request_id: str
    status: str
    kill_rate: float | None = None
    pre_pest_count: int | None = None
    post_pest_count: int | None = None
    kill_rate_threshold: float = 0.7
    action_time_hours: float | None = None
    retry_count: int = 0
    scheduled_at: str | None = None
    evaluated_at: str | None = None
    notes: str | None = None


class EvaluationListResponse(BaseModel):
    """Paginated evaluation list."""

    total: int
    items: list[EvaluationResult]


class MissionIterationResult(BaseModel):
    """One spray+inspect iteration within a mission."""

    iteration_id: int
    iteration_number: int
    spray_request_id: str | None = None
    status: str
    pre_pest_count: int | None = None
    post_pest_count: int | None = None
    kill_rate: float | None = None
    spray_completed_at: str | None = None
    inspected_at: str | None = None
    evaluated_at: str | None = None
    notes: str | None = None


class MissionDetailResponse(BaseModel):
    """Full mission detail with all iterations."""

    mission_row_id: int
    mission_uuid: str
    original_request_id: str
    field_id: str | None = None
    status: str
    kill_rate_threshold: float = 0.9
    max_iterations: int = 3
    current_iteration: int = 0
    final_kill_rate: float | None = None
    pest_types: list[str] = []
    pesticide_name: str | None = None
    crop_name: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    notes: str | None = None
    iterations: list[MissionIterationResult] = []


class MissionListResponse(BaseModel):
    """Paginated mission list."""

    total: int
    items: list[MissionDetailResponse]
