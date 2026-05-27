"""SQLite-backed takeoff confirmation state with file/event compatibility."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from modules.infra.common import DATA_DIR, ensure_runtime_dirs
from app.services.workflow_service import get_sqlite_store


ACTION_TYPE = "takeoff_confirmation"
TAKEOFF_STATE_DIR = DATA_DIR / "runtime" / "takeoff"
TAKEOFF_PENDING_REQUEST_PATH = TAKEOFF_STATE_DIR / "pending_request.json"
TAKEOFF_CONFIRMATION_FLAG_PATH = TAKEOFF_STATE_DIR / "confirmed.flag"


def _with_store(callback: Callable[[Any], Any]) -> Any:
    store = get_sqlite_store()
    return callback(store)


def _ensure_takeoff_state_dir(state_dir: Path = TAKEOFF_STATE_DIR) -> None:
    ensure_runtime_dirs()
    state_dir.mkdir(parents=True, exist_ok=True)


def clear_takeoff_confirmation_state(
    *,
    pending_path: Path = TAKEOFF_PENDING_REQUEST_PATH,
    flag_path: Path = TAKEOFF_CONFIRMATION_FLAG_PATH,
) -> None:
    """Clear shared takeoff confirmation state."""
    for path in (pending_path, flag_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    _with_store(lambda store: store.clear_pending_actions(ACTION_TYPE))


def set_pending_takeoff_request(
    request_id: str,
    *,
    pending_path: Path = TAKEOFF_PENDING_REQUEST_PATH,
    flag_path: Path = TAKEOFF_CONFIRMATION_FLAG_PATH,
) -> None:
    """Persist the currently pending takeoff request for cross-process confirmation."""
    _ensure_takeoff_state_dir(pending_path.parent)
    clear_takeoff_confirmation_state(pending_path=pending_path, flag_path=flag_path)
    pending_path.write_text(
        json.dumps({"request_id": request_id}, ensure_ascii=False),
        encoding="utf-8",
    )
    _with_store(
        lambda store: store.create_pending_action(
            request_id=request_id,
            action_type=ACTION_TYPE,
        )
    )


def _pending_request_id_from_file(pending_path: Path = TAKEOFF_PENDING_REQUEST_PATH) -> str | None:
    if not pending_path.exists():
        return None
    try:
        payload = json.loads(pending_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    request_id = payload.get("request_id")
    return request_id if isinstance(request_id, str) and request_id else None


def get_pending_takeoff_request_id(
    *,
    pending_path: Path = TAKEOFF_PENDING_REQUEST_PATH,
) -> str | None:
    """Return the pending takeoff request id from SQLite or legacy file state."""
    pending = _with_store(lambda store: store.get_pending_action(ACTION_TYPE))
    if pending and pending.get("request_id"):
        return str(pending["request_id"])
    return _pending_request_id_from_file(pending_path)


def is_takeoff_confirmed(
    *,
    pending_path: Path = TAKEOFF_PENDING_REQUEST_PATH,
    flag_path: Path = TAKEOFF_CONFIRMATION_FLAG_PATH,
) -> bool:
    """Check whether takeoff was confirmed through SQLite or legacy file state."""
    if flag_path.exists():
        return True
    pending_request_id = _pending_request_id_from_file(pending_path)
    if not pending_request_id:
        return False
    row = _with_store(
        lambda store: store.fetch_one(
            """
            SELECT status
            FROM pending_actions
            WHERE request_id = ? AND action_type = ?
            """,
            (pending_request_id, ACTION_TYPE),
        )
    )
    return bool(row and row.get("status") == "confirmed")


def mark_takeoff_confirmed(
    *,
    pending_path: Path = TAKEOFF_PENDING_REQUEST_PATH,
    flag_path: Path = TAKEOFF_CONFIRMATION_FLAG_PATH,
) -> None:
    """Mark pending takeoff as confirmed for SQLite and legacy file consumers."""
    _ensure_takeoff_state_dir(flag_path.parent)
    pending_request_id = get_pending_takeoff_request_id(pending_path=pending_path)
    if pending_request_id:
        _with_store(lambda store: store.confirm_pending_action(pending_request_id, ACTION_TYPE))
    flag_path.write_text("confirmed\n", encoding="utf-8")


def expire_pending_takeoff_request(
    *,
    pending_path: Path = TAKEOFF_PENDING_REQUEST_PATH,
) -> None:
    """Mark the current pending takeoff action as expired in SQLite."""
    pending_request_id = get_pending_takeoff_request_id(pending_path=pending_path)
    if pending_request_id:
        _with_store(lambda store: store.expire_pending_action(pending_request_id, ACTION_TYPE))


async def wait_for_takeoff_confirmation(
    poll_interval_seconds: float = 0.2,
    timeout_seconds: float = 300.0,
    *,
    pending_path: Path = TAKEOFF_PENDING_REQUEST_PATH,
    flag_path: Path = TAKEOFF_CONFIRMATION_FLAG_PATH,
) -> None:
    """Wait until takeoff confirmation arrives from SQLite or legacy file state."""
    pending_request_id = get_pending_takeoff_request_id(pending_path=pending_path)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_takeoff_confirmed(pending_path=pending_path, flag_path=flag_path):
            return
        await asyncio.sleep(poll_interval_seconds)
    expire_pending_takeoff_request(pending_path=pending_path)
    raise asyncio.TimeoutError(
        f"起飞确认超时（{timeout_seconds}s），请在前端确认起飞"
    )
