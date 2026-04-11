from __future__ import annotations

import asyncio
import base64
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

import httpx
from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from modules.common import generate_request_id, log_event


MINIMAL_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="
)


class CollectorError(RuntimeError):
    """数据采集阶段错误。"""


class _ImageCreatedHandler(FileSystemEventHandler):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[Path], Awaitable[None]],
        logger: logging.Logger,
        client_ip: str,
    ) -> None:
        self.loop = loop
        self.callback = callback
        self.logger = logger
        self.client_ip = client_ip

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            return

        future = asyncio.run_coroutine_threadsafe(
            self._dispatch(path),
            self.loop,
        )

        def _log_failure(task: object) -> None:
            try:
                future.result()
            except Exception as exc:  # pragma: no cover - watchdog 异步线程回调
                log_event(
                    self.logger,
                    logging.ERROR,
                    "新图片事件处理失败",
                    request_id=generate_request_id(),
                    client_ip=self.client_ip,
                    error=str(exc),
                    image_path=str(path),
                )

        future.add_done_callback(_log_failure)

    async def _dispatch(self, path: Path) -> None:
        await self.callback(path)


class DataCollectorService:
    def __init__(
        self,
        images_dir: Path,
        drone_config: dict,
        on_new_image: Callable[[Path], Awaitable[None]],
        logger: logging.Logger,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.images_dir = images_dir
        self.drone_config = drone_config
        self.on_new_image = on_new_image
        self.logger = logger
        self._observer: Observer | None = None
        self._scheduler_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        monitoring = drone_config.get("monitoring", {})
        execution = drone_config.get("execution", {})
        self.capture_interval_hours = float(monitoring.get("capture_interval_hours", 24))
        self.capture_on_startup = bool(monitoring.get("capture_on_startup", True))
        self.simulate_capture = bool(monitoring.get("simulate_capture", True))
        self.capture_endpoint = monitoring.get("capture_endpoint") or None
        self.capture_method = str(monitoring.get("http_method", "GET")).upper()
        self.client_ip = drone_config.get("network", {}).get("client_ip", "127.0.0.1")
        self.timeout = float(execution.get("request_timeout_seconds", 15))
        self._client = httpx.AsyncClient(timeout=self.timeout, transport=transport)

    async def start(
        self,
        *,
        enable_scheduler: bool = True,
        capture_on_startup: bool | None = None,
    ) -> None:
        loop = asyncio.get_running_loop()
        self._start_observer(loop)

        should_capture = self.capture_on_startup if capture_on_startup is None else capture_on_startup
        if should_capture:
            await self.capture_image()

        if enable_scheduler:
            self._scheduler_task = asyncio.create_task(self._schedule_loop())

    async def shutdown(self) -> None:
        self._stop_event.set()
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        if self._observer:
            self._observer.stop()
            await asyncio.to_thread(self._observer.join, 5)
            self._observer = None
        await self._client.aclose()

    async def capture_image(self) -> Path:
        request_id = generate_request_id()
        started = time.perf_counter()
        self.images_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y%m%d-%H%M%S.jpg")
        target = self.images_dir / filename

        try:
            if self.simulate_capture or not self.capture_endpoint:
                # 无真实无人机时生成一张最小 JPEG，便于联调整个链路。
                await asyncio.to_thread(target.write_bytes, MINIMAL_JPEG)
            else:
                if self.capture_method == "POST":
                    response = await self._client.post(self.capture_endpoint)
                else:
                    response = await self._client.get(self.capture_endpoint)
                response.raise_for_status()
                content = response.content
                if not content:
                    raise CollectorError("无人机接口返回空图像内容")
                await asyncio.to_thread(target.write_bytes, content)

            log_event(
                self.logger,
                logging.INFO,
                "无人机图像采集完成",
                request_id=request_id,
                client_ip=self.client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                image_path=str(target),
                simulate=self.simulate_capture or not self.capture_endpoint,
            )
            # 主动回调一次，避免仅依赖文件监听时出现启动阶段竞态。
            await self.on_new_image(target)
            return target
        except Exception as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "无人机图像采集失败",
                request_id=request_id,
                client_ip=self.client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
            )
            raise CollectorError(str(exc)) from exc

    def _start_observer(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._observer:
            return
        handler = _ImageCreatedHandler(loop, self.on_new_image, self.logger, self.client_ip)
        observer = Observer()
        observer.schedule(handler, str(self.images_dir), recursive=False)
        observer.start()
        self._observer = observer

    async def _schedule_loop(self) -> None:
        interval_seconds = max(int(self.capture_interval_hours * 3600), 60)
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                await self.capture_image()
