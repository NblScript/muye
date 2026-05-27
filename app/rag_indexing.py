"""RAG indexing service for decisions and mission summaries."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any

from modules.decision.rag import (
    COLLECTION_DECISIONS,
    VectorStoreManager,
    build_historical_decision_document,
)
from modules.infra.common import log_event
from modules.infra.sqlite_store import SqliteStore


class RagIndexer:
    """Indexes decisions and mission summaries into ChromaDB for RAG retrieval."""

    _executor: concurrent.futures.ThreadPoolExecutor | None = None

    def __init__(
        self,
        *,
        rag_vector_store: VectorStoreManager | None,
        sqlite_store: SqliteStore,
        logger: logging.Logger,
        client_ip: str,
        background_tasks: set[asyncio.Task[None]],
    ) -> None:
        self.rag_vector_store = rag_vector_store
        self.sqlite_store = sqlite_store
        self.logger = logger
        self.client_ip = client_ip
        self._background_tasks = background_tasks
        if RagIndexer._executor is None:
            RagIndexer._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def schedule_mission_rag_index(self, mission_uuid: str) -> None:
        """Schedule RAG indexing for a completed or failed mission."""
        if self.rag_vector_store is None:
            return
        task = asyncio.create_task(self._index_mission_into_rag(mission_uuid))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _index_mission_into_rag(self, mission_uuid: str) -> None:
        """Index mission summary into RAG for future decision-making."""
        try:
            mission = self.sqlite_store.fetch_mission_with_iterations(mission_uuid)
            if mission is None:
                return

            from modules.decision.rag import build_mission_summary_document
            document = build_mission_summary_document(
                mission=mission,
                iterations=mission.get("iterations", []),
            )
            if document is None:
                return

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._executor,
                self.rag_vector_store.add_documents,
                COLLECTION_DECISIONS,
                [document],
            )
            log_event(
                self.logger, logging.INFO, "任务已索引到 RAG",
                mission_id=mission_uuid,
                iterations=len(mission.get("iterations", [])),
                final_kill_rate=mission.get("final_kill_rate"),
            )
        except Exception as exc:
            log_event(
                self.logger, logging.WARNING, "任务 RAG 索引失败",
                mission_id=mission_uuid, error=str(exc),
            )

    def schedule_incremental_rag_index(
        self,
        *,
        request_id: str,
        decision: dict[str, Any],
        pest_detections: list[dict[str, Any]],
        field_context: dict[str, Any],
    ) -> None:
        if self.rag_vector_store is None:
            return

        task = asyncio.create_task(
            self._index_decision_into_rag(
                request_id=request_id,
                decision=decision,
                pest_detections=pest_detections,
                field_context=field_context,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _index_decision_into_rag(
        self,
        *,
        request_id: str,
        decision: dict[str, Any],
        pest_detections: list[dict[str, Any]],
        field_context: dict[str, Any],
    ) -> None:
        if self.rag_vector_store is None:
            return

        pest_types = [
            str(item.get("pest_type", "")).strip()
            for item in pest_detections
            if str(item.get("pest_type", "")).strip()
        ]
        crop_cycle = field_context.get("crop_cycle")
        crop_name = None
        if isinstance(crop_cycle, dict):
            candidate = crop_cycle.get("crop_name")
            if isinstance(candidate, str) and candidate.strip():
                crop_name = candidate.strip()

        document = build_historical_decision_document(
            request_id=request_id,
            decision=decision,
            pest_types=pest_types,
            field_id=str(field_context.get("field_id") or ""),
            crop_name=crop_name,
        )
        if document is None:
            return

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._executor,
                self.rag_vector_store.add_documents,
                COLLECTION_DECISIONS,
                [document],
            )
            log_event(
                self.logger,
                logging.INFO,
                "RAG 历史决策增量索引完成",
                request_id=request_id,
                client_ip=self.client_ip,
                pest_types=pest_types,
                crop_name=crop_name or "",
            )
        except Exception as exc:
            log_event(
                self.logger,
                logging.WARNING,
                "RAG 历史决策增量索引失败",
                request_id=request_id,
                client_ip=self.client_ip,
                error=str(exc),
            )
