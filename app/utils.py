"""Shared utility functions extracted from MuyeApplication."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from modules.infra.common import log_event


def evaluate_effectiveness(
    pre_count: int, post_count: int, threshold: float,
) -> tuple[float, str]:
    """Calculate kill rate and determine if threshold is met."""
    if pre_count <= 0:
        return 1.0, "passed"
    kill_rate = (pre_count - post_count) / pre_count
    status = "passed" if kill_rate >= threshold else "retry_scheduled"
    return kill_rate, status


def parse_action_time(text: str) -> float | None:
    """Parse Chinese action time expressions like '24小时', '48-72小时' to hours."""
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-~到至]\s*(\d+(?:\.\d+)?)\s*小时", text)
    if match:
        return float(match.group(2))
    match = re.search(r"(\d+(?:\.\d+)?)\s*小时", text)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)\s*天", text)
    if match:
        return float(match.group(1)) * 24
    return None


def safe_sqlite_write(
    logger: logging.Logger,
    request_id: str,
    client_ip: str,
    sqlite_path: str,
    operation: str,
    callback: Callable[[], None],
) -> None:
    try:
        callback()
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "SQLite 写入失败",
            request_id=request_id,
            client_ip=client_ip,
            operation=operation,
            sqlite_path=sqlite_path,
            error=str(exc),
        )
