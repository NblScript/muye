from __future__ import annotations

import json
import logging
import math
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
                  field_id TEXT,
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
            )
            self._connection.commit()
        self._ensure_table_column("tasks", "field_id", "TEXT")
        self._ensure_table_column("fields", "owner_user_id", "TEXT")
        self._ensure_table_column("crop_catalog", "water_demand_coefficient", "REAL")

    def _ensure_table_column(self, table_name: str, column_name: str, column_definition: str) -> None:
        with self._lock:
            rows = self._connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            existing_columns = {str(row["name"]) for row in rows}
            if column_name in existing_columns:
                return
            self._connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )
            self._connection.commit()

    def mark_task_queued(self, request_id: str, image_path: str, field_id: str | None = None) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                """
                UPDATE tasks
                SET image_path = ?,
                    field_id = COALESCE(?, field_id),
                    status = COALESCE(status, ?)
                WHERE request_id = ?
                """,
                (image_path, field_id, "queued", request_id),
            )
            self._connection.commit()

    def mark_task_started(self, request_id: str, image_path: str, field_id: str | None = None) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                """
                UPDATE tasks
                SET image_path = ?,
                    field_id = COALESCE(?, field_id),
                    start_time = COALESCE(start_time, ?),
                    status = ?
                WHERE request_id = ?
                """,
                (image_path, field_id, utc_now_iso(), "running", request_id),
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

    def add_drone_mission_update(
        self,
        request_id: str,
        *,
        task_id: str | None,
        status: str,
        message: str,
        progress: int | None = None,
        current_waypoint_index: int | None = None,
        instruction: dict[str, Any] | None = None,
        medication: dict[str, Any] | None = None,
    ) -> None:
        self._ensure_task(request_id)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO drone_mission_updates (
                  request_id, timestamp, task_id, status, message, progress,
                  current_waypoint_index, instruction, medication
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    utc_now_iso(),
                    task_id,
                    status,
                    message,
                    progress,
                    current_waypoint_index,
                    json.dumps(instruction or {}, ensure_ascii=False),
                    json.dumps(medication or {}, ensure_ascii=False),
                ),
            )
            self._connection.commit()

    def upsert_data_source(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO data_sources (
                  source_id, source_name, publisher, region_scope, source_type,
                  source_url, access_level, retrieval_date, license, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                  source_name = excluded.source_name,
                  publisher = excluded.publisher,
                  region_scope = excluded.region_scope,
                  source_type = excluded.source_type,
                  source_url = excluded.source_url,
                  access_level = excluded.access_level,
                  retrieval_date = excluded.retrieval_date,
                  license = excluded.license,
                  notes = excluded.notes
                """,
                (
                    record["source_id"],
                    record["source_name"],
                    record.get("publisher"),
                    record.get("region_scope"),
                    record.get("source_type"),
                    record["source_url"],
                    record.get("access_level"),
                    record.get("retrieval_date"),
                    record.get("license"),
                    record.get("notes"),
                ),
            )
            self._connection.commit()

    def upsert_agri_statistical_indicator(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO agri_statistical_indicators (
                  region_level, region_name, province, city, county, year, period,
                  indicator_code, indicator_name, value, unit, source_id,
                  source_excerpt, raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                  region_level, region_name, province, city, county, year, period, indicator_code
                ) DO UPDATE SET
                  indicator_name = excluded.indicator_name,
                  value = excluded.value,
                  unit = excluded.unit,
                  source_id = excluded.source_id,
                  source_excerpt = excluded.source_excerpt,
                  raw_payload = excluded.raw_payload
                """,
                (
                    record["region_level"],
                    record["region_name"],
                    record.get("province"),
                    record.get("city"),
                    record.get("county"),
                    int(record["year"]),
                    record["period"],
                    record["indicator_code"],
                    record["indicator_name"],
                    float(record["value"]),
                    record.get("unit"),
                    record.get("source_id"),
                    record.get("source_excerpt"),
                    json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
                ),
            )
            self._connection.commit()

    def upsert_pesticide_catalog_record(self, record: dict[str, Any]) -> None:
        target_crops = record.get("target_crops")
        if isinstance(target_crops, (list, dict)):
            target_crops = json.dumps(target_crops, ensure_ascii=False)

        target_pests = record.get("target_pests")
        if isinstance(target_pests, (list, dict)):
            target_pests = json.dumps(target_pests, ensure_ascii=False)

        raw_payload = record.get("raw_payload", {})
        if isinstance(raw_payload, str):
            raw_payload_text = raw_payload
        else:
            raw_payload_text = json.dumps(raw_payload, ensure_ascii=False)

        with self._lock:
            self._connection.execute(
                """
                INSERT INTO pesticide_catalog (
                  pesticide_id, registration_no, product_name, active_ingredient,
                  formulation, toxicity, manufacturer, target_crops, target_pests,
                  dilution_guidance, source, raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pesticide_id) DO UPDATE SET
                  registration_no = excluded.registration_no,
                  product_name = excluded.product_name,
                  active_ingredient = excluded.active_ingredient,
                  formulation = excluded.formulation,
                  toxicity = excluded.toxicity,
                  manufacturer = excluded.manufacturer,
                  target_crops = excluded.target_crops,
                  target_pests = excluded.target_pests,
                  dilution_guidance = excluded.dilution_guidance,
                  source = excluded.source,
                  raw_payload = excluded.raw_payload
                """,
                (
                    str(record["pesticide_id"]),
                    record.get("registration_no"),
                    record["product_name"],
                    record.get("active_ingredient"),
                    record.get("formulation"),
                    record.get("toxicity"),
                    record.get("manufacturer"),
                    target_crops,
                    target_pests,
                    record.get("dilution_guidance"),
                    record.get("source"),
                    raw_payload_text,
                ),
            )
            self._connection.commit()

    def upsert_soil_record(self, record: dict[str, Any]) -> None:
        existing = self.fetch_one(
            """
            SELECT id
            FROM soil_records
            WHERE field_id = ? AND sample_date = ? AND depth_cm = ?
            """,
            (
                str(record["field_id"]),
                record.get("sample_date"),
                self._to_int(record.get("depth_cm")),
            ),
        )
        params = (
            str(record["field_id"]),
            record.get("sample_date"),
            self._to_int(record.get("depth_cm")),
            self._to_float(record.get("ph")),
            self._to_float(record.get("organic_matter_gkg")),
            self._to_float(record.get("alkali_hydrolyzable_nitrogen_mgkg")),
            self._to_float(record.get("available_phosphorus_mgkg")),
            self._to_float(record.get("available_potassium_mgkg")),
            self._to_float(record.get("moisture_percent")),
            self._to_float(record.get("salinity_gkg")),
            record.get("texture"),
            record.get("source"),
            json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
        )
        with self._lock:
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO soil_records (
                      field_id, sample_date, depth_cm, ph, organic_matter_gkg,
                      alkali_hydrolyzable_nitrogen_mgkg, available_phosphorus_mgkg,
                      available_potassium_mgkg, moisture_percent, salinity_gkg,
                      texture, source, raw_payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
            else:
                self._connection.execute(
                    """
                    UPDATE soil_records
                    SET ph = ?, organic_matter_gkg = ?, alkali_hydrolyzable_nitrogen_mgkg = ?,
                        available_phosphorus_mgkg = ?, available_potassium_mgkg = ?,
                        moisture_percent = ?, salinity_gkg = ?, texture = ?,
                        source = ?, raw_payload = ?
                    WHERE id = ?
                    """,
                    (
                        self._to_float(record.get("ph")),
                        self._to_float(record.get("organic_matter_gkg")),
                        self._to_float(record.get("alkali_hydrolyzable_nitrogen_mgkg")),
                        self._to_float(record.get("available_phosphorus_mgkg")),
                        self._to_float(record.get("available_potassium_mgkg")),
                        self._to_float(record.get("moisture_percent")),
                        self._to_float(record.get("salinity_gkg")),
                        record.get("texture"),
                        record.get("source"),
                        json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
                        int(existing["id"]),
                    ),
                )
            self._connection.commit()

    def upsert_weather_station(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO weather_stations (
                  station_code, station_name, province, city, county,
                  latitude, longitude, elevation_m, source_id, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(station_code) DO UPDATE SET
                  station_name = excluded.station_name,
                  province = excluded.province,
                  city = excluded.city,
                  county = excluded.county,
                  latitude = excluded.latitude,
                  longitude = excluded.longitude,
                  elevation_m = excluded.elevation_m,
                  source_id = excluded.source_id,
                  notes = excluded.notes
                """,
                (
                    record["station_code"],
                    record["station_name"],
                    record.get("province"),
                    record.get("city"),
                    record.get("county"),
                    record.get("latitude"),
                    record.get("longitude"),
                    record.get("elevation_m"),
                    record.get("source_id"),
                    record.get("notes"),
                ),
            )
            self._connection.commit()

    def upsert_weather_history_daily(self, record: dict[str, Any]) -> None:
        field_id = record.get("field_id")
        if field_id is None:
            existing = self.fetch_one(
                """
                SELECT id
                FROM weather_history_daily
                WHERE field_id IS NULL
                  AND station_code = ?
                  AND observation_date = ?
                """,
                (
                    record.get("station_code"),
                    record["observation_date"],
                ),
            )
        else:
            existing = self.fetch_one(
                """
                SELECT id
                FROM weather_history_daily
                WHERE field_id = ?
                  AND station_code = ?
                  AND observation_date = ?
                """,
                (
                    str(field_id),
                    record.get("station_code"),
                    record["observation_date"],
                ),
            )
        params = (
            str(field_id) if field_id is not None else None,
            record.get("station_code"),
            record.get("station_name"),
            record["observation_date"],
            record.get("weather_summary"),
            record.get("temperature_avg_c"),
            record.get("temperature_min_c"),
            record.get("temperature_max_c"),
            record.get("humidity_avg_percent"),
            record.get("precipitation_mm"),
            record.get("wind_speed_avg_mps"),
            record.get("wind_direction"),
            record.get("sunshine_hours"),
            record.get("source"),
            json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
        )
        with self._lock:
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO weather_history_daily (
                      field_id, station_code, station_name, observation_date, weather_summary,
                      temperature_avg_c, temperature_min_c, temperature_max_c,
                      humidity_avg_percent, precipitation_mm, wind_speed_avg_mps,
                      wind_direction, sunshine_hours, source, raw_payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
            else:
                self._connection.execute(
                    """
                    UPDATE weather_history_daily
                    SET field_id = ?, station_name = ?, weather_summary = ?, temperature_avg_c = ?,
                        temperature_min_c = ?, temperature_max_c = ?, humidity_avg_percent = ?,
                        precipitation_mm = ?, wind_speed_avg_mps = ?, wind_direction = ?,
                        sunshine_hours = ?, source = ?, raw_payload = ?
                    WHERE id = ?
                    """,
                    (
                        record.get("field_id"),
                        record.get("station_name"),
                        record.get("weather_summary"),
                        record.get("temperature_avg_c"),
                        record.get("temperature_min_c"),
                        record.get("temperature_max_c"),
                        record.get("humidity_avg_percent"),
                        record.get("precipitation_mm"),
                        record.get("wind_speed_avg_mps"),
                        record.get("wind_direction"),
                        record.get("sunshine_hours"),
                        record.get("source"),
                        json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
                        int(existing["id"]),
                    ),
                )
            self._connection.commit()

    def upsert_field(self, record: dict[str, Any]) -> None:
        geofence = record.get("geofence")
        if isinstance(geofence, (list, dict)):
            geofence = json.dumps(geofence, ensure_ascii=False)

        area_mu = self._to_float(record.get("area_mu"))
        area_hectare = self._to_float(record.get("area_hectare"))
        if area_hectare is None and area_mu is not None:
            area_hectare = round(area_mu * 0.0666667, 4)

        with self._lock:
            self._connection.execute(
                """
                INSERT INTO fields (
                  field_id, field_code, field_name, owner_user_id, province, city, county,
                  township, village, latitude, longitude, area_mu, area_hectare,
                  geofence, soil_type, irrigation_type, source, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(field_id) DO UPDATE SET
                  field_code = excluded.field_code,
                  field_name = excluded.field_name,
                  owner_user_id = excluded.owner_user_id,
                  province = excluded.province,
                  city = excluded.city,
                  county = excluded.county,
                  township = excluded.township,
                  village = excluded.village,
                  latitude = excluded.latitude,
                  longitude = excluded.longitude,
                  area_mu = excluded.area_mu,
                  area_hectare = excluded.area_hectare,
                  geofence = excluded.geofence,
                  soil_type = excluded.soil_type,
                  irrigation_type = excluded.irrigation_type,
                  source = excluded.source,
                  notes = excluded.notes,
                  updated_at = excluded.updated_at
                """,
                (
                    str(record["field_id"]),
                    record.get("field_code"),
                    record["field_name"],
                    record.get("owner_user_id"),
                    record.get("province"),
                    record.get("city"),
                    record.get("county"),
                    record.get("township"),
                    record.get("village"),
                    self._to_float(record.get("latitude")),
                    self._to_float(record.get("longitude")),
                    area_mu,
                    area_hectare,
                    geofence,
                    record.get("soil_type"),
                    record.get("irrigation_type"),
                    record.get("source"),
                    record.get("notes"),
                    record.get("created_at"),
                    record.get("updated_at"),
                ),
            )
            self._connection.commit()

    def upsert_crop_catalog_record(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO crop_catalog (
                  crop_code, crop_name, category, variety, growth_cycle_days,
                  water_demand_coefficient, typical_planting_month, typical_harvest_month,
                  source, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(crop_code) DO UPDATE SET
                  crop_name = excluded.crop_name,
                  category = excluded.category,
                  variety = excluded.variety,
                  growth_cycle_days = excluded.growth_cycle_days,
                  water_demand_coefficient = excluded.water_demand_coefficient,
                  typical_planting_month = excluded.typical_planting_month,
                  typical_harvest_month = excluded.typical_harvest_month,
                  source = excluded.source,
                  notes = excluded.notes
                """,
                (
                    str(record["crop_code"]),
                    record["crop_name"],
                    record.get("category"),
                    record.get("variety"),
                    self._to_int(record.get("growth_cycle_days")),
                    self._to_float(record.get("water_demand_coefficient")),
                    record.get("typical_planting_month"),
                    record.get("typical_harvest_month"),
                    record.get("source"),
                    record.get("notes"),
                ),
            )
            self._connection.commit()

    def upsert_field_crop_cycle(self, record: dict[str, Any]) -> None:
        existing = self.fetch_one(
            """
            SELECT id
            FROM field_crop_cycles
            WHERE field_id = ? AND crop_code = ? AND planting_date = ?
            """,
            (
                str(record["field_id"]),
                str(record["crop_code"]),
                record.get("planting_date"),
            ),
        )
        params = (
            str(record["field_id"]),
            str(record["crop_code"]),
            self._to_int(record.get("year")),
            record.get("season"),
            record.get("planting_date"),
            record.get("harvest_date"),
            self._to_float(record.get("area_mu")),
            self._to_float(record.get("expected_yield_kg")),
            self._to_float(record.get("actual_yield_kg")),
            record.get("status"),
            record.get("source"),
            record.get("notes"),
        )
        with self._lock:
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO field_crop_cycles (
                      field_id, crop_code, year, season, planting_date, harvest_date,
                      area_mu, expected_yield_kg, actual_yield_kg, status, source, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
            else:
                self._connection.execute(
                    """
                    UPDATE field_crop_cycles
                    SET year = ?, season = ?, harvest_date = ?, area_mu = ?,
                        expected_yield_kg = ?, actual_yield_kg = ?, status = ?,
                        source = ?, notes = ?
                    WHERE id = ?
                    """,
                    (
                        self._to_int(record.get("year")),
                        record.get("season"),
                        record.get("harvest_date"),
                        self._to_float(record.get("area_mu")),
                        self._to_float(record.get("expected_yield_kg")),
                        self._to_float(record.get("actual_yield_kg")),
                        record.get("status"),
                        record.get("source"),
                        record.get("notes"),
                        int(existing["id"]),
                    ),
                )
            self._connection.commit()

    def upsert_spray_record(self, record: dict[str, Any]) -> None:
        request_id = record.get("request_id")
        drone_task_id = record.get("drone_task_id")
        if request_id:
            self._ensure_task(str(request_id))

        if request_id:
            existing = self.fetch_one(
                """
                SELECT id
                FROM spray_records
                WHERE request_id = ?
                """,
                (str(request_id),),
            )
        elif drone_task_id:
            existing = self.fetch_one(
                """
                SELECT id
                FROM spray_records
                WHERE drone_task_id = ?
                """,
                (str(drone_task_id),),
            )
        else:
            existing = self.fetch_one(
                """
                SELECT id
                FROM spray_records
                WHERE field_id = ? AND spray_date = ?
                """,
                (
                    str(record["field_id"]),
                    record["spray_date"],
                ),
            )

        weather_snapshot = record.get("weather_snapshot")
        if isinstance(weather_snapshot, (dict, list)):
            weather_snapshot = json.dumps(weather_snapshot, ensure_ascii=False)

        params = (
            str(request_id) if request_id else None,
            str(record["field_id"]),
            self._to_int(record.get("crop_cycle_id")),
            str(drone_task_id) if drone_task_id else None,
            record.get("pesticide_id"),
            record["spray_date"],
            record.get("operator_name"),
            self._to_float(record.get("spray_area_mu")),
            self._to_float(record.get("dosage_per_mu")),
            self._to_float(record.get("total_dosage")),
            record.get("dilution_ratio"),
            self._to_float(record.get("spray_rate_lpm")),
            self._to_float(record.get("flight_height_m")),
            self._to_float(record.get("flight_speed_mps")),
            weather_snapshot,
            record.get("result_status"),
            record.get("source"),
            record.get("notes"),
        )
        with self._lock:
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO spray_records (
                      request_id, field_id, crop_cycle_id, drone_task_id, pesticide_id,
                      spray_date, operator_name, spray_area_mu, dosage_per_mu,
                      total_dosage, dilution_ratio, spray_rate_lpm, flight_height_m,
                      flight_speed_mps, weather_snapshot, result_status, source, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
            else:
                self._connection.execute(
                    """
                    UPDATE spray_records
                    SET request_id = ?, field_id = ?, crop_cycle_id = ?, drone_task_id = ?,
                        pesticide_id = ?, spray_date = ?, operator_name = ?, spray_area_mu = ?,
                        dosage_per_mu = ?, total_dosage = ?, dilution_ratio = ?,
                        spray_rate_lpm = ?, flight_height_m = ?, flight_speed_mps = ?,
                        weather_snapshot = ?, result_status = ?, source = ?, notes = ?
                    WHERE id = ?
                    """,
                    (*params, int(existing["id"])),
                )
            self._connection.commit()

    def fetch_field_context(self, field_id: str | None = None) -> dict[str, Any] | None:
        if field_id:
            field_row = self.fetch_one(
                """
                SELECT *
                FROM fields
                WHERE field_id = ?
                """,
                (field_id,),
            )
        else:
            field_count_row = self.fetch_one("SELECT COUNT(*) AS total FROM fields")
            field_count = int(field_count_row["total"]) if field_count_row else 0
            if field_count == 0:
                return None
            if field_count > 1:
                raise RuntimeError("检测到多个地块，请显式设置 MUYE_ACTIVE_FIELD_ID")
            field_row = self.fetch_one(
                """
                SELECT *
                FROM fields
                ORDER BY city ASC, field_name ASC
                LIMIT 1
                """
            )

        if field_row is None:
            return None

        latitude = self._to_float(field_row.get("latitude"))
        longitude = self._to_float(field_row.get("longitude"))
        area_mu = self._to_float(field_row.get("area_mu"))
        geofence = self._parse_json_value(field_row.get("geofence"), default=[])
        if not geofence and latitude is not None and longitude is not None:
            geofence = self._derive_square_geofence(latitude, longitude, area_mu or 30.0)

        crop_cycle = self.fetch_one(
            """
            SELECT
              field_crop_cycles.id,
              field_crop_cycles.field_id,
              field_crop_cycles.crop_code,
              field_crop_cycles.year,
              field_crop_cycles.season,
              field_crop_cycles.planting_date,
              field_crop_cycles.harvest_date,
              field_crop_cycles.area_mu,
              field_crop_cycles.status,
              crop_catalog.crop_name,
              crop_catalog.category,
              crop_catalog.growth_cycle_days,
              crop_catalog.water_demand_coefficient
            FROM field_crop_cycles
            LEFT JOIN crop_catalog
              ON crop_catalog.crop_code = field_crop_cycles.crop_code
            WHERE field_crop_cycles.field_id = ?
            ORDER BY
              CASE field_crop_cycles.status
                WHEN 'growing' THEN 0
                WHEN 'planted' THEN 1
                WHEN 'planned' THEN 2
                ELSE 3
              END,
              COALESCE(field_crop_cycles.harvest_date, field_crop_cycles.planting_date) DESC
            LIMIT 1
            """,
            (str(field_row["field_id"]),),
        )

        weather_location = (
            (
                f"{longitude},{latitude}"
                if longitude is not None and latitude is not None
                else None
            )
            or field_row.get("city")
            or field_row.get("county")
        )

        return {
            "field_id": str(field_row["field_id"]),
            "name": field_row.get("field_name"),
            "weather_location": weather_location,
            "area_mu": area_mu,
            "soil_type": field_row.get("soil_type"),
            "geofence": geofence,
            "location": {
                "province": field_row.get("province"),
                "city": field_row.get("city"),
                "county": field_row.get("county"),
                "latitude": latitude,
                "longitude": longitude,
            },
            "crop_cycle": crop_cycle,
        }

    def find_nearest_field_id(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        city: str | None = None,
        county: str | None = None,
    ) -> str | None:
        if latitude is None or longitude is None:
            return None

        filters = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
        params: list[Any] = []
        if county:
            filters.append("county = ?")
            params.append(county)
        elif city:
            filters.append("city = ?")
            params.append(city)

        rows = self.fetch_all(
            f"""
            SELECT field_id, latitude, longitude
            FROM fields
            WHERE {' AND '.join(filters)}
            """,
            tuple(params),
        )
        if not rows and city and county:
            rows = self.fetch_all(
                """
                SELECT field_id, latitude, longitude
                FROM fields
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND city = ?
                """,
                (city,),
            )
        if not rows:
            rows = self.fetch_all(
                """
                SELECT field_id, latitude, longitude
                FROM fields
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                """
            )
        if not rows:
            return None

        nearest = min(
            rows,
            key=lambda row: self._distance_sq(
                latitude,
                longitude,
                self._to_float(row.get("latitude")) or latitude,
                self._to_float(row.get("longitude")) or longitude,
            ),
        )
        return str(nearest["field_id"])

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(query, params).fetchone()
        return dict(row) if row is not None else None

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def fetch_task_views(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []

        if status:
            filters.append("status = ?")
            params.append(status)

        if search:
            keyword = f"%{search.strip()}%"
            filters.append(
                """
                (
                  request_id LIKE ?
                  OR field_id LIKE ?
                  OR image_path LIKE ?
                  OR EXISTS (
                    SELECT 1
                    FROM detections
                    WHERE detections.request_id = tasks.request_id
                      AND detections.label LIKE ?
                  )
                )
                """
            )
            params.extend([keyword, keyword, keyword, keyword])

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        query = f"""
            SELECT request_id, field_id, image_path, start_time, end_time, status
            FROM tasks
            {where_clause}
            ORDER BY COALESCE(end_time, start_time) DESC, request_id DESC
            LIMIT ?
        """
        params.append(max(1, limit))
        task_rows = self.fetch_all(query, tuple(params))
        if not task_rows:
            return []

        request_ids = [str(item["request_id"]) for item in task_rows]
        placeholders = ",".join("?" for _ in request_ids)

        detection_rows = self.fetch_all(
            f"""
            SELECT request_id, label, confidence, bbox
            FROM detections
            WHERE request_id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(request_ids),
        )
        weather_rows = self.fetch_all(
            f"""
            SELECT request_id, timestamp, weather_data
            FROM weather_snapshots
            WHERE request_id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(request_ids),
        )
        decision_rows = self.fetch_all(
            f"""
            SELECT request_id, timestamp, decision_text
            FROM decisions
            WHERE request_id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(request_ids),
        )
        spray_rows = self.fetch_all(
            f"""
            SELECT request_id, field_id, spray_date, spray_area_mu, dosage_per_mu,
                   total_dosage, dilution_ratio, spray_rate_lpm, flight_height_m,
                   flight_speed_mps, result_status
            FROM spray_records
            WHERE request_id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(request_ids),
        )
        drone_rows = self.fetch_all(
            f"""
            SELECT request_id, task_id, status, message, progress,
                   current_waypoint_index, instruction, medication
            FROM drone_mission_updates
            WHERE request_id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(request_ids),
        )

        field_ids = sorted(
            {
                str(item["field_id"])
                for item in task_rows
                if item.get("field_id") not in (None, "")
            }
        )
        field_by_id: dict[str, dict[str, Any]] = {}
        if field_ids:
            field_placeholders = ",".join("?" for _ in field_ids)
            field_rows = self.fetch_all(
                f"""
                SELECT field_id, field_code, field_name, province, city, county,
                       latitude, longitude, area_mu, area_hectare, geofence
                FROM fields
                WHERE field_id IN ({field_placeholders})
                """,
                tuple(field_ids),
            )
            for row in field_rows:
                field_id = str(row["field_id"])
                field_by_id[field_id] = {
                    "field_id": field_id,
                    "field_code": row.get("field_code"),
                    "field_name": row.get("field_name"),
                    "province": row.get("province"),
                    "city": row.get("city"),
                    "county": row.get("county"),
                    "latitude": self._to_float(row.get("latitude")),
                    "longitude": self._to_float(row.get("longitude")),
                    "area_mu": self._to_float(row.get("area_mu")),
                    "area_hectare": self._to_float(row.get("area_hectare")),
                    "geofence": self._parse_json_value(row.get("geofence"), default=[]),
                }

        detections_by_request: dict[str, list[dict[str, Any]]] = {}
        for row in detection_rows:
            request_id = str(row["request_id"])
            detections_by_request.setdefault(request_id, []).append(
                {
                    "pest_type": row["label"],
                    "confidence": row["confidence"],
                    "position": self._parse_json_value(row["bbox"], default={}),
                }
            )

        weather_by_request: dict[str, dict[str, Any]] = {}
        for row in weather_rows:
            weather_by_request[str(row["request_id"])] = self._parse_json_value(
                row["weather_data"],
                default={},
            )

        decisions_by_request: dict[str, dict[str, Any]] = {}
        for row in decision_rows:
            decisions_by_request[str(row["request_id"])] = self._parse_json_value(
                row["decision_text"],
                default={},
            )

        spray_by_request: dict[str, dict[str, Any]] = {}
        for row in spray_rows:
            spray_by_request[str(row["request_id"])] = {
                "field_id": row.get("field_id"),
                "spray_date": row.get("spray_date"),
                "spray_area_mu": self._to_float(row.get("spray_area_mu")),
                "dosage_per_mu": self._to_float(row.get("dosage_per_mu")),
                "total_dosage": self._to_float(row.get("total_dosage")),
                "dilution_ratio": row.get("dilution_ratio"),
                "spray_rate_lpm": self._to_float(row.get("spray_rate_lpm")),
                "flight_height_m": self._to_float(row.get("flight_height_m")),
                "flight_speed_mps": self._to_float(row.get("flight_speed_mps")),
                "result_status": row.get("result_status"),
            }

        drone_by_request: dict[str, dict[str, Any]] = {}
        for row in drone_rows:
            drone_by_request[str(row["request_id"])] = {
                "task_id": row.get("task_id"),
                "status": row.get("status"),
                "message": row.get("message"),
                "progress": row.get("progress"),
                "current_waypoint_index": row.get("current_waypoint_index"),
                "instruction": self._parse_json_value(row.get("instruction"), default={}),
                "medication": self._parse_json_value(row.get("medication"), default={}),
            }

        task_views: list[dict[str, Any]] = []
        for row in task_rows:
            request_id = str(row["request_id"])
            start_time = row.get("start_time")
            end_time = row.get("end_time")
            status_value = str(row.get("status") or "queued")
            field_id = row.get("field_id")
            task_views.append(
                {
                    "request_id": request_id,
                    "field_id": field_id,
                    "created_at": start_time,
                    "updated_at": end_time or start_time,
                    "current_stage": self._infer_stage(status_value, end_time=end_time),
                    "status": status_value,
                    "message": self._status_message(status_value),
                    "image_path": row.get("image_path"),
                    "field": field_by_id.get(str(field_id), {}) if field_id else {},
                    "spray_summary": spray_by_request.get(request_id, {}),
                    "detections": detections_by_request.get(request_id, []),
                    "weather": weather_by_request.get(request_id, {}),
                    "decision": decisions_by_request.get(request_id, {}),
                    "drone": drone_by_request.get(request_id, {}),
                    "events": [],
                    "error": "任务执行失败" if status_value == "error" else None,
                }
            )
        return task_views

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

    def _to_float(self, value: Any) -> float | None:
        if value in (None, "", "NA", "N/A", "null", "NULL"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

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
        lat_scale = 111_000
        lon_scale = 111_000 * max(math.cos(math.radians((lat_a + lat_b) / 2)), 0.1)
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
        lat_delta = half_side_m / 111_000
        lon_delta = half_side_m / (111_000 * max(math.cos(math.radians(latitude)), 0.1))
        return [
            [round(longitude - lon_delta, 6), round(latitude - lat_delta, 6)],
            [round(longitude + lon_delta, 6), round(latitude - lat_delta, 6)],
            [round(longitude + lon_delta, 6), round(latitude + lat_delta, 6)],
            [round(longitude - lon_delta, 6), round(latitude + lat_delta, 6)],
        ]
