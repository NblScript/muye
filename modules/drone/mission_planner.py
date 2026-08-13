from __future__ import annotations

import logging
import math
from typing import Any

from modules.drone.density_map import DensityMap
from modules.infra.common import METERS_PER_DEGREE_LAT


class MissionPlannerError(RuntimeError):
    """系统规划阶段错误。"""


class MissionPlanner:
    def __init__(
        self,
        flight_constraints: dict[str, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self.flight_constraints = flight_constraints
        self.logger = logger or logging.getLogger("muye.planner")

    def plan_variable_rate_mission(
        self,
        *,
        field_context: dict[str, Any],
        current_weather: dict[str, Any],
        density_map: DensityMap,
    ) -> dict[str, Any]:
        result = self.plan_spray_mission(
            field_context=field_context,
            current_weather=current_weather,
        )

        geofence = self._normalize_geofence(field_context.get("geofence", []))
        presentation_profile = field_context.get("presentation_profile") or {}
        crop_cycle = field_context.get("crop_cycle") or {}
        crop_name = str(crop_cycle.get("crop_name") or "")

        lane_spacing_m = self._resolve_lane_spacing(
            crop_name=crop_name,
            presentation_profile=presentation_profile,
        )
        lat_span = (max(p[1] for p in geofence) - min(p[1] for p in geofence)) if geofence else 0
        lat_span_m = lat_span * METERS_PER_DEGREE_LAT
        lane_count = max(2, int(math.ceil(lat_span_m / lane_spacing_m)) + 1) if lat_span_m > 0 else 2

        spray_rate_range = self.flight_constraints.get("spray_rate_range_lpm", [0.3, 3.0])
        base_rate = result.get("喷洒速率", 1.0)

        spray_schedule = density_map.suggest_spray_rates(
            base_rate=base_rate,
            rate_range=spray_rate_range,
            lane_count=lane_count,
        )

        result["spray_schedule"] = spray_schedule
        result["density_grid"] = density_map.to_geo_grid()
        result["density_metadata"] = density_map.metadata()
        result["source"] = "system_planner_variable_rate"
        return result

    def plan_spray_mission(
        self,
        *,
        field_context: dict[str, Any],
        current_weather: dict[str, Any],
    ) -> dict[str, Any]:
        geofence = self._normalize_geofence(field_context.get("geofence", []))
        if len(geofence) < 3:
            raise MissionPlannerError("系统 planner 缺少有效地块围栏，无法生成喷洒任务")

        altitude_range = self.flight_constraints.get("altitude_range_m", [2.0, 8.0])
        speed_range = self.flight_constraints.get("speed_range_mps", [1.0, 6.0])
        spray_rate_range = self.flight_constraints.get("spray_rate_range_lpm", [0.3, 3.0])
        max_safe_wind = float(self.flight_constraints.get("max_safe_wind_speed_mps", 8.0))

        crop_cycle = field_context.get("crop_cycle") or {}
        crop_name = str(crop_cycle.get("crop_name") or "")
        area_mu = float(field_context.get("area_mu") or 30.0)
        current_wind = float(current_weather.get("wind_speed", 0.0))
        presentation_profile = field_context.get("presentation_profile") or {}
        route = self._resolve_route(
            field_context=field_context,
            geofence=geofence,
            crop_name=crop_name,
            presentation_profile=presentation_profile,
        )

        altitude = self._clamp(
            self._suggest_altitude(crop_name=crop_name, area_mu=area_mu),
            altitude_range,
        )
        speed = self._clamp(
            self._suggest_speed(
                current_wind=current_wind,
                speed_range=speed_range,
                presentation_profile=presentation_profile,
            ),
            speed_range,
        )
        spray_rate = self._clamp(
            self._suggest_spray_rate(crop_name=crop_name, area_mu=area_mu),
            spray_rate_range,
        )

        return {
            "source": "system_planner",
            "field_id": field_context.get("field_id"),
            "field_name": field_context.get("name"),
            "crop_name": crop_name,
            "飞行路径": route,
            "高度": round(altitude, 2),
            "速度": round(speed, 2),
            "喷洒速率": round(spray_rate, 2),
            "航点控制": self._build_waypoint_control(presentation_profile=presentation_profile),
            "覆盖区域": {
                "type": "polygon",
                "coordinates": geofence,
            },
            "气象限制": {
                "最大风速": round(min(max_safe_wind, max(current_wind + 1.5, 4.0)), 2),
                "最低温度": 5.0,
                "最高温度": 35.0,
                "最大湿度": 85.0,
            },
        }

    def plan_inspection_mission(
        self,
        *,
        field_context: dict[str, Any],
        current_weather: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate an inspection flight plan (lower altitude/speed, no spray)."""
        spray_plan = self.plan_spray_mission(
            field_context=field_context,
            current_weather=current_weather,
        )
        altitude_range = self.flight_constraints.get("altitude_range_m", [2.0, 8.0])
        speed_range = self.flight_constraints.get("speed_range_mps", [1.0, 6.0])

        inspection_altitude = self._clamp(
            spray_plan["高度"] * 0.65,
            altitude_range,
        )
        inspection_speed = self._clamp(
            spray_plan["速度"] * 0.5,
            speed_range,
        )

        return {
            **spray_plan,
            "source": "system_planner_inspection",
            "高度": round(inspection_altitude, 2),
            "速度": round(inspection_speed, 2),
            "喷洒速率": 0.0,
        }

    def _normalize_geofence(self, geofence: Any) -> list[list[float]]:
        if not isinstance(geofence, list):
            return []

        normalized: list[list[float]] = []
        for point in geofence:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            try:
                normalized.append([float(point[0]), float(point[1])])
            except (TypeError, ValueError):
                continue

        if len(normalized) >= 2 and normalized[0] == normalized[-1]:
            normalized = normalized[:-1]
        return normalized

    def _build_coverage_route(
        self,
        geofence: list[list[float]],
        *,
        crop_name: str,
        lane_spacing_m: float | None = None,
    ) -> list[list[float]]:
        if len(geofence) < 3:
            return geofence

        longitudes = [point[0] for point in geofence]
        latitudes = [point[1] for point in geofence]
        min_lon, max_lon = min(longitudes), max(longitudes)
        min_lat, max_lat = min(latitudes), max(latitudes)
        lat_span = max_lat - min_lat
        if lat_span <= 0:
            return geofence

        if lane_spacing_m is None:
            lane_spacing_m = self._resolve_lane_spacing(
                crop_name=crop_name,
                presentation_profile=None,
            )
        lat_span_m = lat_span * METERS_PER_DEGREE_LAT
        lane_count = max(2, int(math.ceil(lat_span_m / lane_spacing_m)) + 1)

        route: list[list[float]] = []
        for lane_index in range(lane_count):
            lane_lat = min_lat + lat_span * lane_index / max(lane_count - 1, 1)
            intersections = self._horizontal_intersections(geofence, lane_lat)
            if len(intersections) < 2:
                continue
            start_lon, end_lon = intersections[0], intersections[-1]
            lane_points = [
                [round(start_lon, 6), round(lane_lat, 6)],
                [round(end_lon, 6), round(lane_lat, 6)],
            ]
            if lane_index % 2 == 1:
                lane_points.reverse()
            if route and route[-1] == lane_points[0]:
                route.append(lane_points[1])
            else:
                route.extend(lane_points)

        return route if len(route) >= 2 else geofence

    def _horizontal_intersections(
        self,
        polygon: list[list[float]],
        latitude: float,
    ) -> list[float]:
        intersections: list[float] = []
        total = len(polygon)
        for index in range(total):
            lon1, lat1 = polygon[index]
            lon2, lat2 = polygon[(index + 1) % total]

            if lat1 == lat2:
                if abs(latitude - lat1) < 1e-9:
                    intersections.extend([lon1, lon2])
                continue

            low_lat, high_lat = sorted((lat1, lat2))
            if not (low_lat <= latitude <= high_lat):
                continue

            ratio = (latitude - lat1) / (lat2 - lat1)
            if 0 <= ratio <= 1:
                intersections.append(lon1 + (lon2 - lon1) * ratio)

        normalized = sorted({round(item, 9) for item in intersections})
        return normalized

    def _resolve_route(
        self,
        *,
        field_context: dict[str, Any],
        geofence: list[list[float]],
        crop_name: str,
        presentation_profile: dict[str, Any] | None,
    ) -> list[list[float]]:
        explicit_route = self._normalize_geofence(field_context.get("explicit_route", []))
        if len(explicit_route) >= 2:
            return explicit_route

        lane_spacing_m = self._resolve_lane_spacing(
            crop_name=crop_name,
            presentation_profile=presentation_profile,
        )
        return self._build_coverage_route(
            geofence,
            crop_name=crop_name,
            lane_spacing_m=lane_spacing_m,
        )

    def _resolve_lane_spacing(
        self,
        *,
        crop_name: str,
        presentation_profile: dict[str, Any] | None,
    ) -> float:
        if presentation_profile:
            custom_spacing = presentation_profile.get("lane_spacing_m")
            if isinstance(custom_spacing, (int, float)) and custom_spacing > 0:
                return float(custom_spacing)
        if "小麦" in crop_name:
            return 18.0
        if "玉米" in crop_name:
            return 22.0
        return 20.0

    def _build_waypoint_control(
        self,
        *,
        presentation_profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        presentation_profile = presentation_profile or {}
        acceptance_radius_m = presentation_profile.get("acceptance_radius_m")
        waypoint_loiter_time_s = presentation_profile.get("waypoint_loiter_time_s")
        fly_through = presentation_profile.get("fly_through")
        turn_mode = presentation_profile.get("turn_mode")
        turn_loiter_time_s = presentation_profile.get("turn_loiter_time_s")

        control: dict[str, Any] = {}
        if isinstance(acceptance_radius_m, (int, float)) and acceptance_radius_m > 0:
            control["接受半径"] = float(acceptance_radius_m)
        if isinstance(waypoint_loiter_time_s, (int, float)) and waypoint_loiter_time_s >= 0:
            control["到点停留秒数"] = float(waypoint_loiter_time_s)
        if isinstance(fly_through, bool):
            control["飞越航点"] = fly_through
        if isinstance(turn_mode, str) and turn_mode.strip():
            control["转弯模式"] = turn_mode.strip()
        if isinstance(turn_loiter_time_s, (int, float)) and turn_loiter_time_s >= 0:
            control["转弯停留秒数"] = float(turn_loiter_time_s)
        return control

    def _suggest_altitude(self, *, crop_name: str, area_mu: float) -> float:
        if "玉米" in crop_name:
            base = 3.8
        elif "小麦" in crop_name:
            base = 3.2
        else:
            base = 3.5
        if area_mu >= 80:
            base += 0.3
        return base

    def _suggest_speed(
        self,
        *,
        current_wind: float,
        speed_range: list[float],
        presentation_profile: dict[str, Any] | None = None,
    ) -> float:
        speed_min, speed_max = float(speed_range[0]), float(speed_range[1])
        if presentation_profile:
            target_speed = presentation_profile.get("target_speed_mps")
            if isinstance(target_speed, (int, float)):
                return float(target_speed)
        wind_ratio = min(max(current_wind / max(float(self.flight_constraints.get("max_safe_wind_speed_mps", 8.0)), 0.1), 0.0), 1.0)
        return speed_max - (speed_max - speed_min) * (0.45 + wind_ratio * 0.35)

    def _suggest_spray_rate(self, *, crop_name: str, area_mu: float) -> float:
        if "玉米" in crop_name:
            base = 1.3
        elif "小麦" in crop_name:
            base = 1.0
        else:
            base = 1.1
        if area_mu >= 80:
            base += 0.15
        return base

    def _clamp(self, value: float, value_range: list[float]) -> float:
        lower, upper = float(value_range[0]), float(value_range[1])
        return max(lower, min(upper, float(value)))
