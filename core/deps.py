"""Dependency injection for FastAPI routes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from services.map_simulator import Px4MapStateSimulator


# Global simulator instance (initialized in main.py)
simulator: Px4MapStateSimulator | None = None

# Global reference for health checks
embedded_yolo_runner_for_health: Any = None


def get_simulator() -> Px4MapStateSimulator:
    """Get the map state simulator instance."""
    if simulator is None:
        from services.map_simulator import Px4MapStateSimulator
        # Create a default simulator if not set
        simulator = Px4MapStateSimulator()
    return simulator


def get_embedded_yolo_runner() -> Any:
    """Get the embedded YOLO runner for health checks."""
    return embedded_yolo_runner_for_health


def iso_utc_offset(seconds_ago: int) -> str:
    """Generate ISO UTC timestamp with offset."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds_ago))
