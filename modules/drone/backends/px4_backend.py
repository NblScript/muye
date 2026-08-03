"""PX4 backend — animation demo or real MAVSDK execution.

Selects the executor from ``drone_config["px4"]["execution_mode"]``:

- ``animated_demo`` (default): PX4Simulator — pure animation for competition demos
- ``real``: PX4RealExecutor — drives a real PX4 vehicle via MAVSDK (serial telemetry)
"""

from __future__ import annotations

import logging
from typing import Any

from modules.drone.backends.base import DroneBackend, StatusCallback
from modules.drone.px4_simulator import PX4Simulator
from modules.drone.px4_real import PX4RealExecutor


class PX4Backend(DroneBackend):
    """PX4 backend wrapping either the animation demo or the real executor."""

    def __init__(
        self,
        drone_config: dict[str, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self.drone_config = drone_config
        self.logger = logger or logging.getLogger("muye.px4")
        execution_mode = str(
            drone_config.get("px4", {}).get("execution_mode", "animated_demo")
        ).strip().lower()
        if execution_mode == "real":
            self._executor = PX4RealExecutor(drone_config, logger=self.logger)
            self.execution_mode = "real"
        else:
            self._executor = PX4Simulator(drone_config, logger=self.logger)
            self.execution_mode = "animated_demo"

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
        return await self._executor.execute_spray_mission(
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
        return await self._executor.execute_inspection_mission(
            request_id=request_id,
            execution_plan=execution_plan,
            on_status=on_status,
        )
