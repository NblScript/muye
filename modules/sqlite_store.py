from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteStore:
    def __init__(self, db_path: Path, logger: logging.Logger | None = None) -> None:
        self.db_path = db_path
        self.logger = logger or logging.getLogger("muye.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")
        self.initialize()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _migrate_v1_1(self) -> None:
        """Apply migration for v1.1 to existing databases.

        - Ensure request_id indexes exist on child tables (handled later by initialize()).
        - Ensure tasks.status has CHECK constraint by recreating table when missing.
        Idempotent and safe to run multiple times.
        """
        with self._lock:
            cur = self._connection.cursor()
            # If tasks table does not exist, nothing to migrate
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone()
            if row is None:
                return

            # Check if CHECK constraint already present
            sql_row = cur.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone()
            table_sql = sql_row[0] if sql_row and sql_row[0] else ""
            has_check = "CHECK" in table_sql and "status" in table_sql and "queued" in table_sql
            if has_check:
                return

            self.logger.info("Applying v1.1 migration: add CHECK constraint to tasks.status")

            # Make a quick backup before destructive changes
            try:
                backup_path = self.db_path.with_suffix(self.db_path.suffix + ".bak")
                import shutil

                shutil.copy2(self.db_path, backup_path)
            except Exception as e:  # pragma: no cover - best-effort backup
                self.logger.warning("Backup before migration failed: %s", e)

            # Normalize invalid statuses up-front to avoid copy failures
            cur.execute(
                """
                UPDATE tasks
                SET status = CASE
                  WHEN status IN ('queued','running','completed','error') THEN status
                  ELSE 'error'
                END
                WHERE status IS NOT NULL
                """
            )
            self._connection.commit()

            # Rebuild tasks table with CHECK constraint
            cur.execute("PRAGMA foreign_keys = OFF")
            self._connection.execute("BEGIN IMMEDIATE")
            cur.execute("DROP TABLE IF EXISTS tasks_new")
            cur.execute(
                """
                CREATE TABLE tasks_new (
                  request_id TEXT PRIMARY KEY,
                  image_path TEXT,
                  start_time DATETIME,
                  end_time DATETIME,
                  status TEXT CHECK(status IN ('queued', 'running', 'completed', 'error'))
                )
                """
            )
            cur.execute(
                """
                INSERT INTO tasks_new (request_id, image_path, start_time, end_time, status)
                SELECT request_id, image_path, start_time, end_time,
                       CASE WHEN status IN ('queued','running','completed','error') OR status IS NULL
                            THEN status ELSE 'error' END
                FROM tasks
                """
            )
            cur.execute("DROP TABLE tasks")
            cur.execute("ALTER TABLE tasks_new RENAME TO tasks")
            self._connection.commit()
            cur.execute("PRAGMA foreign_keys = ON")
            self.logger.info("v1.1 migration complete: tasks.status now has CHECK constraint")

    def initialize(self) -> None:
        # Run migration first so that existing DBs gain new constraints/indexes
        self._migrate_v1_1()
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                  request_id TEXT PRIMARY KEY,
                  image_path TEXT,
                  start_time DATETIME,
                  end_time DATETIME,
                  status TEXT CHECK(status IN ('queued', 'running', 'completed', 'error'))
                );

                CREATE TABLE IF NOT EXISTS detections (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  request_id TEXT NOT NULL,
                  label TEXT,
                  confidence REAL,
                  bbox TEXT,
                  FOREIGN KEY (request_id) REFERENCES tasks(request_id)
                );

                CREATE TABLE IF NOT EXISTS weather_snapshots (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  request_id TEXT NOT NULL,
                  timestamp DATETIME,
                  weather_data TEXT,
                  FOREIGN KEY (request_id) REFERENCES tasks(request_id)
                );

                CREATE TABLE IF NOT EXISTS decisions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  request_id TEXT NOT NULL,
                  timestamp DATETIME,
                  decision_text TEXT,
                  FOREIGN KEY (request_id) REFERENCES tasks(request_id)
                );

                CREATE INDEX IF NOT EXISTS idx_detections_request_id
                ON detections(request_id);

                CREATE INDEX IF NOT EXISTS idx_weather_snapshots_request_id
                ON weather_snapshots(request_id);

                CREATE INDEX IF NOT EXISTS idx_decisions_request_id
                ON decisions(request_id);
                """
            )
            self._connection.commit()

    def mark_task_queued(self, request_id: str, image_path: str) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                """
                UPDATE tasks
                SET image_path = ?, status = COALESCE(status, ?)
                WHERE request_id = ?
                """,
                (image_path, "queued", request_id),
            )
            self._connection.commit()

    def mark_task_started(self, request_id: str, image_path: str) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                """
                UPDATE tasks
                SET image_path = ?,
                    start_time = COALESCE(start_time, ?),
                    status = ?
                WHERE request_id = ?
                """,
                (image_path, utc_now_iso(), "running", request_id),
            )
            self._connection.commit()

    def mark_task_finished(self, request_id: str, status: str) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                """
                UPDATE tasks
                SET end_time = ?, status = ?
                WHERE request_id = ?
                """,
                (utc_now_iso(), status, request_id),
            )
            self._connection.commit()

    def replace_detections(self, request_id: str, detections: list[dict[str, Any]]) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                "DELETE FROM detections WHERE request_id = ?",
                (request_id,),
            )
            self._connection.executemany(
                """
                INSERT INTO detections (request_id, label, confidence, bbox)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        request_id,
                        str(item.get("pest_type", "")),
                        float(item.get("confidence", 0.0)),
                        json.dumps(item.get("position", {}), ensure_ascii=False),
                    )
                    for item in detections
                ],
            )
            self._connection.commit()

    def add_weather_snapshot(self, request_id: str, weather_data: dict[str, Any]) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO weather_snapshots (request_id, timestamp, weather_data)
                VALUES (?, ?, ?)
                """,
                (
                    request_id,
                    utc_now_iso(),
                    json.dumps(weather_data, ensure_ascii=False),
                ),
            )
            self._connection.commit()

    def add_decision(self, request_id: str, decision: dict[str, Any]) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO decisions (request_id, timestamp, decision_text)
                VALUES (?, ?, ?)
                """,
                (
                    request_id,
                    utc_now_iso(),
                    json.dumps(decision, ensure_ascii=False),
                ),
            )
            self._connection.commit()

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(query, params).fetchone()
        return dict(row) if row is not None else None

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def _ensure_task(self, request_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO tasks (request_id) VALUES (?)",
                (request_id,),
            )
            self._connection.commit()
