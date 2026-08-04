"""Contract tests for durable insect heatmap query endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.services.workflow_service as workflow_service


def _metadata(*, source: str, simulated: bool = False) -> dict[str, object]:
    return {
        "source": source,
        "algorithm_version": "relative-bbox-grid-v1",
        "density_kind": "relative_detection_weight",
        "coordinate_space": "image_normalized",
        "projection": "image_frame_to_geofence_bbox",
        "normalization": "max_cell_weight",
        "grid_rows": 1,
        "grid_cols": 2,
        "accepted_detection_count": 1,
        "is_simulated": simulated,
    }


@pytest_asyncio.fixture()
async def heatmap_client(tmp_path, monkeypatch):
    db_path = tmp_path / "heatmap-api.db"
    monkeypatch.setenv("MUYE_SQLITE_PATH", str(db_path))
    workflow_service.reset_sqlite_store()
    store = workflow_service.get_sqlite_store()

    store.mark_task_started("req-paired", "/tmp/pre.jpg", field_id="field-a")
    store.save_heatmap_snapshot(
        request_id="req-paired",
        field_id="field-a",
        inspection_kind="pre_spray",
        iteration_number=1,
        captured_at="2026-08-01T08:00:00+00:00",
        image_paths=["/tmp/pre.jpg"],
        detections=[
            {"pest_type": "aphid", "confidence": 0.93, "position": {"x": 0.2}},
            {"pest_type": "aphid", "confidence": 0.88, "position": {"x": 0.6}},
        ],
        density_grid=[
            {"row": 0, "col": 0, "density": 1.0},
            {"row": 0, "col": 1, "density": 0.2},
        ],
        density_metadata=_metadata(source="yolo_bbox"),
    )
    store.create_mission(
        mission_id="mission-paired",
        original_request_id="req-paired",
        field_id="field-a",
    )
    store.attach_heatmap_snapshot_to_mission(
        request_id="req-paired",
        mission_id="mission-paired",
        inspection_kind="pre_spray",
        iteration_number=1,
    )
    store.save_heatmap_snapshot(
        request_id="req-paired",
        field_id="field-a",
        mission_id="mission-paired",
        inspection_kind="reinspection",
        iteration_number=1,
        captured_at="2026-08-02T08:00:00+00:00",
        image_paths=["/tmp/post.jpg"],
        detections=[
            {"pest_type": "aphid", "confidence": 0.71, "position": {"x": 0.4}},
        ],
        density_grid=[
            {"row": 0, "col": 0, "density": 0.4},
            {"row": 0, "col": 1, "density": 0.1},
        ],
        density_metadata=_metadata(source="yolo_bbox"),
    )

    store.mark_task_started("req-demo", "/tmp/demo.jpg", field_id="field-b")
    store.save_heatmap_snapshot(
        request_id="req-demo",
        field_id="field-b",
        inspection_kind="pre_spray",
        iteration_number=1,
        captured_at="2026-08-03T08:00:00+00:00",
        image_paths=["/tmp/demo.jpg"],
        detections=[
            {"pest_type": "thrips", "confidence": 0.82, "position": {"x": 0.5}},
        ],
        density_grid=[{"row": 0, "col": 0, "density": 0.8}],
        density_metadata=_metadata(source="demo_seed", simulated=True),
    )

    store.mark_task_started("req-legacy", "/tmp/legacy.jpg", field_id="field-legacy")
    store.replace_detections(
        "req-legacy",
        [{"pest_type": "whitefly", "confidence": 0.77, "position": {"x": 0.4}}],
    )
    store.add_drone_mission_update(
        "req-legacy",
        task_id="legacy-drone",
        status="completed",
        message="legacy",
        instruction={
            "density_grid": [{"row": 0, "col": 0, "density": 0.7}],
            "density_metadata": {"source": "legacy_yolo", "is_simulated": False},
        },
    )

    from app.main import api_app

    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    workflow_service.reset_sqlite_store()


@pytest.mark.asyncio
async def test_latest_heatmap_supports_global_and_field_scope(heatmap_client):
    response = await heatmap_client.get("/heatmaps/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req-demo"
    assert data["source"] == "demo_seed"
    assert data["is_simulated"] is True

    response = await heatmap_client.get("/api/heatmaps/latest", params={"field_id": "field-a"})
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req-paired"
    assert data["inspection_kind"] == "reinspection"
    assert data["peak_relative_heat"] == 0.4
    assert data["density_grid"][0]["density"] == 0.4


@pytest.mark.asyncio
async def test_heatmap_list_combines_filters_and_paginates(heatmap_client):
    response = await heatmap_client.get(
        "/heatmaps/snapshots",
        params={
            "field_id": "field-a",
            "pest_type": "APHID",
            "source": "YOLO_BBOX",
            "is_simulated": "false",
            "captured_from": "2026-08-01T12:00:00+00:00",
            "captured_to": "2026-08-03T00:00:00+00:00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["inspection_kind"] == "reinspection"
    assert data["items"][0]["pest_counts"] == {"aphid": 1}
    assert "density_grid" not in data["items"][0]

    page = await heatmap_client.get(
        "/api/heatmaps/snapshots",
        params={"limit": 1, "offset": 1},
    )
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert page.json()["items"][0]["snapshot_id"] == "heatmap:req-paired:reinspection:1"


@pytest.mark.asyncio
async def test_heatmap_list_validates_boundaries_and_unknown_pest_is_empty(heatmap_client):
    empty = await heatmap_client.get(
        "/heatmaps/snapshots",
        params={"pest_type": "unknown-pest"},
    )
    assert empty.status_code == 200
    assert empty.json()["total"] == 0
    assert empty.json()["items"] == []

    invalid_range = await heatmap_client.get(
        "/heatmaps/snapshots",
        params={
            "captured_from": "2026-08-04T00:00:00Z",
            "captured_to": "2026-08-01T00:00:00Z",
        },
    )
    assert invalid_range.status_code == 422
    assert "captured_from" in invalid_range.json()["detail"]

    invalid_kind = await heatmap_client.get(
        "/heatmaps/snapshots",
        params={"inspection_kind": "other"},
    )
    assert invalid_kind.status_code == 422

    invalid_page = await heatmap_client.get(
        "/heatmaps/snapshots",
        params={"limit": 0},
    )
    assert invalid_page.status_code == 422


@pytest.mark.asyncio
async def test_heatmap_detail_supports_durable_and_read_only_legacy_ids(heatmap_client):
    durable = await heatmap_client.get(
        "/heatmaps/snapshots/heatmap:req-paired:pre_spray:1"
    )
    assert durable.status_code == 200
    assert durable.json()["legacy"] is False
    assert len(durable.json()["detections"]) == 2

    legacy = await heatmap_client.get("/api/heatmaps/snapshots/legacy:req-legacy")
    assert legacy.status_code == 200
    assert legacy.json()["legacy"] is True
    assert legacy.json()["algorithm_version"] == "legacy-unversioned"
    assert legacy.json()["pest_counts"] == {"whitefly": 1}

    missing = await heatmap_client.get("/heatmaps/snapshots/missing")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_heatmap_comparison_returns_pair_metrics_and_pending_state(heatmap_client):
    paired = await heatmap_client.get("/heatmaps/comparison/req-paired")
    assert paired.status_code == 200
    data = paired.json()
    assert data["status"] == "paired"
    assert data["mission_id"] == "mission-paired"
    assert data["pre_spray"]["total_detection_count"] == 2
    assert data["reinspection"]["total_detection_count"] == 1
    assert data["metrics"] == {
        "detection_count_change": -1,
        "hotspot_cell_count_change": -1,
        "peak_relative_heat_change": -0.6,
    }

    pending = await heatmap_client.get("/api/heatmaps/comparison/req-demo")
    assert pending.status_code == 200
    assert pending.json()["status"] == "pending_reinspection"
    assert pending.json()["metrics"] is None

    missing = await heatmap_client.get("/heatmaps/comparison/does-not-exist")
    assert missing.status_code == 404
