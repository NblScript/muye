from __future__ import annotations

import io
from pathlib import Path

import pytest


fastapi = pytest.importorskip("fastapi")
from fastapi import HTTPException, UploadFile

from modules.detection.local_yolo_api import LocalYoloApiService, LocalYoloSettings


class FakePredictor:
    def __init__(self) -> None:
        self.model_path = Path("/tmp/fake-best.pt")

    def predict(self, image_paths, confidence_threshold):
        assert len(image_paths) == 1
        assert confidence_threshold == 0.35
        return [
            {
                "image": image_paths[0].name,
                "detections": [
                    {
                        "pest_type": "rice-planthopper",
                        "confidence": 0.91,
                        "position": {"x1": 10.0, "y1": 20.0, "x2": 30.0, "y2": 40.0},
                    }
                ],
            }
        ]


def build_settings() -> LocalYoloSettings:
    return LocalYoloSettings(
        host="127.0.0.1",
        port=8010,
        model_path=Path("/tmp/fake-best.pt"),
        device="auto",
        api_key="token-123",
        allowed_ips=[],
        rate_limit_per_minute=10,
        max_batch_size=4,
    )


@pytest.mark.asyncio
async def test_local_yolo_service_detect_success() -> None:
    service = LocalYoloApiService(settings=build_settings(), predictor=FakePredictor())
    upload = UploadFile(filename="leaf.jpg", file=io.BytesIO(b"fake-image"))

    payload = await service.detect(
        images=[upload],
        confidence_threshold=0.35,
        request_id="req-local-yolo-1",
        client_ip="127.0.0.1",
    )

    assert payload["request_id"] == "req-local-yolo-1"
    assert payload["model_path"] == "/tmp/fake-best.pt"
    assert payload["results"][0]["image"] == "leaf.jpg"
    assert payload["results"][0]["detections"][0]["pest_type"] == "rice-planthopper"


def test_local_yolo_service_rejects_unauthorized_request() -> None:
    service = LocalYoloApiService(settings=build_settings(), predictor=FakePredictor())

    with pytest.raises(HTTPException) as exc_info:
        service.ensure_authorized(authorization=None, x_api_key=None)

    assert exc_info.value.status_code == 401
