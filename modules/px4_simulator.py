from __future__ import annotations

import asyncio
import inspect
import logging
import math
from typing import Any, Callable


class PX4SimulationError(RuntimeError):
    """PX4 SITL 执行阶段错误。"""


class PX4Simulator:
    def __init__(
        self,
        drone_config: dict[str, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self.drone_config = drone_config
        self.logger = logger or logging.getLogger("muye.px4")

    async def execute_spray_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        medication: dict[str, Any],
        current_weather: dict[str, Any],
        on_status: Callable[[str, str, int, int], None] | None = None,
    ) -> dict[str, Any]:
        del medication
        del current_weather

        try:
            System, MissionItem, MissionPlan = self._load_mavsdk()
            px4_config = self.drone_config.get("px4", {})
            mission_id = f"px4-{request_id[:8]}"
            system_address = self._normalize_system_address(
                str(px4_config.get("system_address", "udpin://0.0.0.0:14540"))
            )
            connect_timeout = float(px4_config.get("connect_timeout_seconds", 30))
            mission_timeout = float(px4_config.get("mission_timeout_seconds", 180))
            auto_arm = bool(px4_config.get("auto_arm", True))
            auto_start_mission = bool(px4_config.get("auto_start_mission", True))
            require_global_position = bool(px4_config.get("require_global_position", True))
            total_waypoints = len(execution_plan["飞行路径"])
            waypoint_control = execution_plan.get("航点控制") or {}
            acceptance_radius_m = float(
                waypoint_control.get("接受半径", px4_config.get("acceptance_radius_m", 2.0))
            )
            loiter_time_s = float(waypoint_control.get("到点停留秒数", 0.0))
            is_fly_through = bool(waypoint_control.get("飞越航点", True))
            turn_mode = str(waypoint_control.get("转弯模式", "")).strip().lower()
            turn_loiter_time_s = float(waypoint_control.get("转弯停留秒数", loiter_time_s))

            if on_status:
                on_status("connecting", "正在连接 PX4 SITL", 5, 0)

            drone = System()
            await drone.connect(system_address=system_address)
            await asyncio.wait_for(self._wait_for_connection(drone), timeout=connect_timeout)

            if on_status:
                on_status("connected", f"PX4 SITL 已连接: {system_address}", 15, 0)

            if require_global_position:
                await asyncio.wait_for(
                    self._wait_for_global_position(drone),
                    timeout=connect_timeout,
                )
                if on_status:
                    on_status("ready", "PX4 SITL 定位状态已就绪", 20, 0)

            mission_items = self._build_mission_items(
                MissionItem=MissionItem,
                route=execution_plan["飞行路径"],
                altitude_m=float(execution_plan["高度"]),
                speed_m_s=float(execution_plan["速度"]),
                acceptance_radius_m=acceptance_radius_m,
                loiter_time_s=loiter_time_s,
                is_fly_through=is_fly_through,
                turn_mode=turn_mode,
                turn_loiter_time_s=turn_loiter_time_s,
            )
            mission_plan = MissionPlan(mission_items)

            if hasattr(drone.mission, "set_return_to_launch_after_mission"):
                await drone.mission.set_return_to_launch_after_mission(
                    bool(px4_config.get("return_to_launch_after_mission", True))
                )

            await drone.mission.upload_mission(mission_plan)
            if on_status:
                on_status("uploaded", "PX4 航线已上传", 30, 0)

            if auto_arm:
                await drone.action.arm()
                if on_status:
                    on_status("armed", "PX4 已解锁电机", 40, 0)

            if auto_start_mission:
                await drone.mission.start_mission()
                if on_status:
                    on_status("takeoff", "PX4 任务已启动", 50, 0)

                await asyncio.wait_for(
                    self._wait_for_mission_completion(
                        drone=drone,
                        total_waypoints=total_waypoints,
                        on_status=on_status,
                    ),
                    timeout=mission_timeout,
                )
                last_known_status = "completed"
                final_status = "completed"
            else:
                last_known_status = "uploaded"
                final_status = "planned"

            return {
                "status": "submitted",
                "task_id": mission_id,
                "accepted": True,
                "backend": "px4",
                "system_address": system_address,
                "final_status": final_status,
                "last_known_status": last_known_status,
            }
        except ImportError as exc:
            raise PX4SimulationError(
                "PX4 backend 需要安装 mavsdk。请先在项目环境中安装 mavsdk 后再运行 PX4 任务。"
            ) from exc
        except asyncio.TimeoutError as exc:
            raise PX4SimulationError("等待 PX4 SITL 连接或任务完成超时") from exc
        except PX4SimulationError:
            raise
        except Exception as exc:
            raise PX4SimulationError(f"PX4 SITL 执行失败: {exc}") from exc

    def _load_mavsdk(self) -> tuple[Any, Any, Any]:
        from mavsdk import System
        from mavsdk.mission import MissionItem, MissionPlan

        return System, MissionItem, MissionPlan

    async def _wait_for_connection(self, drone: Any) -> None:
        async for state in drone.core.connection_state():
            if getattr(state, "is_connected", False):
                return

    async def _wait_for_global_position(self, drone: Any) -> None:
        async for health in drone.telemetry.health():
            if getattr(health, "is_global_position_ok", False) or getattr(
                health, "is_home_position_ok", False
            ):
                return

    async def _wait_for_mission_completion(
        self,
        *,
        drone: Any,
        total_waypoints: int,
        on_status: Callable[[str, str, int, int], None] | None,
    ) -> None:
        state = {
            "current": 0,
            "total": max(total_waypoints, 1),
        }
        mission_finished = asyncio.Event()
        progress_task = asyncio.create_task(
            self._watch_mission_progress(
                drone=drone,
                state=state,
                mission_finished=mission_finished,
                on_status=on_status,
            )
        )

        try:
            while not mission_finished.is_set():
                if await drone.mission.is_mission_finished():
                    mission_finished.set()
                    break
                await asyncio.sleep(0.5)

            if on_status:
                on_status(
                    "completed",
                    "PX4 喷洒任务完成",
                    100,
                    max(int(state["current"]), int(state["total"])),
                )
        finally:
            progress_task.cancel()
            await asyncio.gather(progress_task, return_exceptions=True)

    async def _watch_mission_progress(
        self,
        *,
        drone: Any,
        state: dict[str, int],
        mission_finished: asyncio.Event,
        on_status: Callable[[str, str, int, int], None] | None,
    ) -> None:
        async for progress in drone.mission.mission_progress():
            current = int(getattr(progress, "current", 0))
            reported_total = int(getattr(progress, "total", 0))
            state["current"] = max(state["current"], current)
            state["total"] = max(state["total"], reported_total)

            progress_value = min(
                99,
                max(55, int((state["current"] / max(state["total"], 1)) * 100)),
            )
            if on_status:
                on_status(
                    "spraying",
                    "PX4 正在执行喷洒航线",
                    progress_value,
                    state["current"],
                )

            if state["total"] > 0 and state["current"] >= state["total"]:
                mission_finished.set()
                return

    def _normalize_system_address(self, system_address: str) -> str:
        if system_address.startswith("udp://:"):
            return "udpin://0.0.0.0:" + system_address.removeprefix("udp://:")
        if system_address.startswith("udp://0.0.0.0:"):
            return "udpin://0.0.0.0:" + system_address.removeprefix("udp://0.0.0.0:")
        return system_address

    def _build_mission_items(
        self,
        *,
        MissionItem: Any,
        route: list[list[float]],
        altitude_m: float,
        speed_m_s: float,
        acceptance_radius_m: float,
        loiter_time_s: float,
        is_fly_through: bool,
        turn_mode: str,
        turn_loiter_time_s: float,
    ) -> list[Any]:
        normalized_route = [
            (float(point[0]), float(point[1]))
            for point in route
        ]
        if not normalized_route:
            return []

        headings: list[float] = []
        for current, nxt in zip(normalized_route, normalized_route[1:]):
            headings.append(self._compute_heading_deg(current, nxt))

        mission_items: list[Any] = []
        for index, (longitude, latitude) in enumerate(normalized_route):
            arrival_heading = headings[index - 1] if index > 0 and headings else (
                headings[0] if headings else float("nan")
            )
            next_heading = headings[index] if index < len(headings) else arrival_heading
            should_pivot = (
                turn_mode == "in_place"
                and 0 < index < len(normalized_route) - 1
                and self._heading_delta_deg(arrival_heading, next_heading) >= 10.0
            )

            mission_items.append(
                self._build_mission_item(
                    MissionItem=MissionItem,
                    longitude=longitude,
                    latitude=latitude,
                    altitude_m=altitude_m,
                    speed_m_s=speed_m_s,
                    acceptance_radius_m=acceptance_radius_m,
                    loiter_time_s=0.0 if should_pivot else loiter_time_s,
                    is_fly_through=False if should_pivot else is_fly_through,
                    yaw_deg=arrival_heading,
                )
            )

            if should_pivot:
                mission_items.append(
                    self._build_mission_item(
                        MissionItem=MissionItem,
                        longitude=longitude,
                        latitude=latitude,
                        altitude_m=altitude_m,
                        speed_m_s=speed_m_s,
                        acceptance_radius_m=acceptance_radius_m,
                        loiter_time_s=turn_loiter_time_s,
                        is_fly_through=False,
                        yaw_deg=next_heading,
                    )
                )

        return mission_items

    def _compute_heading_deg(
        self,
        current: tuple[float, float],
        nxt: tuple[float, float],
    ) -> float:
        current_lon, current_lat = current
        next_lon, next_lat = nxt
        delta_lon = (next_lon - current_lon) * 111_000 * math.cos(math.radians((current_lat + next_lat) / 2))
        delta_lat = (next_lat - current_lat) * 111_000
        return math.degrees(math.atan2(delta_lon, delta_lat))

    def _heading_delta_deg(self, current: float, nxt: float) -> float:
        delta = (nxt - current + 180.0) % 360.0 - 180.0
        return abs(delta)

    def _build_mission_item(
        self,
        *,
        MissionItem: Any,
        longitude: float,
        latitude: float,
        altitude_m: float,
        speed_m_s: float,
        acceptance_radius_m: float,
        loiter_time_s: float,
        is_fly_through: bool,
        yaw_deg: float,
    ) -> Any:
        signature = inspect.signature(MissionItem)
        camera_action = getattr(getattr(MissionItem, "CameraAction", None), "NONE", None)
        vehicle_action = getattr(getattr(MissionItem, "VehicleAction", None), "NONE", None)
        kwargs = {
            "latitude_deg": latitude,
            "longitude_deg": longitude,
            "relative_altitude_m": altitude_m,
            "speed_m_s": speed_m_s,
            "is_fly_through": is_fly_through,
            "gimbal_pitch_deg": 0.0,
            "gimbal_yaw_deg": 0.0,
            "camera_action": camera_action,
            "loiter_time_s": loiter_time_s,
            "camera_photo_interval_s": 0.0,
            "acceptance_radius_m": acceptance_radius_m,
            "yaw_deg": yaw_deg,
            "camera_photo_distance_m": 0.0,
            "vehicle_action": vehicle_action,
        }
        filtered_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key in signature.parameters and value is not None
        }
        return MissionItem(**filtered_kwargs)
