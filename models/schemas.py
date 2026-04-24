"""Pydantic model definitions for API schemas."""

from __future__ import annotations

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
    drone: dict[str, Any]
    drone_timeline: list[WorkflowTimelineEntry]
    recent_events: list[WorkflowEventEntry]
    error: str | None = None


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


class WsCombinedState(BaseModel):
    """Combined state for WebSocket push."""

    timestamp: float
    sim_map: SimMapStateResponse | None = None
    workflow_state: WorkflowStateResponse | None = None
