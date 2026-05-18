"""Dependency injection for FastAPI routes."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from modules.infra.common import DATA_DIR, ensure_runtime_dirs

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


def _ensure_takeoff_state_dir() -> None:
    ensure_runtime_dirs()
    TAKEOFF_STATE_DIR.mkdir(parents=True, exist_ok=True)


def clear_takeoff_confirmation_state() -> None:
    """Clear shared takeoff confirmation state."""
    for path in (TAKEOFF_PENDING_REQUEST_PATH, TAKEOFF_CONFIRMATION_FLAG_PATH):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def set_pending_takeoff_request(request_id: str) -> None:
    """Persist the currently pending takeoff request for cross-process confirmation."""
    _ensure_takeoff_state_dir()
    clear_takeoff_confirmation_state()
    TAKEOFF_PENDING_REQUEST_PATH.write_text(
        json.dumps({"request_id": request_id}, ensure_ascii=False),
        encoding="utf-8",
    )


def get_pending_takeoff_request_id() -> str | None:
    """Return the pending takeoff request id from shared state."""
    if not TAKEOFF_PENDING_REQUEST_PATH.exists():
        return None
    try:
        payload = json.loads(TAKEOFF_PENDING_REQUEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    request_id = payload.get("request_id")
    return request_id if isinstance(request_id, str) and request_id else None


def is_takeoff_confirmed() -> bool:
    """Check whether takeoff was confirmed in-process or via shared state."""
    return bool(
        (takeoff_confirmation_event is not None and takeoff_confirmation_event.is_set())
        or TAKEOFF_CONFIRMATION_FLAG_PATH.exists()
    )


def mark_takeoff_confirmed() -> None:
    """Mark pending takeoff as confirmed for both local and external processes."""
    _ensure_takeoff_state_dir()
    TAKEOFF_CONFIRMATION_FLAG_PATH.write_text("confirmed\n", encoding="utf-8")
    if takeoff_confirmation_event is not None:
        takeoff_confirmation_event.set()


async def wait_for_takeoff_confirmation(
    poll_interval_seconds: float = 0.2,
    timeout_seconds: float = 300.0,
) -> None:
    """Wait until takeoff confirmation arrives from local or shared state."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if takeoff_confirmation_event is not None and takeoff_confirmation_event.is_set():
            return
        if TAKEOFF_CONFIRMATION_FLAG_PATH.exists():
            if takeoff_confirmation_event is not None:
                takeoff_confirmation_event.set()
            return
        await asyncio.sleep(poll_interval_seconds)
    raise asyncio.TimeoutError(
        f"起飞确认超时（{timeout_seconds}s），请在前端确认起飞"
    )


def iso_utc_offset(seconds_ago: int) -> str:
    """Generate ISO UTC timestamp with offset."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds_ago))
