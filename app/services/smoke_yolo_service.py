"""Deterministic fake YOLO service used only by the container smoke stack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI

from modules.detection.local_yolo_api import (
    LocalYoloSettings,
    PredictorProtocol,
    create_app,
)


SMOKE_MODEL_PATH = Path("/app/smoke/fake-yolo.pt")


class SmokePredictor(PredictorProtocol):
    """Return one stable normalized aphid box for every input image."""

    model_path = SMOKE_MODEL_PATH

    def predict(
        self,
        image_paths: list[Path],
        confidence_threshold: float,
    ) -> list[dict[str, Any]]:
        detections = [] if confidence_threshold > 0.94 else [
            {
                "pest_type": "aphid",
                "confidence": 0.94,
                "position": {
                    "x1": 0.2,
                    "y1": 0.18,
                    "x2": 0.58,
                    "y2": 0.66,
                    "coordinate_space": "image_normalized",
                },
            }
        ]
        return [
            {
                "image": image_path.name,
                "detections": detections,
            }
            for image_path in image_paths
        ]


def create_smoke_yolo_app() -> FastAPI:
    """Build the explicitly simulated API without loading a model file."""
    settings = LocalYoloSettings(
        host="0.0.0.0",
        port=8010,
        model_path=SMOKE_MODEL_PATH,
        device="fake",
        api_key="",
        allowed_ips=[],
        rate_limit_per_minute=600,
        max_batch_size=4,
        model_name="container-smoke-fake",
    )
    return create_app(
        settings=settings,
        predictor=SmokePredictor(),
        health_metadata={
            "mode": "smoke_fake",
            "is_simulated": True,
            "warning": "deterministic fake detections; never use for production",
        },
    )
