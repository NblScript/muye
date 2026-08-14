"""Demo readiness endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.routes.health import collect_health_status
from app.services import workflow_service
from app.services.demo_readiness_service import build_demo_readiness_response
from app.slo import get_slo_metrics


async def get_demo_readiness() -> dict[str, Any]:
    """Return a presentation-friendly readiness summary."""
    health, _healthy = collect_health_status()
    workflow = workflow_service.build_workflow_state_response().model_dump()
    ws_metrics = get_slo_metrics().snapshot().get("websocket", {})
    websocket_connected = bool(
        ws_metrics.get("connects", 0) > ws_metrics.get("disconnects", 0)
    )
    return build_demo_readiness_response(
        health=health,
        workflow=workflow,
        websocket_connected=websocket_connected,
    )


def register_demo_readiness_routes(app: FastAPI) -> None:
    app.get("/demo/readiness", response_model=None)(get_demo_readiness)
    app.get("/api/demo/readiness", include_in_schema=False, response_model=None)(get_demo_readiness)
