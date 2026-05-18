from __future__ import annotations

import ipaddress
import logging
import re
import time
from typing import Any

from modules.infra.common import log_event, point_in_polygon
from modules.infra.event_bus import FileEventBus
from modules.drone.mission_planner import MissionPlanner
from modules.drone.px4_simulator import PX4SimulationError, PX4Simulator
from modules.infra.sqlite_store import SqliteStore


class DroneExecutionError(RuntimeError):
    """无人机执行阶段错误。"""


class DroneController:
    def __init__(
        self,
        drone_config: dict[str, Any],
        logger: logging.Logger | None = None,
        event_bus: FileEventBus | None = None,
        sqlite_store: SqliteStore | None = None,
    ) -> None:
        self.drone_config = drone_config
        self.logger = logger or logging.getLogger("muye.drone")
        self.event_bus = event_bus
        self.sqlite_store = sqlite_store
        self.planner = MissionPlanner(
            self.drone_config.get("flight_constraints", {}),
            logger=self.logger,
        )
        self.px4_backend = PX4Simulator(self.drone_config, logger=self.logger)

    async def close(self) -> None:
        return None

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
        self._sync_telemetry_update(
            request_id=request_id,
            task_id=task_id,
            status=status,
            message=message,
            progress=progress,
            current_waypoint_index=current_waypoint_index,
            position=position,
        )
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

    def _sync_telemetry_update(
        self,
        *,
        request_id: str,
        task_id: str | None,
        status: str,
        message: str,
        progress: int,
        current_waypoint_index: int,
        position: dict[str, float] | None,
    ) -> None:
        from app.services.telemetry_service import get_telemetry_service

        telemetry_service = get_telemetry_service()
        if int(progress) <= 0 or str(status).strip().lower() in {"queued", "submitted", "ready"}:
            telemetry_service.reset_trajectory()
        telemetry_service.update_from_drone_status(
            request_id=request_id,
            task_id=task_id,
            status=status,
            message=message,
            progress=progress,
            current_waypoint_index=current_waypoint_index,
            position=position,
        )

    def _map_drone_status_to_spray_result(self, status: str) -> str:
        normalized = status.strip().lower()
        if normalized in {"completed", "success"}:
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
        return "px4"

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

    def build_spray_record(
        self,
        *,
        request_id: str,
        field_context: dict[str, Any],
        decision: dict[str, Any],
        weather: dict[str, Any],
        execution_plan: dict[str, Any],
        mission_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        从执行结果构建喷洒记录。
        返回 None 表示无法构建有效记录（如 field_id 缺失）。
        """
        field_id = str(field_context.get("field_id") or "").strip()
        if not field_id:
            return None

        medication = decision.get("用药") or {}
        crop_cycle = field_context.get("crop_cycle") or {}
        crop_cycle_id = crop_cycle.get("id")
        pesticide_name = str(medication.get("农药名称") or "").strip()
        pesticide_id = None
        if pesticide_name and self.sqlite_store:
            pesticide_id = self.sqlite_store.resolve_pesticide_id_by_name(pesticide_name)

        total_dosage = self._parse_total_dosage_liters(medication.get("总量"))
        spray_area_mu = self._extract_numeric_value(field_context.get("area_mu"))
        dosage_per_mu = None
        if total_dosage is not None and spray_area_mu and spray_area_mu > 0:
            dosage_per_mu = round(total_dosage / spray_area_mu, 4)

        notes_parts = []
        if pesticide_name:
            notes_parts.append(f"农药名称={pesticide_name}")
        if medication.get("浓度"):
            notes_parts.append(f"浓度={medication['浓度']}")
        if medication.get("安全提示"):
            notes_parts.append(
                "安全提示=" + "；".join(str(item) for item in medication.get("安全提示", []))
            )
        if decision.get("农事建议"):
            notes_parts.append(
                "农事建议=" + "；".join(str(item) for item in decision.get("农事建议", []))
            )

        return {
            "request_id": request_id,
            "field_id": field_id,
            "crop_cycle_id": crop_cycle_id,
            "drone_task_id": mission_result.get("task_id") or mission_result.get("mission_id"),
            "pesticide_id": pesticide_id,
            "spray_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "spray_area_mu": spray_area_mu,
            "dosage_per_mu": dosage_per_mu,
            "total_dosage": total_dosage,
            "dilution_ratio": medication.get("配比"),
            "spray_rate_lpm": execution_plan.get("喷洒速率"),
            "flight_height_m": execution_plan.get("高度"),
            "flight_speed_mps": execution_plan.get("速度"),
            "weather_snapshot": weather,
            "result_status": self._normalize_spray_result_status(mission_result),
            "source": "main_pipeline",
            "notes": " | ".join(notes_parts) if notes_parts else None,
        }

    def _normalize_spray_result_status(self, mission_result: dict[str, Any]) -> str:
        status = str(
            mission_result.get("final_status")
            or mission_result.get("last_known_status")
            or mission_result.get("status")
            or "planned"
        ).strip().lower()
        if status == "completed":
            return "completed"
        if status in {"failed", "error"}:
            return "failed"
        if status in {"cancelled", "canceled"}:
            return "cancelled"
        if status in {
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

    def _extract_numeric_value(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if not match:
            return None
        return float(match.group(0))

    def _parse_total_dosage_liters(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text:
            return None

        normalized = text.replace(" ", "")
        unit_match = re.search(r"(-?\d+(?:\.\d+)?)(mL|ml|ML|毫升|L|l|升|g|G|kg|KG|克|千克)", normalized)
        if unit_match:
            amount = float(unit_match.group(1))
            unit = unit_match.group(2).lower()
            if unit in ("ml", "毫升"):
                return round(amount / 1000, 6)
            # 固体农药单位 — 粗略估算：假设密度≈1 g/mL（实际粉剂~0.5、颗粒剂~0.8），
            # 此换算仅用于喷洒速率近似，极端场景可能有±50%偏差；
            # 后续应让 Qwen 直接返回体积单位(mL/L)以消除密度假设
            if unit in ("g", "克"):
                return round(amount / 1000, 6)  # 克 → 升（密度≈1 粗略换算）
            if unit in ("kg", "千克"):
                return amount  # 千克 → 升（密度≈1 粗略换算）
            return amount

        return self._extract_numeric_value(text)
