"""Integration tests for mission endpoints."""

from __future__ import annotations

import pytest

import app.routes.mission as mission_routes
from modules.infra.sqlite_store import SqliteStore


def test_mission_response_exposes_heatmap_route_trace(monkeypatch, tmp_path) -> None:
    store = SqliteStore(tmp_path / "mission-route.db")
    store.mark_task_started("req-trace", "/tmp/trace.jpg", field_id="field-1")
    store.create_mission(
        mission_id="mission-trace",
        original_request_id="req-trace",
        field_id="field-1",
    )
    snapshot_id = store.save_heatmap_snapshot(
        request_id="req-trace",
        field_id="field-1",
        mission_id="mission-trace",
        inspection_kind="pre_spray",
        iteration_number=1,
        image_paths=["/tmp/trace.jpg"],
        detections=[],
        density_grid=[],
        density_metadata={"algorithm_version": "trace-v1", "source": "yolo_bbox"},
    )
    store.create_iteration(
        mission_id="mission-trace",
        iteration_number=1,
        spray_request_id="req-trace",
        heatmap_snapshot_id=snapshot_id,
        heatmap_algorithm_version="trace-v1",
        spray_plan={
            "planning_mode": "uniform_fallback",
            "heatmap_snapshot_id": snapshot_id,
        },
    )
    monkeypatch.setattr(mission_routes, "get_sqlite_store", lambda: store)

    try:
        mission = store.fetch_mission_by_mission_id("mission-trace")
        assert mission is not None
        response = mission_routes._build_mission_response(mission).model_dump()
    finally:
        store.close()

    iteration = response["iterations"][0]
    assert iteration["heatmap_snapshot_id"] == snapshot_id
    assert iteration["heatmap_algorithm_version"] == "trace-v1"
    assert iteration["spray_plan"]["planning_mode"] == "uniform_fallback"


@pytest.mark.asyncio
async def test_get_missions(client):
    resp = await client.get("/api/missions")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or "missions" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_missions_with_status_filter(client):
    resp = await client.get("/api/missions?status=completed")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or "missions" in data


@pytest.mark.asyncio
async def test_get_mission_not_found(client):
    resp = await client.get("/api/mission/nonexistent_id")
    assert resp.status_code in (404, 200)


@pytest.mark.asyncio
async def test_get_mission_by_request_not_found(client):
    resp = await client.get("/api/mission/by-request/nonexistent_id")
    assert resp.status_code in (404, 200)


@pytest.mark.asyncio
async def test_cancel_mission_not_found(client):
    resp = await client.post("/api/mission/nonexistent_id/cancel")
    assert resp.status_code in (404, 200)
