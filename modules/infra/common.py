from __future__ import annotations

import json
import logging
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterable

import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
LOGS_DIR = DATA_DIR / "logs"


def ensure_runtime_dirs() -> None:
    for directory in (CONFIG_DIR, DATA_DIR, IMAGES_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def load_environment(env_file: Path | None = None) -> Path:
    ensure_runtime_dirs()
    target = env_file or CONFIG_DIR / "api_keys.env"
    if target.exists():
        load_dotenv(target, override=False)
    return target


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def build_logger(name: str = "muye") -> logging.Logger:
    ensure_runtime_dirs()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        LOGS_DIR / "system.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def generate_request_id() -> str:
    return uuid.uuid4().hex


def _serialize_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    request_id: str,
    client_ip: str = "127.0.0.1",
    duration_ms: float | None = None,
    **fields: Any,
) -> None:
    parts = [f"request_id={request_id}", f"client_ip={client_ip}"]
    if duration_ms is not None:
        parts.append(f"duration_ms={duration_ms:.2f}")
    for key, value in fields.items():
        parts.append(f"{key}={_serialize_value(value)}")
    logger.log(level, f"{message} | {' '.join(parts)}")


def point_in_polygon(point: Iterable[float], polygon: list[list[float]]) -> bool:
    x, y = point
    inside = False
    total = len(polygon)
    for index in range(total):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % total]
        if _point_on_segment(x, y, x1, y1, x2, y2):
            return True
        on_vertical_span = (y1 > y) != (y2 > y)
        if not on_vertical_span:
            continue
        denominator = (y2 - y1) or 1e-12
        x_intersection = (x2 - x1) * (y - y1) / denominator + x1
        if x < x_intersection:
            inside = not inside
    return inside


def _point_on_segment(
    x: float,
    y: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> bool:
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > 1e-9:
        return False

    min_x, max_x = sorted((x1, x2))
    min_y, max_y = sorted((y1, y2))
    return min_x - 1e-9 <= x <= max_x + 1e-9 and min_y - 1e-9 <= y <= max_y + 1e-9


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def strip_code_fence(content: str) -> str:
    candidate = content.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return candidate
