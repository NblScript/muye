"""Integration tests for health and live endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_live_returns_ok(client):
    resp = await client.get("/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_live_api_mirror(client):
    resp = await client.get("/api/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_checks(client):
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "checks" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_slo_returns_metrics(client):
    resp = await client.get("/slo")
    assert resp.status_code == 200
    data = resp.json()
    assert "api" in data or "api_success_rate" in data
