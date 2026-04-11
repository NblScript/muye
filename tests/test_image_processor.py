from __future__ import annotations

import httpx
import pytest

from modules.image_processor import ImageProcessingError, ImageProcessor


@pytest.mark.asyncio
async def test_image_processor_filters_low_confidence_results(tmp_path) -> None:
    image_file = tmp_path / "field.jpg"
    image_file.write_bytes(b"fake-jpeg")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "detections": [
                    {
                        "pest_type": "aphid",
                        "confidence": 0.92,
                        "position": {"x": 10, "y": 20, "w": 30, "h": 40},
                    },
                    {
                        "pest_type": "beneficial-insect",
                        "confidence": 0.12,
                        "position": {"x": 5, "y": 6, "w": 7, "h": 8},
                    },
                ]
            },
        )

    processor = ImageProcessor(
        api_url="https://yolo.test/detect",
        confidence_threshold=0.25,
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await processor.detect_pests(image_file, request_id="req-image-1")
    finally:
        await processor.close()

    assert result == [
        {
            "pest_type": "aphid",
            "confidence": 0.92,
            "position": {"x1": 10.0, "y1": 20.0, "x2": 40.0, "y2": 60.0},
        }
    ]


@pytest.mark.asyncio
async def test_image_processor_raises_on_invalid_payload(tmp_path) -> None:
    image_file = tmp_path / "invalid.jpg"
    image_file.write_bytes(b"fake-jpeg")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": []})

    processor = ImageProcessor(
        api_url="https://yolo.test/detect",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(ImageProcessingError):
            await processor.detect_pests(image_file, request_id="req-image-2")
    finally:
        await processor.close()
