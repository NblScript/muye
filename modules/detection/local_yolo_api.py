from __future__ import annotations

import ipaddress
import logging
import os
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile

from modules.infra.common import (
    CONFIG_DIR,
    PROJECT_ROOT,
    build_logger,
    generate_request_id,
    load_environment,
    load_yaml,
    log_event,
)


@dataclass(slots=True)
class LocalYoloSettings:
    host: str
    port: int
    model_path: Path
    device: str
    api_key: str
    allowed_ips: list[str]
    rate_limit_per_minute: int
    max_batch_size: int
    model_name: str = ""
    available_models: dict[str, dict[str, Any]] | None = None


class PredictorProtocol(Protocol):
    model_path: Path

    def predict(
        self,
        image_paths: list[Path],
        confidence_threshold: float,
    ) -> list[dict[str, Any]]:
        """对一批图片执行推理，并返回标准化结果。"""


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = max(limit_per_minute, 1)
        self._records: dict[str, deque[float]] = {}

    def check(self, key: str) -> None:
        now = time.time()
        window_start = now - 60
        bucket = self._records.setdefault(key, deque())
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self.limit_per_minute:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        bucket.append(now)


class UltralyticsPredictor:
    def __init__(self, model_path: Path, device: str = "auto") -> None:
        if not model_path.exists():
            raise FileNotFoundError(f"YOLO 模型不存在: {model_path}")

        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - 依赖缺失时在运行期提示
            raise RuntimeError(
                "未安装 ultralytics，请先执行 pip install -r requirements.txt"
            ) from exc

        self.model_path = model_path
        self.device = device
        self._model = YOLO(str(model_path))

    def predict(
        self,
        image_paths: list[Path],
        confidence_threshold: float,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "source": [str(path) for path in image_paths],
            "conf": confidence_threshold,
            "verbose": False,
            "stream": False,
        }
        if self.device and self.device.lower() != "auto":
            kwargs["device"] = self.device

        results = self._model.predict(**kwargs)
        normalized_results: list[dict[str, Any]] = []
        for index, path in enumerate(image_paths):
            result = results[index] if index < len(results) else None
            normalized_results.append(
                {
                    "image": path.name,
                    "detections": self._serialize_detections(result),
                }
            )
        return normalized_results

    def _serialize_detections(self, result: Any) -> list[dict[str, Any]]:
        if result is None or getattr(result, "boxes", None) is None:
            return []

        names = getattr(result, "names", {}) or {}
        orig_shape = getattr(result, "orig_shape", None)
        has_orig_shape = isinstance(orig_shape, (list, tuple)) and len(orig_shape) >= 2
        image_height = int(orig_shape[0]) if has_orig_shape else None
        image_width = int(orig_shape[1]) if has_orig_shape else None
        detections: list[dict[str, Any]] = []
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            detections.append(
                {
                    "pest_type": str(names.get(class_id, class_id)),
                    "confidence": round(confidence, 4),
                    "position": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "coordinate_space": "image_pixel",
                        **({"image_width": image_width} if image_width else {}),
                        **({"image_height": image_height} if image_height else {}),
                    },
                }
            )
        return detections


class LocalYoloApiService:
    def __init__(
        self,
        settings: LocalYoloSettings,
        predictor: PredictorProtocol,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.predictor = predictor
        self.logger = logger or build_logger("muye.yolo_api")
        self.predict_lock = threading.Lock()
        self.rate_limiter = InMemoryRateLimiter(settings.rate_limit_per_minute)

    async def detect(
        self,
        images: list[UploadFile],
        confidence_threshold: float,
        request_id: str,
        client_ip: str,
    ) -> dict[str, Any]:
        if not images:
            raise HTTPException(status_code=400, detail="至少上传一张图片")
        if len(images) > self.settings.max_batch_size:
            raise HTTPException(
                status_code=400,
                detail=f"单次最多上传 {self.settings.max_batch_size} 张图片",
            )

        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="muye_yolo_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            image_paths = await self._persist_uploads(images, temp_dir_path)
            results = self._predict_serialized(image_paths, confidence_threshold)

        duration_ms = (time.perf_counter() - started) * 1000
        payload = {
            "request_id": request_id,
            "model_path": str(self.predictor.model_path),
            "results": results,
        }
        log_event(
            self.logger,
            logging.INFO,
            "本地 YOLO 推理完成",
            request_id=request_id,
            client_ip=client_ip,
            duration_ms=duration_ms,
            batch_size=len(images),
            detections=sum(len(item["detections"]) for item in results),
        )
        return payload

    async def _persist_uploads(self, images: list[UploadFile], temp_dir: Path) -> list[Path]:
        max_file_size = 20 * 1024 * 1024  # 20MB
        saved_paths: list[Path] = []
        for index, upload in enumerate(images, start=1):
            filename = Path(upload.filename or f"image-{index}.jpg").name
            target = temp_dir / filename
            content = upload.file.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"图片 {filename} 内容为空")
            if len(content) > max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"图片 {filename} 超过 20MB 限制",
                )
            target.write_bytes(content)
            saved_paths.append(target)
        return saved_paths

    def _predict_serialized(
        self,
        image_paths: list[Path],
        confidence_threshold: float,
    ) -> list[dict[str, Any]]:
        with self.predict_lock:
            return self.predictor.predict(image_paths, confidence_threshold)

    def reload_model(self, model_name: str) -> dict[str, Any]:
        """切换到指定模型（需要在配置中预定义）。"""
        available = self.settings.available_models
        if not available or model_name not in available:
            raise HTTPException(
                status_code=400,
                detail=f"模型 '{model_name}' 不存在。可用模型: {list(available.keys()) if available else '无'}",
            )

        profile = available[model_name]
        model_path = Path(profile["path"])
        if not model_path.is_absolute():
            model_path = PROJECT_ROOT / model_path

        if not model_path.exists():
            raise HTTPException(status_code=400, detail=f"模型文件不存在: {model_path}")

        device = str(profile.get("device", "auto"))

        with self.predict_lock:
            new_predictor = UltralyticsPredictor(model_path=model_path, device=device)
            self.predictor = new_predictor
            self.settings.model_name = model_name
            self.settings.model_path = model_path
            self.settings.device = device

        self.logger.info("模型已切换: %s -> %s", model_name, model_path)
        return {
            "model_name": model_name,
            "model_path": str(model_path),
            "device": device,
            "description": profile.get("description", ""),
        }

    def ensure_authorized(self, authorization: str | None, x_api_key: str | None) -> None:
        if not self.settings.api_key:
            return
        bearer_token = ""
        if authorization and authorization.lower().startswith("bearer "):
            bearer_token = authorization.split(" ", 1)[1].strip()
        if bearer_token == self.settings.api_key or x_api_key == self.settings.api_key:
            return
        raise HTTPException(status_code=401, detail="YOLO API 鉴权失败")

    def ensure_ip_allowed(self, client_ip: str) -> None:
        if not self.settings.allowed_ips:
            return
        address = ipaddress.ip_address(client_ip)
        for item in self.settings.allowed_ips:
            if not item:
                continue
            try:
                if "/" in item:
                    if address in ipaddress.ip_network(item, strict=False):
                        return
                elif address == ipaddress.ip_address(item):
                    return
            except ValueError as exc:
                raise HTTPException(status_code=500, detail=f"YOLO 白名单配置非法: {item}") from exc
        raise HTTPException(status_code=403, detail=f"客户端 IP {client_ip} 不在白名单中")


def _resolve_model_from_config(config: dict[str, Any]) -> tuple[Path, str, str, dict[str, dict[str, Any]]]:
    """从配置解析模型路径、设备、模型名和可用模型列表。

    优先级：环境变量 > models[active_model] > local_api.model_path（向后兼容）
    """
    local_api = config.get("local_api", {})
    models_section = config.get("models", {})
    active_model = config.get("active_model", "")

    # 环境变量优先
    env_model_path = os.getenv("YOLO_LOCAL_MODEL_PATH")
    env_device = os.getenv("YOLO_LOCAL_DEVICE")

    if models_section and active_model and active_model in models_section:
        # 多模型模式
        profile = models_section[active_model]
        model_path_raw = env_model_path or profile.get("path", "models/best.pt")
        device = env_device or str(profile.get("device", "auto"))
        model_name = active_model
    else:
        # 向后兼容：单模型模式
        model_path_raw = env_model_path or local_api.get("model_path") or "models/best.pt"
        device = env_device or str(local_api.get("device", "auto"))
        model_name = ""

    model_path = Path(model_path_raw)
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path

    return model_path, device, model_name, models_section


def load_local_yolo_settings() -> LocalYoloSettings:
    load_environment()
    config = load_yaml(CONFIG_DIR / "yolo_config.yaml")
    local_api = config.get("local_api", {})

    model_path, device, model_name, available_models = _resolve_model_from_config(config)

    allowed_ips_env = os.getenv("YOLO_ALLOWED_IPS", "")
    if allowed_ips_env.strip():
        allowed_ips = [item.strip() for item in allowed_ips_env.split(",")]
    else:
        allowed_ips = []

    return LocalYoloSettings(
        host=os.getenv("YOLO_LOCAL_HOST", str(local_api.get("host", "127.0.0.1"))),
        port=int(os.getenv("YOLO_LOCAL_PORT", str(local_api.get("port", 8010)))),
        model_path=model_path,
        device=device,
        api_key=os.getenv("YOLO_API_KEY", ""),
        allowed_ips=allowed_ips,
        rate_limit_per_minute=int(os.getenv("YOLO_RATE_LIMIT_PER_MINUTE", "120")),
        max_batch_size=int(local_api.get("max_batch_size", config.get("batch_size", 4))),
        model_name=model_name,
        available_models=available_models or None,
    )


def create_app(
    settings: LocalYoloSettings | None = None,
    predictor: PredictorProtocol | None = None,
    logger: logging.Logger | None = None,
    health_metadata: dict[str, Any] | None = None,
) -> FastAPI:
    active_settings = settings or load_local_yolo_settings()
    active_predictor = predictor or UltralyticsPredictor(
        model_path=active_settings.model_path,
        device=active_settings.device,
    )
    service = LocalYoloApiService(
        settings=active_settings,
        predictor=active_predictor,
        logger=logger,
    )
    app = FastAPI(title="Muye Local YOLO API", version="1.0.0")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "model_path": str(active_predictor.model_path),
            "max_batch_size": active_settings.max_batch_size,
            **(health_metadata or {}),
        }

    @app.post("/detect")
    async def detect(
        request: Request,
        images: list[UploadFile] = File(...),
        confidence_threshold: float = Form(0.25),
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
        x_request_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        request_id = x_request_id or generate_request_id()
        client_ip = request.client.host if request.client else "127.0.0.1"
        service.ensure_authorized(authorization, x_api_key)
        service.ensure_ip_allowed(client_ip)
        service.rate_limiter.check(client_ip)
        return await service.detect(images, confidence_threshold, request_id, client_ip)

    @app.get("/models")
    async def list_models() -> dict[str, Any]:
        available = service.settings.available_models or {}
        models_info: list[dict[str, Any]] = []
        for name, profile in available.items():
            model_path = Path(profile["path"])
            if not model_path.is_absolute():
                model_path = PROJECT_ROOT / model_path
            models_info.append({
                "name": name,
                "path": profile["path"],
                "device": profile.get("device", "auto"),
                "description": profile.get("description", ""),
                "available": model_path.exists(),
                "active": name == service.settings.model_name,
            })
        return {
            "active_model": service.settings.model_name,
            "models": models_info,
        }

    @app.post("/models/switch")
    async def switch_model(request: Request) -> dict[str, Any]:
        body = await request.json()
        model_name = body.get("model_name", "")
        if not model_name:
            raise HTTPException(status_code=400, detail="缺少 model_name 参数")
        return service.reload_model(model_name)

    return app
