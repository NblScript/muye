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
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI

from modules.decision.ai_decision import DecisionEngine
from modules.decision.agents.consultation import ExpertConsultation
from modules.decision.router import DecisionRouter
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
    load_pesticide_from_json,
    load_pesticide_from_sqlite,
)
from modules.infra.sqlite_store import SqliteStore
from modules.infra.weather import WeatherClient

# Import route registration functions
from app.routes.dashboard import register_dashboard_routes
from app.routes.demo import register_demo_routes
from app.routes.demo_readiness import register_demo_readiness_routes
from app.routes.drone import ensure_px4_ready, register_drone_routes
from app.routes.evaluation import register_evaluation_routes
from app.routes.health import register_health_routes
from app.routes.mission import register_mission_routes
from app.routes.sim import register_sim_routes
from app.routes.tasks import register_tasks_routes
from app.routes.workflow import register_workflow_routes

# Import services and models
from app.services.map_simulator import Px4MapStateSimulator
from app.services.pipeline_policy_service import (
    resolve_policy_takeoff_mode,
    resolve_runtime_takeoff_mode,
)
from app.services.pipeline_planning_service import plan_spray_mission

# Import core configuration
from app.config import build_local_yolo_urls
from app.config_types import MuyeConfig
import app.deps as deps
from app.deps import embedded_yolo_runner_for_health
from app.embedded_runners import EmbeddedApiRunner, EmbeddedYoloApiRunner
from app.mission_manager import MissionManager
from app.rag_indexing import RagIndexer
from app.utils import safe_sqlite_write


# ============================================================================
# FastAPI Application Setup
# ============================================================================

# Global simulator instance
simulator = Px4MapStateSimulator()

# Create FastAPI app
api_app = FastAPI(title="Muye Frontend API", version="1.3.0")

# Rate limiting middleware
from app.middleware import RateLimitMiddleware

_rate_limit = int(os.environ.get("MUYE_API_RATE_LIMIT_PER_MINUTE", "120"))
api_app.add_middleware(RateLimitMiddleware, limit_per_minute=_rate_limit)

# Register all routes
register_health_routes(api_app)
register_workflow_routes(api_app)
register_dashboard_routes(api_app)
register_demo_routes(api_app)
register_demo_readiness_routes(api_app)
register_drone_routes(api_app)
register_tasks_routes(api_app)
register_evaluation_routes(api_app)
register_mission_routes(api_app)
register_sim_routes(api_app, simulator)


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

        # 加载决策模型 provider 映射（model_config.yaml）
        from modules.decision.agents.expert_roles import apply_provider_mapping, load_provider_mapping
        provider_mapping = load_provider_mapping()
        if provider_mapping:
            apply_provider_mapping(provider_mapping)

        consultation = None
        if self.config.multi_agent_enabled:
            providers: dict[str, dict[str, str]] = {}
            providers["qwen"] = {
                "api_url": self.config.qwen_api_url,
                "api_key": self.config.qwen_api_key,
                "model": self.config.qwen_model,
            }
            if self.config.deepseek_api_key:
                providers["deepseek"] = {
                    "api_url": self.config.deepseek_api_url,
                    "api_key": self.config.deepseek_api_key,
                    "model": self.config.deepseek_model,
                }
            if self.config.xiaomi_api_key and self.config.xiaomi_api_url:
                providers["xiaomi"] = {
                    "api_url": self.config.xiaomi_api_url,
                    "api_key": self.config.xiaomi_api_key,
                    "model": self.config.xiaomi_model,
                }
            consultation = ExpertConsultation(
                providers=providers,
                rag_retriever=self.rag_retriever,
                event_bus=self.event_bus,
                logger=self.logger,
                timeout_seconds=self.config.multi_agent_timeout_seconds,
                temperature=self.config.ai_temperature,
                rag_top_k=self.config.rag_top_k,
            )
            self.logger.info("多智能体会诊模式已启用，providers: %s", list(providers.keys()))
        router = None
        if self.config.router_enabled and consultation is not None:
            router = DecisionRouter(
                familiarity_threshold=self.config.router_familiarity_threshold,
            )
            self.logger.info("决策路由层已启用，阈值: %.2f", self.config.router_familiarity_threshold)
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
            router=router,
            temperature=self.config.ai_temperature,
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
        self._rag_indexer = RagIndexer(
            rag_vector_store=self.rag_vector_store,
            sqlite_store=self.sqlite_store,
            logger=self.logger,
            client_ip=self.client_ip,
            background_tasks=self._background_tasks,
        )
        self._mission_manager = MissionManager(
            config=self.config,
            sqlite_store=self.sqlite_store,
            event_bus=self.event_bus,
            drone_controller=self.drone_controller,
            image_processor=self.image_processor,
            logger=self.logger,
            client_ip=self.client_ip,
            background_tasks=self._background_tasks,
            detect_pests_fn=self._detect_pests,
            rag_index_callback=self._rag_indexer.schedule_mission_rag_index,
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

        execution["simulate_only"] = False
        execution["takeoff_mode"] = self.config.takeoff_mode.strip().lower()

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
        px4_config["prefer_demo_field"] = (
            True if self.config.drone_backend == "px4" else self.config.px4_prefer_demo_field
        )
        px4_config["acceptance_radius_m"] = self.config.px4_acceptance_radius_m
        px4_config["execution_mode"] = self.config.px4_execution_mode
        px4_config["use_existing_mission"] = self.config.px4_use_existing_mission
        px4_config["require_existing_mission"] = self.config.px4_require_existing_mission
        px4_config["existing_mission_total_waypoints"] = self.config.px4_existing_mission_total_waypoints
        px4_config["mission_takeoff_altitude_m"] = self.config.px4_mission_takeoff_altitude_m
        px4_config["mission_takeoff_before_start"] = self.config.px4_mission_takeoff_before_start
        px4_config["mission_takeoff_timeout_seconds"] = self.config.px4_mission_takeoff_timeout_seconds
        px4_config["mission_takeoff_altitude_tolerance_m"] = (
            self.config.px4_mission_takeoff_altitude_tolerance_m
        )
        px4_config["mission_emergency_max_altitude_m"] = (
            self.config.px4_mission_emergency_max_altitude_m
        )

        # DJI OSDK 运行时覆盖
        dji_osdk_config = self.drone_config.setdefault("dji_osdk", {})
        dji_osdk_config["execution_mode"] = self.config.dji_osdk_execution_mode
        dji_osdk_config["serial_port"] = self.config.dji_osdk_serial_port
        dji_osdk_config["baud_rate"] = self.config.dji_osdk_baud_rate
        dji_osdk_config["drone_model"] = self.config.dji_osdk_drone_model

    def configure_embedded_yolo_api(self, detect_url: str) -> None:
        self.yolo_api_url = detect_url
        self.image_processor.api_url = detect_url

    def configure_drone_backend(self, backend: str) -> None:
        normalized = backend.strip().lower()
        from modules.drone.backends import BACKEND_REGISTRY
        if normalized not in BACKEND_REGISTRY:
            raise ValueError(f"未知的无人机后端: {normalized}，可选: {list(BACKEND_REGISTRY.keys())}")
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
            from app.slo import get_slo_metrics
            get_slo_metrics().record_pipeline_start()
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

            # Stage 1: Detection
            detections = await self._detect_pests(request_id, image_path)
            self._sqlite_write(
                request_id,
                "replace_detections",
                lambda: self.sqlite_store.replace_detections(request_id, detections),
            )
            if not detections:
                self._finish_pipeline_no_pests(request_id, image_path, worker_id, started)
                return

            # Check for active missions with the same pest types
            if self._has_active_mission_with_same_pests(request_id, detections, field_context):
                self._finish_pipeline_duplicate_pest(request_id, image_path, worker_id, started, detections)
                return

            # Stage 2: Decision + Compliance
            bundle = await self.decision_engine.generate_decision(
                pest_detections=detections,
                field_context=field_context,
                request_id=request_id,
                client_ip=self.client_ip,
            )
            self._persist_decision(request_id, bundle)
            takeoff_mode = self._check_compliance(request_id, bundle, started)
            if takeoff_mode is None:
                return  # blocked

            # Stage 3: Planning + RAG index
            execution_plan = self._plan_spray_mission(
                field_context=field_context,
                current_weather=bundle["weather"],
                detections=detections,
            )
            self._rag_indexer.schedule_incremental_rag_index(
                request_id=request_id,
                decision=bundle["decision"],
                pest_detections=detections,
                field_context=field_context,
            )

            # Stage 4: Takeoff confirmation (manual mode)
            if takeoff_mode == "manual":
                await self._wait_for_takeoff_confirmation(request_id, execution_plan, bundle["decision"])

            # Stage 5: Execute spray mission
            await self._execute_mission(
                request_id, image_path, worker_id, started,
                detections, bundle, execution_plan, field_context,
            )
        except Exception as exc:
            self._handle_pipeline_error(request_id, image_path, worker_id, started, exc)

    # ── Pipeline Stage Methods ──

    async def _detect_pests(
        self, request_id: str, image_path: Path, *, publish_events: bool = True,
    ) -> list[dict[str, Any]]:
        if publish_events:
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
        if publish_events:
            self.event_bus.publish(
                request_id=request_id,
                stage="yolo",
                status="completed",
                message="YOLO 识别完成",
                payload={"image_path": str(image_path), "detections": detections},
            )
        return detections

    def _finish_pipeline_no_pests(
        self, request_id: str, image_path: Path, worker_id: int, started: float,
    ) -> None:
        from app.slo import get_slo_metrics
        self._sqlite_write(
            request_id,
            "mark_task_finished_no_detections",
            lambda: self.sqlite_store.mark_task_finished(request_id, "completed"),
        )
        get_slo_metrics().record_pipeline_complete()
        self.event_bus.publish(
            request_id=request_id,
            stage="pipeline",
            status="completed",
            message="未发现超过阈值的害虫目标",
            payload={"image_path": str(image_path), "detections": []},
        )
        log_event(
            self.logger, logging.INFO, "未发现超过阈值的害虫目标",
            request_id=request_id, client_ip=self.client_ip,
            duration_ms=(time.perf_counter() - started) * 1000,
            image_path=str(image_path), worker_id=worker_id,
        )

    def _has_active_mission_with_same_pests(
        self,
        request_id: str,
        detections: list[dict[str, Any]],
        field_context: dict[str, Any],
    ) -> bool:
        """Check if there's an active mission targeting the same pest types on the same field."""
        new_pest_types = set()
        for det in detections:
            pt = str(det.get("pest_type") or det.get("label") or "").strip()
            if pt:
                new_pest_types.add(pt)
        if not new_pest_types:
            return False

        field_id = str(field_context.get("field_id") or "").strip()
        active_missions = self.sqlite_store.fetch_active_missions()

        for mission in active_missions:
            if mission.get("original_request_id") == request_id:
                continue
            if field_id and mission.get("field_id") != field_id:
                continue

            mission_pests = mission.get("pest_types", [])
            if isinstance(mission_pests, str):
                import json
                try:
                    mission_pests = json.loads(mission_pests)
                except (json.JSONDecodeError, TypeError):
                    mission_pests = [mission_pests]
            if not isinstance(mission_pests, list):
                mission_pests = []

            mission_pest_set = {str(p).strip() for p in mission_pests if p}
            if new_pest_types & mission_pest_set:
                return True

        return False

    def _finish_pipeline_duplicate_pest(
        self,
        request_id: str,
        image_path: Path,
        worker_id: int,
        started: float,
        detections: list[dict[str, Any]],
    ) -> None:
        """Finish pipeline early because an active mission already handles these pests."""
        from app.slo import get_slo_metrics
        pest_labels = [str(d.get("pest_type") or d.get("label") or "") for d in detections]
        self._sqlite_write(
            request_id,
            "mark_task_finished_duplicate",
            lambda: self.sqlite_store.mark_task_finished(request_id, "completed"),
        )
        get_slo_metrics().record_pipeline_complete()
        self.event_bus.publish(
            request_id=request_id,
            stage="pipeline",
            status="completed",
            message=f"检测到 {', '.join(pest_labels)}，已有相同害虫的任务正在处理，自动跳过",
            payload={"image_path": str(image_path), "detections": detections, "skipped_reason": "duplicate_active_mission"},
        )
        log_event(
            self.logger, logging.INFO, "跳过重复害虫任务",
            request_id=request_id, client_ip=self.client_ip,
            duration_ms=(time.perf_counter() - started) * 1000,
            image_path=str(image_path), worker_id=worker_id,
            pests=pest_labels,
        )

    def _persist_decision(self, request_id: str, bundle: dict[str, Any]) -> None:
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

    def _check_compliance(
        self, request_id: str, bundle: dict[str, Any], started: float,
    ) -> str | None:
        """Check compliance and return takeoff_mode, or None if blocked."""
        from app.slo import get_slo_metrics
        compliance = bundle.get("compliance") or {}
        policy_takeoff = resolve_policy_takeoff_mode(compliance)

        if policy_takeoff == "blocked":
            reasons = compliance.get("blocking_reasons") or []
            message = "农药合规审核未通过，已阻止无人机执行"
            self._sqlite_write(
                request_id,
                "mark_task_finished_compliance_blocked",
                lambda: self.sqlite_store.mark_task_finished(request_id, "blocked"),
            )
            get_slo_metrics().record_pipeline_error()
            self.event_bus.publish(
                request_id=request_id,
                stage="compliance",
                status="blocked",
                message=message,
                payload={"compliance": compliance, "blocking_reasons": reasons},
            )
            log_event(
                self.logger, logging.WARNING, message,
                request_id=request_id, client_ip=self.client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                blocking_reasons=reasons,
            )
            return None

        takeoff_mode, forced_manual, warnings = resolve_runtime_takeoff_mode(
            configured_takeoff_mode=str(
                self.drone_config.get("execution", {}).get("takeoff_mode", "auto")
            ),
            policy_takeoff_mode=policy_takeoff,
            compliance=compliance,
        )
        if forced_manual:
            log_event(
                self.logger, logging.WARNING,
                "合规审核有风险提示，强制进入人工确认流程",
                request_id=request_id, client_ip=self.client_ip,
                warnings=warnings,
            )
        return takeoff_mode

    async def _wait_for_takeoff_confirmation(
        self, request_id: str, execution_plan: dict[str, Any], decision: dict[str, Any],
    ) -> None:
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
                "medication": decision.get("施药方案", {}),
                "current_waypoint_index": 0,
                "position": None,
            },
        )
        self.logger.info("手动模式：等待起飞确认 request_id=%s", request_id)
        await deps.wait_for_takeoff_confirmation()
        deps.clear_takeoff_confirmation_state()
        self.logger.info("手动模式：已确认起飞 request_id=%s", request_id)

    async def _execute_mission(
        self,
        request_id: str, image_path: Path, worker_id: int, started: float,
        detections: list[dict[str, Any]], bundle: dict[str, Any],
        execution_plan: dict[str, Any], field_context: dict[str, Any],
    ) -> None:
        from app.slo import get_slo_metrics
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
        get_slo_metrics().record_pipeline_complete()
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
            self.logger, logging.INFO, "整条处理链执行成功",
            request_id=request_id, client_ip=self.client_ip,
            duration_ms=(time.perf_counter() - started) * 1000,
            image_path=str(image_path), worker_id=worker_id,
            detections=detections, execution_plan=execution_plan,
            mission_result=result,
        )

        # Stage 6: Schedule re-inspection for effectiveness evaluation
        if self.config.evaluation_enabled:
            self._mission_manager.schedule_reinspection(
                request_id, bundle["decision"], detections, field_context, image_path,
                weather=bundle["weather"],
            )

    def _handle_pipeline_error(
        self,
        request_id: str, image_path: Path, worker_id: int,
        started: float, exc: Exception,
    ) -> None:
        from app.slo import get_slo_metrics
        self._sqlite_write(
            request_id,
            "mark_task_finished_error",
            lambda: self.sqlite_store.mark_task_finished(request_id, "error"),
        )
        get_slo_metrics().record_pipeline_error()
        self.event_bus.publish(
            request_id=request_id,
            stage="pipeline",
            status="error",
            message="图片处理链执行失败",
            payload={"image_path": str(image_path), "error": str(exc)},
        )
        log_event(
            self.logger, logging.ERROR, "图片处理链执行失败",
            request_id=request_id, client_ip=self.client_ip,
            duration_ms=(time.perf_counter() - started) * 1000,
            image_path=str(image_path), worker_id=worker_id,
            error=str(exc),
        )

    # ── Delegation to MissionManager and RagIndexer ──

    def _plan_spray_mission(
        self,
        *,
        field_context: dict[str, Any],
        current_weather: dict[str, Any],
        detections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            plan = plan_spray_mission(
                drone_controller=self.drone_controller,
                field_context=field_context,
                current_weather=current_weather,
                detections=detections,
            )
        except Exception:
            self.logger.warning("变量喷洒规划失败，降级为均匀路径", exc_info=True)
            return self.drone_controller.plan_spray_mission(
                field_context=field_context,
                current_weather=current_weather,
            )

        if plan.get("density_grid"):
            self.logger.info(
                "变量喷洒规划完成: %d lanes, %d density cells",
                len(plan.get("spray_schedule", [])),
                len(plan.get("density_grid", [])),
            )
        return plan

    def _sqlite_write(
        self,
        request_id: str,
        operation: str,
        callback: Callable[[], None],
    ) -> None:
        safe_sqlite_write(
            self.logger, request_id, self.client_ip,
            str(self.sqlite_store.db_path), operation, callback,
        )

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
        default="px4",
        help="无人机执行后端: px4（PX4 SITL）| dji_osdk（DJI OSDK，支持 Matrice 系列）",
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
