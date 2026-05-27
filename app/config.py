"""Unified configuration management using environment variables."""

from __future__ import annotations

import os
from typing import Any


def truthy_env(name: str) -> bool:
    """Check if an environment variable is truthy."""
    return os.getenv(name, "false").lower() in {"1", "true", "yes", "on"}


def current_mode_labels() -> dict[str, str]:
    """Get current mode labels for dashboard display."""
    drone_backend = os.getenv("DRONE_BACKEND", "px4").lower()
    drone_mode = {
        "px4": "px4",
    }.get(drone_backend, "px4")
    return {
        "yolo": "real",
        "weather": "mock" if truthy_env("QWEATHER_USE_MOCK") else "real",
        "qwen": "mock" if truthy_env("QWEN_USE_MOCK") else "real",
        "drone": drone_mode,
    }


def resolve_loopback_host(host: str) -> str:
    """Resolve loopback host for local URLs."""
    if host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    return host


def build_local_yolo_urls(host: str, port: int) -> tuple[str, str]:
    """Build local YOLO API URLs."""
    access_host = resolve_loopback_host(host)
    detect_url = f"http://{access_host}:{port}/detect"
    health_url = f"http://{access_host}:{port}/health"
    return detect_url, health_url
