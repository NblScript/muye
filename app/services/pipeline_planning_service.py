"""Spray planning helpers used by the main processing pipeline."""

from __future__ import annotations

from typing import Any


def detection_has_bbox(detections: list[dict[str, Any]]) -> bool:
    """Return true when at least one detection carries structured geometry."""
    for item in detections:
        pos = item.get("position")
        if pos is None:
            pos = item.get("bbox")
        if isinstance(pos, dict) and pos:
            return True
    return False


def plan_spray_mission(
    *,
    drone_controller: Any,
    field_context: dict[str, Any],
    current_weather: dict[str, Any],
    detections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Plan variable-rate spraying when geometry is available, otherwise use uniform route."""
    if detection_has_bbox(detections):
        from modules.drone.density_map import DensityMap

        geofence = field_context.get("geofence", [])
        if geofence and len(geofence) >= 3:
            density_map = DensityMap(geofence)
            density_map.add_detections(detections)
            return drone_controller.planner.plan_variable_rate_mission(
                field_context=field_context,
                current_weather=current_weather,
                density_map=density_map,
            )

    return drone_controller.plan_spray_mission(
        field_context=field_context,
        current_weather=current_weather,
    )
