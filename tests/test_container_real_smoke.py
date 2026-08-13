from __future__ import annotations

from pathlib import Path

import pytest

from scripts import container_smoke


def real_state(filename: str) -> dict:
    return {
        "latest_task": {
            "image_path": f"/app/data/images/{filename}",
            "status": "running",
            "detections": [
                {
                    "pest_type": "aphid",
                    "confidence": 0.91,
                    "position": {
                        "x1": 12.0,
                        "y1": 16.0,
                        "x2": 44.0,
                        "y2": 58.0,
                        "coordinate_space": "image_pixel",
                        "image_width": 640,
                        "image_height": 480,
                    },
                }
            ],
        }
    }


def test_validate_real_detections_requires_pixel_provenance() -> None:
    assert container_smoke._validate_real_detections(real_state("sample.jpg"), "sample.jpg") == {
        "aphid": 1
    }

    invalid = real_state("sample.jpg")
    invalid["latest_task"]["detections"][0]["position"].pop("image_width")
    with pytest.raises(container_smoke.SmokeCheckError, match="missing image dimensions"):
        container_smoke._validate_real_detections(invalid, "sample.jpg")


def test_run_real_model_smoke_crosses_public_http_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sample = tmp_path / "aphid.jpg"
    sample.write_bytes(b"image-fixture")

    def fake_json(url: str, **kwargs) -> dict:
        if url.endswith("/live"):
            return {"status": "ok"}
        if url.endswith("/health"):
            return {
                "status": "ok",
                "checks": {
                    "pipeline_runtime": {"status": "ok", "ready": True},
                    "yolo_model": {
                        "status": "ok",
                        "model_exists": True,
                        "model_path": "/app/models/best.pt",
                    },
                },
            }
        if url.endswith("/api/demo/upload-image"):
            return {"filename": "uploaded-aphid.jpg"}
        if url.endswith("/api/workflow/state"):
            return real_state("uploaded-aphid.jpg")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(container_smoke, "request_json", fake_json)
    monkeypatch.setattr(
        container_smoke,
        "request_bytes",
        lambda *_args, **_kwargs: (200, b"<html>muye</html>", "text/html"),
    )

    container_smoke.run_real_model_smoke(
        backend_url="http://backend",
        frontend_url="http://frontend",
        sample_path=sample,
        pipeline_timeout=1,
    )

    assert "real-model container smoke passed" in capsys.readouterr().out


def test_run_real_model_smoke_rejects_simulated_health(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "aphid.jpg"
    sample.write_bytes(b"image-fixture")

    responses = iter(
        [
            {"status": "ok"},
            {
                "status": "ok",
                "checks": {
                    "pipeline_runtime": {"status": "ok", "ready": True},
                    "yolo_model": {
                        "status": "ok",
                        "model_exists": True,
                        "mode": "smoke_fake",
                        "is_simulated": True,
                    },
                },
            },
        ]
    )
    monkeypatch.setattr(container_smoke, "request_json", lambda *_args, **_kwargs: next(responses))

    with pytest.raises(container_smoke.SmokeCheckError, match="simulated YOLO"):
        container_smoke.run_real_model_smoke(
            backend_url="http://backend",
            frontend_url="http://frontend",
            sample_path=sample,
            pipeline_timeout=1,
        )
