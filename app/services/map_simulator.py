"""Map state simulator for PX4 drone simulation."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from functools import lru_cache

from models.schemas import SimDroneState, SimMapStateResponse, SimPoint
from modules.infra.common import CONFIG_DIR, load_json


@lru_cache(maxsize=1)
def _load_demo_route() -> tuple[tuple[float, float], ...]:
    """Load demo route from drone_config.json (px4.demo_field.explicit_route).

    Each config point is [longitude, latitude]; maps to (x=lng, y=lat).
    """
    config = load_json(CONFIG_DIR / "drone_config.json")
    raw: list[list[float]] = (
        config.get("px4", {}).get("demo_field", {}).get("explicit_route", [])
    )
    if not raw:
        # Fallback: minimal rectangle
        return ((8.5452, 47.3975), (8.5460, 47.3975), (8.5460, 47.3980), (8.5452, 47.3980))
    return tuple((pt[0], pt[1]) for pt in raw)


@dataclass(frozen=True, slots=True)
class SimDroneBlueprint:
    """Blueprint for the PX4 map fallback drone."""

    drone_id: str
    name: str
    status: str
    route: tuple[tuple[float, float], ...]
    speed_units_per_second: float
    battery_start: int
    battery_floor: int
    battery_drain_per_second: float
    phase_offset: float = 0.0


def _route_length(route: tuple[tuple[float, float], ...]) -> float:
    """Compute the total arc length of a route."""
    total = 0.0
    for i in range(1, len(route)):
        dx = route[i][0] - route[i - 1][0]
        dy = route[i][1] - route[i - 1][1]
        total += math.hypot(dx, dy)
    return total


def _interpolate_on_route(
    route: tuple[tuple[float, float], ...],
    distance: float,
) -> tuple[float, float]:
    """Return the (x, y) point at *distance* along the route, clamped to ends."""
    if len(route) == 0:
        return (0.0, 0.0)
    if len(route) == 1:
        return route[0]

    remaining = distance
    for i in range(1, len(route)):
        dx = route[i][0] - route[i - 1][0]
        dy = route[i][1] - route[i - 1][1]
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-9:
            continue
        if remaining <= seg_len:
            ratio = remaining / seg_len
            return (route[i - 1][0] + dx * ratio, route[i - 1][1] + dy * ratio)
        remaining -= seg_len

    return route[-1]


class Px4MapStateSimulator:
    """Simulator for PX4 map state with multiple drones.

    Drones move along their route over time, cycling back to the start
    when they reach the end. Battery drains linearly with time spent
    flying and resets when the drone loops.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._epoch = time.monotonic()
        self._drones = (
            SimDroneBlueprint(
                drone_id="px4-demo",
                name="PX4 植保无人机",
                status="作业中",
                route=_load_demo_route(),
                speed_units_per_second=6.5,
                battery_start=86,
                battery_floor=34,
                battery_drain_per_second=0.22,
                phase_offset=0.0,
            ),
        )

    def snapshot(self) -> SimMapStateResponse:
        """Get a snapshot of the current map state."""
        now = time.monotonic()
        elapsed = now - self._epoch
        with self._lock:
            drones = [
                self._build_drone_state(blueprint, elapsed)
                for blueprint in self._drones
            ]
        return SimMapStateResponse(timestamp=time.time(), drones=drones)

    def _build_drone_state(
        self,
        blueprint: SimDroneBlueprint,
        elapsed: float,
    ) -> SimDroneState:
        """Build a SimDroneState from a blueprint, advancing along the route."""
        route = blueprint.route
        if not route:
            return SimDroneState(
                id=blueprint.drone_id,
                name=blueprint.name,
                status=blueprint.status,
                battery=blueprint.battery_start,
                position=SimPoint(x=0.0, y=0.0),
                route=[],
            )

        # Total route length and round-trip time
        total_len = _route_length(route)
        cycle_time = total_len / blueprint.speed_units_per_second if blueprint.speed_units_per_second > 0 else 1.0

        # Effective time with phase offset and cycling
        effective_time = elapsed + blueprint.phase_offset * cycle_time
        cycle_count = int(effective_time / cycle_time) if cycle_time > 0 else 0
        time_in_cycle = effective_time - cycle_count * cycle_time

        # Position along the route
        distance = time_in_cycle * blueprint.speed_units_per_second
        x, y = _interpolate_on_route(route, distance)

        # Battery: drain linearly during each cycle, reset on loop
        battery_drain = time_in_cycle * blueprint.battery_drain_per_second
        battery = max(
            blueprint.battery_floor,
            round(blueprint.battery_start - battery_drain),
        )

        route_points = [SimPoint(x=px, y=py) for px, py in route]
        return SimDroneState(
            id=blueprint.drone_id,
            name=blueprint.name,
            status=blueprint.status,
            battery=battery,
            position=SimPoint(x=x, y=y),
            route=route_points,
        )
