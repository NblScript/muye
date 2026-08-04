from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from httpx import ASGITransport, AsyncClient
import pytest

from app.routes.health import (
    check_pipeline_runtime_health,
    check_runtime_config_health,
    check_yolo_model_health,
)
from app.services.smoke_yolo_service import create_smoke_yolo_app


ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT_DIR / "data" / "samples" / "aphids_01.jpg"


@pytest.mark.asyncio
async def test_smoke_yolo_is_explicit_and_returns_deterministic_detection() -> None:
    transport = ASGITransport(app=create_smoke_yolo_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["mode"] == "smoke_fake"
        assert health.json()["is_simulated"] is True

        response = await client.post(
            "/detect",
            files={
                "images": (
                    SAMPLE_PATH.name,
                    SAMPLE_PATH.read_bytes(),
                    "image/jpeg",
                )
            },
            data={"confidence_threshold": "0.25"},
        )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["image"] == SAMPLE_PATH.name
    assert result["detections"] == [
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


def test_backend_health_labels_smoke_yolo_without_claiming_model_exists(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MUYE_CONTAINER_SMOKE", "true")

    yolo = check_yolo_model_health()
    runtime = check_runtime_config_health()

    assert yolo == {
        "status": "ok",
        "active_model": "container-smoke-fake",
        "model_path": None,
        "model_exists": False,
        "device": "fake",
        "available_models": [],
        "mode": "smoke_fake",
        "is_simulated": True,
    }
    assert runtime["yolo_mode"] == "smoke_fake"
    assert runtime["yolo_is_simulated"] is True


def test_pipeline_health_waits_for_cross_process_ready_marker(
    monkeypatch,
    tmp_path,
) -> None:
    ready_path = tmp_path / "runtime" / "pipeline.ready"
    monkeypatch.setenv("MUYE_PIPELINE_READY_FILE", str(ready_path))

    assert check_pipeline_runtime_health()["status"] == "error"
    ready_path.parent.mkdir(parents=True)
    ready_path.write_text("ready\n", encoding="utf-8")

    assert check_pipeline_runtime_health() == {
        "status": "ok",
        "ready": True,
        "path": str(ready_path),
    }


def test_fake_yolo_uvicorn_target_refuses_implicit_start() -> None:
    env = os.environ.copy()
    env.pop("MUYE_CONTAINER_SMOKE", None)
    result = subprocess.run(
        [sys.executable, "-c", "import app.smoke_yolo_api"],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "refusing to start fake YOLO" in result.stderr
