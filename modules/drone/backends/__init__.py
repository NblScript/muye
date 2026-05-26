"""Drone backend registry."""

from __future__ import annotations

from typing import Any

from modules.drone.backends.base import DroneBackend
from modules.drone.backends.dji_osdk import DJIOSDKBackend
from modules.drone.backends.px4_backend import PX4Backend

BACKEND_REGISTRY: dict[str, type[DroneBackend]] = {
    "px4": PX4Backend,
    "dji_osdk": DJIOSDKBackend,
}


def resolve_backend(
    name: str,
    drone_config: dict[str, Any],
    logger: Any = None,
) -> DroneBackend:
    """根据名称查找并实例化后端，未知名称降级到 PX4Backend。"""
    cls = BACKEND_REGISTRY.get(name, PX4Backend)
    return cls(drone_config, logger=logger)


__all__ = [
    "DroneBackend",
    "DJIOSDKBackend",
    "PX4Backend",
    "BACKEND_REGISTRY",
    "resolve_backend",
]
