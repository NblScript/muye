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
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import uvicorn
from fastapi import FastAPI

from modules.ai_decision import DecisionEngine
from modules.common import (
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
from modules.data_collector import DataCollectorService
from modules.decision_context import SqliteDecisionContextProvider
from modules.drone_controller import DroneController
from modules.event_bus import FileEventBus
from modules.image_processor import ImageProcessor
from modules.local_yolo_api import create_app as create_local_yolo_app
from modules.local_yolo_api import load_local_yolo_settings
from modules.rag import (
    COLLECTION_PESTICIDES,
    DecisionRAGRetriever,
    QwenEmbeddings,
    VectorStoreManager,
    load_pesticide_from_json,
    load_pesticide_from_sqlite,
)
from modules.sqlite_store import SqliteStore
from modules.virtual_drone_api import create_virtual_drone_app, load_virtual_drone_settings
from modules.weather_integration import WeatherClient

# Import route registration functions
from routes.dashboard import register_dashboard_routes
from routes.demo import register_demo_routes
from routes.health import register_health_routes
from routes.sim import register_sim_routes
from routes.tasks import register_tasks_routes
from routes.workflow import register_workflow_routes

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
from services.map_simulator import Px4MapStateSimulator
from services.workflow_service import (
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
from core.config import build_local_yolo_urls, parse_env_bool, resolve_loopback_host
from core.deps import embedded_yolo_runner_for_health

# Re-export for backward compatibility with tests
# These are internal functions that tests monkeypatch
def _load_sqlite_task_views(*args, **kwargs):
    return load_sqlite_task_views(*args, **kwargs)

def _count_sqlite_tasks(*args, **kwargs):
    return count_sqlite_tasks(*args, **kwargs)

def _load_task_by_request_id(*args, **kwargs):
    return load_task_by_request_id(*args, **kwargs)

def _build_history_response(*args, **kwargs):
    return build_history_response(*args, **kwargs)

def _clear_demo_runtime_state():
    return clear_demo_runtime_state()

_build_local_yolo_urls = build_local_yolo_urls
_resolve_loopback_host = resolve_loopback_host

# Re-export from modules for test monkeypatching
from modules.common import DATA_DIR, IMAGES_DIR, ensure_runtime_dirs, load_environment
from modules.event_bus import FileEventBus, build_task_views, load_events

# Re-export health check functions for test monkeypatching
from routes.health import check_data_dir_health, check_embedded_yolo_health, check_sqlite_health, collect_health_status

_check_sqlite_health = check_sqlite_health
_check_data_dir_health = check_data_dir_health
_check_embedded_yolo_health = check_embedded_yolo_health
_collect_health_status = collect_health_status

# Import annotation function for tests
from routes.tasks import annotate_image, get_task_annotated_image, get_task_original_image
from routes.sim import register_sim_routes, get_sim_map_state
from routes.workflow import get_workflow_history, get_workflow_state
from routes.demo import upload_demo_image, reset_demo_events, MAX_UPLOAD_BYTES as DEMO_MAX_UPLOAD_BYTES
from routes.health import api_health
from routes.dashboard import get_dashboard_context

_annotate_image = annotate_image
MAX_UPLOAD_BYTES = DEMO_MAX_UPLOAD_BYTES

# For test monkeypatching of _save_uploaded_image
from services.workflow_service import sanitize_filename
from modules.common import IMAGES_DIR, ensure_runtime_dirs
import time as _time_module

def _save_uploaded_image(file, content: bytes):
    """Save uploaded image for test monkeypatching."""
    ensure_runtime_dirs()
    timestamp = _time_module.strftime("%Y%m%d-%H%M%S", _time_module.localtime())
    filename = sanitize_filename(file.filename)
    target = IMAGES_DIR / f"{timestamp}-{filename}"
    target.write_bytes(content)
    return target


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
register_tasks_routes(api_app)
register_sim_routes(api_app, simulator)


# ============================================================================
# Embedded API Runners
# ============================================================================

class EmbeddedYoloApiRunner:
    """Runner for embedded YOLO API server."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.settings = load_local_yolo_settings()
        self.detect_url, self.health_url = build_local_yolo_urls(
            self.settings.host,
            self.settings.port,
        )
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        started = time.perf_counter()
        request_id = generate_request_id()
        app = create_local_yolo_app(settings=self.settings, logger=self.logger)
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
                "内嵌 YOLO API 已启动",
                request_id=request_id,
                duration_ms=(time.perf_counter() - started) * 1000,
                detect_url=self.detect_url,
                health_url=self.health_url,
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
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            while time.monotonic() < deadline:
                if self.server_task and self.server_task.done():
                    error = self.server_task.exception()
                    if error:
                        raise RuntimeError(f"内嵌 YOLO API 启动失败: {error}") from error
                    raise RuntimeError("内嵌 YOLO API 意外退出")
                try:
                    response = await client.get(self.health_url)
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(interval_seconds)
        raise TimeoutError(f"等待 YOLO API 就绪超时: {self.health_url}")


class EmbeddedDroneApiRunner:
    """Runner for embedded virtual drone API server."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.settings = load_virtual_drone_settings()
        access_host = resolve_loopback_host(self.settings.host)
        self.api_url = f"http://{access_host}:{self.settings.port}/missions"
        self.health_url = f"http://{access_host}:{self.settings.port}/health"
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        started = time.perf_counter()
        request_id = generate_request_id()
        app = create_virtual_drone_app(settings=self.settings, logger=self.logger)
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
                "内嵌虚拟无人机 API 已启动",
                request_id=request_id,
                duration_ms=(time.perf_counter() - started) * 1000,
                api_url=self.api_url,
                health_url=self.health_url,
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
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            while time.monotonic() < deadline:
                if self.server_task and self.server_task.done():
                    error = self.server_task.exception()
                    if error:
                        raise RuntimeError(f"内嵌虚拟无人机 API 启动失败: {error}") from error
                    raise RuntimeError("内嵌虚拟无人机 API 意外退出")
                try:
                    response = await client.get(self.health_url)
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(interval_seconds)
        raise TimeoutError(f"等待虚拟无人机 API 就绪超时: {self.health_url}")


# ============================================================================
# Main Application Class
# ============================================================================

class MuyeApplication:
    """Main application class for the Muye agricultural pest control system."""

    def __init__(self) -> None:
        ensure_runtime_dirs()
        load_environment()
        self.logger = build_logger("muye")
        self.drone_config = load_json(CONFIG_DIR / "drone_config.json")
        self._apply_runtime_drone_overrides()
        self.yolo_config = load_yaml(CONFIG_DIR / "yolo_config.yaml")
        self.event_bus = FileEventBus()
        self.client_ip = os.getenv(
            "SERVICE_CLIENT_IP",
            self.drone_config.get("network", {}).get("client_ip", "127.0.0.1"),
        )
        sqlite_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
        self.sqlite_store = SqliteStore(sqlite_path, logger=self.logger)
        self.rag_embeddings: QwenEmbeddings | None = None
        self.rag_vector_store: VectorStoreManager | None = None
        self.rag_retriever: DecisionRAGRetriever | None = None

        self.queue: asyncio.Queue[tuple[str, Path, dict[str, Any]]] = asyncio.Queue()
        self.pending_images: set[str] = set()
        self.worker_tasks: list[asyncio.Task[None]] = []

        self.yolo_api_url = os.getenv("YOLO_API_URL", "http://127.0.0.1:8010/detect")
        self.image_processor = ImageProcessor(
            api_url=self.yolo_api_url,
            api_key=os.getenv("YOLO_API_KEY", ""),
            confidence_threshold=float(
                os.getenv(
                    "YOLO_CONFIDENCE_THRESHOLD",
                    self.yolo_config.get("confidence_threshold", 0.25),
                )
            ),
            timeout_seconds=float(self.yolo_config.get("timeout_seconds", 20)),
            batch_size=int(self.yolo_config.get("batch_size", 4)),
            headers=self.yolo_config.get("request_headers", {}),
            logger=self.logger,
        )
        self.weather_client = WeatherClient(
            geo_api_url=os.getenv(
                "QWEATHER_GEO_URL",
                "https://geoapi.qweather.com/v2/city/lookup",
            ),
            weather_api_url=os.getenv(
                "QWEATHER_WEATHER_URL",
                "https://devapi.qweather.com/v7/weather/now",
            ),
            api_key=os.getenv("QWEATHER_API_KEY", ""),
            use_mock=os.getenv("QWEATHER_USE_MOCK", "false").lower() in {"1", "true", "yes", "on"},
            mock_weather={
                "temperature": os.getenv("QWEATHER_MOCK_TEMPERATURE", "26"),
                "humidity": os.getenv("QWEATHER_MOCK_HUMIDITY", "58"),
                "summary": os.getenv("QWEATHER_MOCK_SUMMARY", "多云"),
                "wind_direction": os.getenv("QWEATHER_MOCK_WIND_DIRECTION", "东南风"),
                "wind_scale_text": os.getenv("QWEATHER_MOCK_WIND_SCALE", "2"),
                "wind_speed": os.getenv("QWEATHER_MOCK_WIND_SPEED", "3.3"),
            },
            timeout_seconds=float(
                self.drone_config.get("execution", {}).get("request_timeout_seconds", 15)
            ),
            logger=self.logger,
        )
        decision_context_provider = None
        if os.getenv("MUYE_ENABLE_SQLITE_DECISION_CONTEXT", "false").lower() in {"1", "true", "yes", "on"}:
            decision_context_provider = SqliteDecisionContextProvider(self.sqlite_store)
        self.rag_retriever = self._initialize_rag()
        self.decision_engine = DecisionEngine(
            api_url=os.getenv("QWEN_API_URL", ""),
            api_key=os.getenv("QWEN_API_KEY", ""),
            model=os.getenv("QWEN_MODEL", "qwen-max"),
            weather_client=self.weather_client,
            use_mock=os.getenv("QWEN_USE_MOCK", "false").lower() in {"1", "true", "yes", "on"},
            timeout_seconds=30,
            logger=self.logger,
            event_bus=self.event_bus,
            decision_context_provider=decision_context_provider,
            rag_retriever=self.rag_retriever,
        )
        self.drone_controller = DroneController(
            drone_config=self.drone_config,
            api_url=os.getenv("DRONE_API_URL", ""),
            api_key=os.getenv("DRONE_API_KEY", ""),
            timeout_seconds=float(
                self.drone_config.get("execution", {}).get("request_timeout_seconds", 15)
            ),
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
        if not parse_env_bool(os.getenv("RAG_ENABLED"), True):
            self.logger.info("RAG 初始化已禁用: RAG_ENABLED=false")
            return None

        try:
            self.rag_embeddings = QwenEmbeddings(
                api_url=os.getenv(
                    "QWEN_EMBEDDING_API_URL",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ),
                api_key=os.getenv("QWEN_API_KEY"),
                model=os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v3"),
                dimensions=int(os.getenv("QWEN_EMBEDDING_DIMENSIONS", "1024")),
                timeout=float(os.getenv("QWEN_EMBEDDING_TIMEOUT_SECONDS", "60")),
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

        backend = os.getenv("DRONE_BACKEND")
        if backend:
            execution["backend"] = backend.strip().lower()

        if execution.get("backend") == "simulated":
            execution["simulate_only"] = True
        elif execution.get("backend") in {"remote_api", "px4"}:
            execution["simulate_only"] = False

        if os.getenv("PX4_SYSTEM_ADDRESS"):
            px4_config["system_address"] = os.getenv("PX4_SYSTEM_ADDRESS")
        if os.getenv("PX4_CONNECT_TIMEOUT_SECONDS"):
            px4_config["connect_timeout_seconds"] = float(os.getenv("PX4_CONNECT_TIMEOUT_SECONDS", "30"))
        if os.getenv("PX4_MISSION_TIMEOUT_SECONDS"):
            px4_config["mission_timeout_seconds"] = float(os.getenv("PX4_MISSION_TIMEOUT_SECONDS", "180"))

        px4_config["auto_arm"] = parse_env_bool(
            os.getenv("PX4_AUTO_ARM"),
            bool(px4_config.get("auto_arm", True)),
        )
        px4_config["auto_start_mission"] = parse_env_bool(
            os.getenv("PX4_AUTO_START_MISSION"),
            bool(px4_config.get("auto_start_mission", True)),
        )
        px4_config["return_to_launch_after_mission"] = parse_env_bool(
            os.getenv("PX4_RETURN_TO_LAUNCH_AFTER_MISSION"),
            bool(px4_config.get("return_to_launch_after_mission", True)),
        )
        px4_config["require_global_position"] = parse_env_bool(
            os.getenv("PX4_REQUIRE_GLOBAL_POSITION"),
            bool(px4_config.get("require_global_position", True)),
        )
        px4_config["prefer_demo_field"] = parse_env_bool(
            os.getenv("PX4_USE_SITL_DEMO_FIELD"),
            bool(px4_config.get("prefer_demo_field", False)),
        )
        if os.getenv("PX4_ACCEPTANCE_RADIUS_M"):
            px4_config["acceptance_radius_m"] = float(os.getenv("PX4_ACCEPTANCE_RADIUS_M", "2.0"))

    def configure_embedded_yolo_api(self, detect_url: str) -> None:
        self.yolo_api_url = detect_url
        self.image_processor.api_url = detect_url

    def configure_drone_backend(self, backend: str) -> None:
        normalized = backend.strip().lower()
        self.drone_config.setdefault("execution", {})["backend"] = normalized
        self.drone_config["execution"]["simulate_only"] = normalized == "simulated"

    def configure_embedded_drone_api(self, api_url: str) -> None:
        self.configure_drone_backend("remote_api")
        self.drone_controller.api_url = api_url

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
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
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
            field_context = self._resolve_runtime_field_context()
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
            result = await self.drone_controller.execute_spray_mission(
                decision=bundle["decision"],
                current_weather=bundle["weather"],
                request_id=request_id,
                client_ip=self.client_ip,
                execution_plan=execution_plan,
                field_context=field_context,
            )
            spray_record = self._build_spray_record(
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

    def _resolve_runtime_field_context(self) -> dict[str, Any]:
        if self._should_use_px4_demo_field():
            return self._build_px4_demo_field_context()

        configured_field_id = str(self.drone_config.get("field", {}).get("field_id") or "").strip() or None
        env_field_id = os.getenv("MUYE_ACTIVE_FIELD_ID")
        preferred_field_id = env_field_id or configured_field_id
        field_count_row = self.sqlite_store.fetch_one("SELECT COUNT(*) AS total FROM fields")
        field_count = int(field_count_row["total"]) if field_count_row else 0
        if preferred_field_id:
            field_context = self.sqlite_store.fetch_field_context(field_id=preferred_field_id)
            if field_context:
                if env_field_id or not self._should_ignore_config_fallback_field(preferred_field_id):
                    return field_context
            elif env_field_id or field_count > 0:
                raise RuntimeError(f"指定地块不存在: {preferred_field_id}")
        real_field_context = self._resolve_non_fallback_field_context()
        if real_field_context:
            return real_field_context
        field_context = self.sqlite_store.fetch_field_context()
        if field_context:
            return field_context
        return self._build_config_field_context()

    def _should_use_px4_demo_field(self) -> bool:
        execution = self.drone_config.get("execution", {})
        px4_config = self.drone_config.get("px4", {})
        return execution.get("backend") == "px4" and bool(px4_config.get("prefer_demo_field", False))

    def _build_px4_demo_field_context(self) -> dict[str, Any]:
        px4_config = self.drone_config.get("px4", {})
        demo_field = px4_config.get("demo_field") or {}
        location = demo_field.get("location", {})
        geofence = demo_field.get("geofence", [])
        if len(geofence) < 3:
            raise RuntimeError("PX4 SITL 演示地块缺少有效 geofence 配置")
        field_context = {
            "field_id": demo_field.get("field_id", "px4-sitl-demo"),
            "name": demo_field.get("name", "PX4 SITL 演示地块"),
            "weather_location": demo_field.get("weather_location") or location.get("city") or "Zurich",
            "area_mu": demo_field.get("area_mu", 1.0),
            "soil_type": demo_field.get("soil_type", "demo"),
            "geofence": geofence,
            "explicit_route": demo_field.get("explicit_route"),
            "presentation_profile": demo_field.get("presentation_profile"),
            "location": {
                "province": location.get("province"),
                "city": location.get("city"),
                "county": location.get("county"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
            "crop_cycle": demo_field.get("crop_cycle"),
        }
        self._seed_field_context(
            field_context,
            source="px4_sitl_demo",
            notes="Auto-seeded from config/drone_config.json PX4 SITL demo field.",
        )
        return field_context

    def _build_config_field_context(self) -> dict[str, Any]:
        field = self.drone_config.get("field", {})
        location = field.get("location", {})
        field_context = {
            "field_id": field.get("field_id"),
            "name": field.get("name", "默认示范田"),
            "weather_location": field.get("weather_location") or location.get("city"),
            "area_mu": field.get("area_mu"),
            "soil_type": field.get("soil_type"),
            "geofence": field.get("geofence", []),
            "location": {
                "province": location.get("province"),
                "city": location.get("city"),
                "county": location.get("county"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
            "crop_cycle": None,
        }
        self._seed_field_context(
            field_context,
            source="drone_config_fallback",
            notes="Auto-seeded from config/drone_config.json fallback context.",
            skip_if_any_field_exists=True,
        )
        return field_context

    def _seed_field_context(
        self,
        field_context: dict[str, Any],
        *,
        source: str,
        notes: str,
        skip_if_any_field_exists: bool = False,
    ) -> None:
        field_id = str(field_context.get("field_id") or "").strip()
        if not field_id:
            return
        location = field_context.get("location", {})
        existing_field = self.sqlite_store.fetch_one(
            """
            SELECT field_id
            FROM fields
            WHERE field_id = ?
            """,
            (field_id,),
        )
        if existing_field is not None:
            return
        if skip_if_any_field_exists:
            field_count_row = self.sqlite_store.fetch_one("SELECT COUNT(*) AS total FROM fields")
            field_count = int(field_count_row["total"]) if field_count_row else 0
            if field_count > 0:
                return
        try:
            self.sqlite_store.upsert_field(
                {
                    "field_id": field_id,
                    "field_code": field_id.upper(),
                    "field_name": field_context.get("name") or field_id,
                    "province": location.get("province"),
                    "city": location.get("city"),
                    "county": location.get("county"),
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "area_mu": field_context.get("area_mu"),
                    "geofence": field_context.get("geofence"),
                    "soil_type": field_context.get("soil_type"),
                    "source": source,
                    "notes": notes,
                }
            )
        except Exception as exc:
            log_event(
                self.logger,
                logging.WARNING,
                "配置地块回写 SQLite 失败",
                client_ip=self.client_ip,
                sqlite_path=str(self.sqlite_store.db_path),
                field_id=field_id,
                error=str(exc),
            )

    def _build_spray_record(
        self,
        *,
        request_id: str,
        field_context: dict[str, Any],
        decision: dict[str, Any],
        weather: dict[str, Any],
        execution_plan: dict[str, Any],
        mission_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        field_id = str(field_context.get("field_id") or "").strip()
        if not field_id:
            return None

        medication = decision.get("用药") or {}
        crop_cycle = field_context.get("crop_cycle") or {}
        crop_cycle_id = crop_cycle.get("id")
        pesticide_name = str(medication.get("农药名称") or "").strip()
        pesticide_row = None
        if pesticide_name:
            pesticide_row = self.sqlite_store.fetch_one(
                """
                SELECT pesticide_id
                FROM pesticide_catalog
                WHERE product_name = ?
                ORDER BY pesticide_id ASC
                LIMIT 1
                """,
                (pesticide_name,),
            )

        total_dosage = self._parse_total_dosage_liters(medication.get("总量"))
        spray_area_mu = self._extract_numeric_value(field_context.get("area_mu"))
        dosage_per_mu = None
        if total_dosage is not None and spray_area_mu and spray_area_mu > 0:
            dosage_per_mu = round(total_dosage / spray_area_mu, 4)

        notes_parts = []
        if pesticide_name:
            notes_parts.append(f"农药名称={pesticide_name}")
        if medication.get("浓度"):
            notes_parts.append(f"浓度={medication['浓度']}")
        if medication.get("安全提示"):
            notes_parts.append(
                "安全提示=" + "；".join(str(item) for item in medication.get("安全提示", []))
            )
        if decision.get("农事建议"):
            notes_parts.append(
                "农事建议=" + "；".join(str(item) for item in decision.get("农事建议", []))
            )

        return {
            "request_id": request_id,
            "field_id": field_id,
            "crop_cycle_id": crop_cycle_id,
            "drone_task_id": mission_result.get("task_id") or mission_result.get("mission_id"),
            "pesticide_id": pesticide_row["pesticide_id"] if pesticide_row else None,
            "spray_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "spray_area_mu": spray_area_mu,
            "dosage_per_mu": dosage_per_mu,
            "total_dosage": total_dosage,
            "dilution_ratio": medication.get("配比"),
            "spray_rate_lpm": execution_plan.get("喷洒速率"),
            "flight_height_m": execution_plan.get("高度"),
            "flight_speed_mps": execution_plan.get("速度"),
            "weather_snapshot": weather,
            "result_status": self._normalize_spray_result_status(mission_result),
            "source": "main_pipeline",
            "notes": " | ".join(notes_parts) if notes_parts else None,
        }

    def _should_ignore_config_fallback_field(self, field_id: str) -> bool:
        row = self.sqlite_store.fetch_one(
            """
            SELECT source
            FROM fields
            WHERE field_id = ?
            """,
            (field_id,),
        )
        if row is None or row.get("source") != "drone_config_fallback":
            return False
        non_fallback_row = self.sqlite_store.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM fields
            WHERE source IS NULL OR source != 'drone_config_fallback'
            """
        )
        non_fallback_count = int(non_fallback_row["total"]) if non_fallback_row else 0
        return non_fallback_count > 0

    def _resolve_non_fallback_field_context(self) -> dict[str, Any] | None:
        non_fallback_row = self.sqlite_store.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM fields
            WHERE source IS NULL OR source != 'drone_config_fallback'
            """
        )
        non_fallback_count = int(non_fallback_row["total"]) if non_fallback_row else 0
        if non_fallback_count == 0:
            return None
        if non_fallback_count > 1:
            raise RuntimeError("检测到多个地块，请显式设置 MUYE_ACTIVE_FIELD_ID")
        selected = self.sqlite_store.fetch_one(
            """
            SELECT field_id
            FROM fields
            WHERE source IS NULL OR source != 'drone_config_fallback'
            ORDER BY city ASC, field_name ASC
            LIMIT 1
            """
        )
        if selected is None:
            return None
        return self.sqlite_store.fetch_field_context(field_id=str(selected["field_id"]))

    def _normalize_spray_result_status(self, mission_result: dict[str, Any]) -> str:
        status = str(
            mission_result.get("final_status")
            or mission_result.get("last_known_status")
            or mission_result.get("status")
            or "planned"
        ).strip().lower()
        if status in {"completed", "simulated"}:
            return "completed"
        if status in {"failed", "error"}:
            return "failed"
        if status in {"cancelled", "canceled"}:
            return "cancelled"
        if status in {
            "takeoff",
            "enroute",
            "spraying",
            "returning",
            "running",
            "in_progress",
            "processing",
        }:
            return "in_progress"
        return "planned"

    def _extract_numeric_value(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if not match:
            return None
        return float(match.group(0))

    def _parse_total_dosage_liters(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text:
            return None

        normalized = text.replace(" ", "")
        unit_match = re.search(r"(-?\d+(?:\.\d+)?)(mL|ml|ML|毫升|L|l|升)", normalized)
        if unit_match:
            amount = float(unit_match.group(1))
            unit = unit_match.group(2).lower()
            if unit in {"ml", "毫升"}:
                return round(amount / 1000, 6)
            return amount

        return self._extract_numeric_value(text)

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
    import core.deps as deps
    
    app = MuyeApplication()
    embedded_yolo_runner: EmbeddedYoloApiRunner | None = None
    embedded_drone_runner: EmbeddedDroneApiRunner | None = None
    try:
        if args.drone_backend:
            app.configure_drone_backend(args.drone_backend)

        if args.with_yolo_api or args.with_demo_stack:
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

        if args.with_virtual_drone_api or args.with_demo_stack:
            embedded_drone_runner = EmbeddedDroneApiRunner(logger=app.logger)
            app.configure_embedded_drone_api(embedded_drone_runner.api_url)
            await embedded_drone_runner.start()
            app.logger.info(
                "演示模式已接管虚拟无人机 API 地址: %s",
                embedded_drone_runner.api_url,
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
        if embedded_drone_runner:
            await embedded_drone_runner.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="牧野智能农业害虫防治系统")
    parser.add_argument("--once", action="store_true", help="执行一次采集与处理流程后退出")
    parser.add_argument(
        "--with-yolo-api",
        action="store_true",
        help="在主进程内一并启动本地 YOLO API，再启动农业防治主系统",
    )
    parser.add_argument(
        "--with-virtual-drone-api",
        action="store_true",
        help="在主进程内一并启动虚拟无人机 API，并接管无人机任务执行",
    )
    parser.add_argument(
        "--with-demo-stack",
        action="store_true",
        help="一键启动本地 YOLO API、虚拟无人机 API 和农业防治主系统",
    )
    parser.add_argument(
        "--drone-backend",
        choices=["simulated", "remote_api", "px4"],
        help="覆盖无人机执行后端，可选 simulated、remote_api、px4",
    )
    parser.add_argument(
        "--no-capture-on-startup",
        action="store_true",
        help="启动后不立即自动采图，适合由外部脚本投喂指定演示图片",
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
