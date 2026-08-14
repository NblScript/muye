"""Evaluation endpoints for pesticide effectiveness closed-loop."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from models.schemas import EvaluationListResponse, EvaluationResult
from app.services.workflow_service import get_sqlite_store


async def get_evaluation(request_id: str) -> EvaluationResult:
    """Get the latest evaluation result for a task."""
    store = get_sqlite_store()
    row = store.fetch_evaluation_by_task(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="未找到评估记录")
    return EvaluationResult(
        evaluation_id=row["id"],
        original_request_id=row["original_request_id"],
        status=row["status"],
        kill_rate=row.get("kill_rate"),
        pre_pest_count=row.get("pre_pest_count"),
        post_pest_count=row.get("post_pest_count"),
        kill_rate_threshold=row.get("kill_rate_threshold", 0.9),
        action_time_hours=row.get("action_time_hours"),
        retry_count=row.get("retry_count", 0),
        scheduled_at=row.get("scheduled_at"),
        evaluated_at=row.get("evaluated_at"),
        notes=row.get("notes"),
    )


async def list_evaluations(
    status: str | None = None, limit: int = 50, offset: int = 0,
) -> EvaluationListResponse:
    """List evaluation records, optionally filtered by status."""
    store = get_sqlite_store()
    if status:
        rows = store.fetch_evaluations_by_status(status)
    else:
        rows = store.fetch_all("SELECT * FROM task_evaluations ORDER BY id DESC")
        rows = [dict(r) for r in rows]
    total = len(rows)
    page = rows[offset : offset + limit]
    items = [
        EvaluationResult(
            evaluation_id=r["id"],
            original_request_id=r["original_request_id"],
            status=r["status"],
            kill_rate=r.get("kill_rate"),
            pre_pest_count=r.get("pre_pest_count"),
            post_pest_count=r.get("post_pest_count"),
            kill_rate_threshold=r.get("kill_rate_threshold", 0.9),
            action_time_hours=r.get("action_time_hours"),
            retry_count=r.get("retry_count", 0),
            scheduled_at=r.get("scheduled_at"),
            evaluated_at=r.get("evaluated_at"),
            notes=r.get("notes"),
        )
        for r in page
    ]
    return EvaluationListResponse(total=total, items=items)


async def cancel_evaluation(request_id: str) -> dict[str, str]:
    """Cancel a pending evaluation."""
    store = get_sqlite_store()
    row = store.fetch_evaluation_by_task(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="未找到评估记录")
    if row["status"] not in ("scheduled", "retry_scheduled"):
        raise HTTPException(status_code=400, detail="当前状态不允许取消")
    store.update_evaluation(row["id"], status="cancelled", notes="用户手动取消")
    return {"status": "cancelled", "request_id": request_id}


def register_evaluation_routes(app: FastAPI) -> None:
    """Register evaluation API routes."""
    app.get("/api/evaluation/{request_id}", response_model=EvaluationResult)(get_evaluation)
    app.get("/api/evaluations", response_model=EvaluationListResponse)(list_evaluations)
    app.post("/api/evaluation/{request_id}/cancel")(cancel_evaluation)
