from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx

from modules.common import chunked, log_event


class ImageProcessingError(RuntimeError):
    """YOLO 图像处理阶段错误。"""


class ImageProcessor:
    def __init__(
        self,
        api_url: str,
        confidence_threshold: float = 0.25,
        timeout_seconds: float = 20,
        batch_size: int = 4,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        logger: logging.Logger | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = api_url
        self.confidence_threshold = confidence_threshold
        self.batch_size = max(batch_size, 1)
        self.headers = headers or {}
        self.api_key = api_key or ""
        self.logger = logger or logging.getLogger("muye.image")
        self._client = httpx.AsyncClient(timeout=timeout_seconds, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def detect_pests(
        self,
        image_path: str | Path,
        request_id: str,
        client_ip: str = "127.0.0.1",
    ) -> list[dict[str, Any]]:
        batch_result = await self.detect_pests_batch([image_path], request_id, client_ip)
        key = str(Path(image_path))
        return batch_result.get(key, [])

    async def detect_pests_batch(
        self,
        image_paths: list[str | Path],
        request_id: str,
        client_ip: str = "127.0.0.1",
    ) -> dict[str, list[dict[str, Any]]]:
        targets = [Path(path) for path in image_paths]
        results: dict[str, list[dict[str, Any]]] = {str(path): [] for path in targets}

        for batch in chunked(targets, self.batch_size):
            batch_result = await self._submit_batch(batch, request_id, client_ip)
            results.update(batch_result)
        return results

    async def _submit_batch(
        self,
        batch: list[Path],
        request_id: str,
        client_ip: str,
    ) -> dict[str, list[dict[str, Any]]]:
        started = time.perf_counter()
        try:
            # 单批次图片数量受 batch_size 限制，直接读取能避免测试环境中的线程池挂起问题。
            contents = [path.read_bytes() for path in batch]
            files = [
                (
                    "images",
                    (
                        path.name,
                        content,
                        "image/jpeg",
                    ),
                )
                for path, content in zip(batch, contents, strict=True)
            ]

            headers = {"Accept": "application/json", **self.headers}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-Request-ID"] = request_id
            headers["X-Client-IP"] = client_ip

            response = await self._client.post(
                self.api_url,
                files=files,
                data={
                    "confidence_threshold": str(self.confidence_threshold),
                    "batch_hint": str(len(batch)),
                },
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            normalized = self._normalize_payload(payload, batch)
            log_event(
                self.logger,
                logging.INFO,
                "YOLO 检测完成",
                request_id=request_id,
                client_ip=client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                batch_size=len(batch),
                detections=sum(len(item) for item in normalized.values()),
            )
            return normalized
        except Exception as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "YOLO 检测失败",
                request_id=request_id,
                client_ip=client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
                batch=[str(path) for path in batch],
            )
            raise ImageProcessingError(str(exc)) from exc

    def _normalize_payload(
        self,
        payload: Any,
        batch: list[Path],
    ) -> dict[str, list[dict[str, Any]]]:
        if isinstance(payload, dict) and "results" in payload:
            raw_results = payload["results"]
        elif isinstance(payload, list):
            raw_results = payload
        elif isinstance(payload, dict) and "detections" in payload:
            raw_results = [{"image": batch[0].name, "detections": payload["detections"]}]
        else:
            raise ImageProcessingError("YOLO 返回结构不合法，缺少 results 或 detections")

        normalized: dict[str, list[dict[str, Any]]] = {str(path): [] for path in batch}
        for index, item in enumerate(raw_results):
            image_path = self._resolve_image_key(item, batch, index)
            detections = item.get("detections", [])
            normalized[str(image_path)] = self._validate_detections(detections)
        return normalized

    def _resolve_image_key(self, item: dict[str, Any], batch: list[Path], index: int) -> Path:
        image_name = item.get("image") or item.get("filename") or item.get("image_path")
        if image_name:
            for path in batch:
                if path.name == Path(image_name).name or str(path) == image_name:
                    return path
        if index >= len(batch):
            raise ImageProcessingError("YOLO 批处理结果数量超过输入图片数量")
        return batch[index]

    def _validate_detections(self, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for detection in detections:
            pest_type = (
                detection.get("pest_type")
                or detection.get("label")
                or detection.get("class_name")
                or detection.get("name")
            )
            confidence_raw = detection.get("confidence", detection.get("score", detection.get("conf")))
            position_raw = detection.get("position", detection.get("bbox", detection.get("box")))

            if pest_type is None or confidence_raw is None or position_raw is None:
                raise ImageProcessingError("YOLO 检测结果缺少 pest_type/confidence/position")

            confidence = float(confidence_raw)
            if confidence < self.confidence_threshold:
                continue

            normalized.append(
                {
                    "pest_type": str(pest_type),
                    "confidence": round(confidence, 4),
                    "position": self._normalize_position(position_raw),
                }
            )
        return normalized

    def _normalize_position(self, position: dict[str, Any]) -> dict[str, float]:
        if {"x1", "y1", "x2", "y2"}.issubset(position):
            return {
                "x1": float(position["x1"]),
                "y1": float(position["y1"]),
                "x2": float(position["x2"]),
                "y2": float(position["y2"]),
            }

        if {"x", "y", "w", "h"}.issubset(position):
            x = float(position["x"])
            y = float(position["y"])
            width = float(position["w"])
            height = float(position["h"])
            return {
                "x1": x,
                "y1": y,
                "x2": x + width,
                "y2": y + height,
            }

        raise ImageProcessingError("YOLO 检测框格式不合法")
