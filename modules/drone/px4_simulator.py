from __future__ import annotations

import asyncio
import logging
import math
import subprocess
import time
from typing import Any, Callable

from pathlib import Path

from modules.infra.common import IMAGES_DIR, METERS_PER_DEGREE_LAT, ensure_runtime_dirs
from modules.detection.data_collector import MINIMAL_JPEG


class PX4SimulationError(RuntimeError):
    """PX4 demo execution error."""


class PX4Simulator:
    """Pure animation demo player for the fixed PX4 route."""

    def __init__(
        self,
        drone_config: dict[str, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self.drone_config = drone_config
        self.logger = logger or logging.getLogger("muye.px4")
        self._gazebo_world_name = "muye_demo_field"
        self._gazebo_model_name = "x500_0"
        self._pose_update_interval_seconds = 0.05

    async def execute_spray_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        medication: dict[str, Any],
        current_weather: dict[str, Any],
        on_status: Callable[[str, str, int, int, dict[str, float] | None], None] | None = None,
    ) -> dict[str, Any]:
        del medication
        del current_weather

        route = self._normalize_route(execution_plan.get("飞行路径"))
        if len(route) < 2:
            raise PX4SimulationError("航线至少需要两个航点")

        mission_id = f"px4-{request_id[:8]}"
        altitude_m = float(execution_plan.get("高度", 3.2))
        speed_m_s = float(execution_plan.get("速度", 4.5))
        battery_start = 92.0
        total_waypoints = len(route)
        step_delay_seconds = self._resolve_step_delay_seconds(
            route=route,
            speed_m_s=speed_m_s,
        )

        self._set_world_paused(True)
        try:
            self._emit_status(on_status, "connecting", "连接 PX4", 5, 0, None)
            await asyncio.sleep(0.6)
            self._emit_status(on_status, "connected", "已连接", 15, 0, None)
            await asyncio.sleep(0.5)
            self._emit_status(on_status, "ready", "定位就绪", 20, 0, None)
            await asyncio.sleep(0.5)
            self._emit_status(on_status, "uploaded", f"航线已上传 {total_waypoints} 点", 30, 0, None)
            await asyncio.sleep(0.5)
            self._emit_status(on_status, "armed", "PX4 已解锁电机", 40, 0, None)
            await asyncio.sleep(0.5)

            initial_heading = self._heading_between(route[0], route[1])
            await self._animate_takeoff(
                point=route[0],
                target_altitude_m=altitude_m,
                heading_deg=initial_heading,
                battery_remaining=battery_start,
                on_status=on_status,
            )

            for index, point in enumerate(route):
                prev_point = route[index - 1] if index > 0 else point
                next_point = route[index + 1] if index + 1 < len(route) else point
                heading_deg = self._heading_between(prev_point, next_point)
                progress = min(99, max(55, int(round(55 + (index / max(total_waypoints - 1, 1)) * 40))))
                battery_remaining = max(48.0, battery_start - index * 1.4)
                position = self._build_position(
                    longitude=point[0],
                    latitude=point[1],
                    relative_altitude_m=altitude_m,
                    heading_deg=heading_deg,
                    speed_m_s=speed_m_s,
                    battery_remaining=battery_remaining,
                )
                self._emit_status(
                    on_status,
                    "spraying",
                    f"航点 {index + 1}/{total_waypoints}",
                    progress,
                    index,
                    position,
                )
                self._update_gazebo_pose(point, altitude_m, heading_deg)
                if index + 1 < len(route):
                    await self._animate_segment(
                        start_point=point,
                        end_point=route[index + 1],
                        altitude_m=altitude_m,
                        speed_m_s=speed_m_s,
                        start_heading_deg=heading_deg,
                        end_heading_deg=self._heading_between(point, route[index + 1]),
                    )
                else:
                    await asyncio.sleep(min(step_delay_seconds, 0.5))

            final_position = self._build_position(
                longitude=route[-1][0],
                latitude=route[-1][1],
                relative_altitude_m=altitude_m,
                heading_deg=self._heading_between(route[-2], route[-1]),
                speed_m_s=0.0,
                battery_remaining=max(42.0, battery_start - total_waypoints * 1.4),
            )
            self._update_gazebo_pose(route[-1], altitude_m, final_position["heading"])
            self._emit_status(on_status, "completed", "PX4 喷洒任务完成", 100, total_waypoints, final_position)
        finally:
            self._set_world_paused(False)

        return {
            "status": "submitted",
            "task_id": mission_id,
            "accepted": True,
            "backend": "px4",
            "execution_mode": "animated_demo",
            "final_status": "completed",
            "last_known_status": "completed",
        }

    async def execute_inspection_mission(
        self,
        *,
        request_id: str,
        execution_plan: dict[str, Any],
        on_status: Callable[[str, str, int, int, dict[str, float] | None], None] | None = None,
    ) -> dict[str, Any]:
        """Execute an inspection flight (fly route without spraying, capture images)."""
        route = self._normalize_route(execution_plan.get("飞行路径"))
        if len(route) < 2:
            raise PX4SimulationError("巡检航线至少需要两个航点")

        mission_id = f"px4-inspect-{request_id[:8]}"
        altitude_m = float(execution_plan.get("高度", 2.5))
        speed_m_s = float(execution_plan.get("速度", 2.0))
        battery_start = 92.0
        total_waypoints = len(route)
        step_delay_seconds = self._resolve_step_delay_seconds(
            route=route, speed_m_s=speed_m_s,
        )

        captured_images: list[str] = []

        self._set_world_paused(True)
        try:
            self._emit_status(on_status, "connecting", "连接 PX4 巡检", 5, 0, None)
            await asyncio.sleep(0.6)
            self._emit_status(on_status, "connected", "已连接", 15, 0, None)
            await asyncio.sleep(0.5)
            self._emit_status(on_status, "ready", "巡检定位就绪", 20, 0, None)
            await asyncio.sleep(0.5)
            self._emit_status(on_status, "uploaded", f"巡检航线已上传 {total_waypoints} 点", 30, 0, None)
            await asyncio.sleep(0.5)
            self._emit_status(on_status, "armed", "PX4 巡检已解锁电机", 40, 0, None)
            await asyncio.sleep(0.5)

            initial_heading = self._heading_between(route[0], route[1])
            await self._animate_takeoff(
                point=route[0],
                target_altitude_m=altitude_m,
                heading_deg=initial_heading,
                battery_remaining=battery_start,
                on_status=on_status,
            )

            for index, point in enumerate(route):
                prev_point = route[index - 1] if index > 0 else point
                next_point = route[index + 1] if index + 1 < len(route) else point
                heading_deg = self._heading_between(prev_point, next_point)
                progress = min(99, max(55, int(round(55 + (index / max(total_waypoints - 1, 1)) * 40))))
                battery_remaining = max(48.0, battery_start - index * 1.4)
                position = self._build_position(
                    longitude=point[0],
                    latitude=point[1],
                    relative_altitude_m=altitude_m,
                    heading_deg=heading_deg,
                    speed_m_s=speed_m_s,
                    battery_remaining=battery_remaining,
                )
                self._emit_status(
                    on_status,
                    "inspecting",
                    f"巡检航点 {index + 1}/{total_waypoints}",
                    progress,
                    index,
                    position,
                )
                self._update_gazebo_pose(point, altitude_m, heading_deg)

                # Capture image at this waypoint
                image_path = await self._capture_waypoint_image(request_id, index)
                if image_path:
                    captured_images.append(str(image_path))

                if index + 1 < len(route):
                    await self._animate_segment(
                        start_point=point,
                        end_point=route[index + 1],
                        altitude_m=altitude_m,
                        speed_m_s=speed_m_s,
                        start_heading_deg=heading_deg,
                        end_heading_deg=self._heading_between(point, route[index + 1]),
                    )
                else:
                    await asyncio.sleep(min(step_delay_seconds, 0.5))

            final_position = self._build_position(
                longitude=route[-1][0],
                latitude=route[-1][1],
                relative_altitude_m=altitude_m,
                heading_deg=self._heading_between(route[-2], route[-1]),
                speed_m_s=0.0,
                battery_remaining=max(42.0, battery_start - total_waypoints * 1.4),
            )
            self._update_gazebo_pose(route[-1], altitude_m, final_position["heading"])
            self._emit_status(on_status, "completed", "PX4 巡检任务完成", 100, total_waypoints, final_position)
        finally:
            self._set_world_paused(False)

        return {
            "status": "submitted",
            "task_id": mission_id,
            "accepted": True,
            "backend": "px4",
            "execution_mode": "animated_demo",
            "final_status": "completed",
            "last_known_status": "completed",
            "captured_images": captured_images,
        }

    async def _capture_waypoint_image(self, request_id: str, waypoint_index: int) -> Path | None:
        """Capture an image at a waypoint during inspection."""
        ensure_runtime_dirs()
        filename = f"reinspect-{request_id[:12]}-wp{waypoint_index}_{time.strftime('%Y%m%d-%H%M%S')}.jpg"
        path = IMAGES_DIR / filename
        # Write minimal JPEG placeholder (simulates camera capture)
        path.write_bytes(MINIMAL_JPEG)
        return path

    def _resolve_step_delay_seconds(
        self,
        *,
        route: list[list[float]],
        speed_m_s: float,
    ) -> float:
        total_distance_m = self._compute_route_cumulative_distances(route)[-1]
        display_speed_m_s = max(speed_m_s * 0.85, 1.6)
        raw_seconds = total_distance_m / max(display_speed_m_s, 0.1)
        normalized_seconds = raw_seconds / max(len(route) - 1, 1)
        return min(1.1, max(0.22, normalized_seconds))

    async def _animate_takeoff(
        self,
        *,
        point: list[float],
        target_altitude_m: float,
        heading_deg: float,
        battery_remaining: float,
        on_status: Callable[[str, str, int, int, dict[str, float] | None], None] | None,
    ) -> None:
        steps = max(1, int(2.4 / self._pose_update_interval_seconds))
        for index in range(steps):
            ratio = (index + 1) / steps
            eased_ratio = self._ease_in_out(ratio)
            altitude = max(0.15, target_altitude_m * eased_ratio)
            position = self._build_position(
                longitude=point[0],
                latitude=point[1],
                relative_altitude_m=altitude,
                heading_deg=heading_deg,
                speed_m_s=max(0.2, eased_ratio * 1.6),
                battery_remaining=battery_remaining,
            )
            self._update_gazebo_pose(point, altitude, heading_deg)
            self._emit_status(on_status, "takeoff", "PX4 任务已启动", 50, 0, position)
            await asyncio.sleep(self._pose_update_interval_seconds)

    async def _animate_segment(
        self,
        *,
        start_point: list[float],
        end_point: list[float],
        altitude_m: float,
        speed_m_s: float,
        start_heading_deg: float,
        end_heading_deg: float,
    ) -> None:
        segment_distance_m = self._distance_between_route_points(start_point, end_point)
        duration_seconds = max(0.45, segment_distance_m / max(speed_m_s, 0.1))
        steps = max(1, int(duration_seconds / self._pose_update_interval_seconds))
        control_point = self._build_turn_control_point(start_point, end_point, altitude_m)
        for step in range(steps):
            ratio = (step + 1) / steps
            eased_ratio = self._ease_in_out(ratio)
            longitude, latitude = self._quadratic_bezier_point(
                start=start_point,
                control=control_point,
                end=end_point,
                ratio=eased_ratio,
            )
            heading = self._interpolate_heading(start_heading_deg, end_heading_deg, eased_ratio)
            self._update_gazebo_pose([longitude, latitude], altitude_m, heading)
            await asyncio.sleep(self._pose_update_interval_seconds)

    def _build_position(
        self,
        *,
        longitude: float,
        latitude: float,
        relative_altitude_m: float,
        heading_deg: float,
        speed_m_s: float,
        battery_remaining: float,
    ) -> dict[str, float]:
        return {
            "longitude": longitude,
            "latitude": latitude,
            "absolute_altitude_m": 488.0 + relative_altitude_m,
            "relative_altitude_m": relative_altitude_m,
            "heading": heading_deg,
            "speed": speed_m_s,
            "battery_remaining": battery_remaining,
            "timestamp": time.time(),
        }

    def _emit_status(
        self,
        on_status: Callable[[str, str, int, int, dict[str, float] | None], None] | None,
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

    def _update_gazebo_pose(
        self,
        point: list[float] | tuple[float, float],
        relative_altitude_m: float,
        heading_deg: float,
    ) -> None:
        try:
            x, y = self._route_point_to_world_xy(float(point[0]), float(point[1]))
            yaw_rad = math.radians(float(heading_deg))
            qz = math.sin(yaw_rad / 2.0)
            qw = math.cos(yaw_rad / 2.0)
            request = (
                f'name: "{self._gazebo_model_name}" '
                f'position {{ x: {x} y: {y} z: {relative_altitude_m + 0.03} }} '
                f'orientation {{ z: {qz} w: {qw} }}'
            )
            subprocess.run(
                [
                    "gz",
                    "service",
                    "-s",
                    f"/world/{self._gazebo_world_name}/set_pose",
                    "--reqtype",
                    "gz.msgs.Pose",
                    "--reptype",
                    "gz.msgs.Boolean",
                    "--timeout",
                    "2000",
                    "--req",
                    request,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            self.logger.warning("更新 Gazebo 无人机位姿失败: %s", exc)

    def _route_point_to_world_xy(self, longitude: float, latitude: float) -> tuple[float, float]:
        demo_field = self.drone_config.get("px4", {}).get("demo_field", {})
        location = demo_field.get("location", {})
        origin_lon = float(location.get("longitude", 8.545594))
        origin_lat = float(location.get("latitude", 47.397742))
        x = (longitude - origin_lon) * METERS_PER_DEGREE_LAT * math.cos(math.radians(origin_lat))
        y = (latitude - origin_lat) * METERS_PER_DEGREE_LAT
        return x, y

    def _set_world_paused(self, paused: bool) -> None:
        try:
            subprocess.run(
                [
                    "gz",
                    "service",
                    "-s",
                    f"/world/{self._gazebo_world_name}/control",
                    "--reqtype",
                    "gz.msgs.WorldControl",
                    "--reptype",
                    "gz.msgs.Boolean",
                    "--timeout",
                    "2000",
                    "--req",
                    f"pause: {'true' if paused else 'false'}",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            self.logger.warning("切换 Gazebo world 暂停状态失败: %s", exc)

    def _heading_between(
        self,
        current: list[float] | tuple[float, float],
        nxt: list[float] | tuple[float, float],
    ) -> float:
        current_lon, current_lat = float(current[0]), float(current[1])
        next_lon, next_lat = float(nxt[0]), float(nxt[1])
        delta_lon = (next_lon - current_lon) * METERS_PER_DEGREE_LAT * math.cos(math.radians((current_lat + next_lat) / 2))
        delta_lat = (next_lat - current_lat) * METERS_PER_DEGREE_LAT
        if abs(delta_lon) < 1e-9 and abs(delta_lat) < 1e-9:
            return 0.0
        return math.degrees(math.atan2(delta_lon, delta_lat))

    def _interpolate_heading(self, start_deg: float, end_deg: float, ratio: float) -> float:
        delta = (end_deg - start_deg + 180.0) % 360.0 - 180.0
        return start_deg + delta * ratio

    def _ease_in_out(self, ratio: float) -> float:
        ratio = max(0.0, min(1.0, ratio))
        return 0.5 - 0.5 * math.cos(math.pi * ratio)

    def _build_turn_control_point(
        self,
        start_point: list[float],
        end_point: list[float],
        altitude_m: float,
    ) -> list[float]:
        del altitude_m
        start_lon = float(start_point[0])
        start_lat = float(start_point[1])
        end_lon = float(end_point[0])
        end_lat = float(end_point[1])
        mid_lon = (start_lon + end_lon) / 2.0
        mid_lat = (start_lat + end_lat) / 2.0

        delta_lon = end_lon - start_lon
        delta_lat = end_lat - start_lat
        length = math.hypot(delta_lon, delta_lat)
        if length < 1e-12:
            return [mid_lon, mid_lat]

        normal_lon = -delta_lat / length
        normal_lat = delta_lon / length
        curve_strength = min(0.000012, length * 0.12)
        return [
            mid_lon + normal_lon * curve_strength,
            mid_lat + normal_lat * curve_strength,
        ]

    def _quadratic_bezier_point(
        self,
        *,
        start: list[float],
        control: list[float],
        end: list[float],
        ratio: float,
    ) -> tuple[float, float]:
        one_minus = 1.0 - ratio
        longitude = (
            one_minus * one_minus * float(start[0])
            + 2.0 * one_minus * ratio * float(control[0])
            + ratio * ratio * float(end[0])
        )
        latitude = (
            one_minus * one_minus * float(start[1])
            + 2.0 * one_minus * ratio * float(control[1])
            + ratio * ratio * float(end[1])
        )
        return longitude, latitude
