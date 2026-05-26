"""DJI OSDK backend for professional drones (Matrice/M300/M350).

Supports two execution modes:
- osdk_real: Serial/UDP connection to onboard computer (requires hardware)
- osdk_sim: Simulation mode with GPS interpolation (no hardware needed)
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

from modules.drone.backends.base import DroneBackend, StatusCallback


class DJIOSDKError(RuntimeError):
    """DJI OSDK execution error."""


class DJIOSDKBackend(DroneBackend):
    """DJI OSDK 行业级无人机后端。"""

    def __init__(
        self,
        drone_config: dict[str, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self.drone_config = drone_config
        self.logger = logger or logging.getLogger("muye.dji_osdk")
        self._cfg = drone_config.get("dji_osdk", {})
        self._mode = self._cfg.get("execution_mode", "osdk_sim")
        self._connected = False
        self._drone_model = self._cfg.get("drone_model", "Matrice 30T")
        self._position: dict[str, float] = {
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0.0,
        }
        self._battery_percent = 100.0

    async def connect(self) -> None:
        if self._mode == "osdk_sim":
            self._connected = True
            self.logger.info("DJI OSDK 仿真模式已连接")
            return

        # osdk_real: 串口/UDP 连接
        serial_port = self._cfg.get("serial_port", "/dev/ttyACM0")
        baud_rate = self._cfg.get("baud_rate", 921600)
        timeout = self._cfg.get("connect_timeout_seconds", 30)
        self.logger.info(
            "DJI OSDK 正在连接 %s (波特率 %d, 超时 %ds)",
            serial_port, baud_rate, timeout,
        )
        # TODO: 实际串口连接逻辑（需要 pyserial 或 OSDK 库）
        # import serial
        # self._serial = serial.Serial(serial_port, baud_rate, timeout=timeout)
        # handshake...
        self._connected = True
        self.logger.info("DJI OSDK 已连接 %s", self._drone_model)

    async def disconnect(self) -> None:
        if not self._connected:
            return
        if self._mode == "osdk_real":
            # TODO: 关闭串口连接
            pass
        self._connected = False
        self.logger.info("DJI OSDK 已断开连接")

    async def execute_spray_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        medication: dict[str, Any],
        current_weather: dict[str, Any],
        on_status: StatusCallback | None = None,
    ) -> dict[str, Any]:
        if not self._connected:
            await self.connect()

        if self._mode == "osdk_sim":
            return await self._simulate_mission(
                request_id=request_id,
                execution_plan=execution_plan,
                medication=medication,
                on_status=on_status,
            )
        return await self._real_mission(
            request_id=request_id,
            execution_plan=execution_plan,
            medication=medication,
            current_weather=current_weather,
            on_status=on_status,
        )

    async def _simulate_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        medication: dict[str, Any],
        on_status: StatusCallback | None,
    ) -> dict[str, Any]:
        """仿真模式：用 GPS 坐标插值模拟飞行。"""
        route = execution_plan.get("飞行路径", [])
        if len(route) < 2:
            raise DJIOSDKError("航线至少需要两个航点")

        altitude_m = float(execution_plan.get("高度", 3.2))
        speed_m_s = float(execution_plan.get("速度", 4.5))
        total_waypoints = len(route)
        mission_id = f"dji-{request_id[:8]}"

        # 初始化位置到第一个航点
        self._position = {
            "latitude": route[0][1],
            "longitude": route[0][0],
            "altitude": altitude_m,
        }

        # 连接阶段
        if on_status:
            on_status("connecting", "正在连接 DJI OSDK", 0, 0, self._position)
        await asyncio.sleep(0.3)
        if on_status:
            on_status("connected", f"已连接 {self._drone_model}", 5, 0, self._position)

        # 起飞
        await asyncio.sleep(0.2)
        if on_status:
            on_status("armed", "DJI 已解锁准备起飞", 10, 0, self._position)
        await asyncio.sleep(0.2)
        if on_status:
            on_status("takeoff", "DJI 正在起飞", 15, 0, self._position)

        # 模拟爬升
        for alt in range(0, int(altitude_m) + 1):
            self._position["altitude"] = float(alt)
            await asyncio.sleep(0.05)

        # 执行航线
        for wp_idx in range(1, total_waypoints):
            start_lon, start_lat = route[wp_idx - 1]
            end_lon, end_lat = route[wp_idx]
            segment_distance = self._haversine_distance(start_lat, start_lon, end_lat, end_lon)
            segment_time = max(segment_distance / max(speed_m_s, 0.1), 0.1)
            steps = max(int(segment_time / 0.1), 1)

            for step in range(1, steps + 1):
                t = step / steps
                self._position["latitude"] = start_lat + (end_lat - start_lat) * t
                self._position["longitude"] = start_lon + (end_lon - start_lon) * t
                self._position["altitude"] = altitude_m
                self._battery_percent = max(0, self._battery_percent - 0.1)
                await asyncio.sleep(0.05)

            progress = int(15 + 80 * wp_idx / total_waypoints)
            if on_status:
                on_status(
                    "spraying",
                    f"DJI 执行航点 {wp_idx}/{total_waypoints - 1}",
                    progress,
                    wp_idx,
                    dict(self._position),
                )

        # 返航
        if on_status:
            on_status("returning", "DJI 正在返航", 95, total_waypoints, self._position)
        await asyncio.sleep(0.3)

        # 完成
        if on_status:
            on_status("completed", "DJI 喷洒任务完成", 100, total_waypoints, self._position)

        return {
            "backend": "dji_osdk",
            "execution_mode": "osdk_sim",
            "drone_model": self._drone_model,
            "mission_id": mission_id,
            "task_id": mission_id,
            "last_known_status": "completed",
            "final_status": "completed",
            "total_waypoints": total_waypoints,
            "battery_remaining": self._battery_percent,
        }

    async def _real_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        medication: dict[str, Any],
        current_weather: dict[str, Any],
        on_status: StatusCallback | None,
    ) -> dict[str, Any]:
        """真实 OSDK 任务执行（需要硬件）。"""
        # TODO: 实现真实 OSDK 任务上传和监控
        # 1. 通过串口发送航点任务
        # 2. 等待任务执行完成
        # 3. 通过 on_status 回调进度
        raise DJIOSDKError(
            "osdk_real 模式需要真实 DJI 硬件连接。"
            "请连接机载计算机后使用，或切换到 osdk_sim 模式。"
        )

    async def get_telemetry(self) -> dict[str, Any]:
        return {
            "latitude": self._position["latitude"],
            "longitude": self._position["longitude"],
            "altitude": self._position["altitude"],
            "battery_percent": self._battery_percent,
            "drone_model": self._drone_model,
            "connected": self._connected,
            "mode": self._mode,
        }

    async def get_status(self) -> dict[str, Any]:
        return {
            "backend": "dji_osdk",
            "execution_mode": self._mode,
            "drone_model": self._drone_model,
            "connected": self._connected,
        }

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float,
    ) -> float:
        """计算两点间的 Haversine 距离（米）。"""
        r = 6371000  # 地球半径（米）
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
