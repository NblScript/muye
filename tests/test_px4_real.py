"""Tests for modules/drone/px4_real.py (MAVSDK real-vehicle executor).

MAVSDK is mocked — these tests verify the executor's orchestration,
retry/arming logic and route math without requiring hardware.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from modules.drone.px4_real import PX4RealError, PX4RealExecutor


@pytest.fixture
def drone_config() -> dict:
    return {
        "px4": {
            "system_address": "udp://:14540",
            "connect_timeout_seconds": 5,
            "mission_timeout_seconds": 60,
            "arm_retries": 3,
            "arm_retry_delay_seconds": 0.0,
            "allow_force_arm": True,
            "auto_arm": True,
            "auto_start_mission": True,
            "require_global_position": True,
            "return_to_launch_after_mission": True,
            "acceptance_radius_m": 2.0,
        }
    }


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.px4_real")


class _FakeMissionItem:
    class CameraAction:
        NONE = "camera-none"

    class VehicleAction:
        NONE = "vehicle-none"

    def __init__(
        self,
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
        **kwargs,
    ) -> None:
        self.latitude_deg = latitude_deg
        self.longitude_deg = longitude_deg
        self.relative_altitude_m = relative_altitude_m
        self.speed_m_s = speed_m_s
        self.is_fly_through = is_fly_through
        self.loiter_time_s = loiter_time_s
        self.acceptance_radius_m = acceptance_radius_m
        self.yaw_deg = yaw_deg
        self.extra = kwargs


class _FakeMissionPlan:
    def __init__(self, mission_items) -> None:
        self.mission_items = mission_items


class _FakeAction:
    def __init__(self, arm_failures: int = 0) -> None:
        self.arm_calls = 0
        self.force_arm_calls = 0
        self.arm_failures = arm_failures

    async def arm(self) -> None:
        self.arm_calls += 1
        if self.arm_calls <= self.arm_failures:
            raise RuntimeError("COMMAND_DENIED")

    async def arm_force(self) -> None:
        self.force_arm_calls += 1


class _FakeMission:
    def __init__(self) -> None:
        self.upload_calls = 0
        self.start_calls = 0
        self.finished = False
        self.rtl_set: bool | None = None
        self.uploaded_plan: _FakeMissionPlan | None = None

    async def set_return_to_launch_after_mission(self, enabled: bool) -> None:
        self.rtl_set = enabled

    async def upload_mission(self, plan: _FakeMissionPlan) -> None:
        self.upload_calls += 1
        self.uploaded_plan = plan

    async def start_mission(self) -> None:
        self.start_calls += 1
        self.finished = True

    async def is_mission_finished(self) -> bool:
        return self.finished


class _FakeTelemetry:
    def __init__(self) -> None:
        self.health_ok = True

    async def health(self):
        yield SimpleNamespace(
            is_global_position_ok=self.health_ok,
            is_home_position_ok=True,
        )

    async def position(self):
        yield SimpleNamespace(
            latitude_deg=8.54532,
            longitude_deg=47.397622,
            absolute_altitude_m=490.0,
            relative_altitude_m=3.2,
        )
        while True:
            await asyncio.sleep(0.01)


class _FakeCore:
    def __init__(self) -> None:
        self.connected = False

    async def connection_state(self):
        yield SimpleNamespace(is_connected=self.connected)


class _FakeSystem:
    last_instance: "_FakeSystem | None" = None

    def __init__(self) -> None:
        self.core = _FakeCore()
        self.telemetry = _FakeTelemetry()
        self.action = _FakeAction()
        self.mission = _FakeMission()
        _FakeSystem.last_instance = self

    async def connect(self, *, system_address: str) -> None:
        self.system_address = system_address
        self.core.connected = True


def _make_executor(drone_config: dict, logger: logging.Logger) -> PX4RealExecutor:
    return PX4RealExecutor(drone_config, logger=logger)


def _execution_plan() -> dict:
    return {
        "飞行路径": [
            [8.54532, 47.397622],
            [8.545868, 47.397622],
            [8.545868, 47.397646],
        ],
        "高度": 3.2,
        "速度": 4.5,
        "航点控制": {
            "接受半径": 0.15,
            "到点停留秒数": 0.0,
            "飞越航点": False,
            "转弯模式": "in_place",
            "转弯停留秒数": 0.8,
        },
    }


@pytest.mark.asyncio
async def test_execute_spray_mission_full_flow(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    """Happy path: connect -> upload -> arm -> start -> complete."""
    async def fast_sleep(delay: float) -> None:
        del delay

    _FakeSystem.last_instance = None
    monkeypatch.setattr("asyncio.sleep", fast_sleep)
    executor = _make_executor(drone_config, logger)
    monkeypatch.setattr(
        executor,
        "_load_mavsdk",
        lambda: (_FakeSystem, _FakeMissionItem, _FakeMissionPlan),
    )

    statuses: list[str] = []

    def on_status(status: str, message: str, progress: int, waypoint: int, position=None) -> None:
        statuses.append(status)

    result = await executor.execute_spray_mission(
        request_id="req-real-1",
        execution_plan=_execution_plan(),
        medication={},
        current_weather={},
        on_status=on_status,
    )

    drone = _FakeSystem.last_instance
    assert result["execution_mode"] == "real"
    assert result["final_status"] == "completed"
    assert drone is not None
    assert drone.mission.upload_calls == 1
    assert drone.mission.start_calls == 1
    assert drone.action.arm_calls == 1
    assert drone.mission.rtl_set is True
    assert drone.system_address == "udpin://0.0.0.0:14540"
    assert statuses[0] == "connecting"
    assert statuses[-1] == "completed"


@pytest.mark.asyncio
async def test_execute_mission_requires_two_waypoints(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    executor = _make_executor(drone_config, logger)
    monkeypatch.setattr(
        executor,
        "_load_mavsdk",
        lambda: (_FakeSystem, _FakeMissionItem, _FakeMissionPlan),
    )

    with pytest.raises(PX4RealError, match="至少需要两个航点"):
        await executor.execute_spray_mission(
            request_id="req-real-2",
            execution_plan={"飞行路径": [[8.54532, 47.397622]]},
            medication={},
            current_weather={},
        )


@pytest.mark.asyncio
async def test_execute_mission_wraps_import_error(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    def raise_import() -> None:
        raise ImportError("No module named 'mavsdk'")

    executor = _make_executor(drone_config, logger)
    monkeypatch.setattr(executor, "_load_mavsdk", raise_import)

    with pytest.raises(PX4RealError, match="需要安装 mavsdk"):
        await executor.execute_spray_mission(
            request_id="req-real-3",
            execution_plan=_execution_plan(),
            medication={},
            current_weather={},
        )


@pytest.mark.asyncio
async def test_arm_with_retries_succeeds_after_denials(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    executor = _make_executor(drone_config, logger)
    drone = _FakeSystem()
    drone.action = _FakeAction(arm_failures=2)

    await executor._arm_with_retries(
        drone=drone,
        attempts=3,
        retry_delay_seconds=0.0,
        allow_force_arm=True,
    )

    assert drone.action.arm_calls == 3
    assert drone.action.force_arm_calls == 0


@pytest.mark.asyncio
async def test_arm_with_retries_force_arms_when_enabled(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    executor = _make_executor(drone_config, logger)
    drone = _FakeSystem()
    drone.action = _FakeAction(arm_failures=99)

    await executor._arm_with_retries(
        drone=drone,
        attempts=2,
        retry_delay_seconds=0.0,
        allow_force_arm=True,
    )

    assert drone.action.force_arm_calls == 1


@pytest.mark.asyncio
async def test_arm_with_retries_raises_when_force_disabled(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    executor = _make_executor(drone_config, logger)
    drone = _FakeSystem()
    drone.action = _FakeAction(arm_failures=99)

    with pytest.raises(PX4RealError, match="解锁失败"):
        await executor._arm_with_retries(
            drone=drone,
            attempts=1,
            retry_delay_seconds=0.0,
            allow_force_arm=False,
        )


def test_normalize_system_address_handles_legacy_udp(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    executor = _make_executor(drone_config, logger)

    assert executor._normalize_system_address("udp://:14540") == "udpin://0.0.0.0:14540"
    assert executor._normalize_system_address("udp://0.0.0.0:14540") == "udpin://0.0.0.0:14540"
    assert executor._normalize_system_address("udpin://0.0.0.0:14540") == "udpin://0.0.0.0:14540"
    assert executor._normalize_system_address("udpout://127.0.0.1:14580") == "udpout://127.0.0.1:14580"


def test_estimate_mission_duration_adds_safety_buffer(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    executor = _make_executor(drone_config, logger)

    duration = executor._estimate_mission_duration_seconds(
        route=[[0.0, 0.0], [0.0, 0.01], [0.01, 0.01]],
        speed_m_s=10.0,
        loiter_time_s=0.0,
        turn_mode="",
        turn_loiter_time_s=0.0,
    )

    assert duration >= 120.0


def test_resolve_mission_timeout_uses_max(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    executor = _make_executor(drone_config, logger)

    resolved = executor._resolve_mission_timeout_seconds(
        configured_timeout_seconds=30.0,
        route=[[0.0, 0.0], [0.0, 0.1]],
        speed_m_s=1.0,
        loiter_time_s=0.0,
        turn_mode="",
        turn_loiter_time_s=0.0,
    )

    assert resolved >= 30.0


def test_estimate_route_progress_mid_route(drone_config: dict, logger: logging.Logger) -> None:
    executor = _make_executor(drone_config, logger)
    route = [[8.54532, 47.397622], [8.545868, 47.397622]]
    distances = executor._compute_route_cumulative_distances(route)

    progress = executor._estimate_route_progress(
        route=route,
        route_distances=distances,
        position={"longitude": 8.5455, "latitude": 47.397622, "relative_altitude_m": 3.0},
    )

    assert progress is not None
    assert 0.0 < float(progress["distance_ratio"]) < 1.0
    assert progress["current_waypoint_index"] == 1


def test_build_mission_items_skips_unknown_kwargs(
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    executor = _make_executor(drone_config, logger)

    items = executor._build_mission_items(
        MissionItem=_FakeMissionItem,
        route=[[8.54532, 47.397622], [8.545868, 47.397622], [8.545868, 47.397646]],
        altitude_m=3.2,
        speed_m_s=4.5,
        acceptance_radius_m=0.15,
        loiter_time_s=0.0,
        is_fly_through=False,
        turn_mode="in_place",
        turn_loiter_time_s=0.8,
    )

    # 3 waypoints + 1 in-place pivot at the middle waypoint
    assert len(items) == 4
    assert items[0].latitude_deg == 47.397622
    assert items[1].loiter_time_s == 0.0
    assert items[2].loiter_time_s == 0.8
