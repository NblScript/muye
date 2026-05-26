"""Tests for the API rate limiting middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.middleware import RateLimitMiddleware


def _make_app(limit: int = 5) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit_per_minute=limit)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_allows_requests_under_limit():
    app = _make_app(limit=5)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(5):
            resp = await client.get("/test")
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_blocks_requests_over_limit():
    app = _make_app(limit=3)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            assert (await client.get("/test")).status_code == 200
        resp = await client.get("/test")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


@pytest.mark.asyncio
async def test_429_response_body():
    app = _make_app(limit=1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/test")
        resp = await client.get("/test")
    assert resp.status_code == 429
    assert resp.json()["detail"] == "请求过于频繁，请稍后再试"


@pytest.mark.asyncio
async def test_websocket_skips_rate_limit():
    """WebSocket upgrades should bypass rate limiting."""
    app = _make_app(limit=1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First request uses up the limit.
        assert (await client.get("/test")).status_code == 200
        # This is still a GET, but the middleware should bypass rate limiting
        # because the upgrade header is present.
        resp = await client.get("/test", headers={"upgrade": "websocket"})
    assert resp.status_code == 200
