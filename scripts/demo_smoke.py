from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from modules.decision.ai_decision import DecisionEngine
from io import BytesIO

from modules.detection.local_yolo_api import LocalYoloApiService, LocalYoloSettings
from modules.infra.event_bus import FileEventBus, load_events
from modules.infra.weather import WeatherClient


class FakePredictor:
    model_path = Path("smoke-fake-yolo.pt")

    def predict(
        self,
        image_paths: list[Path],
        confidence_threshold: float,
    ) -> list[dict[str, Any]]:
        return [
            {
                "image": path.name,
                "detections": [
                    {
                        "pest_type": "aphid",
                        "confidence": max(confidence_threshold, 0.91),
                        "position": {"x1": 10, "y1": 12, "x2": 80, "y2": 96},
                    }
                ],
            }
            for path in image_paths
        ]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


async def check_frontend_api() -> None:
    from app.routes.health import api_health, api_slo
    from app.routes.workflow import get_workflow_state

    health = await api_health()
    health_status = health.get("status") if isinstance(health, dict) else getattr(health, "status_code", None)
    require(health_status in {"ok", 503}, f"unexpected health response: {health_status}")

    workflow = await get_workflow_state()
    require(workflow.latest_task.request_id, "workflow state missing latest task")

    slo = await api_slo()
    require("api" in slo and "success_rate" in slo["api"], "SLO snapshot missing API success rate")


def check_event_bus() -> None:
    with tempfile.TemporaryDirectory(prefix="muye-smoke-events-") as temp_dir:
        path = Path(temp_dir) / "events.jsonl"
        bus = FileEventBus(path=path)
        bus.publish(
            request_id="smoke-request",
            stage="smoke",
            status="ok",
            message="smoke event",
            payload={"source": "demo_smoke"},
        )
        events = load_events(path)
        require(len(events) == 1, "event bus did not persist the smoke event")
        require(events[0]["request_id"] == "smoke-request", "event bus returned wrong request_id")


async def check_yolo_api() -> None:
    settings = LocalYoloSettings(
        host="127.0.0.1",
        port=8010,
        model_path=Path("smoke-fake-yolo.pt"),
        device="cpu",
        api_key="",
        allowed_ips=[],
        rate_limit_per_minute=120,
        max_batch_size=4,
        model_name="smoke",
        available_models={"smoke": {"path": "smoke-fake-yolo.pt", "device": "cpu"}},
    )
    service = LocalYoloApiService(settings=settings, predictor=FakePredictor())

    class Upload:
        filename = "leaf.jpg"
        file = BytesIO(b"not-a-real-image-but-nonempty")

    payload = await service.detect(
        [Upload()],
        confidence_threshold=0.25,
        request_id="smoke-request",
        client_ip="127.0.0.1",
    )
    detections = payload["results"][0]["detections"]
    require(detections and detections[0]["pest_type"] == "aphid", "YOLO smoke detection missing")


async def check_mock_decision() -> None:
    weather_client = WeatherClient(
        geo_api_url="",
        weather_api_url="",
        api_key="",
        use_mock=True,
        mock_weather={
            "temperature": "26",
            "humidity": "70",
            "summary": "cloudy",
            "wind_direction": "SE",
            "wind_scale_text": "2",
            "wind_speed": "3.3",
        },
    )
    engine = DecisionEngine(
        api_url="",
        api_key="",
        model="mock",
        weather_client=weather_client,
        use_mock=True,
    )
    try:
        bundle = await engine.generate_decision(
            pest_detections=[
                {
                    "pest_type": "aphid",
                    "confidence": 0.92,
                    "position": {"x1": 10, "y1": 12, "x2": 80, "y2": 96},
                }
            ],
            field_context={
                "field_id": "smoke-field",
                "weather_location": "Zhengzhou",
                "location": {"city": "Zhengzhou"},
                "area_mu": 1.0,
                "crop_cycle": {"crop_name": "wheat"},
            },
            request_id="smoke-request",
        )
    finally:
        await engine.close()
        await weather_client.close()

    require(float(bundle["weather"]["humidity"]) == 70.0, "mock weather did not return expected humidity")
    require("用药" in bundle["decision"], "mock decision missing medication section")


def main() -> None:
    print("[smoke] frontend api", flush=True)
    asyncio.run(check_frontend_api())
    print("[smoke] event bus", flush=True)
    check_event_bus()
    print("[smoke] yolo api", flush=True)
    asyncio.run(check_yolo_api())
    print("[smoke] mock decision", flush=True)
    asyncio.run(check_mock_decision())
    print("demo smoke passed")


if __name__ == "__main__":
    main()
