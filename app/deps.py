"""Dependency injection for FastAPI routes."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from modules.infra.common import DATA_DIR

if TYPE_CHECKING:
    from app.services.map_simulator import Px4MapStateSimulator


# Global simulator instance (initialized in app.main)
simulator: Px4MapStateSimulator | None = None

# Global reference for health checks
embedded_yolo_runner_for_health: Any = None

# Global reference for takeoff confirmation (initialized in app.main)
takeoff_confirmation_event: asyncio.Event | None = None

TAKEOFF_STATE_DIR = DATA_DIR / "runtime" / "takeoff"
TAKEOFF_PENDING_REQUEST_PATH = TAKEOFF_STATE_DIR / "pending_request.json"
TAKEOFF_CONFIRMATION_FLAG_PATH = TAKEOFF_STATE_DIR / "confirmed.flag"

def get_simulator() -> Px4MapStateSimulator:
    """Get the map state simulator instance."""
    global simulator
    if simulator is None:
        from app.services.map_simulator import Px4MapStateSimulator
        # Create a default simulator if not set
        simulator = Px4MapStateSimulator()
    return simulator


def get_embedded_yolo_runner() -> Any:
    """Get the embedded YOLO runner for health checks."""
    return embedded_yolo_runner_for_health


def clear_takeoff_confirmation_state() -> None:
    """Clear shared takeoff confirmation state."""
    from app.services.takeoff_confirmation_service import clear_takeoff_confirmation_state as clear_state
    clear_state(
        pending_path=TAKEOFF_PENDING_REQUEST_PATH,
        flag_path=TAKEOFF_CONFIRMATION_FLAG_PATH,
    )
    if takeoff_confirmation_event is not None:
        takeoff_confirmation_event.clear()


def set_pending_takeoff_request(request_id: str) -> None:
    """Persist the currently pending takeoff request for cross-process confirmation."""
    from app.services.takeoff_confirmation_service import set_pending_takeoff_request as set_pending
    set_pending(
        request_id,
        pending_path=TAKEOFF_PENDING_REQUEST_PATH,
        flag_path=TAKEOFF_CONFIRMATION_FLAG_PATH,
    )


def get_pending_takeoff_request_id() -> str | None:
    """Return the pending takeoff request id from shared state."""
    from app.services.takeoff_confirmation_service import get_pending_takeoff_request_id as get_pending
    return get_pending(pending_path=TAKEOFF_PENDING_REQUEST_PATH)


def is_takeoff_confirmed() -> bool:
    """Check whether takeoff was confirmed in-process or via shared state."""
    from app.services.takeoff_confirmation_service import is_takeoff_confirmed as is_confirmed
    return bool(
        (takeoff_confirmation_event is not None and takeoff_confirmation_event.is_set())
        or is_confirmed(
            pending_path=TAKEOFF_PENDING_REQUEST_PATH,
            flag_path=TAKEOFF_CONFIRMATION_FLAG_PATH,
        )
    )


def mark_takeoff_confirmed() -> None:
    """Mark pending takeoff as confirmed for both local and external processes."""
    from app.services.takeoff_confirmation_service import mark_takeoff_confirmed as mark_confirmed
    mark_confirmed(
        pending_path=TAKEOFF_PENDING_REQUEST_PATH,
        flag_path=TAKEOFF_CONFIRMATION_FLAG_PATH,
    )
    if takeoff_confirmation_event is not None:
        takeoff_confirmation_event.set()


async def wait_for_takeoff_confirmation(
    poll_interval_seconds: float = 0.2,
    timeout_seconds: float = 300.0,
) -> None:
    """Wait until takeoff confirmation arrives from local or shared state."""
    from app.services.takeoff_confirmation_service import expire_pending_takeoff_request

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if takeoff_confirmation_event is not None and takeoff_confirmation_event.is_set():
            return
        if is_takeoff_confirmed():
            if takeoff_confirmation_event is not None:
                takeoff_confirmation_event.set()
            return
        await asyncio.sleep(poll_interval_seconds)
    expire_pending_takeoff_request(
        pending_path=TAKEOFF_PENDING_REQUEST_PATH,
    )
    raise asyncio.TimeoutError(
        f"起飞确认超时（{timeout_seconds}s），请在前端确认起飞"
    )


def iso_utc_offset(seconds_ago: int) -> str:
    """Generate ISO UTC timestamp with offset."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds_ago))
