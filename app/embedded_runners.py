"""Embedded API runners for in-process YOLO API."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI

from modules.infra.common import generate_request_id, log_event


class EmbeddedApiRunner(ABC):
    """Abstract base class for embedded API runners."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.settings = self._load_settings()
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task[None] | None = None

    @abstractmethod
    def _load_settings(self) -> Any:
        ...

    @abstractmethod
    def _create_app(self) -> FastAPI:
        ...

    @abstractmethod
    def _get_health_url(self) -> str:
        ...

    @abstractmethod
    def _get_startup_message(self) -> str:
        ...

    @abstractmethod
    def _get_startup_error_prefix(self) -> str:
        ...

    @abstractmethod
    def _get_log_extra(self) -> dict[str, Any]:
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
        from modules.detection.local_yolo_api import load_local_yolo_settings
        return load_local_yolo_settings()

    def _create_app(self) -> FastAPI:
        from modules.detection.local_yolo_api import create_app as create_local_yolo_app
        return create_local_yolo_app(settings=self.settings, logger=self.logger)

    def _get_health_url(self) -> str:
        from app.config import build_local_yolo_urls
        _, health_url = build_local_yolo_urls(self.settings.host, self.settings.port)
        return health_url

    def _get_startup_message(self) -> str:
        return "内嵌 YOLO API 已启动"

    def _get_startup_error_prefix(self) -> str:
        return "内嵌 YOLO API"

    def _get_log_extra(self) -> dict[str, Any]:
        from app.config import build_local_yolo_urls
        detect_url, health_url = build_local_yolo_urls(self.settings.host, self.settings.port)
        return {"detect_url": detect_url, "health_url": health_url}

    @property
    def detect_url(self) -> str:
        from app.config import build_local_yolo_urls
        detect_url, _ = build_local_yolo_urls(self.settings.host, self.settings.port)
        return detect_url

    @property
    def health_url(self) -> str:
        from app.config import build_local_yolo_urls
        _, health_url = build_local_yolo_urls(self.settings.host, self.settings.port)
        return health_url
