"""Map state simulator for PX4 drone simulation."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from models.schemas import SimDroneState, SimMapStateResponse, SimPoint


@dataclass(frozen=True, slots=True)
class SimDroneBlueprint:
    """Blueprint for a simulated drone."""

    drone_id: str
    name: str
    status: str
    route: tuple[tuple[float, float], ...]
    speed_units_per_second: float
    battery_start: int
    battery_floor: int
    battery_drain_per_second: float
    phase_offset: float = 0.0


class Px4MapStateSimulator:
    """Simulator for PX4 map state with multiple drones."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._drones = (
            SimDroneBlueprint(
                drone_id="drone-a07",
                name="植保无人机 A-07",
                status="作业中",
                route=((24, 29), (34, 31), (48, 34), (54, 40), (42, 36)),
                speed_units_per_second=6.5,
                battery_start=86,
                battery_floor=34,
                battery_drain_per_second=0.22,
                phase_offset=0.0,
            ),
            SimDroneBlueprint(
                drone_id="drone-c12",
                name="植保无人机 C-12",
                status="返航",
                route=((104, 78), (98, 74), (94, 70), (90, 66), (80, 50)),
                speed_units_per_second=4.2,
                battery_start=58,
                battery_floor=18,
                battery_drain_per_second=0.18,
                phase_offset=0.35,
            ),
        )

    def snapshot(self) -> SimMapStateResponse:
        """Get a snapshot of the current map state."""
        with self._lock:
            drones = [self._build_drone_state(blueprint) for blueprint in self._drones]
        return SimMapStateResponse(timestamp=time.time(), drones=drones)

    def _build_drone_state(self, blueprint: SimDroneBlueprint) -> SimDroneState:
        """Build a SimDroneState from a blueprint."""
        anchor = blueprint.route[0] if blueprint.route else (0.0, 0.0)
        route = [SimPoint(x=x, y=y) for x, y in blueprint.route]
        return SimDroneState(
            id=blueprint.drone_id,
            name=blueprint.name,
            status=blueprint.status,
            battery=blueprint.battery_start,
            position=SimPoint(x=anchor[0], y=anchor[1]),
            route=route,
        )
