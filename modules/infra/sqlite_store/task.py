from __future__ import annotations

import json
from typing import Any

from modules.infra.sqlite_store._private import utc_now_iso


class TaskMixin:
    def mark_task_queued(
        self,
        request_id: str,
        image_path: str,
        field_id: str | None = None,
    ) -> None:
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

    def mark_task_started(
        self,
        request_id: str,
        image_path: str,
        field_id: str | None = None,
    ) -> None:
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

    def _build_task_filter_clause(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[str, list[Any]]:
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
        return where_clause, params

    def count_task_views(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        where_clause, params = self._build_task_filter_clause(status=status, search=search)
        row = self.fetch_one(
            f"""
            SELECT COUNT(*) AS total
            FROM tasks
            {where_clause}
            """,
            tuple(params),
        )
        return int(row["total"]) if row and row.get("total") is not None else 0

    def fetch_task_views(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._build_task_filter_clause(status=status, search=search)
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
            for field_id in field_ids:
                field_context = self.fetch_field_context(field_id)
                if field_context:
                    location = field_context.get("location") or {}
                    field_by_id[field_id] = {
                        "field_id": field_id,
                        "field_name": field_context.get("name"),
                        "name": field_context.get("name"),
                        "province": location.get("province"),
                        "city": location.get("city"),
                        "county": location.get("county"),
                        "latitude": location.get("latitude"),
                        "longitude": location.get("longitude"),
                        "area_mu": self._to_float(field_context.get("area_mu")),
                        "soil_type": field_context.get("soil_type"),
                        "geofence": field_context.get("geofence") or [],
                        "crop_cycle": field_context.get("crop_cycle") or {},
                    }
                    continue

                row = self.fetch_one(
                    """
                    SELECT field_id, field_code, field_name, province, city, county,
                           latitude, longitude, area_mu, area_hectare, geofence
                    FROM fields
                    WHERE field_id = ?
                    """,
                    (field_id,),
                )
                if row is None:
                    continue
                field_by_id[field_id] = {
                    "field_id": field_id,
                    "field_code": row.get("field_code"),
                    "field_name": row.get("field_name"),
                    "name": row.get("field_name"),
                    "province": row.get("province"),
                    "city": row.get("city"),
                    "county": row.get("county"),
                    "latitude": self._to_float(row.get("latitude")),
                    "longitude": self._to_float(row.get("longitude")),
                    "area_mu": self._to_float(row.get("area_mu")),
                    "area_hectare": self._to_float(row.get("area_hectare")),
                    "geofence": self._parse_json_value(row.get("geofence"), default=[]),
                    "crop_cycle": {},
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

    def clear_runtime_task_data(self) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM spray_records WHERE request_id IS NOT NULL")
            self._connection.execute("DELETE FROM drone_mission_updates")
            self._connection.execute("DELETE FROM decisions")
            self._connection.execute("DELETE FROM weather_snapshots")
            self._connection.execute("DELETE FROM detections")
            self._connection.execute("DELETE FROM tasks")
            self._connection.commit()
