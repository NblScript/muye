from __future__ import annotations

from modules.infra.event_bus import FileEventBus, build_task_views, load_events


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


# ---------------------------------------------------------------------------
# Log rotation tests
# ---------------------------------------------------------------------------


def test_rotation_triggers_when_file_exceeds_limit(tmp_path) -> None:
    """A publish call should rotate the log when the file is already over the limit."""
    target = tmp_path / "events.jsonl"
    # Use a tiny max size so rotation triggers after a single write.
    bus = FileEventBus(target, max_file_size_mb=0.00001, max_backup_files=3)

    # First publish creates the file and writes one event.
    bus.publish(request_id="r1", stage="queue", status="queued", message="first", payload={})
    assert target.exists()
    first_events = load_events(target)
    assert len(first_events) == 1

    # Second publish: file already exceeds the tiny limit → rotation.
    bus.publish(request_id="r2", stage="queue", status="queued", message="second", payload={})

    # Backup .1 should contain the first event.
    backup_1 = tmp_path / "events.jsonl.1"
    assert backup_1.exists()
    assert load_events(backup_1) == first_events

    # Current file should contain only the second event.
    current_events = load_events(target)
    assert len(current_events) == 1
    assert current_events[0]["request_id"] == "r2"


def test_rotation_shifts_backup_indices(tmp_path) -> None:
    """Multiple rotations should shift backup files: .1→.2, .2→.3, …"""
    target = tmp_path / "events.jsonl"
    bus = FileEventBus(target, max_file_size_mb=0.00001, max_backup_files=3)

    for i in range(5):
        bus.publish(request_id=f"r{i}", stage="queue", status="queued", message=f"msg{i}", payload={})

    # After 5 publishes (4 rotations with tiny size), we expect at most 3 backups (.1, .2, .3)
    # plus the current file.
    backup_indices = sorted(
        int(f.name.rsplit(".", 1)[-1])
        for f in tmp_path.iterdir()
        if f.name.startswith("events.jsonl.") and f.name.rsplit(".", 1)[-1].isdigit()
    )
    assert max(backup_indices) <= 3

    # The current file should have the most recent event.
    current_events = load_events(target)
    assert current_events[0]["request_id"] == "r4"


def test_rotation_deletes_oldest_backup_beyond_limit(tmp_path) -> None:
    """When the number of backups exceeds max_backup_files, the oldest is removed."""
    target = tmp_path / "events.jsonl"
    bus = FileEventBus(target, max_file_size_mb=0.00001, max_backup_files=2)

    for i in range(6):
        bus.publish(request_id=f"r{i}", stage="queue", status="queued", message=f"msg{i}", payload={})

    # max_backup_files=2 → only .1 and .2 should exist; .3 must not exist.
    assert not (tmp_path / "events.jsonl.3").exists()
    assert (tmp_path / "events.jsonl.1").exists()
    assert (tmp_path / "events.jsonl.2").exists()


def test_no_rotation_when_file_is_small(tmp_path) -> None:
    """With the default 10 MB limit, a tiny file should not rotate."""
    target = tmp_path / "events.jsonl"
    bus = FileEventBus(target, max_file_size_mb=10.0, max_backup_files=5)

    for i in range(20):
        bus.publish(request_id=f"r{i}", stage="queue", status="queued", message=f"msg{i}", payload={})

    # No backup files should have been created.
    backup_files = [f for f in tmp_path.iterdir() if f.name.startswith("events.jsonl.")]
    assert backup_files == []

    # All 20 events should be in the current file.
    events = load_events(target)
    assert len(events) == 20
