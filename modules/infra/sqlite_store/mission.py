"""Mission mixin for missions and mission_iterations tables."""

from __future__ import annotations

import json
from typing import Any

from modules.infra.sqlite_store._private import utc_now_iso


class MissionMixin:
    """CRUD for mission lifecycle records."""

    # ── Mission CRUD ──

    def create_mission(
        self,
        *,
        mission_id: str,
        original_request_id: str,
        field_id: str | None = None,
        kill_rate_threshold: float = 0.9,
        max_iterations: int = 3,
        pest_types: list[str] | None = None,
        pesticide_name: str | None = None,
        crop_name: str | None = None,
    ) -> int:
        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT INTO missions
                  (mission_id, original_request_id, field_id, status,
                   kill_rate_threshold, max_iterations, current_iteration,
                   pest_types, pesticide_name, crop_name, created_at)
                VALUES (?, ?, ?, 'active', ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    mission_id,
                    original_request_id,
                    field_id,
                    kill_rate_threshold,
                    max_iterations,
                    json.dumps(pest_types or [], ensure_ascii=False),
                    pesticide_name,
                    crop_name,
                    utc_now_iso(),
                ),
            )
            self._connection.commit()
            return cursor.lastrowid

    def update_mission(self, mission_row_id: int, **kwargs: Any) -> None:
        if not kwargs:
            return
        sets: list[str] = []
        values: list[Any] = []
        for key in (
            "status",
            "current_iteration",
            "final_kill_rate",
            "total_pre_pest_count",
            "total_post_pest_count",
            "completed_at",
            "notes",
        ):
            if key in kwargs:
                sets.append(f"{key} = ?")
                values.append(kwargs[key])
        if not sets:
            return
        values.append(mission_row_id)
        with self._lock:
            self._connection.execute(
                f"UPDATE missions SET {', '.join(sets)} WHERE id = ?",
                values,
            )
            self._connection.commit()

    def fetch_mission_by_request_id(self, original_request_id: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            "SELECT * FROM missions WHERE original_request_id = ? ORDER BY id DESC LIMIT 1",
            (original_request_id,),
        )
        if row is None:
            return None
        result = dict(row)
        result["pest_types"] = self._parse_json_value(result.get("pest_types"), default=[])
        return result

    def fetch_mission_by_mission_id(self, mission_id: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            "SELECT * FROM missions WHERE mission_id = ? ORDER BY id DESC LIMIT 1",
            (mission_id,),
        )
        if row is None:
            return None
        result = dict(row)
        result["pest_types"] = self._parse_json_value(result.get("pest_types"), default=[])
        return result

    def fetch_active_missions(self) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            "SELECT * FROM missions WHERE status = 'active' ORDER BY created_at DESC",
        )
        results = []
        for row in rows:
            r = dict(row)
            r["pest_types"] = self._parse_json_value(r.get("pest_types"), default=[])
            results.append(r)
        return results

    def fetch_missions(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if status:
            rows = self.fetch_all(
                "SELECT * FROM missions WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        else:
            rows = self.fetch_all(
                "SELECT * FROM missions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        results = []
        for row in rows:
            r = dict(row)
            r["pest_types"] = self._parse_json_value(r.get("pest_types"), default=[])
            results.append(r)
        return results

    def count_missions(self, *, status: str | None = None) -> int:
        if status:
            row = self.fetch_one(
                "SELECT COUNT(*) as cnt FROM missions WHERE status = ?",
                (status,),
            )
        else:
            row = self.fetch_one("SELECT COUNT(*) as cnt FROM missions")
        return int(row["cnt"]) if row else 0

    # ── Iteration CRUD ──

    def create_iteration(
        self,
        *,
        mission_id: str,
        iteration_number: int,
        spray_request_id: str | None = None,
        heatmap_snapshot_id: str | None = None,
        heatmap_algorithm_version: str | None = None,
        spray_plan: dict[str, Any] | None = None,
    ) -> int:
        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT INTO mission_iterations
                  (mission_id, iteration_number, spray_request_id, status, created_at,
                   heatmap_snapshot_id, heatmap_algorithm_version, spray_plan)
                VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    mission_id,
                    iteration_number,
                    spray_request_id,
                    utc_now_iso(),
                    heatmap_snapshot_id,
                    heatmap_algorithm_version,
                    json.dumps(spray_plan or {}, ensure_ascii=False),
                ),
            )
            self._connection.commit()
            return cursor.lastrowid

    def update_iteration(self, iteration_id: int, **kwargs: Any) -> None:
        if not kwargs:
            return
        sets: list[str] = []
        values: list[Any] = []
        for key in (
            "spray_request_id",
            "evaluation_id",
            "status",
            "pre_pest_count",
            "post_pest_count",
            "kill_rate",
            "captured_images",
            "spray_completed_at",
            "inspected_at",
            "evaluated_at",
            "heatmap_snapshot_id",
            "heatmap_algorithm_version",
            "spray_plan",
            "notes",
        ):
            if key in kwargs:
                val = kwargs[key]
                if key in {"captured_images", "spray_plan"} and isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                sets.append(f"{key} = ?")
                values.append(val)
        if not sets:
            return
        values.append(iteration_id)
        with self._lock:
            self._connection.execute(
                f"UPDATE mission_iterations SET {', '.join(sets)} WHERE id = ?",
                values,
            )
            self._connection.commit()

    def fetch_iterations(self, mission_id: str) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            "SELECT * FROM mission_iterations WHERE mission_id = ? ORDER BY iteration_number ASC",
            (mission_id,),
        )
        results = []
        for row in rows:
            r = dict(row)
            r["captured_images"] = self._parse_json_value(r.get("captured_images"), default=[])
            r["spray_plan"] = self._parse_json_value(r.get("spray_plan"), default={})
            results.append(r)
        return results

    def fetch_latest_iteration(self, mission_id: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            "SELECT * FROM mission_iterations WHERE mission_id = ? ORDER BY iteration_number DESC LIMIT 1",
            (mission_id,),
        )
        if row is None:
            return None
        result = dict(row)
        result["captured_images"] = self._parse_json_value(result.get("captured_images"), default=[])
        result["spray_plan"] = self._parse_json_value(result.get("spray_plan"), default={})
        return result

    def fetch_mission_with_iterations(self, mission_id: str) -> dict[str, Any] | None:
        mission = self.fetch_mission_by_mission_id(mission_id)
        if mission is None:
            return None
        mission["iterations"] = self.fetch_iterations(mission_id)
        return mission
