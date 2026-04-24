"""Workflow state and history endpoints."""

from fastapi import FastAPI, Query

from models.schemas import WorkflowHistoryResponse, WorkflowStateResponse
import app.services.workflow_service as workflow_service


async def get_workflow_state() -> WorkflowStateResponse:
    """Workflow state endpoint handler."""
    return workflow_service.build_workflow_state_response()


async def get_workflow_history(
    limit: int = Query(default=12, ge=1, le=80),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> WorkflowHistoryResponse:
    """Workflow history endpoint handler."""
    return workflow_service.build_history_response(limit=limit, status=status, search=search)


def register_workflow_routes(app: FastAPI) -> None:
    """Register workflow routes."""
    app.get("/workflow/state", response_model=WorkflowStateResponse)(get_workflow_state)
    app.get("/api/workflow/state", include_in_schema=False, response_model=WorkflowStateResponse)(get_workflow_state)
    app.get("/workflow/history", response_model=WorkflowHistoryResponse)(get_workflow_history)
    app.get("/api/workflow/history", include_in_schema=False, response_model=WorkflowHistoryResponse)(get_workflow_history)
