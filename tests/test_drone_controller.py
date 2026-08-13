from __future__ import annotations

import asyncio

import pytest

import modules.infra.telemetry as telemetry_module
from modules.infra.telemetry import TelemetryService
from modules.drone.controller import DroneController
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
