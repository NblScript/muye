from __future__ import annotations

from modules.event_bus import FileEventBus, build_task_views, load_events


def test_file_event_bus_publishes_and_loads_events(tmp_path) -> None:
    bus = FileEventBus(tmp_path / "events.jsonl")
    bus.publish(
        request_id="req-1",
        stage="queue",
        status="queued",
        message="图片已进入处理队列",
        payload={"image_path": "/tmp/a.jpg"},
    )
    bus.publish(
        request_id="req-1",
        stage="yolo",
        status="completed",
        message="YOLO 完成",
        payload={"detections": [{"pest_type": "aphid", "confidence": 0.88}]},
    )

    events = load_events(tmp_path / "events.jsonl")
    tasks = build_task_views(events)

    assert len(events) == 2
    assert tasks[0]["request_id"] == "req-1"
    assert tasks[0]["image_path"] == "/tmp/a.jpg"
    assert tasks[0]["detections"][0]["pest_type"] == "aphid"


def test_file_event_bus_clear(tmp_path) -> None:
    target = tmp_path / "events.jsonl"
    bus = FileEventBus(target)
    bus.publish(
        request_id="req-1",
        stage="pipeline",
        status="running",
        message="开始处理",
        payload={},
    )
    bus.clear()

    assert load_events(target) == []
