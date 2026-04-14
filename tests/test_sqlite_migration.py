from __future__ import annotations

import sqlite3

from modules.sqlite_store import SqliteStore


def test_sqlite_store_migrates_legacy_database_to_v1_1(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE tasks (
              request_id TEXT PRIMARY KEY,
              image_path TEXT,
              start_time DATETIME,
              end_time DATETIME,
              status TEXT
            );

            CREATE TABLE detections (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id TEXT NOT NULL,
              label TEXT,
              confidence REAL,
              bbox TEXT,
              FOREIGN KEY (request_id) REFERENCES tasks(request_id)
            );

            CREATE TABLE weather_snapshots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id TEXT NOT NULL,
              timestamp DATETIME,
              weather_data TEXT,
              FOREIGN KEY (request_id) REFERENCES tasks(request_id)
            );

            CREATE TABLE decisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id TEXT NOT NULL,
              timestamp DATETIME,
              decision_text TEXT,
              FOREIGN KEY (request_id) REFERENCES tasks(request_id)
            );
            """
        )
        connection.execute(
            """
            INSERT INTO tasks (request_id, image_path, start_time, end_time, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("req-legacy", "/tmp/legacy.jpg", "2026-04-14T00:00:00+00:00", None, "broken-status"),
        )
        connection.execute(
            """
            INSERT INTO detections (request_id, label, confidence, bbox)
            VALUES (?, ?, ?, ?)
            """,
            ("req-legacy", "aphid", 0.95, '{"x1":1,"y1":2,"x2":3,"y2":4}'),
        )
        connection.commit()
    finally:
        connection.close()

    store = SqliteStore(db_path)
    try:
        task = store.fetch_one(
            "SELECT request_id, image_path, status FROM tasks WHERE request_id = ?",
            ("req-legacy",),
        )
        detections = store.fetch_all(
            "SELECT request_id, label FROM detections WHERE request_id = ?",
            ("req-legacy",),
        )
        task_table_sql = store.fetch_one(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        )
        detection_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('detections')")
        }
        weather_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('weather_snapshots')")
        }
        decision_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('decisions')")
        }
    finally:
        store.close()

    assert task is not None
    assert task["request_id"] == "req-legacy"
    assert task["image_path"] == "/tmp/legacy.jpg"
    assert task["status"] == "error"

    assert len(detections) == 1
    assert detections[0]["label"] == "aphid"

    assert task_table_sql is not None
    assert "CHECK" in task_table_sql["sql"]
    assert "queued" in task_table_sql["sql"]
    assert "error" in task_table_sql["sql"]

    assert "idx_detections_request_id" in detection_indexes
    assert "idx_weather_snapshots_request_id" in weather_indexes
    assert "idx_decisions_request_id" in decision_indexes
