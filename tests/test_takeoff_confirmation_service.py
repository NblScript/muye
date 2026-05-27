from __future__ import annotations

from pathlib import Path

import pytest

import app.deps as deps
from app.services import takeoff_confirmation_service as service
from modules.infra.sqlite_store import SqliteStore


def test_sqlite_store_tracks_pending_takeoff_action_lifecycle(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    try:
        store.create_pending_action(
            request_id="req-1",
            action_type="takeoff_confirmation",
            expires_at="2026-05-27T12:00:00Z",
        )

        pending = store.get_pending_action("takeoff_confirmation")
        assert pending is not None
        assert pending["request_id"] == "req-1"
        assert pending["status"] == "pending"
        assert pending["expires_at"] == "2026-05-27T12:00:00Z"

        assert store.confirm_pending_action("req-1", "takeoff_confirmation") is True
        confirmed = store.get_pending_action("takeoff_confirmation")
        assert confirmed is None

        row = store.fetch_one(
            """
            SELECT request_id, action_type, status, confirmed_at
            FROM pending_actions
            WHERE request_id = ?
            """,
            ("req-1",),
        )
        assert row is not None
        assert row["status"] == "confirmed"
        assert row["confirmed_at"]
    finally:
        store.close()


def test_sqlite_store_expires_pending_takeoff_action(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "muye.db")
    try:
        store.create_pending_action(
            request_id="req-2",
            action_type="takeoff_confirmation",
        )

        assert store.expire_pending_action("req-2", "takeoff_confirmation") is True
        assert store.get_pending_action("takeoff_confirmation") is None

        row = store.fetch_one(
            "SELECT status FROM pending_actions WHERE request_id = ?",
            ("req-2",),
        )
        assert row is not None
        assert row["status"] == "expired"
    finally:
        store.close()


def test_takeoff_service_uses_sqlite_for_cross_process_confirmation(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "muye.db"
    monkeypatch.setenv("MUYE_SQLITE_PATH", str(db_path))

    service.set_pending_takeoff_request("req-3")

    assert service.get_pending_takeoff_request_id() == "req-3"
    assert service.is_takeoff_confirmed() is False

    service.mark_takeoff_confirmed()

    assert service.is_takeoff_confirmed() is True
    store = SqliteStore(db_path)
    try:
        row = store.fetch_one(
            "SELECT status FROM pending_actions WHERE request_id = ?",
            ("req-3",),
        )
        assert row is not None
        assert row["status"] == "confirmed"
    finally:
        store.close()


@pytest.mark.asyncio
async def test_takeoff_service_wait_marks_pending_action_expired(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "muye.db"
    monkeypatch.setenv("MUYE_SQLITE_PATH", str(db_path))
    service.set_pending_takeoff_request("req-4")

    with pytest.raises(TimeoutError):
        await service.wait_for_takeoff_confirmation(
            poll_interval_seconds=0.01,
            timeout_seconds=0.01,
        )

    store = SqliteStore(db_path)
    try:
        row = store.fetch_one(
            "SELECT status FROM pending_actions WHERE request_id = ?",
            ("req-4",),
        )
        assert row is not None
        assert row["status"] == "expired"
    finally:
        store.close()


@pytest.mark.asyncio
async def test_deps_wait_preserves_timeout_message_and_expires_action(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "muye.db"
    pending_path = tmp_path / "pending_request.json"
    flag_path = tmp_path / "confirmed.flag"
    monkeypatch.setenv("MUYE_SQLITE_PATH", str(db_path))
    monkeypatch.setattr(deps, "TAKEOFF_PENDING_REQUEST_PATH", pending_path)
    monkeypatch.setattr(deps, "TAKEOFF_CONFIRMATION_FLAG_PATH", flag_path)
    monkeypatch.setattr(deps, "takeoff_confirmation_event", None)
    deps.set_pending_takeoff_request("req-5")

    with pytest.raises(TimeoutError, match=r"0.02s"):
        await deps.wait_for_takeoff_confirmation(
            poll_interval_seconds=0.01,
            timeout_seconds=0.02,
        )

    store = SqliteStore(db_path)
    try:
        row = store.fetch_one(
            "SELECT status FROM pending_actions WHERE request_id = ?",
            ("req-5",),
        )
        assert row is not None
        assert row["status"] == "expired"
    finally:
        store.close()
