"""Mission lifecycle endpoints for multi-round spray+inspect cycles."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from models.schemas import (
    MissionDetailResponse,
    MissionIterationResult,
    MissionListResponse,
)
from app.services.workflow_service import get_sqlite_store


def _build_mission_response(mission: dict) -> MissionDetailResponse:
    """Build a MissionDetailResponse from a mission row."""
    store = get_sqlite_store()
    iterations = store.fetch_iterations(mission["mission_id"])
    iter_results = [
        MissionIterationResult(
            iteration_id=it["id"],
            iteration_number=it["iteration_number"],
            spray_request_id=it.get("spray_request_id"),
            status=it.get("status", "pending"),
            pre_pest_count=it.get("pre_pest_count"),
            post_pest_count=it.get("post_pest_count"),
            kill_rate=it.get("kill_rate"),
            spray_completed_at=it.get("spray_completed_at"),
            inspected_at=it.get("inspected_at"),
            evaluated_at=it.get("evaluated_at"),
            notes=it.get("notes"),
        )
        for it in iterations
    ]
    return MissionDetailResponse(
        mission_row_id=mission["id"],
        mission_uuid=mission["mission_id"],
        original_request_id=mission["original_request_id"],
        field_id=mission.get("field_id"),
        status=mission.get("status", "active"),
        kill_rate_threshold=mission.get("kill_rate_threshold", 0.9),
        max_iterations=mission.get("max_iterations", 3),
        current_iteration=mission.get("current_iteration", 0),
        final_kill_rate=mission.get("final_kill_rate"),
        pest_types=mission.get("pest_types", []),
        pesticide_name=mission.get("pesticide_name"),
        crop_name=mission.get("crop_name"),
        created_at=mission.get("created_at"),
        completed_at=mission.get("completed_at"),
        notes=mission.get("notes"),
        iterations=iter_results,
    )


async def get_mission_by_request(request_id: str) -> MissionDetailResponse:
    """Get mission detail by original request ID."""
    store = get_sqlite_store()
    mission = store.fetch_mission_by_request_id(request_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="未找到任务记录")
    return _build_mission_response(mission)


async def get_mission(mission_uuid: str) -> MissionDetailResponse:
    """Get mission detail by mission UUID."""
    store = get_sqlite_store()
    mission = store.fetch_mission_by_mission_id(mission_uuid)
    if mission is None:
        raise HTTPException(status_code=404, detail="未找到任务记录")
    return _build_mission_response(mission)


async def list_missions(
    status: str | None = None, limit: int = 50, offset: int = 0,
) -> MissionListResponse:
    """List missions with optional status filter."""
    store = get_sqlite_store()
    total = store.count_missions(status=status)
    rows = store.fetch_missions(status=status, limit=limit, offset=offset)
    items = [_build_mission_response(r) for r in rows]
    return MissionListResponse(total=total, items=items)


async def cancel_mission(mission_uuid: str) -> dict[str, str]:
    """Cancel an active mission."""
    store = get_sqlite_store()
    mission = store.fetch_mission_by_mission_id(mission_uuid)
    if mission is None:
        raise HTTPException(status_code=404, detail="未找到任务记录")
    if mission["status"] != "active":
        raise HTTPException(status_code=400, detail="只有进行中的任务可以取消")
    store.update_mission(mission["id"], status="cancelled", notes="用户手动取消")
    return {"status": "cancelled", "mission_id": mission_uuid}


def register_mission_routes(app: FastAPI) -> None:
    """Register mission API routes."""
    app.get("/api/mission/by-request/{request_id}", response_model=MissionDetailResponse)(get_mission_by_request)
    app.get("/api/mission/{mission_uuid}", response_model=MissionDetailResponse)(get_mission)
    app.get("/api/missions", response_model=MissionListResponse)(list_missions)
    app.post("/api/mission/{mission_uuid}/cancel")(cancel_mission)
