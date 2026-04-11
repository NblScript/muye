from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from pathlib import Path

import httpx
import uvicorn

from modules.ai_decision import DecisionEngine
from modules.common import (
    CONFIG_DIR,
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
from modules.drone_controller import DroneController
from modules.event_bus import FileEventBus
from modules.image_processor import ImageProcessor
from modules.local_yolo_api import create_app as create_local_yolo_app
from modules.local_yolo_api import load_local_yolo_settings
from modules.virtual_drone_api import create_virtual_drone_app, load_virtual_drone_settings
from modules.weather_integration import WeatherClient


def _resolve_loopback_host(host: str) -> str:
    if host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    return host


def _build_local_yolo_urls(host: str, port: int) -> tuple[str, str]:
    access_host = _resolve_loopback_host(host)
    detect_url = f"http://{access_host}:{port}/detect"
    health_url = f"http://{access_host}:{port}/health"
    return detect_url, health_url


class EmbeddedYoloApiRunner:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.settings = load_local_yolo_settings()
        self.detect_url, self.health_url = _build_local_yolo_urls(
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
        async with httpx.AsyncClient(timeout=2.0) as client:
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
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.settings = load_virtual_drone_settings()
        access_host = _resolve_loopback_host(self.settings.host)
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
        async with httpx.AsyncClient(timeout=2.0) as client:
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


class MuyeApplication:
    def __init__(self) -> None:
        ensure_runtime_dirs()
        load_environment()
        self.logger = build_logger("muye")
        self.drone_config = load_json(CONFIG_DIR / "drone_config.json")
        self.yolo_config = load_yaml(CONFIG_DIR / "yolo_config.yaml")
        self.event_bus = FileEventBus()
        self.client_ip = os.getenv(
            "SERVICE_CLIENT_IP",
            self.drone_config.get("network", {}).get("client_ip", "127.0.0.1"),
        )

        self.queue: asyncio.Queue[tuple[str, Path]] = asyncio.Queue()
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
        self.decision_engine = DecisionEngine(
            api_url=os.getenv("QWEN_API_URL", ""),
            api_key=os.getenv("QWEN_API_KEY", ""),
            model=os.getenv("QWEN_MODEL", "qwen-max"),
            weather_client=self.weather_client,
            use_mock=os.getenv("QWEN_USE_MOCK", "false").lower() in {"1", "true", "yes", "on"},
            timeout_seconds=30,
            logger=self.logger,
            event_bus=self.event_bus,
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
        )
        self.data_collector = DataCollectorService(
            images_dir=IMAGES_DIR,
            drone_config=self.drone_config,
            on_new_image=self.enqueue_image,
            logger=self.logger,
        )

    def configure_embedded_yolo_api(self, detect_url: str) -> None:
        self.yolo_api_url = detect_url
        self.image_processor.api_url = detect_url

    def configure_embedded_drone_api(self, api_url: str) -> None:
        self.drone_config.setdefault("execution", {})["simulate_only"] = False
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
        self.pending_images.add(key)
        await self.queue.put((request_id, image_path))
        self.event_bus.publish(
            request_id=request_id,
            stage="queue",
            status="queued",
            message="图片已进入处理队列",
            payload={"image_path": str(image_path), "filename": image_path.name},
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

    async def run_forever(self, workers: int) -> None:
        await self.start(workers=workers)
        await asyncio.Event().wait()

    async def run_once(self, workers: int, timeout_seconds: int) -> None:
        await self.start(workers=workers, enable_scheduler=False, capture_on_startup=False)
        await self.data_collector.capture_image()
        await asyncio.wait_for(self.queue.join(), timeout=timeout_seconds)

    async def _worker(self, worker_id: int) -> None:
        while True:
            request_id, image_path = await self.queue.get()
            try:
                await self._process_image(request_id, image_path, worker_id)
            finally:
                self.pending_images.discard(str(image_path.resolve()))
                self.queue.task_done()

    async def _process_image(self, request_id: str, image_path: Path, worker_id: int) -> None:
        started = time.perf_counter()
        try:
            self.event_bus.publish(
                request_id=request_id,
                stage="pipeline",
                status="running",
                message="开始处理图片",
                payload={"image_path": str(image_path), "worker_id": worker_id},
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
            if not detections:
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
                field_context=self.drone_config.get("field", {}),
                request_id=request_id,
                client_ip=self.client_ip,
            )
            result = await self.drone_controller.execute_spray_mission(
                decision=bundle["decision"],
                current_weather=bundle["weather"],
                request_id=request_id,
                client_ip=self.client_ip,
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
                mission_result=result,
            )
        except Exception as exc:
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


async def _async_main(args: argparse.Namespace) -> None:
    app = MuyeApplication()
    embedded_yolo_runner: EmbeddedYoloApiRunner | None = None
    embedded_drone_runner: EmbeddedDroneApiRunner | None = None
    try:
        if args.with_yolo_api or args.with_demo_stack:
            embedded_yolo_runner = EmbeddedYoloApiRunner(logger=app.logger)
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
            await app.run_forever(workers=args.workers)
    finally:
        await app.shutdown()
        if embedded_yolo_runner:
            await embedded_yolo_runner.stop()
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
