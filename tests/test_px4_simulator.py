"""Smoke tests for modules/drone/px4_simulator.py"""

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


def test_px4_simulation_error_is_runtime_error() -> None:
    """Test PX4SimulationError is a RuntimeError subclass."""
    assert issubclass(PX4SimulationError, RuntimeError)

    error = PX4SimulationError("Test error")
    assert str(error) == "Test error"
