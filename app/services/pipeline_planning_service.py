"""Spray planning helpers used by the main processing pipeline."""

from __future__ import annotations

from typing import Any

from modules.drone.density_map import DENSITY_ALGORITHM_VERSION, DensityMap


SPRAY_RATE_POLICY = {
    "basis": "lane_max_relative_heat",
    "bands": [
        {
            "label": "低热值",
            "minimum": 0.0,
            "maximum_exclusive": 0.3,
            "multiplier": 0.5,
        },
        {
            "label": "中热值",
            "minimum": 0.3,
            "maximum_exclusive": 0.6,
            "multiplier": 1.0,
        },
        {
            "label": "高热值",
            "minimum": 0.6,
            "maximum_exclusive": None,
            "multiplier": 1.5,
        },
    ],
}


def detection_has_bbox(detections: list[dict[str, Any]]) -> bool:
    """Return true when at least one detection carries structured geometry."""
    for item in detections:
        pos = item.get("position")
        if pos is None:
            pos = item.get("bbox")
        if not isinstance(pos, dict):
            continue
        if {"x1", "y1", "x2", "y2"}.issubset(pos) or {"x", "y", "w", "h"}.issubset(pos):
            return True
    return False


def build_density_payload(
    *,
    field_context: dict[str, Any],
    detections: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build a durable heatmap payload, including explicit unavailable metadata."""
    geofence = field_context.get("geofence", [])
    if isinstance(geofence, list) and len(geofence) >= 3:
        try:
            density_map = DensityMap(geofence)
            density_map.add_detections(detections)
            return density_map.to_geo_grid(), density_map.metadata()
        except (TypeError, ValueError):
            pass

    return [], {
        "source": "yolo_bbox",
        "algorithm_version": DENSITY_ALGORITHM_VERSION,
        "density_kind": "relative_detection_weight",
        "coordinate_space": "image_normalized",
        "projection": "image_frame_to_geofence_bbox",
        "normalization": "max_cell_weight",
        "grid_rows": 8,
        "grid_cols": 10,
        "detection_count": len(detections),
        "accepted_detection_count": 0,
        "rejected_detection_count": len(detections),
        "is_simulated": False,
        "status": "unavailable",
        "reason": "invalid_geofence",
    }


def attach_heatmap_trace(
    plan: dict[str, Any],
    *,
    snapshot_id: str | None,
    density_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Bind a spray plan to the exact heatmap snapshot it consumed."""
    traced_plan = dict(plan)
    metadata = dict(density_metadata or {})
    has_variable_schedule = bool(
        traced_plan.get("density_grid") and traced_plan.get("spray_schedule")
    )
    accepted_count = int(metadata.get("accepted_detection_count") or 0)

    traced_plan["planning_mode"] = (
        "variable_rate" if has_variable_schedule else "uniform_fallback"
    )
    traced_plan["heatmap_snapshot_id"] = snapshot_id
    traced_plan["heatmap_algorithm_version"] = str(
        metadata.get("algorithm_version") or "unversioned"
    )
    traced_plan["heatmap_snapshot_source"] = str(metadata.get("source") or "unknown")
    traced_plan["heatmap_trace_status"] = (
        "linked" if snapshot_id else "snapshot_persistence_unavailable"
    )
    traced_plan["spray_rate_policy"] = {
        **SPRAY_RATE_POLICY,
        "base_rate_lpm": traced_plan.get("喷洒速率"),
    }

    if not has_variable_schedule:
        traced_plan["degradation_reason"] = str(
            metadata.get("reason")
            or ("no_valid_detection_coordinates" if accepted_count <= 0 else "variable_planning_unavailable")
        )
    return traced_plan


def plan_spray_mission(
    *,
    drone_controller: Any,
    field_context: dict[str, Any],
    current_weather: dict[str, Any],
    detections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Plan variable-rate spraying when geometry is available, otherwise use uniform route."""
    if detection_has_bbox(detections):
        geofence = field_context.get("geofence", [])
        if geofence and len(geofence) >= 3:
            density_map = DensityMap(geofence)
            density_map.add_detections(detections)
            if density_map.has_data:
                return drone_controller.planner.plan_variable_rate_mission(
                    field_context=field_context,
                    current_weather=current_weather,
                    density_map=density_map,
                )

    return drone_controller.plan_spray_mission(
        field_context=field_context,
        current_weather=current_weather,
    )
