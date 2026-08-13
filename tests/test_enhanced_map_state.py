from __future__ import annotations

import asyncio

from fastapi import WebSocketDisconnect

import app.routes.sim as sim_routes
import modules.infra.telemetry as telemetry_module
from modules.infra.telemetry import TelemetryService
from models.schemas import DroneStatusEnum, SimMapStateResponse
from modules.drone.controller import DroneController


def test_legacy_sim_map_ws_keeps_simulation_shape(monkeypatch) -> None:
    class FakeSimulator:
        def snapshot(self) -> SimMapStateResponse:
            return SimMapStateResponse(
                timestamp=123.0,
                drones=[
                    {
                        "id": "drone-1",
                        "name": "测试无人机",
                        "status": "作业中",
                        "battery": 88,
                        "position": {"x": 12, "y": 34},
                        "route": [{"x": 12, "y": 34}, {"x": 56, "y": 78}],
                    }
                ],
            )

    class FakeWebSocket:
        def __init__(self) -> None:
            self.accepted = False
            self.payloads: list[dict[str, object]] = []

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, payload: dict[str, object]) -> None:
            self.payloads.append(payload)
            raise WebSocketDisconnect()

    websocket = FakeWebSocket()
    monkeypatch.setattr(sim_routes, "_simulator", FakeSimulator())

    asyncio.run(sim_routes.sim_map_state_ws(websocket))

    assert websocket.accepted is True
    assert len(websocket.payloads) == 1
    assert websocket.payloads[0]["timestamp"] == 123.0
    assert "drones" in websocket.payloads[0]
    assert "drone" not in websocket.payloads[0]
    assert websocket.payloads[0]["drones"][0]["position"] == {"x": 12.0, "y": 34.0}


def test_enhanced_state_ws_keeps_stream_alive_when_workflow_state_build_fails(monkeypatch) -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.accepted = False
            self.payloads: list[dict[str, object]] = []

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, payload: dict[str, object]) -> None:
            self.payloads.append(payload)
            raise WebSocketDisconnect()

    def raise_workflow_error() -> None:
        raise RuntimeError("workflow exploded")

    websocket = FakeWebSocket()
    monkeypatch.setattr(sim_routes, "get_telemetry_service", TelemetryService)
    monkeypatch.setattr(sim_routes.workflow_service, "build_workflow_state_response", raise_workflow_error)

    asyncio.run(sim_routes.enhanced_state_ws(websocket))

    assert websocket.accepted is True
    assert len(websocket.payloads) == 1
    assert websocket.payloads[0]["drone"]["status"] == "connecting"
    assert websocket.payloads[0]["mission"]["status"] == "unknown"
    assert websocket.payloads[0]["trajectory"] == {"recent_points": [], "total_distance": 0.0}
    assert websocket.payloads[0]["workflow_state"] is None


def test_publish_drone_update_adds_px4_position_to_telemetry_service(monkeypatch) -> None:
    service = TelemetryService()
    reset_calls = 0

    def fake_get_telemetry_service() -> TelemetryService:
        return service

    def fake_reset_trajectory() -> None:
        nonlocal reset_calls
        reset_calls += 1
        TelemetryService.reset_trajectory(service)

    monkeypatch.setattr(telemetry_module, "get_telemetry_service", fake_get_telemetry_service)
    monkeypatch.setattr(service, "reset_trajectory", fake_reset_trajectory)

    controller = DroneController(
        drone_config={
            "network": {"ip_whitelist": []},
            "flight_constraints": {},
            "execution": {"backend": "px4", "simulate_only": False},
        },
    )

    try:
        controller._publish_drone_update(
            request_id="req-telemetry-1",
            task_id="task-telemetry-1",
            status="takeoff",
            message="PX4 起飞",
            progress=0,
            instruction={},
            medication={},
            current_waypoint_index=0,
            position={
                "latitude": 34.7469,
                "longitude": 113.6243,
                "relative_altitude_m": 5.5,
                "heading": 45,
                "speed": 3.2,
                "battery_remaining": 91,
            },
        )
    finally:
        asyncio.run(controller.close())

    assert reset_calls == 1
    assert service.current_state is not None
    assert service.current_state.status == DroneStatusEnum.TAKEOFF
    assert service.current_state.position is not None
    assert service.current_state.position.latitude == 34.7469
    assert service.current_state.telemetry.speed == 3.2
    assert len(service.get_trajectory_state().recent_points) == 1
