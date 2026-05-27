"""Rate limiting + SLO metrics middleware for the Muye API."""

from __future__ import annotations

import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.slo import get_slo_metrics


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter with SLO metrics recording.

    Tracks request timestamps per client IP and rejects requests that exceed
    the configured limit within a 60-second window. Also records request
    status codes for SLO API success rate tracking.
    """

    def __init__(self, app, limit_per_minute: int = 120) -> None:
        super().__init__(app)
        self.limit_per_minute = max(limit_per_minute, 1)
        self._records: dict[str, deque[float]] = {}
        self._max_ips = 10_000

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for WebSocket upgrades
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.time()
        window_start = now - 60
        bucket = self._records.setdefault(ip, deque())

        # Evict stale entries
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        # Evict empty buckets when IP count exceeds limit
        if len(self._records) > self._max_ips:
            self._records = {
                k: v for k, v in self._records.items() if v
            }

        if len(bucket) >= self.limit_per_minute:
            retry_after = int(bucket[0] - window_start) + 1
            get_slo_metrics().record_request(429)
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        response = await call_next(request)
        get_slo_metrics().record_request(response.status_code)
        return response
