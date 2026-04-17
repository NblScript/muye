from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from typing import Any

import httpx

from modules.common import log_event, point_in_polygon
from modules.event_bus import FileEventBus
from modules.mission_planner import MissionPlanner
from modules.px4_simulator import PX4SimulationError, PX4Simulator
from modules.sqlite_store import SqliteStore


class DroneExecutionError(RuntimeError):
    """无人机执行阶段错误。"""


class DroneController:
    def __init__(
        self,
        drone_config: dict[str, Any],
        api_url: str,
        api_key: str,
        timeout_seconds: float = 15,
        logger: logging.Logger | None = None,
        event_bus: FileEventBus | None = None,
        sqlite_store: SqliteStore | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.drone_config = drone_config
        self.api_url = api_url
        self.api_key = api_key
        self.logger = logger or logging.getLogger("muye.drone")
        self.event_bus = event_bus
        self.sqlite_store = sqlite_store
        self.planner = MissionPlanner(
            self.drone_config.get("flight_constraints", {}),
            logger=self.logger,
        )
        self.px4_backend = PX4Simulator(self.drone_config, logger=self.logger)
        self._client = httpx.AsyncClient(timeout=timeout_seconds, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def execute_spray_mission(
        self,
        decision: dict[str, Any],
        current_weather: dict[str, Any],
        request_id: str,
        client_ip: str = "127.0.0.1",
        execution_plan: dict[str, Any] | None = None,
        field_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            plan = execution_plan or self.plan_spray_mission(
                field_context=field_context or self.drone_config.get("field", {}),
                current_weather=current_weather,
            )
            self.validate_execution_plan(
                execution_plan=plan,
                current_weather=current_weather,
                client_ip=client_ip,
                geofence=(field_context or {}).get("geofence"),
            )
            execution = self.drone_config.get("execution", {})
            payload = {
                "request_id": request_id,
                "medication": decision["用药"],
                "instruction": plan,
                "weather": current_weather,
            }
            backend = self._resolve_backend()
            if backend == "simulated":
                result = {
                    "status": "simulated",
                    "task_id": f"sim-{request_id[:8]}",
                    "accepted": True,
                    "final_status": "completed",
                    "last_known_status": "completed",
                }
                await self._simulate_mission_progress(request_id, result["task_id"], payload)
                log_event(
                    self.logger,
                    logging.INFO,
                    "无人机喷洒任务已模拟执行",
                    request_id=request_id,
                    client_ip=client_ip,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    result=result,
                )
                return result

            if backend == "px4":
                result = await self._execute_px4_mission(
                    request_id=request_id,
                    plan=plan,
                    medication=decision["用药"],
                    current_weather=current_weather,
                )
                log_event(
                    self.logger,
                    logging.INFO,
                    "PX4 喷洒任务已提交",
                    request_id=request_id,
                    client_ip=client_ip,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    result=result,
                )
                return result

            response = await self._client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-Request-ID": request_id,
                },
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            self._validate_drone_response(result)
            self._publish_drone_update(
                request_id=request_id,
                task_id=result.get("task_id") or result.get("mission_id"),
                status="submitted",
                message="无人机任务已提交",
                progress=int(result.get("progress", 5)),
                instruction=plan,
                medication=decision["用药"],
                current_waypoint_index=0,
                position=None,
            )
            final_payload = await self._track_remote_mission(
                request_id=request_id,
                task_id=result.get("task_id") or result.get("mission_id"),
                instruction=plan,
                medication=decision["用药"],
            )
            last_known_status = str(
                (final_payload or {}).get("status")
                or result.get("status")
                or "submitted"
            )
            result["last_known_status"] = last_known_status
            result["final_status"] = self._map_drone_status_to_spray_result(last_known_status)
            log_event(
                self.logger,
                logging.INFO,
                "无人机喷洒任务已提交",
                request_id=request_id,
                client_ip=client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                result=result,
            )
            return result
        except Exception as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "无人机喷洒任务执行失败",
                request_id=request_id,
                client_ip=client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
            )
            raise DroneExecutionError(str(exc)) from exc

    async def _execute_px4_mission(
        self,
        *,
        request_id: str,
        plan: dict[str, Any],
        medication: dict[str, Any],
        current_weather: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            result = await self.px4_backend.execute_spray_mission(
                request_id=request_id,
                execution_plan=plan,
                medication=medication,
                current_weather=current_weather,
                on_status=lambda status, message, progress, current_waypoint_index, position=None: self._publish_drone_update(
                    request_id=request_id,
                    task_id=f"px4-{request_id[:8]}",
                    status=status,
                    message=message,
                    progress=progress,
                    instruction=plan,
                    medication=medication,
                    current_waypoint_index=current_waypoint_index,
                    position=position,
                ),
            )
        except PX4SimulationError as exc:
            raise DroneExecutionError(str(exc)) from exc

        result["last_known_status"] = str(result.get("last_known_status") or "submitted")
        result["final_status"] = self._map_drone_status_to_spray_result(
            result["last_known_status"]
        )
        return result

    def plan_spray_mission(
        self,
        *,
        field_context: dict[str, Any],
        current_weather: dict[str, Any],
    ) -> dict[str, Any]:
        return self.planner.plan_spray_mission(
            field_context=field_context,
            current_weather=current_weather,
        )

    async def _track_remote_mission(
        self,
        request_id: str,
        task_id: str,
        instruction: dict[str, Any],
        medication: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not task_id or not self.api_url:
            return None

        status_url = f"{self.api_url.rstrip('/')}/{task_id}"
        seen_statuses: set[str] = set()
        deadline = time.monotonic() + 15
        last_payload: dict[str, Any] | None = None

        while time.monotonic() < deadline:
            response = await self._client.get(
                status_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Request-ID": request_id,
                },
            )
            response.raise_for_status()
            payload = response.json()
            last_payload = payload
            status = str(payload.get("status", "unknown"))
            if status not in seen_statuses:
                seen_statuses.add(status)
                self._publish_drone_update(
                    request_id=request_id,
                    task_id=task_id,
                    status=status,
                    message=str(payload.get("message", "无人机状态更新")),
                    progress=int(payload.get("progress", 0)),
                    instruction=instruction,
                    medication=medication,
                    current_waypoint_index=int(payload.get("current_waypoint_index", 0)),
                    position=payload.get("position") if isinstance(payload.get("position"), dict) else None,
                )
            if status == "completed":
                return payload
            await asyncio.sleep(0.25)
        return last_payload

    async def _simulate_mission_progress(
        self,
        request_id: str,
        task_id: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.event_bus and not self.sqlite_store:
            return

        stages = [
            ("queued", "虚拟无人机已接收任务", 10),
            ("takeoff", "虚拟无人机起飞中", 35),
            ("spraying", "虚拟无人机喷洒中", 75),
            ("completed", "虚拟无人机任务完成", 100),
        ]

        for status, message, progress in stages:
            self._publish_drone_update(
                request_id=request_id,
                task_id=task_id,
                status=status,
                message=message,
                progress=progress,
                instruction=payload["instruction"],
                medication=payload["medication"],
                current_waypoint_index=0,
                position=None,
            )
            await asyncio.sleep(0.25)

    def _publish_drone_update(
        self,
        *,
        request_id: str,
        task_id: str | None,
        status: str,
        message: str,
        progress: int,
        instruction: dict[str, Any],
        medication: dict[str, Any],
        current_waypoint_index: int,
        position: dict[str, float] | None,
    ) -> None:
        payload = {
            "task_id": task_id,
            "progress": progress,
            "instruction": instruction,
            "medication": medication,
            "current_waypoint_index": current_waypoint_index,
            "position": position,
        }
        if self.event_bus:
            self.event_bus.publish(
                request_id=request_id,
                stage="drone",
                status=status,
                message=message,
                payload=payload,
            )
        if self.sqlite_store:
            self.sqlite_store.add_drone_mission_update(
                request_id,
                task_id=task_id,
                status=status,
                message=message,
                progress=progress,
                current_waypoint_index=current_waypoint_index,
                instruction=instruction,
                medication=medication,
            )

    def _map_drone_status_to_spray_result(self, status: str) -> str:
        normalized = status.strip().lower()
        if normalized in {"completed", "simulated", "success"}:
            return "completed"
        if normalized in {"failed", "error"}:
            return "failed"
        if normalized in {"cancelled", "canceled"}:
            return "cancelled"
        if normalized in {
            "connecting",
            "connected",
            "uploaded",
            "armed",
            "ready",
            "takeoff",
            "enroute",
            "spraying",
            "returning",
            "running",
            "in_progress",
            "processing",
        }:
            return "in_progress"
        return "planned"

    def _resolve_backend(self) -> str:
        execution = self.drone_config.get("execution", {})
        explicit_backend = str(execution.get("backend", "")).strip().lower()
        if explicit_backend in {"simulated", "remote_api", "px4"}:
            return explicit_backend
        if execution.get("simulate_only", True) or not self.api_url:
            return "simulated"
        return "remote_api"

    def validate_execution_plan(
        self,
        execution_plan: dict[str, Any],
        current_weather: dict[str, Any],
        client_ip: str,
        geofence: list[list[float]] | None = None,
    ) -> None:
        self._validate_ip_whitelist(client_ip)
        self._validate_instruction_format(execution_plan)
        self._validate_weather_constraints(execution_plan["气象限制"], current_weather)
        self._validate_geofence(
            execution_plan["飞行路径"],
            execution_plan["覆盖区域"]["coordinates"],
            geofence=geofence,
        )

    def _validate_ip_whitelist(self, client_ip: str) -> None:
        whitelist = self.drone_config.get("network", {}).get("ip_whitelist", [])
        if not whitelist:
            return

        client_address = ipaddress.ip_address(client_ip)
        for item in whitelist:
            try:
                if "/" in item:
                    network = ipaddress.ip_network(item, strict=False)
                    if client_address in network:
                        return
                elif client_address == ipaddress.ip_address(item):
                    return
            except ValueError as exc:
                raise DroneExecutionError(f"配置中的白名单 IP 非法: {item}") from exc
        raise DroneExecutionError(f"客户端 IP {client_ip} 不在白名单内")

    def _validate_instruction_format(self, instruction: dict[str, Any]) -> None:
        flight_constraints = self.drone_config.get("flight_constraints", {})
        altitude_range = flight_constraints.get("altitude_range_m", [2.0, 8.0])
        speed_range = flight_constraints.get("speed_range_mps", [1.0, 6.0])
        spray_rate_range = flight_constraints.get("spray_rate_range_lpm", [0.3, 3.0])

        if len(instruction["飞行路径"]) < 2:
            raise DroneExecutionError("飞行路径至少需要两个航点")
        if not altitude_range[0] <= float(instruction["高度"]) <= altitude_range[1]:
            raise DroneExecutionError("飞行高度超出无人机允许范围")
        if not speed_range[0] <= float(instruction["速度"]) <= speed_range[1]:
            raise DroneExecutionError("飞行速度超出无人机允许范围")
        if not spray_rate_range[0] <= float(instruction["喷洒速率"]) <= spray_rate_range[1]:
            raise DroneExecutionError("喷洒速率超出无人机允许范围")

        for point in instruction["飞行路径"]:
            self._validate_coordinate(point)
        for point in instruction["覆盖区域"]["coordinates"]:
            self._validate_coordinate(point)

    def _validate_weather_constraints(
        self,
        restrictions: dict[str, Any],
        current_weather: dict[str, Any],
    ) -> None:
        flight_constraints = self.drone_config.get("flight_constraints", {})
        max_safe_wind = float(flight_constraints.get("max_safe_wind_speed_mps", 8.0))
        allowed_wind = min(float(restrictions["最大风速"]), max_safe_wind)
        temperature = float(current_weather["temperature"])
        humidity = float(current_weather["humidity"])
        wind_speed = float(current_weather["wind_speed"])

        if wind_speed > allowed_wind:
            raise DroneExecutionError("当前风速超过喷洒安全阈值")
        if temperature < float(restrictions["最低温度"]) or temperature > float(restrictions["最高温度"]):
            raise DroneExecutionError("当前温度不满足喷洒要求")
        if humidity > float(restrictions["最大湿度"]):
            raise DroneExecutionError("当前湿度超过喷洒要求")

    def _validate_geofence(
        self,
        flight_path: list[list[float]],
        coverage_coordinates: list[list[float]],
        *,
        geofence: list[list[float]] | None = None,
    ) -> None:
        active_geofence = geofence or self.drone_config.get("field", {}).get("geofence", [])
        if len(active_geofence) < 3:
            raise DroneExecutionError("无人机配置中的 geofence 至少需要三个坐标点")
        for point in [*flight_path, *coverage_coordinates]:
            if not point_in_polygon(point, active_geofence):
                raise DroneExecutionError(f"坐标 {point} 超出安全地理围栏")

    def _validate_coordinate(self, point: list[float]) -> None:
        if len(point) != 2:
            raise DroneExecutionError("坐标必须为 [经度, 纬度] 二元数组")
        longitude = float(point[0])
        latitude = float(point[1])
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise DroneExecutionError("坐标超出经纬度有效范围")

    def _validate_drone_response(self, payload: dict[str, Any]) -> None:
        status = str(payload.get("status", "")).lower()
        task_id = payload.get("task_id") or payload.get("mission_id")
        accepted = payload.get("accepted")

        if not task_id:
            raise DroneExecutionError("无人机接口返回缺少 task_id/mission_id")
        if accepted is False:
            raise DroneExecutionError("无人机接口拒绝执行任务")
        if status and status not in {"accepted", "queued", "running"}:
            raise DroneExecutionError(f"无人机接口返回异常状态: {status}")
