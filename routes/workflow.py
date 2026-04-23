"""Workflow state and history endpoints."""

import sys

from fastapi import FastAPI, Query

from models.schemas import WorkflowHistoryResponse, WorkflowStateResponse
from services.workflow_service import (
    build_history_response as _original_build_history,
    build_workflow_state_response,
)


def _get_history_builder():
    """Get the history builder function, checking for monkeypatching."""
    main_module = sys.modules.get("main")
    if main_module is not None:
        patched = getattr(main_module, "_build_history_response", None)
        if patched is not None:
            return patched
    return _original_build_history


async def get_workflow_state() -> WorkflowStateResponse:
    """Workflow state endpoint handler."""
    return build_workflow_state_response()


async def get_workflow_history(
    limit: int = Query(default=12, ge=1, le=80),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> WorkflowHistoryResponse:
    """Workflow history endpoint handler."""
    builder = _get_history_builder()
    return builder(limit=limit, status=status, search=search)


def register_workflow_routes(app: FastAPI) -> None:
    """Register workflow routes."""
    app.get("/workflow/state", response_model=WorkflowStateResponse)(get_workflow_state)
    app.get("/api/workflow/state", include_in_schema=False, response_model=WorkflowStateResponse)(get_workflow_state)
    app.get("/workflow/history", response_model=WorkflowHistoryResponse)(get_workflow_history)
    app.get("/api/workflow/history", include_in_schema=False, response_model=WorkflowHistoryResponse)(get_workflow_history)
