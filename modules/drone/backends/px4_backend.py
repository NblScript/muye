"""PX4 backend — thin wrapper around PX4Simulator."""

from __future__ import annotations

import logging
from typing import Any

from modules.drone.backends.base import DroneBackend, StatusCallback
from modules.drone.px4_simulator import PX4Simulator


class PX4Backend(DroneBackend):
    """PX4 SITL 仿真后端，包装现有 PX4Simulator。"""

    def __init__(
        self,
        drone_config: dict[str, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self._simulator = PX4Simulator(drone_config, logger=logger)

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def execute_spray_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        medication: dict[str, Any],
        current_weather: dict[str, Any],
        on_status: StatusCallback | None = None,
    ) -> dict[str, Any]:
        return await self._simulator.execute_spray_mission(
            request_id=request_id,
            execution_plan=execution_plan,
            medication=medication,
            current_weather=current_weather,
            on_status=on_status,
        )

    async def execute_inspection_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        on_status: StatusCallback | None = None,
    ) -> dict[str, Any]:
        return await self._simulator.execute_inspection_mission(
            request_id=request_id,
            execution_plan=execution_plan,
            on_status=on_status,
        )
