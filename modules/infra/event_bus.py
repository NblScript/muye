from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import fcntl

from modules.infra.common import LOGS_DIR, ensure_runtime_dirs


EVENTS_FILE = LOGS_DIR / "demo_events.jsonl"


class FileEventBus:
    def __init__(
        self,
        path: Path | None = None,
        *,
        max_file_size_mb: float = 10.0,
        max_backup_files: int = 5,
    ) -> None:
        ensure_runtime_dirs()
        self.path = path or EVENTS_FILE
        self.max_file_size_mb = max_file_size_mb
        self.max_backup_files = max_backup_files
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    # ------------------------------------------------------------------
    # Log rotation helpers
    # ------------------------------------------------------------------

    def _should_rotate(self) -> bool:
        """Return True if the current log file exceeds *max_file_size_mb*."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return False
        return size >= self.max_file_size_mb * 1024 * 1024

    def _rotate_log(self) -> None:
        """Rotate the log file: events.jsonl → .1, .1 → .2, … drop oldest."""
        # Delete the oldest backup if it would exceed the limit.
        oldest = self.path.parent / f"{self.path.name}.{self.max_backup_files}"
        if oldest.exists():
            oldest.unlink()

        # Shift existing backup files up by one index.
        for i in range(self.max_backup_files - 1, 0, -1):
            src = self.path.parent / f"{self.path.name}.{i}"
            dst = self.path.parent / f"{self.path.name}.{i + 1}"
            if src.exists():
                src.rename(dst)

        # Rename the current file to .1.
        backup_1 = self.path.parent / f"{self.path.name}.1"
        self.path.rename(backup_1)

        # Create a fresh, empty log file.
        self.path.touch(exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(
        self,
        *,
        request_id: str,
        stage: str,
        status: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": uuid4().hex,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "stage": stage,
            "status": status,
            "message": message,
            "payload": payload or {},
        }
        file = self.path.open("a", encoding="utf-8")
        try:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            if self._should_rotate():
                file.close()
                self._rotate_log()
                file = self.path.open("a", encoding="utf-8")
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
            file.flush()
        finally:
            try:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
            except (ValueError, OSError):
                pass
            file.close()
        return event

    def clear(self) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            file.truncate(0)
            file.flush()
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def load_events(path: Path | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    target = path or EVENTS_FILE
    if not target.exists():
        return []

    with target.open("r", encoding="utf-8") as file:
        fcntl.flock(file.fileno(), fcntl.LOCK_SH)
        lines = file.readlines()
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)

    parsed: list[dict[str, Any]] = []
    for line in lines:
        candidate = line.strip()
        if not candidate:
            continue
        try:
            parsed.append(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    if limit is not None:
        return parsed[-limit:]
    return parsed


def build_task_views(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for event in events:
        request_id = str(event.get("request_id", "unknown"))
        if request_id not in tasks:
            tasks[request_id] = {
                "request_id": request_id,
                "created_at": event.get("timestamp"),
                "updated_at": event.get("timestamp"),
                "current_stage": event.get("stage"),
                "status": event.get("status"),
                "message": event.get("message"),
                "image_path": None,
                "detections": [],
                "weather": {},
                "decision": {},
                "drone": {},
                "drone_timeline": [],
                "events": [],
                "error": None,
            }
            order.append(request_id)

        task = tasks[request_id]
        payload = event.get("payload") or {}

        task["updated_at"] = event.get("timestamp")
        task["current_stage"] = event.get("stage")
        task["status"] = event.get("status")
        task["message"] = event.get("message")
        task["events"].append(event)

        image_path = payload.get("image_path")
        if image_path:
            task["image_path"] = image_path

        if event.get("stage") == "yolo" and "detections" in payload:
            task["detections"] = payload.get("detections") or []

        if event.get("stage") == "weather" and "weather" in payload:
            task["weather"] = payload["weather"]

        if event.get("stage") == "decision" and "decision" in payload:
            task["decision"] = payload["decision"]
            if "rag_context" in payload:
                task["rag_context"] = payload["rag_context"]

        if event.get("stage") == "drone":
            task["drone"] = {
                **task.get("drone", {}),
                **payload,
                "status": event.get("status"),
                "message": event.get("message"),
            }
            timeline_entry = {
                "timestamp": event.get("timestamp"),
                "status": event.get("status"),
                "message": event.get("message"),
                "progress": payload.get("progress"),
                "current_waypoint_index": payload.get("current_waypoint_index"),
                "task_id": payload.get("task_id"),
            }
            timeline = task["drone_timeline"]
            if timeline and timeline[-1].get("status") == timeline_entry["status"]:
                timeline[-1] = {
                    **timeline[-1],
                    **timeline_entry,
                }
            else:
                timeline.append(timeline_entry)

        if event.get("status") == "error":
            task["error"] = payload.get("error") or event.get("message")

    return [tasks[request_id] for request_id in reversed(order)]
