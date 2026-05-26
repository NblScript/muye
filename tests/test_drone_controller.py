from __future__ import annotations

import asyncio

import pytest

import app.services.telemetry_service as telemetry_module
from app.services.telemetry_service import TelemetryService
from modules.drone.controller import DroneController
from modules.drone.px4_simulator import PX4Simulator
from modules.infra.sqlite_store import SqliteStore


def build_drone_config() -> dict:
    return {
        "network": {"ip_whitelist": []},
        "flight_constraints": {
            "altitude_range_m": [2.0, 8.0],
            "speed_range_mps": [1.0, 6.0],
            "spray_rate_range_lpm": [0.3, 3.0],
            "max_safe_wind_speed_mps": 8.0,
        },
        "field": {
            "geofence": [
                [113.6241, 34.7467],
                [113.6257, 34.7467],
                [113.6257, 34.7479],
                [113.6241, 34.7479],
            ]
        },
        "execution": {"simulate_only": False, "backend": "px4"},
        "px4": {
            "system_address": "udpin://0.0.0.0:14540",
            "connect_timeout_seconds": 5,
            "mission_timeout_seconds": 30,
            "auto_arm": True,
            "auto_start_mission": True,
            "return_to_launch_after_mission": True,
            "require_global_position": False,
            "acceptance_radius_m": 2.0,
            "prefer_demo_field": False,
        },
    }


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
        drone_config=build_drone_config(),
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
    assert service.current_state.position is not None
    assert service.current_state.position.latitude == 34.7469
    assert service.current_state.telemetry.speed == 3.2
    assert len(service.get_trajectory_state().recent_points) == 1


@pytest.mark.asyncio
async def test_drone_controller_persists_px4_status_updates_to_sqlite(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    drone_config = build_drone_config()
    controller = DroneController(
        drone_config=drone_config,
        sqlite_store=store,
    )
    decision = {
        "用药": {
            "农药名称": "吡虫啉",
            "浓度": "1000倍",
            "配比": "1:1000",
            "总量": "1L",
            "安全提示": ["佩戴防护装备"],
        },
    }
    weather = {
        "temperature": 26,
        "humidity": 61,
        "wind_speed": 3.1,
    }
    field_context = {
        "field_id": "req-field-1",
        "name": "测试地块",
        "area_mu": 66.0,
        "geofence": build_drone_config()["field"]["geofence"],
        "crop_cycle": {"crop_name": "冬小麦"},
    }
    execution_plan = controller.plan_spray_mission(
        field_context=field_context,
        current_weather=weather,
    )

    async def fake_execute_spray_mission(
        *,
        request_id: str,
        execution_plan: dict,
        medication: dict,
        current_weather: dict,
        on_status,
    ) -> dict:
        del execution_plan
        del medication
        del current_weather
        on_status("connecting", "正在连接 PX4 SITL", 5, 0)
        on_status("spraying", "PX4 正在执行喷洒航线", 70, 2)
        on_status("completed", "PX4 喷洒任务完成", 100, 4)
        return {
            "status": "submitted",
            "task_id": f"drone-{request_id[:8]}",
            "accepted": True,
            "backend": "px4",
            "last_known_status": "completed",
            "final_status": "completed",
        }

    controller.backend.execute_spray_mission = fake_execute_spray_mission  # type: ignore[method-assign]

    try:
        result = await controller.execute_spray_mission(
            decision=decision,
            current_weather=weather,
            request_id="req-drone-px4-1",
            execution_plan=execution_plan,
            field_context=field_context,
        )
        updates = store.fetch_all(
            """
            SELECT task_id, status, message, progress
            FROM drone_mission_updates
            WHERE request_id = ?
            ORDER BY id ASC
            """,
            ("req-drone-px4-1",),
        )
        task_view = store.fetch_task_views(search="req-drone-px4-1", limit=5)[0]
    finally:
        await controller.close()
        store.close()

    assert result["status"] == "submitted"
    assert result["final_status"] == "completed"
    assert result["last_known_status"] == "completed"
    assert [item["status"] for item in updates] == ["connecting", "spraying", "completed"]
    assert updates[-1]["task_id"] == "drone-req-dron"
    assert updates[-1]["progress"] == 100
    assert task_view["drone"]["status"] == "completed"
    assert task_view["drone"]["task_id"] == "drone-req-dron"
    assert task_view["drone"]["message"] == "PX4 喷洒任务完成"


@pytest.mark.asyncio
async def test_px4_simulator_marks_completed_when_is_mission_finished(tmp_path) -> None:
    del tmp_path
    simulator = PX4Simulator(build_drone_config())
    status_updates: list[tuple[str, str, int, int]] = []

    class Progress:
        def __init__(self, current: int, total: int) -> None:
            self.current = current
            self.total = total

    class FakeMission:
        def __init__(self) -> None:
            self._checks = 0

        async def mission_progress(self):
            yield Progress(1, 4)
            yield Progress(2, 4)
            while True:
                await asyncio.sleep(0.01)

        async def is_mission_finished(self) -> bool:
            self._checks += 1
            return self._checks >= 3

    class FakeDrone:
        def __init__(self) -> None:
            self.mission = FakeMission()

    await simulator._wait_for_mission_completion(  # type: ignore[attr-defined]
        drone=FakeDrone(),
        total_waypoints=4,
        on_status=lambda status, message, progress, waypoint: status_updates.append(
            (status, message, progress, waypoint)
        ),
    )

    assert status_updates[-1] == ("completed", "PX4 喷洒任务完成", 100, 4)


def test_px4_simulator_normalizes_legacy_udp_listener_address() -> None:
    simulator = PX4Simulator(build_drone_config())

    assert simulator._normalize_system_address("udp://:14540") == "udpin://0.0.0.0:14540"
    assert simulator._normalize_system_address("udp://0.0.0.0:14540") == "udpin://0.0.0.0:14540"
    assert simulator._normalize_system_address("udpout://127.0.0.1:14580") == "udpout://127.0.0.1:14580"


def test_px4_simulator_build_mission_item_uses_waypoint_timing_controls() -> None:
    simulator = PX4Simulator(build_drone_config())

    class FakeMissionItem:
        def __init__(
            self,
            latitude_deg: float,
            longitude_deg: float,
            relative_altitude_m: float,
            speed_m_s: float,
            is_fly_through: bool,
            loiter_time_s: float,
            acceptance_radius_m: float,
            yaw_deg: float,
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

    item = simulator._build_mission_item(  # type: ignore[attr-defined]
        MissionItem=FakeMissionItem,
        longitude=8.545541,
        latitude=47.397711,
        altitude_m=3.5,
        speed_m_s=1.0,
        acceptance_radius_m=0.15,
        loiter_time_s=0.4,
        is_fly_through=False,
        yaw_deg=90.0,
    )

    assert item.acceptance_radius_m == 0.15
    assert item.loiter_time_s == 0.4
    assert item.is_fly_through is False
    assert item.yaw_deg == 90.0


def test_px4_simulator_replaces_far_route_with_sitl_demo_route() -> None:
    drone_config = build_drone_config()
    demo_route = [
        [8.545183, 47.397562],
        [8.546005, 47.397562],
        [8.546005, 47.397598],
    ]
    drone_config["px4"]["demo_field"] = {"explicit_route": demo_route}
    simulator = PX4Simulator(drone_config)

    route = simulator._resolve_px4_route(  # type: ignore[attr-defined]
        {
            "飞行路径": [
                [113.6241, 34.7467],
                [113.6257, 34.7479],
            ],
        }
    )

    assert route == demo_route


def test_px4_simulator_builds_in_place_turn_pivot_items() -> None:
    simulator = PX4Simulator(build_drone_config())

    class FakeMissionItem:
        def __init__(
            self,
            latitude_deg: float,
            longitude_deg: float,
            relative_altitude_m: float,
            speed_m_s: float,
            is_fly_through: bool,
            loiter_time_s: float,
            acceptance_radius_m: float,
            yaw_deg: float,
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

    route = [
        [8.545541, 47.397711],
        [8.545647, 47.397711],
        [8.545647, 47.397719],
    ]
    items = simulator._build_mission_items(  # type: ignore[attr-defined]
        MissionItem=FakeMissionItem,
        route=route,
        altitude_m=3.5,
        speed_m_s=1.0,
        acceptance_radius_m=0.15,
        loiter_time_s=0.0,
        is_fly_through=False,
        turn_mode="in_place",
        turn_loiter_time_s=0.8,
    )

    assert len(items) == 4
    assert items[1].latitude_deg == items[2].latitude_deg
    assert items[1].longitude_deg == items[2].longitude_deg
    assert items[1].loiter_time_s == 0.0
    assert items[2].loiter_time_s == 0.8
    assert items[1].is_fly_through is False
    assert items[2].is_fly_through is False


def test_build_spray_record_returns_none_when_field_id_missing(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    controller = DroneController(
        drone_config=build_drone_config(),
        sqlite_store=store,
    )

    record = controller.build_spray_record(
        request_id="test-req-1",
        field_context={"field_id": None, "area_mu": 10.0},
        decision={"用药": {"农药名称": "吡虫啉"}},
        weather={"temperature": 26},
        execution_plan={"喷洒速率": 1.5, "高度": 4.0, "速度": 3.0},
        mission_result={"task_id": "task-1", "status": "completed"},
    )

    store.close()
    assert record is None


def test_build_spray_record_builds_valid_record(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    controller = DroneController(
        drone_config=build_drone_config(),
        sqlite_store=store,
    )

    record = controller.build_spray_record(
        request_id="test-req-2",
        field_context={
            "field_id": "field-123",
            "area_mu": 20.0,
            "crop_cycle": {"id": "cycle-456", "crop_name": "冬小麦"},
        },
        decision={
            "用药": {
                "农药名称": "吡虫啉",
                "浓度": "1000倍",
                "配比": "1:1000",
                "总量": "2L",
                "安全提示": ["佩戴防护装备", "避免高温作业"],
            },
            "农事建议": ["喷洒后24小时内禁止进入田间"],
        },
        weather={"temperature": 26, "humidity": 60, "wind_speed": 2.5},
        execution_plan={"喷洒速率": 1.5, "高度": 4.0, "速度": 3.0},
        mission_result={"task_id": "task-2", "status": "completed"},
    )

    store.close()
    assert record is not None
    assert record["request_id"] == "test-req-2"
    assert record["field_id"] == "field-123"
    assert record["crop_cycle_id"] == "cycle-456"
    assert record["drone_task_id"] == "task-2"
    assert record["spray_area_mu"] == 20.0
    assert record["total_dosage"] == 2.0
    assert record["dosage_per_mu"] == 0.1  # 2L / 20mu
    assert record["dilution_ratio"] == "1:1000"
    assert record["spray_rate_lpm"] == 1.5
    assert record["flight_height_m"] == 4.0
    assert record["flight_speed_mps"] == 3.0
    assert record["result_status"] == "completed"
    assert record["source"] == "main_pipeline"
    assert "农药名称=吡虫啉" in record["notes"]
    assert "浓度=1000倍" in record["notes"]
    assert "佩戴防护装备" in record["notes"]


def test_build_spray_record_parses_dosage_with_ml_unit(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    controller = DroneController(
        drone_config=build_drone_config(),
        sqlite_store=store,
    )

    record = controller.build_spray_record(
        request_id="test-req-3",
        field_context={"field_id": "field-456", "area_mu": 10.0},
        decision={"用药": {"总量": "500ml"}},
        weather={},
        execution_plan={},
        mission_result={"status": "completed"},
    )

    store.close()
    assert record is not None
    assert record["total_dosage"] == 0.5  # 500ml = 0.5L


def test_build_spray_record_normalizes_result_status(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    controller = DroneController(
        drone_config=build_drone_config(),
        sqlite_store=store,
    )

    record = controller.build_spray_record(
        request_id="test-req-4",
        field_context={"field_id": "field-789"},
        decision={},
        weather={},
        execution_plan={},
        mission_result={"status": "completed"},
    )
    store.close()
    assert record is not None
    assert record["result_status"] == "completed"


def test_normalize_spray_result_status_various_statuses(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    controller = DroneController(
        drone_config=build_drone_config(),
        sqlite_store=store,
    )

    test_cases = [
        ({"status": "completed"}, "completed"),
        ({"status": "failed"}, "failed"),
        ({"status": "error"}, "failed"),
        ({"status": "cancelled"}, "cancelled"),
        ({"status": "takeoff"}, "in_progress"),
        ({"status": "spraying"}, "in_progress"),
        ({"status": "running"}, "in_progress"),
        ({"status": "unknown_status"}, "planned"),
        ({"final_status": "completed"}, "completed"),
        ({"last_known_status": "spraying"}, "in_progress"),
    ]

    for mission_result, expected in test_cases:
        result = controller._normalize_spray_result_status(mission_result)
        assert result == expected, f"Expected {expected} for {mission_result}, got {result}"

    store.close()


def test_extract_numeric_value(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    controller = DroneController(
        drone_config=build_drone_config(),
        sqlite_store=store,
    )

    assert controller._extract_numeric_value(None) is None
    assert controller._extract_numeric_value("") is None
    assert controller._extract_numeric_value(10) == 10.0
    assert controller._extract_numeric_value(3.14) == 3.14
    assert controller._extract_numeric_value("42") == 42.0
    assert controller._extract_numeric_value("约100亩") == 100.0
    assert controller._extract_numeric_value("abc") is None

    store.close()


def test_parse_total_dosage_liters(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    controller = DroneController(
        drone_config=build_drone_config(),
        sqlite_store=store,
    )

    assert controller._parse_total_dosage_liters(None) is None
    assert controller._parse_total_dosage_liters("") is None
    assert controller._parse_total_dosage_liters(5) == 5.0
    assert controller._parse_total_dosage_liters(2.5) == 2.5
    assert controller._parse_total_dosage_liters("1L") == 1.0
    assert controller._parse_total_dosage_liters("500ml") == 0.5
    assert controller._parse_total_dosage_liters("500毫升") == 0.5
    assert controller._parse_total_dosage_liters("2 升") == 2.0
    assert controller._parse_total_dosage_liters("3L ") == 3.0

    store.close()
