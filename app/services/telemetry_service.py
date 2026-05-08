"""Telemetry state service for enhanced websocket map updates."""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from models.schemas import (
    BatteryState,
    DroneState,
    DroneStatusEnum,
    GPSPosition,
    TelemetryData,
    TrajectoryState,
)

logger = logging.getLogger(__name__)


class TelemetryBuffer:
    """Keep recent PX4 positions and accumulated flight distance."""

    def __init__(self, max_points: int = 500) -> None:
        self.max_points = max_points
        self.points: deque[GPSPosition] = deque(maxlen=max_points)
        self.total_distance = 0.0
        self.last_point: GPSPosition | None = None

    def add_point(self, point: GPSPosition) -> None:
        """Add a GPS point and accumulate Haversine distance."""
        if self.last_point is not None:
            if self._same_position(self.last_point, point):
                return
            self.total_distance += self._calculate_distance(self.last_point, point)

        self.points.append(point)
        self.last_point = point

    def get_recent_points(self, count: int = 10) -> list[GPSPosition]:
        """Return the latest trajectory points."""
        return list(self.points)[-count:]

    def to_trajectory_state(self) -> TrajectoryState:
        """Build the websocket trajectory state."""
        return TrajectoryState(
            recent_points=self.get_recent_points(10),
            total_distance=self.total_distance,
        )

    def reset(self) -> None:
        """Clear all buffered trajectory state."""
        self.points.clear()
        self.total_distance = 0.0
        self.last_point = None

    @staticmethod
    def _same_position(p1: GPSPosition, p2: GPSPosition) -> bool:
        return (
            p1.latitude == p2.latitude
            and p1.longitude == p2.longitude
            and p1.altitude == p2.altitude
        )

    @staticmethod
    def _calculate_distance(p1: GPSPosition, p2: GPSPosition) -> float:
        """Calculate distance between two GPS points in meters."""
        lat1 = math.radians(p1.latitude)
        lon1 = math.radians(p1.longitude)
        lat2 = math.radians(p2.latitude)
        lon2 = math.radians(p2.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return 6371000 * 2 * math.asin(math.sqrt(a))


class TelemetryService:
    """Manage current drone telemetry state and trajectory history."""

    def __init__(self) -> None:
        self.buffer = TelemetryBuffer(max_points=500)
        self.current_state: DroneState | None = None
        self._subscribers: list[Callable[[DroneState], None]] = []
        self._current_task_id: str | None = None

    def subscribe(self, callback: Callable[[DroneState], None]) -> None:
        """Subscribe to drone state updates."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[DroneState], None]) -> None:
        """Unsubscribe from drone state updates."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def update_from_drone_status(
        self,
        request_id: str,
        task_id: str | None,
        status: str,
        message: str,
        progress: int | float,
        current_waypoint_index: int,
        position: dict[str, Any] | None,
    ) -> None:
        """Update telemetry from PX4 or workflow drone status payload."""
        del request_id, progress, current_waypoint_index
        normalized_task_id = str(task_id or "px4-sitl")
        if self._current_task_id is not None and self._current_task_id != normalized_task_id:
            self.reset()
        self._current_task_id = normalized_task_id

        try:
            gps_position = self._build_position(position)
            if gps_position is not None:
                self.buffer.add_point(gps_position)

            drone_state = DroneState(
                id=normalized_task_id,
                name="PX4 SITL 飞行器",
                status=self._map_status(status),
                message=message,
                position=gps_position or (self.current_state.position if self.current_state else None),
                battery=self._build_battery(position),
                telemetry=self._build_telemetry(position),
            )
            self.current_state = drone_state
            self._notify(drone_state)
        except Exception as exc:
            logger.exception("Failed to update telemetry from drone status: %s", exc)

    def get_trajectory_state(self) -> TrajectoryState:
        """Return recent trajectory state."""
        return self.buffer.to_trajectory_state()

    def reset(self) -> None:
        """Reset trajectory and current task tracking."""
        self.buffer.reset()
        self._current_task_id = None

    def reset_trajectory(self) -> None:
        """Compatibility alias for resetting trajectory history."""
        self.reset()

    def _notify(self, drone_state: DroneState) -> None:
        for callback in list(self._subscribers):
            try:
                callback(drone_state)
            except Exception as exc:
                logger.exception("Telemetry subscriber callback failed: %s", exc)

    @staticmethod
    def _build_position(position: dict[str, Any] | None) -> GPSPosition | None:
        if not position:
            return None

        latitude = _to_float(position.get("latitude"))
        longitude = _to_float(position.get("longitude"))
        if latitude is None or longitude is None:
            return None

        altitude = _first_float(
            position,
            "relative_altitude_m",
            "relative_altitude",
            "altitude",
        )
        return GPSPosition(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude or 0.0,
            absolute_altitude=_first_float(position, "absolute_altitude_m", "absolute_altitude"),
            heading=_first_float(position, "heading", "yaw_deg"),
            speed=_first_float(position, "speed", "ground_speed", "ground_speed_m_s"),
            timestamp=_first_float(position, "timestamp") or time.time(),
        )

    @staticmethod
    def _build_battery(position: dict[str, Any] | None) -> BatteryState:
        source = position or {}
        return BatteryState(
            voltage=_first_float(source, "voltage", "battery_voltage"),
            current=_first_float(source, "current", "battery_current"),
            remaining=_first_float(source, "battery_remaining", "remaining", "battery") or 85.0,
            temperature=_first_float(source, "temperature", "battery_temperature"),
        )

    @staticmethod
    def _build_telemetry(position: dict[str, Any] | None) -> TelemetryData:
        source = position or {}
        speed = _first_float(source, "speed", "ground_speed", "ground_speed_m_s") or 0.0
        return TelemetryData(
            speed=speed,
            ground_speed=_first_float(source, "ground_speed", "ground_speed_m_s"),
            air_speed=_first_float(source, "air_speed", "airspeed_m_s"),
            heading=_first_float(source, "heading", "yaw_deg"),
            climb_rate=_first_float(source, "climb_rate", "vertical_speed_m_s"),
        )

    @staticmethod
    def _map_status(status: str) -> DroneStatusEnum:
        status_map = {
            "connecting": DroneStatusEnum.CONNECTING,
            "connected": DroneStatusEnum.READY,
            "ready": DroneStatusEnum.READY,
            "queued": DroneStatusEnum.READY,
            "submitted": DroneStatusEnum.READY,
            "uploaded": DroneStatusEnum.READY,
            "armed": DroneStatusEnum.READY,
            "takeoff": DroneStatusEnum.TAKEOFF,
            "spraying": DroneStatusEnum.SPRAYING,
            "enroute": DroneStatusEnum.SPRAYING,
            "returning": DroneStatusEnum.RETURNING,
            "rtl": DroneStatusEnum.RETURNING,
            "completed": DroneStatusEnum.COMPLETED,
            "simulated": DroneStatusEnum.COMPLETED,
        }
        return status_map.get(str(status).strip().lower(), DroneStatusEnum.ERROR)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_float(source: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _to_float(source.get(key))
        if value is not None:
            return value
    return None


_telemetry_service: TelemetryService | None = None


def get_telemetry_service() -> TelemetryService:
    """Return the process-wide telemetry service."""
    global _telemetry_service
    if _telemetry_service is None:
        _telemetry_service = TelemetryService()
    return _telemetry_service
