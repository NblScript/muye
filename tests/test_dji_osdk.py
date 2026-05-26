"""Tests for the DJI OSDK backend."""

from __future__ import annotations

import pytest

from modules.drone.backends.dji_osdk import DJIOSDKBackend, DJIOSDKError


def build_config(mode: str = "osdk_sim") -> dict:
    return {
        "dji_osdk": {
            "execution_mode": mode,
            "drone_model": "Matrice 30T",
            "serial_port": "/dev/ttyACM0",
            "baud_rate": 921600,
            "connect_timeout_seconds": 5,
        },
    }


@pytest.mark.asyncio
async def test_sim_connect():
    backend = DJIOSDKBackend(build_config())
    assert not backend._connected
    await backend.connect()
    assert backend._connected


@pytest.mark.asyncio
async def test_sim_disconnect():
    backend = DJIOSDKBackend(build_config())
    await backend.connect()
    await backend.disconnect()
    assert not backend._connected


@pytest.mark.asyncio
async def test_sim_execute_mission():
    backend = DJIOSDKBackend(build_config())
    status_log: list[tuple[str, str, int, int]] = []

    def on_status(status, message, progress, wp_idx, pos=None):
        status_log.append((status, message, progress, wp_idx))

    execution_plan = {
        "飞行路径": [
            [113.6241, 34.7467],
            [113.6257, 34.7467],
            [113.6257, 34.7479],
        ],
        "高度": 3.5,
        "速度": 5.0,
    }

    result = await backend.execute_spray_mission(
        request_id="test-dji-001",
        execution_plan=execution_plan,
        medication={"农药名称": "吡虫啉"},
        current_weather={"temperature": 25, "humidity": 60, "wind_speed": 2},
        on_status=on_status,
    )

    assert result["backend"] == "dji_osdk"
    assert result["execution_mode"] == "osdk_sim"
    assert result["drone_model"] == "Matrice 30T"
    assert result["final_status"] == "completed"
    assert result["total_waypoints"] == 3

    # 验证状态回调序列
    statuses = [s[0] for s in status_log]
    assert "connecting" in statuses
    assert "connected" in statuses
    assert "spraying" in statuses
    assert "completed" in statuses
    assert statuses[-1] == "completed"


@pytest.mark.asyncio
async def test_sim_execute_minimal_route():
    backend = DJIOSDKBackend(build_config())
    execution_plan = {
        "飞行路径": [
            [113.6241, 34.7467],
            [113.6257, 34.7467],
        ],
        "高度": 3.0,
        "速度": 4.0,
    }

    result = await backend.execute_spray_mission(
        request_id="test-dji-002",
        execution_plan=execution_plan,
        medication={},
        current_weather={},
    )
    assert result["final_status"] == "completed"


@pytest.mark.asyncio
async def test_sim_execute_single_waypoint_raises():
    backend = DJIOSDKBackend(build_config())
    execution_plan = {
        "飞行路径": [[113.6241, 34.7467]],
        "高度": 3.0,
        "速度": 4.0,
    }

    with pytest.raises(DJIOSDKError, match="至少需要两个航点"):
        await backend.execute_spray_mission(
            request_id="test-dji-003",
            execution_plan=execution_plan,
            medication={},
            current_weather={},
        )


@pytest.mark.asyncio
async def test_sim_auto_connect_on_mission():
    backend = DJIOSDKBackend(build_config())
    assert not backend._connected

    execution_plan = {
        "飞行路径": [
            [113.6241, 34.7467],
            [113.6257, 34.7467],
        ],
        "高度": 3.0,
        "速度": 4.0,
    }
    await backend.execute_spray_mission(
        request_id="test-dji-004",
        execution_plan=execution_plan,
        medication={},
        current_weather={},
    )
    assert backend._connected


@pytest.mark.asyncio
async def test_get_telemetry():
    backend = DJIOSDKBackend(build_config())
    telemetry = await backend.get_telemetry()
    assert "latitude" in telemetry
    assert "longitude" in telemetry
    assert "battery_percent" in telemetry
    assert telemetry["drone_model"] == "Matrice 30T"
    assert telemetry["connected"] is False


@pytest.mark.asyncio
async def test_get_status():
    backend = DJIOSDKBackend(build_config())
    status = await backend.get_status()
    assert status["backend"] == "dji_osdk"
    assert status["execution_mode"] == "osdk_sim"
    assert status["drone_model"] == "Matrice 30T"
    assert status["connected"] is False


@pytest.mark.asyncio
async def test_real_mode_raises_without_hardware():
    backend = DJIOSDKBackend(build_config("osdk_real"))
    await backend.connect()

    execution_plan = {
        "飞行路径": [
            [113.6241, 34.7467],
            [113.6257, 34.7467],
        ],
        "高度": 3.0,
        "速度": 4.0,
    }

    with pytest.raises(DJIOSDKError, match="需要真实 DJI 硬件"):
        await backend.execute_spray_mission(
            request_id="test-dji-005",
            execution_plan=execution_plan,
            medication={},
            current_weather={},
        )


def test_haversine_distance():
    # 已知距离：北京天安门到故宫约 1km
    dist = DJIOSDKBackend._haversine_distance(39.9042, 116.4074, 39.9163, 116.3972)
    assert 1000 < dist < 2000  # 约 1.5km
