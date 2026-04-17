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


def test_build_task_views_compacts_drone_timeline() -> None:
    events = [
        {
            "timestamp": "2026-04-16T01:00:00+00:00",
            "request_id": "req-drone-1",
            "stage": "drone",
            "status": "connecting",
            "message": "正在连接 PX4 SITL",
            "payload": {"task_id": "px4-req-dro", "progress": 5, "current_waypoint_index": 0},
        },
        {
            "timestamp": "2026-04-16T01:00:01+00:00",
            "request_id": "req-drone-1",
            "stage": "drone",
            "status": "connected",
            "message": "PX4 SITL 已连接",
            "payload": {"task_id": "px4-req-dro", "progress": 15, "current_waypoint_index": 0},
        },
        {
            "timestamp": "2026-04-16T01:00:02+00:00",
            "request_id": "req-drone-1",
            "stage": "drone",
            "status": "spraying",
            "message": "PX4 正在执行喷洒航线",
            "payload": {"task_id": "px4-req-dro", "progress": 55, "current_waypoint_index": 1},
        },
        {
            "timestamp": "2026-04-16T01:00:03+00:00",
            "request_id": "req-drone-1",
            "stage": "drone",
            "status": "spraying",
            "message": "PX4 正在执行喷洒航线",
            "payload": {"task_id": "px4-req-dro", "progress": 82, "current_waypoint_index": 3},
        },
        {
            "timestamp": "2026-04-16T01:00:04+00:00",
            "request_id": "req-drone-1",
            "stage": "drone",
            "status": "completed",
            "message": "PX4 喷洒任务完成",
            "payload": {"task_id": "px4-req-dro", "progress": 100, "current_waypoint_index": 4},
        },
    ]

    tasks = build_task_views(events)

    assert tasks[0]["drone"]["status"] == "completed"
    assert tasks[0]["drone"]["progress"] == 100
    assert [item["status"] for item in tasks[0]["drone_timeline"]] == [
        "connecting",
        "connected",
        "spraying",
        "completed",
    ]
    assert tasks[0]["drone_timeline"][2]["progress"] == 82
    assert tasks[0]["drone_timeline"][2]["current_waypoint_index"] == 3
