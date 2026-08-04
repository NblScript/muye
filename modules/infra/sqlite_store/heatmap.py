"""Inspection batch and heatmap snapshot persistence."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from modules.infra.sqlite_store._private import utc_now_iso


class HeatmapMixin:
    """CRUD for durable inspection detections and relative heatmap snapshots."""

    _INSPECTION_KINDS = frozenset({"pre_spray", "reinspection"})

    def save_heatmap_snapshot(
        self,
        *,
        request_id: str,
        field_id: str | None,
        inspection_kind: str,
        iteration_number: int,
        image_paths: list[str],
        detections: list[dict[str, Any]],
        density_grid: list[Any],
        density_metadata: dict[str, Any],
        mission_id: str | None = None,
        captured_at: str | None = None,
        batch_id: str | None = None,
        snapshot_id: str | None = None,
        algorithm_version: str | None = None,
        source: str | None = None,
        is_simulated: bool | None = None,
    ) -> str:
        """Atomically upsert an inspection batch, detections, and its heatmap."""
        normalized_kind = str(inspection_kind).strip().lower()
        if normalized_kind not in self._INSPECTION_KINDS:
            raise ValueError(f"Unsupported inspection kind: {inspection_kind!r}")

        normalized_iteration = int(iteration_number)
        if normalized_iteration < 1:
            raise ValueError("iteration_number must be at least 1")

        self._ensure_task(request_id)
        captured_at = captured_at or utc_now_iso()
        batch_id = batch_id or f"inspection:{request_id}:{normalized_kind}:{normalized_iteration}"
        snapshot_id = snapshot_id or f"heatmap:{request_id}:{normalized_kind}:{normalized_iteration}"

        metadata = dict(density_metadata or {})
        algorithm_version = str(
            algorithm_version or metadata.get("algorithm_version") or "unversioned"
        )
        metadata["algorithm_version"] = algorithm_version
        source = str(source or metadata.get("source") or "unknown")
        simulated = bool(metadata.get("is_simulated", False) if is_simulated is None else is_simulated)
        metadata["source"] = source
        metadata["is_simulated"] = simulated

        normalized_images = list(dict.fromkeys(str(path) for path in image_paths if str(path)))
        pest_counts = Counter(
            str(item.get("pest_type") or item.get("label") or "").strip()
            for item in detections
        )
        pest_counts.pop("", None)
        now = utc_now_iso()

        with self._lock:
            try:
                self._connection.execute(
                    """
                    INSERT INTO inspection_batches (
                      batch_id, request_id, field_id, mission_id, iteration_number,
                      inspection_kind, captured_at, image_paths, source, is_simulated,
                      created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(batch_id) DO UPDATE SET
                      request_id = excluded.request_id,
                      field_id = COALESCE(excluded.field_id, inspection_batches.field_id),
                      mission_id = COALESCE(excluded.mission_id, inspection_batches.mission_id),
                      iteration_number = excluded.iteration_number,
                      inspection_kind = excluded.inspection_kind,
                      captured_at = excluded.captured_at,
                      image_paths = excluded.image_paths,
                      source = excluded.source,
                      is_simulated = excluded.is_simulated
                    """,
                    (
                        batch_id,
                        request_id,
                        field_id,
                        mission_id,
                        normalized_iteration,
                        normalized_kind,
                        captured_at,
                        json.dumps(normalized_images, ensure_ascii=False),
                        source,
                        int(simulated),
                        now,
                    ),
                )
                self._connection.execute(
                    "DELETE FROM inspection_detections WHERE batch_id = ?",
                    (batch_id,),
                )
                self._connection.executemany(
                    """
                    INSERT INTO inspection_detections (
                      batch_id, image_path, pest_type, confidence, bbox, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            batch_id,
                            item.get("image_path")
                            or (normalized_images[0] if len(normalized_images) == 1 else None),
                            str(item.get("pest_type") or item.get("label") or ""),
                            float(item.get("confidence", 0.0)),
                            json.dumps(
                                item.get("position") or item.get("bbox") or {},
                                ensure_ascii=False,
                            ),
                            now,
                        )
                        for item in detections
                    ],
                )
                self._connection.execute(
                    """
                    INSERT INTO heatmap_snapshots (
                      snapshot_id, batch_id, request_id, field_id, mission_id,
                      iteration_number, inspection_kind, captured_at,
                      algorithm_version, density_grid, density_metadata, pest_counts,
                      total_detection_count, source, is_simulated, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(snapshot_id) DO UPDATE SET
                      batch_id = excluded.batch_id,
                      request_id = excluded.request_id,
                      field_id = COALESCE(excluded.field_id, heatmap_snapshots.field_id),
                      mission_id = COALESCE(excluded.mission_id, heatmap_snapshots.mission_id),
                      iteration_number = excluded.iteration_number,
                      inspection_kind = excluded.inspection_kind,
                      captured_at = excluded.captured_at,
                      algorithm_version = excluded.algorithm_version,
                      density_grid = excluded.density_grid,
                      density_metadata = excluded.density_metadata,
                      pest_counts = excluded.pest_counts,
                      total_detection_count = excluded.total_detection_count,
                      source = excluded.source,
                      is_simulated = excluded.is_simulated
                    """,
                    (
                        snapshot_id,
                        batch_id,
                        request_id,
                        field_id,
                        mission_id,
                        normalized_iteration,
                        normalized_kind,
                        captured_at,
                        algorithm_version,
                        json.dumps(density_grid or [], ensure_ascii=False),
                        json.dumps(metadata, ensure_ascii=False),
                        json.dumps(dict(sorted(pest_counts.items())), ensure_ascii=False),
                        len(detections),
                        source,
                        int(simulated),
                        now,
                    ),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

        return snapshot_id

    def attach_heatmap_snapshot_to_mission(
        self,
        *,
        request_id: str,
        mission_id: str,
        inspection_kind: str,
        iteration_number: int,
    ) -> bool:
        """Attach an already persisted snapshot to a mission iteration."""
        with self._lock:
            batch_cursor = self._connection.execute(
                """
                UPDATE inspection_batches
                SET mission_id = ?
                WHERE request_id = ? AND inspection_kind = ? AND iteration_number = ?
                """,
                (mission_id, request_id, inspection_kind, iteration_number),
            )
            snapshot_cursor = self._connection.execute(
                """
                UPDATE heatmap_snapshots
                SET mission_id = ?
                WHERE request_id = ? AND inspection_kind = ? AND iteration_number = ?
                """,
                (mission_id, request_id, inspection_kind, iteration_number),
            )
            self._connection.commit()
        return batch_cursor.rowcount > 0 or snapshot_cursor.rowcount > 0

    def fetch_heatmap_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        if snapshot_id.startswith("legacy:"):
            request_id = snapshot_id.removeprefix("legacy:")
            return self._build_legacy_heatmap_snapshot(request_id) if request_id else None
        row = self.fetch_one(
            "SELECT * FROM heatmap_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        return self._decode_heatmap_snapshot(row) if row else None

    def fetch_heatmap_snapshots(
        self,
        *,
        field_id: str | None = None,
        request_id: str | None = None,
        mission_id: str | None = None,
        pest_type: str | None = None,
        source: str | None = None,
        is_simulated: bool | None = None,
        inspection_kind: str | None = None,
        captured_from: str | None = None,
        captured_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List durable heatmap snapshots using exact, composable filters."""
        filters, params = self._build_heatmap_snapshot_filters(
            field_id=field_id,
            request_id=request_id,
            mission_id=mission_id,
            pest_type=pest_type,
            source=source,
            is_simulated=is_simulated,
            inspection_kind=inspection_kind,
            captured_from=captured_from,
            captured_to=captured_to,
        )
        normalized_limit = max(1, min(int(limit), 200))
        normalized_offset = max(0, int(offset))
        rows = self.fetch_all(
            f"""
            SELECT hs.* FROM heatmap_snapshots AS hs
            WHERE {' AND '.join(filters)}
            ORDER BY hs.captured_at DESC, hs.id DESC
            LIMIT ? OFFSET ?
            """,
            tuple([*params, normalized_limit, normalized_offset]),
        )
        return [self._decode_heatmap_snapshot(row) for row in rows]

    def count_heatmap_snapshots(
        self,
        *,
        field_id: str | None = None,
        request_id: str | None = None,
        mission_id: str | None = None,
        pest_type: str | None = None,
        source: str | None = None,
        is_simulated: bool | None = None,
        inspection_kind: str | None = None,
        captured_from: str | None = None,
        captured_to: str | None = None,
    ) -> int:
        """Count durable heatmap snapshots using the list endpoint filters."""
        filters, params = self._build_heatmap_snapshot_filters(
            field_id=field_id,
            request_id=request_id,
            mission_id=mission_id,
            pest_type=pest_type,
            source=source,
            is_simulated=is_simulated,
            inspection_kind=inspection_kind,
            captured_from=captured_from,
            captured_to=captured_to,
        )
        row = self.fetch_one(
            f"""
            SELECT COUNT(*) AS total FROM heatmap_snapshots AS hs
            WHERE {' AND '.join(filters)}
            """,
            tuple(params),
        )
        return int(row["total"]) if row else 0

    def _build_heatmap_snapshot_filters(
        self,
        *,
        field_id: str | None,
        request_id: str | None,
        mission_id: str | None,
        pest_type: str | None,
        source: str | None,
        is_simulated: bool | None,
        inspection_kind: str | None,
        captured_from: str | None,
        captured_to: str | None,
    ) -> tuple[list[str], list[Any]]:
        filters = ["1 = 1"]
        params: list[Any] = []
        for column, value in (
            ("field_id", field_id),
            ("request_id", request_id),
            ("mission_id", mission_id),
            ("inspection_kind", inspection_kind),
        ):
            if value is not None:
                filters.append(f"hs.{column} = ?")
                params.append(value)
        if source is not None:
            filters.append("hs.source = ? COLLATE NOCASE")
            params.append(source)
        if is_simulated is not None:
            filters.append("hs.is_simulated = ?")
            params.append(int(is_simulated))
        if captured_from is not None:
            filters.append("hs.captured_at >= ?")
            params.append(captured_from)
        if captured_to is not None:
            filters.append("hs.captured_at <= ?")
            params.append(captured_to)
        if pest_type is not None:
            filters.append(
                """
                EXISTS (
                  SELECT 1 FROM inspection_detections AS detection
                  WHERE detection.batch_id = hs.batch_id
                    AND detection.pest_type = ? COLLATE NOCASE
                )
                """
            )
            params.append(pest_type)
        return filters, params

    def fetch_heatmap_snapshot_by_request(
        self,
        request_id: str,
        *,
        inspection_kind: str | None = None,
        iteration_number: int | None = None,
        include_legacy: bool = True,
    ) -> dict[str, Any] | None:
        filters = ["request_id = ?"]
        params: list[Any] = [request_id]
        if inspection_kind is not None:
            filters.append("inspection_kind = ?")
            params.append(inspection_kind)
        if iteration_number is not None:
            filters.append("iteration_number = ?")
            params.append(iteration_number)
        row = self.fetch_one(
            f"""
            SELECT * FROM heatmap_snapshots
            WHERE {' AND '.join(filters)}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        if row:
            return self._decode_heatmap_snapshot(row)
        if include_legacy:
            return self._build_legacy_heatmap_snapshot(request_id)
        return None

    def fetch_latest_heatmap_snapshot(
        self,
        *,
        field_id: str | None = None,
    ) -> dict[str, Any] | None:
        if field_id is None:
            row = self.fetch_one(
                "SELECT * FROM heatmap_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1"
            )
        else:
            row = self.fetch_one(
                """
                SELECT * FROM heatmap_snapshots
                WHERE field_id = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT 1
                """,
                (field_id,),
            )
        return self._decode_heatmap_snapshot(row) if row else None

    def _decode_heatmap_snapshot(self, row: dict[str, Any]) -> dict[str, Any]:
        batch_id = str(row["batch_id"])
        batch = self.fetch_one(
            "SELECT image_paths FROM inspection_batches WHERE batch_id = ?",
            (batch_id,),
        )
        detection_rows = self.fetch_all(
            """
            SELECT image_path, pest_type, confidence, bbox
            FROM inspection_detections
            WHERE batch_id = ?
            ORDER BY id ASC
            """,
            (batch_id,),
        )
        return {
            **dict(row),
            "is_simulated": bool(row.get("is_simulated")),
            "density_grid": self._parse_json_value(row.get("density_grid"), default=[]),
            "density_metadata": self._parse_json_value(
                row.get("density_metadata"), default={}
            ),
            "pest_counts": self._parse_json_value(row.get("pest_counts"), default={}),
            "image_paths": self._parse_json_value(
                batch.get("image_paths") if batch else None,
                default=[],
            ),
            "detections": [
                {
                    "image_path": item.get("image_path"),
                    "pest_type": item.get("pest_type"),
                    "confidence": item.get("confidence"),
                    "position": self._parse_json_value(item.get("bbox"), default={}),
                }
                for item in detection_rows
            ],
            "legacy": False,
        }

    def _build_legacy_heatmap_snapshot(self, request_id: str) -> dict[str, Any] | None:
        task = self.fetch_one(
            "SELECT request_id, field_id, image_path, start_time FROM tasks WHERE request_id = ?",
            (request_id,),
        )
        if task is None:
            return None

        instruction: dict[str, Any] | None = None
        captured_at = task.get("start_time") or utc_now_iso()
        for row in self.fetch_all(
            """
            SELECT timestamp, instruction
            FROM drone_mission_updates
            WHERE request_id = ?
            ORDER BY id DESC
            """,
            (request_id,),
        ):
            candidate = self._parse_json_value(row.get("instruction"), default={})
            if candidate.get("density_grid") is not None:
                instruction = candidate
                captured_at = row.get("timestamp") or captured_at
                break
        if instruction is None:
            return None

        detections = []
        pest_counts: Counter[str] = Counter()
        for item in self.fetch_all(
            """
            SELECT label, confidence, bbox
            FROM detections
            WHERE request_id = ?
            ORDER BY id ASC
            """,
            (request_id,),
        ):
            pest_type = str(item.get("label") or "")
            if pest_type:
                pest_counts[pest_type] += 1
            detections.append(
                {
                    "image_path": task.get("image_path"),
                    "pest_type": pest_type,
                    "confidence": item.get("confidence"),
                    "position": self._parse_json_value(item.get("bbox"), default={}),
                }
            )

        metadata = self._parse_json_value(instruction.get("density_metadata"), default={})
        mission = self.fetch_one(
            """
            SELECT mission_id FROM missions
            WHERE original_request_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (request_id,),
        )
        source = str(metadata.get("source") or instruction.get("source") or "legacy_task")
        return {
            "snapshot_id": f"legacy:{request_id}",
            "batch_id": f"legacy:{request_id}",
            "request_id": request_id,
            "field_id": task.get("field_id"),
            "mission_id": mission.get("mission_id") if mission else None,
            "iteration_number": 1,
            "inspection_kind": "pre_spray",
            "captured_at": captured_at,
            "algorithm_version": str(metadata.get("algorithm_version") or "legacy-unversioned"),
            "density_grid": instruction.get("density_grid") or [],
            "density_metadata": metadata,
            "pest_counts": dict(sorted(pest_counts.items())),
            "total_detection_count": len(detections),
            "source": source,
            "is_simulated": bool(metadata.get("is_simulated", False)),
            "image_paths": [task["image_path"]] if task.get("image_path") else [],
            "detections": detections,
            "legacy": True,
            "created_at": None,
        }
