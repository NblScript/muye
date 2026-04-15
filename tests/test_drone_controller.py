from __future__ import annotations

import asyncio

import pytest

from modules.drone_controller import DroneController
from modules.sqlite_store import SqliteStore


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
                [121.4700, 31.2290],
                [121.4750, 31.2290],
                [121.4750, 31.2330],
                [121.4700, 31.2330],
            ]
        },
        "execution": {"simulate_only": True},
    }


@pytest.mark.asyncio
async def test_drone_controller_persists_simulated_status_updates_to_sqlite(tmp_path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    controller = DroneController(
        drone_config=build_drone_config(),
        api_url="",
        api_key="",
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

    try:
        result = await controller.execute_spray_mission(
            decision=decision,
            current_weather=weather,
            request_id="req-drone-sqlite-1",
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
            ("req-drone-sqlite-1",),
        )
        task_view = store.fetch_task_views(search="req-drone-sqlite-1", limit=5)[0]
    finally:
        await controller.close()
        store.close()

    assert result["status"] == "simulated"
    assert len(updates) == 4
    assert [item["status"] for item in updates] == ["queued", "takeoff", "spraying", "completed"]
    assert updates[-1]["progress"] == 100
    assert task_view["drone"]["status"] == "completed"
    assert task_view["drone"]["task_id"] == result["task_id"]
    assert task_view["drone"]["message"] == "虚拟无人机任务完成"
