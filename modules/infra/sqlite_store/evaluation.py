"""Evaluation mixin for task_evaluations table."""

from __future__ import annotations

from typing import Any

from modules.infra.sqlite_store._private import utc_now_iso


class EvaluationMixin:
    """CRUD for pesticide effectiveness evaluation records."""

    def create_evaluation(
        self,
        *,
        original_request_id: str,
        scheduled_at: str,
        action_time_hours: float,
        pre_pest_count: int,
        kill_rate_threshold: float = 0.7,
        retry_count: int = 0,
    ) -> int:
        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT INTO task_evaluations
                  (original_request_id, status, scheduled_at, action_time_hours,
                   pre_pest_count, kill_rate_threshold, retry_count)
                VALUES (?, 'scheduled', ?, ?, ?, ?, ?)
                """,
                (
                    original_request_id,
                    scheduled_at,
                    action_time_hours,
                    pre_pest_count,
                    kill_rate_threshold,
                    retry_count,
                ),
            )
            self._connection.commit()
            return cursor.lastrowid

    def update_evaluation(self, evaluation_id: int, **kwargs: Any) -> None:
        if not kwargs:
            return
        sets: list[str] = []
        values: list[Any] = []
        for key in (
            "status",
            "reinspect_request_id",
            "inspected_at",
            "evaluated_at",
            "post_pest_count",
            "kill_rate",
            "retry_request_id",
            "notes",
        ):
            if key in kwargs:
                sets.append(f"{key} = ?")
                values.append(kwargs[key])
        if not sets:
            return
        values.append(evaluation_id)
        with self._lock:
            self._connection.execute(
                f"UPDATE task_evaluations SET {', '.join(sets)} WHERE id = ?",
                values,
            )
            self._connection.commit()

    def fetch_evaluation_by_task(self, request_id: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT * FROM task_evaluations
            WHERE original_request_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (request_id,),
        )
        return dict(row) if row else None

    def fetch_evaluations_by_status(self, status: str) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            "SELECT * FROM task_evaluations WHERE status = ? ORDER BY scheduled_at ASC",
            (status,),
        )
        return [dict(r) for r in rows]

    def fetch_pending_evaluations(self, due_before: str | None = None) -> list[dict[str, Any]]:
        if due_before is None:
            due_before = utc_now_iso()
        rows = self.fetch_all(
            """
            SELECT * FROM task_evaluations
            WHERE status = 'scheduled' AND scheduled_at <= ?
            ORDER BY scheduled_at ASC
            """,
            (due_before,),
        )
        return [dict(r) for r in rows]

    def fetch_evaluation_chain(self, request_id: str) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT * FROM task_evaluations
            WHERE original_request_id = ?
            ORDER BY id ASC
            """,
            (request_id,),
        )
        return [dict(r) for r in rows]
