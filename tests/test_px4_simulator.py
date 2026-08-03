"""Smoke tests for modules/drone/px4_simulator.py

PX4Simulator was refactored into a pure animation demo player for the fixed
PX4 route (competition-stability focused). These tests cover the current
animation implementation and its pure helper methods.
"""

from __future__ import annotations

import logging

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
            "demo_field": {
                "location": {"longitude": 8.545594, "latitude": 47.397742},
                "explicit_route": [[0.0, 0.0], [1.0, 0.0]],
            },
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


def test_resolve_step_delay_seconds_bounded(
    drone_config: dict, logger: logging.Logger
) -> None:
    """Test step delay is bounded between 0.22s and 1.1s."""
    simulator = PX4Simulator(drone_config, logger=logger)

    long_route = [[0.0, 0.0], [0.0, 0.1], [0.1, 0.1], [0.1, 0.2]]
    delay = simulator._resolve_step_delay_seconds(route=long_route, speed_m_s=0.5)

    assert 0.22 <= delay <= 1.1


def test_distance_between_route_points(drone_config: dict, logger: logging.Logger) -> None:
    """Test distance between two route points is positive and symmetric."""
    simulator = PX4Simulator(drone_config, logger=logger)

    a = [8.545594, 47.397742]
    b = [8.545694, 47.397742]
    d_ab = simulator._distance_between_route_points(a, b)
    d_ba = simulator._distance_between_route_points(b, a)

    assert d_ab > 0
    assert d_ab == pytest.approx(d_ba)


def test_route_point_to_world_xy_origin(drone_config: dict, logger: logging.Logger) -> None:
    """Test world-projection maps the demo origin to (0, 0)."""
    simulator = PX4Simulator(drone_config, logger=logger)

    x, y = simulator._route_point_to_world_xy(8.545594, 47.397742)

    assert x == pytest.approx(0.0, abs=1e-3)
    assert y == pytest.approx(0.0, abs=1e-3)


def test_px4_simulation_error_is_runtime_error() -> None:
    """Test PX4SimulationError is a RuntimeError subclass."""
    assert issubclass(PX4SimulationError, RuntimeError)

    error = PX4SimulationError("Test error")
    assert str(error) == "Test error"


def test_heading_between(drone_config: dict, logger: logging.Logger) -> None:
    """Heading between two points: east moves is 90 deg (lon-first order)."""
    simulator = PX4Simulator(drone_config, logger=logger)

    east = simulator._heading_between([0.0, 0.0], [0.0001, 0.0])
    north = simulator._heading_between([0.0, 0.0], [0.0, 0.0001])
    same = simulator._heading_between([0.0, 0.0], [0.0, 0.0])

    assert east == pytest.approx(90.0, abs=1.0)
    assert north == pytest.approx(0.0, abs=1.0)
    assert same == 0.0


def test_interpolate_heading_shortest_path(drone_config: dict, logger: logging.Logger) -> None:
    """Heading interpolation takes the shortest turn."""
    simulator = PX4Simulator(drone_config, logger=logger)

    assert simulator._interpolate_heading(10.0, 20.0, 0.5) == pytest.approx(15.0)
    interpolated = simulator._interpolate_heading(350.0, 10.0, 0.5)
    assert interpolated % 360.0 == pytest.approx(0.0, abs=1.0)


def test_ease_in_out_edges(drone_config: dict, logger: logging.Logger) -> None:
    """Easing is clamped to [0, 1]."""
    simulator = PX4Simulator(drone_config, logger=logger)

    assert simulator._ease_in_out(0.0) == 0.0
    assert simulator._ease_in_out(1.0) == pytest.approx(1.0)
    assert simulator._ease_in_out(-1.0) == 0.0
    assert simulator._ease_in_out(2.0) == pytest.approx(1.0)


def test_build_turn_control_point_arcs_to_the_side(drone_config: dict, logger: logging.Logger) -> None:
    """Control point is offset perpendicular to the segment (smooth turns)."""
    simulator = PX4Simulator(drone_config, logger=logger)

    control = simulator._build_turn_control_point([0.0, 0.0], [1.0, 0.0], 3.0)

    # Perpendicular offset -> same longitude midpoint, shifted latitude
    assert control[0] == pytest.approx(0.5, abs=1e-6)
    assert abs(control[1]) > 0


def test_quadratic_bezier_point_hits_endpoints(drone_config: dict, logger: logging.Logger) -> None:
    """Bezier interpolation starts at start and ends at end."""
    simulator = PX4Simulator(drone_config, logger=logger)

    start = simulator._quadratic_bezier_point(start=[0.0, 0.0], control=[0.5, 0.5], end=[1.0, 0.0], ratio=0.0)
    end = simulator._quadratic_bezier_point(start=[0.0, 0.0], control=[0.5, 0.5], end=[1.0, 0.0], ratio=1.0)

    assert start == (0.0, 0.0)
    assert end == (1.0, 0.0)


@pytest.mark.asyncio
async def test_execute_spray_mission_animates_and_completes(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    """Animation player emits statuses and returns completed result."""
    async def fast_sleep(delay: float) -> None:
        del delay

    monkeypatch.setattr("asyncio.sleep", fast_sleep)
    simulator = PX4Simulator(drone_config, logger=logger)
    monkeypatch.setattr(simulator, "_update_gazebo_pose", lambda *args, **kwargs: None)
    monkeypatch.setattr(simulator, "_set_world_paused", lambda paused: None)

    statuses: list[str] = []

    def on_status(status: str, message: str, progress: int, waypoint: int, position: dict | None = None) -> None:
        statuses.append(status)

    result = await simulator.execute_spray_mission(
        request_id="req-anim-1",
        execution_plan={
            "飞行路径": [[0.0, 0.0], [0.01, 0.0], [0.02, 0.0]],
            "高度": 3.0,
            "速度": 2.0,
        },
        medication={},
        current_weather={},
        on_status=on_status,
    )

    assert result["status"] == "submitted"
    assert result["execution_mode"] == "animated_demo"
    assert result["final_status"] == "completed"
    assert statuses[0] == "connecting"
    assert statuses[-1] == "completed"
    assert "spraying" in statuses
    assert "armed" in statuses


@pytest.mark.asyncio
async def test_execute_spray_mission_requires_two_waypoints(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
) -> None:
    async def fast_sleep(delay: float) -> None:
        del delay

    monkeypatch.setattr("asyncio.sleep", fast_sleep)
    simulator = PX4Simulator(drone_config, logger=logger)
    monkeypatch.setattr(simulator, "_update_gazebo_pose", lambda *args, **kwargs: None)
    monkeypatch.setattr(simulator, "_set_world_paused", lambda paused: None)

    with pytest.raises(PX4SimulationError, match="至少需要两个航点"):
        await simulator.execute_spray_mission(
            request_id="req-anim-2",
            execution_plan={"飞行路径": [[0.0, 0.0]]},
            medication={},
            current_weather={},
        )


@pytest.mark.asyncio
async def test_execute_inspection_mission_captures_images(
    monkeypatch,
    drone_config: dict,
    logger: logging.Logger,
    tmp_path,
) -> None:
    """Inspection mission captures a placeholder image per waypoint."""
    async def fast_sleep(delay: float) -> None:
        del delay

    import modules.drone.px4_simulator as px4_module

    monkeypatch.setattr(px4_module, "IMAGES_DIR", tmp_path)
    monkeypatch.setattr("asyncio.sleep", fast_sleep)
    simulator = PX4Simulator(drone_config, logger=logger)
    monkeypatch.setattr(simulator, "_update_gazebo_pose", lambda *args, **kwargs: None)
    monkeypatch.setattr(simulator, "_set_world_paused", lambda paused: None)

    result = await simulator.execute_inspection_mission(
        request_id="req-inspect-1",
        execution_plan={
            "飞行路径": [[0.0, 0.0], [0.01, 0.0]],
            "高度": 2.5,
            "速度": 2.0,
        },
        on_status=None,
    )

    assert result["execution_mode"] == "animated_demo"
    assert result["final_status"] == "completed"
    assert len(result["captured_images"]) == 2
    assert all(image.startswith(str(tmp_path)) for image in result["captured_images"])
