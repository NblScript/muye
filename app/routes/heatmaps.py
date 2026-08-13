"""Query endpoints for durable insect heatmap snapshots."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query

from app.services.workflow_service import get_sqlite_store
from models.schemas import (
    HeatmapComparisonMetrics,
    HeatmapComparisonResponse,
    HeatmapSnapshotDetail,
    HeatmapSnapshotListResponse,
    HeatmapSnapshotSummary,
)


HOTSPOT_RELATIVE_HEAT_THRESHOLD = 0.7


def _relative_heat_stats(snapshot: dict[str, Any]) -> tuple[int, float]:
    values: list[float] = []
    for cell in snapshot.get("density_grid", []) or []:
        try:
            value = float(cell.get("density", 0.0))
        except (AttributeError, TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(max(0.0, min(1.0, value)))
    hotspot_count = sum(value >= HOTSPOT_RELATIVE_HEAT_THRESHOLD for value in values)
    peak = max(values, default=0.0)
    return hotspot_count, round(peak, 6)


def _snapshot_summary(snapshot: dict[str, Any]) -> HeatmapSnapshotSummary:
    hotspot_count, peak = _relative_heat_stats(snapshot)
    return HeatmapSnapshotSummary(
        snapshot_id=str(snapshot["snapshot_id"]),
        batch_id=str(snapshot["batch_id"]),
        request_id=str(snapshot["request_id"]),
        field_id=snapshot.get("field_id"),
        mission_id=snapshot.get("mission_id"),
        iteration_number=int(snapshot.get("iteration_number") or 1),
        inspection_kind=snapshot.get("inspection_kind", "pre_spray"),
        captured_at=str(snapshot["captured_at"]),
        algorithm_version=str(snapshot.get("algorithm_version") or "unversioned"),
        pest_counts={
            str(name): int(count)
            for name, count in (snapshot.get("pest_counts") or {}).items()
        },
        total_detection_count=int(snapshot.get("total_detection_count") or 0),
        hotspot_cell_count=hotspot_count,
        peak_relative_heat=peak,
        source=str(snapshot.get("source") or "unknown"),
        is_simulated=bool(snapshot.get("is_simulated")),
        legacy=bool(snapshot.get("legacy")),
        created_at=snapshot.get("created_at"),
    )


def _snapshot_detail(snapshot: dict[str, Any]) -> HeatmapSnapshotDetail:
    summary = _snapshot_summary(snapshot)
    return HeatmapSnapshotDetail(
        **summary.model_dump(),
        density_grid=snapshot.get("density_grid") or [],
        density_metadata=snapshot.get("density_metadata") or {},
        image_paths=[str(path) for path in (snapshot.get("image_paths") or [])],
        detections=snapshot.get("detections") or [],
    )


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


async def get_latest_heatmap(
    field_id: str | None = Query(default=None, min_length=1, max_length=120),
) -> HeatmapSnapshotDetail:
    """Return the latest durable snapshot, optionally scoped to one field."""
    snapshot = get_sqlite_store().fetch_latest_heatmap_snapshot(field_id=field_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="未找到热力图快照")
    return _snapshot_detail(snapshot)


async def list_heatmap_snapshots(
    field_id: str | None = Query(default=None, min_length=1, max_length=120),
    request_id: str | None = Query(default=None, min_length=1, max_length=160),
    mission_id: str | None = Query(default=None, min_length=1, max_length=160),
    pest_type: str | None = Query(default=None, min_length=1, max_length=120),
    source: str | None = Query(default=None, min_length=1, max_length=120),
    is_simulated: bool | None = Query(default=None),
    inspection_kind: Literal["pre_spray", "reinspection"] | None = Query(default=None),
    captured_from: datetime | None = Query(default=None),
    captured_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> HeatmapSnapshotListResponse:
    """List durable snapshots using field, pest, time, and provenance filters."""
    captured_from_iso = _utc_iso(captured_from)
    captured_to_iso = _utc_iso(captured_to)
    if captured_from_iso and captured_to_iso and captured_from_iso > captured_to_iso:
        raise HTTPException(
            status_code=422,
            detail="captured_from 不能晚于 captured_to",
        )

    filters = {
        "field_id": field_id,
        "request_id": request_id,
        "mission_id": mission_id,
        "pest_type": pest_type,
        "source": source,
        "is_simulated": is_simulated,
        "inspection_kind": inspection_kind,
        "captured_from": captured_from_iso,
        "captured_to": captured_to_iso,
    }
    store = get_sqlite_store()
    total = store.count_heatmap_snapshots(**filters)
    snapshots = store.fetch_heatmap_snapshots(
        **filters,
        limit=limit,
        offset=offset,
    )
    return HeatmapSnapshotListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_snapshot_summary(snapshot) for snapshot in snapshots],
    )


async def get_heatmap_snapshot(snapshot_id: str) -> HeatmapSnapshotDetail:
    """Return one full snapshot, including read-only legacy conversion."""
    snapshot = get_sqlite_store().fetch_heatmap_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="未找到热力图快照")
    return _snapshot_detail(snapshot)


async def get_heatmap_comparison(
    request_id: str,
    iteration_number: int | None = Query(default=None, ge=1, le=1000),
) -> HeatmapComparisonResponse:
    """Pair a task's pre-spray snapshot with one reinspection snapshot."""
    store = get_sqlite_store()
    pre_spray = store.fetch_heatmap_snapshot_by_request(
        request_id,
        inspection_kind="pre_spray",
    )
    reinspection = store.fetch_heatmap_snapshot_by_request(
        request_id,
        inspection_kind="reinspection",
        iteration_number=iteration_number,
        include_legacy=False,
    )
    if pre_spray is None and reinspection is None:
        raise HTTPException(status_code=404, detail="未找到可对比的热力图快照")

    resolved_iteration = int(
        iteration_number
        or (reinspection or {}).get("iteration_number")
        or 1
    )
    metrics = None
    if pre_spray is not None and reinspection is not None:
        pre_hotspots, pre_peak = _relative_heat_stats(pre_spray)
        post_hotspots, post_peak = _relative_heat_stats(reinspection)
        metrics = HeatmapComparisonMetrics(
            detection_count_change=int(reinspection.get("total_detection_count") or 0)
            - int(pre_spray.get("total_detection_count") or 0),
            hotspot_cell_count_change=post_hotspots - pre_hotspots,
            peak_relative_heat_change=round(post_peak - pre_peak, 6),
        )

    status: Literal["paired", "pending_pre_spray", "pending_reinspection"]
    if pre_spray is None:
        status = "pending_pre_spray"
    elif reinspection is None:
        status = "pending_reinspection"
    else:
        status = "paired"

    return HeatmapComparisonResponse(
        request_id=request_id,
        mission_id=(reinspection or pre_spray or {}).get("mission_id"),
        iteration_number=resolved_iteration,
        status=status,
        pre_spray=_snapshot_detail(pre_spray) if pre_spray else None,
        reinspection=_snapshot_detail(reinspection) if reinspection else None,
        metrics=metrics,
    )


def register_heatmap_routes(app: FastAPI) -> None:
    """Register canonical heatmap routes and hidden /api aliases."""
    app.get("/heatmaps/latest", response_model=HeatmapSnapshotDetail)(get_latest_heatmap)
    app.get(
        "/api/heatmaps/latest",
        include_in_schema=False,
        response_model=HeatmapSnapshotDetail,
    )(get_latest_heatmap)
    app.get(
        "/heatmaps/snapshots",
        response_model=HeatmapSnapshotListResponse,
    )(list_heatmap_snapshots)
    app.get(
        "/api/heatmaps/snapshots",
        include_in_schema=False,
        response_model=HeatmapSnapshotListResponse,
    )(list_heatmap_snapshots)
    app.get(
        "/heatmaps/comparison/{request_id}",
        response_model=HeatmapComparisonResponse,
    )(get_heatmap_comparison)
    app.get(
        "/api/heatmaps/comparison/{request_id}",
        include_in_schema=False,
        response_model=HeatmapComparisonResponse,
    )(get_heatmap_comparison)
    app.get(
        "/heatmaps/snapshots/{snapshot_id}",
        response_model=HeatmapSnapshotDetail,
    )(get_heatmap_snapshot)
    app.get(
        "/api/heatmaps/snapshots/{snapshot_id}",
        include_in_schema=False,
        response_model=HeatmapSnapshotDetail,
    )(get_heatmap_snapshot)
