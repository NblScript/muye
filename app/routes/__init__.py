from __future__ import annotations

from app.routes.dashboard import get_dashboard_context, register_dashboard_routes
from app.routes.demo import register_demo_routes, reset_demo_events, upload_demo_image
from app.routes.drone import confirm_drone_takeoff, register_drone_routes
from app.routes.health import api_health, api_live, register_health_routes
from app.routes.sim import get_sim_map_state, register_sim_routes
from app.routes.tasks import (
    annotate_image,
    get_task_annotated_image,
    get_task_original_image,
    register_tasks_routes,
)
from app.routes.workflow import (
    get_workflow_history,
    get_workflow_state,
    register_workflow_routes,
)

__all__ = [
    "annotate_image",
    "api_health",
    "api_live",
    "confirm_drone_takeoff",
    "get_dashboard_context",
    "get_sim_map_state",
    "get_task_annotated_image",
    "get_task_original_image",
    "get_workflow_history",
    "get_workflow_state",
    "register_dashboard_routes",
    "register_demo_routes",
    "register_drone_routes",
    "register_health_routes",
    "register_sim_routes",
    "register_tasks_routes",
    "register_workflow_routes",
    "reset_demo_events",
    "upload_demo_image",
]
