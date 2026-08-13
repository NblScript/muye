"""Uvicorn target for the explicitly enabled container smoke YOLO API."""

from __future__ import annotations

import os

from app.services.smoke_yolo_service import create_smoke_yolo_app


if os.getenv("MUYE_CONTAINER_SMOKE", "").strip().lower() not in {
    "1",
    "true",
    "yes",
    "on",
}:
    raise RuntimeError(
        "refusing to start fake YOLO without MUYE_CONTAINER_SMOKE=true"
    )


app = create_smoke_yolo_app()
