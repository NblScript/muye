from __future__ import annotations

import asyncio
import logging

from app.config_types import MuyeConfig
from app.mission_manager import MissionManager
from modules.infra.event_bus import FileEventBus
from modules.infra.sqlite_store import SqliteStore, utc_now_iso


def test_reinspection_persists_heatmap_snapshot_with_iteration_link(tmp_path) -> None:
    image_path = tmp_path / "reinspection.jpg"
    image_path.write_bytes(b"inspection")
    store = SqliteStore(tmp_path / "muye.db")
    store.mark_task_started("req-mission", str(image_path), field_id="field-1")
    store.create_mission(
        mission_id="mission-heatmap",
        original_request_id="req-mission",
        field_id="field-1",
    )
    evaluation_id = store.create_evaluation(
        original_request_id="req-mission",
        scheduled_at=utc_now_iso(),
        action_time_hours=24,
        pre_pest_count=2,
    )
    iteration_id = store.create_iteration(
        mission_id="mission-heatmap",
        iteration_number=1,
        spray_request_id="req-mission",
    )
    store.update_iteration(iteration_id, evaluation_id=evaluation_id, status="spraying")

    class FakeDroneController:
        def plan_inspection_mission(self, **kwargs):
            return {"飞行路径": [[113.62, 34.74], [113.63, 34.75]]}

        async def execute_inspection_mission(self, **kwargs):
            return {"captured_images": [str(image_path)]}

    async def detect_pests(*args, **kwargs):
        return [{
            "pest_type": "aphid",
            "confidence": 0.88,
            "position": {
                "x1": 64,
                "y1": 48,
                "x2": 128,
                "y2": 96,
                "coordinate_space": "image_pixel",
                "image_width": 640,
                "image_height": 480,
            },
        }]

    manager = MissionManager(
        config=MuyeConfig(sqlite_path=tmp_path / "muye.db", rag_enabled=False),
        sqlite_store=store,
        event_bus=FileEventBus(tmp_path / "events.jsonl"),
        drone_controller=FakeDroneController(),
        image_processor=None,
        logger=logging.getLogger("test.mission.heatmap"),
        client_ip="127.0.0.1",
        background_tasks=set(),
        detect_pests_fn=detect_pests,
    )
    context = {
        "image_path": image_path,
        "field_context": {
            "field_id": "field-1",
            "geofence": [
                [113.62, 34.74],
                [113.63, 34.74],
                [113.63, 34.75],
                [113.62, 34.75],
            ],
        },
        "detections": [
            {"pest_type": "aphid", "confidence": 0.9},
            {"pest_type": "aphid", "confidence": 0.85},
        ],
        "weather": {},
    }

    try:
        kill_rate = asyncio.run(
            manager._run_single_evaluation(
                context,
                "req-mission",
                "mission-heatmap",
                iteration_number=1,
            )
        )
        snapshot = store.fetch_heatmap_snapshot_by_request(
            "req-mission",
            inspection_kind="reinspection",
            iteration_number=1,
        )
    finally:
        store.close()

    assert kill_rate == 0.5
    assert snapshot is not None
    assert snapshot["mission_id"] == "mission-heatmap"
    assert snapshot["iteration_number"] == 1
    assert snapshot["inspection_kind"] == "reinspection"
    assert snapshot["image_paths"] == [str(image_path)]
    assert snapshot["detections"][0]["image_path"] == str(image_path)
    assert snapshot["pest_counts"] == {"aphid": 1}
    assert snapshot["density_metadata"]["accepted_detection_count"] == 1
    assert context["latest_heatmap_snapshot_id"] == snapshot["snapshot_id"]
    assert len(context["detections"]) == 1


def test_retry_spray_consumes_previous_reinspection_snapshot(tmp_path) -> None:
    image_path = tmp_path / "retry.jpg"
    image_path.write_bytes(b"inspection")
    store = SqliteStore(tmp_path / "retry.db")
    store.mark_task_started("req-retry", str(image_path), field_id="field-1")
    store.create_mission(
        mission_id="mission-retry",
        original_request_id="req-retry",
        field_id="field-1",
    )
    detections = [{
        "pest_type": "aphid",
        "confidence": 0.9,
        "position": {
            "x1": 64,
            "y1": 48,
            "x2": 128,
            "y2": 96,
            "coordinate_space": "image_pixel",
            "image_width": 640,
            "image_height": 480,
        },
    }]
    density_metadata = {
        "source": "yolo_bbox",
        "algorithm_version": "relative-bbox-grid-v1",
        "accepted_detection_count": 1,
    }
    snapshot_id = store.save_heatmap_snapshot(
        request_id="req-retry",
        field_id="field-1",
        mission_id="mission-retry",
        inspection_kind="reinspection",
        iteration_number=1,
        image_paths=[str(image_path)],
        detections=detections,
        density_grid=[{"row": 0, "col": 0, "density": 1.0, "bounds": [[0, 0], [1, 1]]}],
        density_metadata=density_metadata,
    )

    class FakePlanner:
        def plan_variable_rate_mission(self, **kwargs):
            return {
                "喷洒速率": 1.0,
                "density_grid": [{"row": 0, "col": 0, "density": 1.0}],
                "spray_schedule": [1.5],
                "source": "system_planner_variable_rate",
            }

    class FakeDroneController:
        planner = FakePlanner()

        def __init__(self) -> None:
            self.executed_plan = None

        def plan_spray_mission(self, **kwargs):
            return {"喷洒速率": 1.0, "source": "system_planner"}

        async def execute_spray_mission(self, **kwargs):
            self.executed_plan = kwargs["execution_plan"]
            return {"status": "completed"}

    controller = FakeDroneController()
    manager = MissionManager(
        config=MuyeConfig(
            sqlite_path=tmp_path / "retry.db",
            rag_enabled=False,
            evaluation_demo_delay_seconds=0,
        ),
        sqlite_store=store,
        event_bus=FileEventBus(tmp_path / "retry-events.jsonl"),
        drone_controller=controller,
        image_processor=None,
        logger=logging.getLogger("test.mission.retry.trace"),
        client_ip="127.0.0.1",
        background_tasks=set(),
        detect_pests_fn=lambda *args, **kwargs: None,
    )
    context = {
        "image_path": image_path,
        "field_context": {
            "field_id": "field-1",
            "geofence": [[0, 0], [1, 0], [1, 1], [0, 1]],
        },
        "decision": {"用药": {"农药名称": "吡虫啉"}},
        "detections": detections,
        "weather": {},
        "action_hours": 24,
        "latest_heatmap_snapshot_id": snapshot_id,
        "latest_heatmap_metadata": density_metadata,
    }

    async def fake_evaluation(*args, **kwargs):
        return 0.95

    manager._run_single_evaluation = fake_evaluation  # type: ignore[method-assign]

    try:
        kill_rate = asyncio.run(
            manager._execute_mission_iteration(
                context,
                "req-retry",
                "mission-retry",
                iteration_number=2,
            )
        )
        iteration = store.fetch_latest_iteration("mission-retry")
    finally:
        store.close()

    assert kill_rate == 0.95
    assert iteration is not None
    assert iteration["heatmap_snapshot_id"] == snapshot_id
    assert iteration["heatmap_algorithm_version"] == "relative-bbox-grid-v1"
    assert iteration["spray_plan"]["planning_mode"] == "variable_rate"
    assert controller.executed_plan["heatmap_snapshot_id"] == snapshot_id
