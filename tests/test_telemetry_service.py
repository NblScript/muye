from __future__ import annotations

from app.services.telemetry_service import TelemetryBuffer, TelemetryService
from models.schemas import DroneStatusEnum, GPSPosition


def test_telemetry_buffer_keeps_recent_points_and_accumulates_distance() -> None:
    buffer = TelemetryBuffer(max_points=500)

    for index in range(12):
        buffer.add_point(
            GPSPosition(
                latitude=34.0,
                longitude=113.0 + index * 0.0001,
                altitude=5.0,
                timestamp=1000.0 + index,
            )
        )

    trajectory = buffer.to_trajectory_state()

    assert len(trajectory.recent_points) == 10
    assert trajectory.recent_points[0].longitude == 113.0002
    assert trajectory.recent_points[-1].longitude == 113.0011
    assert 100.0 < trajectory.total_distance < 103.0


def test_telemetry_service_updates_drone_state_from_px4_position_and_resets_for_new_task() -> None:
    service = TelemetryService()

    service.update_from_drone_status(
        request_id="req-1",
        task_id="task-1",
        status="spraying",
        message="PX4 正在沿预设航线飞行",
        progress=60,
        current_waypoint_index=2,
        position={
            "latitude": 34.123,
            "longitude": 113.456,
            "relative_altitude_m": 6.5,
            "absolute_altitude_m": 106.5,
            "heading": 92.0,
            "speed": 4.2,
            "battery_remaining": 83.0,
            "voltage": 15.7,
        },
    )

    assert service.current_state is not None
    assert service.current_state.status == DroneStatusEnum.SPRAYING
    assert service.current_state.position is not None
    assert service.current_state.position.latitude == 34.123
    assert service.current_state.position.heading == 92.0
    assert service.current_state.telemetry.speed == 4.2
    assert service.current_state.battery.remaining == 83.0
    assert len(service.get_trajectory_state().recent_points) == 1

    service.update_from_drone_status(
        request_id="req-2",
        task_id="task-2",
        status="ready",
        message="新任务就绪",
        progress=0,
        current_waypoint_index=0,
        position=None,
    )

    assert service.current_state is not None
    assert service.current_state.id == "task-2"
    assert service.current_state.status == DroneStatusEnum.READY
    assert service.get_trajectory_state().recent_points == []
    assert service.get_trajectory_state().total_distance == 0.0
