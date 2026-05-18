"""Smoke tests for modules/drone/px4_simulator.py"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from modules.drone.px4_simulator import PX4Simulator, PX4SimulationError


@pytest.fixture
def drone_config() -> dict:
    return {
        "px4": {
            "system_address": "udpin://0.0.0.0:14540",
            "connect_timeout_seconds": 5,
            "mission_timeout_seconds": 60,
            "auto_arm": True,
            "auto_start_mission": True,
            "acceptance_radius_m": 2.0,
        }
    }


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.px4")


def test_px4_simulator_initializes(drone_config: dict, logger: logging.Logger) -> None:
    """Test PX4Simulator can be instantiated."""
    simulator = PX4Simulator(drone_config, logger=logger)

    assert simulator.drone_config == drone_config
    assert simulator.logger == logger


def test_px4_simulator_uses_default_logger(drone_config: dict) -> None:
    """Test PX4Simulator creates default logger if none provided."""
    simulator = PX4Simulator(drone_config)

    assert simulator.logger.name == "muye.px4"


def test_normalize_route_handles_valid_route(drone_config: dict, logger: logging.Logger) -> None:
    """Test route normalization with valid coordinates."""
    simulator = PX4Simulator(drone_config, logger=logger)

    route = [[113.6241, 34.7467], [113.6257, 34.7479], [113.6273, 34.7491]]
    normalized = simulator._normalize_route(route)

    assert len(normalized) == 3
    assert normalized[0] == [113.6241, 34.7467]


def test_normalize_route_filters_invalid_points(drone_config: dict, logger: logging.Logger) -> None:
    """Test route normalization filters out invalid points."""
    simulator = PX4Simulator(drone_config, logger=logger)

    route = [[113.6241, 34.7467], [113.6257], "invalid", [113.6273, 34.7491]]
    normalized = simulator._normalize_route(route)

    assert len(normalized) == 2
    assert normalized[0] == [113.6241, 34.7467]
    assert normalized[1] == [113.6273, 34.7491]


def test_normalize_route_returns_empty_for_non_list(drone_config: dict, logger: logging.Logger) -> None:
    """Test route normalization returns empty for non-list input."""
    simulator = PX4Simulator(drone_config, logger=logger)

    assert simulator._normalize_route("not a list") == []
    assert simulator._normalize_route(None) == []
    assert simulator._normalize_route(123) == []


def test_compute_route_cumulative_distances(drone_config: dict, logger: logging.Logger) -> None:
    """Test cumulative distance calculation."""
    simulator = PX4Simulator(drone_config, logger=logger)

    # Route with known distances
    route = [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    distances = simulator._compute_route_cumulative_distances(route)

    assert len(distances) == 3
    assert distances[0] == 0.0
    assert distances[1] > 0
    assert distances[2] > distances[1]


def test_compute_route_cumulative_distances_empty_route(
    drone_config: dict, logger: logging.Logger
) -> None:
    """Test cumulative distance returns empty for empty route."""
    simulator = PX4Simulator(drone_config, logger=logger)

    assert simulator._compute_route_cumulative_distances([]) == []


def test_estimate_mission_duration_seconds(drone_config: dict, logger: logging.Logger) -> None:
    """Test mission duration estimation."""
    simulator = PX4Simulator(drone_config, logger=logger)

    route = [[0.0, 0.0], [0.0, 0.01], [0.01, 0.01]]
    duration = simulator._estimate_mission_duration_seconds(
        route=route,
        speed_m_s=10.0,
        loiter_time_s=0.0,
        turn_mode="",
        turn_loiter_time_s=0.0,
    )

    # Should include travel time plus 120s buffer
    assert duration >= 120.0


def test_estimate_mission_duration_single_point(drone_config: dict, logger: logging.Logger) -> None:
    """Test mission duration returns default for single point."""
    simulator = PX4Simulator(drone_config, logger=logger)

    duration = simulator._estimate_mission_duration_seconds(
        route=[[0.0, 0.0]],
        speed_m_s=10.0,
        loiter_time_s=0.0,
        turn_mode="",
        turn_loiter_time_s=0.0,
    )

    assert duration == 180.0


def test_project_lon_lat_to_meters(drone_config: dict, logger: logging.Logger) -> None:
    """Test longitude/latitude to meters projection."""
    import math

    simulator = PX4Simulator(drone_config, logger=logger)

    x, y = simulator._project_lon_lat_to_meters(113.0, 34.0, 34.0)

    # x = longitude * 111000 * cos(radians(origin_latitude))
    # y = latitude * 111000
    expected_x = 113.0 * 111000 * math.cos(math.radians(34.0))
    expected_y = 34.0 * 111000
    assert abs(x - expected_x) < 1.0
    assert abs(y - expected_y) < 1.0


def test_px4_default_execution_mode_is_native_mission(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    assert simulator._resolve_execution_mode(drone_config["px4"]) == "native_mission"
    assert simulator._resolve_execution_mode({"execution_mode": "global_mission"}) == "native_mission"
    assert simulator._resolve_execution_mode({"use_existing_mission": True}) == "existing_native_mission"


def test_px4_builds_default_local_route_without_using_plan_coordinates(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    route = simulator._resolve_native_local_route(
        execution_plan={
            "飞行路径": [
                [113.6241, 34.7467],
                [113.6257, 34.7479],
            ],
        },
        px4_config={
            "local_route": {
                "use_planner_shape": True,
                "width_m": 10.0,
                "height_m": 6.0,
                "lane_count": 3,
            }
        },
    )

    assert route == [
        [0.0, 0.0],
        [10.0, 0.0],
        [10.0, 3.0],
        [0.0, 3.0],
        [0.0, 6.0],
        [10.0, 6.0],
    ]


def test_px4_uses_configured_local_route_points(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    route = simulator._resolve_native_local_route(
        execution_plan={},
        px4_config={
            "local_route": {
                "points": [
                    {"east_m": 1.0, "north_m": 2.0},
                    [3.0, 4.0],
                ]
            }
        },
    )

    assert route == [[0.0, 0.0], [1.0, 2.0], [3.0, 4.0]]


def test_px4_uses_demo_explicit_local_route_points(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    route = simulator._resolve_native_local_route(
        execution_plan={"飞行路径": [[113.6241, 34.7467], [113.6257, 34.7479]]},
        px4_config={
            "local_route": {
                "use_planner_shape": False,
                "width_m": 99.0,
                "height_m": 99.0,
                "lane_count": 99,
                "points": [
                    [0.0, 0.0],
                    [12.0, 0.0],
                    [12.0, 2.0],
                    [0.0, 2.0],
                    [0.0, 0.0],
                ],
            }
        },
    )

    assert route == [[0.0, 0.0], [12.0, 0.0], [12.0, 2.0], [0.0, 2.0], [0.0, 0.0]]


def test_px4_anchors_local_route_to_current_position(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    assert simulator._anchor_local_route_to_origin(
        route=[[0.05, 0.0], [0.1, -0.2]],
        origin_east_m=7.0,
        origin_north_m=12.0,
    ) == [[7.05, 12.0], [7.1, 11.8]]


def test_px4_converts_local_route_to_px4_current_global_origin(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    route = simulator._local_route_to_global_route(
        route=[[0.0, 0.0], [12.0, 0.0], [12.0, 8.0]],
        origin_latitude=47.397742,
        origin_longitude=8.545594,
    )

    assert route[0] == [8.545594, 47.397742]
    assert route[1][0] > route[0][0]
    assert route[1][1] == pytest.approx(route[0][1])
    assert route[2][1] > route[1][1]
    assert all(point[0] < 10.0 for point in route)


def test_px4_default_local_route_starts_at_current_position(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    route = simulator._resolve_native_local_route(
        execution_plan={"飞行路径": [[113.6241, 34.7467], [113.6257, 34.7479]]},
        px4_config={"local_route": {"width_m": 12.0, "height_m": 8.0, "lane_count": 5}},
    )

    assert route[0] == [0.0, 0.0]
    assert route == [
        [0.0, 0.0],
        [12.0, 0.0],
        [12.0, 2.0],
        [0.0, 2.0],
        [0.0, 4.0],
        [12.0, 4.0],
        [12.0, 6.0],
        [0.0, 6.0],
        [0.0, 8.0],
        [12.0, 8.0],
    ]


def test_px4_simulation_error_is_runtime_error() -> None:
    """Test PX4SimulationError is a RuntimeError subclass."""
    assert issubclass(PX4SimulationError, RuntimeError)

    error = PX4SimulationError("Test error")
    assert str(error) == "Test error"


@pytest.mark.asyncio
async def test_px4_wait_for_global_position_accepts_home_position(drone_config: dict, logger: logging.Logger) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    class FakeTelemetry:
        async def health(self):
            yield SimpleNamespace(is_global_position_ok=False, is_home_position_ok=False)
            yield SimpleNamespace(is_global_position_ok=False, is_home_position_ok=True)

    class FakeDrone:
        telemetry = FakeTelemetry()

    await simulator._wait_for_global_position(FakeDrone())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_px4_arm_vehicle_force_arms_when_enabled(drone_config: dict, logger: logging.Logger) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    class FakeAction:
        def __init__(self) -> None:
            self.arm_calls = 0
            self.force_arm_calls = 0

        async def arm(self) -> None:
            self.arm_calls += 1
            raise RuntimeError("COMMAND_DENIED")

        async def arm_force(self) -> None:
            self.force_arm_calls += 1

    class FakeDrone:
        def __init__(self) -> None:
            self.action = FakeAction()

    drone = FakeDrone()
    await simulator._arm_vehicle(  # type: ignore[arg-type]
        drone=drone,
        attempts=2,
        retry_delay_seconds=0,
        allow_force_arm=True,
    )

    assert drone.action.arm_calls == 2
    assert drone.action.force_arm_calls == 1


@pytest.mark.asyncio
async def test_px4_arm_vehicle_raises_when_force_arm_disabled(drone_config: dict, logger: logging.Logger) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    class FakeAction:
        async def arm(self) -> None:
            raise RuntimeError("COMMAND_DENIED")

    class FakeDrone:
        def __init__(self) -> None:
            self.action = FakeAction()

    with pytest.raises(PX4SimulationError, match="解锁失败"):
        await simulator._arm_vehicle(  # type: ignore[arg-type]
            drone=FakeDrone(),
            attempts=1,
            retry_delay_seconds=0,
            allow_force_arm=False,
        )


@pytest.mark.asyncio
async def test_px4_simulator_retries_normal_arm(drone_config: dict, logger: logging.Logger) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    class FakeAction:
        def __init__(self) -> None:
            self.arm_calls = 0

        async def arm(self) -> None:
            self.arm_calls += 1
            if self.arm_calls < 3:
                raise RuntimeError("COMMAND_DENIED")

    class FakeDrone:
        def __init__(self) -> None:
            self.action = FakeAction()

    drone = FakeDrone()

    await simulator._arm_with_retries(  # type: ignore[attr-defined]
        drone=drone,
        attempts=3,
        retry_delay_seconds=0,
    )

    assert drone.action.arm_calls == 3


@pytest.mark.asyncio
async def test_px4_simulator_force_arms_when_enabled(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    simulator = PX4Simulator(drone_config, logger=logger)

    class FakeAction:
        def __init__(self) -> None:
            self.arm_calls = 0
            self.force_arm_calls = 0

        async def arm(self) -> None:
            self.arm_calls += 1
            raise RuntimeError("COMMAND_DENIED")

        async def arm_force(self) -> None:
            self.force_arm_calls += 1

    class FakeDrone:
        def __init__(self) -> None:
            self.action = FakeAction()

    drone = FakeDrone()

    await simulator._arm_vehicle(  # type: ignore[attr-defined]
        drone=drone,
        attempts=2,
        retry_delay_seconds=0,
        allow_force_arm=True,
    )

    assert drone.action.arm_calls == 2
    assert drone.action.force_arm_calls == 1


class _FakeMissionItem:
    class CameraAction:
        NONE = "camera-none"

    class VehicleAction:
        NONE = "vehicle-none"
        TAKEOFF = "takeoff"

    def __init__(
        self,
        *,
        latitude_deg: float,
        longitude_deg: float,
        relative_altitude_m: float,
        speed_m_s: float,
        is_fly_through: bool,
        gimbal_pitch_deg: float,
        gimbal_yaw_deg: float,
        camera_action: str,
        loiter_time_s: float,
        camera_photo_interval_s: float,
        acceptance_radius_m: float,
        yaw_deg: float,
        camera_photo_distance_m: float,
        vehicle_action: str,
    ) -> None:
        self.latitude_deg = latitude_deg
        self.longitude_deg = longitude_deg
        self.relative_altitude_m = relative_altitude_m
        self.speed_m_s = speed_m_s
        self.is_fly_through = is_fly_through
        self.gimbal_pitch_deg = gimbal_pitch_deg
        self.gimbal_yaw_deg = gimbal_yaw_deg
        self.camera_action = camera_action
        self.loiter_time_s = loiter_time_s
        self.camera_photo_interval_s = camera_photo_interval_s
        self.acceptance_radius_m = acceptance_radius_m
        self.yaw_deg = yaw_deg
        self.camera_photo_distance_m = camera_photo_distance_m
        self.vehicle_action = vehicle_action


class _FakeMissionPlan:
    def __init__(self, mission_items: list[_FakeMissionItem]) -> None:
        self.mission_items = mission_items


class _FakeOffboard:
    def __init__(self) -> None:
        self.start_calls = 0

    async def start(self) -> None:
        self.start_calls += 1


class _FakeMission:
    def __init__(self) -> None:
        self.upload_calls = 0
        self.download_calls = 0
        self.uploaded_plan: _FakeMissionPlan | None = None
        self.start_calls = 0
        self.finished = False
        self.existing_plan = _FakeMissionPlan([_FakeMissionItem(
            latitude_deg=47.397742,
            longitude_deg=8.545594,
            relative_altitude_m=2.0,
            speed_m_s=1.0,
            is_fly_through=True,
            gimbal_pitch_deg=0.0,
            gimbal_yaw_deg=0.0,
            camera_action=_FakeMissionItem.CameraAction.NONE,
            loiter_time_s=0.0,
            camera_photo_interval_s=0.0,
            acceptance_radius_m=2.0,
            yaw_deg=0.0,
            camera_photo_distance_m=0.0,
            vehicle_action=_FakeMissionItem.VehicleAction.NONE,
        ) for _ in range(4)])

    async def upload_mission(self, mission_plan: _FakeMissionPlan) -> None:
        self.upload_calls += 1
        self.uploaded_plan = mission_plan

    async def download_mission(self) -> _FakeMissionPlan:
        self.download_calls += 1
        return self.existing_plan

    async def start_mission(self) -> None:
        self.start_calls += 1
        self.finished = True

    async def is_mission_finished(self) -> bool:
        return self.finished

    async def mission_progress(self):
        yield SimpleNamespace(current=1, total=2)
        yield SimpleNamespace(current=2, total=2)


class _FakeAction:
    def __init__(self) -> None:
        self.arm_calls = 0
        self.return_calls = 0
        self.takeoff_calls = 0
        self.takeoff_altitude = None

    async def arm(self) -> None:
        self.arm_calls += 1

    async def set_takeoff_altitude(self, altitude_m: float) -> None:
        self.takeoff_altitude = altitude_m

    async def takeoff(self) -> None:
        self.takeoff_calls += 1

    async def return_to_launch(self) -> None:
        self.return_calls += 1


class _FakeCore:
    async def connection_state(self):
        yield SimpleNamespace(is_connected=True)


class _FakeTelemetry:
    def __init__(self) -> None:
        self.position_calls = 0

    async def health(self):
        yield SimpleNamespace(
            is_global_position_ok=True,
            is_home_position_ok=True,
            is_local_position_ok=True,
            is_armable=True,
        )

    async def position(self):
        self.position_calls += 1
        if self.position_calls == 1:
            yield SimpleNamespace(
                latitude_deg=47.397742,
                longitude_deg=8.545594,
                absolute_altitude_m=488.0,
                relative_altitude_m=0.0,
            )
            return
        yield SimpleNamespace(
            latitude_deg=47.397742,
            longitude_deg=8.545594,
            absolute_altitude_m=488.0,
            relative_altitude_m=1.8,
        )
        yield SimpleNamespace(
            latitude_deg=47.397742,
            longitude_deg=8.545594,
            absolute_altitude_m=490.0,
            relative_altitude_m=2.0,
        )
        yield SimpleNamespace(
            latitude_deg=47.397742,
            longitude_deg=8.545594,
            absolute_altitude_m=490.0,
            relative_altitude_m=2.0,
        )


class _FakeSystem:
    last_instance: "_FakeSystem | None" = None

    def __init__(self) -> None:
        self.core = _FakeCore()
        self.telemetry = _FakeTelemetry()
        self.offboard = _FakeOffboard()
        self.mission = _FakeMission()
        self.action = _FakeAction()
        _FakeSystem.last_instance = self

    async def connect(self, *, system_address: str) -> None:
        self.system_address = system_address


@pytest.mark.asyncio
async def test_px4_native_mission_uploads_px4_mission_items(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    async def fast_sleep(delay: float) -> None:
        del delay

    _FakeSystem.last_instance = None
    config = {
        "px4": {
            **drone_config["px4"],
            "auto_arm": True,
            "auto_start_mission": True,
            "require_global_position": True,
            "return_to_launch_after_mission": True,
            "mission_timeout_seconds": 5,
            "execution_mode": "native_mission",
            "local_route": {
                "altitude_m": 2.0,
                "max_altitude_m": 2.0,
                "points": [[0.0, 0.0], [12.0, 0.0], [12.0, 8.0]],
            },
        }
    }
    simulator = PX4Simulator(config, logger=logger)
    monkeypatch.setattr(
        simulator,
        "_load_mavsdk",
        lambda: (_FakeSystem, _FakeMissionItem, _FakeMissionPlan),
    )
    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    result = await simulator.execute_spray_mission(
        request_id="req-mission-1",
        execution_plan={
            "飞行路径": [
                [113.6241, 34.7467],
                [113.6257, 34.7479],
            ],
            "高度": 3.0,
            "速度": 1.0,
            "喷洒速率": 1.0,
            "气象限制": {},
            "覆盖区域": {"coordinates": []},
        },
        medication={},
        current_weather={},
    )
    drone = _FakeSystem.last_instance

    assert result["execution_mode"] == "native_mission"
    assert drone is not None
    assert drone.mission.upload_calls == 1
    assert drone.mission.start_calls == 1
    assert drone.offboard.start_calls == 0
    assert drone.action.arm_calls == 1
    assert drone.action.takeoff_calls == 1
    assert drone.action.takeoff_altitude == pytest.approx(2.0)
    assert drone.action.return_calls == 1
    assert drone.mission.uploaded_plan is not None
    items = drone.mission.uploaded_plan.mission_items
    assert len(items) == 3
    assert items[0].vehicle_action == _FakeMissionItem.VehicleAction.NONE
    assert items[0].latitude_deg == pytest.approx(47.397742)
    assert items[0].longitude_deg == pytest.approx(8.545594)
    assert items[1].longitude_deg > items[0].longitude_deg
    assert items[2].latitude_deg > items[1].latitude_deg
    assert all(item.relative_altitude_m == pytest.approx(2.0) for item in items)
    assert all(abs(item.longitude_deg - 113.0) > 1.0 for item in items)


@pytest.mark.asyncio
async def test_px4_existing_native_mission_starts_without_upload(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    async def fast_sleep(delay: float) -> None:
        del delay

    _FakeSystem.last_instance = None
    config = {
        "px4": {
            **drone_config["px4"],
            "auto_arm": True,
            "auto_start_mission": True,
            "require_global_position": True,
            "return_to_launch_after_mission": False,
            "mission_timeout_seconds": 5,
            "execution_mode": "native_mission",
            "use_existing_mission": True,
            "require_existing_mission": True,
        }
    }
    simulator = PX4Simulator(config, logger=logger)
    monkeypatch.setattr(
        simulator,
        "_load_mavsdk",
        lambda: (_FakeSystem, _FakeMissionItem, _FakeMissionPlan),
    )
    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    result = await simulator.execute_spray_mission(
        request_id="req-existing-mission",
        execution_plan={
            "飞行路径": [[113.6241, 34.7467], [113.6257, 34.7479]],
            "高度": 3.0,
            "速度": 1.0,
            "喷洒速率": 1.0,
            "气象限制": {},
            "覆盖区域": {"coordinates": []},
        },
        medication={},
        current_weather={},
    )
    drone = _FakeSystem.last_instance

    assert result["execution_mode"] == "existing_native_mission"
    assert drone is not None
    assert drone.mission.download_calls == 1
    assert drone.mission.upload_calls == 0
    assert drone.mission.start_calls == 1
    assert drone.offboard.start_calls == 0
    assert drone.action.arm_calls == 1
    assert drone.action.takeoff_calls == 0


@pytest.mark.asyncio
async def test_px4_existing_native_mission_fails_when_qgc_mission_missing(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    class EmptyMissionSystem(_FakeSystem):
        def __init__(self) -> None:
            super().__init__()
            self.mission.existing_plan = _FakeMissionPlan([])

    async def fast_sleep(delay: float) -> None:
        del delay

    config = {
        "px4": {
            **drone_config["px4"],
            "auto_arm": True,
            "auto_start_mission": True,
            "require_global_position": True,
            "return_to_launch_after_mission": False,
            "mission_timeout_seconds": 5,
            "execution_mode": "native_mission",
            "use_existing_mission": True,
            "require_existing_mission": True,
        }
    }
    simulator = PX4Simulator(config, logger=logger)
    monkeypatch.setattr(
        simulator,
        "_load_mavsdk",
        lambda: (EmptyMissionSystem, _FakeMissionItem, _FakeMissionPlan),
    )
    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    with pytest.raises(PX4SimulationError, match="没有已上传 Mission 航点"):
        await simulator.execute_spray_mission(
            request_id="req-existing-mission-empty",
            execution_plan={
                "飞行路径": [[113.6241, 34.7467], [113.6257, 34.7479]],
                "高度": 3.0,
                "速度": 1.0,
                "喷洒速率": 1.0,
                "气象限制": {},
                "覆盖区域": {"coordinates": []},
            },
            medication={},
            current_weather={},
        )
