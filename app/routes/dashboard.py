"""Dashboard context endpoint."""

from fastapi import FastAPI

from app.config import current_mode_labels
from models.schemas import DashboardContextResponse


async def get_dashboard_context() -> DashboardContextResponse:
    """Dashboard context endpoint handler."""
    return DashboardContextResponse(
        modes=current_mode_labels(),
        upload_accept=["jpg", "jpeg", "png"],
    )


def register_dashboard_routes(app: FastAPI) -> None:
    """Register dashboard routes."""
    app.get("/dashboard/context", response_model=DashboardContextResponse)(get_dashboard_context)
    app.get("/api/dashboard/context", include_in_schema=False, response_model=DashboardContextResponse)(get_dashboard_context)
