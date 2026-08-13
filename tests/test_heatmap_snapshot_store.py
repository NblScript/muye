from __future__ import annotations

from modules.infra.sqlite_store import SqliteStore


def _metadata(*, simulated: bool = False) -> dict[str, object]:
    return {
        "source": "demo_seed" if simulated else "yolo_bbox",
        "algorithm_version": "demo-v1" if simulated else "relative-bbox-grid-v1",
        "density_kind": "relative_detection_weight",
        "coordinate_space": "image_normalized",
        "projection": "image_frame_to_geofence_bbox",
        "normalization": "max_cell_weight",
        "grid_rows": 1,
        "grid_cols": 2,
        "detection_count": 2,
        "accepted_detection_count": 2,
        "rejected_detection_count": 0,
        "is_simulated": simulated,
    }


def test_heatmap_snapshot_survives_restart_with_mission_association(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    store = SqliteStore(db_path)
    try:
        store.mark_task_started("req-heatmap", "/tmp/field.jpg", field_id="field-1")
        snapshot_id = store.save_heatmap_snapshot(
            request_id="req-heatmap",
            field_id="field-1",
            inspection_kind="pre_spray",
            iteration_number=1,
            image_paths=["/tmp/field.jpg"],
            detections=[
                {
                    "pest_type": "aphid",
                    "confidence": 0.93,
                    "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                },
                {
                    "pest_type": "aphid",
                    "confidence": 0.89,
                    "position": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                },
            ],
            density_grid=[
                {"row": 0, "col": 0, "density": 1.0},
                {"row": 0, "col": 1, "density": 0.0},
            ],
            density_metadata=_metadata(),
        )
        mission_row_id = store.create_mission(
            mission_id="mission-1",
            original_request_id="req-heatmap",
            field_id="field-1",
        )
        assert mission_row_id > 0
        assert store.attach_heatmap_snapshot_to_mission(
            request_id="req-heatmap",
            mission_id="mission-1",
            inspection_kind="pre_spray",
            iteration_number=1,
        ) is True
    finally:
        store.close()

    reopened = SqliteStore(db_path)
    try:
        snapshot = reopened.fetch_heatmap_snapshot(snapshot_id)
        latest = reopened.fetch_latest_heatmap_snapshot(field_id="field-1")
        detection_count = reopened.fetch_one(
            "SELECT COUNT(*) AS total FROM inspection_detections"
        )
    finally:
        reopened.close()

    assert snapshot is not None
    assert snapshot["snapshot_id"] == "heatmap:req-heatmap:pre_spray:1"
    assert snapshot["mission_id"] == "mission-1"
    assert snapshot["field_id"] == "field-1"
    assert snapshot["inspection_kind"] == "pre_spray"
    assert snapshot["algorithm_version"] == "relative-bbox-grid-v1"
    assert snapshot["pest_counts"] == {"aphid": 2}
    assert snapshot["total_detection_count"] == 2
    assert snapshot["image_paths"] == ["/tmp/field.jpg"]
    assert snapshot["detections"][0]["position"] == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}
    assert snapshot["density_grid"][0]["density"] == 1.0
    assert snapshot["legacy"] is False
    assert latest is not None and latest["snapshot_id"] == snapshot["snapshot_id"]
    assert detection_count == {"total": 2}


def test_heatmap_snapshot_upsert_replaces_detection_items(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    try:
        store.mark_task_started("req-upsert", "/tmp/first.jpg")
        for detections in (
            [{"pest_type": "aphid", "confidence": 0.9, "position": {"x": 0.2, "y": 0.3}}],
            [{"pest_type": "whitefly", "confidence": 0.8, "position": {"x": 0.7, "y": 0.6}}],
        ):
            store.save_heatmap_snapshot(
                request_id="req-upsert",
                field_id=None,
                inspection_kind="reinspection",
                iteration_number=2,
                image_paths=["/tmp/second.jpg"],
                detections=detections,
                density_grid=[],
                density_metadata=_metadata(),
            )
        snapshot = store.fetch_heatmap_snapshot_by_request(
            "req-upsert",
            inspection_kind="reinspection",
            iteration_number=2,
        )
        snapshot_count = store.fetch_one("SELECT COUNT(*) AS total FROM heatmap_snapshots")
        detection_count = store.fetch_one(
            "SELECT COUNT(*) AS total FROM inspection_detections"
        )
    finally:
        store.close()

    assert snapshot is not None
    assert snapshot["pest_counts"] == {"whitefly": 1}
    assert snapshot["detections"][0]["pest_type"] == "whitefly"
    assert snapshot_count == {"total": 1}
    assert detection_count == {"total": 1}


def test_legacy_task_density_is_exposed_as_read_only_snapshot(tmp_path) -> None:
    store = SqliteStore(tmp_path / "legacy.db")
    try:
        store.mark_task_started("req-legacy-density", "/tmp/legacy.jpg", field_id="legacy-field")
        store.replace_detections(
            "req-legacy-density",
            [{
                "pest_type": "aphid",
                "confidence": 0.91,
                "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
            }],
        )
        store.add_drone_mission_update(
            "req-legacy-density",
            task_id="legacy-drone",
            status="completed",
            message="legacy",
            instruction={
                "density_grid": [{"row": 0, "col": 0, "density": 1.0}],
                "density_metadata": {"source": "yolo_bbox", "is_simulated": False},
            },
        )
        snapshot = store.fetch_heatmap_snapshot_by_request("req-legacy-density")
        durable_count = store.fetch_one("SELECT COUNT(*) AS total FROM heatmap_snapshots")
    finally:
        store.close()

    assert snapshot is not None
    assert snapshot["snapshot_id"] == "legacy:req-legacy-density"
    assert snapshot["legacy"] is True
    assert snapshot["algorithm_version"] == "legacy-unversioned"
    assert snapshot["pest_counts"] == {"aphid": 1}
    assert snapshot["image_paths"] == ["/tmp/legacy.jpg"]
    assert durable_count == {"total": 0}


def test_heatmap_snapshot_query_filters_and_pagination(tmp_path) -> None:
    store = SqliteStore(tmp_path / "filters.db")
    try:
        for index, (field_id, pest_type, source, simulated) in enumerate(
            [
                ("field-a", "aphid", "yolo_bbox", False),
                ("field-a", "whitefly", "yolo_bbox", False),
                ("field-b", "aphid", "demo_seed", True),
            ],
            start=1,
        ):
            request_id = f"req-filter-{index}"
            store.mark_task_started(request_id, f"/tmp/{index}.jpg", field_id=field_id)
            store.save_heatmap_snapshot(
                request_id=request_id,
                field_id=field_id,
                inspection_kind="pre_spray",
                iteration_number=1,
                captured_at=f"2026-08-0{index}T00:00:00+00:00",
                image_paths=[f"/tmp/{index}.jpg"],
                detections=[{"pest_type": pest_type, "confidence": 0.8}],
                density_grid=[{"density": 0.8}],
                density_metadata={
                    **_metadata(simulated=simulated),
                    "source": source,
                },
            )

        filters = {
            "field_id": "field-a",
            "source": "YOLO_BBOX",
            "is_simulated": False,
            "captured_from": "2026-08-01T12:00:00+00:00",
            "captured_to": "2026-08-03T00:00:00+00:00",
        }
        rows = store.fetch_heatmap_snapshots(**filters, limit=1, offset=0)
        total = store.count_heatmap_snapshots(**filters)
        aphid_total = store.count_heatmap_snapshots(pest_type="APHID")
    finally:
        store.close()

    assert total == 1
    assert rows[0]["snapshot_id"] == "heatmap:req-filter-2:pre_spray:1"
    assert aphid_total == 2
