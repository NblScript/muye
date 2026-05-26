"""In-process SLO metrics collector.

Tracks the four SLOs defined in RELIABILITY.md:
- API success rate (99%): non-5xx response ratio
- Pipeline completion rate (95%): completed / total tasks
- WebSocket connection stability (99%): successful / total connections
- System availability (99.9%): uptime ratio
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WindowCounter:
    """Sliding-window counter over a 60-second window."""

    window_seconds: int = 60
    _timestamps: deque[float] = field(default_factory=deque)

    def record(self) -> None:
        self._timestamps.append(time.time())

    def count(self) -> int:
        cutoff = time.time() - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps)


class SLOMetrics:
    """Thread-safe in-process SLO metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.time()

        # API request counters (sliding 60s window)
        self._api_total = WindowCounter()
        self._api_5xx = WindowCounter()

        # Pipeline counters (cumulative)
        self._pipeline_total = 0
        self._pipeline_completed = 0
        self._pipeline_errored = 0

        # WebSocket counters (cumulative)
        self._ws_connects = 0
        self._ws_disconnects = 0

    # -- API request tracking (called from middleware) --

    def record_request(self, status_code: int) -> None:
        with self._lock:
            self._api_total.record()
            if status_code >= 500:
                self._api_5xx.record()

    # -- Pipeline tracking (called from task lifecycle) --

    def record_pipeline_start(self) -> None:
        with self._lock:
            self._pipeline_total += 1

    def record_pipeline_complete(self) -> None:
        with self._lock:
            self._pipeline_completed += 1

    def record_pipeline_error(self) -> None:
        with self._lock:
            self._pipeline_errored += 1

    # -- WebSocket tracking --

    def record_ws_connect(self) -> None:
        with self._lock:
            self._ws_connects += 1

    def record_ws_disconnect(self) -> None:
        with self._lock:
            self._ws_disconnects += 1

    # -- Snapshot --

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            uptime_seconds = now - self._start_time

            api_total = self._api_total.count()
            api_5xx = self._api_5xx.count()
            api_success_rate = (
                round((api_total - api_5xx) / api_total, 4) if api_total > 0 else 1.0
            )

            pipeline_total = self._pipeline_total
            pipeline_completed = self._pipeline_completed
            pipeline_errored = self._pipeline_errored
            pipeline_rate = (
                round(pipeline_completed / pipeline_total, 4)
                if pipeline_total > 0
                else 1.0
            )

            ws_total = self._ws_connects + self._ws_disconnects
            ws_stability = (
                round(self._ws_connects / ws_total, 4) if ws_total > 0 else 1.0
            )

            return {
                "uptime_seconds": round(uptime_seconds, 1),
                "api": {
                    "success_rate": api_success_rate,
                    "target": 0.99,
                    "ok": api_success_rate >= 0.99,
                    "total_60s": api_total,
                    "errors_60s": api_5xx,
                },
                "pipeline": {
                    "completion_rate": pipeline_rate,
                    "target": 0.95,
                    "ok": pipeline_rate >= 0.95,
                    "total": pipeline_total,
                    "completed": pipeline_completed,
                    "errored": pipeline_errored,
                },
                "websocket": {
                    "stability": ws_stability,
                    "target": 0.99,
                    "ok": ws_stability >= 0.99,
                    "connects": self._ws_connects,
                    "disconnects": self._ws_disconnects,
                },
                "availability": {
                    "uptime_hours": round(uptime_seconds / 3600, 2),
                    "target": 0.999,
                    "ok": True,
                },
            }


# Global singleton
_metrics = SLOMetrics()


def get_slo_metrics() -> SLOMetrics:
    return _metrics
