from __future__ import annotations

import json
import logging
import math
import sqlite3
import threading
from pathlib import Path
from typing import Any

from modules.infra.common import METERS_PER_DEGREE_LAT, safe_float

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
  request_id TEXT PRIMARY KEY,
  field_id TEXT,
  image_path TEXT,
  start_time DATETIME,
  end_time DATETIME,
  status TEXT CHECK(status IN ('queued', 'running', 'completed', 'blocked', 'error'))
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

CREATE TABLE IF NOT EXISTS drone_mission_updates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  timestamp DATETIME,
  task_id TEXT,
  status TEXT,
  message TEXT,
  progress INTEGER,
  current_waypoint_index INTEGER,
  instruction TEXT,
  medication TEXT,
  FOREIGN KEY (request_id) REFERENCES tasks(request_id)
);

CREATE TABLE IF NOT EXISTS pending_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  status TEXT CHECK(status IN ('pending', 'confirmed', 'expired', 'cancelled')) NOT NULL,
  created_at DATETIME NOT NULL,
  confirmed_at DATETIME,
  expires_at DATETIME,
  UNIQUE(request_id, action_type)
);

CREATE TABLE IF NOT EXISTS fields (
  field_id TEXT PRIMARY KEY,
  field_code TEXT UNIQUE,
  field_name TEXT NOT NULL,
  owner_user_id TEXT,
  province TEXT,
  city TEXT,
  county TEXT,
  township TEXT,
  village TEXT,
  latitude REAL,
  longitude REAL,
  area_mu REAL,
  area_hectare REAL,
  geofence TEXT,
  soil_type TEXT,
  irrigation_type TEXT,
  source TEXT,
  notes TEXT,
  created_at DATETIME,
  updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS crop_catalog (
  crop_code TEXT PRIMARY KEY,
  crop_name TEXT NOT NULL,
  category TEXT,
  variety TEXT,
  growth_cycle_days INTEGER,
  water_demand_coefficient REAL,
  typical_planting_month TEXT,
  typical_harvest_month TEXT,
  source TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS field_crop_cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  field_id TEXT NOT NULL,
  crop_code TEXT NOT NULL,
  year INTEGER,
  season TEXT,
  planting_date DATE,
  harvest_date DATE,
  area_mu REAL,
  expected_yield_kg REAL,
  actual_yield_kg REAL,
  status TEXT CHECK(status IN ('planned', 'planted', 'growing', 'harvested', 'cancelled')),
  source TEXT,
  notes TEXT,
  FOREIGN KEY (field_id) REFERENCES fields(field_id),
  FOREIGN KEY (crop_code) REFERENCES crop_catalog(crop_code)
);

CREATE TABLE IF NOT EXISTS soil_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  field_id TEXT NOT NULL,
  sample_date DATE,
  depth_cm INTEGER,
  ph REAL,
  organic_matter_gkg REAL,
  alkali_hydrolyzable_nitrogen_mgkg REAL,
  available_phosphorus_mgkg REAL,
  available_potassium_mgkg REAL,
  moisture_percent REAL,
  salinity_gkg REAL,
  texture TEXT,
  source TEXT,
  raw_payload TEXT,
  FOREIGN KEY (field_id) REFERENCES fields(field_id)
);

CREATE TABLE IF NOT EXISTS weather_stations (
  station_code TEXT PRIMARY KEY,
  station_name TEXT NOT NULL,
  province TEXT,
  city TEXT,
  county TEXT,
  latitude REAL,
  longitude REAL,
  elevation_m REAL,
  source_id TEXT,
  notes TEXT,
  FOREIGN KEY (source_id) REFERENCES data_sources(source_id)
);

CREATE TABLE IF NOT EXISTS weather_history_daily (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  field_id TEXT,
  station_code TEXT,
  station_name TEXT,
  observation_date DATE NOT NULL,
  weather_summary TEXT,
  temperature_avg_c REAL,
  temperature_min_c REAL,
  temperature_max_c REAL,
  humidity_avg_percent REAL,
  precipitation_mm REAL,
  wind_speed_avg_mps REAL,
  wind_direction TEXT,
  sunshine_hours REAL,
  source TEXT,
  raw_payload TEXT,
  FOREIGN KEY (field_id) REFERENCES fields(field_id)
);

CREATE TABLE IF NOT EXISTS pesticide_catalog (
  pesticide_id TEXT PRIMARY KEY,
  registration_no TEXT UNIQUE,
  product_name TEXT NOT NULL,
  active_ingredient TEXT,
  formulation TEXT,
  toxicity TEXT,
  manufacturer TEXT,
  target_crops TEXT,
  target_pests TEXT,
  dilution_guidance TEXT,
  source TEXT,
  raw_payload TEXT
);

CREATE TABLE IF NOT EXISTS spray_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT,
  field_id TEXT NOT NULL,
  crop_cycle_id INTEGER,
  drone_task_id TEXT,
  pesticide_id TEXT,
  spray_date DATETIME NOT NULL,
  operator_name TEXT,
  spray_area_mu REAL,
  dosage_per_mu REAL,
  total_dosage REAL,
  dilution_ratio TEXT,
  spray_rate_lpm REAL,
  flight_height_m REAL,
  flight_speed_mps REAL,
  weather_snapshot TEXT,
  result_status TEXT CHECK(result_status IN ('planned', 'in_progress', 'completed', 'failed', 'cancelled')),
  source TEXT,
  notes TEXT,
  FOREIGN KEY (request_id) REFERENCES tasks(request_id),
  FOREIGN KEY (field_id) REFERENCES fields(field_id),
  FOREIGN KEY (crop_cycle_id) REFERENCES field_crop_cycles(id),
  FOREIGN KEY (pesticide_id) REFERENCES pesticide_catalog(pesticide_id)
);

CREATE TABLE IF NOT EXISTS data_sources (
  source_id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL,
  publisher TEXT,
  region_scope TEXT,
  source_type TEXT,
  source_url TEXT NOT NULL,
  access_level TEXT,
  retrieval_date DATE,
  license TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS agri_statistical_indicators (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  region_level TEXT NOT NULL,
  region_name TEXT NOT NULL,
  province TEXT,
  city TEXT,
  county TEXT,
  year INTEGER NOT NULL,
  period TEXT NOT NULL,
  indicator_code TEXT NOT NULL,
  indicator_name TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT,
  source_id TEXT,
  source_excerpt TEXT,
  raw_payload TEXT,
  UNIQUE (
    region_level, region_name, province, city, county,
    year, period, indicator_code
  ),
  FOREIGN KEY (source_id) REFERENCES data_sources(source_id)
);

CREATE INDEX IF NOT EXISTS idx_detections_request_id
ON detections(request_id);
CREATE INDEX IF NOT EXISTS idx_weather_snapshots_request_id
ON weather_snapshots(request_id);
CREATE INDEX IF NOT EXISTS idx_decisions_request_id
ON decisions(request_id);
CREATE INDEX IF NOT EXISTS idx_drone_mission_updates_request_id
ON drone_mission_updates(request_id);
CREATE INDEX IF NOT EXISTS idx_pending_actions_type_status
ON pending_actions(action_type, status);
CREATE INDEX IF NOT EXISTS idx_fields_city_county
ON fields(city, county);
CREATE INDEX IF NOT EXISTS idx_field_crop_cycles_field_id
ON field_crop_cycles(field_id);
CREATE INDEX IF NOT EXISTS idx_field_crop_cycles_crop_code
ON field_crop_cycles(crop_code);
CREATE INDEX IF NOT EXISTS idx_soil_records_field_id_sample_date
ON soil_records(field_id, sample_date);
CREATE INDEX IF NOT EXISTS idx_weather_stations_city_county
ON weather_stations(city, county);
CREATE INDEX IF NOT EXISTS idx_weather_history_daily_field_date
ON weather_history_daily(field_id, observation_date);
CREATE INDEX IF NOT EXISTS idx_weather_history_daily_station_date
ON weather_history_daily(station_code, observation_date);
CREATE INDEX IF NOT EXISTS idx_spray_records_field_date
ON spray_records(field_id, spray_date);
CREATE INDEX IF NOT EXISTS idx_spray_records_request_id
ON spray_records(request_id);
CREATE INDEX IF NOT EXISTS idx_spray_records_crop_cycle_id
ON spray_records(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_agri_statistical_indicators_region_year
ON agri_statistical_indicators(province, city, county, year);
CREATE INDEX IF NOT EXISTS idx_agri_statistical_indicators_code
ON agri_statistical_indicators(indicator_code);
"""

from modules.infra.sqlite_store._private import utc_now_iso


class BaseMixin:
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
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone()
            if row is None:
                return

            sql_row = cur.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone()
            table_sql = sql_row[0] if sql_row and sql_row[0] else ""
            has_check = "CHECK" in table_sql and "status" in table_sql and "queued" in table_sql
            if has_check and "blocked" in table_sql:
                return

            self.logger.info("Applying v1.1 migration: update CHECK constraint on tasks.status")

            try:
                backup_path = self.db_path.with_suffix(self.db_path.suffix + ".bak")
                import shutil

                shutil.copy2(self.db_path, backup_path)
            except Exception as e:  # pragma: no cover - best-effort backup
                self.logger.warning("Backup before migration failed: %s", e)

            cur.execute(
                """
                UPDATE tasks
                SET status = CASE
                  WHEN status IN ('queued','running','completed','blocked','error') THEN status
                  ELSE 'error'
                END
                WHERE status IS NOT NULL
                """
            )
            self._connection.commit()

            cur.execute("PRAGMA foreign_keys = OFF")
            self._connection.execute("BEGIN IMMEDIATE")
            columns = [item[1] for item in cur.execute("PRAGMA table_info(tasks)").fetchall()]
            has_field_id = "field_id" in columns
            cur.execute("DROP TABLE IF EXISTS tasks_new")
            if has_field_id:
                cur.execute(
                    """
                    CREATE TABLE tasks_new (
                      request_id TEXT PRIMARY KEY,
                      field_id TEXT,
                      image_path TEXT,
                      start_time DATETIME,
                      end_time DATETIME,
                      status TEXT CHECK(status IN ('queued', 'running', 'completed', 'blocked', 'error'))
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO tasks_new (request_id, field_id, image_path, start_time, end_time, status)
                    SELECT request_id, field_id, image_path, start_time, end_time,
                           CASE WHEN status IN ('queued','running','completed','blocked','error') OR status IS NULL
                                THEN status ELSE 'error' END
                    FROM tasks
                    """
                )
            else:
                cur.execute(
                    """
                    CREATE TABLE tasks_new (
                      request_id TEXT PRIMARY KEY,
                      image_path TEXT,
                      start_time DATETIME,
                      end_time DATETIME,
                      status TEXT CHECK(status IN ('queued', 'running', 'completed', 'blocked', 'error'))
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO tasks_new (request_id, image_path, start_time, end_time, status)
                    SELECT request_id, image_path, start_time, end_time,
                           CASE WHEN status IN ('queued','running','completed','blocked','error') OR status IS NULL
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
        self._migrate_v1_1()
        with self._lock:
            self._connection.executescript(_SCHEMA_SQL)
            self._connection.commit()
        self._ensure_table_column("tasks", "field_id", "TEXT")
        self._ensure_table_column("fields", "owner_user_id", "TEXT")
        self._ensure_table_column("crop_catalog", "water_demand_coefficient", "REAL")

    _ALLOWED_TABLES = frozenset(
        {
            "tasks",
            "fields",
            "detections",
            "weather_snapshots",
            "crop_catalog",
            "soil_records",
            "reference_data",
            "weather_history",
        }
    )

    def _ensure_table_column(
        self,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        if table_name not in self._ALLOWED_TABLES:
            raise ValueError(f"Unknown table: {table_name!r}")
        if not column_name.isidentifier():
            raise ValueError(f"Invalid column name: {column_name!r}")
        with self._lock:
            rows = self._connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            existing_columns = {str(row["name"]) for row in rows}
            if column_name in existing_columns:
                return
            self._connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )
            self._connection.commit()

    def _ensure_task(self, request_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO tasks (request_id) VALUES (?)",
                (request_id,),
            )
            self._connection.commit()

    def _parse_json_value(self, value: Any, *, default: Any) -> Any:
        if value in (None, ""):
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except (TypeError, json.JSONDecodeError):
            return default

    def _to_float(self, value: Any) -> float | None:
        return safe_float(value)

    def _to_int(self, value: Any) -> int | None:
        if value in (None, "", "NA", "N/A", "null", "NULL"):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _distance_sq(
        self,
        lat_a: float,
        lon_a: float,
        lat_b: float,
        lon_b: float,
    ) -> float:
        lat_scale = METERS_PER_DEGREE_LAT
        lon_scale = METERS_PER_DEGREE_LAT * max(math.cos(math.radians((lat_a + lat_b) / 2)), 0.1)
        dy = (lat_a - lat_b) * lat_scale
        dx = (lon_a - lon_b) * lon_scale
        return dx * dx + dy * dy

    def _derive_square_geofence(
        self,
        latitude: float,
        longitude: float,
        area_mu: float,
    ) -> list[list[float]]:
        area_square_m = max(area_mu, 1.0) * 666.6667
        half_side_m = math.sqrt(area_square_m) / 2
        lat_delta = half_side_m / METERS_PER_DEGREE_LAT
        lon_delta = half_side_m / (METERS_PER_DEGREE_LAT * max(math.cos(math.radians(latitude)), 0.1))
        return [
            [round(longitude - lon_delta, 6), round(latitude - lat_delta, 6)],
            [round(longitude + lon_delta, 6), round(latitude - lat_delta, 6)],
            [round(longitude + lon_delta, 6), round(latitude + lat_delta, 6)],
            [round(longitude - lon_delta, 6), round(latitude + lat_delta, 6)],
        ]

    def _infer_stage(self, status: str, *, end_time: Any) -> str:
        if status == "queued":
            return "queue"
        if status == "running":
            return "pipeline"
        if status == "completed":
            return "pipeline"
        if status == "error":
            return "pipeline" if end_time else "running"
        return "pipeline"

    def _status_message(self, status: str) -> str:
        if status == "queued":
            return "图片已进入处理队列"
        if status == "running":
            return "任务处理中"
        if status == "completed":
            return "任务已完成"
        if status == "error":
            return "任务执行失败"
        return "任务状态未知"

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(query, params).fetchone()
        return dict(row) if row is not None else None

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]
