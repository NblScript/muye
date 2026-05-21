"""
Muye - Intelligent Agricultural Pest Control System.

This is the main entry point that:
- Creates and configures the FastAPI app
- Registers all API routes
- Defines the MuyeApplication class for the processing pipeline
- Provides the startup entry point
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import uvicorn
from fastapi import FastAPI

from modules.decision.ai_decision import DecisionEngine
from modules.decision.agents.consultation import ExpertConsultation
from modules.infra.common import (
    CONFIG_DIR,
    DATA_DIR,
    IMAGES_DIR,
    build_logger,
    ensure_runtime_dirs,
    generate_request_id,
    load_environment,
    load_json,
    load_yaml,
    log_event,
)
from modules.detection.data_collector import DataCollectorService
from modules.decision.decision_context import SqliteDecisionContextProvider
from modules.drone.controller import DroneController
from modules.drone.field_context_resolver import FieldContextResolver
from modules.infra.event_bus import FileEventBus
from modules.detection.image_processor import ImageProcessor
from modules.detection.local_yolo_api import create_app as create_local_yolo_app
from modules.detection.local_yolo_api import load_local_yolo_settings
from modules.decision.rag import (
    COLLECTION_DECISIONS,
    COLLECTION_PESTICIDES,
    DecisionRAGRetriever,
    QwenEmbeddings,
    VectorStoreManager,
    build_historical_decision_document,
    load_pesticide_from_json,
    load_pesticide_from_sqlite,
)
from modules.infra.sqlite_store import SqliteStore
from modules.infra.weather import WeatherClient

# Import route registration functions
from app.routes.dashboard import register_dashboard_routes
from app.routes.demo import register_demo_routes
from app.routes.drone import ensure_px4_ready, register_drone_routes
from app.routes.health import register_health_routes
from app.routes.sim import register_sim_routes
from app.routes.tasks import register_tasks_routes
from app.routes.workflow import register_workflow_routes

# Import services and models
from models.schemas import (
    DashboardContextResponse,
    DashboardTaskEntry,
    HistoryTaskEntry,
    SimDroneState,
    SimMapStateResponse,
    SimPoint,
    WorkflowEventEntry,
    WorkflowHistoryResponse,
    WorkflowStateResponse,
    WorkflowTaskState,
    WorkflowTimelineEntry,
)
from app.services.map_simulator import Px4MapStateSimulator
from app.services.workflow_service import (
    MAX_UPLOAD_BYTES,
    build_fallback_workflow_state,
    build_history_response,
    build_workflow_state_response,
    clear_demo_runtime_state,
    count_sqlite_tasks,
    load_sqlite_task_views,
    load_task_by_request_id,
    merge_sqlite_tasks_with_events,
    sanitize_filename,
)

# Import core configuration
from app.config import build_local_yolo_urls
from app.config_types import MuyeConfig
import app.deps as deps
from app.deps import embedded_yolo_runner_for_health


# ============================================================================
# FastAPI Application Setup
# ============================================================================

# Global simulator instance
simulator = Px4MapStateSimulator()

# Create FastAPI app
api_app = FastAPI(title="Muye Frontend API", version="1.3.0")

# Register all routes
register_health_routes(api_app)
register_workflow_routes(api_app)
register_dashboard_routes(api_app)
register_demo_routes(api_app)
register_drone_routes(api_app)
register_tasks_routes(api_app)
register_sim_routes(api_app, simulator)


# ============================================================================
# Embedded API Runners
# ============================================================================


class EmbeddedApiRunner(ABC):
    """Abstract base class for embedded API runners."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.settings = self._load_settings()
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task[None] | None = None

    @abstractmethod
    def _load_settings(self) -> Any:
        """Load and return the settings object for this runner."""
        ...

    @abstractmethod
    def _create_app(self) -> FastAPI:
        """Create and return the FastAPI application."""
        ...

    @abstractmethod
    def _get_health_url(self) -> str:
        """Return the health check URL for this API."""
        ...

    @abstractmethod
    def _get_startup_message(self) -> str:
        """Return the startup success log message."""
        ...

    @abstractmethod
    def _get_startup_error_prefix(self) -> str:
        """Return the prefix for startup error messages."""
        ...

    @abstractmethod
    def _get_log_extra(self) -> dict[str, Any]:
        """Return extra fields for the startup log message."""
        ...

    async def start(self) -> None:
        started = time.perf_counter()
        request_id = generate_request_id()
        app = self._create_app()
        config = uvicorn.Config(
            app=app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        self.server = server
        self.server_task = asyncio.create_task(server.serve())

        try:
            await self._wait_until_ready()
            log_event(
                self.logger,
                logging.INFO,
                self._get_startup_message(),
                request_id=request_id,
                duration_ms=(time.perf_counter() - started) * 1000,
                **self._get_log_extra(),
            )
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        if not self.server_task:
            return

        self.server.should_exit = True  # type: ignore[union-attr]
        try:
            await asyncio.wait_for(self.server_task, timeout=5)
        except asyncio.TimeoutError:
            self.server_task.cancel()
            await asyncio.gather(self.server_task, return_exceptions=True)
        finally:
            self.server_task = None
            self.server = None

    async def _wait_until_ready(self, timeout_seconds: float = 30, interval_seconds: float = 0.2) -> None:
        deadline = time.monotonic() + timeout_seconds
        health_url = self._get_health_url()
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            while time.monotonic() < deadline:
                if self.server_task and self.server_task.done():
                    error = self.server_task.exception()
                    if error:
                        raise RuntimeError(f"{self._get_startup_error_prefix()}启动失败: {error}") from error
                    raise RuntimeError(f"{self._get_startup_error_prefix()}意外退出")
                try:
                    response = await client.get(health_url)
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(interval_seconds)
        raise TimeoutError(f"等待 {self._get_startup_error_prefix()}就绪超时: {health_url}")


class EmbeddedYoloApiRunner(EmbeddedApiRunner):
    """Runner for embedded YOLO API server."""

    def _load_settings(self) -> Any:
        return load_local_yolo_settings()

    def _create_app(self) -> FastAPI:
        return create_local_yolo_app(settings=self.settings, logger=self.logger)

    def _get_health_url(self) -> str:
        _, health_url = build_local_yolo_urls(self.settings.host, self.settings.port)
        return health_url

    def _get_startup_message(self) -> str:
        return "内嵌 YOLO API 已启动"

    def _get_startup_error_prefix(self) -> str:
        return "内嵌 YOLO API"

    def _get_log_extra(self) -> dict[str, Any]:
        detect_url, health_url = build_local_yolo_urls(self.settings.host, self.settings.port)
        return {"detect_url": detect_url, "health_url": health_url}

    @property
    def detect_url(self) -> str:
        """Return the detect API URL."""
        detect_url, _ = build_local_yolo_urls(self.settings.host, self.settings.port)
        return detect_url

    @property
    def health_url(self) -> str:
        """Return the health check URL."""
        _, health_url = build_local_yolo_urls(self.settings.host, self.settings.port)
        return health_url


# ============================================================================
# Main Application Class
# ============================================================================

class MuyeApplication:
    """Main application class for the Muye agricultural pest control system."""

    def __init__(self, config: MuyeConfig | None = None) -> None:
        ensure_runtime_dirs()
        load_environment()
        self.logger = build_logger("muye")
        self.drone_config = load_json(CONFIG_DIR / "drone_config.json")
        self.config = config or MuyeConfig.from_env(drone_config=self.drone_config)
        self._apply_runtime_drone_overrides()
        self.yolo_config = load_yaml(CONFIG_DIR / "yolo_config.yaml")
        self.event_bus = FileEventBus()
        self.client_ip = self.config.client_ip
        self.sqlite_store = SqliteStore(self.config.sqlite_path, logger=self.logger)
        self.field_resolver = FieldContextResolver(
            sqlite_store=self.sqlite_store,
            drone_config=self.drone_config,
            logger=self.logger,
        )
        self.rag_embeddings: QwenEmbeddings | None = None
        self.rag_vector_store: VectorStoreManager | None = None
        self.rag_retriever: DecisionRAGRetriever | None = None
        self._background_tasks: set[asyncio.Task[None]] = set()

        self.queue: asyncio.Queue[tuple[str, Path, dict[str, Any]]] = asyncio.Queue()
        self.pending_images: set[str] = set()
        self.worker_tasks: list[asyncio.Task[None]] = []

        # 手动起飞确认机制
        self._takeoff_confirmed = asyncio.Event()
        self._takeoff_request_id: str | None = None
        deps.takeoff_confirmation_event = self._takeoff_confirmed
        deps.clear_takeoff_confirmation_state()

        self.yolo_api_url = self.config.yolo_api_url
        self.image_processor = ImageProcessor(
            api_url=self.config.yolo_api_url,
            api_key=self.config.yolo_api_key,
            confidence_threshold=self.config.yolo_confidence_threshold,
            timeout_seconds=float(self.yolo_config.get("timeout_seconds", 20)),
            batch_size=int(self.yolo_config.get("batch_size", 4)),
            headers=self.yolo_config.get("request_headers", {}),
            logger=self.logger,
        )
        self.weather_client = WeatherClient(
            geo_api_url=self.config.qweather_geo_url,
            weather_api_url=self.config.qweather_weather_url,
            api_key=self.config.qweather_api_key,
            use_mock=self.config.qweather_use_mock,
            mock_weather={
                "temperature": self.config.qweather_mock_temperature,
                "humidity": self.config.qweather_mock_humidity,
                "summary": self.config.qweather_mock_summary,
                "wind_direction": self.config.qweather_mock_wind_direction,
                "wind_scale_text": self.config.qweather_mock_wind_scale,
                "wind_speed": self.config.qweather_mock_wind_speed,
            },
            timeout_seconds=float(
                self.drone_config.get("execution", {}).get("request_timeout_seconds", 15)
            ),
            logger=self.logger,
        )
        decision_context_provider = None
        if self.config.enable_sqlite_decision_context:
            decision_context_provider = SqliteDecisionContextProvider(self.sqlite_store)
        self.rag_retriever = self._initialize_rag()
        consultation = None
        if self.config.multi_agent_enabled:
            consultation = ExpertConsultation(
                api_url=self.config.qwen_api_url,
                api_key=self.config.qwen_api_key,
                model=self.config.qwen_model,
                rag_retriever=self.rag_retriever,
                event_bus=self.event_bus,
                logger=self.logger,
                timeout_seconds=self.config.multi_agent_timeout_seconds,
            )
            self.logger.info("多智能体会诊模式已启用")
        self.decision_engine = DecisionEngine(
            api_url=self.config.qwen_api_url,
            api_key=self.config.qwen_api_key,
            model=self.config.qwen_model,
            weather_client=self.weather_client,
            use_mock=self.config.qwen_use_mock,
            timeout_seconds=30,
            logger=self.logger,
            event_bus=self.event_bus,
            decision_context_provider=decision_context_provider,
            rag_retriever=self.rag_retriever,
            consultation=consultation,
        )
        self.drone_controller = DroneController(
            drone_config=self.drone_config,
            logger=self.logger,
            event_bus=self.event_bus,
            sqlite_store=self.sqlite_store,
        )
        self.data_collector = DataCollectorService(
            images_dir=IMAGES_DIR,
            drone_config=self.drone_config,
            on_new_image=self.enqueue_image,
            logger=self.logger,
        )

    def _initialize_rag(self) -> DecisionRAGRetriever | None:
        if not self.config.rag_enabled:
            self.logger.info("RAG 初始化已禁用: RAG_ENABLED=false")
            return None

        try:
            self.rag_embeddings = QwenEmbeddings(
                api_url=self.config.qwen_embedding_api_url,
                api_key=self.config.qwen_api_key,
                model=self.config.qwen_embedding_model,
                dimensions=self.config.qwen_embedding_dimensions,
                timeout=self.config.qwen_embedding_timeout_seconds,
            )
            self.rag_vector_store = VectorStoreManager(embedding=self.rag_embeddings)
            self._seed_rag_pesticide_knowledge_if_needed(self.rag_vector_store)
            retriever = DecisionRAGRetriever(vector_store=self.rag_vector_store)
            self.logger.info("RAG 检索器初始化完成")
            return retriever
        except Exception as exc:
            self.rag_embeddings = None
            self.rag_vector_store = None
            self.logger.warning("RAG 初始化失败，已降级为无 RAG 模式: %s", exc)
            return None

    def _seed_rag_pesticide_knowledge_if_needed(self, vector_store: VectorStoreManager) -> None:
        if self._get_vector_collection_count(vector_store, COLLECTION_PESTICIDES) > 0:
            return

        pesticide_docs = self._load_rag_pesticide_documents()
        if not pesticide_docs:
            self.logger.warning("RAG 农药目录为空，未加载任何初始化知识")
            return

        vector_store.add_documents(COLLECTION_PESTICIDES, pesticide_docs)
        self.logger.info("RAG 农药目录初始化完成，已加载 %s 条文档", len(pesticide_docs))

    def _load_rag_pesticide_documents(self) -> list[Any]:
        try:
            pesticide_docs = load_pesticide_from_sqlite(self.sqlite_store)
        except Exception as exc:
            self.logger.warning("从 SQLite 加载 RAG 农药目录失败，将尝试 seed JSON: %s", exc)
            pesticide_docs = []

        if pesticide_docs:
            return pesticide_docs

        seed_path = DATA_DIR / "seeds" / "henan" / "pesticide_catalog.json"
        if not seed_path.exists():
            return []

        try:
            return load_pesticide_from_json(seed_path)
        except Exception as exc:
            self.logger.warning("从 seed JSON 加载 RAG 农药目录失败: %s", exc)
            return []

    def _get_vector_collection_count(
        self,
        vector_store: VectorStoreManager,
        collection_name: str,
    ) -> int:
        store = vector_store.get_store(collection_name)
        collection = getattr(store, "_collection", None)
        if collection is None:
            return 0
        return int(collection.count())

    def _apply_runtime_drone_overrides(self) -> None:
        execution = self.drone_config.setdefault("execution", {})
        px4_config = self.drone_config.setdefault("px4", {})

        if self.config.drone_backend:
            execution["backend"] = self.config.drone_backend.strip().lower()

        execution["backend"] = "px4"
        execution["simulate_only"] = False

        if self.config.px4_system_address:
            px4_config["system_address"] = self.config.px4_system_address
        px4_config["connect_timeout_seconds"] = self.config.px4_connect_timeout_seconds
        px4_config["mission_timeout_seconds"] = self.config.px4_mission_timeout_seconds
        px4_config["auto_arm"] = self.config.px4_auto_arm
        px4_config["auto_start_mission"] = self.config.px4_auto_start_mission
        px4_config["auto_start_on_spray"] = self.config.px4_auto_start_on_spray
        px4_config["return_to_launch_after_mission"] = self.config.px4_return_to_launch_after_mission
        px4_config["require_global_position"] = self.config.px4_require_global_position
        px4_config["arm_timeout_seconds"] = self.config.px4_arm_timeout_seconds
        px4_config["arm_retries"] = self.config.px4_arm_retries
        px4_config["arm_retry_delay_seconds"] = self.config.px4_arm_retry_delay_seconds
        px4_config["allow_force_arm"] = self.config.px4_allow_force_arm
        px4_config["prefer_demo_field"] = True
        px4_config["acceptance_radius_m"] = self.config.px4_acceptance_radius_m
        px4_config["execution_mode"] = "native_mission"

    def configure_embedded_yolo_api(self, detect_url: str) -> None:
        self.yolo_api_url = detect_url
        self.image_processor.api_url = detect_url

    def configure_drone_backend(self, backend: str) -> None:
        normalized = backend.strip().lower()
        if normalized != "px4":
            raise ValueError("无人机执行后端已固定为 px4")
        self.drone_config.setdefault("execution", {})["backend"] = normalized
        self.drone_config["execution"]["simulate_only"] = False

    async def start(
        self,
        *,
        workers: int = 1,
        enable_scheduler: bool = True,
        capture_on_startup: bool | None = None,
    ) -> None:
        worker_count = max(1, workers)
        self.worker_tasks = [
            asyncio.create_task(self._worker(index + 1)) for index in range(worker_count)
        ]
        await self.data_collector.start(
            enable_scheduler=enable_scheduler,
            capture_on_startup=capture_on_startup,
        )
        log_event(
            self.logger,
            logging.INFO,
            "主处理链已启动",
            request_id=generate_request_id(),
            client_ip=self.client_ip,
            workers=worker_count,
            enable_scheduler=enable_scheduler,
            capture_on_startup=(
                self.data_collector.capture_on_startup
                if capture_on_startup is None
                else capture_on_startup
            ),
        )

    async def shutdown(self) -> None:
        await self.data_collector.shutdown()
        for task in self.worker_tasks:
            task.cancel()
        for task in list(self._background_tasks):
            task.cancel()
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        await self.image_processor.close()
        await self.decision_engine.close()
        await self.weather_client.close()
        await self.drone_controller.close()
        self.sqlite_store.close()

    async def enqueue_image(self, image_path: Path) -> None:
        ready = await self._wait_until_ready(image_path)
        if not ready:
            log_event(
                self.logger,
                logging.ERROR,
                "图片文件未就绪，已跳过",
                request_id=generate_request_id(),
                client_ip=self.client_ip,
                image_path=str(image_path),
            )
            return

        key = str(image_path.resolve())
        if key in self.pending_images:
            return

        request_id = generate_request_id()
        try:
            field_context = self.field_resolver.resolve()
        except Exception as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "运行时地块上下文解析失败",
                request_id=request_id,
                client_ip=self.client_ip,
                image_path=str(image_path),
                error=str(exc),
            )
            return
        self.pending_images.add(key)
        await self.queue.put((request_id, image_path, field_context))
        self._sqlite_write(
            request_id,
            "mark_task_queued",
            lambda: self.sqlite_store.mark_task_queued(
                request_id,
                str(image_path),
                field_id=field_context.get("field_id"),
            ),
        )
        self.event_bus.publish(
            request_id=request_id,
            stage="queue",
            status="queued",
            message="图片已进入处理队列",
            payload={
                "image_path": str(image_path),
                "filename": image_path.name,
                "field_id": field_context.get("field_id"),
                "field_name": field_context.get("name"),
            },
        )
        log_event(
            self.logger,
            logging.INFO,
            "新图片已进入处理队列",
            request_id=request_id,
            client_ip=self.client_ip,
            image_path=str(image_path),
            queue_size=self.queue.qsize(),
        )

    async def run_forever(
        self,
        workers: int,
        capture_on_startup: bool | None = None,
    ) -> None:
        await self.start(workers=workers, capture_on_startup=capture_on_startup)
        await asyncio.Event().wait()

    async def run_once(self, workers: int, timeout_seconds: int) -> None:
        await self.start(workers=workers, enable_scheduler=False, capture_on_startup=False)
        await self.data_collector.capture_image()
        await asyncio.wait_for(self.queue.join(), timeout=timeout_seconds)

    async def _worker(self, worker_id: int) -> None:
        while True:
            request_id, image_path, field_context = await self.queue.get()
            try:
                await self._process_image(request_id, image_path, field_context, worker_id)
            finally:
                self.pending_images.discard(str(image_path.resolve()))
                self.queue.task_done()

    async def _process_image(
        self,
        request_id: str,
        image_path: Path,
        field_context: dict[str, Any],
        worker_id: int,
    ) -> None:
        started = time.perf_counter()
        try:
            self._sqlite_write(
                request_id,
                "mark_task_started",
                lambda: self.sqlite_store.mark_task_started(
                    request_id,
                    str(image_path),
                    field_id=field_context.get("field_id"),
                ),
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="pipeline",
                status="running",
                message="开始处理图片",
                payload={
                    "image_path": str(image_path),
                    "worker_id": worker_id,
                    "field_id": field_context.get("field_id"),
                    "field_name": field_context.get("name"),
                },
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="yolo",
                status="running",
                message="正在执行 YOLO 识别",
                payload={"image_path": str(image_path)},
            )
            detections = await self.image_processor.detect_pests(
                image_path=image_path,
                request_id=request_id,
                client_ip=self.client_ip,
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="yolo",
                status="completed",
                message="YOLO 识别完成",
                payload={"image_path": str(image_path), "detections": detections},
            )
            self._sqlite_write(
                request_id,
                "replace_detections",
                lambda: self.sqlite_store.replace_detections(request_id, detections),
            )
            if not detections:
                self._sqlite_write(
                    request_id,
                    "mark_task_finished_no_detections",
                    lambda: self.sqlite_store.mark_task_finished(request_id, "completed"),
                )
                self.event_bus.publish(
                    request_id=request_id,
                    stage="pipeline",
                    status="completed",
                    message="未发现超过阈值的害虫目标",
                    payload={"image_path": str(image_path), "detections": []},
                )
                log_event(
                    self.logger,
                    logging.INFO,
                    "未发现超过阈值的害虫目标",
                    request_id=request_id,
                    client_ip=self.client_ip,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    image_path=str(image_path),
                    worker_id=worker_id,
                )
                return

            bundle = await self.decision_engine.generate_decision(
                pest_detections=detections,
                field_context=field_context,
                request_id=request_id,
                client_ip=self.client_ip,
            )
            execution_plan = self.drone_controller.plan_spray_mission(
                field_context=field_context,
                current_weather=bundle["weather"],
            )
            self._sqlite_write(
                request_id,
                "add_weather_snapshot",
                lambda: self.sqlite_store.add_weather_snapshot(request_id, bundle["weather"]),
            )
            self._sqlite_write(
                request_id,
                "add_decision",
                lambda: self.sqlite_store.add_decision(request_id, bundle["decision"]),
            )
            self._schedule_incremental_rag_index(
                request_id=request_id,
                decision=bundle["decision"],
                pest_detections=detections,
                field_context=field_context,
            )

            # 手动模式：决策完成后暂停，等待人工确认起飞
            takeoff_mode = str(
                self.drone_config.get("execution", {}).get("takeoff_mode", "auto")
            ).strip().lower()
            if takeoff_mode == "manual":
                self._takeoff_request_id = request_id
                self._takeoff_confirmed.clear()
                deps.set_pending_takeoff_request(request_id)
                self.event_bus.publish(
                    request_id=request_id,
                    stage="drone",
                    status="pending_confirmation",
                    message="决策完成，等待确认起飞",
                    payload={
                        "task_id": f"manual-{request_id[:8]}",
                        "progress": 30,
                        "instruction": execution_plan,
                        "medication": bundle["decision"].get("施药方案", {}),
                        "current_waypoint_index": 0,
                        "position": None,
                    },
                )
                self.logger.info(
                    "手动模式：等待起飞确认 request_id=%s", request_id
                )
                await deps.wait_for_takeoff_confirmation()
                deps.clear_takeoff_confirmation_state()
                self.logger.info(
                    "手动模式：已确认起飞 request_id=%s", request_id
                )

            await self._ensure_px4_ready_for_spray(request_id)
            result = await self.drone_controller.execute_spray_mission(
                decision=bundle["decision"],
                current_weather=bundle["weather"],
                request_id=request_id,
                client_ip=self.client_ip,
                execution_plan=execution_plan,
                field_context=field_context,
            )
            spray_record = self.drone_controller.build_spray_record(
                request_id=request_id,
                field_context=field_context,
                decision=bundle["decision"],
                weather=bundle["weather"],
                execution_plan=execution_plan,
                mission_result=result,
            )
            if spray_record is not None:
                self._sqlite_write(
                    request_id,
                    "upsert_spray_record",
                    lambda: self.sqlite_store.upsert_spray_record(spray_record),
                )
            self._sqlite_write(
                request_id,
                "mark_task_finished_success",
                lambda: self.sqlite_store.mark_task_finished(request_id, "completed"),
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="pipeline",
                status="completed",
                message="整条处理链执行成功",
                payload={
                    "image_path": str(image_path),
                    "detections": detections,
                    "weather": bundle["weather"],
                    "decision": bundle["decision"],
                    "execution_plan": execution_plan,
                    "mission_result": result,
                },
            )
            log_event(
                self.logger,
                logging.INFO,
                "整条处理链执行成功",
                request_id=request_id,
                client_ip=self.client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                image_path=str(image_path),
                worker_id=worker_id,
                detections=detections,
                execution_plan=execution_plan,
                mission_result=result,
            )
        except Exception as exc:
            self._sqlite_write(
                request_id,
                "mark_task_finished_error",
                lambda: self.sqlite_store.mark_task_finished(request_id, "error"),
            )
            self.event_bus.publish(
                request_id=request_id,
                stage="pipeline",
                status="error",
                message="图片处理链执行失败",
                payload={"image_path": str(image_path), "error": str(exc)},
            )
            log_event(
                self.logger,
                logging.ERROR,
                "图片处理链执行失败",
                request_id=request_id,
                client_ip=self.client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                image_path=str(image_path),
                worker_id=worker_id,
                error=str(exc),
            )

    def _sqlite_write(
        self,
        request_id: str,
        operation: str,
        callback: Callable[[], None],
    ) -> None:
        try:
            callback()
        except Exception as exc:
            log_event(
                self.logger,
                logging.WARNING,
                "SQLite 写入失败",
                request_id=request_id,
                client_ip=self.client_ip,
                operation=operation,
                sqlite_path=str(self.sqlite_store.db_path),
                error=str(exc),
            )

    def _schedule_incremental_rag_index(
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

    async def _ensure_px4_ready_for_spray(self, request_id: str) -> None:
        execution = self.drone_config.get("execution", {})
        px4_config = self.drone_config.get("px4", {})
        if str(execution.get("backend", "")).strip().lower() != "px4":
            return
        if not bool(px4_config.get("auto_start_on_spray", True)):
            return

        self.event_bus.publish(
            request_id=request_id,
            stage="drone",
            status="running",
            message="正在启动 PX4 飞行仿真",
            payload={"progress": 35},
        )
        try:
            px4_info = await ensure_px4_ready()
        except Exception as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "PX4 自动启动失败",
                request_id=request_id,
                client_ip=self.client_ip,
                error=str(exc),
            )
            raise

        self.event_bus.publish(
            request_id=request_id,
            stage="drone",
            status="running",
            message="PX4 已就绪，准备执行喷洒航线",
            payload={"progress": 40, "px4": px4_info},
        )
        log_event(
            self.logger,
            logging.INFO,
            "PX4 已关联启动",
            request_id=request_id,
            client_ip=self.client_ip,
            px4=px4_info,
        )

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
            await asyncio.to_thread(
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

    async def _wait_until_ready(
        self,
        image_path: Path,
        retries: int = 10,
        delay_seconds: float = 0.2,
    ) -> bool:
        last_size = -1
        for _ in range(retries):
            if image_path.exists():
                current_size = image_path.stat().st_size
                if current_size > 0 and current_size == last_size:
                    return True
                last_size = current_size
            await asyncio.sleep(delay_seconds)
        return image_path.exists() and image_path.stat().st_size > 0


# ============================================================================
# Main Entry Point
# ============================================================================

async def _async_main(args: argparse.Namespace) -> None:
    app = MuyeApplication()
    embedded_yolo_runner: EmbeddedYoloApiRunner | None = None
    try:
        app.configure_drone_backend(args.drone_backend)

        if args.with_yolo_api:
            embedded_yolo_runner = EmbeddedYoloApiRunner(logger=app.logger)
            deps.embedded_yolo_runner_for_health = embedded_yolo_runner
            app.configure_embedded_yolo_api(embedded_yolo_runner.detect_url)
            await embedded_yolo_runner.start()
            app.logger.info(
                "一键模式已接管 YOLO API 目标地址: %s",
                embedded_yolo_runner.detect_url,
            )
        else:
            app.logger.info(
                "当前使用外部 YOLO API: %s",
                app.yolo_api_url,
            )

        if args.once:
            await app.run_once(workers=args.workers, timeout_seconds=args.timeout)
        else:
            await app.run_forever(
                workers=args.workers,
                capture_on_startup=False if args.no_capture_on_startup else None,
            )
    finally:
        await app.shutdown()
        if embedded_yolo_runner:
            await embedded_yolo_runner.stop()
        deps.embedded_yolo_runner_for_health = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="app.main", description="牧野智能农业害虫防治系统")
    parser.add_argument("--once", action="store_true", help="执行一次采集与处理流程后退出")
    parser.add_argument(
        "--with-yolo-api",
        action="store_true",
        help="在主进程内一并启动本地 YOLO API，再启动农业防治主系统",
    )
    parser.add_argument(
        "--drone-backend",
        choices=["px4"],
        default="px4",
        help="无人机执行后端固定为 px4",
    )
    parser.add_argument(
        "--no-capture-on-startup",
        action="store_true",
        help="启动后不立即自动采图，适合由外部脚本投喂指定巡检图片",
    )
    parser.add_argument("--workers", type=int, default=1, help="图片处理并发 worker 数量")
    parser.add_argument("--timeout", type=int, default=60, help="--once 模式的等待超时时间")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
