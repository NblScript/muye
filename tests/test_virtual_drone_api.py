from __future__ import annotations

import asyncio

import pytest

from modules.virtual_drone_api import MissionRequest, VirtualDroneService, VirtualDroneSettings


def build_settings() -> VirtualDroneSettings:
    return VirtualDroneSettings(
        host="127.0.0.1",
        port=9010,
        api_key="virtual-drone-token",
        allowed_ips=[],
    )


@pytest.mark.asyncio
async def test_virtual_drone_service_advances_mission() -> None:
    service = VirtualDroneService(build_settings())
    record = await service.create_mission(
        MissionRequest(
            request_id="req-drone-1",
            medication={"农药名称": "吡虫啉"},
            instruction={"飞行路径": [[121.1, 31.1], [121.2, 31.2]]},
            weather={"temperature": 25},
        )
    )

    assert record.status == "queued"
    await asyncio.sleep(1.8)
    latest = await service.get_mission(record.task_id)
    assert latest.status == "completed"
    assert latest.progress == 100
    assert latest.current_waypoint_index >= 1
