"""Drone backend abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

# on_status callback signature: (status, message, progress, current_waypoint_index, position)
StatusCallback = Callable[[str, str, int, int, dict[str, float] | None], None]


class DroneBackend(ABC):
    """无人机后端抽象接口。

    所有无人机后端（PX4、DJI OSDK、DJI Cloud API）都实现此接口。
    DroneController 通过此接口与具体后端交互，实现后端无关的任务执行。
    """

    @abstractmethod
    async def connect(self) -> None:
        """建立与无人机的连接。"""

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接。"""

    @abstractmethod
    async def execute_spray_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        medication: dict[str, Any],
        current_weather: dict[str, Any],
        on_status: StatusCallback | None = None,
    ) -> dict[str, Any]:
        """执行喷洒任务。

        Returns:
            结果字典，至少包含 backend、execution_mode、final_status 字段。
        """

    async def get_telemetry(self) -> dict[str, Any]:
        """获取当前遥测数据（位置、电量、速度等）。"""
        return {}

    async def get_status(self) -> dict[str, Any]:
        """获取后端状态（连接状态、无人机型号等）。"""
        return {}
