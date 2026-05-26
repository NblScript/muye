"""Tests for the API rate limiting middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware


def _make_app(limit: int = 5) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit_per_minute=limit)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


def test_allows_requests_under_limit():
    app = _make_app(limit=5)
    client = TestClient(app)
    for _ in range(5):
        resp = client.get("/test")
        assert resp.status_code == 200


def test_blocks_requests_over_limit():
    app = _make_app(limit=3)
    client = TestClient(app)
    for _ in range(3):
        assert client.get("/test").status_code == 200
    resp = client.get("/test")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_429_response_body():
    app = _make_app(limit=1)
    client = TestClient(app)
    client.get("/test")
    resp = client.get("/test")
    assert resp.status_code == 429
    assert resp.json()["detail"] == "请求过于频繁，请稍后再试"


def test_websocket_skips_rate_limit():
    """WebSocket upgrades should bypass rate limiting."""
    app = _make_app(limit=1)
    # Just verify the middleware doesn't crash on WS upgrade headers
    # (actual WS testing requires a running server)
    from starlette.testclient import TestClient as StarletteClient
    client = StarletteClient(app)
    # First request uses up the limit
    assert client.get("/test").status_code == 200
    # WS upgrade header should bypass rate limiting
    resp = client.get("/test", headers={"upgrade": "websocket"})
    # This is still a GET (TestClient doesn't do real WS), but the middleware
    # should let it through since the upgrade header is present
    assert resp.status_code == 200
