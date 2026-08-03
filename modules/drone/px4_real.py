"""MAVSDK-based real drone executor for PX4 flight controllers.

This backend drives a real PX4 vehicle (self-built quadcopter with a Pixhawk /
Cube flight controller connected over serial telemetry) through MAVSDK:

    connect -> wait for global position -> upload mission -> arm -> start
    -> watch mission progress + live position -> complete

It is selected by setting ``px4.execution_mode`` to ``"real"`` in
``config/drone_config.json`` (or ``PX4_EXECUTION_MODE=real``). The
``animated_demo`` mode (PX4Simulator) remains untouched for competition demos.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import time
from typing import Any, Callable

from modules.infra.common import METERS_PER_DEGREE_LAT


class PX4RealError(RuntimeError):
    """PX4 real-vehicle execution error."""


# on_status callback signature: (status, message, progress, current_waypoint_index, position)
StatusCallback = Callable[[str, str, int, int, dict[str, float] | None], None]


class PX4RealExecutor:
    """Execute a spray/inspection mission on a real PX4 vehicle via MAVSDK."""

    def __init__(
        self,
        drone_config: dict[str, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self.drone_config = drone_config
        self.logger = logger or logging.getLogger("muye.px4.real")

    # ── public API ──────────────────────────────────────────────────────────

    async def execute_spray_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        medication: dict[str, Any],
        current_weather: dict[str, Any],
        on_status: StatusCallback | None = None,
    ) -> dict[str, Any]:
        del medication
        del current_weather

        return await self._execute_mission(
            request_id=request_id,
            execution_plan=execution_plan,
            on_status=on_status,
            inspection=False,
        )

    async def execute_inspection_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        on_status: StatusCallback | None = None,
    ) -> dict[str, Any]:
        return await self._execute_mission(
            request_id=request_id,
            execution_plan=execution_plan,
            on_status=on_status,
            inspection=True,
        )

    # ── core execution ──────────────────────────────────────────────────────

    async def _execute_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        on_status: StatusCallback | None,
        inspection: bool,
    ) -> dict[str, Any]:
        try:
            System, MissionItem, MissionPlan = self._load_mavsdk()
            px4_config = self.drone_config.get("px4", {})
            prefix = "巡检" if inspection else "喷洒"
            mission_id = f"px4-{prefix}-{request_id[:8]}"
            system_address = self._normalize_system_address(
                str(px4_config.get("system_address", "udpin://0.0.0.0:14540"))
            )
            connect_timeout = float(px4_config.get("connect_timeout_seconds", 30))
            configured_mission_timeout = float(px4_config.get("mission_timeout_seconds", 300))
            auto_arm = bool(px4_config.get("auto_arm", True))
            auto_start_mission = bool(px4_config.get("auto_start_mission", True))
            require_global_position = bool(px4_config.get("require_global_position", True))
            route = self._normalize_route(execution_plan.get("飞行路径"))
            if len(route) < 2:
                raise PX4RealError("航线至少需要两个航点")
            total_waypoints = len(route)

            waypoint_control = execution_plan.get("航点控制") or {}
            acceptance_radius_m = float(
                waypoint_control.get("接受半径", px4_config.get("acceptance_radius_m", 2.0))
            )
            loiter_time_s = float(waypoint_control.get("到点停留秒数", 0.0))
            is_fly_through = bool(waypoint_control.get("飞越航点", True))
            turn_mode = str(waypoint_control.get("转弯模式", "")).strip().lower()
            turn_loiter_time_s = float(waypoint_control.get("转弯停留秒数", loiter_time_s))
            flight_speed_m_s = float(execution_plan.get("速度", 4.5))
            altitude_m = float(execution_plan.get("高度", 3.2))

            mission_timeout = self._resolve_mission_timeout_seconds(
                configured_timeout_seconds=configured_mission_timeout,
                route=route,
                speed_m_s=flight_speed_m_s,
                loiter_time_s=loiter_time_s,
                turn_mode=turn_mode,
                turn_loiter_time_s=turn_loiter_time_s,
            )

            self._emit_status(on_status, "connecting", f"正在连接 PX4（{prefix}任务）", 5, 0, None)

            drone = System()
            await drone.connect(system_address=system_address)
            await asyncio.wait_for(self._wait_for_connection(drone), timeout=connect_timeout)

            self._emit_status(
                on_status,
                "connected",
                f"PX4 已连接: {system_address}",
                15,
                0,
                None,
            )

            if require_global_position:
                await asyncio.wait_for(
                    self._wait_for_global_position(drone),
                    timeout=connect_timeout,
                )
                self._emit_status(on_status, "ready", "PX4 定位状态已就绪", 20, 0, None)

            mission_items = self._build_mission_items(
                MissionItem=MissionItem,
                route=route,
                altitude_m=altitude_m,
                speed_m_s=flight_speed_m_s,
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
            self._emit_status(on_status, "uploaded", f"PX4 航线已上传 {total_waypoints} 点", 30, 0, None)

            if auto_arm:
                await self._arm_with_retries(
                    drone=drone,
                    attempts=int(px4_config.get("arm_retries", 3)),
                    retry_delay_seconds=float(px4_config.get("arm_retry_delay_seconds", 1.0)),
                    allow_force_arm=bool(px4_config.get("allow_force_arm", True)),
                )
                self._emit_status(on_status, "armed", "PX4 已解锁电机", 40, 0, None)

            if auto_start_mission:
                await drone.mission.start_mission()
                self._emit_status(on_status, "takeoff", f"PX4 {prefix}任务已启动", 50, 0, None)

                await asyncio.wait_for(
                    self._wait_for_mission_completion(
                        drone=drone,
                        route=route,
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
                "execution_mode": "real",
                "system_address": system_address,
                "final_status": final_status,
                "last_known_status": last_known_status,
                "total_waypoints": total_waypoints,
            }
        except ImportError as exc:
            raise PX4RealError(
                "PX4 真机后端需要安装 mavsdk。请执行 pip install mavsdk 后再运行 PX4 任务。"
            ) from exc
        except asyncio.TimeoutError as exc:
            raise PX4RealError("等待 PX4 连接或任务完成超时") from exc
        except PX4RealError:
            raise
        except Exception as exc:
            raise PX4RealError(f"PX4 真机执行失败: {exc}") from exc

    # ── MAVSDK loading ──────────────────────────────────────────────────────

    def _load_mavsdk(self) -> tuple[Any, Any, Any]:
        from mavsdk import System
        from mavsdk.mission import MissionItem, MissionPlan

        return System, MissionItem, MissionPlan

    # ── connection & arming ─────────────────────────────────────────────────

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

    async def _arm_with_retries(
        self,
        *,
        drone: Any,
        attempts: int,
        retry_delay_seconds: float,
        allow_force_arm: bool,
    ) -> None:
        """Try normal arm up to `attempts` times; force-arm as a last resort."""
        last_error: Exception | None = None
        for attempt in range(max(attempts, 1)):
            try:
                await drone.action.arm()
                return
            except Exception as exc:
                last_error = exc
                self.logger.warning("PX4 解锁失败（第 %d/%d 次）: %s", attempt + 1, attempts, exc)
                if attempt + 1 < attempts:
                    await asyncio.sleep(retry_delay_seconds)

        if allow_force_arm and hasattr(drone.action, "arm_force"):
            self.logger.warning("PX4 普通解锁失败，尝试强制解锁")
            await drone.action.arm_force()
            return

        raise PX4RealError(f"PX4 解锁失败: {last_error}") from last_error

    # ── mission completion watch ────────────────────────────────────────────

    async def _wait_for_mission_completion(
        self,
        *,
        drone: Any,
        route: list[list[float]] | None = None,
        total_waypoints: int,
        on_status: StatusCallback | None,
    ) -> None:
        normalized_route = self._normalize_route(route or [])
        route_distances = self._compute_route_cumulative_distances(normalized_route)
        state: dict[str, Any] = {
            "current": 0,
            "total": max(total_waypoints, 1),
            "progress": 50,
            "position": None,
            "last_position_for_emit": None,
            "last_emit_at": 0.0,
            "last_emitted_waypoint_index": None,
            "mission_current": 0,
            "mission_total": 0,
            "route": normalized_route,
            "route_distances": route_distances,
            "route_total_distance_m": route_distances[-1] if route_distances else 0.0,
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
        position_task = asyncio.create_task(
            self._watch_position(
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

            self._emit_status(
                on_status,
                "completed",
                "PX4 任务完成",
                100,
                max(int(state["current"]), int(state["total"])),
                state["position"],
            )
        finally:
            progress_task.cancel()
            position_task.cancel()
            await asyncio.gather(progress_task, position_task, return_exceptions=True)

    async def _watch_mission_progress(
        self,
        *,
        drone: Any,
        state: dict[str, Any],
        mission_finished: asyncio.Event,
        on_status: StatusCallback | None,
    ) -> None:
        del on_status
        async for progress in drone.mission.mission_progress():
            if mission_finished.is_set():
                return

            current = int(getattr(progress, "current", 0))
            reported_total = int(getattr(progress, "total", 0))
            state["mission_current"] = max(int(state.get("mission_current", 0)), current)
            state["mission_total"] = max(int(state.get("mission_total", 0)), reported_total)

            if state["mission_total"] > 0 and state["mission_current"] >= state["mission_total"]:
                mission_finished.set()
                return

    async def _watch_position(
        self,
        *,
        drone: Any,
        state: dict[str, Any],
        mission_finished: asyncio.Event,
        on_status: StatusCallback | None,
    ) -> None:
        async for position in drone.telemetry.position():
            if mission_finished.is_set():
                return

            current_position = {
                "latitude": float(getattr(position, "latitude_deg", 0.0)),
                "longitude": float(getattr(position, "longitude_deg", 0.0)),
                "absolute_altitude_m": float(getattr(position, "absolute_altitude_m", 0.0)),
                "relative_altitude_m": float(getattr(position, "relative_altitude_m", 0.0)),
            }
            state["position"] = current_position
            route_progress = self._estimate_route_progress(
                route=state.get("route", []),
                route_distances=state.get("route_distances", []),
                position=current_position,
            )

            current_waypoint_index = int(state.get("current", 0))
            progress_value = int(state.get("progress", 50))
            status = "takeoff"
            message = "PX4 起飞中"

            if route_progress is not None:
                current_waypoint_index = int(route_progress["current_waypoint_index"])
                progress_ratio = float(route_progress["distance_ratio"])
                state["current"] = current_waypoint_index
                progress_value = min(99, max(55, int(round(55 + progress_ratio * 44))))
                state["progress"] = progress_value
                if progress_ratio > 0.002 or current_position["relative_altitude_m"] >= 1.0:
                    status = "spraying"
                    message = "PX4 正在沿预设航线飞行"
                if float(route_progress["remaining_distance_m"]) <= 1.0:
                    progress_value = 99
                    state["progress"] = progress_value
            elif current_position["relative_altitude_m"] >= 1.0:
                progress_value = 55
                state["progress"] = progress_value
                status = "spraying"
                message = "PX4 正在执行喷洒航线"

            if not self._should_emit_position_update(
                state=state,
                current_position=current_position,
                current_waypoint_index=current_waypoint_index,
            ):
                continue

            self._emit_status(
                on_status,
                status,
                message,
                progress_value,
                current_waypoint_index,
                current_position,
            )

    # ── status emission ─────────────────────────────────────────────────────

    def _emit_status(
        self,
        on_status: StatusCallback | None,
        status: str,
        message: str,
        progress: int,
        current_waypoint_index: int,
        position: dict[str, float] | None,
    ) -> None:
        if on_status is None:
            return
        try:
            on_status(status, message, progress, current_waypoint_index, position)
        except TypeError:
            on_status(status, message, progress, current_waypoint_index)

    # ── timeout estimation ──────────────────────────────────────────────────

    def _resolve_mission_timeout_seconds(
        self,
        *,
        configured_timeout_seconds: float,
        route: list[list[float]],
        speed_m_s: float,
        loiter_time_s: float,
        turn_mode: str,
        turn_loiter_time_s: float,
    ) -> float:
        estimated_seconds = self._estimate_mission_duration_seconds(
            route=route,
            speed_m_s=speed_m_s,
            loiter_time_s=loiter_time_s,
            turn_mode=turn_mode,
            turn_loiter_time_s=turn_loiter_time_s,
        )
        resolved_timeout = max(float(configured_timeout_seconds), estimated_seconds)
        self.logger.info(
            "Resolved PX4 mission timeout: configured=%.2fs estimated=%.2fs resolved=%.2fs",
            float(configured_timeout_seconds),
            estimated_seconds,
            resolved_timeout,
        )
        return resolved_timeout

    def _estimate_mission_duration_seconds(
        self,
        *,
        route: list[list[float]],
        speed_m_s: float,
        loiter_time_s: float,
        turn_mode: str,
        turn_loiter_time_s: float,
    ) -> float:
        if len(route) < 2:
            return 180.0

        straight_distance_m = self._compute_route_cumulative_distances(route)[-1]
        travel_time_seconds = straight_distance_m / max(float(speed_m_s), 0.1)
        pivot_turn_count = self._count_pivot_turns(route=route, turn_mode=turn_mode)
        normal_loiter_count = max(len(route) - 1 - pivot_turn_count, 0)
        loiter_budget = normal_loiter_count * max(loiter_time_s, 0.0)
        pivot_budget = pivot_turn_count * max(turn_loiter_time_s, 0.0)
        # Startup, takeoff, and a safety buffer so the task does not fail mid-flight.
        return travel_time_seconds + loiter_budget + pivot_budget + 120.0

    def _count_pivot_turns(
        self,
        *,
        route: list[list[float]],
        turn_mode: str,
    ) -> int:
        if turn_mode != "in_place" or len(route) < 3:
            return 0

        normalized_route = [(float(point[0]), float(point[1])) for point in route]
        headings: list[float] = []
        for current, nxt in zip(normalized_route, normalized_route[1:]):
            headings.append(self._compute_heading_deg(current, nxt))

        count = 0
        for index in range(1, len(normalized_route) - 1):
            arrival_heading = headings[index - 1]
            next_heading = headings[index]
            if self._heading_delta_deg(arrival_heading, next_heading) >= 10.0:
                count += 1
        return count

    # ── route helpers ───────────────────────────────────────────────────────

    def _normalize_route(self, route: Any) -> list[list[float]]:
        if not isinstance(route, list):
            return []
        normalized: list[list[float]] = []
        for point in route:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                normalized.append([float(point[0]), float(point[1])])
            except (TypeError, ValueError):
                continue
        return normalized

    def _compute_route_cumulative_distances(self, route: list[list[float]]) -> list[float]:
        if not route:
            return []

        distances = [0.0]
        total = 0.0
        for start, end in zip(route, route[1:]):
            total += self._distance_between_route_points(start, end)
            distances.append(total)
        return distances

    def _estimate_route_progress(
        self,
        *,
        route: list[list[float]],
        route_distances: list[float],
        position: dict[str, float],
    ) -> dict[str, float | int] | None:
        if len(route) < 2 or len(route_distances) != len(route):
            return None

        current_lon = float(position.get("longitude", 0.0))
        current_lat = float(position.get("latitude", 0.0))
        best_projection: dict[str, float | int] | None = None

        for index, (start, end) in enumerate(zip(route, route[1:])):
            start_lon, start_lat = float(start[0]), float(start[1])
            end_lon, end_lat = float(end[0]), float(end[1])
            origin_lat = (start_lat + end_lat + current_lat) / 3

            start_x, start_y = self._project_lon_lat_to_meters(start_lon, start_lat, origin_lat)
            end_x, end_y = self._project_lon_lat_to_meters(end_lon, end_lat, origin_lat)
            point_x, point_y = self._project_lon_lat_to_meters(current_lon, current_lat, origin_lat)

            segment_dx = end_x - start_x
            segment_dy = end_y - start_y
            segment_length_sq = segment_dx * segment_dx + segment_dy * segment_dy
            if segment_length_sq <= 1e-9:
                continue

            projection_ratio = ((point_x - start_x) * segment_dx + (point_y - start_y) * segment_dy) / segment_length_sq
            projection_ratio = max(0.0, min(1.0, projection_ratio))
            projected_x = start_x + segment_dx * projection_ratio
            projected_y = start_y + segment_dy * projection_ratio
            lateral_distance_m = math.hypot(point_x - projected_x, point_y - projected_y)
            segment_length_m = math.sqrt(segment_length_sq)
            distance_along_route_m = route_distances[index] + segment_length_m * projection_ratio

            candidate: dict[str, float | int] = {
                "segment_index": index,
                "projection_ratio": projection_ratio,
                "distance_along_route_m": distance_along_route_m,
                "remaining_distance_m": max(float(route_distances[-1]) - distance_along_route_m, 0.0),
                "current_waypoint_index": min(index + 1, len(route) - 1),
                "distance_ratio": (
                    distance_along_route_m / float(route_distances[-1]) if float(route_distances[-1]) > 0 else 0.0
                ),
                "lateral_distance_m": lateral_distance_m,
            }

            if best_projection is None or float(candidate["lateral_distance_m"]) < float(best_projection["lateral_distance_m"]):
                best_projection = candidate

        return best_projection

    def _project_lon_lat_to_meters(
        self,
        longitude: float,
        latitude: float,
        origin_latitude: float,
    ) -> tuple[float, float]:
        return (
            longitude * 111_000 * math.cos(math.radians(origin_latitude)),
            latitude * 111_000,
        )

    def _distance_between_route_points(
        self,
        current: list[float] | tuple[float, float],
        nxt: list[float] | tuple[float, float],
    ) -> float:
        current_lon, current_lat = float(current[0]), float(current[1])
        next_lon, next_lat = float(nxt[0]), float(nxt[1])
        delta_lon = (next_lon - current_lon) * METERS_PER_DEGREE_LAT * math.cos(math.radians((current_lat + next_lat) / 2))
        delta_lat = (next_lat - current_lat) * METERS_PER_DEGREE_LAT
        return math.hypot(delta_lon, delta_lat)

    def _distance_between_positions(
        self,
        current: dict[str, float],
        nxt: dict[str, float],
    ) -> float:
        return self._distance_between_route_points(
            [float(current.get("longitude", 0.0)), float(current.get("latitude", 0.0))],
            [float(nxt.get("longitude", 0.0)), float(nxt.get("latitude", 0.0))],
        )

    def _should_emit_position_update(
        self,
        *,
        state: dict[str, Any],
        current_position: dict[str, float],
        current_waypoint_index: int,
    ) -> bool:
        last_position = state.get("last_position_for_emit")
        last_emit_at = float(state.get("last_emit_at", 0.0) or 0.0)
        now = time.monotonic()

        moved_distance_m = (
            self._distance_between_positions(last_position, current_position)
            if isinstance(last_position, dict)
            else None
        )
        waypoint_changed = state.get("last_emitted_waypoint_index") != current_waypoint_index
        should_emit = (
            last_position is None
            or waypoint_changed
            or (moved_distance_m is not None and moved_distance_m >= 0.8)
            or (now - last_emit_at) >= 0.6
        )
        if should_emit:
            state["last_position_for_emit"] = current_position
            state["last_emit_at"] = now
            state["last_emitted_waypoint_index"] = current_waypoint_index
        return should_emit

    def _normalize_system_address(self, system_address: str) -> str:
        if system_address.startswith("udp://:"):
            return "udpin://0.0.0.0:" + system_address.removeprefix("udp://:")
        if system_address.startswith("udp://0.0.0.0:"):
            return "udpin://0.0.0.0:" + system_address.removeprefix("udp://0.0.0.0:")
        return system_address

    # ── mission item building ───────────────────────────────────────────────

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
        normalized_route = [(float(point[0]), float(point[1])) for point in route]
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
        delta_lon = (next_lon - current_lon) * METERS_PER_DEGREE_LAT * math.cos(math.radians((current_lat + next_lat) / 2))
        delta_lat = (next_lat - current_lat) * METERS_PER_DEGREE_LAT
        if abs(delta_lon) < 1e-9 and abs(delta_lat) < 1e-9:
            return 0.0
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
